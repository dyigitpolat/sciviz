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
    Bar, BarGroup, BarSeries, Canvas, Diagram, GroupedBarChart, Theme,
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


# ---- card-mode annotation headroom ------------------------------------------

def _card_top_and_text_baseline(svg: str, text: str):
    """Return (card rect top y, baseline y of the given text run)."""
    card = re.search(r'<rect [^>]*y="(-?[0-9.]+)"[^>]*rx="[0-9.]+"', svg)
    assert card, f"no card rect in {svg}"
    run = re.search(rf'<text[^>]*y="(-?[0-9.]+)"[^>]*>{re.escape(text)}<',
                    svg)
    assert run, f"missing {text!r} in {svg}"
    return float(card.group(1)), float(run.group(1))


def test_card_annotation_near_ymax_stays_inside_card():
    """Regression: with show_cards=True and a target near y_max, the
    annotation stack used to cross the card's top border (the border
    stroke cut through the glyphs).  The card must now reserve enough
    headroom that the annotation's topmost ink stays inside it."""
    theme = Theme()
    chart = GroupedBarChart(
        [("Method", [96.4, 95.2], "W1 / U2  -1.16 pt")],
        y_max=100.0, y_step=10.0,
        plot_width=330.0, plot_height=200.0,
    )
    assert chart._card_annotation_headroom(theme) > 0.0
    svg = _render(chart)
    card_top, ann_y = _card_top_and_text_baseline(svg, "W1 / U2  -1.16 pt")
    # Baseline minus one line height over-approximates the top of the
    # annotation ink; it must clear the card's top border.
    assert ann_y - theme.text_height("small") >= card_top


def test_card_annotation_headroom_covers_multiline_stacks():
    theme = Theme()
    chart = GroupedBarChart(
        [("Method", [97.0, 95.0], "first line\nsecond line")],
        y_max=100.0, y_step=10.0,
    )
    svg = _render(chart)
    card_top, first_y = _card_top_and_text_baseline(svg, "first line")
    assert first_y - theme.text_height("small") >= card_top


def test_card_annotation_headroom_zero_when_target_has_room():
    """Charts whose annotations already fit must render unchanged."""
    theme = Theme()
    chart = GroupedBarChart(
        [("Method", [40.0, 55.0], "+37.5%")],
        y_max=100.0, y_step=20.0,
    )
    assert chart._card_annotation_headroom(theme) == 0.0
    # Flat charts never take card headroom regardless of geometry.
    flat = GroupedBarChart(
        [("Method", [96.4, 95.2], "near top")],
        y_max=100.0, y_step=10.0, show_cards=False,
    )
    assert flat._card_annotation_headroom(theme) == 0.0


def test_card_annotation_headroom_grows_measure_bbox():
    """The taller card is real ink: measure() must report it."""
    theme = Theme()
    tight = GroupedBarChart([("A", [96.4, 95.2], "note")],
                            y_max=100.0, y_step=10.0)
    comfy = GroupedBarChart([("A", [40.0, 55.0], "note")],
                            y_max=100.0, y_step=10.0)
    headroom = tight._card_annotation_headroom(theme)
    assert headroom > 0.0
    assert tight.measure(theme).h == pytest.approx(
        comfy.measure(theme).h + headroom)


# ---- negative values, empty slots, qualified bars ----------------------------

def _bar_rects(svg: str):
    """Return (x, y, w, h) for every plain (non-card, non-wash) bar rect."""
    rects = []
    for m in re.finditer(
            r'<rect x="(-?[0-9.]+)" y="(-?[0-9.]+)" width="([0-9.]+)" '
            r'height="([0-9.]+)"[^>]*/>', svg):
        rects.append(tuple(float(v) for v in m.groups()))
    return rects


def _flat(groups, **kw):
    base = dict(show_cards=False, show_target_line=False,
                show_delta_arrow=False, show_titles=False, show_axis=False,
                grid=False)
    base.update(kw)
    return GroupedBarChart(groups, **base)


def test_negative_values_grow_down_from_zero_baseline():
    chart = _flat([("A", [4.0, -2.0])], y_max=4.0, y_min=-4.0, y_step=2.0,
                  show_values=False)
    svg = _render(chart)
    rects = _bar_rects(svg)
    # background + wash + 2 bars; bars are the last two rects.
    up, down = rects[-2], rects[-1]
    baseline = up[1] + up[3]           # bottom of the positive bar
    assert down[1] == pytest.approx(baseline)          # starts at zero line
    assert down[3] == pytest.approx(up[3] / 2)         # |-2| = half of 4
    assert down[1] + down[3] > baseline                # extends downward


