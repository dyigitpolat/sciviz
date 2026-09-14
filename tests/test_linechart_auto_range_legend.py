"""LineChart automatic ranging and occlusion-free inside-legend placement.

Motivating case (SHAQ paper, PGD-depth figure): panels carried large bands
of dead whitespace because the author had to over-pad explicit ranges so an
``inside-top-right`` legend would not sit on the curves. The library now
fits automatic ranges snugly to the data and treats an inside legend corner
as a preference: keep it when clear, relocate when another corner is clear,
or expand automatic y headroom just enough to clear the data.
"""
from __future__ import annotations

import pytest

from sciviz import LineChart, Series, Theme
from sciviz.auto.labelplacer import overlap_area
from sciviz.core import Canvas
from sciviz.specialized._linechart import Annotate


THEME = Theme()


def _render(chart: LineChart) -> None:
    size = chart.measure(THEME)
    canvas = Canvas()
    chart.render(canvas, 0.0, 0.0, THEME)
    canvas.to_svg(size.w, size.h)


def _line(ys, label="series", **kw):
    n = len(ys)
    pts = [(i / (n - 1), y) for i, y in enumerate(ys)]
    return Series(points=pts, label=label, **kw)


# ---- automatic ranging ---------------------------------------------------


def test_auto_y_range_fits_data_snugly():
    chart = LineChart([_line([23.0, 41.0, 57.0])])
    _render(chart)
    lo, hi = chart._yr
    assert lo <= 23.0 and hi >= 57.0, f"data not covered: {(lo, hi)}"
    assert (hi - lo) <= (57.0 - 23.0) * 1.8, (
        f"auto range not snug: {(lo, hi)} for data [23, 57]")


def test_auto_ticks_land_on_round_values():
    chart = LineChart([_line([12.0, 33.0, 47.0])])
    _render(chart)
    step = chart._y_step
    assert step is not None
    ticks = chart._ticks("auto", chart._yr, False, step)
    for t in ticks:
        assert abs(t / step - round(t / step)) < 1e-6, (
            f"tick {t} not on step grid {step}")
    assert ticks[0] == chart._yr[0] and ticks[-1] == chart._yr[1]


def test_explicit_ranges_pass_through_verbatim():
    chart = LineChart([_line([0.2, 0.4])],
                      x_range=(0.0, 100.0), y_range=(0.0, 1.0))
    _render(chart)
    assert chart._xr == (0.0, 100.0)
    assert chart._yr == (0.0, 1.0)


def test_constant_series_still_gets_a_usable_range():
    chart = LineChart([_line([5.0, 5.0, 5.0])])
    _render(chart)
    lo, hi = chart._yr
    assert lo < 5.0 < hi


# ---- inside-legend placement --------------------------------------------


def test_preferred_corner_kept_when_clear():
    chart = LineChart([_line([0.10, 0.12, 0.11])],
                      y_range=(0.0, 1.0), x_range=(0.0, 1.0),
                      legend="inside-top-right")
    _render(chart)
    x0, y0, _, _ = chart._legend_rect
    assert x0 > chart.width / 2, "expected legend kept on the right"
    assert y0 < chart.height / 2, "expected legend kept at the top"


def test_relocates_to_clear_corner_when_preferred_is_covered():
    chart = LineChart([_line([0.95] * 12)],
                      y_range=(0.0, 1.0), x_range=(0.0, 1.0),
                      legend="inside-top-right")
    _render(chart)
    assert chart._yr == (0.0, 1.0), "explicit range must never be mutated"
    x0, y0, x1, y1 = chart._legend_rect
    assert y0 > chart.height / 2, (
        "legend should relocate below the top-hugging line")
    rects, _, _ = chart._legend_obstacles(THEME)
    covered = sum(overlap_area(chart._legend_rect, ob) for ob in rects)
    assert covered <= 1e-9, f"relocated legend still covers data: {covered}"


