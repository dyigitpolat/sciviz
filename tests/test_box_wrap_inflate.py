"""Wrapped Box labels re-flow to the width the box was actually given.

``Box(wrap=True)`` wraps its label at a theme-derived intrinsic budget.
When a sibling-equalising container (``Row(equal_widths=True)``,
``AlignedStack(stretch=True)``, ``EqualGrid``) inflates the box to a
wider slot, the label must re-wrap to fill that slot: otherwise the
extra width is dead margin around a tall, narrow text column, and rows
keep the height of the narrow wrap.  ``Row`` therefore equalises widths
*before* shape-peer normalisation locks in shared min-heights.
"""
from __future__ import annotations

from sciviz import Box, Row, Theme


LONG = ("contrastive parent pair selection with measured speedups "
        "presented side by side")


def test_inflated_box_rewraps_to_fewer_lines():
    theme = Theme()
    box = Box(LONG, wrap=True)
    intrinsic = box.measure(theme)
    lines_before = len(box._label_lines(theme))
    box.inflate_to(intrinsic.w * 2, 0.0)
    inflated = box.measure(theme)
    lines_after = len(box._label_lines(theme))
    assert inflated.w == intrinsic.w * 2
    assert lines_after < lines_before
    assert inflated.h < intrinsic.h


def test_explicit_max_width_still_wins():
    theme = Theme()
    box = Box(LONG, wrap=True, max_width=60)
    lines_before = len(box._label_lines(theme))
    box.inflate_to(600, 0.0)
    assert len(box._label_lines(theme)) == lines_before


def test_equal_width_row_peers_share_short_height():
    """Two same-shape wrapped cells in an equal-width Row end at the
    same height, and that height reflects the re-wrapped (wide) text,
    not the intrinsic narrow wrap."""
    theme = Theme()
    tall_alone = Box(LONG, wrap=True, shape_key="cell")
    h_narrow = tall_alone.measure(theme).h

    wide = Box("a label that is significantly wider than its siblings "
               "so it sets the shared slot width for the whole row",
               wrap=True, shape_key="cell")
    tall = Box(LONG, wrap=True, shape_key="cell")
    row = Row(wide, tall, equal_widths=True)
    row.measure(theme)
    assert tall.measure(theme).w == wide.measure(theme).w
    assert tall.measure(theme).h == wide.measure(theme).h
    assert tall.measure(theme).h <= h_narrow
