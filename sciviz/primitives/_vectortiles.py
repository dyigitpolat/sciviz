"""VectorTiles: compact row of tiny bars / arrows (quantized gradients etc.)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


class VectorTiles(Element):
    """A 1D vector rendered as a series of small coloured cells.

    The standard visual idiom for "an embedding", "a hidden state slice",
    "a chunk of activations".  Stacks vertically by default; pass
    ``orientation="horizontal"`` for a row.

    Parameters
    ----------
    n : int
        Number of cells.
    color : ColorRef or str
        Fill colour for every cell.  If ``per_cell`` is provided it overrides.
    per_cell : list of (color or value), optional
        Per-cell fill colours.  Strings/ColorRefs are used directly; floats
        are mapped through the sequential palette.
    orientation : str
        ``"vertical"`` (default, top-down stack) or ``"horizontal"`` (left-right).
    cell_size : float
        Size in pixels of the long edge of each cell.
    cell_thickness : float
        Size in pixels of the short edge of each cell.
    cell_spacing : float
        Gap between cells.
    stroke : ColorRef, str, or None
        Per-cell border colour.  ``None`` -> no border.
    radius : float
        Corner radius.
    """

    def __init__(self, n: int, *,
                 color = "info",
                 per_cell: Optional[Sequence] = None,
                 orientation: str = "vertical",
                 cell_size: float = 14.0,
                 cell_thickness: float = 14.0,
                 cell_spacing: float = 0.5,
                 stroke = "text",
                 radius: float = 1.5,
                 palette: str = "blues"):
        self.n = n
        self.color = color
        self.per_cell = list(per_cell) if per_cell else None
        self.orientation = orientation
        self.cell_size = cell_size
        self.cell_thickness = cell_thickness
        self.cell_spacing = cell_spacing
        self.stroke = stroke
        self.radius = radius
        self.palette = palette

    def measure(self, theme: Theme) -> BBox:
        long_dim = self.n * self.cell_size + (self.n - 1) * self.cell_spacing
        if self.orientation == "vertical":
            return BBox(self.cell_thickness, long_dim)
        return BBox(long_dim, self.cell_thickness)

    def _resolve_cell_color(self, idx: int, theme: Theme) -> str:
        if self.per_cell is not None and idx < len(self.per_cell):
            entry = self.per_cell[idx]
            if isinstance(entry, (int, float)):
                return theme.color_scale(entry, self.palette, 0.0, 1.0)
            return theme.color_of(entry)
        return theme.color_of(self.color)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        has_stroke = self.stroke is not None and self.stroke != "none"
        stroke_col = theme.color_of(self.stroke) if has_stroke else "none"
        sw = theme.hairline if has_stroke else 0.0
        for i in range(self.n):
            offset = i * (self.cell_size + self.cell_spacing)
            if self.orientation == "vertical":
                cx = x
                cy = y + offset
                w = self.cell_thickness
                h = self.cell_size
            else:
                cx = x + offset
                cy = y
                w = self.cell_size
                h = self.cell_thickness
            canvas.rect(cx, cy, w, h,
                       fill=self._resolve_cell_color(i, theme),
                       stroke=stroke_col, stroke_width=sw,
                       rx=self.radius)



