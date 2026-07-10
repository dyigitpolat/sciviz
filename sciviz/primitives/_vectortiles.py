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

    _SIZES = {
        "xs": (1.8, 0.8, 0.0, 0.15),
        "sm": (2.4, 1.1, 0.0, 0.20),
        "md": (3.0, 1.3, 0.0, 0.25),
        "lg": (3.8, 1.7, 0.1, 0.30),
    }

    def __init__(self, n: int, *,
                 color = "info",
                 per_cell: Optional[Sequence] = None,
                 orientation: str = "vertical",
                 cell_size: float = 14.0,
                 cell_thickness: float = 14.0,
                 cell_spacing: float = 0.5,
                 stroke = "text",
                 radius: float = 1.5,
                 palette: str = "blues",
                 size: Optional[str] = None):
        if size is not None and size not in self._SIZES:
            allowed = ", ".join(self._SIZES)
            raise ValueError(f"VectorTiles.size must be one of {allowed} or None")
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
        self.size = size

    def _dimensions(self, theme: Theme):
        if self.size is None:
            return (self.cell_size, self.cell_thickness,
                    self.cell_spacing, self.radius)
        long_u, thick_u, gap_u, radius_u = self._SIZES[self.size]
        return (theme.unit * long_u, theme.unit * thick_u,
                theme.unit * gap_u, theme.unit * radius_u)

    def measure(self, theme: Theme) -> BBox:
        cell_size, cell_thickness, cell_spacing, _radius = \
            self._dimensions(theme)
        long_dim = self.n * cell_size + (self.n - 1) * cell_spacing
        if self.orientation == "vertical":
            return BBox(cell_thickness, long_dim)
        return BBox(long_dim, cell_thickness)

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
        cell_size, cell_thickness, cell_spacing, radius = \
            self._dimensions(theme)
        for i in range(self.n):
            offset = i * (cell_size + cell_spacing)
            if self.orientation == "vertical":
                cx = x
                cy = y + offset
                w = cell_thickness
                h = cell_size
            else:
                cx = x + offset
                cy = y
                w = cell_size
                h = cell_thickness
            canvas.rect(cx, cy, w, h,
                       fill=self._resolve_cell_color(i, theme),
                       stroke=stroke_col, stroke_width=sw,
                       rx=radius)


