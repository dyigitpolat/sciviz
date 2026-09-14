"""The chart marker vocabulary is reusable as a legend swatch.

Motivating case (AgentEvolve AAAI-27 chance-baseline figure): five
allocation policies distinguished only by marker shape and fill. The
legend had no way to show the plotted glyph -- authors were reduced to
embedding a one-point chart per legend entry, which drags an axis and
tick labels along with it. :class:`Marker` is the glyph itself, and the
charts draw through the same helper, so a legend cannot disagree with the
plot it explains.
"""
from __future__ import annotations

import pytest

from sciviz import (Legend, LegendItem, LineChart, Marker, Palette, Series,
                    Slopegraph, Theme)
from sciviz.core import Canvas
from sciviz.elements._marker import SHAPES, draw_marker, marker_radius


THEME = Theme()


def _svg(element) -> str:
    box = element.measure(THEME)
    canvas = Canvas(default_font_family=THEME.font_family)
    element.render(canvas, 0.0, 0.0, THEME)
    return canvas.to_svg(box.w, box.h)


def test_every_shape_renders():
    for shape in SHAPES:
        svg = _svg(Marker(shape, color=Palette.red))
        assert "<circle" in svg or "<rect" in svg or "<polygon" in svg


def test_marker_ink_stays_inside_its_measured_box():
    for shape in SHAPES:
        marker = Marker(shape, color=Palette.blue, size="md")
        box = marker.measure(THEME)
        canvas = Canvas(default_font_family=THEME.font_family)
        marker.render(canvas, 0.0, 0.0, THEME)
        x0, y0, x1, y1 = canvas.ink_bbox
        assert x0 >= -0.5 and y0 >= -0.5
        assert x1 <= box.w + 0.5 and y1 <= box.h + 0.5


def test_size_token_and_explicit_radius_agree_with_the_charts():
    # The element resolves sizes through the same helper the charts use.
    assert marker_radius("xs", THEME) == LineChart._marker_radius("xs", THEME)
    assert Marker("circle", size=3.0).measure(THEME).w == pytest.approx(
        2 * 3.0 + THEME.line)


def test_hollow_and_solid_differ():
    solid = _svg(Marker("diamond", color=Palette.red, fill="solid"))
    hollow = _svg(Marker("diamond", color=Palette.red, fill="hollow"))
    assert solid != hollow


def test_legend_item_accepts_a_marker():
    legend = Legend(
        LegendItem(Marker("triangle", color=Palette.gray), "incumbent"),
        LegendItem(Marker("diamond", color=Palette.red, fill="hollow"), "ours"),
    )
    svg = _svg(legend)
    assert "incumbent" in svg and "ours" in svg
    assert "<polygon" in svg


def test_bad_shape_and_fill_are_rejected():
    with pytest.raises(ValueError):
        Marker("star")
    with pytest.raises(ValueError):
        Marker("circle", fill="striped")
    with pytest.raises(ValueError):
        marker_radius("enormous", THEME)


def test_charts_share_the_marker_helper():
    """A shape drawn by the element and by a chart is the same path."""
    canvas_a = Canvas()
    draw_marker(canvas_a, "triangle", 10.0, 10.0, 3.0,
                THEME.color_of(Palette.red), THEME)
    canvas_b = Canvas()
    chart = LineChart([Series([(0.0, 0.0)], marker="triangle")])
    chart._draw_marker(canvas_b, "triangle", 10.0, 10.0, 3.0,
                       THEME.color_of(Palette.red), THEME)
    assert canvas_a.to_svg(20, 20) == canvas_b.to_svg(20, 20)
    canvas_c = Canvas()
    Slopegraph([("a", 1.0, 2.0)])._draw_marker(
        canvas_c, "triangle", 10.0, 10.0, 3.0,
        THEME.color_of(Palette.red), THEME)
    assert canvas_c.to_svg(20, 20) == canvas_a.to_svg(20, 20)