def test_auto_y_min_covers_negative_data():
    chart = GroupedBarChart([("A", [3.0, -2.0])])
    assert chart._resolved_y_min() == pytest.approx(-2.1)
    all_pos = GroupedBarChart([("A", [3.0, 2.0])])
    assert all_pos._resolved_y_min() == 0.0


def test_positive_y_min_rejected():
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0])], y_min=1.0)


def test_negative_axis_ticks_are_labelled():
    chart = GroupedBarChart([("A", [3.0, -2.0])],
                            y_max=4.0, y_min=-4.0, y_step=2.0,
                            show_cards=False, show_target_line=False,
                            show_delta_arrow=False, show_values=False,
                            show_titles=False)
    svg = _render(chart)
    assert ">-2<" in svg and ">-4<" in svg and ">0<" in svg and ">4<" in svg


def test_value_label_sits_below_negative_bar():
    chart = _flat([("A", [4.0, -2.0])], y_max=4.0, y_min=-4.0, y_step=2.0,
                  show_values=True)
    svg = _render(chart)
    rects = _bar_rects(svg)
    down = rects[-1]
    label = re.search(r'<text[^>]*y="(-?[0-9.]+)"[^>]*>-2<', svg)
    assert label, f"missing below-bar label in {svg}"
    assert float(label.group(1)) > down[1] + down[3]   # below the bar bottom


def test_none_value_renders_empty_slot():
    two = _flat([("A", [1.0, 2.0])], show_values=False)
    one = _flat([("A", [1.0, None])],
                series=[BarSeries(color="#111"), BarSeries(color="#222")],
                show_values=False)
    assert len(_bar_rects(_render(two))) == len(_bar_rects(_render(one))) + 1


def test_none_slots_keep_series_alignment():
    """A trailing None must not shift the remaining bars' slots."""
    full = _flat([("A", [1.0, 2.0, 3.0])], show_values=False)
    holed = _flat([("A", [1.0, None, 3.0])],
                  series=[BarSeries(color="#111"), BarSeries(color="#222"),
                          BarSeries(color="#333")],
                  show_values=False)
    xs_full = [r[0] for r in _bar_rects(_render(full))[-3:]]
    xs_holed = [r[0] for r in _bar_rects(_render(holed))[-2:]]
    assert xs_holed == [xs_full[0], xs_full[2]]


def test_caveat_bar_renders_dashed_lightened_qualified_style():
    chart = _flat([("A", [Bar(2.0), Bar(3.0, caveat=True)])],
                  series=[BarSeries(color="#1d3557"),
                          BarSeries(color="#1d3557")],
                  show_values=False)
    svg = _render(chart)
    caveat = re.search(r'<rect[^>]*stroke-dasharray="3,2.4"[^>]*/>', svg)
    assert caveat, f"no qualified bar in {svg}"
    assert 'fill="#1d3557"' in caveat.group(0).replace("FILL", "fill") \
        or 'stroke="#1d3557"' in caveat.group(0)
    # Lightened fill differs from the solid series colour.
    assert 'fill="#1d3557"' not in caveat.group(0)


def test_delta_arrow_skipped_when_endpoint_missing():
    chart = GroupedBarChart([("A", [10.0, None])],
                            series=[BarSeries(color="#111"),
                                    BarSeries(color="#222")],
                            show_cards=False, show_target_line=False,
                            show_values=False, show_titles=False,
                            show_axis=False)
    svg = _render(chart)
    assert "marker-end" not in svg


def test_long_rotated_y_label_stays_inside_bbox():
    """A y-label longer than the plot height must grow the element's
    margins instead of inking outside the reported bbox."""
    theme = Theme()
    label = "a rather long vertical axis label " * 3
    short = GroupedBarChart([("A", [1.0, 2.0])], y_label="y",
                            plot_height=100.0)
    tall = GroupedBarChart([("A", [1.0, 2.0])], y_label=label,
                           plot_height=100.0)
    label_w = theme.text_width(label, "small", bold=True)
    assert label_w > 100.0                    # premise: label exceeds plot
    grown = tall.measure(theme).h - short.measure(theme).h
    assert grown == pytest.approx(label_w - 100.0)


