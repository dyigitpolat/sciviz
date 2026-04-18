"""``Badge("+", bordered=True)`` is the "paper-style operator glyph":
white interior, dark ring, dark plus glyph.  Other Badge uses (numbered
markers like ``Badge("1")``) keep their filled pill look.
"""
from __future__ import annotations

import re

from sciviz import Badge, Canvas, Theme


def _render(b):
    theme = Theme()
    size = b.measure(theme)
    c = Canvas()
    b.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), theme


def test_bordered_plus_badge_defaults_to_paper_style():
    """bordered=True with no color= should render white interior, dark
    stroke, dark glyph -- the common "inline addition" pill."""
    svg, theme = _render(Badge("+", bordered=True))
    circle = re.search(r'<circle[^/]+/>', svg)
    assert circle, svg
    circle_str = circle.group(0)
    # Fill should be the "page" colour (white / theme background), not
    # a palette colour.
    fill_m = re.search(r'fill="([^"]+)"', circle_str)
    assert fill_m, circle_str
    fill = fill_m.group(1)
    text_col = theme.color_of("text")
    assert fill != text_col, (
        f"bordered operator Badge should not be filled with text colour; "
        f"got fill={fill}")
    info = theme.color_of("info")
    assert fill != info, (
        f"bordered operator Badge should not default to info colour; "
        f"got fill={fill}")
    # Stroke should be dark (text colour)
    stroke_m = re.search(r'stroke="([^"]+)"', circle_str)
    assert stroke_m and stroke_m.group(1) == text_col, (
        f"stroke should be text colour; circle={circle_str}")
    # The glyph is rendered as a <text ... fill="text_colour"> (dark)
    glyph = re.search(r'<text[^>]+fill="([^"]+)"[^>]*>\+</text>', svg)
    assert glyph, svg
    assert glyph.group(1) == text_col, (
        f"'+' glyph should be text colour; got {glyph.group(1)}")


def test_unbordered_numbered_badge_still_filled():
    """Badge("1") -- numbered marker, no border -- keeps its info-blue
    fill + white glyph (the traditional "reference number" look)."""
    svg, theme = _render(Badge("1"))
    circle = re.search(r'<circle[^/]+/>', svg)
    assert circle, svg
    circle_str = circle.group(0)
    fill_m = re.search(r'fill="([^"]+)"', circle_str)
    assert fill_m, circle_str
    assert fill_m.group(1) == theme.color_of("info"), (
        f"unbordered Badge should still default to info fill; circle={circle_str}")
