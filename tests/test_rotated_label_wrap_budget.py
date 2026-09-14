"""The rotated-label wrap budget.

Turning a caption along a wire changes which dimension it is read
across: the arm becomes the whole of its reading width. Two consequences,
locked here.

1. An arm long enough to carry the words gets them back on ONE line,
   even when an earlier, narrower budget folded them. A caption folded
   for a corridor it no longer occupies is a stale layout decision, and
   the placer is the last party that knows which arm the caption ended
   up on.
2. An arm that cannot carry them on one line forfeits rotation. A
   rotated block sets as parallel columns of tilted text, which is not
   reading matter in any orientation, so the caption stays upright
   beside the wire instead.

Authored hard breaks are content, not layout: a caption the author broke
with ``"\\n"`` is never reflowed, and therefore never rotated as a block.
"""
from __future__ import annotations

from sciviz.auto.labels import (
    measure_label, narrowest_wrap, place_polyline_label, place_segment_label,
    rotated_caption,
)
from sciviz.core import Theme


CAPTION = "C5: joint search (Chapter 8)"

# A corridor walled on both sides of a vertical wire, inside a region
# boundary: the geometry that used to turn a folded caption into columns
# of tilted text.
WALLS = [(0.0, 0.0, 85.0, 400.0), (140.0, 0.0, 300.0, 400.0)]
BOUNDS = (0.0, 0.0, 300.0, 400.0)


def _folded(theme):
    """The caption as a narrow corridor would have folded it."""
    return measure_label(narrowest_wrap(CAPTION, theme, "small"),
                         theme, "small", source=CAPTION)


def test_long_arm_restores_a_folded_caption_to_one_line():
    theme = Theme()
    label = _folded(theme)
    assert len(label.lines) > 1, "probe assumes a folded caption"

    placed = place_polyline_label([(100.0, 0.0), (100.0, 400.0)], label,
                                  obstacles=WALLS, gap=6.0, bounds=BOUNDS)

    assert placed.rotation == 90.0
    assert placed.text == CAPTION, placed.text


def test_short_arm_refuses_rotation_rather_than_tilting_a_block():
    theme = Theme()
    label = _folded(theme)

    placed = place_polyline_label([(100.0, 0.0), (100.0, 60.0)], label,
                                  obstacles=WALLS, gap=6.0, bounds=BOUNDS)

    assert placed.rotation == 0.0
    assert rotated_caption(label, 60.0, 6.0) is None


def test_authored_line_breaks_are_never_reflowed_or_tilted():
    theme = Theme()
    authored = measure_label("C5: joint search\n(Chapter 8)", theme, "small")

    assert authored.set_to(400.0) is authored
    assert rotated_caption(authored, 400.0, 6.0) is None

    placed = place_polyline_label([(100.0, 0.0), (100.0, 400.0)], authored,
                                  obstacles=WALLS, gap=6.0, bounds=BOUNDS)
    assert placed.rotation == 0.0


def test_straight_segment_placer_obeys_the_same_budget():
    theme = Theme()
    label = _folded(theme)

    long_arm = place_segment_label(((100.0, 0.0), (100.0, 400.0)), label,
                                   obstacles=[], gap=6.0)
    assert long_arm.rotation == 90.0
    assert long_arm.text == CAPTION

    short_arm = place_segment_label(((100.0, 0.0), (100.0, 60.0)), label,
                                    obstacles=[], gap=6.0)
    assert short_arm.rotation == 0.0


def test_horizontal_arm_keeps_the_caption_it_was_handed():
    # Rotation on a horizontal arm reads ACROSS the wire, where the arm
    # bounds nothing, so there is no arm budget to re-set against.
    theme = Theme()
    label = measure_label(CAPTION, theme, "small")

    placed = place_polyline_label([(0.0, 100.0), (400.0, 100.0)], label,
                                  obstacles=[], gap=6.0)

    assert placed.rotation == 0.0
    assert placed.text == CAPTION
