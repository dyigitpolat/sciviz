"""Parity tests for the unified Connect API.

Each test builds two diagrams that should render identically:
  - left:  the new Connect(...) form
  - right: the equivalent pre-existing form (Arrow / Flow / Labeled / Bus)

The SVG strings are compared byte-for-byte. These tests lock in the
promise that Connect is a true replacement for the legacy primitives.
"""
from __future__ import annotations

from sciviz import (Diagram, Row, Column, Box, Text, Anchor)
from sciviz.composition import Flow, Flowed, Labeled, Bus
from sciviz.elements import Arrow
from sciviz.connect import Connect


def _render(body) -> str:
    return Diagram(body=body).render()


# -------------------------------------------------------------------- inline

def test_connect_inline_matches_arrow():
    new = _render(Row(Box("A"), Connect(label="x", direction="right"), Box("B")))
    old = _render(Row(Box("A"), Arrow(label="x", direction="right"), Box("B")))
    assert new == old


def test_connect_inline_directions():
    for direction in ("right", "left", "up", "down"):
        new = _render(Row(Box("A"), Connect(direction=direction), Box("B")))
        old = _render(Row(Box("A"), Arrow(direction=direction), Box("B")))
        assert new == old, f"inline direction {direction!r} mismatch"


def test_connect_inline_no_head():
    new = _render(Row(Box("A"), Connect(direction="right", head=False), Box("B")))
    old = _render(Row(Box("A"), Arrow(direction="right", head=False), Box("B")))
    assert new == old


def test_connect_inline_label_list():
    new = _render(Row(Box("A"), Connect(label=["top", "bot"], direction="right"), Box("B")))
    old = _render(Row(Box("A"), Arrow(label=["top", "bot"], direction="right"), Box("B")))
    assert new == old


# -------------------------------------------------------------------- routed

def _routed_body_new():
    return Column(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        Connect("a", "b", src_side="right", dst_side="left"),
    )


def _routed_body_old():
    return Flowed(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        flows=[Flow("a", "b", src_side="right", dst_side="left")],
    )


def test_connect_routed_matches_flowed():
    assert _render(_routed_body_new()) == _render(_routed_body_old())


def test_connect_routed_dashed():
    new = _render(Column(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        Connect("a", "b", src_side="right", dst_side="left", dashed=True),
    ))
    old = _render(Flowed(
        Row(Anchor("a", Box("A")), Anchor("b", Box("B")), gap="lg"),
        flows=[Flow("a", "b", src_side="right", dst_side="left", dashed=True)],
    ))
    assert new == old


# ---------------------------------------------------------------------- bus

def test_connect_bus_matches_bus():
    new = _render(Column(
        Row(Anchor("a", Box("A"))),
        Row(
            Anchor("b1", Box("B1")),
            Anchor("b2", Box("B2")),
            Anchor("b3", Box("B3")),
            gap="lg",
        ),
        Connect("a", ["b1", "b2", "b3"], label="shared"),
    ))
    old = _render(Flowed(
        Column(
            Row(Anchor("a", Box("A"))),
            Row(
                Anchor("b1", Box("B1")),
                Anchor("b2", Box("B2")),
                Anchor("b3", Box("B3")),
                gap="lg",
            ),
        ),
        flows=[Bus("a", ["b1", "b2", "b3"], label="shared")],
    ))
    assert new == old


# ---------------------------------------------------------------- labeled()

def test_connect_labeled_matches_labeled_class():
    a = Box("src")
    b = Text("lbl")
    new = _render(Connect.labeled(a, b))
    old = _render(Labeled(a, b))
    assert new == old


# ---------------------------------------------------------- classification

def test_connect_classify_inline():
    """Connect(direction='right') without src/dst classifies as inline."""
    c = Connect(direction="right")
    assert c.mode == "inline"


def test_connect_classify_routed():
    c = Connect("a", "b")
    assert c.mode == "routed"


def test_connect_classify_bus_list_of_dsts():
    c = Connect("a", ["b1", "b2"])
    assert c.mode == "bus"


def test_connect_classify_bus_list_of_srcs():
    c = Connect(["a1", "a2"], "b")
    assert c.mode == "bus"


# ------------------------------------------------- invisible layout marker

def test_connect_routed_is_layout_invisible_in_column():
    """A routed Connect placeholder inside a Column should not consume
    a gap slot: the column's measured height must equal the sum of its
    visible rows' heights plus (n_visible - 1) gaps."""
    with_connect = Column(
        Row(Anchor("a", Box("A"))),
        Row(Anchor("b", Box("B"))),
        Connect("a", "b", src_side="bottom", dst_side="top"),
    )
    without_connect = Column(
        Row(Anchor("a", Box("A"))),
        Row(Anchor("b", Box("B"))),
    )
    from sciviz.core import DEFAULT_THEME
    assert with_connect.measure(DEFAULT_THEME).h == \
        without_connect.measure(DEFAULT_THEME).h
