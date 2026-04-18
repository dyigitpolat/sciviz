"""Topological boundary router.

A single, shared path planner used by :class:`sciviz.composition.Flow` and
every other connector primitive.  The planner is pure Python (no canvas
dependency) so it can be unit-tested in isolation.

The design is *topological*: the caller supplies the set of anchor
rectangles (real obstacles) and the set of region rectangles (logical
containers -- panels, dashed Apply / Update boxes, etc.).  Given a source
and destination endpoint, the planner computes which *region boundaries*
the path must cross -- exactly the symmetric difference of the two
endpoints' region ancestors -- and rejects any candidate polyline that
crosses any other region boundary, or intersects any anchor obstacle.

Two rendering helpers consume the planner output:

* :func:`render_orthogonal` -- emits axis-aligned ``<line>`` segments.
* :func:`render_curved`     -- smooths the waypoints into a cardinal
  spline with cardinal endpoint tangents so arrowhead markers line up.

Authors never touch this module directly; :class:`Flow` and friends
invoke it during their render pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle known to the planner.

    ``kind`` is ``"anchor"`` for real content rectangles and ``"region"``
    for logical containers whose boundary can be crossed only when it is
    on the path's required-crossings set.
    """
    x: float
    y: float
    w: float
    h: float
    name: str = ""
    kind: str = "anchor"

    @property
    def left(self) -> float: return self.x
    @property
    def right(self) -> float: return self.x + self.w
    @property
    def top(self) -> float: return self.y
    @property
    def bottom(self) -> float: return self.y + self.h
    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2

    def contains_point(self, px: float, py: float, *, eps: float = 0.0) -> bool:
        return (self.left - eps <= px <= self.right + eps
                and self.top - eps <= py <= self.bottom + eps)


@dataclass(frozen=True)
class Endpoint:
    """An oriented attachment point on an anchor's boundary.

    ``tap_fraction`` shifts the attachment point along its edge:
    0.0 = start of edge (top for vertical sides, left for horizontal),
    0.5 = midpoint (default, center),
    1.0 = end of edge.  Used by :class:`Flowed` to share an anchor
    edge among multiple flows without piling them onto the midpoint.
    """
    anchor: Box
    side: str = "auto"
    tap: float = 8.0
    tap_fraction: float = 0.5


@dataclass(frozen=True)
class Plan:
    """Result of :func:`plan_path`.

    ``waypoints`` is a list of at least 2 (x, y) vertices describing an
    axis-aligned polyline from source to destination.  ``crossings``
    enumerates the region names the path legitimately crosses, for
    debugging and for downstream label placement.
    """
    waypoints: List[Tuple[float, float]]
    crossings: List[str] = field(default_factory=list)
    style_hint: str = "direct"
    resolved_src_side: str = ""
    resolved_dst_side: str = ""


@dataclass(frozen=True)
class CrossPolicy:
    """Tie-breakers for candidate selection."""
    min_tap: float = 1.0
    prefer_fewer_corners: bool = True
    corner_radius: float = 0.0
    tolerance: float = 0.5


