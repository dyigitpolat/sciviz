"""Unit bars: BarChart(mark="units") draws a count as a run of countable
cells that carries its legend label and its number, and
MiniRaster.from_counts packs a composition into a waffle."""
from __future__ import annotations

import pytest

from sciviz import BarChart, MiniRaster
from sciviz.core import Theme

from tests._recording_canvas import assert_inside, render

TH = Theme()
ITEMS = [("Apples", 5, "5", "#1f4e79"),
         ("Oranges", 24, "24", "#9ca3af"),
         ("Pears", 32, "32", "#6b7280"),
         ("Plums", 0, "0", "#d1d5db")]


def _cells(canvas):
    return [a for a, k in canvas.of("rect") if a[2] < 4 and a[3] < 4]


def test_one_cell_per_unit_starting_at_one_x():
    chart = BarChart(ITEMS, mark="units", wrap=12, label_size="tiny",
                     value_size="tiny")
    canvas, box = render(chart, TH)
    cells = _cells(canvas)
    assert len(cells) == 5 + 24 + 32
    firsts = {}
    for x, y, *_ in cells:
        firsts.setdefault(round(y, 3), x)
    assert len({round(x, 3) for x in firsts.values()}) == 1
    assert_inside(chart, TH, canvas, box)
    assert {"Apples", "5", "24", "32", "0"} <= set(canvas.texts())


def test_runs_wrap_at_the_budget():
    chart = BarChart([("a", 30, "30")], mark="units", wrap=12, cell=3.0)
    canvas, _ = render(chart, TH)
    xs = sorted({round(a[0], 3) for a in _cells(canvas)})
    ys = sorted({round(a[1], 3) for a in _cells(canvas)})
    assert len(xs) == 12 and len(ys) == 3


def test_group_rule_and_bar_mode_unchanged():
    chart = BarChart(ITEMS, mark="units", wrap=12, rules_after=(0,))
    canvas, _ = render(chart, TH)
    assert len(canvas.of("line")) == 1
    with pytest.raises(ValueError):
        BarChart(ITEMS, mark="dots")


@pytest.mark.parametrize("kw", [dict(cell=3.0), dict(wrap=12),
                                dict(rules_after=(0,))])
def test_unit_run_parameters_need_the_units_mark(kw):
    """cell, wrap and rules_after shape unit runs; a proportional bar
    would ignore them, so passing them with mark='bar' is an error."""
    with pytest.raises(ValueError):
        BarChart(ITEMS, **kw)


def test_waffle_from_counts_is_contiguous_in_part_order():
    r = MiniRaster.from_counts([(5, "a"), (3, "b"), (4, "c")], columns=5)
    flat = [c for row in r.grid for c in row]
    assert flat == ["a"] * 5 + ["b"] * 3 + ["c"] * 4
    assert [len(row) for row in r.grid] == [5, 5, 2]
    auto = MiniRaster.from_counts([(61, "a")])
    assert max(len(row) for row in auto.grid) == 10
