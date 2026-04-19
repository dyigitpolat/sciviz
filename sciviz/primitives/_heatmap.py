"""Heatmap: 2D scalar field rendered as a filled cell grid."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


class Heatmap(Element):
    """A 2D scalar heatmap with axis labels and an optional colorbar.

    Distinct from :class:`Matrix` which was tuned for ML weight visualisation
    (with ``highlight_rows`` / ``highlight_cols`` etc.).  ``Heatmap`` is the
    minimum viable element when you just need "show me this 2D array nicely".

    Parameters
    ----------
    data : nested list of float or numpy array
    cell : float
        Per-cell pixel size.
    palette : str
        Sequential palette name (``"blues"``, ``"emeralds"``, ...).
    vmin, vmax : float, optional
        Color scale endpoints.  Default = data min/max.
    x_label, y_label : str, optional
        Axis titles.
    show_grid : bool
        Draw thin gridlines between cells.
    show_values : bool
        Print numeric value in each cell.
    border : bool
        Outline the whole heatmap.
    """

    def __init__(self, data, *,
                 cell: float = 18.0,
                 palette: str = "blues",
                 vmin: Optional[float] = None,
                 vmax: Optional[float] = None,
                 x_label: Optional[str] = None,
                 y_label: Optional[str] = None,
                 show_grid: bool = True,
                 show_values: bool = False,
                 border: bool = True):
        # numpy compat
        if hasattr(data, "tolist"):
            data = data.tolist()
        self.data = [list(row) for row in data]
        self.cell = cell
        self.palette = palette
        self._vmin = vmin
        self._vmax = vmax
        self.x_label = x_label
        self.y_label = y_label
        self.show_grid = show_grid
        self.show_values = show_values
        self.border = border

    @property
    def rows(self): return len(self.data)
    @property
    def cols(self): return len(self.data[0]) if self.data else 0

    def _vrange(self):
        if self._vmin is not None and self._vmax is not None:
            return self._vmin, self._vmax
        flat = [v for r in self.data for v in r]
        if not flat:
            return 0.0, 1.0
        lo = self._vmin if self._vmin is not None else min(flat)
        hi = self._vmax if self._vmax is not None else max(flat)
        if hi == lo:
            hi = lo + 1e-9
        return lo, hi

    def _x_label_h(self, theme):
        return theme.text_height("small") + theme.unit * 0.4 if self.x_label else 0.0

    def _y_label_w(self, theme):
        return theme.text_height("small") + theme.unit * 0.4 if self.y_label else 0.0

    def measure(self, theme: Theme) -> BBox:
        return BBox(self._y_label_w(theme) + self.cols * self.cell,
                    self.rows * self.cell + self._x_label_h(theme))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        gx = x + self._y_label_w(theme)
        gy = y
        vmin, vmax = self._vrange()

        for i in range(self.rows):
            for j in range(self.cols):
                v = self.data[i][j]
                color = theme.color_scale(v, self.palette, vmin, vmax)
                cx = gx + j * self.cell
                cy = gy + i * self.cell
                stroke = theme.color_of("border") if self.show_grid else "none"
                canvas.rect(cx, cy, self.cell, self.cell,
                           fill=color, stroke=stroke,
                           stroke_width=theme.hairline if self.show_grid else 0)
                if self.show_values:
                    txt_color = theme.text_on(color)
                    canvas.text(cx + self.cell / 2,
                               cy + self.cell / 2 + theme.size_px("tiny") * 0.33,
                               f"{v:.2f}", size=theme.size_px("tiny"),
                               fill=txt_color, anchor="middle")
        if self.border:
            canvas.rect(gx, gy, self.cols * self.cell, self.rows * self.cell,
                       fill="none", stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
        # Axis labels
        if self.x_label:
            canvas.text(gx + (self.cols * self.cell) / 2,
                       gy + self.rows * self.cell + theme.size_px("small") * 1.4,
                       self.x_label, size=theme.size_px("small"),
                       fill=theme.color_of("text_muted"), anchor="middle")
        if self.y_label:
            yl_x = x + theme.text_height("small") * 0.5
            yl_y = gy + (self.rows * self.cell) / 2
            canvas.raw(
                f'<text x="{yl_x:.2f}" y="{yl_y:.2f}" '
                f'font-size="{theme.size_px("small"):.1f}" '
                f'fill="{theme.color_of("text_muted")}" '
                f'text-anchor="middle" '
                f'transform="rotate(-90 {yl_x:.2f} {yl_y:.2f})">'
                f'{self.y_label}</text>'
            )