DEFAULT_POLICY = CrossPolicy()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def plan_path(src: Endpoint, dst: Endpoint, *,
              anchors: Sequence[Box] = (),
              regions: Sequence[Box] = (),
              policy: CrossPolicy = DEFAULT_POLICY) -> Plan:
    """Compute an orthogonal path from ``src`` to ``dst``.

    The path exits ``src.anchor`` perpendicular to ``src.side`` by at
    least ``src.tap`` pixels, enters ``dst.anchor`` similarly, and
    between those endpoints uses as few right-angle corners as the
    obstacle / region topology allows.

    ``anchors`` must include every real rectangle -- *including* src and
    dst themselves (the planner filters them out so callers do not have
    to).  ``regions`` lists logical containers; their rectangles do not
    block the path on their own, but any boundary the path crosses must
    appear in the required-crossings set (= symmetric difference of the
    two endpoints' region ancestors).
    """
    tol = policy.tolerance

    src_anchor = src.anchor
    dst_anchor = dst.anchor

    obstacles: List[Box] = [a for a in anchors
                            if a is not src_anchor and a is not dst_anchor
                            and not _same_box(a, src_anchor)
                            and not _same_box(a, dst_anchor)]

    src_side = _resolve_side(src_anchor, dst_anchor, src.side)
    dst_side = _resolve_side(dst_anchor, src_anchor, dst.side)

    src_ancestors = _region_ancestors(src_anchor, regions)
    dst_ancestors = _region_ancestors(dst_anchor, regions)
    required_region_names = (set(a.name for a in src_ancestors)
                             ^ set(a.name for a in dst_ancestors))
    forbidden_regions = [r for r in regions
                         if r.name not in required_region_names
                         and r not in src_ancestors and r not in dst_ancestors]

    sx, sy = _side_point_frac(src_anchor, src_side, src.tap_fraction)
    dx, dy = _side_point_frac(dst_anchor, dst_side, dst.tap_fraction)

    src_dir = _outward(src_side)
    dst_dir = _outward(dst_side)

    stap = _clamp_tap(src_anchor, src_dir, src.tap, obstacles, policy)
    dtap = _clamp_tap(dst_anchor, dst_dir, dst.tap, obstacles, policy)
    src_tap = (sx + src_dir[0] * stap, sy + src_dir[1] * stap)
    dst_tap = (dx + dst_dir[0] * dtap, dy + dst_dir[1] * dtap)

    def ok(path: Sequence[Tuple[float, float]], *, skip_endpoints: bool = False) -> bool:
        return _path_valid(path, obstacles, forbidden_regions,
                           src_anchor, dst_anchor,
                           required_region_names, tol,
                           skip_endpoints=skip_endpoints)

    crossings = sorted(required_region_names)

    # ------------------------------------------------------------------
    # Candidate enumeration, shortest-corner-count first.
    # ------------------------------------------------------------------

    # 0. Direct colinear segment -- only meaningful when src and dst sit
    #    on the same axis and their tap directions oppose.
    if _is_opposite(src_dir, dst_dir):
        if src_dir[0] == 0 and abs(sx - dx) < tol:
            cand = [(sx, sy), (dx, dy)]
            if ok(cand):
                return Plan(cand, crossings, "direct", src_side, dst_side)
        if src_dir[1] == 0 and abs(sy - dy) < tol:
            cand = [(sx, sy), (dx, dy)]
            if ok(cand):
                return Plan(cand, crossings, "direct", src_side, dst_side)

    # 1. Single-corner L.  Elbow at (dx, sy) or (sx, dy) -- only the
    #    variant whose first leg travels in src_dir and whose second leg
    #    arrives against dst_dir can be "clean" (taps absorb into the
    #    outer legs).
    for elbow in _l_elbows(sx, sy, dx, dy, src_dir, dst_dir, tol):
        cand = [(sx, sy), elbow, (dx, dy)]
        cand = _simplify(cand, tol)
        if len(cand) >= 2 and ok(cand):
            return Plan(cand, crossings, "L", src_side, dst_side)

    # 2a. Two-corner U / Z using a bridge column (both endpoints exit
    #     vertically) or a bridge row (both exit horizontally).  The
    #     bridge coord is searched on the *free* interval so neither
    #     vertical nor horizontal leg impales an obstacle.  We try every
    #     free interval in preference order so that a bridge row/column
    #     in a different slab can replace one whose candidate path
    #     happens to be blocked by a two-dimensional obstacle layout
    #     that the 1-D free-interval filter does not see.
    if src_dir[0] == 0 and dst_dir[0] == 0:
        for bridge_y in _bridge_y_candidates(
                src_tap, dst_tap, src_dir, dst_dir, sx, dx, obstacles,
                forbidden_regions, src_anchor, dst_anchor,
                required_region_names, tol):
            cand = [(sx, sy), (sx, bridge_y), (dx, bridge_y), (dx, dy)]
            cand = _simplify(cand, tol)
            if ok(cand):
                return Plan(cand, crossings, "U", src_side, dst_side)

    if src_dir[1] == 0 and dst_dir[1] == 0:
        for bridge_x in _bridge_x_candidates(
                src_tap, dst_tap, src_dir, dst_dir, sy, dy, obstacles,
                forbidden_regions, src_anchor, dst_anchor,
                required_region_names, tol):
            cand = [(sx, sy), (bridge_x, sy), (bridge_x, dy), (dx, dy)]
            cand = _simplify(cand, tol)
            if ok(cand):
                return Plan(cand, crossings, "U", src_side, dst_side)

    # 2b. Mixed-direction single corner: one axis exit and one axis
    #     entry.  Both elbow positions were already tried above, but we
    #     retry without the L tap-direction constraint to cover shapes
    #     the L filter excluded.
    for elbow in ((dx, sy), (sx, dy)):
        cand = [(sx, sy), elbow, (dx, dy)]
        cand = _simplify(cand, tol)
        if len(cand) >= 2 and ok(cand):
            return Plan(cand, crossings, "L", src_side, dst_side)

    # 3. Staircase fallback: exit tap, cross bridge, enter tap.  We
    #    enumerate multiple bridge candidates (free intervals) and pick
    #    whichever valid candidate has the shortest total length after
    #    simplification.  This lets the router prefer an "up and over"
    #    detour when a "down and under" detour would be equivalent in
    #    corner count but runs closer to other anchors.
    def _score(cand: Sequence[Tuple[float, float]]) -> float:
        total = 0.0
        for i in range(len(cand) - 1):
            ax, ay = cand[i]
            bx, by = cand[i + 1]
            total += abs(bx - ax) + abs(by - ay)
        return total

    best_cand = None
    best_score = float("inf")
    if src_dir[0] == 0 and dst_dir[0] == 0:
        bridge_y_cands = _bridge_y_candidates(
            src_tap, dst_tap, src_dir, dst_dir,
            src_tap[0], dst_tap[0], obstacles,
            forbidden_regions, src_anchor, dst_anchor,
            required_region_names, tol, allow_any=True)
        if not bridge_y_cands:
            bridge_y_cands = [(src_tap[1] + dst_tap[1]) / 2]
        bridge_x_cands = _best_bridge_x_for_vertical_all(
            src_tap, dst_tap, obstacles, forbidden_regions,
            src_anchor, dst_anchor, required_region_names, tol) \
            or [(src_tap[0] + dst_tap[0]) / 2]
        for bridge_y in bridge_y_cands:
            for bridge_x in bridge_x_cands:
                cand = [(sx, sy), src_tap,
                        (bridge_x, src_tap[1]), (bridge_x, dst_tap[1]),
                        dst_tap, (dx, dy)]
                cand = _simplify(cand, tol)
                if ok(cand, skip_endpoints=True):
                    score = _score(cand)
                    if score < best_score:
                        best_score = score
                        best_cand = cand
    elif src_dir[1] == 0 and dst_dir[1] == 0:
        bridge_x_cands = _bridge_x_candidates(
            src_tap, dst_tap, src_dir, dst_dir,
            src_tap[1], dst_tap[1], obstacles,
            forbidden_regions, src_anchor, dst_anchor,
            required_region_names, tol, allow_any=True)
        if not bridge_x_cands:
            bridge_x_cands = [(src_tap[0] + dst_tap[0]) / 2]
        bridge_y_cands = _bridge_y_for_horizontal_candidates(
            src_tap, dst_tap, obstacles, forbidden_regions,
            src_anchor, dst_anchor, required_region_names, tol) \
            or [(src_tap[1] + dst_tap[1]) / 2]
        for bridge_y in bridge_y_cands:
            for bridge_x in bridge_x_cands:
                cand = [(sx, sy), src_tap,
                        (src_tap[0], bridge_y), (dst_tap[0], bridge_y),
                        dst_tap, (dx, dy)]
                cand = _simplify(cand, tol)
                if ok(cand, skip_endpoints=True):
                    score = _score(cand)
                    if score < best_score:
                        best_score = score
                        best_cand = cand
    else:
        corner = (dst_tap[0], src_tap[1]) if src_dir[0] == 0 \
            else (src_tap[0], dst_tap[1])
        cand = [(sx, sy), src_tap, corner, dst_tap, (dx, dy)]
        cand = _simplify(cand, tol)
        if ok(cand, skip_endpoints=True):
            best_cand = cand

    if best_cand is not None:
        return Plan(best_cand, crossings, "staircase", src_side, dst_side)

    # 4. Last-resort corridor: always emit *something* -- the caller
    #    prefers an ugly route over a missing arrow.
    fallback = [(sx, sy), src_tap, dst_tap, (dx, dy)]
    return Plan(_simplify(fallback, tol), crossings, "fallback",
                src_side, dst_side)


