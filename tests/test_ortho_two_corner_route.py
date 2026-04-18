"""Orthogonal Flow should use a 2-corner path when it's unobstructed.

For the common DeepSeek shape -- a source in one column whose top feeds
into a destination in an adjacent column one row up -- the aesthetic,
minimum-complexity path is:

  up from (sx, sy) to (sx, bridge_y)
  across from (sx, bridge_y) to (dx, bridge_y)
  up from (dx, bridge_y) to (dx, dy)

That's 3 segments with 2 right-angle corners.

The previous router always emitted a 5-segment "tap → bridge → tap"
staircase, producing 4 corners including a vestigial 2px bridge stub
between tap points.  When no obstacle sits between src and dst, this
extra zig-zag adds visual clutter for no gain.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Canvas, Column, Flow, Flowed, Row,
                    Spacer, Theme)


_LINE_RX = re.compile(
    r'<line\s+x1="([-\d.]+)"\s+y1="([-\d.]+)"'
    r'\s+x2="([-\d.]+)"\s+y2="([-\d.]+)"([^/]*)/>')


def _segments(svg: str):
    return [
        (float(m.group(1)), float(m.group(2)),
         float(m.group(3)), float(m.group(4)),
         m.group(5))
        for m in _LINE_RX.finditer(svg)
    ]


def _flow_segments(svg: str):
    """Segments belonging to the flow (those carrying a marker-end OR
    chained adjacently -- simplest heuristic: any line with the flow
    stroke color ``#0b1220`` and a ``stroke-width`` attribute)."""
    out = []
    for x1, y1, x2, y2, rest in _segments(svg):
        if "#0b1220" in rest and "stroke-width" in rest:
            out.append((x1, y1, x2, y2))
    return out


def test_orthogonal_flow_unobstructed_uses_two_corner_path():
    """When src (col A, row 2) connects to dst (col B, row 1) in the same
    panel with nothing between them, the router should emit exactly
    three segments (up, across, up) -- two right-angle corners."""
    theme = Theme()
    src = Anchor("src", Box("SRC", width=60, height=22))
    dst = Anchor("dst", Box("DST", width=60, height=22))

    body = Column(
        Row(Spacer(120, 0), dst, gap="lg"),
        Spacer(0, 40),
        Row(src, Spacer(120, 0), gap="lg"),
        gap="md",
    )
    d = Flowed(body, flows=[
        Flow("src", "dst", src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
    ])
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)

    segs = _flow_segments(svg)
    assert segs, f"no flow segments in svg:\n{svg}"

    horiz = [s for s in segs if abs(s[3] - s[1]) < 0.5]
    vert = [s for s in segs if abs(s[2] - s[0]) < 0.5]

    assert len(horiz) == 1, (
        f"expected exactly one horizontal bridge segment, got "
        f"{len(horiz)}: horiz={horiz} vert={vert}")
    assert len(vert) == 2, (
        f"expected exactly two vertical legs (src-exit and dst-entry), "
        f"got {len(vert)}: horiz={horiz} vert={vert}")

    (hx1, hy1, hx2, hy2) = horiz[0]
    v1, v2 = vert
    assert abs(v1[0] - hx1) < 0.5 or abs(v1[0] - hx2) < 0.5, (
        f"vertical leg {v1} not aligned with horizontal endpoints "
        f"{horiz[0]}")
    assert abs(v2[0] - hx1) < 0.5 or abs(v2[0] - hx2) < 0.5, (
        f"vertical leg {v2} not aligned with horizontal endpoints "
        f"{horiz[0]}")
