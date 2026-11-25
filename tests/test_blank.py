"""``Blank(element)``: an element's place without its drawing.

A withheld value keeps its figure's geometry: the blank measures and aligns as the element (its box, content box,
first baseline, anchor and ports), and nothing of the element is rendered. A new element: no default changes.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Column, Diagram, Icon, Row, Table, Text, Theme
from sciviz.elements._blank import Blank


def _svg(body):
    return Diagram(body).render(embed_fonts=False)


def _text_positions(svg, word):
    """(x, y) of every text element that holds ``word``, as the SVG places it."""
    out = []
    for m in re.finditer(r"<text([^>]*)>([^<]*)</text>", svg):
        if word in m.group(2):
            x = re.search(r'\bx="([-0-9.]+)"', m.group(1))
            y = re.search(r'\by="([-0-9.]+)"', m.group(1))
            out.append((float(x.group(1)) if x else None, float(y.group(1)) if y else None))
    return out


def test_measures_and_aligns_as_the_element():
    theme = Theme()
    for el in (Text("21,730 cores", size=7.0), Box(width=6.0, height=17.0), Icon("check", size=8.0),
               Row(Text("a", size=7.0), Text("bc", size=9.0), align="baseline")):
        b = Blank(el)
        assert b.measure(theme) == el.measure(theme)
        assert b.content_bbox(theme) == el.content_bbox(theme)
        assert b.primary_anchor_bbox(theme) == el.primary_anchor_bbox(theme)
        assert b.port_bbox(theme, "left") == el.port_bbox(theme, "left")


def test_keeps_the_first_baseline():
    from sciviz.layout._baseline import first_baseline
    theme = Theme()
    t = Text("Equal outputs", size=7.0)
    assert first_baseline(Blank(t), theme) == pytest.approx(first_baseline(t, theme))
    assert first_baseline(Blank(Box(width=4.0, height=4.0)), theme) is None


def test_draws_nothing():
    svg = _svg(Row(Blank(Text("0 of 500,000", size=7.0)), Blank(Box(width=6.0, height=6.0, fill="#2b6cb0")),
                   Text("kept", size=7.0)))
    assert "500,000" not in svg
    assert "#2b6cb0" not in svg.lower()
    assert _text_positions(svg, "kept")


@pytest.mark.parametrize("build", [
    lambda a: Row(a, Text("kept", size=7.0), gap=3.0, align="baseline"),
    lambda a: Column(a, Text("kept", size=6.5), gap=0.0, align="start"),
    lambda a: Table([[a, Text("kept", size=7.0)], [Text("9 passes", size=7.0), Text("1", size=6.5)]],
                    col_align=("end", "center"), gap_x=0.0, gap_y=0.8),
])
def test_the_neighbours_stand_where_they_stood(build):
    theme = Theme()
    shown = build(Column(Text("21,730 cores", size=7.0), Text("Single pass", size=7.0), gap=0.0, align="end"))
    blank = build(Blank(Column(Text("21,730 cores", size=7.0), Text("Single pass", size=7.0), gap=0.0,
                               align="end")))
    assert blank.measure(theme) == shown.measure(theme)
    assert _text_positions(_svg(blank), "kept") == _text_positions(_svg(shown), "kept")


def test_refuses_a_non_element():
    with pytest.raises(TypeError):
        Blank("text")


def test_a_stand_in_is_drawn_in_the_place():
    theme = Theme()
    el = Text("8× fewer cores", size=8.5, weight="700")
    b = Blank(el, stand_in=Text("Pending", size=7.0))
    assert b.measure(theme) == el.measure(theme)
    svg = _svg(Row(b, Text("kept", size=7.0)))
    assert "Pending" in svg and "fewer" not in svg
    shown = _svg(Row(el, Text("kept", size=7.0)))
    assert _text_positions(svg, "kept") == _text_positions(shown, "kept")
    with pytest.raises(TypeError):
        Blank(el, stand_in="Pending")
