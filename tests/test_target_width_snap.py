"""Target-width snapping: figures land at EXACTLY the declared width.

The density fixed-point in ``_fit_density`` converges to the target
from above (text widths do not scale with density), so a fitted canvas
structurally ends a fraction of a point over the target.  The exported
canvas must still be pinned to exactly ``target_width_pt`` -- widened
when under, trimmed by a sub-point sliver of outer margin when a hair
over -- so ``\\includegraphics[width=...]`` scales by exactly 1.0 and
authored font sizes equal printed sizes.
"""
from __future__ import annotations

import warnings

import pytest

from sciviz import Box, Card, Diagram, Palette, Row, card_header


TARGET = 252.0


def _wrappy_card(title: str) -> Card:
    role = Palette.blue
    return Card(
        card_header(title),
        Box("first long descriptive label", wrap=True, text_size="tiny",
            fill=role.soft(), stroke=role),
        Box("second long descriptive label", wrap=True, text_size="tiny",
            fill=role.soft(), stroke=role),
        role=role,
    )


def _wide_body() -> Row:
    return Row(_wrappy_card("Alpha"), _wrappy_card("Beta"),
               _wrappy_card("Gamma"), gap="md", equal_widths=True)


def test_width_fit_lands_exactly_on_target():
    d = Diagram.for_paper(_wide_body(), target_width_pt=TARGET)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d.render()
    assert d._last_render_size.w == TARGET


def test_aspect_fit_lands_exactly_on_target():
    """The aspect-probing path (``target_aspect``) must also pin the
    canvas to the exact target, not the fixed-point's +epsilon."""
    d = Diagram.for_paper(_wide_body(), target_width_pt=TARGET,
                          target_aspect=(0.2, 1.5))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d.render()
    assert d._last_render_size.w == TARGET


def test_far_overshoot_still_warns_and_keeps_size():
    body = Row(Box("an uncompressible single very long unbroken label"),
               Box("another equally long unbroken label text"))
    d = Diagram.for_paper(body, target_width_pt=60.0)
    with pytest.warns(UserWarning, match="does not\nshrink fonts|shrink fonts"):
        d.render()
    assert d._last_render_size.w > 60.0
