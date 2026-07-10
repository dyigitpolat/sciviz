"""Semantic storage cylinders are measured, printable architecture nodes."""

from sciviz import Canvas, Cylinder, Math, Palette, Theme


def test_cylinder_grows_for_multiline_label_and_renders_two_curves():
    theme = Theme()
    cylinder = Cylinder(
        "KV pool\nBFP8",
        size="sm",
        fill=Palette.blue.soft(),
        stroke=Palette.blue,
    )
    size = cylinder.measure(theme)
    canvas = Canvas()
    cylinder.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert size.w >= theme.unit * 9
    assert size.h >= theme.unit * 5
    assert size.w / size.h <= Cylinder._MAX_ASPECT
    assert svg.count("<path") == 2
    assert "KV pool" in svg and "BFP8" in svg


def test_cylinder_accepts_math_label_and_semantic_inflation():
    theme = Theme()
    cylinder = Cylinder(Math(r"K_{V}"), size="sm")
    cylinder.inflate_to(120, 60)
    assert cylinder.measure(theme).w == 120
    # inflate_to is a minimum-size contract; silhouette constraints may grow
    # the other axis further to preserve a recognisable storage cylinder.
    assert cylinder.measure(theme).h >= 60
    assert cylinder.measure(theme).w / cylinder.measure(theme).h \
        <= Cylinder._MAX_ASPECT
