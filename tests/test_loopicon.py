from sciviz import Canvas, DEFAULT_THEME, LoopIcon


def test_loopicon_arc_publishes_local_ink_bounds():
    """A right-shifted arc must not inflate the canvas vertically."""
    icon = LoopIcon(size=18.0)
    canvas = Canvas()

    icon.render(canvas, 900.0, 20.0, DEFAULT_THEME)

    x0, y0, x1, y1 = canvas.ink_bbox
    assert 895.0 < x0 < 910.0
    assert x1 < 925.0
    assert 15.0 < y0 < 35.0
    assert y1 < 45.0
