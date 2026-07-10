"""Text contrast context must never recolor shape paint."""

from sciviz import Box, Canvas, Card, Palette, Theme


def test_white_box_stays_white_inside_light_card_body():
    theme = Theme()
    card = Card(
        "Header",
        Box("paper", fill="white", stroke=Palette.blue),
        role=Palette.blue,
        body_fill="white",
    )
    size = card.measure(theme)
    canvas = Canvas()
    card.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert svg.count('fill="#ffffff"') >= 2
    assert '>paper<' in svg


def test_paint_resolution_ignores_light_background_contrast_stack():
    theme = Theme()
    theme.push_bg(theme.primary_soft)
    try:
        assert theme.color_of("white") == theme.text
        assert theme.paint_of("white") == theme.text_inverse
    finally:
        theme.pop_bg()
