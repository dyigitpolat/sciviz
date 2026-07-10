from __future__ import annotations

from sciviz import Box, Caption, Diagram, Theme


def test_diagram_wraps_caption_to_a_body_proportional_paragraph():
    theme = Theme()
    body = Box("body", width=120, height=30)
    caption = Caption(" ".join(["long caption text"] * 20))
    diagram = Diagram.for_paper(body, footer=caption, theme=theme)

    diagram.measure()
    measured = caption.measure(theme)

    assert measured.w <= body.measure(theme).w * Caption._BODY_WIDTH_FACTOR
    assert measured.h > theme.text_height("small")


def test_explicit_caption_ceiling_remains_authoritative():
    theme = Theme()
    caption = Caption("one two three four five six seven", max_width=70)
    caption.fit_width(300)
    assert caption.measure(theme).w <= 70


def test_caption_accepts_semantic_weight():
    theme = Theme()
    normal = Caption("Figure 1: Caption")
    bold = Caption("Figure 1: Caption", weight="700")
    assert bold.measure(theme).w > normal.measure(theme).w


def test_wide_body_does_not_force_long_caption_onto_one_line():
    theme = Theme()
    caption = Caption(" ".join(["caption word"] * 20), size="label")
    caption.fit_width(2000)
    assert caption.measure(theme).w <= theme.size_px("label") * 90
    assert caption.measure(theme).h > theme.text_height("label")
