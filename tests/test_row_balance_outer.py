"""Bilateral Row geometry keeps a semantic middle on the true centreline."""

import pytest

from sciviz import Box, Row, Theme


def _box(label: str, width: float) -> Box:
    return Box(label, width=width, height=30, shape_key="")


def test_balance_outer_centres_middle_and_packs_sides_inward():
    theme = Theme()
    row = Row(
        _box("left", 60),
        _box("centre", 20),
        _box("right", 100),
        gap=10,
        balance_outer=True,
    )

    offsets = row._child_offsets(theme)
    size = row.measure(theme)

    assert size.w == pytest.approx(240)
    assert offsets[0][0] == pytest.approx(40)
    assert offsets[1][0] == pytest.approx(110)
    assert offsets[2][0] == pytest.approx(140)
    middle = offsets[1][0] + offsets[1][2].w / 2
    assert middle == pytest.approx(size.w / 2)
    assert offsets[0][0] + offsets[0][2].w + 10 == pytest.approx(offsets[1][0])
    assert offsets[1][0] + offsets[1][2].w + 10 == pytest.approx(offsets[2][0])


def test_balance_outer_distributes_an_inflated_width_symmetrically():
    theme = Theme()
    row = Row(
        _box("left", 60),
        _box("centre", 20),
        _box("right", 100),
        gap=10,
        balance_outer=True,
    )
    row.inflate_to(300, 0)

    offsets = row._child_offsets(theme)
    size = row.measure(theme)

    assert size.w == pytest.approx(300)
    assert offsets[1][0] + offsets[1][2].w / 2 == pytest.approx(150)


def test_balance_outer_requires_three_visible_children():
    row = Row(_box("left", 40), _box("right", 40), balance_outer=True)

    with pytest.raises(ValueError, match="exactly three visible children"):
        row.measure(Theme())


def test_balance_outer_is_distinct_from_equal_widths():
    with pytest.raises(ValueError, match="alternative Row slot contracts"):
        Row(
            _box("left", 40),
            _box("centre", 40),
            _box("right", 40),
            balance_outer=True,
            equal_widths=True,
        )
