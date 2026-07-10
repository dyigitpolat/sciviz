"""Genericity tests for :class:`GroupedBarChart`.

The chart was motivated by fig03 (2-bar TTRL comparison) but must work
for the general "N series across K groups" pattern without special-
casing.  These tests pin that the chart accepts:

* 1 / 2 / 3+ bars per group,
* tuple and dataclass group shapes,
* each decoration turned on or off independently,
* custom per-series styling via :class:`BarSeries`,
* theme-token colours and hex literals interchangeably,
* auto-scaled y_max when not specified.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (
    BarGroup, BarSeries, Canvas, Diagram, GroupedBarChart, Theme,
)


def _render(chart: GroupedBarChart) -> str:
    d = Diagram(body=chart)
    size = d.measure()
    canvas = Canvas()
    chart.render(canvas, 0.0, 0.0, Theme())
    return canvas.to_svg(size.w, size.h)


# ---- shape coercion ---------------------------------------------------------

def test_accepts_legacy_two_bar_tuple():
    chart = GroupedBarChart([("AIME", 16.7, 43.3, "+159.3%")])
    assert chart.groups[0].values == [16.7, 43.3]
    assert chart.groups[0].annotation == "+159.3%"


def test_accepts_values_list_tuple():
    chart = GroupedBarChart([("X", [1.0, 2.0, 3.0], "note")])
    assert chart.groups[0].values == [1.0, 2.0, 3.0]
    assert chart.groups[0].annotation == "note"


def test_accepts_bargroup_dataclass():
    g = BarGroup("Y", [5.0, 6.0], annotation="x", target=10.0)
    chart = GroupedBarChart([g])
    assert chart.groups[0] is g


def test_rejects_uneven_groups():
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0]), ("B", [1.0, 2.0, 3.0])])


def test_rejects_too_few_series_for_bars():
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0, 3.0])],
                        series=[BarSeries(color="#111")])


# ---- decoration toggles -----------------------------------------------------

def test_decoration_flags_off_produce_no_extra_svg_ops():
    """All toggles off should emit only bars + wash (no cards, axis,
    target lines, delta arrows, values, or titles)."""
    chart = GroupedBarChart(
        [("A", [10.0, 20.0])],
        show_cards=False, show_target_line=False,
        show_delta_arrow=False, show_values=False,
        show_titles=False, show_axis=False,
        y_label="",
    )
    svg = _render(chart)
    # to_svg injects a background <rect>; add chart wash + 2 bars = 4 total.
    assert svg.count("<rect") == 4
    assert "stroke-dasharray" not in svg   # no target line
    assert "<line " not in svg             # no axis, no delta arrow
    assert "<text" not in svg              # no titles/values/axis labels


def test_target_line_only():
    chart = GroupedBarChart(
        [("A", [10.0, 20.0])],
        show_cards=False, show_target_line=True,
        show_delta_arrow=False, show_values=False,
        show_titles=False, show_axis=False,
    )
    svg = _render(chart)
    assert "stroke-dasharray" in svg


def test_delta_arrow_endpoints_configurable():
    """With three bars, the arrow goes from delta_from to delta_to."""
    # Default (0 -> -1): arrow from first (small) to last (large) bar.
    chart = GroupedBarChart(
        [("A", [10.0, 20.0, 80.0])],
        series=[BarSeries(color="#aa0000"),
                BarSeries(color="#00aa00"),
                BarSeries(color="#0000aa")],
        show_cards=False, show_target_line=False,
        show_values=False, show_titles=False, show_axis=False,
    )
    svg = _render(chart)
    # One arrow-marker path exists (via <defs>) and the line refers to it.
    assert "marker-end" in svg


def test_delta_arrow_off_when_disabled():
    chart = GroupedBarChart(
        [("A", [10.0, 80.0])],
        show_cards=False, show_target_line=False,
        show_delta_arrow=False,
        show_values=False, show_titles=False, show_axis=False,
    )
    svg = _render(chart)
    assert "marker-end" not in svg


# ---- axis ------------------------------------------------------------------

def test_auto_y_max_adapts_to_data():
    chart = GroupedBarChart([("A", [5.0, 8.0])])
    # 1.05 * max(8) = 8.4, rounded via y_step=20 we get at least 20.
    assert chart._resolved_y_max() >= 8.4


def test_explicit_y_max_respected():
    chart = GroupedBarChart([("A", [5.0, 8.0])], y_max=50)
    assert chart._resolved_y_max() == 50.0


def test_semantic_plot_sizes_scale_both_axes():
    small = GroupedBarChart([("A", [1.0])], size="sm")
    large = GroupedBarChart([("A", [1.0])], size="xl")
    assert large.plot_width > small.plot_width
    assert large.plot_height > small.plot_height


def test_rejects_unknown_semantic_plot_size():
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0])], size="enormous")


# ---- series styling ---------------------------------------------------------

def test_series_tuples_and_strings_coerce():
    chart = GroupedBarChart(
        [("A", [1.0, 2.0])],
        series=["#aa0000", ("Treatment", "#0000aa", "#ffffff")],
    )
    assert chart.series[0].color == "#aa0000"
    assert chart.series[1].color == "#0000aa"
    assert chart.series[1].value_color == "#ffffff"
    assert chart.series[1].name == "Treatment"


def test_value_color_auto_contrast():
    """Dark bars get white in-bar labels without explicit configuration."""
    chart = GroupedBarChart(
        [("A", [10.0, 20.0])],
        series=[BarSeries(color="#ffffff"), BarSeries(color="#000000")],
        show_titles=False, show_axis=False, show_cards=False,
        show_target_line=False, show_delta_arrow=False,
    )
    svg = _render(chart)
    # Both in-bar labels appear; white label for the dark bar.
    assert 'fill="#ffffff"' in svg.lower() or "fill=\"#FFFFFF\"" in svg


def test_single_series_works():
    """A 1-bar-per-group chart (ablation bars, simple histogram) renders
    without touching the delta-arrow or target-line code paths."""
    chart = GroupedBarChart(
        [("A", [10.0]), ("B", [20.0]), ("C", [30.0])],
        series=[BarSeries(color="primary_fill")],
        show_delta_arrow=False,
    )
    svg = _render(chart)
    assert "<rect" in svg
    assert svg.count("<text") >= 3       # titles at least


def test_flat_single_series_uses_fitted_category_slots_and_exact_values():
    """Flat categories must fit the axis and keep hundredth precision."""
    chart = GroupedBarChart(
        [BarGroup("Baseline", [4.56], color="#15803d"),
         BarGroup("+IndexShare\n+KVShare", [5.10], color="#cbd1db"),
         BarGroup("+End-to-end", [5.47], color="#3b82f6")],
        y_max=6,
        y_step=1,
        show_cards=False,
        show_target_line=False,
        show_delta_arrow=False,
    )
    theme = Theme()
    offset, panel_w, inter, bar_w, intra, pad = chart._group_geometry(
        theme, chart.plot_width)
    assert offset == 0.0
    assert inter == 0.0
    assert panel_w * len(chart.groups) == pytest.approx(chart.plot_width)
    assert bar_w > 0 and pad >= 0
    svg = _render(chart)
    assert "4.56" in svg and "5.47" in svg
    assert "#15803d" in svg.lower()
    assert "+KVShare" in svg


def test_flat_chart_defaults_to_quiet_horizontal_grid():
    chart = GroupedBarChart(
        [("A", [1.0]), ("B", [2.0])],
        y_max=3, y_step=1,
        show_cards=False, show_target_line=False,
        show_delta_arrow=False,
    )
    svg = _render(chart)
    assert 'opacity="0.18"' in svg


def test_flat_annotation_stacks_above_value_without_collision():
    chart = GroupedBarChart(
        [BarGroup("Final", [5.47], annotation="+20%\nvs Baseline")],
        y_max=6, y_step=1,
        show_cards=False, show_target_line=False,
        show_delta_arrow=False,
    )
    svg = _render(chart)

    def text_y(text):
        match = re.search(rf'<text[^>]*y="([0-9.]+)"[^>]*>{re.escape(text)}<',
                          svg)
        assert match, f"missing {text!r} in {svg}"
        return float(match.group(1))

    value_y = text_y("5.47")
    annotation_bottom_y = text_y("vs Baseline")
    assert value_y - annotation_bottom_y >= Theme().text_height("label")


# ---- theme integration ------------------------------------------------------

def test_theme_tokens_resolve_through_theme_color_of():
    """A chart built entirely from theme tokens renders on both the
    default and slides themes without raising."""
    chart = GroupedBarChart(
        [("A", [20.0, 80.0], "+300%")],
        series=[BarSeries(color="primary_soft"),
                BarSeries(color="primary", value_color="inverse")],
        annotation_color="highlight",
    )
    for theme in (Theme(), Theme.slides()):
        canvas = Canvas()
        bbox = chart.measure(theme)
        chart.render(canvas, 0.0, 0.0, theme)
        assert bbox.w > 0 and bbox.h > 0
