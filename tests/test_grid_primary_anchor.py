"""Grid cell centering should key off an element's ``primary_anchor`` when
present, so that ``Labeled(Box, side_label)`` composites place the Box on
the column axis and let the side label extend freely into the inter-column
gap.

Representative failure: in DeepSeek-V3 the main column ``ce`` row holds
``Labeled(Anchor("main_ce", Cross-Entropy Loss), loss_math("Main"))``.
Because ``Labeled`` is wider than a plain Box, the Grid's naive center
pushes the Box left of the axis while ``Output Head`` (plain Box) sits
centered.

After the fix, the Cross-Entropy Loss Box and the Output Head Box share
the same horizontal center in their column.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Canvas, Grid, Palette, Theme)
from sciviz.composition import Labeled
from sciviz.math import Math


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


def test_grid_centers_on_primary_anchor_not_composite():
    PROC = Palette.literal("#fbe5a8")
    SHARED = Palette.literal("#c1e1c1")
    ce = Labeled(
        Anchor("ce_a", Box("Cross-Entropy Loss", sub_label="FP32",
                           text_size="small", fill=PROC)),
        Math(r"\mathcal{L}_{\text{Main}}", size="label"),
    )
    out = Anchor("out_a", Box("Output Head", sub_label="BF16",
                              text_size="small", fill=SHARED))
    g = Grid(rows=["ce", "out"],
             columns=[{"ce": ce, "out": out}])

    svg = _render(g)
    rects = _rects(svg)
    proc_rects = [r for r in rects if r["fill"].lower() == "#fbe5a8"]
    shared_rects = [r for r in rects if r["fill"].lower() == "#c1e1c1"]
    assert proc_rects and shared_rects, rects

    ce_cx = proc_rects[0]["x"] + proc_rects[0]["width"] / 2
    out_cx = shared_rects[0]["x"] + shared_rects[0]["width"] / 2
    assert abs(ce_cx - out_cx) < 0.5, (
        f"CE box center {ce_cx} should equal Output Head center {out_cx}")
