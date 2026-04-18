"""Orthogonal flow routing must prefer inter-column gaps.

When a flow crosses between two column-like groups of anchors, its
vertical descent segment ("bridge") should land in the empty gap
between the groups, not inside either group.

This is the root cause of the inter-module arrow mess in the DeepSeek
diagram: the router picked ``gap_x`` as the midpoint between the raw
src/dst bboxes, which -- for a wide upstream block (e.g. StackedBoxes)
-- falls just inside the destination column's panel, so the descent
grazes the destination column's left edge and cuts through its other
rows' content.

Desired behaviour: the router considers all registered anchors as
obstacles and places the vertical bridge at the x-midpoint of the
widest unobstructed slice between ``src_right`` and ``dst_left``
that is clear across the full descent y-range.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Column, Flow, Flowed, Row, Spacer,
                    Theme, Canvas)


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


def _render(body, flows, theme=None):
    theme = theme or Theme()
    d = Flowed(body, flows=flows)
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


def test_vertical_bridge_falls_in_inter_column_gap():
    """Two "columns" of anchors: src column on the left, dst column on
    the right.  A Flow from src TOP to dst BOTTOM must descend in the
    clear gap between the columns -- not inside either column's x-range.

    Critical case: the src anchor (``src_top``) is a WIDE box that sticks
    out well past the centres of the siblings in its column, so the
    naive midpoint of (src.right, dst.left) would land *inside* the
    destination column.  The router must detect the dst column's
    sibling anchors as obstacles and push the bridge into the gap.
    """
    WIDE = 140.0
    NARROW = 80.0
    H = 20.0
    src_top = Anchor("src_top", Box("S top (wide)", width=WIDE, height=H))
    src_bot = Anchor("src_bot", Box("S bot", width=NARROW, height=H))
    # Destination column: a SIBLING anchor (dst_top) is WIDER than
    # dst_bot, so its left edge sits further left than dst_bot's.
    # In the DeepSeek case this models how the MTP column's
    # Transformer Block / Linear Projection rows are wider than
    # the RMSNorm row, so their left edges push left.
    dst_top = Anchor("dst_top", Box("D top (wide)", width=WIDE, height=H))
    dst_bot = Anchor("dst_bot", Box("D bot", width=NARROW, height=H))
    # Left column centred on x=WIDE/2; right column placed WIDE/2 + gap
    # to the right of that.  In the original DeepSeek example, the
    # stacked Transformer Block (wide) is src_top and rn_l (narrow) is
    # dst_bot, with the dst column's sibling rows (e.g. mtp_out) sitting
    # centred in the dst column.
    left = Column(src_top, Spacer(0, 40), src_bot, gap="md", align="center")
    right = Column(dst_top, Spacer(0, 40), dst_bot, gap="md", align="center")
    body = Row(left, Spacer(20, 0), right, gap="lg")
    svg, _, _ = _render(body, [
        Flow("src_top", "dst_bot",
             src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
    ])
    ls = _lines(svg)

    verticals = [l for l in ls
                 if abs(l["x1"] - l["x2"]) < 0.5
                 and abs(l["y1"] - l["y2"]) > 30.0]
    assert verticals, f"no bridge found; svg={svg[:2000]}"
    bridge_x = verticals[0]["x1"]

    # Bridge must sit strictly between src_top's right edge and the
    # dst column's LEFTMOST anchor edge (not inside either column).
    # src_top right edge:
    rects = re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" '
        r'height="([\d.]+)"[^/]*/>', svg)
    by_width = {}
    for x, y, w, h in rects:
        by_width.setdefault(float(w), []).append((float(x), float(y)))
    wide_rects = sorted(by_width[WIDE], key=lambda p: p[0])
    src_top_right = wide_rects[0][0] + WIDE
    # Dst column: the dst_top is ALSO WIDE; its left edge is further
    # left than dst_bot's.  The bridge must not cross into the dst
    # column's extent.
    dst_col_left = wide_rects[1][0] if len(wide_rects) > 1 else \
                    min(x for x, _ in by_width[NARROW] if x > src_top_right + 1)

    assert src_top_right < bridge_x < dst_col_left, (
        f"bridge_x={bridge_x} must fall strictly in inter-column gap "
        f"({src_top_right}, {dst_col_left}); svg={svg[:2000]}")
