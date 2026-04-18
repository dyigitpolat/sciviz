"""Arrowhead markers should be proportional to stroke width.

Historically the Canvas defined arrowhead markers with a fixed absolute
size (e.g. 6px), which produces visually huge heads next to the default
0.9px connector stroke.  The library should instead scale marker size
with stroke width so arrows read as tidy terminators, not black triangles.
"""
from __future__ import annotations

import re

from sciviz import Canvas, Theme


def test_canvas_arrowhead_marker_size_scales_with_stroke():
    """Calling ``define_arrow_marker(stroke_width=sw)`` yields a marker
    whose ``markerWidth``/``markerHeight`` are close to a small multiple
    of ``sw`` (not an absolute pixel constant like 6).

    The exact factor is an implementation detail but should be in the
    range ~3..6 of the stroke width -- in particular, a 0.9px stroke
    should produce a marker smaller than 8px.
    """
    c = Canvas()
    # New API
    assert hasattr(c, "define_arrow_marker"), (
        "Canvas should expose define_arrow_marker(stroke_width=...)")
    mid = c.define_arrow_marker(color="#000000", stroke_width=0.9)
    svg = c.to_svg(10, 10)
    m = re.search(
        r'<marker[^>]+id="' + re.escape(mid) + r'"[^>]+markerWidth="([^"]+)"[^>]+markerHeight="([^"]+)"',
        svg)
    assert m, svg
    mw = float(m.group(1))
    mh = float(m.group(2))
    assert mw < 8.0 and mh < 8.0, (
        f"marker too large for 0.9px stroke: {mw}x{mh}")


def test_canvas_arrowhead_grows_with_thicker_stroke():
    c = Canvas()
    m_thin = c.define_arrow_marker(color="#000000", stroke_width=0.8)
    m_thick = c.define_arrow_marker(color="#000000", stroke_width=2.5)
    svg = c.to_svg(10, 10)
    def width(mid):
        m = re.search(
            r'<marker[^>]+id="' + re.escape(mid) + r'"[^>]+markerWidth="([^"]+)"',
            svg)
        return float(m.group(1))
    assert width(m_thin) < width(m_thick)
