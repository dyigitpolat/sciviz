"""Orthogonal :class:`Flow` with a ``label`` parameter should actually draw
the label on the path (previously it was silently dropped).
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Canvas, Row, Theme)
from sciviz.composition import Flow, Flowed


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def test_orthogonal_flow_renders_label():
    a = Anchor("A", Box("A", text_size="small"))
    b = Anchor("B", Box("B", text_size="small"))
    flowed = Flowed(Row(a, b, gap="2xl"),
                    flows=[Flow("A", "B",
                                src_side="right", dst_side="left",
                                style="orthogonal",
                                label="signal")])
    svg = _render(flowed)
    assert re.search(r'>signal<', svg), (
        f"orthogonal Flow label 'signal' missing from SVG: {svg}")
