"""Table spanning cells: TableSpan covers adjacent columns.

A span is sized after the ordinary cells: a narrow one leaves the
columns alone, a wide one shares its excess over the columns it covers
in proportion to their widths, and it renders inside its column range.
A table whose cells are all one-column spans is the plain table.
"""
from __future__ import annotations

import pytest

from sciviz import Table, TableSpan, Text
from sciviz.core import Theme

from tests._recording_canvas import assert_inside, render

TH = Theme()
ROWS = [["channel", "from", "to"], ["temperature", "20", "70"],
        ["sample period", "0.3", "1.0"]]


def test_narrow_span_keeps_column_widths():
    plain = Table(ROWS)
    spanned = Table(ROWS + [[TableSpan("note", 2), "x"]])
    assert spanned._extents(TH)[1] == plain._extents(TH)[1]


def test_wide_span_shares_excess_over_its_columns():
    plain = Table(ROWS)
    wide = "a spanning title far wider than the two columns"
    t = Table([[TableSpan(wide, 2), "x"]] + ROWS)
    base = plain._extents(TH)[1]
    got = t._extents(TH)[1]
    gx = TH.gap_px("sm")
    assert got[0] + got[1] + gx == pytest.approx(TH.text_width(wide, "body"), abs=0.5)
    assert got[0] / got[1] == pytest.approx(base[0] / base[1])
    assert got[2] == base[2]


def test_span_renders_inside_its_column_range_and_measured_box():
    t = Table(ROWS + [[TableSpan("a long spanning note under the table")]],
              header=True, rules="rows")
    canvas, box = render(t, TH)
    assert_inside(t, TH, canvas, box)
    a, _ = canvas.texts()["a long spanning note under the table"]
    assert a[0] == pytest.approx(box[0])


def test_rest_of_row_span_and_alignment():
    t = Table(ROWS + [["total", TableSpan("90", align="end")]])
    assert t._slots[-1] == [(0, 1), (1, 2)]
    canvas, box = render(t, TH)
    a, _ = canvas.texts()["90"]
    assert a[0] + TH.text_width("90", "body") == pytest.approx(box[2], abs=0.5)


def test_rows_must_cover_every_column():
    with pytest.raises(ValueError, match="equal length"):
        Table([["a", "b", "c"], [TableSpan("x", 2), "y", "z"]])
    with pytest.raises(ValueError, match="column count"):
        Table([[TableSpan("x")]])


def test_one_column_spans_are_the_plain_table():
    plain = Table(ROWS, header=True, rules="all", zebra="bg_subtle")
    spans = Table([[TableSpan(c, 1) if i else c for i, c in enumerate(r)]
                   for r in ROWS], header=True, rules="all", zebra="bg_subtle")
    ca, _ = render(plain, TH)
    cb, _ = render(spans, TH)
    assert ca.calls == cb.calls


def test_span_style_lays_over_column_style():
    t = Table([["a", "b"], [TableSpan("note", style={"italic": True})]],
              column_styles=[{"color": "text_muted"}, {}])
    cell = t.rows[1][0]
    assert isinstance(cell, Text)
    assert cell.italic and cell.color == "text_muted"
