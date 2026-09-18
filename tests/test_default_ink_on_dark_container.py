"""The default dark ink turns light inside a dark container, and back."""

from __future__ import annotations

import re

from sciviz import Box, Card, DEFAULT_THEME, Diagram, Palette, Text

T = DEFAULT_THEME


def _svg(element) -> str:
    return Diagram(element).render(embed_fonts=False)


def _fill_of(svg: str, label: str) -> str:
    m = re.search(r'<text[^>]*fill="([^"]+)"[^>]*>' + re.escape(label), svg)
    assert m, label
    return m.group(1).lower()


def test_plain_text_header_reads_light_on_the_role_band():
    card = Card(Text("Head", size="tiny", weight="700"), Box("Body text"),
                role=Palette.indigo)
    svg = _svg(card)
    assert _fill_of(svg, "Head") == T.text_inverse.lower()
    assert _fill_of(svg, "Body text") == T.text.lower()


def test_theme_swaps_both_inks_by_container():
    T.push_bg("#4338ca")
    try:
        assert T.color_of("text").lower() == T.text_inverse.lower()
        assert T.color_of("white").lower() == T.text_inverse.lower()
    finally:
        T.pop_bg()
    T.push_bg("#f5e2da")
    try:
        assert T.color_of("text").lower() == T.text.lower()
        assert T.color_of("white").lower() == T.text.lower()
    finally:
        T.pop_bg()
    assert T.color_of("text").lower() == T.text.lower()
