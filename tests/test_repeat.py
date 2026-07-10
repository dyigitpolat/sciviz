"""Sequential repetition must remain distinct from overlapping stacks."""

from __future__ import annotations

import pytest

from sciviz import Box, Canvas, Repeat, Theme


def _render(element) -> str:
    theme = Theme()
    canvas = Canvas()
    size = element.measure(theme)
    element.render(canvas, 0, 0, theme)
    return canvas.to_svg(size.w, size.h)


def test_vertical_repeat_renders_every_occurrence_and_connectors():
    repeated = Repeat(
        Box("block"), count=3, axis="vertical", direction="up"
    )
    svg = _render(repeated)
    assert svg.count(">block<") == 3
    assert svg.count("marker-end") >= 2


def test_repeat_absorbs_height_by_spacing_the_chain():
    theme = Theme()
    repeated = Repeat(
        Box("block"), count=3, axis="vertical", direction="up"
    )
    natural = repeated.measure(theme)
    repeated.inflate_to(0, natural.h + 80)
    assert repeated.measure(theme).h == pytest.approx(natural.h + 80)


def test_repeat_validates_axis_direction_pair():
    with pytest.raises(ValueError):
        Repeat(Box("x"), count=2, axis="horizontal", direction="up")
