"""A region titled on its border line (``tab_style="legend"``) in a row and in a column.

A row aligns and equalises it on its WALLS: the half title above the top wall is neither content nor frame, it
rides in the room a taller neighbour leaves free and adds to the row's height only where nothing leaves it room.
A column lets it ride in the gap to the neighbour above. Every other region, and every row and column without
such a region, is laid out as before.
"""
import pytest

from sciviz import Anchor, Box, Column, DEFAULT_THEME, Region, Row
from sciviz.core import Canvas

T = DEFAULT_THEME


def _box(h, w=60.0):
    return Box(width=w, height=h, fill="#ffffff", stroke="none")


def _legend(h=40.0, **kw):
    kw.setdefault("margin_x", 0.0)
    kw.setdefault("margin_y", 0.0)
    return Region(_box(h, 160.0), label="Toolchain", label_style="tab", tab_style="legend", color="#808890",
                  dashed=False, **kw)


def _frame(h=40.0):
    """A frame without a title: its measured box is its walls. (Its box stands in a column, so the row does not
    take it for a shape peer of the legend region's box and equalise the two boxes themselves.)"""
    return Region(Column(_box(h)), color="#808890", dashed=False, margin_x=0.0, margin_y=0.0)


def _walls(row, index):
    """(top, bottom) of child ``index``'s walls in the row's frame."""
    (_ox, oy, size) = row._child_offsets(T)[index]
    child = row.children[index]
    frame = child.frame_bbox(T) if hasattr(child, "frame_bbox") else None
    if frame is None:
        return oy, oy + size.h
    return oy + frame[1], oy + frame[1] + frame[3]


def test_only_a_legend_titled_region_declares_a_frame():
    half = _legend().wall_offsets(T)[0]
    assert half > 0.0
    legend = _legend()
    box = legend.measure(T)
    assert legend.frame_bbox(T)[1] == pytest.approx(half)
    assert legend.frame_bbox(T)[3] == pytest.approx(box.h - half)
    assert legend.wall_overhang(T) == pytest.approx((half, 0.0))
    plate = Region(_box(40.0), label="Toolchain", label_style="tab", color="#808890", dashed=False)
    outside = Region(_box(40.0), label="Toolchain", color="#808890", dashed=False)
    for other in (plate, outside, _frame()):
        assert other.frame_bbox(T) is None
        assert other.wall_overhang(T) == (0.0, 0.0)


def test_a_row_equalises_and_aligns_a_legend_region_on_its_walls():
    legend, frame = _legend(40.0), _frame(70.0)
    row = Row(legend, frame, gap=10.0, align="center", equal_heights=True)
    h = row.measure(T).h
    half = legend.wall_offsets(T)[0]
    top_l, bottom_l = _walls(row, 0)
    top_f, bottom_f = _walls(row, 1)
    assert top_l == pytest.approx(top_f)                 # the top walls stand on one line
    assert bottom_l == pytest.approx(bottom_f)           # and the bottom walls
    assert bottom_l - top_l == pytest.approx(frame.measure(T).h)
    assert h == pytest.approx(frame.measure(T).h + half)  # the half title alone rides above the shared top
    assert top_l == pytest.approx(half)


def test_an_anchor_is_transparent_to_the_wall_alignment():
    legend, frame = _legend(40.0), _frame(70.0)
    row = Row(Anchor("card", legend), Anchor("side", frame), gap=10.0, align="center", equal_heights=True)
    row.measure(T)
    assert _walls(row, 0) == pytest.approx(_walls(row, 1))
    for align in ("start", "stretch", "end"):
        # beside a neighbour whose content is its whole box, the walls stand on its top and its foot
        legend, side = _legend(40.0), Column(_box(70.0))
        row = Row(Anchor("card", legend), side, gap=10.0, align=align, equal_heights=True)
        row.measure(T)
        assert _walls(row, 0) == pytest.approx(_walls(row, 1)), align
        assert row.measure(T).h == pytest.approx(70.0 + legend.wall_offsets(T)[0]), align


