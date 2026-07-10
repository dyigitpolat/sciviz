from __future__ import annotations

import pytest

from sciviz.charts._donut import DonutChart, GroupSummary, Part
from sciviz.core import Canvas, DEFAULT_THEME


def render(chart: DonutChart) -> str:
    size = chart.measure(DEFAULT_THEME)
    canvas = Canvas()
    chart.render(canvas, 0, 0, DEFAULT_THEME)
    return canvas.to_svg(size.w, size.h)


def test_donut_renders_one_sector_per_part_and_outside_labels():
    chart = DonutChart([
        Part("a", 40, label="Alpha"),
        Part("b", 35, label="Beta"),
        Part("c", 25, label="Gamma"),
    ])
    svg = render(chart)
    assert svg.count("<path") == 3
    assert "Alpha 40%" in svg
    assert "Beta 35%" in svg
    assert "Gamma 25%" in svg
    assert svg.count("<line") >= 3


def test_donut_group_summary_is_derived_from_parts():
    chart = DonutChart(
        [Part("v1", 40, group="video"),
         Part("v2", 40, group="video"),
         Part("image", 20, group="image")],
        center=GroupSummary(("video", "image"), label="mix"),
        labels=None,
    )
    svg = render(chart)
    assert "mix" in svg
    assert "80 / 20" in svg


def test_single_part_is_drawn_as_two_half_arcs():
    svg = render(DonutChart([Part("whole", 1)], labels=None))
    assert svg.count("<path") == 2


def test_arc_ink_bounds_stay_inside_the_measured_chart():
    chart = DonutChart(
        [Part("a", 20), Part("b", 30), Part("c", 50)],
        size="lg",
    )
    size = chart.measure(DEFAULT_THEME)
    canvas = Canvas()
    chart.render(canvas, 0, 0, DEFAULT_THEME)
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= -DEFAULT_THEME.unit
    assert y0 >= -DEFAULT_THEME.unit
    assert x1 <= size.w + DEFAULT_THEME.unit
    assert y1 <= size.h + DEFAULT_THEME.unit


@pytest.mark.parametrize(
    "parts, kwargs, message",
    [
        ([Part("bad", -1)], {}, "nonnegative"),
        ([Part("zero", 0)], {}, "positive"),
        ([Part("a", 1)], {"total": 2}, "explicit total"),
    ],
)
def test_donut_rejects_invalid_part_totals(parts, kwargs, message):
    with pytest.raises(ValueError, match=message):
        DonutChart(parts, **kwargs)
