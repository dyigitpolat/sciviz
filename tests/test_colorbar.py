"""Focused tests for the measured ColorBar element."""

from __future__ import annotations

import pytest

from sciviz import Canvas, Theme
from sciviz.elements._matrix import ColorBar, ColorScale


def _render(element):
    theme = Theme()
    size = element.measure(theme)
    canvas = Canvas()
    element.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size, canvas, theme


def _assert_ink_within_measure(size, canvas):
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= -1e-6
    assert y0 >= -1e-6
    assert x1 <= size.w + 1e-6
    assert y1 <= size.h + 1e-6


def test_vertical_colorbar_is_measured_and_renders_numeric_legend():
    bar = ColorBar(
        ColorScale((-1, 1), center=0),
        ticks=(-1, 0, 1),
        end_labels=("negative", "positive"),
        label="synergy",
    )
    svg, size, canvas, _ = _render(bar)
    assert "<linearGradient" in svg
    assert ">-1<" in svg and ">0<" in svg and ">1<" in svg
    assert "negative" in svg and "positive" in svg and "synergy" in svg
    assert size.w > 0 and size.h > 0
    _assert_ink_within_measure(size, canvas)


def test_horizontal_colorbar_supports_callable_tick_format():
    bar = ColorBar(
        ColorScale((0, 10), palette="emeralds"),
        orientation="horizontal",
        ticks=(0, 5, 10),
        tick_format=lambda value: f"{value:.0f} ms",
        end_labels=("low", "high"),
        label="latency",
    )
    svg, size, canvas, _ = _render(bar)
    assert "0 ms" in svg and "5 ms" in svg and "10 ms" in svg
    assert "low" in svg and "high" in svg and "latency" in svg
    _assert_ink_within_measure(size, canvas)


def test_colorbar_gradient_places_asymmetric_center_at_data_position():
    theme = Theme()
    scale = ColorScale((-1, 3), center=0)
    stops = scale.gradient_stops(theme)
    middle_color = theme.palette("diverging")[4]
    middle = [offset for offset, color in stops if color == middle_color]
    assert middle == pytest.approx([0.25])


def test_colorbar_gradient_reverses_colors_not_numeric_axis():
    theme = Theme()
    normal = ColorScale((0, 1), palette="blues")
    reverse = ColorScale((0, 1), palette="blues", reverse=True)
    assert normal.color(theme, 0) == reverse.color(theme, 1)
    assert normal.color(theme, 1) == reverse.color(theme, 0)
    reverse_stops = reverse.gradient_stops(theme)
    assert reverse_stops[0][1] == theme.palette("blues")[-1]
    assert reverse_stops[-1][1] == theme.palette("blues")[0]


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"orientation": "diagonal"}, ValueError),
        ({"ticks": "some"}, ValueError),
        ({"ticks": (-1, 2)}, ValueError),
        ({"tick_format": object()}, TypeError),
        ({"end_labels": ("only",)}, ValueError),
    ],
)
def test_colorbar_rejects_invalid_configuration(kwargs, error):
    with pytest.raises(error):
        ColorBar(ColorScale((0, 1)), **kwargs)