def test_the_half_title_rides_in_the_room_a_taller_neighbour_leaves():
    legend = _legend(40.0)
    walls = legend.frame_bbox(T)[3]
    half = legend.wall_offsets(T)[0]
    # a neighbour much taller than the walls: the title adds nothing to the row
    tall = Column(_box(walls + 40.0))
    row = Row(legend, tall, gap=10.0, align="center", equal_heights=False)
    assert row.measure(T).h == pytest.approx(walls + 40.0)
    top, bottom = _walls(row, 0)
    assert (top + bottom) / 2.0 == pytest.approx((walls + 40.0) / 2.0)       # centred on its walls
    # a neighbour a little taller: only the part of the half title that finds no room adds height
    legend = _legend(40.0)
    near = Column(_box(walls + half))
    row = Row(legend, near, gap=10.0, align="center", equal_heights=False)
    assert row.measure(T).h == pytest.approx(walls + 1.5 * half)
    top, bottom = _walls(row, 0)
    (_ox, oy, size) = row._child_offsets(T)[1]
    assert (top + bottom) / 2.0 == pytest.approx(oy + size.h / 2.0)
    assert min(oy, top - half) == pytest.approx(0.0)      # nothing above the row, no empty band either


def test_a_column_lets_the_half_title_ride_in_the_gap_above_the_wall():
    half = _legend().wall_offsets(T)[0]
    gap = half + 6.0
    legend = _legend(40.0)
    column = Column(_box(20.0), legend, gap=gap, align="start")
    assert column.measure(T).h == pytest.approx(20.0 + gap + legend.frame_bbox(T)[3])   # the gap runs to the WALL
    plain = Column(_box(20.0), _frame(40.0), gap=gap, align="start")
    assert plain.measure(T).h == pytest.approx(20.0 + gap + _frame(40.0).measure(T).h)  # as before
    # a title higher than the gap: the neighbour touches it, never overlaps it
    legend = _legend(40.0)
    tight = Column(_box(20.0), legend, gap=half / 2.0, align="start")
    assert tight.measure(T).h == pytest.approx(20.0 + legend.measure(T).h)
    # at the head of a column there is no gap to ride in: the half title is the column's own
    legend = _legend(40.0)
    first = Column(legend, _box(20.0), gap=gap, align="start")
    assert first.measure(T).h == pytest.approx(legend.measure(T).h + gap + 20.0)


def test_rows_and_columns_without_a_legend_region_keep_the_general_rule():
    outside = Region(_box(40.0), label="Stage", color="#808890", dashed=False)
    row = Row(outside, _box(90.0), gap=10.0, align="center")
    sizes = [c.measure(T) for c in row.children]
    content = [c.content_bbox(T) for c in row.children]
    assert row._alignment_boxes(T, content) is content
    assert row._wall_envelope(T, content, sizes) is None
    expect = (max(cb[3] for cb in content) + max(cb[1] for cb in content)
              + max(s.h - cb[1] - cb[3] for s, cb in zip(sizes, content)))
    assert row.measure(T).h == pytest.approx(max(expect, max(s.h for s in sizes)))
    column = Column(_box(20.0), outside, gap=10.0)
    assert column._ridden_gaps(T, column._visible_children()) is None


def test_balanced_padding_mirrors_the_title_half_under_the_bottom_wall():
    plain, even = _legend(40.0, pad_y=3.0), _legend(40.0, pad_y=3.0, balance_label_padding=True)
    half = plain.wall_offsets(T)[0]

    def bands(region):
        frame, content = region.frame_bbox(T), region.content_bbox(T)
        return content[1] - frame[1], (frame[1] + frame[3]) - (content[1] + content[3])
    top, bottom = bands(plain)
    assert top - bottom == pytest.approx(half)            # the inner half of the title, over the content alone
    top, bottom = bands(even)
    assert top == pytest.approx(bottom)                   # the content centred between the walls
    assert even.measure(T).h == pytest.approx(plain.measure(T).h + half)
    # the keyword changes nothing for a region without a title on a wall
    a = Region(_box(40.0), color="#808890", dashed=False)
    b = Region(_box(40.0), color="#808890", dashed=False, balance_label_padding=True)
    assert a.measure(T) == b.measure(T)


def test_a_legend_title_inks_the_capitals_it_reserves():
    full, tight = Canvas(), Canvas()
    full.text(0.0, 20.0, "Toolchain", size=10.0)
    tight.text(0.0, 20.0, "Toolchain", size=10.0, ink_ascent=0.71)
    assert full.ink_bbox[1] == pytest.approx(10.0)        # the default: the full ascent, as before
    assert tight.ink_bbox[1] == pytest.approx(20.0 - 7.1)
    assert full.ink_bbox[3] == pytest.approx(tight.ink_bbox[3])
    # the title of a legend region stays inside the half it reserves above the wall
    from sciviz import Diagram
    legend = _legend(40.0)
    canvas = Canvas()
    legend.render(canvas, 0.0, 0.0, T)
    texts = [item for item in canvas.ink_items("text")]
    assert texts and min(item[1] for item in texts) >= -0.05
    assert Diagram(legend).render(embed_fonts=False)      # and the region still renders as a figure
