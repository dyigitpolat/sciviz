"""`Table(column_styles=[...])` applies default text styling to string cells
per column, replacing the boilerplate of wrapping every cell in
``Text(..., size="small", color="muted")``.
"""
from __future__ import annotations

import re

from sciviz import Table, Canvas, Theme


def _svg(elem):
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), theme


def test_string_cells_coerced_with_column_style():
    t = Table(
        [["mode", "point", "notes"],
         ["one", "A", "lorem"],
         ["two", "B", "ipsum"]],
        column_styles=[
            {"size": "small", "color": "muted", "weight": "700"},
            {"size": "small", "color": "text"},
            {"size": "small", "color": "muted"},
        ],
    )
    svg, theme = _svg(t)
    muted = theme.color_of("muted")
    text = theme.color_of("text")
    # "mode" column header should have muted-coloured bold text.
    m = re.search(r'<text[^>]+fill="([^"]+)"[^>]+font-weight="700"[^>]*>mode</text>',
                  svg)
    assert m and m.group(1) == muted, f"mode should be muted bold; svg={svg[:400]}"
    # "A" in column 2 uses text colour (no weight override).
    m2 = re.search(r'<text[^>]+fill="([^"]+)"[^>]*>A</text>', svg)
    assert m2 and m2.group(1) == text, f"A should be plain text colour"


def test_element_cells_pass_through_unchanged():
    """Only raw strings are coerced; existing Element cells are respected."""
    from sciviz import Text
    t = Table(
        [[Text("custom", color="alert"), "other"]],
        column_styles=[{"color": "muted"}, {"color": "muted"}],
    )
    svg, theme = _svg(t)
    alert = theme.color_of("alert")
    muted = theme.color_of("muted")
    # "custom" keeps its alert colour; "other" gets column default muted.
    assert re.search(rf'<text[^>]+fill="{alert}"[^>]*>custom</text>', svg), (
        "existing Element should not be overridden by column_styles")
    assert re.search(rf'<text[^>]+fill="{muted}"[^>]*>other</text>', svg), (
        "string cell should pick up column_styles colour")


def test_column_styles_length_validated():
    import pytest
    with pytest.raises(ValueError):
        Table([["a", "b"]], column_styles=[{"color": "muted"}])
