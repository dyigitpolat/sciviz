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


def test_diagonal_label_rectangle_clears_its_own_segment():
    from sciviz._labelplacer import place_label

    p1, p2 = (100.0, 100.0), (20.0, 40.0)
    gap = 4.0
    rect, _anchor = place_label(
        segment=(p1, p2),
        label_w=90.0,
        label_h=12.0,
        prefer="above",
        gap=gap,
    )

    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = (dx * dx + dy * dy) ** 0.5
    nx, ny = dy / length, -dx / length
    corners = (
        (rect[0], rect[1]), (rect[2], rect[1]),
        (rect[0], rect[3]), (rect[2], rect[3]),
    )
    signed = [nx * (x - p1[0]) + ny * (y - p1[1]) for x, y in corners]
    assert all(value >= gap - 1e-6 for value in signed) \
        or all(value <= -gap + 1e-6 for value in signed)
