"""Lanes a container surfaces align content but never size a row.

A column whose first card carries a wire above it reports that corridor
as a top lane and leaves it out of its content box, so a top-aligned row
lines the content up past it. That alignment may spend the room a
sibling leaves free; it must not make the row taller (or shorter) than
the row its children's boxes already need."""
import pytest

from sciviz import DEFAULT_THEME, Anchor, Box, Column, Connect, Diagram, Row
from sciviz.connect._resolver import _FlowResolver


def _row(align):
    left = Column(Anchor("a", Box("a")), Box("a2"), gap="sm")
    right = Column(Box("b1"), Anchor("b", Box("b")), gap="sm")
    row = Row(left, right, Box("tall\nbox\nhere\n!"), gap="md", align=align)
    body = Column(Anchor("top", Box("top")), row,
                  Anchor("bottom", Box("bottom")),
                  Connect("a", "top", src_side="top", dst_side="bottom"),
                  Connect("b", "bottom", src_side="bottom", dst_side="top"),
                  gap="md")
    _FlowResolver(body)._apply_flow_margins(DEFAULT_THEME)
    return row, left, right


@pytest.mark.parametrize("align", ["start", "center", "end", "stretch"])
def test_row_height_is_what_the_boxes_need(align):
    row, left, right = _row(align)
    T = DEFAULT_THEME
    assert left.flow_lanes(T)[0] > 0 and right.flow_lanes(T)[1] > 0
    h = row.measure(T).h
    tallest = max(c.measure(T).h for c in row.children)
    assert h == pytest.approx(tallest)


@pytest.mark.parametrize("align", ["start", "center", "end", "stretch"])
def test_children_stay_inside_the_row(align):
    row, _left, _right = _row(align)
    T = DEFAULT_THEME
    H = row.measure(T).h
    d = Diagram.for_paper(Column(row))
    d.render(embed_fonts=False)
    for _ox, oy, size in row._child_offsets(T):
        if align in ("start", "stretch"):
            continue            # legacy frame: content tops at 0
        assert -1e-6 <= oy and oy + size.h <= H + 1e-6
