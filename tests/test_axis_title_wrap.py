"""Axis titles wrap to their own gutter instead of escaping the chart box.

Motivating case (AgentEvolve AAAI-27 gain-anatomy figure): two small
single-column panels whose x titles were prose ("members, ranked by realised
gain"). ``measure()`` reported only ``left + plot + right``, so the centred
title drew straight through the neighbouring panel's frame -- ink outside the
measured bbox, which the layout engine cannot see and cannot route around.

Axis titles are prose, so the fix is to wrap them to the span they are
centred over rather than to widen every figure that uses one: a long title
claims another title line in its own gutter, and a single unbreakable word
grows the box symmetrically so the bbox still contains every glyph.
"""
from __future__ import annotations

from sciviz import LineChart, Scatter, Series, Theme
from sciviz.core import Canvas


THEME = Theme()
LONG_X = "members, ranked by realised archive gain"
LONG_Y = "cumulative share of realised gain (%)"


def _ink_bbox(element):
    """Union of every glyph/line/marker the element actually draws.

    The canvas carries the theme's font family, as :class:`Diagram` builds
    it, so text ink is accounted with the real glyph advances rather than
    the no-font fallback estimate.
    """
    canvas = Canvas(default_font_family=THEME.font_family)
    element.render(canvas, 0.0, 0.0, THEME)
    return canvas.ink_bbox


def _chart(**kw):
    return LineChart([Series([(0.0, 0.0), (1.0, 1.0)], label="s")],
                     width=70.0, height=56.0, **kw)


# ---- Theme.wrap_lines ----------------------------------------------------


def test_wrap_lines_respects_the_budget():
    lines = THEME.wrap_lines(LONG_X, "label", 90.0)
    assert len(lines) > 1
    assert " ".join(lines) == LONG_X
    assert all(THEME.text_width(line, "label") <= 90.0 for line in lines)


def test_wrap_lines_keeps_hard_breaks_and_long_words():
    assert THEME.wrap_lines("a\nb", "label", 500.0) == ["a", "b"]
    # A word wider than the budget claims its own line, never a truncation.
    assert THEME.wrap_lines("supercalifragilistic", "label", 5.0) == [
        "supercalifragilistic"]
    assert THEME.wrap_lines("", "label", 50.0) == []


# ---- LineChart -----------------------------------------------------------


def test_long_x_title_wraps_rather_than_widening_the_chart():
    plain = _chart()
    titled = _chart(x_label=LONG_X)
    # The title costs height (an extra title line), not width.
    assert titled.measure(THEME).w == plain.measure(THEME).w
    assert titled.measure(THEME).h > plain.measure(THEME).h


def test_long_x_title_ink_stays_inside_the_measured_box():
    titled = _chart(x_label=LONG_X)
    box = titled.measure(THEME)
    x0, y0, x1, y1 = _ink_bbox(titled)
    assert x0 >= -0.5 and x1 <= box.w + 0.5
    assert y0 >= -0.5 and y1 <= box.h + 0.5


def test_long_y_title_ink_stays_inside_the_measured_box():
    titled = _chart(y_label=LONG_Y)
    box = titled.measure(THEME)
    x0, y0, x1, y1 = _ink_bbox(titled)
    assert x0 >= -0.5 and x1 <= box.w + 0.5
    assert y0 >= -0.5 and y1 <= box.h + 0.5


def test_unbreakable_title_grows_the_box_instead_of_spilling():
    word = "hypervolume" * 4
    titled = _chart(x_label=word)
    box = titled.measure(THEME)
    assert box.w > _chart().measure(THEME).w
    x0, _y0, x1, _y1 = _ink_bbox(titled)
    assert x0 >= -0.5 and x1 <= box.w + 0.5


def test_short_titles_are_unchanged():
    chart = _chart(x_label="evaluations", y_label="gain")
    box = chart.measure(THEME)
    x0, y0, x1, y1 = _ink_bbox(chart)
    assert x0 >= -0.5 and x1 <= box.w + 0.5
    assert y0 >= -0.5 and y1 <= box.h + 0.5


# ---- Scatter reads as the same family ------------------------------------


def _scatter(**kw):
    return Scatter([(0.1, 0.1), (0.9, 0.9)], width=70.0, height=56.0, **kw)


def test_scatter_long_titles_stay_inside_the_measured_box():
    plot = _scatter(x_label=LONG_X, y_label=LONG_Y)
    box = plot.measure(THEME)
    x0, y0, x1, y1 = _ink_bbox(plot)
    assert x0 >= -0.5 and x1 <= box.w + 0.5
    assert y0 >= -0.5 and y1 <= box.h + 0.5


def test_scatter_x_title_costs_height_not_width():
    assert _scatter(x_label=LONG_X).measure(THEME).w == _scatter().measure(THEME).w
    assert _scatter(x_label=LONG_X).measure(THEME).h > _scatter().measure(THEME).h
