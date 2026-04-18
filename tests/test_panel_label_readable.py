"""Panel titles should be rendered in readable BLACK (theme text color),
not in the same light blue-gray as the panel border.

Previously the title inherited ``border_color`` (= ``panel_soft``),
which made e.g. "Main Model" / "MTP Module 1" barely readable against
the white background.
"""
from __future__ import annotations

import re

from sciviz import Box, Canvas, Grid, Theme


_TEXT_RX = re.compile(
    r'<text\s+[^>]*fill="([^"]+)"[^>]*>([^<]+)</text>'
)


def _texts(svg: str):
    return [{"fill": m.group(1), "text": m.group(2)}
            for m in _TEXT_RX.finditer(svg)]


def test_panel_title_fill_is_theme_text():
    theme = Theme()
    g = Grid(
        rows=["a"],
        columns=[{"_panel": "Main Model", "a": Box("x", width=60, height=22)}],
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    texts = _texts(svg)
    title = [t for t in texts if t["text"] == "Main Model"]
    assert title, f"panel title missing in svg: {texts}"
    assert title[0]["fill"].lower() == theme.color_of("text").lower(), (
        f"panel title fill {title[0]['fill']} should equal "
        f"theme.color_of('text') = {theme.color_of('text')}")


def test_panel_subtitle_fill_is_muted_label():
    """Continuation lines (subtitle/helper text) sit below the bold
    title and should use ``muted_label`` (not ``panel_soft``).
    """
    theme = Theme()
    g = Grid(
        rows=["a"],
        columns=[{"_panel": "Main Model\n(Next Token Prediction)",
                  "a": Box("x", width=60, height=22)}],
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    texts = _texts(svg)
    sub = [t for t in texts if t["text"] == "(Next Token Prediction)"]
    assert sub, texts
    assert sub[0]["fill"].lower() == theme.color_of("muted_label").lower(), (
        f"subtitle fill {sub[0]['fill']} should equal "
        f"theme.color_of('muted_label') = {theme.color_of('muted_label')}")
