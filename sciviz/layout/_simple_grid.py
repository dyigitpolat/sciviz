"""Simple regular N-column Grid from the layout package.

This is a legacy alternative to :class:`sciviz.grid.Grid`; kept because
some older composites still reference the simpler variant. New callers
should use :class:`sciviz.grid.Grid` for its richer per-column alignment.
"""

from __future__ import annotations

from typing import Union

from ..core import BBox, Canvas, Element, Theme


class Grid(Element):
    """Regular N-column grid, children placed row-major.

    Column widths and row heights are automatically set to the max of the
    cells they contain, so every cell is the same size within its row/column.
    """

    def __init__(self, *children: Element, cols: int,
                 gap_x: Union[str, float] = "md",
                 gap_y: Union[str, float] = "md",
                 align: str = "center"):
        self.children = list(children)
        self.cols = cols
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.align = align
        self._forced_col_w: "list[float] | None" = None

    def _col_row_extents(self, theme):
        sizes = [c.measure(theme) for c in self.children]
        rows = (len(sizes) + self.cols - 1) // self.cols
        col_w = [0.0] * self.cols
        row_h = [0.0] * rows
        for i, s in enumerate(sizes):
            r, c = i // self.cols, i % self.cols
            col_w[c] = max(col_w[c], s.w)
            row_h[r] = max(row_h[r], s.h)
        if self._forced_col_w is not None:
            for j in range(min(len(col_w), len(self._forced_col_w))):
                if self._forced_col_w[j] > col_w[j]:
                    col_w[j] = self._forced_col_w[j]
        return sizes, col_w, row_h

    def _shared_column_widths(self, theme) -> "list[float]":
        saved = self._forced_col_w
        self._forced_col_w = None
        try:
            _, col_w, _ = self._col_row_extents(theme)
        finally:
            self._forced_col_w = saved
        return list(col_w)

    def _apply_shared_columns(self, widths) -> None:
        self._forced_col_w = list(widths)

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        _, col_w, row_h = self._col_row_extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        W = sum(col_w) + gx * (len(col_w) - 1)
        H = sum(row_h) + gy * (len(row_h) - 1)
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes, col_w, row_h = self._col_row_extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        col_x = [0.0]
        for w in col_w[:-1]:
            col_x.append(col_x[-1] + w + gx)
        row_y = [0.0]
        for h in row_h[:-1]:
            row_y.append(row_y[-1] + h + gy)
        for i, (child, size) in enumerate(zip(self.children, sizes)):
            r, c = i // self.cols, i % self.cols
            cell_w, cell_h = col_w[c], row_h[r]
            if self.align == "start":
                dx, dy = 0, 0
            elif self.align == "end":
                dx = cell_w - size.w
                dy = cell_h - size.h
            else:
                dx = (cell_w - size.w) / 2
                dy = (cell_h - size.h) / 2
            child.render(canvas, x + col_x[c] + dx, y + row_y[r] + dy, theme)
