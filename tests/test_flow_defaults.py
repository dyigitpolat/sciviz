"""Flow defaults: orthogonal routing + neutral dark stroke.

Papers almost always route connectors as axis-aligned right-angle lines
("Manhattan" style), not Bezier curves.  The library should default to
that and default to the neutral text colour, so authors need to call out
the EXCEPTIONS (curves, accent arrows), not the common case.
"""
from __future__ import annotations

import re

from sciviz import Anchor, Box, Canvas, Flow, Flowed, Row, Spacer, Theme


def _render(children, flows, theme=None):
    theme = theme or Theme()
    d = Flowed(Row(*children, gap="lg"), flows=flows)
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def test_flow_default_style_is_orthogonal():
    """A Flow created without style= should render as axis-aligned
    right-angle <line> segments, not as a curved <path>.
    """
    theme = Theme()
    svg = _render(
        [Anchor("a", Box("A", width=40, height=20)),
         Spacer(40, 0),
         Anchor("b", Box("B", width=40, height=20))],
        flows=[Flow("a", "b", src_side="right", dst_side="left")],
    )
    # orthogonal style emits <line> primitives; bezier emits a single
    # <path d="M ... C ..."> element.  Presence of a path with "C" is
    # the bezier fingerprint.
    assert not re.search(r'<path[^>]*d="[^"]*[CcSsQqTt]', svg), (
        f"default Flow should not emit a Bezier path; svg=\n{svg}")
    # Must have at least one straight line segment.
    assert re.search(r'<line ', svg), (
        f"default orthogonal Flow should emit <line> segments; svg=\n{svg}")


def test_flow_default_color_is_neutral_text():
    """A Flow with no color= should use the theme's text colour (neutral
    dark), not an orange accent.  Authors opt INTO accents."""
    theme = Theme()
    svg = _render(
        [Anchor("a", Box("A", width=40, height=20)),
         Spacer(40, 0),
         Anchor("b", Box("B", width=40, height=20))],
        flows=[Flow("a", "b", src_side="right", dst_side="left")],
    )
    expected = theme.color_of("text")
    # Every connector line / path the Flow emits must be drawn in the
    # expected colour (at least one such stroke must match).
    assert f'stroke="{expected}"' in svg, (
        f"expected Flow stroke={expected}; svg=\n{svg}")
    # And must NOT be drawn in the "warn" (orange accent) colour.
    warn = theme.color_of("warn")
    if warn != expected:
        # Acceptable: "warn" doesn't appear as a STROKE in a default flow.
        assert f'stroke="{warn}"' not in svg, (
            f"default Flow should not use warn accent; svg=\n{svg}")