def test_auto_range_expands_headroom_when_no_corner_is_clear():
    chart = LineChart([_line([0.95] * 12, label="top"),
                       _line([0.05] * 12, label="bottom")],
                      legend="inside-top-right")
    _render(chart)
    assert chart._yr[1] > 1.0, (
        f"expected y headroom above the nice bound 1.0, got {chart._yr}")
    x0, y0, _, _ = chart._legend_rect
    assert x0 > chart.width / 2 and y0 < chart.height / 2, (
        "author's corner should be kept when headroom expansion clears it")
    rects, _, _ = chart._legend_obstacles(THEME)
    covered = sum(overlap_area(chart._legend_rect, ob) for ob in rects)
    assert covered <= 1e-9, f"legend still covers data: {covered}"


def test_explicit_range_falls_back_to_least_covering_corner():
    chart = LineChart([_line([0.95] * 12, label="top"),
                       _line([0.05] * 12, label="bottom")],
                      y_range=(0.0, 1.0), legend="inside-top-right")
    _render(chart)
    assert chart._yr == (0.0, 1.0), "explicit range must never be mutated"
    assert chart._legend_rect is not None


def test_annotation_text_is_an_obstacle():
    ann = Annotate(0.55, 0.5, "important note", dx=8.0, dy=-4.0)
    clear = LineChart([_line([0.1, 0.1], label="s")],
                      y_range=(0.0, 1.0), x_range=(0.0, 1.0),
                      legend="inside-top-right")
    _render(clear)
    with_ann = LineChart([_line([0.1, 0.1], label="s")],
                         y_range=(0.0, 1.0), x_range=(0.0, 1.0),
                         annotations=[ann], legend="inside-top-right")
    _render(with_ann)
    rects, _, _ = with_ann._legend_obstacles(THEME)
    covered = sum(overlap_area(with_ann._legend_rect, ob) for ob in rects)
    assert covered <= 1e-9, "legend must not cover annotation text"


def test_inside_bottom_left_is_a_valid_preference():
    chart = LineChart([_line([0.9, 0.92])],
                      y_range=(0.0, 1.0), x_range=(0.0, 1.0),
                      legend="inside-bottom-left")
    _render(chart)
    x0, y0, _, _ = chart._legend_rect
    assert x0 < chart.width / 2 and y0 > chart.height / 2


def test_unknown_legend_value_is_rejected():
    with pytest.raises(ValueError):
        LineChart([_line([0.1, 0.2])], legend="inside-center")


# ---- label-derived gutters -----------------------------------------------


def test_left_gutter_tracks_tick_label_width():
    narrow = LineChart([_line([20.0, 55.0])], y_label="accuracy")
    wide = LineChart([_line([20000.0, 55000.0])], y_label="accuracy")
    dw = wide.measure(THEME).w - narrow.measure(THEME).w
    tw_narrow = narrow._y_tick_width(THEME)
    tw_wide = wide._y_tick_width(THEME)
    assert tw_wide > tw_narrow + 5.0, "test premise: wider tick labels"
    assert abs(dw - (tw_wide - tw_narrow)) < 0.5, (
        "left gutter must grow exactly with the tick labels, "
        f"got bbox delta {dw} for label delta {tw_wide - tw_narrow}")


def test_bottom_gutter_is_tick_line_plus_title_band():
    bare = LineChart([_line([0.1, 0.9])])
    titled = LineChart([_line([0.1, 0.9])], x_label="steps")
    dh = titled.measure(THEME).h - bare.measure(THEME).h
    # One title line: its baseline offset plus the descender it inks
    # below that baseline. Reserving text_height() alone left the
    # descender outside the measured box.
    _ascent, descent = THEME.text_ink_extents(titled._TITLE_SIZE)
    expected = (THEME.text_height(titled._TITLE_SIZE)
                * titled._X_TITLE_BASELINE
                + descent + titled._axis_gap(THEME) * 0.6)
    assert abs(dh - expected) < 0.5, (
        f"x title band should add {expected}, added {dh}")


def test_render_is_idempotent():
    chart = LineChart([_line([0.95] * 12, label="top"),
                       _line([0.05] * 12, label="bottom")],
                      legend="inside-top-right")
    _render(chart)
    first = (chart._yr, chart._legend_rect)
    _render(chart)
    assert (chart._yr, chart._legend_rect) == first


# ---- secondary (right) y axis --------------------------------------------


def _svg(chart: LineChart) -> str:
    size = chart.measure(THEME)
    canvas = Canvas()
    chart.render(canvas, 0.0, 0.0, THEME)
    return canvas.to_svg(size.w, size.h)


