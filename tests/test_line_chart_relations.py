from __future__ import annotations

import pytest

from sciviz.core import Canvas, DEFAULT_THEME
from sciviz.specialized._linechart import FillBetween, LineChart, Series


def render(chart: LineChart) -> str:
    size = chart.measure(DEFAULT_THEME)
    canvas = Canvas()
    chart.render(canvas, 0, 0, DEFAULT_THEME)
    return canvas.to_svg(size.w, size.h)


def test_fill_between_interpolates_and_renders_below_lines():
    chart = LineChart(
        [Series([(0, 0), (2, 2)], label="low", key="low", marker="circle"),
         Series([(0, 2), (1, 3), (2, 4)], label="high", key="high",
                marker="square")],
        fills=[FillBetween("low", "high")],
        x_range=(0, 2), y_range=(0, 4),
    )
    svg = render(chart)
    polygon = svg.index("<polygon")
    first_line_path = svg.index("<path", polygon)
    assert polygon < first_line_path
    assert svg.count("<circle") >= 2
    assert svg.count("<rect") >= 3  # background plus square markers


def test_fill_between_derives_labels_from_both_series():
    chart = LineChart(
        [Series([(0, 1), (1, 2)], key="low"),
         Series([(0, 2), (1, 4)], key="high", color="positive")],
        fills=[FillBetween(
            "low",
            "high",
            labels=lambda _x, low, high: f"+{high - low:.1f}",
        )],
        x_range=(0, 1),
        y_range=(0, 4),
    )
    svg = render(chart)
    assert ">+1.0<" in svg
    assert ">+2.0<" in svg
    assert f'fill="{DEFAULT_THEME.color_of("positive")}"' in svg


def test_semantic_size_token_and_inside_legend():
    chart = LineChart(
        [Series([(0, 0), (1, 1)], label="A", marker="circle")],
        size="lg",
        legend="inside-bottom-right",
    )
    assert chart.width == 360.0
    assert chart.height == 210.0
    svg = render(chart)
    assert ">A<" in svg
    assert f'fill="{DEFAULT_THEME.color_of("bg")}"' in svg


def test_explicit_ticks_and_formatters_are_honored():
    chart = LineChart(
        [Series([(0, 1), (2, 3)])],
        x_range=(0, 2), y_range=(1, 3),
        x_ticks=(0, 1, 2), y_ticks=(1, 2, 3),
        x_tick_format=lambda value: f"x={value:.0f}",
        y_tick_format=".1f",
    )
    svg = render(chart)
    assert "x=0" in svg and "x=1" in svg and "x=2" in svg
    assert "1.0" in svg and "2.0" in svg and "3.0" in svg


def test_fill_between_rejects_unknown_series_key():
    with pytest.raises(ValueError, match="unknown series"):
        LineChart(
            [Series([(0, 0), (1, 1)], key="known")],
            fills=[FillBetween("known", "missing")],
        )


def test_marker_name_is_validated():
    with pytest.raises(ValueError, match="Series.marker"):
        LineChart([Series([(0, 0), (1, 1)], marker="star")])
