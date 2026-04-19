"""Tests for :class:`sciviz.AlignedStack`.

AlignedStack's raison d'être is cross-parent column alignment: two
sibling :class:`Table` / :class:`Row` / :class:`Grid` containers stacked
vertically, whose columns should share widths even though each container
would naturally pick its own.

The contract is tested on every currently-wired child type.
"""

from __future__ import annotations

from sciviz import (
    AlignedStack,
    Box,
    Canvas,
    Column,
    DEFAULT_THEME,
    Row,
    Table,
    Text,
)
from sciviz.layout._simple_grid import Grid as SimpleGrid


def test_aligned_stack_measures_like_column_for_plain_children():
    plain = Column(Box("A"), Box("BB"), gap="xs")
    stack = AlignedStack(Box("A"), Box("BB"), gap="xs")
    assert abs(plain.measure(DEFAULT_THEME).h - stack.measure(DEFAULT_THEME).h) < 0.01


def test_stacked_tables_share_column_widths():
    a = Table([
        [Text("short"), Text("123")],
        [Text("mid"), Text("456")],
    ], gap_x="sm")
    b = Table([
        [Text("a much longer first-column label"), Text("78")],
        [Text("ditto"), Text("9")],
    ], gap_x="sm")
    stack = AlignedStack(a, b, gap="md")
    stack.measure(DEFAULT_THEME)  # triggers the two-pass propagation

    widths_a = a._shared_column_widths(DEFAULT_THEME)
    widths_b = b._shared_column_widths(DEFAULT_THEME)
    # After propagation, both tables report the same col_w through _extents.
    _, col_w_a, _ = a._extents(DEFAULT_THEME)
    _, col_w_b, _ = b._extents(DEFAULT_THEME)
    assert col_w_a == col_w_b
    # Each shared width is at least the max of the two tables' intrinsic widths.
    for i in range(2):
        assert col_w_a[i] >= max(widths_a[i], widths_b[i])


def test_aligned_stack_preserves_table_output_row_widths():
    """After alignment each Table renders at the *same* width so the stack
    reports a rectangular outer bbox."""
    a = Table([[Text("x"), Text("1")]])
    b = Table([[Text("yyyyyyyyyyyyyy"), Text("2")]])
    stack = AlignedStack(a, b)
    w_a = a.measure(DEFAULT_THEME).w
    w_b = b.measure(DEFAULT_THEME).w
    stack.measure(DEFAULT_THEME)
    # After propagation both tables adopt the max col widths.
    w_a2 = a.measure(DEFAULT_THEME).w
    w_b2 = b.measure(DEFAULT_THEME).w
    assert abs(w_a2 - w_b2) < 0.01
    # And neither row got narrower than it was before.
    assert w_a2 >= w_a - 0.01
    assert w_b2 >= w_b - 0.01


def test_stacked_rows_share_column_widths():
    a = Row(Box("A", width=40), Box("BB"), gap="sm")
    b = Row(Box("C", width=80), Box("DD"), gap="sm")
    stack = AlignedStack(a, b)
    stack.measure(DEFAULT_THEME)
    # Row._forced_slot_w must be populated on both and the first slot
    # width must match between them.
    assert a._forced_slot_w is not None
    assert b._forced_slot_w is not None
    assert a._forced_slot_w[0] == b._forced_slot_w[0]
    assert a._forced_slot_w[0] >= 80.0  # widest of the two


def test_stacked_grids_share_column_widths():
    g1 = SimpleGrid(Box("a", width=30), Box("b", width=30), cols=2)
    g2 = SimpleGrid(Box("c", width=70), Box("d", width=30), cols=2)
    stack = AlignedStack(g1, g2)
    stack.measure(DEFAULT_THEME)
    _, c1, _ = g1._col_row_extents(DEFAULT_THEME)
    _, c2, _ = g2._col_row_extents(DEFAULT_THEME)
    assert c1 == c2
    assert c1[0] >= 70.0


def test_aligned_stack_independent_mode_skips_propagation():
    a = Table([[Text("a"), Text("1")]])
    b = Table([[Text("very very long label"), Text("2")]])
    stack = AlignedStack(a, b, column_widths="independent")
    stack.measure(DEFAULT_THEME)
    _, cw_a, _ = a._extents(DEFAULT_THEME)
    _, cw_b, _ = b._extents(DEFAULT_THEME)
    assert cw_a != cw_b


def test_aligned_stack_horizontal_axis():
    stack = AlignedStack(Box("A", height=40), Box("B", height=60),
                         axis="horizontal", gap="sm")
    bbox = stack.measure(DEFAULT_THEME)
    # Horizontal axis: widths sum, height is max.
    assert bbox.h >= 60
    assert bbox.w >= 2  # at least two boxes' widths


def test_aligned_stack_renders():
    a = Table([[Text("a"), Text("1")]])
    b = Table([[Text("long"), Text("22")]])
    stack = AlignedStack(a, b)
    c = Canvas()
    stack.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    assert ">a<" in svg
    assert ">long<" in svg


def test_aligned_stack_rejects_bad_axis():
    import pytest
    with pytest.raises(ValueError):
        AlignedStack(axis="zzz")


def test_aligned_stack_rejects_bad_column_widths():
    import pytest
    with pytest.raises(ValueError):
        AlignedStack(column_widths="magic")
