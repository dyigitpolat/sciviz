"""``Connect(..., src_room=, dst_room=)`` sets the room reserved at a wire's end.

The layout reserves room beside each pinned end of a wire for its shaft
(a caption-sized corridor when the wire is labelled). An end whose shaft
already has visible room elsewhere (an arrow that enters a card inside a
region from outside the region) can set its own room; ``None``, the
default, keeps the automatic reservation.
"""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, DEFAULT_THEME
from sciviz.composition._flow import Flow
from sciviz.composition._flowed import Flowed


def _pair(**kw):
    a = Anchor("a", Box(width=40, height=20))
    b = Anchor("b", Box(width=40, height=20))
    flowed = Flowed(Column(a, b, gap=10.0),
                    [Flow("a", "b", src_side="bottom", dst_side="bottom",
                          label="Loop", **kw)])
    flowed._apply_flow_margins(DEFAULT_THEME)
    return a, b


def test_default_keeps_the_automatic_reservation():
    a, b = _pair()
    assert a.margin_bottom > 0.0
    assert b.margin_bottom > 0.0
    a2, b2 = _pair(src_room=None, dst_room=None)
    assert (a2.margin_bottom, b2.margin_bottom) == (a.margin_bottom, b.margin_bottom)


def test_dst_room_zero_reserves_nothing_at_the_destination():
    a0, _ = _pair()
    a, b = _pair(dst_room=0.0)
    assert b.margin_bottom == 0.0
    assert a.margin_bottom == pytest.approx(a0.margin_bottom)   # the other end is untouched


def test_src_room_sets_the_source_reservation():
    a, b = _pair(src_room=3.0)
    assert a.margin_bottom == pytest.approx(3.0)
    assert b.margin_bottom > 0.0


def test_negative_room_is_refused():
    with pytest.raises(ValueError):
        Flow("a", "b", dst_room=-1.0)


def test_connect_passes_the_rooms_to_its_flow():
    c = Connect("a", "b", src_side="bottom", dst_side="bottom", src_room=2.0, dst_room=0.0)
    assert c._impl._flow.src_room == 2.0
    assert c._impl._flow.dst_room == 0.0
    d = Connect("a", "b", src_side="bottom", dst_side="bottom")
    assert d._impl._flow.src_room is None and d._impl._flow.dst_room is None


def _tree(**kw):
    from sciviz.connect._resolver import _FlowResolver
    a = Anchor("a", Box(width=40, height=20))
    b = Anchor("b", Box(width=40, height=20))
    tree = Column(a, b, Connect("a", "b", src_side="bottom", dst_side="bottom",
                                label="Loop", **kw), gap=10.0)
    _FlowResolver(tree)._apply_flow_margins(DEFAULT_THEME)
    return a, b


def test_a_connect_in_the_tree_reserves_the_set_room():
    a0, b0 = _tree()
    assert a0.margin_bottom > 0.0 and b0.margin_bottom > 0.0
    a, b = _tree(dst_room=0.0)
    assert b.margin_bottom == 0.0
    assert a.margin_bottom == pytest.approx(a0.margin_bottom)
    a, b = _tree(src_room=3.0)
    assert a.margin_bottom == pytest.approx(3.0)
    assert b.margin_bottom == pytest.approx(b0.margin_bottom)