def test_all_positive_defaults_render_bottom_baseline_unchanged():
    """y_min defaults keep the historical geometry: the category axis is
    the plot bottom and bars rise from it."""
    chart = GroupedBarChart([("A", [10.0, 20.0])], y_max=20.0, y_step=10.0,
                            show_cards=False, show_target_line=False,
                            show_delta_arrow=False, show_values=False,
                            show_titles=False)
    svg = _render(chart)
    rects = _bar_rects(svg)
    tall = rects[-1]
    # The 20-value bar spans the full plot height and ends on the axis.
    axis = re.findall(r'<line x1="(-?[0-9.]+)" y1="(-?[0-9.]+)" '
                      r'x2="(-?[0-9.]+)" y2="(-?[0-9.]+)"[^>]*/>', svg)
    horizontals = [l for l in axis if l[1] == l[3]]
    assert any(abs(float(l[1]) - (tall[1] + tall[3])) < 1e-6
               for l in horizontals)


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


# ---- logarithmic value axis -------------------------------------------------

def test_log_y_allows_positive_y_min():
    """A positive y_min is required on a log axis (bars grow from the
    floor, not from zero) and must be accepted, unlike the linear case."""
    chart = GroupedBarChart([("A", [1.0, 10.0])],
                            log_y=True, y_min=0.1, y_max=100.0)
    assert chart._resolved_y_min() == pytest.approx(0.1)
    assert chart._resolved_y_max() == pytest.approx(100.0)
    # The linear guard still rejects a positive y_min.
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0])], y_min=1.0)


def test_log_y_rejects_nonpositive_bounds_and_values():
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0])], log_y=True, y_min=0.0)
    with pytest.raises(ValueError):
        GroupedBarChart([("A", [1.0, 2.0])], log_y=True, y_max=-5.0)
    with pytest.raises(ValueError):        # a zero-valued bar has no log
        GroupedBarChart([("A", [0.0, 2.0])], log_y=True)
    with pytest.raises(ValueError):        # a negative bar has no log
        GroupedBarChart([("A", [1.0, -2.0])], log_y=True)
    with pytest.raises(ValueError):        # targets must be positive too
        GroupedBarChart([BarGroup("A", [1.0, 2.0], target=-1.0)], log_y=True)


def test_log_auto_bounds_are_enclosing_decades():
    """Auto y_min/y_max snap to the decades that bracket the data so the
    smallest bar stays visible and the tallest keeps head-room."""
    chart = GroupedBarChart([("A", [0.069, 258.0])], log_y=True)
    assert chart._resolved_y_min() == pytest.approx(0.01)   # 10**floor(-1.16)
    assert chart._resolved_y_max() == pytest.approx(1000.0)  # 10**(floor(2.4)+1)


def test_log_axis_draws_decade_ticks():
    chart = GroupedBarChart(
        [("A", [1.0, 100.0])],
        log_y=True, y_min=0.01, y_max=1000.0,
        show_cards=False, show_target_line=False, show_delta_arrow=False,
        show_values=False, show_titles=False,
    )
    assert chart._axis_tick_values(0.01, 1000.0) == pytest.approx(
        [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0])
    svg = _render(chart)
    for label in ("0.01", "0.1", "1", "10", "100", "1000"):
        assert f">{label}<" in svg


def test_log_bar_heights_follow_log_fraction_from_shared_floor():
    """Bars grow from the axis floor with heights proportional to the log
    of their value: over [0.1, 1000] the value 100 is three decades above
    the floor and 1.0 is one, so the 100-bar is 3x taller -- and both share
    the floor (equal bottoms)."""
    chart = _flat([("A", [1.0, 100.0])],
                  log_y=True, y_min=0.1, y_max=1000.0, show_values=False)
    small, big = _bar_rects(_render(chart))[-2:]
    assert big[3] == pytest.approx(small[3] * 3.0, rel=1e-3)   # height ratio
    assert small[1] + small[3] == pytest.approx(big[1] + big[3])  # same floor


def test_log_and_linear_share_one_measure_contract():
    """A log chart still reports a positive, finite bbox on both themes."""
    chart = GroupedBarChart([("A", [0.05, 5.0, 500.0])],
                            series=[BarSeries(color="#b91c1c"),
                                    BarSeries(color="#0f766e"),
                                    BarSeries(color="#3b5fa0")],
                            log_y=True)
    for theme in (Theme(), Theme.slides()):
        bbox = chart.measure(theme)
        assert bbox.w > 0 and bbox.h > 0
