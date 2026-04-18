"""Paper figures use distinct grid lines between the cells of a stacked
vector (e.g. ``|t1|t2|t3|``), which makes it read as a segmented
sequence rather than a solid bar.

VectorTiles should therefore draw each cell with a visible hairline
stroke by default, not no stroke.  The separator reads automatically
without the author remembering to set ``stroke=``.
"""
from __future__ import annotations

import re

from sciviz import VectorTiles, Canvas, Theme


def test_vector_tiles_each_cell_has_default_stroke():
    theme = Theme()
    v = VectorTiles(4, color="info")
    size = v.measure(theme)
    c = Canvas()
    v.render(c, 0.0, 0.0, theme)
    svg = c.to_svg(size.w, size.h)
    # Find rects in the SVG body.  Each tile must have a non-"none" stroke.
    rects = re.findall(r'<rect[^/]+/>', svg)
    # skip the outer background rect (stroke may be absent/zero)
    tile_rects = [r for r in rects if 'stroke="none"' not in r]
    assert len(tile_rects) >= 4, tile_rects
    # At least four tiles have a visible stroke (hairline-ish width)
    strokes = []
    for r in tile_rects[:4]:
        m = re.search(r'stroke-width="([-\d.]+)"', r)
        if m:
            strokes.append(float(m.group(1)))
    assert strokes, tile_rects
    # All strokes are small (hairline) but positive
    for sw in strokes:
        assert 0.0 < sw < 1.2, (sw, tile_rects)


def test_vector_tiles_stroke_opt_out_with_stroke_none():
    """Authors can still opt out with ``stroke=None`` -- this should
    draw cells with NO stroke."""
    theme = Theme()
    v = VectorTiles(3, color="info", stroke="none")
    size = v.measure(theme)
    c = Canvas()
    v.render(c, 0.0, 0.0, theme)
    svg = c.to_svg(size.w, size.h)
    rects = re.findall(r'<rect[^/]+/>', svg)
    tile_rects = [r for r in rects[1:]]  # skip background
    # No tile has a non-"none" stroke OR a positive stroke-width
    for r in tile_rects:
        m = re.search(r'stroke-width="([-\d.]+)"', r)
        if m:
            assert float(m.group(1)) == 0.0, (r, tile_rects)
