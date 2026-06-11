"""Connector-label placement along multi-segment polylines.

``place_polyline_label`` generalises the single-segment placer: it
offsets the label from whichever wire leg admits a collision-free slot,
treats the wire's other legs as obstacles, and falls back to a
horizontal label beside a short vertical leg when the rotated label
cannot avoid the surrounding cards.
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
