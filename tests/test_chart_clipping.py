"""An explicit axis range is a window: ink outside it is not drawn.

Before clipping, a series carrying data beyond an explicit ``x_range`` /
``y_range`` was projected and handed to the canvas whole, so the excluded
part was painted outside the axes -- over the tick labels, over the next
panel, and outside the element's own measured box, which is the one
contract every Element owes its parent.
"""

from __future__ import annotations

import re

import pytest

from sciviz import Diagram, LineChart, Scatter, Series
from sciviz.core import Theme
from sciviz.specialized._clip import (
    clip_polygon,
    clip_polyline,
    clip_segment,
    contains,
)

RECT = (0.0, 0.0, 100.0, 50.0)


# --- the geometry primitives ---------------------------------------------

def test_segment_fully_inside_is_untouched():
    assert clip_segment((10.0, 10.0), (90.0, 40.0), RECT) == (
        (10.0, 10.0), (90.0, 40.0))


def test_segment_fully_outside_is_dropped():
    assert clip_segment((-40.0, -10.0), (-10.0, -5.0), RECT) is None


def test_segment_entering_the_window_starts_at_the_edge():
    head, tail = clip_segment((-50.0, 25.0), (50.0, 25.0), RECT)
    assert head == pytest.approx((0.0, 25.0))
    assert tail == pytest.approx((50.0, 25.0))


def test_a_point_on_the_boundary_survives():
    assert contains(RECT, (0.0, 0.0))
    assert contains(RECT, (100.0, 50.0))
    assert not contains(RECT, (100.5, 50.0))


def test_polyline_that_leaves_and_returns_comes_back_as_two_runs():
    runs = clip_polyline(
        [(10.0, 25.0), (30.0, -20.0), (60.0, -20.0), (80.0, 25.0)], RECT)
    assert len(runs) == 2
    assert runs[0][0] == pytest.approx((10.0, 25.0))
    assert runs[-1][-1] == pytest.approx((80.0, 25.0))
    assert all(contains(RECT, point) for run in runs for point in run)


def test_polygon_is_clipped_to_the_window():
    ring = clip_polygon(
        [(-20.0, -20.0), (120.0, -20.0), (120.0, 70.0), (-20.0, 70.0)], RECT)
    assert ring
    assert all(contains(RECT, point) for point in ring)


# --- the charts -----------------------------------------------------------

def _rendered(element) -> str:
    return Diagram.for_paper(element, theme=Theme()).render()


def _path_coordinates(svg: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for command in re.findall(r'\sd="([^"]+)"', svg):
        for x, y in re.findall(r'(-?\d+\.?\d*)[ ,](-?\d+\.?\d*)', command):
            out.append((float(x), float(y)))
    return out


def test_line_chart_does_not_draw_outside_its_declared_range():
    """A curve running far under an explicit y_range stays out of sight."""
    inside = LineChart(
        [Series([(0.0, 0.0), (10.0, 100.0)], color="blue")],
        x_range=(0.0, 10.0), y_range=(0.0, 100.0),
        width=120.0, height=60.0)
    beyond = LineChart(
        [Series([(0.0, -900.0), (5.0, 0.0), (10.0, 100.0)], color="blue")],
        x_range=(0.0, 10.0), y_range=(0.0, 100.0),
        width=120.0, height=60.0)
    theme = Theme()
    assert beyond.measure(theme).h == inside.measure(theme).h
    lowest = max(y for _x, y in _path_coordinates(_rendered(beyond)))
    box = beyond.measure(theme)
    assert lowest <= box.h + 1.0


def test_line_chart_drops_markers_whose_centre_is_outside():
    theme = Theme()
    chart = LineChart(
        [Series([(5.0, 50.0), (5.0, -400.0)], color="red", marker="circle",
                marker_size=4.0, show_line=False)],
        x_range=(0.0, 10.0), y_range=(0.0, 100.0),
        width=120.0, height=60.0)
    assert _rendered(chart).count("<circle") == 1


def test_scatter_drops_points_outside_its_range():
    theme = Theme()
    seen = Scatter([(0.5, 0.5)], x_range=(0, 1), y_range=(0, 1),
                   width=100.0, height=60.0)
    hidden = Scatter([(0.5, 0.5), (9.0, 9.0)], x_range=(0, 1), y_range=(0, 1),
                     width=100.0, height=60.0)
    assert (_rendered(hidden).count("<circle")
            == _rendered(seen).count("<circle"))


def test_clipping_is_a_no_op_when_the_range_is_automatic():
    """Auto ranges already contain the data, so nothing changes."""
    points = [(0.0, 1.0), (1.0, 4.0), (2.0, 9.0)]
    chart = LineChart([Series(points, color="blue")],
                      width=120.0, height=60.0)
    drawn = _path_coordinates(_rendered(chart))
    assert len(drawn) >= len(points)
