"""A "skip connection" is a Flow with src and dst both exiting on the SAME
vertical side (both ``bottom`` or both ``top``).  The orthogonal router
must bridge BELOW (bottom-exit) or ABOVE (top-exit) the WHOLE diagram,
not in the narrow vertical slice between the two boxes (which would
cut through the middle of the figure).
"""
from __future__ import annotations

import re

from sciviz import Anchor, Box, Canvas, Flow, Flowed, Row, Spacer, Theme


def _svg(children, flows, theme=None):
    theme = theme or Theme()
    d = Flowed(Row(*children, gap="lg"), flows=flows)
    size = d.measure(theme)
    c = Canvas()
    d.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), size


def _lines(svg):
    for m in re.finditer(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" '
        r'x2="([-\d.]+)" y2="([-\d.]+)"', svg):
        yield tuple(float(m.group(i)) for i in range(1, 5))


def test_bottom_to_bottom_skip_bridges_below_everything():
    """src.bottom -> dst.bottom with obstacles between must bridge at a
    y-coordinate BELOW the bottom of both src and dst (and below any
    other obstacles in the path), producing a U-shaped path.
    """
    theme = Theme()
    # Three boxes in a row; skip from first to third.  The middle box
    # is a "real obstacle" -- a direct bridge in any narrow column
    # between src and dst would cross it.
    svg, size = _svg(
        [Anchor("src", Box("S", width=40, height=30)),
         Spacer(40, 0),
         Anchor("mid", Box("M", width=300, height=30)),
         Spacer(40, 0),
         Anchor("dst", Box("D", width=40, height=30))],
        flows=[Flow("src", "dst", src_side="bottom", dst_side="bottom",
                    color="text")],
    )
    # bottom edges of src/mid/dst are at y=30
    max_obstacle_bottom = 30.0
    # Collect horizontal segments (y1 == y2) produced by the flow.
    flow_segs = [seg for seg in _lines(svg)
                 if abs(seg[1] - seg[3]) < 0.1
                 and abs(seg[0] - seg[2]) > 5.0]
    # The bridge spans from near src.right to near dst.left (covering
    # the middle obstacle).  Require at least one horizontal segment
    # spanning >= 80% of the distance between src-x and dst-x.
    assert flow_segs, svg
    widest = max(flow_segs, key=lambda s: abs(s[2] - s[0]))
    span = abs(widest[2] - widest[0])
    assert span > size.w * 0.6, (widest, size.w, svg)
    # And the bridge must sit BELOW the obstacles' bottoms.
    assert widest[1] > max_obstacle_bottom + 2.0, (widest, svg)


def test_top_to_top_skip_bridges_above_everything():
    theme = Theme()
    svg, size = _svg(
        [Anchor("src", Box("S", width=40, height=30)),
         Spacer(40, 0),
         Anchor("mid", Box("M", width=300, height=30)),
         Spacer(40, 0),
         Anchor("dst", Box("D", width=40, height=30))],
        flows=[Flow("src", "dst", src_side="top", dst_side="top",
                    color="text")],
    )
    # top edges at y=0
    flow_segs = [seg for seg in _lines(svg)
                 if abs(seg[1] - seg[3]) < 0.1
                 and abs(seg[0] - seg[2]) > 5.0]
    assert flow_segs, svg
    widest = max(flow_segs, key=lambda s: abs(s[2] - s[0]))
    span = abs(widest[2] - widest[0])
    assert span > size.w * 0.6, (widest, size.w, svg)
    # Top-exit skip should bridge ABOVE all boxes (y<0 in this layout).
    assert widest[1] < -2.0, (widest, svg)
