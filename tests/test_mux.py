import pytest

from sciviz import Canvas, Mux, Theme


def test_mux_orientation_owns_semantic_aspect_and_label_rotation():
    theme = Theme()
    vertical = Mux(orientation="down")
    horizontal = Mux(orientation="right")

    assert vertical.measure(theme).h > vertical.measure(theme).w
    assert horizontal.measure(theme).w > horizontal.measure(theme).h

    canvas = Canvas()
    size = vertical.measure(theme)
    vertical.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    assert "<polygon" in svg
    assert "rotate(-90" in svg
    assert ">MUX<" in svg


def test_mux_rejects_non_semantic_orientation():
    with pytest.raises(ValueError, match="orientation"):
        Mux(orientation="diagonal")


def test_horizontal_mux_label_self_sizes_a_tapered_encoder():
    theme = Theme()
    encoder = Mux(
        "Unified Encoder",
        orientation="up",
        size="sm",
        vertical_text=False,
    )
    size = encoder.measure(theme)

    assert size.w >= max(
        theme.text_width(line, "tiny", bold=True)
        for line in encoder._label_lines(theme)
    )
    assert size.w > size.h

    canvas = Canvas()
    encoder.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    assert "Unified" in svg and "Encoder" in svg
    assert "rotate(" not in svg


def test_horizontal_mux_wraps_multiword_label_without_authored_breaks():
    theme = Theme()
    encoder = Mux(
        "Vision Encoder",
        orientation="up",
        size="sm",
        vertical_text=False,
    )

    assert encoder._label_lines(theme) == ["Vision", "Encoder"]
    size = encoder.measure(theme)
    assert size.w / size.h > 1.5
