"""Arrowhead markers: default behaviour and explicit-size behaviour.

When ``define_arrow_marker`` is called without an explicit ``arrow_size``,
we fall back to scaling the marker linearly with stroke width so
sub-pixel strokes still get a visible head and thick strokes don't get
a tiny head.  When ``arrow_size`` IS provided (the preferred path for
diagrams that want uniform heads across varied stroke widths), the
marker's dimensions equal ``arrow_size`` regardless of stroke width.
"""
from __future__ import annotations

import re

from sciviz import Canvas, Theme


_MARKER_SIZE_RX = re.compile(
    r'<marker[^>]+id="{id}"[^>]+markerWidth="([-\d.]+)"'
    r'[^>]+markerHeight="([-\d.]+)"'
)


def _marker_wh(svg: str, mid: str):
    m = re.search(
        _MARKER_SIZE_RX.pattern.replace("{id}", re.escape(mid)),
        svg)
    assert m, f"marker {mid!r} not found"
    return float(m.group(1)), float(m.group(2))


def test_canvas_arrowhead_marker_size_scales_with_stroke_when_no_arrow_size():
    """Legacy behaviour: when no explicit arrow_size is given, the head
    scales with stroke width (so 0.9 px stroke -> small head).
    """
    c = Canvas()
    mid = c.define_arrow_marker(color="#000000", stroke_width=0.9)
    svg = c.to_svg(10, 10)
    mw, mh = _marker_wh(svg, mid)
    assert mw < 8.0 and mh < 8.0, (
        f"marker too large for 0.9px stroke: {mw}x{mh}")


def test_canvas_arrowhead_grows_with_thicker_stroke_when_no_arrow_size():
    c = Canvas()
    m_thin = c.define_arrow_marker(color="#000000", stroke_width=0.8)
    m_thick = c.define_arrow_marker(color="#000000", stroke_width=2.5)
    svg = c.to_svg(10, 10)
    w_thin, _ = _marker_wh(svg, m_thin)
    w_thick, _ = _marker_wh(svg, m_thick)
    assert w_thin < w_thick


def test_canvas_arrowhead_marker_uniform_with_explicit_arrow_size():
    """With an explicit arrow_size, marker dimensions are INDEPENDENT of
    stroke width -- same size whether tied to a thin column-flow line or
    a thick connector.
    """
    c = Canvas()
    theme = Theme()
    m_thin = c.define_arrow_marker(
        color="#000000", stroke_width=theme.line,
        arrow_size=theme.arrow_size)
    m_thick = c.define_arrow_marker(
        color="#000000", stroke_width=theme.connector,
        arrow_size=theme.arrow_size)
    svg = c.to_svg(10, 10)
    w_thin, h_thin = _marker_wh(svg, m_thin)
    w_thick, h_thick = _marker_wh(svg, m_thick)
    assert (w_thin, h_thin) == (w_thick, h_thick), (
        f"arrow_size should pin size; got thin={w_thin}x{h_thin} "
        f"vs thick={w_thick}x{h_thick}")
    assert abs(w_thin - theme.arrow_size) < 0.01
