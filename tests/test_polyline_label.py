"""Connector-label placement along multi-segment polylines.

``place_polyline_label`` generalises the single-segment placer: it
offsets the label from whichever wire leg admits a collision-free slot
and treats the wire's other legs as obstacles.  Orientation follows the
wire, but a vertical leg only prefers the 90-degree rotated label when
it is long enough to genuinely carry the text; short vertical hops
prefer a horizontal label beside the wire (so sibling edges in one
stacked spine share one reading direction), with the other orientation
kept as a collision fallback in both cases.
"""
from __future__ import annotations

from sciviz.auto.labels import (
    LabelBox, place_polyline_label, segment_rects,
)


LBL = LabelBox(text="label", width=40.0, height=10.0, size_px=9.0)


def _overlaps(rect, obstacles):
    x0, y0, x1, y1 = rect
    total = 0.0
    for bx0, by0, bx1, by1 in obstacles:
        total += (max(0.0, min(x1, bx1) - max(x0, bx0))
                  * max(0.0, min(y1, by1) - max(y0, by0)))
    return total


def test_label_moves_to_another_leg_when_longest_is_hemmed_in():
    # L-shaped wire: long vertical leg hemmed in by full-height walls
    # on both sides; the horizontal leg escapes them into open space.
    path = [(0.0, 0.0), (0.0, 200.0), (120.0, 200.0)]
    obstacles = [
        (-60.0, -60.0, -4.0, 260.0),   # wall left of the vertical leg
        (4.0, -60.0, 56.0, 196.0),     # wall right of the vertical leg
        (4.0, 204.0, 56.0, 260.0),     # below-corner block (under the wall)
    ]
    placed = place_polyline_label(path, LBL, obstacles, gap=3.0)
    assert _overlaps(placed.rect, obstacles) == 0.0, placed
    assert placed.rotation == 0.0  # horizontal leg won
    assert placed.rect[0] > 4.0    # escaped the corridor


def test_short_vertical_leg_falls_back_to_horizontal_label():
    # A single short vertical hop between two stacked cards: the
    # rotated label cannot fit between them, a horizontal label beside
    # the wire can.
    path = [(50.0, 30.0), (50.0, 46.0)]
    cards = [
        (0.0, 0.0, 100.0, 30.0),     # card above
        (0.0, 46.0, 100.0, 90.0),    # card below
    ]
    placed = place_polyline_label(path, LBL, cards, gap=2.0)
    assert placed.rotation == 0.0, placed
    assert _overlaps(placed.rect, cards) == 0.0, placed


def test_long_vertical_leg_keeps_rotated_label():
    path = [(50.0, 0.0), (50.0, 200.0)]
    placed = place_polyline_label(path, LBL, [], gap=3.0)
    assert placed.rotation == 90.0


def test_short_vertical_hop_prefers_horizontal_even_in_open_space():
    # Regression: a short vertical hop whose label is small enough that
    # the ROTATED placement is collision-free. The old rotate-first
    # preference let that one edge read top-to-bottom while sibling
    # edges in the same stack (with longer labels) read left-to-right.
    # A leg shorter than the label's rotated extent must prefer the
    # horizontal orientation even when the rotated one would fit.
    path = [(50.0, 30.0), (50.0, 55.0)]  # 25px hop < 40px label width
    placed = place_polyline_label(path, LBL, [], gap=3.0)
    assert placed.rotation == 0.0, placed


def test_short_vertical_hop_falls_back_to_rotated_when_horizontal_blocked():
    # When walls hem in both sides of a short hop so tightly that no
    # horizontal slot exists (corridor narrower than the label width but
    # wide enough for the rotated label), the rotated orientation must
    # remain available as a fallback.
    path = [(50.0, 30.0), (50.0, 55.0)]
    walls = [
        (-200.0, -200.0, 36.0, 300.0),   # wall left of the wire
        (64.0, -200.0, 300.0, 300.0),    # wall right of the wire
    ]
    placed = place_polyline_label(path, LBL, walls, gap=3.0)
    assert placed.rotation == 90.0, placed
    assert _overlaps(placed.rect, walls) == 0.0, placed


def test_readable_horizontal_leg_beats_longer_vertical_leg():
    # Research-figure connector labels should remain horizontal when a real
    # caption lane exists, even if a vertical detour happens to be longer.
    path = [(0.0, 0.0), (0.0, 180.0), (100.0, 180.0)]
    placed = place_polyline_label(path, LBL, [], gap=3.0)
    assert placed.rotation == 0.0
    assert placed.rect[1] > 130.0


def test_label_avoids_other_wires():
    # Open space, but another wire runs parallel exactly where the
    # default offset would land the label.
    path = [(0.0, 50.0), (200.0, 50.0)]
    other_wire = segment_rects([(0.0, 38.0), (200.0, 38.0)], pad=1.0)
    placed = place_polyline_label(path, LBL, other_wire, gap=3.0)
    assert _overlaps(placed.rect, other_wire) == 0.0, placed


def test_own_perpendicular_legs_are_obstacles():
    # U-shaped wire; the label on the long bottom leg must not sit on
    # the two vertical legs.
    path = [(0.0, 0.0), (0.0, 60.0), (120.0, 60.0), (120.0, 0.0)]
    placed = place_polyline_label(path, LBL, [], gap=3.0)
    legs = segment_rects([(0.0, 0.0), (0.0, 60.0)], pad=1.0) + \
        segment_rects([(120.0, 60.0), (120.0, 0.0)], pad=1.0)
    assert _overlaps(placed.rect, legs) == 0.0, placed


def test_segment_rects_skips_degenerate_segments():
    rects = segment_rects([(0.0, 0.0), (0.0, 0.0), (10.0, 0.0)], pad=2.0)
    assert rects == [(-2.0, -2.0, 12.0, 2.0)]
