"""The label placer chooses a collision-free placement for a label given
candidate positions (above/below/left/right of a segment) and a list of
rectangle obstacles.
"""
from __future__ import annotations


def test_place_label_prefers_unobstructed_side():
    from sciviz._labelplacer import place_label

    # Horizontal segment from (0, 10) to (100, 10), label 20x8 px.
    # Obstacle above the segment (0-100, 0-8).  Below is clear.
    obstacles = [(0.0, 0.0, 100.0, 8.0)]
    rect, anchor = place_label(
        segment=((0.0, 10.0), (100.0, 10.0)),
        label_w=20.0, label_h=8.0,
        obstacles=obstacles,
        prefer="below",
    )
    # rect = (x0, y0, x1, y1); y0 should be >= segment y (below)
    assert rect[1] >= 10.0 - 0.5, rect


def test_place_label_falls_back_to_other_side_if_preferred_is_blocked():
    from sciviz._labelplacer import place_label

    # Horizontal segment at y=10.  Obstacle BELOW (10..12) blocks preferred.
    obstacles = [(0.0, 10.5, 100.0, 40.0)]
    rect, anchor = place_label(
        segment=((0.0, 10.0), (100.0, 10.0)),
        label_w=20.0, label_h=8.0,
        obstacles=obstacles,
        prefer="below",
    )
    # rect should end up above the segment (y1 <= 10)
    assert rect[3] <= 10.0 + 0.5, rect


def test_place_label_avoids_all_obstacles_when_possible():
    from sciviz._labelplacer import place_label, rects_overlap

    obstacles = [
        (30.0, 5.0, 60.0, 15.0),   # box crossing the segment in the middle
    ]
    rect, anchor = place_label(
        segment=((0.0, 10.0), (100.0, 10.0)),
        label_w=20.0, label_h=8.0,
        obstacles=obstacles,
        prefer="above",
    )
    for ob in obstacles:
        assert not rects_overlap(rect, ob), (rect, ob)