def test_right_axis_series_spans_the_plot_through_its_own_range():
    """A right-axis series with a tiny value range still uses the full
    plot height, because it is projected through the secondary range."""
    chart = LineChart([_line([0.0, 100.0], label="big"),
                       _line([0.0, 0.10], label="small", axis="right")],
                      x_range=(0.0, 1.0))
    _render(chart)
    assert chart._yr2 is not None and chart._yr2 != chart._yr
    top = chart._y_to_px(0.10, right=True)
    bottom = chart._y_to_px(0.0, right=True)
    assert bottom - top > chart.height * 0.5, (
        f"right series compressed: {top}..{bottom} of {chart.height}")


def test_secondary_axis_claims_a_right_gutter():
    single = LineChart([_line([0.0, 100.0], label="big")], y_label="acc")
    dual = LineChart([_line([0.0, 100.0], label="big"),
                      _line([0.0, 0.10], label="small", axis="right")],
                     y_label="acc", y2_label="hazard")
    assert dual.measure(THEME).w > single.measure(THEME).w + 20.0, (
        "secondary axis must reserve room for its ticks and title")


def test_no_secondary_axis_when_no_series_opts_in():
    chart = LineChart([_line([0.0, 1.0], label="a")], y2_label="unused")
    _render(chart)
    assert chart.has_secondary_axis() is False
    assert chart._yr2 is None


def test_explicit_y2_range_passes_through_verbatim():
    chart = LineChart([_line([0.0, 1.0]),
                       _line([0.2, 0.4], label="r", axis="right")],
                      y2_range=(0.0, 5.0))
    _render(chart)
    assert chart._yr2 == (0.0, 5.0)


def test_right_axis_ink_is_a_legend_obstacle():
    """Ink on the right axis blocks a corner just like left-axis ink: the
    legend leaves the top even though nothing on the *left* axis is up
    there. Both ranges are explicit, so relocation is the only remedy."""
    chart = LineChart([_line([0.5] * 12, label="mid"),
                       _line([0.95] * 12, label="high", axis="right")],
                      x_range=(0.0, 1.0), y_range=(0.0, 1.0),
                      y2_range=(0.0, 1.0), legend="inside-top-right")
    _render(chart)
    assert chart._yr == (0.0, 1.0) and chart._yr2 == (0.0, 1.0)
    _, y0, _, _ = chart._legend_rect
    assert y0 > chart.height / 2, (
        "legend should leave the top, which right-axis ink occupies")
    rects, _, _ = chart._legend_obstacles(THEME)
    covered = sum(overlap_area(chart._legend_rect, ob) for ob in rects)
    assert covered <= 1e-9, (
        f"legend covers right-axis data: {covered}")


def test_right_axis_headroom_expands_independently():
    chart = LineChart([_line([0.05] * 12, label="low"),
                       _line([0.09] * 12, label="high", axis="right")],
                      legend="inside-top-right")
    _render(chart)
    rects, _, _ = chart._legend_obstacles(THEME)
    covered = sum(overlap_area(chart._legend_rect, ob) for ob in rects)
    assert covered <= 1e-9, f"legend covers data: {covered}"


def test_right_axis_renders_a_spine_and_tick_labels():
    chart = LineChart([_line([0.0, 1.0]),
                       _line([0.0, 3.0], label="r", axis="right")],
                      y2_label="secondary")
    svg = _svg(chart)
    assert "secondary" in svg
    ticks = chart._y_axis_ticks(right=True)
    assert ticks and ticks[-1] >= 3.0


def test_cross_axis_fill_and_delta_are_rejected():
    from sciviz.specialized._linechart import FillBetween, SeriesDelta
    left = Series(points=[(0, 0), (1, 1)], key="l")
    right = Series(points=[(0, 0), (1, 1)], key="r", axis="right")
    with pytest.raises(ValueError):
        LineChart([left, right], fills=[FillBetween("l", "r")])
    with pytest.raises(ValueError):
        LineChart([left, right], deltas=[SeriesDelta(0.5, "l", "r", "d")])


def test_unknown_axis_is_rejected():
    with pytest.raises(ValueError):
        LineChart([Series(points=[(0, 0), (1, 1)], axis="middle")])