# ---------------------------------------------------------------------------
# Side / orientation helpers
# ---------------------------------------------------------------------------

def _resolve_side(self_box: Box, other_box: Box, side: str) -> str:
    if side != "auto":
        return side
    dx = other_box.cx - self_box.cx
    dy = other_box.cy - self_box.cy
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def _side_point(box: Box, side: str) -> Tuple[float, float]:
    mapping = {
        "top":         (box.cx, box.top),
        "bottom":      (box.cx, box.bottom),
        "left":        (box.left, box.cy),
        "right":       (box.right, box.cy),
        "topleft":     (box.left, box.top),
        "topright":    (box.right, box.top),
        "bottomleft":  (box.left, box.bottom),
        "bottomright": (box.right, box.bottom),
    }
    return mapping.get(side, (box.cx, box.cy))


def _side_point_frac(box: Box, side: str, frac: float) -> Tuple[float, float]:
    """Point on ``side`` at relative position ``frac`` along the edge.

    For ``top`` / ``bottom`` the edge runs from left to right, so
    ``frac=0`` is the left corner and ``frac=1`` is the right corner.
    For ``left`` / ``right`` the edge runs from top to bottom.

    A small inset (``inset_px``) keeps the tap away from the exact
    corner so the shaft never exits the rounded panel border visibly.
    """
    inset_px = min(4.0, box.w * 0.2, box.h * 0.2)
    frac = max(0.0, min(1.0, frac))
    if side in ("top", "bottom"):
        lo = box.left + inset_px
        hi = box.right - inset_px
        if hi <= lo:
            lo, hi = box.left, box.right
        x = lo + (hi - lo) * frac
        y = box.top if side == "top" else box.bottom
        return (x, y)
    if side in ("left", "right"):
        lo = box.top + inset_px
        hi = box.bottom - inset_px
        if hi <= lo:
            lo, hi = box.top, box.bottom
        y = lo + (hi - lo) * frac
        x = box.left if side == "left" else box.right
        return (x, y)
    # Corners and unknown sides: fall back to the existing midpoint
    # mapping so callers always get a concrete point on the boundary.
    return _side_point(box, side)


