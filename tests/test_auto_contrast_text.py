"""Tests for the bg-aware automatic-contrast text colour resolution.

Authors who write ``color="white"`` inside the body of a soft-fill Card
should not end up with invisible text. Card.render pushes the body bg
onto the theme's bg stack; theme.color_of consults the stack and
auto-swaps ``text_inverse`` to ``text`` when the bg is light.
"""

from __future__ import annotations

from sciviz import (
    Card,
    DEFAULT_THEME,
    Palette,
    Text,
    card_header,
)


def test_color_of_white_swaps_to_dark_when_bg_is_light() -> None:
    theme = DEFAULT_THEME
    # No bg context -> "white" is white.
    assert theme.color_of("white").lower() == theme.text_inverse.lower()
    # Push a light soft-tint colour.
    theme.push_bg(Palette.blue.soft())
    try:
        resolved = theme.color_of("white")
        # On a light bg, white auto-corrects to the dark text colour.
        assert resolved.lower() == theme.text.lower()
    finally:
        theme.pop_bg()
    # Back to no context: "white" is white again.
    assert theme.color_of("white").lower() == theme.text_inverse.lower()


def test_color_of_white_stays_white_when_bg_is_dark() -> None:
    theme = DEFAULT_THEME
    # The saturated role colour is dark enough for white to read.
    theme.push_bg(Palette.blue)
    try:
        assert theme.color_of("white").lower() == theme.text_inverse.lower()
    finally:
        theme.pop_bg()


def test_contrast_text_picks_white_on_dark_text_on_light() -> None:
    theme = DEFAULT_THEME
    # On the saturated blue, white is readable.
    assert theme.contrast_text(Palette.blue).lower() == theme.text_inverse.lower()
    # On the soft blue, dark text is readable.
    assert theme.contrast_text(Palette.blue.soft()).lower() == theme.text.lower()


def test_card_body_white_text_renders_visible(tmp_path) -> None:
    # Regression: a Card body with explicit color="white" should not
    # produce an invisible label. We assert by checking that the SVG
    # text fill is the dark text colour, not the white one.
    card = Card(
        card_header("Header", icon="cpu"),
        Text("body line", color="white", size="tiny"),
        role=Palette.blue,
    )
    from sciviz import Diagram
    out = tmp_path / "card_body"
    Diagram.for_paper(card).save_all(out, formats=("svg",))
    svg = (out.with_suffix(".svg")).read_text()
    # The body line "body line" should appear with the theme's dark
    # text fill, not text_inverse.
    assert ">body line<" in svg
    # The dark text colour should appear in the SVG; text_inverse
    # ("#ffffff") should not be the only text fill present in the body.
    assert DEFAULT_THEME.text.lower() in svg.lower()
