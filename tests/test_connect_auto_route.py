"""Auto-routing is the default for every Connect mode.

A plain ``Connect("a", "b")`` must route through the topological planner
(i.e. behave like ``style="orthogonal"``).  ``auto_route=False`` is the
opt-out hatch and falls back to a straight segment.  An explicit
``style=`` always wins over ``auto_route``.
"""
from __future__ import annotations

from sciviz import Diagram, Row, Column, Box, Anchor
from sciviz.connect import Connect


def _render(body) -> str:
    return Diagram(body=body).render()


def test_routed_default_is_auto_routed():
    explicit = Connect("a", "b", src_side="right", dst_side="left",
                       style="orthogonal")
    default = Connect("a", "b", src_side="right", dst_side="left")
    assert default._impl._flow.style == explicit._impl._flow.style == "orthogonal"


def test_routed_opt_out_falls_back_to_straight():
    c = Connect("a", "b", src_side="right", dst_side="left", auto_route=False)
    assert c._impl._flow.style == "straight"


def test_explicit_style_beats_auto_route_flag():
    # style= wins, even when auto_route says otherwise.
    c = Connect("a", "b", src_side="right", dst_side="left",
                auto_route=False, style="curve")
    assert c._impl._flow.style == "curve"


def test_bus_accepts_auto_route_flag():
    # Bus geometry is always auto-routed; the flag is accepted for
    # API symmetry without raising.
    c = Connect("a", ["b1", "b2"], auto_route=True)
    assert c.mode == "bus"
    assert c._impl._bus.auto_route is True


def test_inline_accepts_auto_route_flag():
    # Inline arrows are axis-aligned by construction; accepting the
    # flag keeps the API uniform across modes.
    body = Row(Box("A"), Connect(direction="right", auto_route=True), Box("B"))
    _render(body)  # must not raise


def test_routed_auto_route_on_matches_orthogonal_default():
    on = _render(Column(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        Connect("a", "b", src_side="right", dst_side="left", auto_route=True),
    ))
    default = _render(Column(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        Connect("a", "b", src_side="right", dst_side="left"),
    ))
    assert on == default