def _outward(side: str) -> Tuple[int, int]:
    return {
        "top":         (0, -1),
        "bottom":      (0, +1),
        "left":        (-1, 0),
        "right":       (+1, 0),
        "topleft":     (0, -1),
        "topright":    (0, -1),
        "bottomleft":  (0, +1),
        "bottomright": (0, +1),
    }.get(side, (0, 0))


def _is_opposite(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return a[0] + b[0] == 0 and a[1] + b[1] == 0 and (a[0] or a[1])


def _same_box(a: Box, b: Box) -> bool:
    return (abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6
            and abs(a.w - b.w) < 1e-6 and abs(a.h - b.h) < 1e-6)


# ---------------------------------------------------------------------------
# Region ancestry (containment DAG)
# ---------------------------------------------------------------------------

def _region_ancestors(anchor: Box, regions: Sequence[Box]) -> List[Box]:
    ancestors = [r for r in regions
                 if r.contains_point(anchor.cx, anchor.cy, eps=0.5)]
    ancestors.sort(key=lambda r: r.w * r.h)
    return ancestors


# ---------------------------------------------------------------------------
# Tap clamping
# ---------------------------------------------------------------------------

def _clamp_tap(anchor: Box, direction: Tuple[int, int],
               base_tap: float, obstacles: Sequence[Box],
               policy: CrossPolicy) -> float:
    if direction == (0, -1):
        edge = anchor.top
        ahead = [o.bottom for o in obstacles
                 if o.left < anchor.right and o.right > anchor.left
                 and o.bottom <= edge + 0.5]
        nearest = max(ahead) if ahead else None
        limit = edge - nearest - 2 if nearest is not None else base_tap
    elif direction == (0, +1):
        edge = anchor.bottom
        ahead = [o.top for o in obstacles
                 if o.left < anchor.right and o.right > anchor.left
                 and o.top >= edge - 0.5]
        nearest = min(ahead) if ahead else None
        limit = nearest - edge - 2 if nearest is not None else base_tap
    elif direction == (-1, 0):
        edge = anchor.left
        ahead = [o.right for o in obstacles
                 if o.top < anchor.bottom and o.bottom > anchor.top
                 and o.right <= edge + 0.5]
        nearest = max(ahead) if ahead else None
        limit = edge - nearest - 2 if nearest is not None else base_tap
    elif direction == (+1, 0):
        edge = anchor.right
        ahead = [o.left for o in obstacles
                 if o.top < anchor.bottom and o.bottom > anchor.top
                 and o.left >= edge - 0.5]
        nearest = min(ahead) if ahead else None
        limit = nearest - edge - 2 if nearest is not None else base_tap
    else:
        limit = base_tap
    return max(policy.min_tap, min(base_tap, limit))


# ---------------------------------------------------------------------------
# Candidate L-elbow selection
# ---------------------------------------------------------------------------

def _l_elbows(sx: float, sy: float, dx: float, dy: float,
              src_dir: Tuple[int, int], dst_dir: Tuple[int, int],
              tol: float) -> List[Tuple[float, float]]:
    """Return the L-corner candidates that respect src/dst exit dirs."""
    elbows = []
    # (sx, dy) -- first leg moves along y from sy to dy, second along x.
    if src_dir[0] == 0 and dst_dir[1] == 0:
        first = (dy - sy) * src_dir[1]
        second = (sx - dx) * dst_dir[0]
        if first > -tol and second > -tol:
            elbows.append((sx, dy))
    # (dx, sy) -- first leg moves along x from sx to dx, second along y.
    if src_dir[1] == 0 and dst_dir[0] == 0:
        first = (dx - sx) * src_dir[0]
        second = (sy - dy) * dst_dir[1]
        if first > -tol and second > -tol:
            elbows.append((dx, sy))
    return elbows


# ---------------------------------------------------------------------------
# Bridge coord search
# ---------------------------------------------------------------------------

def _free_intervals_1d(lo: float, hi: float,
                        blocks: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if hi <= lo:
        return []
    intervals = [(lo, hi)]
    for (a, b) in blocks:
        next_intervals = []
        for (u, v) in intervals:
            if b <= u or a >= v:
                next_intervals.append((u, v))
                continue
            if a > u:
                next_intervals.append((u, a))
            if b < v:
                next_intervals.append((b, v))
        intervals = next_intervals
    return [(a, b) for (a, b) in intervals if b - a > 0.5]


def _best_bridge_y(src_tap, dst_tap, src_dir, dst_dir,
                   xa: float, xb: float, obstacles, forbidden_regions,
                   src_anchor: Box, dst_anchor: Box,
                   required_region_names: set, tol: float,
                   *, allow_any: bool = False) -> Optional[float]:
    cands = _bridge_y_candidates(src_tap, dst_tap, src_dir, dst_dir,
                                 xa, xb, obstacles, forbidden_regions,
                                 src_anchor, dst_anchor,
                                 required_region_names, tol,
                                 allow_any=allow_any)
    return cands[0] if cands else None


def _bridge_y_candidates(src_tap, dst_tap, src_dir, dst_dir,
                         xa: float, xb: float, obstacles, forbidden_regions,
                         src_anchor: Box, dst_anchor: Box,
                         required_region_names: set, tol: float,
                         *, allow_any: bool = False) -> List[float]:
    """Return candidate bridge-y values sorted by preference.  The
    top-ranked candidate is the old ``_best_bridge_y`` return value; we
    also include one point per free interval so plan_path can fall
    through to an alternative bridge row if the preferred one's
    candidate path crosses a different obstacle not visible to the 1-D
    free-interval filter.
    """
    x_lo, x_hi = (xa, xb) if xa <= xb else (xb, xa)
    blocks = []
    for o in obstacles:
        if o.right < x_lo - tol or o.left > x_hi + tol:
            continue
        blocks.append((o.top, o.bottom))
    for r in forbidden_regions:
        if r.right < x_lo - tol or r.left > x_hi + tol:
            continue
        blocks.append((r.top, r.bottom))
    same_vert = (src_dir[1] != 0 and src_dir[1] == dst_dir[1])
    sy = src_tap[1]
    dy = dst_tap[1]
    if same_vert:
        ext = 400.0
        if src_dir[1] > 0:
            lo = max(src_anchor.bottom, dst_anchor.bottom)
            hi = max(sy, dy) + ext
            target = max(sy, dy) + 6.0
        else:
            lo = min(sy, dy) - ext
            hi = min(src_anchor.top, dst_anchor.top)
            target = min(sy, dy) - 6.0
    else:
        lo = min(sy, dy)
        hi = max(sy, dy)
        if allow_any:
            lo -= 200.0
            hi += 200.0
        target = (sy + dy) / 2
    free = _free_intervals_1d(lo, hi, blocks)
    if not free:
        return []
    if same_vert:
        if src_dir[1] > 0:
            free_sorted = sorted(free, key=lambda iv: iv[0])
        else:
            free_sorted = sorted(free, key=lambda iv: -iv[1])
    else:
        free_sorted = sorted(free, key=lambda iv: (abs((iv[0]+iv[1])/2 - target), -(iv[1]-iv[0])))
    out = []
    for (a, b) in free_sorted:
        out.append(max(a + 2, min(b - 2, target)))
    return out


def _best_bridge_x(src_tap, dst_tap, src_dir, dst_dir,
                   ya: float, yb: float, obstacles, forbidden_regions,
                   src_anchor: Box, dst_anchor: Box,
                   required_region_names: set, tol: float,
                   *, allow_any: bool = False) -> Optional[float]:
    cands = _bridge_x_candidates(src_tap, dst_tap, src_dir, dst_dir,
                                 ya, yb, obstacles, forbidden_regions,
                                 src_anchor, dst_anchor,
                                 required_region_names, tol,
                                 allow_any=allow_any)
    return cands[0] if cands else None


def _bridge_x_candidates(src_tap, dst_tap, src_dir, dst_dir,
                         ya: float, yb: float, obstacles, forbidden_regions,
                         src_anchor: Box, dst_anchor: Box,
                         required_region_names: set, tol: float,
                         *, allow_any: bool = False) -> List[float]:
    y_lo, y_hi = (ya, yb) if ya <= yb else (yb, ya)
    blocks = []
    for o in obstacles:
        if o.bottom < y_lo - tol or o.top > y_hi + tol:
            continue
        blocks.append((o.left, o.right))
    for r in forbidden_regions:
        if r.bottom < y_lo - tol or r.top > y_hi + tol:
            continue
        blocks.append((r.left, r.right))
    same_horiz = (src_dir[0] != 0 and src_dir[0] == dst_dir[0])
    sx = src_tap[0]
    dx = dst_tap[0]
    if same_horiz:
        ext = 400.0
        if src_dir[0] > 0:
            lo = max(src_anchor.right, dst_anchor.right)
            hi = max(sx, dx) + ext
            target = lo + 2
        else:
            lo = min(sx, dx) - ext
            hi = min(src_anchor.left, dst_anchor.left)
            target = hi - 2
    else:
        lo = min(sx, dx)
        hi = max(sx, dx)
        if allow_any:
            lo -= 200.0
            hi += 200.0
        target = (sx + dx) / 2
    free = _free_intervals_1d(lo, hi, blocks)
    if not free:
        return []
    if same_horiz:
        if src_dir[0] > 0:
            free_sorted = sorted(free, key=lambda iv: iv[0])
        else:
            free_sorted = sorted(free, key=lambda iv: -iv[1])
    else:
        free_sorted = sorted(free, key=lambda iv: (abs((iv[0]+iv[1])/2 - target), -(iv[1]-iv[0])))
    out = []
    for (a, b) in free_sorted:
        out.append(max(a + 2, min(b - 2, target)))
    return out


def _best_bridge_x_for_vertical(src_tap, dst_tap, obstacles,
                                forbidden_regions,
                                src_anchor, dst_anchor,
                                required_region_names, tol) -> float:
    """Pick an x clear of anchor obstacles and forbidden regions.

    Scans the inter-anchor slab first, then extends outside it when no
    free interval is found inside.
    """
    y_lo = min(src_tap[1], dst_tap[1])
    y_hi = max(src_tap[1], dst_tap[1])
    if src_tap[0] <= dst_tap[0]:
        inner_lo = src_anchor.right
        inner_hi = dst_anchor.left
    else:
        inner_lo = dst_anchor.right
        inner_hi = src_anchor.left
    blocks = []
    for o in obstacles:
        if o.bottom < y_lo - tol or o.top > y_hi + tol:
            continue
        blocks.append((o.left, o.right))
    for r in forbidden_regions:
        if r.bottom < y_lo - tol or r.top > y_hi + tol:
            continue
        blocks.append((r.left, r.right))
    if inner_hi > inner_lo:
        free = _free_intervals_1d(inner_lo, inner_hi, blocks)
        if free:
            widest = max(free, key=lambda iv: iv[1] - iv[0])
            return (widest[0] + widest[1]) / 2
    ext_lo = min(src_anchor.left, dst_anchor.left) - 400.0
    ext_hi = max(src_anchor.right, dst_anchor.right) + 400.0
    free = _free_intervals_1d(ext_lo, ext_hi, blocks)
    if free:
        target = (src_tap[0] + dst_tap[0]) / 2
        return _pick_closest_in_intervals(free, target)
    return (src_tap[0] + dst_tap[0]) / 2


def _best_bridge_y_for_horizontal(src_tap, dst_tap, obstacles,
                                  forbidden_regions,
                                  src_anchor, dst_anchor,
                                  required_region_names, tol) -> float:
    cs = _bridge_y_for_horizontal_candidates(
        src_tap, dst_tap, obstacles, forbidden_regions,
        src_anchor, dst_anchor, required_region_names, tol)
    return cs[0] if cs else (src_tap[1] + dst_tap[1]) / 2


def _bridge_y_for_horizontal_candidates(src_tap, dst_tap, obstacles,
                                        forbidden_regions,
                                        src_anchor, dst_anchor,
                                        required_region_names, tol) -> List[float]:
    x_lo = min(src_tap[0], dst_tap[0])
    x_hi = max(src_tap[0], dst_tap[0])
    if src_tap[1] <= dst_tap[1]:
        inner_lo = src_anchor.bottom
        inner_hi = dst_anchor.top
    else:
        inner_lo = dst_anchor.bottom
        inner_hi = src_anchor.top
    blocks = []
    for o in obstacles:
        if o.right < x_lo - tol or o.left > x_hi + tol:
            continue
        blocks.append((o.top, o.bottom))
    for r in forbidden_regions:
        if r.right < x_lo - tol or r.left > x_hi + tol:
            continue
        blocks.append((r.top, r.bottom))
    target = (src_tap[1] + dst_tap[1]) / 2
    inner_candidates: List[float] = []
    if inner_hi > inner_lo:
        inner_free = _free_intervals_1d(inner_lo, inner_hi, blocks)
        for (a, b) in inner_free:
            inner_candidates.append((a + b) / 2)
    ext_lo = min(src_anchor.top, dst_anchor.top) - 400.0
    ext_hi = max(src_anchor.bottom, dst_anchor.bottom) + 400.0
    ext_free = _free_intervals_1d(ext_lo, ext_hi, blocks)
    ext_candidates: List[float] = []
    for (a, b) in ext_free:
        clamp = max(a + 6.0, min(b - 6.0, target))
        ext_candidates.append(clamp)
    merged = list(inner_candidates) + ext_candidates
    seen: List[float] = []
    for c in sorted(merged, key=lambda v: abs(v - target)):
        if all(abs(c - s) > 2.0 for s in seen):
            seen.append(c)
    return seen


def _best_bridge_x_for_vertical_all(src_tap, dst_tap, obstacles,
                                    forbidden_regions,
                                    src_anchor, dst_anchor,
                                    required_region_names, tol) -> List[float]:
    y_lo = min(src_tap[1], dst_tap[1])
    y_hi = max(src_tap[1], dst_tap[1])
    if src_tap[0] <= dst_tap[0]:
        inner_lo = src_anchor.right
        inner_hi = dst_anchor.left
    else:
        inner_lo = dst_anchor.right
        inner_hi = src_anchor.left
    blocks = []
    for o in obstacles:
        if o.bottom < y_lo - tol or o.top > y_hi + tol:
            continue
        blocks.append((o.left, o.right))
    for r in forbidden_regions:
        if r.bottom < y_lo - tol or r.top > y_hi + tol:
            continue
        blocks.append((r.left, r.right))
    target = (src_tap[0] + dst_tap[0]) / 2
    inner: List[float] = []
    if inner_hi > inner_lo:
        for (a, b) in _free_intervals_1d(inner_lo, inner_hi, blocks):
            inner.append((a + b) / 2)
    ext_lo = min(src_anchor.left, dst_anchor.left) - 400.0
    ext_hi = max(src_anchor.right, dst_anchor.right) + 400.0
    ext: List[float] = []
    for (a, b) in _free_intervals_1d(ext_lo, ext_hi, blocks):
        ext.append(max(a + 6.0, min(b - 6.0, target)))
    merged = list(inner) + ext
    seen: List[float] = []
    for c in sorted(merged, key=lambda v: abs(v - target)):
        if all(abs(c - s) > 2.0 for s in seen):
            seen.append(c)
    return seen


def _pick_closest_in_intervals(free: List[Tuple[float, float]],
                                target: float, *,
                                clearance: float = 6.0) -> float:
    """Return the point inside ``free`` nearest to ``target``.

    For each interval, the closest interior point is the clamp of
    ``target`` to ``[a+clearance, b-clearance]``.  Clearance defaults to
    6 px so bridge rows/columns sit a readable distance from obstacle
    edges, not a single pixel off (which causes rendered strokes to
    graze adjacent boxes).
    """
    def candidate(iv):
        a, b = iv
        inside = max(a + clearance, min(b - clearance, target))
        return (abs(inside - target), inside)
    best = min(free, key=lambda iv: candidate(iv)[0])
    return candidate(best)[1]


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def _segment_intersects_box(x1: float, y1: float, x2: float, y2: float,
                             box: Box, tol: float) -> bool:
    if abs(y1 - y2) < tol:
        # Horizontal segment.
        if y1 + tol < box.top or y1 - tol > box.bottom:
            return False
        lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
        if hi + tol < box.left or lo - tol > box.right:
            return False
        # Interior overlap.
        return (min(hi, box.right) - max(lo, box.left)) > tol
    if abs(x1 - x2) < tol:
        # Vertical segment.
        if x1 + tol < box.left or x1 - tol > box.right:
            return False
        lo, hi = (y1, y2) if y1 <= y2 else (y2, y1)
        if hi + tol < box.top or lo - tol > box.bottom:
            return False
        return (min(hi, box.bottom) - max(lo, box.top)) > tol
    # Diagonal -- fall back to a generic swept-AABB test, but we never
    # emit diagonals so this is just a guard.
    return (box.left - tol < max(x1, x2)
            and box.right + tol > min(x1, x2)
            and box.top - tol < max(y1, y2)
            and box.bottom + tol > min(y1, y2))


def _segment_touches_anchor(x1, y1, x2, y2, anchor: Box, tol: float) -> bool:
    """Anchor hit-test that tolerates a segment running along an edge."""
    if abs(y1 - y2) < tol:
        if y1 < anchor.top - tol or y1 > anchor.bottom + tol:
            return False
        if abs(y1 - anchor.top) < tol or abs(y1 - anchor.bottom) < tol:
            return False
        lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
        return (min(hi, anchor.right) - max(lo, anchor.left)) > tol
    if abs(x1 - x2) < tol:
        if x1 < anchor.left - tol or x1 > anchor.right + tol:
            return False
        if abs(x1 - anchor.left) < tol or abs(x1 - anchor.right) < tol:
            return False
        lo, hi = (y1, y2) if y1 <= y2 else (y2, y1)
        return (min(hi, anchor.bottom) - max(lo, anchor.top)) > tol
    return False


def _path_valid(path: Sequence[Tuple[float, float]],
                 obstacles: Sequence[Box],
                 forbidden_regions: Sequence[Box],
                 src_anchor: Box, dst_anchor: Box,
                 required_region_names: set,
                 tol: float,
                 *, skip_endpoints: bool = False) -> bool:
    if len(path) < 2:
        return False
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        if abs(x1 - x2) < tol and abs(y1 - y2) < tol:
            continue
        for o in obstacles:
            if _segment_touches_anchor(x1, y1, x2, y2, o, tol):
                return False
        for r in forbidden_regions:
            if _segment_intersects_box(x1, y1, x2, y2, r, tol):
                return False
        # Endpoint-through-own-anchor is allowed -- but only for the
        # first and last segments.
        if skip_endpoints and (i == 0 or i == len(path) - 2):
            continue
        if _segment_touches_anchor(x1, y1, x2, y2, src_anchor, tol):
            return False
        if _segment_touches_anchor(x1, y1, x2, y2, dst_anchor, tol):
            return False
    return True


# ---------------------------------------------------------------------------
# Polyline utilities
# ---------------------------------------------------------------------------

def _simplify(points: Sequence[Tuple[float, float]],
              tol: float) -> List[Tuple[float, float]]:
    if not points:
        return []
    out = [tuple(points[0])]
    for p in points[1:]:
        if (abs(p[0] - out[-1][0]) > tol
                or abs(p[1] - out[-1][1]) > tol):
            out.append(tuple(p))
    # Drop colinear middles.
    cleaned = [out[0]]
    for i in range(1, len(out) - 1):
        ax, ay = cleaned[-1]
        bx, by = out[i]
        cx, cy = out[i + 1]
        if (abs(ax - bx) < tol and abs(bx - cx) < tol) or (
                abs(ay - by) < tol and abs(by - cy) < tol):
            continue
        cleaned.append(out[i])
    if len(out) >= 2:
        cleaned.append(out[-1])
    return cleaned


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_orthogonal(canvas, plan: Plan, *,
                       stroke: str, width: float,
                       dasharray: Optional[str] = None,
                       marker_end=None,
                       src_dot: bool = True) -> List[Tuple[float, float, float, float]]:
    """Draw ``plan`` as axis-aligned ``<line>`` segments.

    Returns the list of segment rectangles ``(x0, y0, x1, y1)`` so a
    caller can place a label without re-computing them.
    """
    pts = plan.waypoints
    if len(pts) < 2:
        return []
    rects: List[Tuple[float, float, float, float]] = []
    last = len(pts) - 2
    for i in range(last + 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        attrs = {"stroke": stroke, "stroke_width": width}
        if dasharray:
            attrs["dasharray"] = dasharray
        if marker_end is not None and i == last:
            attrs["marker_end"] = marker_end
        canvas.line(x1, y1, x2, y2, **attrs)
        rects.append((min(x1, x2) - width, min(y1, y2) - width,
                       max(x1, x2) + width, max(y1, y2) + width))
    if src_dot:
        sx, sy = pts[0]
        canvas.circle(sx, sy, r=width * 1.4, fill=stroke, stroke="none")
    return rects


def render_curved(canvas, plan: Plan, *,
                   stroke: str, width: float,
                   dasharray: Optional[str] = None,
                   marker_end=None,
                   curvature: float = 0.5,
                   src_dot: bool = True) -> None:
    """Smooth ``plan.waypoints`` into a cardinal spline path.

    Endpoint tangents are aligned with the first / last emitted
    segments, so arrow markers (`orient="auto"`) point correctly.
    """
    pts = plan.waypoints
    if len(pts) < 2:
        return
    if len(pts) == 2:
        x1, y1 = pts[0]
        x2, y2 = pts[1]
        d = f"M {x1:.2f},{y1:.2f} L {x2:.2f},{y2:.2f}"
        canvas.path(d, stroke=stroke, fill="none", stroke_width=width,
                    marker_end=marker_end, dasharray=dasharray)
        if src_dot:
            canvas.circle(x1, y1, r=width * 1.4, fill=stroke, stroke="none")
        return
    tension = max(0.0, min(1.0, curvature)) * 0.5
    pieces = [f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"]
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1x = p1[0] + (p2[0] - p0[0]) * tension
        c1y = p1[1] + (p2[1] - p0[1]) * tension
        c2x = p2[0] - (p3[0] - p1[0]) * tension
        c2y = p2[1] - (p3[1] - p1[1]) * tension
        pieces.append(f"C {c1x:.2f},{c1y:.2f} "
                      f"{c2x:.2f},{c2y:.2f} "
                      f"{p2[0]:.2f},{p2[1]:.2f}")
    canvas.path(" ".join(pieces), stroke=stroke, fill="none",
                stroke_width=width, marker_end=marker_end,
                dasharray=dasharray)
    if src_dot:
        sx, sy = pts[0]
        canvas.circle(sx, sy, r=width * 1.4, fill=stroke, stroke="none")


# ---------------------------------------------------------------------------
# Small helper to fetch a shared marker -- kept here so every connector
# primitive gets an identical arrowhead.
# ---------------------------------------------------------------------------

def arrow_marker(canvas, theme, color: str, stroke_width: float,
                  name_hint: str = "flow"):
    return canvas.define_arrow_marker(
        color=color,
        stroke_width=stroke_width,
        arrow_size=getattr(theme, "arrow_size", None),
        name_hint=name_hint,
    )
