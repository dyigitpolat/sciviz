"""Cycle: an ordered loop of stages placed around a rectangular ring.

The container owns the two things an author would otherwise hand-tune
per shape -- where each stage sits and which side each hand-off attaches
to -- so re-shaping the ring (by hand or through an ``Aspect``
annotation) never asks the author to restate a side hint.
"""
from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Cycle, DEFAULT_THEME, Diagram
from sciviz.connect import ring_positions, ring_shapes
from sciviz.core import Canvas


def _stages(n: int = 6):
    return [Anchor(f"s{i}", Box(f"stage {i}", width=60, height=36))
            for i in range(n)]


# --------------------------------------------------------------------
# ring geometry
# --------------------------------------------------------------------

def test_ring_walk_is_adjacent_and_closes():
    for shape in ((2, 3), (3, 2), (2, 4), (3, 3), (4, 2)):
        walk = ring_positions(shape)
        assert len(set(walk)) == len(walk), f"{shape} repeats a cell"
        closed = walk + [walk[0]]
        for a, b in zip(closed, closed[1:]):
            step = abs(a[0] - b[0]) + abs(a[1] - b[1])
            assert step == 1, f"{shape}: {a} -> {b} is not a grid step"


def test_ring_shapes_only_admits_rectangles_that_fit():
    assert ring_shapes(6) == [(2, 3), (3, 2)]
    assert (2, 4) in ring_shapes(8) and (3, 3) in ring_shapes(8)
    # An odd count borrows at most one empty perimeter slot.
    assert ring_shapes(5) == [(2, 3), (3, 2)]
    assert all(2 * (r + c) - 4 <= 8 for r, c in ring_shapes(7))


def test_start_corner_and_direction():
    assert ring_positions((2, 3))[0] == (0, 0)
    assert ring_positions((2, 3), start="bottom-left")[0] == (1, 0)
    cw = ring_positions((2, 3))
    ccw = ring_positions((2, 3), direction="counterclockwise")
    assert cw[0] == ccw[0]
    assert cw[1] == (0, 1) and ccw[1] == (1, 0)


def test_invalid_shape_and_direction_are_errors():
    with pytest.raises(ValueError):
        ring_positions((2, 3), direction="widdershins")
    with pytest.raises(ValueError):
        ring_positions((2, 3), start="middle")
    with pytest.raises(ValueError):
        Cycle(*_stages(2), shape=(2, 2))._validate_shape((1, 1))


# --------------------------------------------------------------------
# placement and wiring
# --------------------------------------------------------------------

def test_serpentine_placement_matches_the_ring_walk():
    ring = Cycle(*_stages(6), shape=(2, 3))
    grid = ring._grid
    # Column 0 carries stages 1 and 6, column 2 carries stages 3 and 4.
    assert grid.columns[0]["r0"].name == "s0"
    assert grid.columns[0]["r1"].name == "s5"
    assert grid.columns[2]["r0"].name == "s2"
    assert grid.columns[2]["r1"].name == "s3"


def test_hand_off_sides_follow_the_placement():
    ring = Cycle(*_stages(6), shape=(2, 3))
    sides = [(c._impl._flow.src_side, c._impl._flow.dst_side)
             for c in ring._connects]
    assert sides[0] == ("right", "left")     # across the top row
    assert sides[2] == ("bottom", "top")     # down the right edge
    assert sides[3] == ("left", "right")     # back across the bottom
    assert sides[5] == ("top", "bottom")     # up the left edge


def test_reshaping_rewires_every_hand_off():
    """The whole point: the author never restates a side hint."""
    ring = Cycle(*_stages(6), shape="auto")
    ring._apply_reflow((3, 2))
    sides = [(c._impl._flow.src_side, c._impl._flow.dst_side)
             for c in ring._connects]
    assert sides[0] == ("right", "left")     # top row of a 3x2 is 2 wide
    assert sides[1] == ("bottom", "top")     # then straight down
    assert sides[3] == ("left", "right")
    assert ring.measure(DEFAULT_THEME).w < Cycle(
        *_stages(6), shape=(2, 3)).measure(DEFAULT_THEME).w


def test_edges_accept_labels_dicts_and_suppression():
    ring = Cycle(*_stages(6), shape=(2, 3),
                 edges=["propose", {"label": "commit", "dashed": True},
                        None, False, None, None])
    labels = [c._impl._flow.label for c in ring._connects]
    assert labels[0] == "propose"
    assert labels[1] == "commit"
    assert ring._connects[1]._impl._flow.dashed is True
    # The suppressed hand-off drew no connector at all.
    assert len(ring._connects) == 5
    with pytest.raises(TypeError):
        Cycle(*_stages(6), edges=[3.5])


def test_stage_names_are_addressable_for_extra_connectors():
    ring = Cycle(*_stages(6), shape=(2, 3))
    assert ring.stage_names == [f"s{i}" for i in range(6)]


def test_pinned_shape_opts_out_of_reflow():
    assert Cycle(*_stages(6), shape=(2, 3))._reflow_options() == []
    assert Cycle(*_stages(6), shape="auto")._reflow_options() == [(2, 3), (3, 2)]


def test_shape_too_small_for_the_stage_count_is_rejected():
    with pytest.raises(ValueError):
        Cycle(*_stages(8), shape=(2, 3))


def test_needs_at_least_two_stages():
    with pytest.raises(ValueError):
        Cycle(Box("only", width=20, height=20))


# --------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------

def test_every_stage_and_hand_off_reaches_the_canvas():
    ring = Cycle(*_stages(6), shape=(2, 3), edges=["one"] + [None] * 5)
    d = Diagram.for_paper(ring)
    svg = d.render()
    for i in range(6):
        assert f"stage {i}" in svg
    assert "one" in svg
    # Six hand-offs are actually stroked, not just declared.
    assert svg.count("<line") + svg.count("<path") >= 6


def test_slack_slot_keeps_the_loop_closed():
    """Five stages on a six-slot ring still close back to stage one."""
    ring = Cycle(*_stages(5), shape=(2, 3))
    assert len(ring._connects) == 5
    d = Diagram.for_paper(ring)
    assert "stage 4" in d.render()
