"""``Box(label=Math(...))`` -- label accepts a rendered Element, not only str.

Authors writing paper figures commonly want a Box whose label is a LaTeX
expression (e.g. ``W_{\\text{down}}^{(i)}``) rather than a plain-text
string.  Forcing them to encode it with unicode sub/superscript code
points (a) looks inferior, (b) misses symbols like ``\\mathcal``, and
(c) breaks the moment the label needs formulas.

The library should let any Element stand in as the label.  The box
sizes itself to fit, and centres the element vertically and
horizontally inside.
"""
from __future__ import annotations

from sciviz import Box, Canvas, Math, Theme


def test_box_accepts_element_label_measure_fits_it():
    theme = Theme()
    m = Math(r"W_{\text{down}}^{(i)}")
    msize = m.measure(theme)
    # Box with an element label, no width/height -- should be at least
    # as wide and tall as the math content plus some padding.
    b = Box(m)
    bsize = b.measure(theme)
    assert bsize.w >= msize.w, (bsize.w, msize.w)
    assert bsize.h >= msize.h, (bsize.h, msize.h)


def test_box_element_label_renders_centered():
    """When rendered, the math element's group transform sits roughly at
    the box's centre minus half the math size."""
    theme = Theme()
    m = Math(r"\mathcal{L}(O,V)")
    b = Box(m, width=100.0, height=28.0)
    canvas = Canvas()
    b.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(100, 28)
    # At least one <g class="sciviz-math"> with a translate(x, y) was emitted
    import re
    m_tr = re.search(
        r'<g transform="translate\(([-\d.]+) ([-\d.]+)\)" class="sciviz-math"',
        svg)
    assert m_tr, svg
    tx, ty = float(m_tr.group(1)), float(m_tr.group(2))
    msize = m.measure(theme)
    # Expected centre of math content at box centre (50, 14)
    cx_math = tx + msize.w / 2
    cy_math = ty + msize.h / 2
    assert abs(cx_math - 50.0) < 2.0, (cx_math, svg)
    assert abs(cy_math - 14.0) < 2.0, (cy_math, svg)
