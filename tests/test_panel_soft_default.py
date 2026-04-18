"""Grid's default panel dashed border should be a SOFT blue-gray, not a
dark gray.  The theme exposes a ``panel_soft`` token for this.
"""
from __future__ import annotations

import re

from sciviz import Box, Canvas, Grid, Theme


def test_grid_default_panel_color_is_soft_blue_gray():
    theme = Theme()
    panel_soft = theme.color_of("panel_soft").lower()
    # The token exists and is visibly lighter than the previous hard gray.
    # Previous default: "#9aa7b5".  New default should be perceptibly
    # lighter than that (higher luminance).
    def lum(h):
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 0.299 * r + 0.587 * g + 0.114 * b
    assert lum(panel_soft) > lum("#9aa7b5"), (
        f"panel_soft {panel_soft} should be lighter than old #9aa7b5")


def test_grid_panel_border_uses_theme_panel_soft_by_default():
    theme = Theme()
    want = theme.color_of("panel_soft").lower()
    g = Grid(rows=["a"], columns=[{"_panel": "P", "a": Box("x")}])
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h).lower()
    # Find the dashed rect
    m = re.search(r'<rect [^/]*stroke-dasharray="[^"]+"[^/]*/>', svg)
    assert m, svg
    stroke_m = re.search(r'stroke="([^"]+)"', m.group(0))
    assert stroke_m, m.group(0)
    assert stroke_m.group(1).lower() == want, (
        f"panel stroke {stroke_m.group(1)} != {want}")
