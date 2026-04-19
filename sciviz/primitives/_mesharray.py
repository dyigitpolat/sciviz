"""MeshArray: 2D grid of cells with optional peripheral annotations."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


class MeshArray(Element):
    """A 2D grid of cells with optional peripheral row / column annotations.

    Generalises common diagrams of:

    * Analog crossbars (peripherals = DACs / ADCs).
    * Systolic arrays (peripherals = PEs at edges).
    * NoC tile arrays (peripherals = routers).
    * Spreadsheet-style data with row/column headers.

    The author specifies a grid ``shape=(rows, cols)`` plus optional rendering
    callbacks for cell, top-row, bottom-row, left-column, and right-column.
    The library handles spacing and connections so author writes minimal code.

    Parameters
    ----------
    shape : tuple (rows, cols)
    cell : float
        Per-cell pixel size.
    cell_renderer : callable (i, j) -> Element, optional
        Returns the Element to place at cell (i, j).  Default: a small
        coloured square based on a constant or ``cell_data``.
    cell_data : 2D iterable, optional
        Provides values for default ``cell_renderer`` colour scaling.
    palette : str
    cell_padding : float
        Padding inside each cell when rendering Elements (set to 0 for
        a tight grid).
    top, bottom : list of Element, optional
        Per-column peripheral elements above / below the grid (length = cols).
    left, right : list of Element, optional
        Per-row peripheral elements left / right of the grid (length = rows).
    show_lines : bool
        Draw word-line / bit-line connectors when peripherals are present.
    line_color : ColorRef or str
    """

    def __init__(self, shape: Tuple[int, int], *,
                 cell: float = 18.0,
                 cell_renderer = None,
                 cell_data = None,
                 palette: str = "blues",
                 vmin: Optional[float] = None,
                 vmax: Optional[float] = None,
                 cell_padding: float = 0.0,
                 top = None, bottom = None, left = None, right = None,
                 show_lines: bool = True,
                 line_color = "border_strong",
                 cell_border = True,
                 disable_rows = None,
                 disable_cols = None,
                 disabled_opacity: float = 0.25):
        self.rows, self.cols = shape
        self.cell = cell
        self.cell_renderer = cell_renderer
        if cell_data is not None and hasattr(cell_data, "tolist"):
            cell_data = cell_data.tolist()
        self.cell_data = cell_data
        self.palette = palette
        self._vmin = vmin
        self._vmax = vmax
        self.cell_padding = cell_padding
        self.top = list(top) if top else None
        self.bottom = list(bottom) if bottom else None
        self.left = list(left) if left else None
        self.right = list(right) if right else None
        self.show_lines = show_lines
        self.line_color = line_color
        self.cell_border = cell_border
        self.disable_rows = frozenset(disable_rows) if disable_rows else frozenset()
        self.disable_cols = frozenset(disable_cols) if disable_cols else frozenset()
        self.disabled_opacity = disabled_opacity
        self._validate()

    def _cell_opacity(self, i: int, j: int) -> float:
        """Return 1.0 for fully active cells, ``disabled_opacity`` otherwise."""
        if i in self.disable_rows or j in self.disable_cols:
            return self.disabled_opacity
        return 1.0

    def _validate(self):
        if self.top is not None and len(self.top) != self.cols:
            raise ValueError(f"top has {len(self.top)} elements, need {self.cols}")
        if self.bottom is not None and len(self.bottom) != self.cols:
            raise ValueError(f"bottom has {len(self.bottom)} elements, need {self.cols}")
        if self.left is not None and len(self.left) != self.rows:
            raise ValueError(f"left has {len(self.left)} elements, need {self.rows}")
        if self.right is not None and len(self.right) != self.rows:
            raise ValueError(f"right has {len(self.right)} elements, need {self.rows}")

    def _peripheral_extents(self, theme: Theme):
        """Return (top_h, bottom_h, left_w, right_w)."""
        def col_max_h(items): return max((e.measure(theme).h for e in items), default=0.0)
        def row_max_w(items): return max((e.measure(theme).w for e in items), default=0.0)
        top_h = col_max_h(self.top) + theme.unit if self.top else 0.0
        bottom_h = col_max_h(self.bottom) + theme.unit if self.bottom else 0.0
        left_w = row_max_w(self.left) + theme.unit if self.left else 0.0
        right_w = row_max_w(self.right) + theme.unit if self.right else 0.0
        return top_h, bottom_h, left_w, right_w

    def measure(self, theme: Theme) -> BBox:
        th, bh, lw, rw = self._peripheral_extents(theme)
        gw = self.cols * self.cell
        gh = self.rows * self.cell
        return BBox(lw + gw + rw, th + gh + bh)

    def _vrange(self):
        if self.cell_data is None:
            return 0.0, 1.0
        flat = [v for r in self.cell_data for v in r]
        lo = self._vmin if self._vmin is not None else min(flat)
        hi = self._vmax if self._vmax is not None else max(flat)
        if hi == lo:
            hi = lo + 1e-9
        return lo, hi

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        th, bh, lw, rw = self._peripheral_extents(theme)
        gx = x + lw
        gy = y + th
        gw = self.cols * self.cell
        gh = self.rows * self.cell
        vmin, vmax = self._vrange()
        line_col = theme.color_of(self.line_color)

        # word lines (horizontal across grid) -- shown if left/right exists
        if self.show_lines and (self.left or self.right):
            for i in range(self.rows):
                yy = gy + i * self.cell + self.cell / 2
                canvas.line(gx, yy, gx + gw, yy,
                           stroke=line_col, stroke_width=theme.hairline)
        # bit lines (vertical) -- shown if top/bottom exists
        if self.show_lines and (self.top or self.bottom):
            for j in range(self.cols):
                xx = gx + j * self.cell + self.cell / 2
                canvas.line(xx, gy, xx, gy + gh,
                           stroke=line_col, stroke_width=theme.hairline)

        # cells
        for i in range(self.rows):
            for j in range(self.cols):
                cx = gx + j * self.cell
                cy = gy + i * self.cell
                op = self._cell_opacity(i, j)
                if self.cell_renderer is not None:
                    elem = self.cell_renderer(i, j)
                    if elem is not None:
                        sz = elem.measure(theme)
                        ex = cx + (self.cell - sz.w) / 2
                        ey = cy + (self.cell - sz.h) / 2
                        elem.render(canvas, ex, ey, theme)
                elif self.cell_data is not None:
                    v = self.cell_data[i][j]
                    color = theme.color_scale(v, self.palette, vmin, vmax)
                    pad = max(2.0, self.cell * 0.18)
                    canvas.rect(cx + pad, cy + pad,
                               self.cell - 2 * pad, self.cell - 2 * pad,
                               fill=color,
                               stroke=theme.color_of("text") if self.cell_border else "none",
                               stroke_width=theme.hairline if self.cell_border else 0,
                               rx=1,
                               opacity=op)

        # peripherals
        def _place_col_periph(items, anchor_y, align_top):
            for j, elem in enumerate(items):
                sz = elem.measure(theme)
                ex = gx + j * self.cell + (self.cell - sz.w) / 2
                ey = anchor_y if align_top else anchor_y - sz.h
                elem.render(canvas, ex, ey, theme)
        def _place_row_periph(items, anchor_x, align_left):
            for i, elem in enumerate(items):
                sz = elem.measure(theme)
                ex = anchor_x if align_left else anchor_x - sz.w
                ey = gy + i * self.cell + (self.cell - sz.h) / 2
                elem.render(canvas, ex, ey, theme)

        if self.top:    _place_col_periph(self.top, gy - theme.unit * 0.5, align_top=False)
        if self.bottom: _place_col_periph(self.bottom, gy + gh + theme.unit * 0.5, align_top=True)
        if self.left:   _place_row_periph(self.left, gx - theme.unit * 0.5, align_left=False)
        if self.right:  _place_row_periph(self.right, gx + gw + theme.unit * 0.5, align_left=True)



