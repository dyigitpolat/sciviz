"""Arrowheads should visibly touch their target box, with no gap.

When a line with ``marker-end`` terminates exactly on a target box edge,
a naive SVG marker (``refX`` placed at the triangle's *tip*) causes the
whole triangle body to sit OUTSIDE the box.  At typical stroke widths,
the tip pixel gets absorbed by the box's own border, producing the
"floating arrowhead with a gap" artifact seen in rasterised output.

We fix this at the marker definition: ``refX`` is moved so the triangle
tip extends PAST the nominal line endpoint (into the target box).  The
shaft still ends on the edge; the triangle visibly crosses the boundary
rather than parking outside of it.
"""
from __future__ import annotations

import re

from sciviz import Canvas


_MARKER_RX = re.compile(
    r'<marker[^>]+id="([^"]+)"[^>]+viewBox="0 0 10 10"'
    r'[^>]+refX="([-\d.]+)"[^>]+refY="([-\d.]+)"[^>]+'
    r'markerWidth="([-\d.]+)"[^>]+markerHeight="([-\d.]+)"'
)


def test_arrow_marker_tip_extends_past_line_endpoint():
    """The marker's reference point must sit at the triangle TAIL or
    CENTRE -- never at the tip.  That way the triangle body extends from
    the line endpoint FORWARD along the flow direction, so the tip
    visibly penetrates the target and there is no visual gap at the
    box boundary.
    """
    c = Canvas()
    mid = c.define_arrow_marker(
        color="#000000", stroke_width=1.0, arrow_size=6.0)
    svg = c.to_svg(10, 10)
    m = _MARKER_RX.search(svg)
    assert m, f"no marker in svg: {svg}"
    _mid, refX, _refY, mw, _mh = m.group(1), float(m.group(2)), \
        float(m.group(3)), float(m.group(4)), float(m.group(5))
    # The triangle path is "M0,0 L10,5 L0,10 z" in a 10x10 viewBox, so
    # its tip is at x=10.  To avoid the tip sitting outside the target,
    # refX must be strictly less than the tip -- closer to the tail
    # (x=0) than to the tip (x=10).  Equivalently, the triangle extends
    # FORWARD from the line endpoint.
    assert refX < 10.0 - 1e-6, (
        f"refX={refX} puts the reference at (or past) the triangle tip; "
        "this leaves the whole triangle OUTSIDE the target -- visible "
        "gap in rasterised output.")
    # Guard against the other extreme: if refX is exactly 0 we keep the
    # triangle entirely past the endpoint, which is fine, but we want
    # at least ~half the marker to sit inside the target for clean
    # contact.  Require refX <= markerWidth/2 on the 0-10 scale.
    assert refX <= 5.0 + 1e-6, (
        f"refX={refX} keeps the triangle mostly outside the target; "
        "arrows will still appear to hover above the box edge.")
