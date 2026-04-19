"""`AlignedColumns`: force multiple rows to share per-column widths.

Primary use case is ``gallery/speculative_decoding.py`` (three token strips
whose labels should line up in a single rigid column) and more generally
any time the author would otherwise reach for ``FixedSize`` on every cell.
"""
from __future__ import annotations

import re

from sciviz import AlignedColumns, Box, Text, Theme, Canvas


def _rects(elem):
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    svg = c.to_svg(size.w, size.h)
    return [tuple(float(g) for g in m.groups())
            for m in re.finditer(
                r'<rect[^>]*?\bx="([\d.\-]+)"[^>]*?\by="([\d.\-]+)"'
                r'[^>]*?\bwidth="([\d.\-]+)"[^>]*?\bheight="([\d.\-]+)"', svg)], size


def test_same_column_index_shares_x_across_rows():
    rows = [
        [Box("a", width=30, height=10), Box("b", width=60, height=10)],
        [Box("c", width=60, height=10), Box("d", width=30, height=10)],
    ]
    ac = AlignedColumns(rows, gap_x="md", gap_y="sm")
    rects, _ = _rects(ac)
    # Expect each "column j" to share the same x origin across rows.
    # Collect rects by row.
    row_rects = [[r for r in rects if abs(r[1] - y) < 0.5]
                 for y in sorted({r[1] for r in rects})]
    assert len(row_rects) == 2, row_rects
    for j in range(2):
        x0 = row_rects[0][j][0]
        x1 = row_rects[1][j][0]
        # AlignedColumns centres within column by default; column j should
        # have the same centre x across rows.
        cx0 = x0 + row_rects[0][j][2] / 2
        cx1 = x1 + row_rects[1][j][2] / 2
        assert abs(cx0 - cx1) < 0.5, (
            f"column {j} centres diverge: {cx0} vs {cx1}")


def test_different_row_lengths_rejected():
    import pytest
    with pytest.raises(ValueError):
        AlignedColumns([[Text("a")], [Text("a"), Text("b")]])


def test_col_align_start_left_justifies():
    rows = [
        [Box("a", width=30, height=10), Box("b", width=60, height=10)],
        [Box("c", width=60, height=10), Box("d", width=30, height=10)],
    ]
    ac = AlignedColumns(rows, col_align="start", gap_y="sm")
    rects, _ = _rects(ac)
    by_row = [[r for r in rects if abs(r[1] - y) < 0.5]
              for y in sorted({r[1] for r in rects})]
    # With col_align="start" both rows' first rect should start at x=0.
    assert abs(by_row[0][0][0] - 0.0) < 0.5
    assert abs(by_row[1][0][0] - 0.0) < 0.5
