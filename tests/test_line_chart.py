"""Tests for :class:`sciviz.LineChart`."""

from __future__ import annotations

import pytest

from sciviz import (
    Annotate,
    Canvas,
    DEFAULT_THEME,
    LineChart,
    Series,
    SeriesDelta,
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


def test_line_chart_inside_top_left_legend():
    chart = LineChart(
        [Series([(0, 0), (1, 1)], label="method")],
        legend="inside-top-left",
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 300)
    assert "method" in svg
    assert "<rect" in svg


def test_series_delta_interpolates_and_draws_directed_relation():
    chart = LineChart(
        [
            Series([(0, 0.8), (1, 0.6)], label="upper"),
            Series([(0, 0.3), (1, 0.2)], label="lower"),
        ],
        deltas=[SeriesDelta(
            x=1, source="upper", target="lower", label="3×\nlower"
        )],
    )
    canvas = Canvas()
    chart.render(canvas, 0, 0, DEFAULT_THEME)
    svg = canvas.to_svg(500, 300)
    assert "marker-end" in svg
    assert ">3×<" in svg and ">lower<" in svg


def test_series_delta_stops_at_target_marker_edge():
    """The delta arrowhead must land on the target marker's edge, not
    its centre, so it never occludes the data point."""
    import re

    def arrow_end_y(marked: bool) -> float:
        chart = LineChart(
            [
                Series([(0, 0.2), (1, 0.2)], label="low"),
                Series([(0, 0.9), (1, 0.9)], label="high",
                       marker="diamond" if marked else None,
                       marker_size="md"),
            ],
            deltas=[SeriesDelta(x=0.5, source="low", target="high",
                                label="up")],
        )
        canvas = Canvas()
        chart.render(canvas, 0, 0, DEFAULT_THEME)
        svg = canvas.to_svg(500, 300)
        m = re.search(r'<line [^>]*y2="([0-9.]+)"[^>]*marker-end', svg)
        assert m is not None
        return float(m.group(1))

    # Arrow points upward (smaller y). With a marker on the target the
    # arrow must stop short -- at a larger y than the marker centre.
    assert arrow_end_y(marked=True) > arrow_end_y(marked=False)


def test_series_delta_rejects_unknown_series():
    with pytest.raises(ValueError):
        LineChart(
            [Series([(0, 0), (1, 1)], label="known")],
            deltas=[SeriesDelta(1, "known", "missing", "delta")],
        )


def test_series_hollow_marker_uses_background_fill():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)], marker="circle",
                       marker_fill="hollow", color="blue")],
        x_range=(0, 1), y_range=(0, 1),
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 300)
    bg = DEFAULT_THEME.color_of("bg")
    blue = DEFAULT_THEME.color_of("blue")
    # Hollow markers: background fill, series-colour outline.
    assert f'fill="{bg}" stroke="{blue}"' in svg


def test_series_show_line_false_draws_markers_only():
    chart = LineChart(
        series=[Series(points=[(0, 0), (0.5, 0.5), (1, 1)], marker="circle",
                       show_line=False)],
        x_range=(0, 1), y_range=(0, 1),
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 300)
    assert svg.count("<path ") == 0        # no connecting polyline
    assert svg.count("<circle") == 3       # one marker per point


def test_series_marker_only_legend_sample_has_no_line():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)], marker="circle",
                       show_line=False, label="derived")],
        x_range=(0, 1), y_range=(0, 1),
        legend="right",
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(500, 300)
    assert ">derived<" in svg
    # The chart body draws only axes/grid <line> elements; the legend
    # sample for a marker-only series must not add a sample stroke line
    # beyond the marker itself, so markers = points + legend sample.
    assert svg.count("<circle") == 3


def test_series_rejects_bad_marker_fill():
    with pytest.raises(ValueError):
        LineChart(series=[Series(points=[(0, 0), (1, 1)],
                                 marker="circle", marker_fill="open")])


def test_annotate_dot_false_suppresses_anchor_dot():
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)])],
        x_range=(0, 1), y_range=(0, 1),
        annotations=[Annotate(x=0.5, y=0.5, text="pinned", dot=False)],
    )
    c = Canvas()
    chart.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 300)
    assert "pinned" in svg
    assert "<circle" not in svg


def test_rotated_y_label_ink_is_tracked():
    """The rotated y-axis title must feed the ink bbox, or auto-trim
    (Diagram.for_paper) crops it off the left edge.

    Stated against the chart's own gutter rather than against a
    label-less sibling: the title band now reserves the rotated line's
    real ink extent, so the title sits just inside the measured box
    instead of a hair outside it, and a cross-chart comparison would
    read that fix as a regression.
    """
    theme = DEFAULT_THEME
    chart = LineChart(
        series=[Series(points=[(0, 0), (1, 1)])],
        x_range=(0, 1), y_range=(0, 1),
        y_label="membrane share (%)",
    )
    c = Canvas(default_font_family=theme.font_family)
    chart.render(c, 0, 0, theme)
    assert c.ink_bbox is not None
    x0 = c.ink_bbox[0]
    left = chart._pad(theme)[0]
    tick_label_left = left - chart._TICK_GAP - chart._y_tick_width(theme)
    # The rotated title inks left of the y tick labels ...
    assert x0 < tick_label_left
    # ... and still inside the box the chart measured for itself.
    assert x0 >= -0.5


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
