"""Table furniture: header, rules, bands, padding, and wrap budgets."""

from __future__ import annotations

import re

from sciviz import DEFAULT_THEME, Diagram, Table

T = DEFAULT_THEME
LONG = "a sentence that is long enough to need wrapping at a narrow budget"


def _svg(element) -> str:
    return Diagram(element).render(embed_fonts=False)


def test_col_widths_wrap_string_cells():
    narrow = Table([[LONG]], col_widths=[60])
    wide = Table([[LONG]])
    assert narrow.measure(T).w < wide.measure(T).w
    assert narrow.measure(T).h > wide.measure(T).h


def test_header_is_bold_and_rules_are_drawn():
    rows = [["Head", "Col"], ["1", "2"], ["3", "4"], ["5", "6"]]
    svg = _svg(Table(rows, header=True, rules="all"))
    assert svg.count("<line") == 3          # header rule + two body rules
    assert re.search(r'font-weight="700"[^>]*>\s*Head', svg)
    assert not re.search(r'font-weight="700"[^>]*>\s*1<', svg)
    header_only = _svg(Table(rows, header=True, rules="header"))
    assert header_only.count("<line") == 1
    plain = _svg(Table(rows))
    assert plain.count("<line") == 0


def test_bands_for_chosen_rows_and_zebra():
    rows = [["Head", "Col"], ["1", "2"], ["3", "4"], ["5", "6"], ["7", "8"]]
    svg = _svg(Table(rows, header=True, row_fills={2: "#ffeeaa"}))
    assert svg.count('fill="#ffeeaa"') == 1
    svg = _svg(Table(rows, header=True, zebra="#f0f0f0"))
    assert svg.count('fill="#f0f0f0"') == 2  # body rows 2 and 4


def test_padding_grows_cells():
    bare = Table([["cell"]]).measure(T)
    padded = Table([["cell"]], pad_x=4.0, pad_y=2.0).measure(T)
    assert abs(padded.w - bare.w - 8.0) < 1e-6
    assert abs(padded.h - bare.h - 4.0) < 1e-6


def test_legacy_rule_flags_map_onto_rules():
    rows = [["a"], ["b"]]
    assert Table(rows, header_rule=True).rules == "header"
    assert Table(rows, row_rules=True).rules == "rows"
    assert Table(rows, header_rule=True, row_rules=True).rules == "all"


def test_inflate_to_shares_surplus_width_over_columns():
    t = Table([["ab", "cdef"]])
    w0 = t.measure(T).w
    t.inflate_to(w0 + 40.0)
    assert abs(t.measure(T).w - (w0 + 40.0)) < 1e-6
    assert abs(t.measure(T).h - Table([["ab", "cdef"]]).measure(T).h) < 1e-6
