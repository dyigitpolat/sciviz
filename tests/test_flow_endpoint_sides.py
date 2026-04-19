"""Author control over flow endpoint sides.

The DeepSeek inter-module arrow needs to:
  * exit the TOP of the upstream Transformer Block, and
  * enter the BOTTOM of the downstream LEFT RMSNorm (merging with the
    embedding-layer output that also feeds that RMSNorm from below).

This exercises the orthogonal router's ability to route a flow from
``src_side="top"`` to ``dst_side="bottom"`` across columns -- a down-right
shape, not the top-to-top "both-above" shape currently in use.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Column, Row, Spacer, Theme, Canvas)
from sciviz.composition import Flow, Flowed


def _render(body, flows, theme=None):
    theme = theme or Theme()
    d = Flowed(body, flows=flows)
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


_ATTR_RX = re.compile(r'(\w[\w-]*)="([^"]*)"')
_LINE_RX = re.compile(r'<line ([^/>]*?)/>')


def _lines(svg: str) -> list[dict]:
    out = []
    for m in _LINE_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        out.append({
            "x1": float(attrs["x1"]), "y1": float(attrs["y1"]),
            "x2": float(attrs["x2"]), "y2": float(attrs["y2"]),
            "marker_end": attrs.get("marker-end"),
        })
    return out


def test_orthogonal_flow_top_to_bottom_lands_at_dst_bottom():
    """Flow src_side="top", dst_side="bottom": the final segment must
    end at the BOTTOM edge of the destination box, with an arrowhead."""
    theme = Theme()
    tf = Anchor("tf", Box("Transformer Block", width=80, height=25))
    # Destination: left RMSNorm of the next module, placed further down
    # and to the right of `tf`.  The bottom side of this box is our target.
    rn = Anchor("rn", Box("RMSNorm", width=80, height=25))
    body = Column(
        Row(tf, Spacer(80, 0), rn, gap="lg"),
        Spacer(0, 40),
        gap="md",
    )
    svg, _, _ = _render(body, [
        Flow("tf", "rn", src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
    ])
    ls = _lines(svg)
    arrow_lines = [l for l in ls if l["marker_end"]]
    assert arrow_lines, svg
    # The arrowhead terminates the last segment of the path.  Entering a
    # destination box from the BOTTOM means the final segment is going
    # UPWARD (arrow y2 strictly LESS than y1), terminating at the box's
    # bottom edge.
    ups = [l for l in arrow_lines if l["y2"] < l["y1"] - 0.5]
    assert ups, (
        f"no arrow segment enters destination from below (going up), "
        f"got {arrow_lines}")
