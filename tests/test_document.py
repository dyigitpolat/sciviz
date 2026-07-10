"""Semantic folded-corner documents remain recognisable and measured."""

from sciviz import Canvas, Document, Math, Palette, Theme


def test_document_renders_outline_and_fold_with_portrait_aspect():
    theme = Theme()
    document = Document(
        Math(r"t_{\mathrm{achieved}}"),
        fill=Palette.gray.soft(),
        stroke=Palette.gray,
    )
    size = document.measure(theme)
    canvas = Canvas()
    document.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert size.w / size.h <= Document._MAX_WIDTH_HEIGHT
    assert svg.count("<path") >= 2
    assert "<text" not in svg  # Math is path-rendered, not fallback text.


def test_document_inflation_is_a_minimum_not_an_aspect_override():
    theme = Theme()
    document = Document("artifact", size="sm")
    document.inflate_to(120, 60)
    size = document.measure(theme)
    assert size.w >= 120 and size.h >= 60
    assert size.w / size.h <= Document._MAX_WIDTH_HEIGHT
