"""Clip chart ink to the plot rectangle.

A chart's axis range is a window onto the data, not a suggestion: an
author who writes ``y_range=(98.85, 100.72)`` has said which slice of a
curve the figure is about. Before this module the projected polyline was
handed to the canvas whole, so the part of the data outside the window
was still drawn -- outside the axes, over the tick labels, over the
neighbouring panel, and outside the element's own measured box, which
breaks the bbox contract every :class:`~sciviz.core.Element` owes its
parent (``measure()`` reports all ink ``render()`` can draw).

Every chart therefore clips its series geometry to the plot rectangle
before drawing. When the range is automatic the rectangle already
contains the data and clipping is a no-op, so this only ever changes
figures that were drawing outside their own axes.

Conventions, which follow the usual ones:

* a polyline is clipped segment by segment (Liang--Barsky) and may come
  back as several runs, since a curve can leave the window and return;
* a marker is drawn when its *centre* is inside, whole rather than
  sliced, so a data point on the axis still reads as a data point;
* a filled area is clipped as a polygon (Sutherland--Hodgman against the
  four edges), so a band keeps its outline along the window edge.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]     # (x_min, y_min, x_max, y_max)

# Tolerance for "on the edge", in device units. A point authored exactly at
# the range boundary must survive projection rounding.
EDGE_TOLERANCE = 1e-6


def contains(rect: Rect, point: Point,
             tolerance: float = EDGE_TOLERANCE) -> bool:
    """True when ``point`` lies inside ``rect``, boundary included."""
    x_min, y_min, x_max, y_max = rect
    x, y = point
    return (x_min - tolerance <= x <= x_max + tolerance
            and y_min - tolerance <= y <= y_max + tolerance)


def clip_segment(start: Point, end: Point, rect: Rect
                 ) -> Optional[Tuple[Point, Point]]:
    """Liang--Barsky: the part of ``start``-``end`` inside ``rect``."""
    x_min, y_min, x_max, y_max = rect
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    enter, leave = 0.0, 1.0
    for edge, offset in ((-dx, x0 - x_min), (dx, x_max - x0),
                         (-dy, y0 - y_min), (dy, y_max - y0)):
        if edge == 0.0:
            if offset < -EDGE_TOLERANCE:
                return None                      # parallel and outside
            continue
        crossing = offset / edge
        if edge < 0.0:
            if crossing > leave:
                return None
            enter = max(enter, crossing)
        else:
            if crossing < enter:
                return None
            leave = min(leave, crossing)
    if enter > leave:
        return None
    return ((x0 + enter * dx, y0 + enter * dy),
            (x0 + leave * dx, y0 + leave * dy))


def clip_polyline(points: Sequence[Point], rect: Rect) -> List[List[Point]]:
    """Split a projected polyline into the runs that lie inside ``rect``."""
    if len(points) < 2:
        return [list(points)] if points and contains(rect, points[0]) else []
    runs: List[List[Point]] = []
    current: List[Point] = []
    for start, end in zip(points, points[1:]):
        piece = clip_segment(start, end, rect)
        if piece is None:
            current = []
            continue
        head, tail = piece
        if current and _same(current[-1], head):
            current.append(tail)
            continue
        current = [head, tail]
        runs.append(current)
    return [run for run in runs if len(run) >= 2]


def clip_polygon(points: Sequence[Point], rect: Rect) -> List[Point]:
    """Sutherland--Hodgman: ``points`` clipped against the four edges."""
    x_min, y_min, x_max, y_max = rect
    edges = (
        (lambda p: p[0] >= x_min - EDGE_TOLERANCE, 0, x_min),
        (lambda p: p[0] <= x_max + EDGE_TOLERANCE, 0, x_max),
        (lambda p: p[1] >= y_min - EDGE_TOLERANCE, 1, y_min),
        (lambda p: p[1] <= y_max + EDGE_TOLERANCE, 1, y_max),
    )
    ring: List[Point] = list(points)
    for keep, axis, bound in edges:
        if not ring:
            return []
        clipped: List[Point] = []
        for index, current in enumerate(ring):
            previous = ring[index - 1]
            current_in = keep(current)
            previous_in = keep(previous)
            if current_in:
                if not previous_in:
                    clipped.append(_cross(previous, current, axis, bound))
                clipped.append(current)
            elif previous_in:
                clipped.append(_cross(previous, current, axis, bound))
        ring = clipped
    return ring


def clamp_rect(rect: Rect, bounds: Rect) -> Optional[Rect]:
    """Intersect an ink bbox with the plot rectangle."""
    x0 = max(rect[0], bounds[0])
    y0 = max(rect[1], bounds[1])
    x1 = min(rect[2], bounds[2])
    y1 = min(rect[3], bounds[3])
    if x1 < x0 or y1 < y0:
        return None
    return (x0, y0, x1, y1)


def _same(a: Point, b: Point) -> bool:
    return (abs(a[0] - b[0]) <= EDGE_TOLERANCE
            and abs(a[1] - b[1]) <= EDGE_TOLERANCE)


def _cross(start: Point, end: Point, axis: int, bound: float) -> Point:
    span = end[axis] - start[axis]
    if span == 0.0:
        return end
    ratio = (bound - start[axis]) / span
    other = 1 - axis
    crossed = [0.0, 0.0]
    crossed[axis] = bound
    crossed[other] = start[other] + (end[other] - start[other]) * ratio
    return (crossed[0], crossed[1])
