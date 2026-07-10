"""Typographic alignment for mixed inline content."""

from sciviz import Inline, Math, Text, Theme


def test_inline_aligns_text_and_math_on_a_shared_baseline():
    theme = Theme()
    text = Text("over", size="label")
    math = Math(r"[R_i,G_i]", size="section")
    inline = Inline(text, math, gap="xs")

    text_box = text.measure(theme)
    math_box = math.measure(theme)
    inline_box = inline.measure(theme)

    assert inline_box.w > text_box.w + math_box.w
    # Their ascent/descent bands differ, so a true shared-baseline line is
    # slightly taller than naïvely centring the two outer SVG boxes.
    assert inline_box.h > max(text_box.h, math_box.h)
