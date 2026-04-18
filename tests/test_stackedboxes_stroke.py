"""StackedBoxes should match plain Box's stroke default so a stack in a
Row with regular boxes doesn't visibly change border colour.
"""
from __future__ import annotations

import re

from sciviz import Canvas, Palette, StackedBoxes, Theme


_RECT_RX = re.compile(r'<rect ([^/]+?)/>')


def test_stackedboxes_default_stroke_matches_text():
    """When no ``stroke=`` is passed, StackedBoxes should default to the
    theme's text color (same default as :class:`Box`) so the stack's border
    colour matches siblings.
    """
    theme = Theme()
    PROC = Palette.literal("#fbe5a8")
    sb = StackedBoxes(4, "Transformer Block", fill=PROC)
    size = sb.measure(theme)
    canvas = Canvas()
    sb.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)

    strokes = []
    for m in _RECT_RX.finditer(svg):
        attrs = m.group(1)
        fill = re.search(r'fill="([^"]+)"', attrs)
        stroke = re.search(r'stroke="([^"]+)"', attrs)
        if fill and fill.group(1).lower() == "#fbe5a8" and stroke:
            strokes.append(stroke.group(1).lower())
    assert strokes, svg
    expected = theme.color_of("text").lower()
    for s in strokes:
        assert s == expected, f"StackedBoxes stroke {s} != expected {expected}"
