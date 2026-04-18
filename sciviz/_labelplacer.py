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
) -> List[Tuple[Point, str]]:
    """Generate (center, side) candidates at several fractions along the
    segment, offset perpendicularly on each side.
    """
    p1, p2 = segment
    is_horizontal = abs(p1[1] - p2[1]) <= abs(p1[0] - p2[0])
    fracs = [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]
    out: List[Tuple[Point, str]] = []
    # Axis-aligned offsets for horizontal and vertical segments.
    # "above"/"below" use vertical offsets, "left"/"right" use horizontal.
    for t in fracs:
        mid = _lerp_point(p1, p2, t)
        if is_horizontal:
            out.append(((mid[0], mid[1] - gap - h / 2), "above"))
            out.append(((mid[0], mid[1] + gap + h / 2), "below"))
        else:
            out.append(((mid[0] - gap - w / 2, mid[1]), "left"))
            out.append(((mid[0] + gap + w / 2, mid[1]), "right"))
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

    best: Optional[Tuple[float, float, Rect, str]] = None
    # Score tuple: (overlap_area, preference_penalty, distance_to_midpoint_sq)
    p1, p2 = segment
    mid = _lerp_point(p1, p2, 0.5)
    for (cx, cy), side in candidates:
        rect = _rect_at(cx, cy, label_w, label_h)
        overlap = sum(_overlap_area(rect, ob) for ob in obstacles)
        pref_pen = 0 if side == prefer else 1
        d2 = (cx - mid[0]) ** 2 + (cy - mid[1]) ** 2
        score = (overlap, pref_pen, d2)
        if best is None or score < best[:3]:
            best = (overlap, pref_pen, d2, rect, side)
    assert best is not None
    return best[3], "middle"
