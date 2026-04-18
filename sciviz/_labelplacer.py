"""Pure geometric label placement solver.

Given a line segment (where a connector label *should* sit), a label size
(``(w, h)`` in px), and a set of rectangle obstacles, pick the label
rectangle with minimum overlap and maximum clearance.  Used by :class:`Bus`
and :class:`Flow` so every connector label dodges nearby boxes, arrows,
and other lines automatically without author hints.

Conventions
-----------

* Obstacles are rectangles ``(x0, y0, x1, y1)``.
* Segments are pairs of points ``((x1, y1), (x2, y2))``.
* The returned rectangle ``(x0, y0, x1, y1)`` encloses the label and is
  guaranteed to not overlap any obstacle when possible; if every
  candidate overlaps at least one obstacle, the function returns the
  candidate with least total overlap area.
* The returned ``anchor`` string matches the SVG ``text-anchor`` that
  positions the label's x-coordinate at the CENTRE of the returned rect
  on the x-axis (``"middle"``).  Baseline is at the centre vertically
  (caller offsets appropriately).

Placement strategy
------------------

For each of 5 arc-length fractions along the segment [0.15, 0.3, 0.5,
0.7, 0.85] we try four sides: "above", "below", "left", "right" --
with a small perpendicular offset.  The side preference is an argument
(``prefer``) that acts as a tie-breaker.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple


Rect = Tuple[float, float, float, float]         # (x0, y0, x1, y1)
Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def rects_overlap(a: Rect, b: Rect, eps: float = 0.0) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if ax1 <= bx0 + eps or bx1 <= ax0 + eps:
        return False
    if ay1 <= by0 + eps or by1 <= ay0 + eps:
        return False
    return True


def _overlap_area(a: Rect, b: Rect) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ox = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    oy = max(0.0, min(ay1, by1) - max(ay0, by0))
    return ox * oy


def _min_clearance(rect: Rect, obstacles: Sequence[Rect]) -> float:
    """Smallest L_inf distance from ``rect`` to any obstacle.

    0.0 when some obstacle touches or overlaps.  Larger values mean the
    label sits in more open space.  Used as a tie-breaker so the placer
    prefers candidates that breathe instead of the first one it happens
    to visit.
    """
    ax0, ay0, ax1, ay1 = rect
    best = float("inf")
    for bx0, by0, bx1, by1 in obstacles:
        dx = max(bx0 - ax1, ax0 - bx1, 0.0)
        dy = max(by0 - ay1, ay0 - by1, 0.0)
        d = max(dx, dy)
        if d < best:
            best = d
    if best == float("inf"):
        return 1e9
    return best


def _lerp_point(p1: Point, p2: Point, t: float) -> Point:
    return (p1[0] + (p2[0] - p1[0]) * t,
            p1[1] + (p2[1] - p1[1]) * t)


def _perp(p1: Point, p2: Point) -> Tuple[float, float]:
    """Unit perpendicular to the segment (90 deg clockwise)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return (0.0, 1.0)
    return (dy / length, -dx / length)


def _rect_at(cx: float, cy: float, w: float, h: float) -> Rect:
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _candidate_centers(
    segment: Segment, w: float, h: float, gap: float,
) -> List[Tuple[Point, str, bool]]:
    """Generate (center, side, is_extrapolated) candidates along the
    segment offset perpendicularly on each side.

    Besides the seven in-range fractions we also emit two extrapolated
    candidates just beyond each endpoint so that very short segments
    (or segments flanked on both sides by tall neighbours) still have
    a chance of finding an obstacle-free slot along the spine axis.
    Extrapolated candidates are marked so the placer prefers in-range
    candidates when multiple options share the same overlap/preference
    score.
    """
    p1, p2 = segment
    is_horizontal = abs(p1[1] - p2[1]) <= abs(p1[0] - p2[0])
    in_range = [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]
    out_range = [-0.15, 1.15]
    out: List[Tuple[Point, str, bool]] = []
    for t in in_range + out_range:
        mid = _lerp_point(p1, p2, t)
        extrap = t < 0.0 or t > 1.0
        if is_horizontal:
            out.append(((mid[0], mid[1] - gap - h / 2), "above", extrap))
            out.append(((mid[0], mid[1] + gap + h / 2), "below", extrap))
        else:
            out.append(((mid[0] - gap - w / 2, mid[1]), "left", extrap))
            out.append(((mid[0] + gap + w / 2, mid[1]), "right", extrap))
    return out


def place_label(
    segment: Segment,
    label_w: float,
    label_h: float,
    obstacles: Sequence[Rect] = (),
    *,
    prefer: str = "above",
    gap: float = 1.5,
) -> Tuple[Rect, str]:
    """Return the best label rectangle and its SVG ``text-anchor``.

    The solver minimises overlap area against all ``obstacles``.  Among
    zero-overlap candidates, it prefers ``prefer`` (``"above"``,
    ``"below"``, ``"left"``, ``"right"``), then candidates closest to
    the segment midpoint.
    """
    candidates = _candidate_centers(segment, label_w, label_h, gap)

    # Score tuple:
    #   (overlap_area,              # lower is better
    #    extrapolated_penalty,      # lower is better (prefer in-range first)
    #    preference_penalty,        # lower is better (0 if side == prefer)
    #    -min_clearance,            # lower is better (more breathing room wins)
    #    distance_to_midpoint_sq)   # lower is better (closer to spine centre)
    best: Optional[Tuple[float, float, float, float, float, Rect, str]] = None
    p1, p2 = segment
    mid = _lerp_point(p1, p2, 0.5)
    for (cx, cy), side, extrap in candidates:
        rect = _rect_at(cx, cy, label_w, label_h)
        overlap = sum(_overlap_area(rect, ob) for ob in obstacles)
        extrap_pen = 1 if extrap else 0
        pref_pen = 0 if side == prefer else 1
        clearance = _min_clearance(rect, obstacles)
        d2 = (cx - mid[0]) ** 2 + (cy - mid[1]) ** 2
        score = (overlap, extrap_pen, pref_pen, -clearance, d2)
        if best is None or score < best[:5]:
            best = (overlap, extrap_pen, pref_pen, -clearance, d2, rect, side)
    assert best is not None
    return best[5], "middle"
