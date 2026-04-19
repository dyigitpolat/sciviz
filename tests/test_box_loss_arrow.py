"""The "Cross-Entropy Loss ──> L_MTP" pattern needs a *drawn* arrow
(with arrowhead) emerging from the right edge of the box into the label,
not a text-based arrow character.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Row, Theme, Canvas, Spacer)
from sciviz.composition import Flow, Flowed
from sciviz.math import Math


def _render(elem, theme=None) -> tuple[str, float, float]:
    theme = theme or Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


def test_box_to_label_renders_drawn_arrow():
    """A Flow from the right side of a Box to the left side of a Math
    label renders as an SVG line (or path) with an arrowhead marker.
    """
    theme = Theme()
    body = Row(
        Anchor("box", Box("Cross-Entropy Loss", sub_label="FP32")),
        Spacer(28, 0),
        Anchor("loss", Math(r"\mathcal{L}_{\text{MTP}}^{2}", size="label")),
        gap="sm",
    )
    d = Flowed(body, flows=[
        Flow("box", "loss", src_side="right", dst_side="left",
             curvature=0, color="text"),
    ])
    svg, _, _ = _render(d, theme)
    # must have at least one line/path with marker-end referencing a flow marker
    assert re.search(r'marker-end="url\(#[^)]+\)"', svg), svg


def test_box_to_label_arrow_starts_at_box_right_edge():
    """The arrow shaft begins at the x-coordinate of the box's right edge
    (within a small tolerance).
    """
    theme = Theme()
    body = Row(
        Anchor("box", Box("CE Loss", sub_label="FP32")),
        Spacer(28, 0),
        Anchor("loss", Math(r"\mathcal{L}^{2}", size="label")),
        gap="sm",
    )
    d = Flowed(body, flows=[
        Flow("box", "loss", src_side="right", dst_side="left",
             curvature=0, color="text"),
    ])
    svg, _, _ = _render(d, theme)
    box_size = Box("CE Loss", sub_label="FP32").measure(theme)
    right_edge = box_size.w
    # Orthogonal flows emit <line> segments; the first segment starts at
    # the box's right edge.  Bezier flows (if ever re-enabled on this
    # test) would emit a <path d="M x,y ...">.
    m = re.search(r'<line x1="([0-9.]+)"', svg) \
        or re.search(r' d="M ([0-9.]+),', svg)
    assert m, svg
    mx = float(m.group(1))
    assert abs(mx - right_edge) < 2.0, (mx, right_edge)
