"""Row should align children on their *inner content bbox*, not the outer
margin-inflated bbox.

Representative failure from DeepSeek-V3: two sibling ``Anchor(Box("RMSNorm"))``
share a Row.  One is also a :class:`Flow` destination with ``dst_side="bottom"``,
so :class:`Flowed` bumps its bottom margin.  Before the fix the right RMSNorm
rendered 5 px below the left one because Row centered on the outer bbox.

After the fix, siblings with identical content but asymmetric margins render
their content at the *same* y inside the Row.
"""
from __future__ import annotations

import re

from sciviz import (
    Anchor, Box, Canvas, Flow, Flowed, Palette, Row, Theme,
)


_RECT_RX = re.compile(r'<rect ([^/]+?)/>')


def _rects(svg: str) -> list[dict]:
    out = []
    for m in _RECT_RX.finditer(svg):
        attrs = m.group(1)
        d = {}
        for k in ("x", "y", "width", "height"):
            mk = re.search(rf'{k}="([^"]+)"', attrs)
            if mk:
                d[k] = float(mk.group(1))
        fill_m = re.search(r'fill="([^"]+)"', attrs)
        d["fill"] = fill_m.group(1) if fill_m else ""
        out.append(d)
    return out


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def test_row_aligns_sibling_content_under_asymmetric_margins():
    """Two identical RMSNorm boxes in a Row, wrapped with Anchors, where only
    one Anchor gets a ``bottom`` margin bump (as :class:`Flowed` would do
    for a Flow destination).  Their content boxes must still share a y.
    """
    PROC = Palette.literal("#fbe5a8")
    left = Anchor("L", Box("RMSNorm", sub_label="FP32", text_size="small",
                           fill=PROC))
    right = Anchor("R", Box("RMSNorm", sub_label="FP32", text_size="small",
                            fill=PROC))
    row = Row(left, right, gap="md", align="center")
    flowed = Flowed(row, flows=[
        # This flow sinks into ``L`` from below, bumping L's bottom margin.
        Flow("X", "L", src_side="top", dst_side="bottom",
             style="orthogonal"),
    ])

    svg = _render(flowed)
    rects = [r for r in _rects(svg) if r.get("fill", "").lower() == "#fbe5a8"]
    assert len(rects) == 2, f"expected 2 RMSNorm rects, got {len(rects)}: {rects}"
    y_left, y_right = rects[0]["y"], rects[1]["y"]
    assert abs(y_left - y_right) < 0.5, (
        f"RMSNorm boxes misaligned: y_left={y_left}, y_right={y_right}")
    h_left, h_right = rects[0]["height"], rects[1]["height"]
    assert abs(h_left - h_right) < 0.5, (
        f"RMSNorm boxes heights differ: {h_left} vs {h_right}")
