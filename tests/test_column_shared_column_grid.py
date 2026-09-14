"""Column shares column widths only between children that are the same grid.

Column normalises the slot widths of stacked tabular children so rows of the
same shape line up without the author reaching for AlignedStack. That
normalisation used to merge every contributing child's width list index-wise
from the left, whatever their lengths, so a Column holding a three-slot row
above an unrelated four-slot row stretched the four-slot row onto the
three-slot row's widths plus its own fourth. The result was a child wider than
every element in the column and wider than the column's own content, which is
how a figure silently overruns its declared print width.

Two rows with different slot counts are not one grid, so they are left alone;
two rows with the same slot count still align, which is the feature.
"""
from sciviz import Box, Column, Row


def _row(*widths, gap=0):
    return Row(*[Box(width=w, height=10) for w in widths], gap=gap)


def test_rows_of_different_column_counts_do_not_share_slots(theme=None):
    from sciviz import DEFAULT_THEME

    theme = theme or DEFAULT_THEME
    wide = _row(120, 120, 120)
    narrow = _row(20, 20, 20, 20)
    natural_narrow = narrow.measure(theme).w

    column = Column(wide, narrow, gap=0, align="start")
    measured = column.measure(theme)

    assert narrow.measure(theme).w == natural_narrow, (
        "a four-slot row must not be stretched onto an unrelated three-slot "
        f"row's widths; {narrow.measure(theme).w} vs {natural_narrow}")
    assert measured.w == max(wide.measure(theme).w, natural_narrow), (
        "the column must be no wider than its widest child")


def test_rows_of_equal_column_counts_still_share_slots():
    from sciviz import DEFAULT_THEME as theme

    top = _row(120, 20)
    bottom = _row(20, 120)
    Column(top, bottom, gap=0, align="start").measure(theme)

    # Both rows are the same two-column grid, so each slot takes the wider of
    # the pair and the two rows come out the same width.
    assert top.measure(theme).w == bottom.measure(theme).w
    assert top.measure(theme).w >= 240
