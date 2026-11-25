"""Table overflow row: max_rows cuts a long body and closes it with one
spanning "+ N more" row that is muted, has no rule above it and obeys the
bbox contract."""
from __future__ import annotations

from sciviz import Table, TableSpan
from sciviz.core import Theme

from tests._recording_canvas import assert_inside, render

TH = Theme()
HEAD = ["9 parameters", "from", "to", "unit"]
BODY = [[f"parameter {i}", "0.3", "1.0", "ns"] for i in range(9)]


def test_body_is_cut_and_closed_by_a_spanning_count():
    t = Table([HEAD] + BODY, header=True, rules="rows", max_rows=2)
    assert len(t.rows) == 4
    assert t._slots[-1] == [(0, 4)]
    assert t.rows[-1][0].content == "+ 7 more"


def test_no_overflow_row_when_the_body_fits():
    t = Table([HEAD] + BODY[:2], header=True, max_rows=2)
    assert len(t.rows) == 3


def test_template_and_span_forms_of_more():
    t = Table([HEAD] + BODY, header=True, max_rows=3,
              more="[...] and {n} more")
    assert t.rows[-1][0].content == "[...] and 6 more"
    t = Table(BODY, max_rows=1, more=TableSpan("+{n}", align="end"))
    assert t.rows[-1][0].content == "+8"
    assert t._span_align[-1][0] == "end"


def test_overflow_row_does_not_widen_columns_or_take_a_rule():
    cut = Table([HEAD] + BODY, header=True, rules="rows", max_rows=2)
    short = Table([HEAD] + BODY[:2], header=True, rules="rows")
    assert cut._extents(TH)[1] == short._extents(TH)[1]
    canvas, box = render(cut, TH)
    assert_inside(cut, TH, canvas, box)
    # header rule + one body rule; none above the overflow row
    assert len(canvas.of("line")) == 2
    cell = cut.rows[-1][0]
    assert cell.italic and cell.color == "text_muted"


def test_overflow_row_on_a_narrow_table_stays_inside_its_box():
    t = Table([["a"], ["b"], ["c"]], max_rows=1, more="+ {n} more rows")
    canvas, box = render(t, TH)
    assert_inside(t, TH, canvas, box)


def test_cells_with_symbol_glyphs_stay_inside_the_box():
    """Arrows, micro, times and ellipsis measure as they render."""
    t = Table([["4 channels", "trend"], ["dose (\u00b5g/m\u00b2)", "\u2193"],
               ["pressure, humidity", "\u2193 \u2193"]] + [["x", "\u00d72.0"]] * 3,
              header=True, rules="rows", max_rows=2, more="\u2026 + {n} more")
    canvas, box = render(t, TH)
    assert_inside(t, TH, canvas, box)
