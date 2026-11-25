"""Table row styles and group rules: row_styles is the row-wise twin of
column_styles, and rules_after separates groups of rows with a hairline."""
from __future__ import annotations

import pytest

from sciviz import Table
from sciviz.elements import Arrow
from sciviz.core import Theme

from tests._recording_canvas import render

TH = Theme()


def test_row_style_lays_over_column_style():
    t = Table([["temp 21", "pressure 1013"],
               ["temp_c=21", "pressure_hpa=1013"]],
              column_styles=[{"color": "text_muted"}, {}],
              row_styles={1: {"font": "mono", "size": "tiny"}})
    assert t.rows[0][0].color == "text_muted"
    assert t.rows[1][0].font == "mono" and t.rows[1][0].color == "text_muted"
    assert t.rows[1][1].size == "tiny"
    seq = Table([["a"], ["b"]], row_styles=[{}, {"italic": True}])
    assert seq.rows[1][0].italic and not seq.rows[0][0].italic


def test_rules_after_draws_group_hairlines_only():
    t = Table([["a"], ["b"], ["c"], ["d"]], rules_after=(1,))
    canvas, _ = render(t, TH)
    lines = canvas.of("line")
    assert len(lines) == 1
    (x0, y0, x1, y1), _ = lines[0]
    assert y0 == y1


def test_mapping_recipe_aligns_every_glyph():
    """The documented mapping recipe: a column of bare Arrow glyphs."""
    t = Table([["temp 21", Arrow(direction="down", label=None),
                "temp_c=21"],
               ["pressure 1013", Arrow(direction="up", label=None),
                "pressure_hpa=1013"]],
              col_align=["end", "center", "start"],
              column_styles=[{}, {}, {"font": "mono"}])
    sizes, col_w, _ = t._extents(TH)
    assert sizes[0][1].w == pytest.approx(sizes[1][1].w)
