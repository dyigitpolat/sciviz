"""Tests for :class:`sciviz.LineChart`."""

from __future__ import annotations

import pytest

from sciviz import (
    Annotate,
    Canvas,
    DEFAULT_THEME,
    LineChart,
    Series,
)


def test_line_chart_measures_positive():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)], label="line")],
        x_range=(0, 1), y_range=(0, 1),
        width=200, height=120,
    )
    b = chart.measure(DEFAULT_THEME)
    assert b.w > 200 and b.h > 120


def test_line_chart_renders_series_polyline():
    chart = LineChart(
        series=[Series(points=[(0, 0), (0.5, 0.5), (1.0, 1.0)])],
        x_range=(0, 1), y_range=(0, 1),
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    # Exactly one path is expected for one series.
    assert svg.count('<path ') >= 1


def test_line_chart_multiple_series_auto_color_cycle():
    s1 = Series(points=[(0, 0), (1, 1)])
    s2 = Series(points=[(0, 1), (1, 0)])
    chart = LineChart(series=[s1, s2], x_range=(0, 1), y_range=(0, 1))
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    # Two distinct strokes applied.
    colors = [DEFAULT_THEME.role(DEFAULT_THEME.role_for_index(i))
              for i in (0, 1)]
    for col in colors:
        assert f'stroke="{col}"' in svg


def test_line_chart_series_dict_accepted():
    chart = LineChart(
        series=[dict(points=[(0, 0), (1, 1)], label="viaDict", color="red")],
    )
    chart.measure(DEFAULT_THEME)


def test_line_chart_dash_style():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)], dash="4,3")],
        x_range=(0, 1), y_range=(0, 1),
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    assert 'stroke-dasharray="4,3"' in c.to_svg(400, 400)


def test_line_chart_annotations_render_text():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)])],
        x_range=(0, 1), y_range=(0, 1),
        annotations=[Annotate(x=0.5, y=0.5, text="midpoint")],
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    assert "midpoint" in c.to_svg(400, 400)


def test_line_chart_log_scale():
    chart = LineChart(
        series=[Series(points=[(1, 1), (10, 10), (100, 100)])],
        x_range=(1, 100), y_range=(1, 100),
        log_x=True, log_y=True,
    )
    b = chart.measure(DEFAULT_THEME)
    assert b.w > 0 and b.h > 0


def test_line_chart_rejects_bad_series():
    with pytest.raises(TypeError):
        LineChart(series=[42])


def test_line_chart_rejects_bad_legend():
    with pytest.raises(ValueError):
        LineChart(series=[], legend="inside")


def test_line_chart_legend_right():
    chart = LineChart(
        series=[
            Series(points=[(0, 0), (1, 1)], label="A"),
            Series(points=[(0, 1), (1, 0)], label="B"),
        ],
        x_range=(0, 1), y_range=(0, 1),
        legend="right",
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(500, 300)
    assert ">A<" in svg and ">B<" in svg
