"""A box label is judged against the box's own fill, not the container.

Regression for dark tags inside pale card bodies: the theme's
white-on-light rescue used to look at the card body on the bg stack and
turned a tag's white label dark on a dark tag. Also pins the WCAG rule
behind ``Theme.text_on`` and the ``"auto"`` colour of ``card_header``.
"""

from __future__ import annotations

import re

from sciviz import (
    Box,
    Card,
    Column,
    DEFAULT_THEME,
    Diagram,
    Palette,
    card_header,
)


def _svg(element, tmp_path) -> str:
    d = Diagram(element)
    if hasattr(d, "to_svg"):
        return d.to_svg()
    d.save_all(tmp_path / "probe", formats=("svg",))
    return (tmp_path / "probe.svg").read_text()


def _fill_of(svg: str, label: str) -> str:
    m = re.search(r'<text[^>]*fill="([^"]+)"[^>]*>' + re.escape(label), svg)
    assert m, f"label {label!r} not found in the SVG"
    return m.group(1).lower()


def test_dark_tag_inside_pale_card_body_keeps_its_light_label(tmp_path):
    theme = DEFAULT_THEME
    role = Palette.orange
    chip = Box("chip text", fill=role.soft(), stroke=role, text_color="text",
               text_size="micro")
    tag = Box("D1 tag", fill=role, stroke=role, text_color="white",
              text_size="micro", text_weight="700")
    card = Card(card_header("Head", size="micro"),
                Column(chip, gap="xs", align="stretch"),
                footer=tag, role=role, padding="xs")
    svg = _svg(card, tmp_path)
    assert _fill_of(svg, "Head") == theme.text_inverse.lower()
    assert _fill_of(svg, "chip text") == theme.text.lower()
    assert _fill_of(svg, "D1 tag") == theme.text_inverse.lower()


def test_auto_label_follows_the_box_fill(tmp_path):
    theme = DEFAULT_THEME
    on_dark = Box("on dark", fill=Palette.indigo, stroke=Palette.indigo)
    on_soft = Box("on soft", fill=Palette.indigo.soft(), stroke=Palette.indigo)
    card = Card(card_header("H"), Column(on_dark, on_soft, gap="xs"),
                role=Palette.indigo)
    svg = _svg(card, tmp_path)
    assert _fill_of(svg, "on dark") == theme.text_inverse.lower()
    assert _fill_of(svg, "on soft") == theme.text.lower()


def test_text_on_picks_the_higher_wcag_contrast():
    theme = DEFAULT_THEME
    assert theme.text_on("#4338ca").lower() == theme.text_inverse.lower()
    assert theme.text_on("#f5e2da").lower() == theme.text.lower()
    # A mid orange: dark text has the higher ratio (about 5.4 vs 3.3).
    assert theme.text_on("#ea580c").lower() == theme.text.lower()
    assert theme.text_on("none").lower() == theme.text.lower()
    assert theme.contrast_ratio("#000000", "#ffffff") > 20.9


def test_color_of_auto_follows_the_current_background():
    theme = DEFAULT_THEME
    assert theme.color_of("auto").lower() == theme.text.lower()
    theme.push_bg("#4338ca")
    try:
        assert theme.color_of("auto").lower() == theme.text_inverse.lower()
        assert theme.paint_of("auto").lower() == theme.text_inverse.lower()
    finally:
        theme.pop_bg()
    theme.push_bg("#f5e2da")
    try:
        assert theme.color_of("auto").lower() == theme.text.lower()
    finally:
        theme.pop_bg()


def test_card_header_default_is_light_on_a_dark_band(tmp_path):
    theme = DEFAULT_THEME
    card = Card(card_header("Band"), Box("body"), role=Palette.teal)
    svg = _svg(card, tmp_path)
    assert _fill_of(svg, "Band") == theme.text_inverse.lower()
