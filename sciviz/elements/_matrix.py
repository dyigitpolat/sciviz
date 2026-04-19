"""Matrix: heat-map style rectangular tile grid with optional overlays."""

from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


def _normalise_matrix(data) -> List[List[float]]:
    """Accept a nested list, numpy array, or tuple (rows, cols)."""
    # Numpy array?
    if hasattr(data, "tolist") and hasattr(data, "shape"):
        return [list(row) for row in data.tolist()]
    # (rows, cols) shape -> demo data
    if isinstance(data, tuple) and len(data) == 2 and all(isinstance(v, int) for v in data):
        rows, cols = data
        import random
        rng = random.Random(0)
        return [[rng.uniform(-1, 1) for _ in range(cols)] for _ in range(rows)]
    # List of lists
    return [list(row) for row in data]


class Matrix(Element):
    """A heat-mapped matrix with optional structured highlighting.

    This is the workhorse of weight/activation/attention visualisations.

    Parameters
    ----------
    data : nested list, numpy array, or ``(rows, cols)`` tuple
        The matrix values.  Cells are coloured by magnitude.
    cell_size : str or float
        ``"xs"`` .. ``"lg"`` token, or a px value.
    highlight_rows, highlight_cols : list of int
        Indices to outline with a dashed "prune" frame.
    row_labels, col_labels : "auto" | list[str] | None
        ``"auto"`` produces ``i₁, i₂, ...`` / ``j₁, j₂, ...`` subscripted labels.
    palette : str
        ``"blues"``, ``"emeralds"``, ``"ambers"``, ``"grays"``, ``"diverging"``.
    show_values : bool
        Write numeric values in each cell (small font).
    mask : 2D iterable of bool
        Where True, the cell is rendered as "pruned" (light/dashed).
    caption : str, optional
        A single-line caption below the matrix.
    """

    _CELL_SIZES = {"xs": 18.0, "sm": 22.0, "md": 28.0, "lg": 36.0}

    def __init__(self, data, *,
                 cell_size: Union[str, float] = "md",
                 highlight_rows: Optional[Sequence[int]] = None,
                 highlight_cols: Optional[Sequence[int]] = None,
                 row_labels: Union[str, Sequence[str], None] = "auto",
                 col_labels: Union[str, Sequence[str], None] = "auto",
                 palette: str = "blues",
                 show_values: bool = False,
                 mask: Optional[Sequence[Sequence[bool]]] = None,
                 caption: Optional[str] = None,
                 absolute: bool = True,
                 vmin: Optional[float] = None,
                 vmax: Optional[float] = None):
        self.data = _normalise_matrix(data)
        self.cell_size = cell_size
        self.highlight_rows = list(highlight_rows or [])
        self.highlight_cols = list(highlight_cols or [])
        self.row_labels = row_labels
        self.col_labels = col_labels
        self.palette = palette
        self.show_values = show_values
        self.mask = mask
        self.caption = caption
        self.absolute = absolute
        self._vmin = vmin
        self._vmax = vmax

    @property
    def rows(self) -> int:
        return len(self.data)

    @property
    def cols(self) -> int:
        return len(self.data[0]) if self.data else 0

    def _cell_px(self, theme: Theme) -> float:
        if isinstance(self.cell_size, str):
            return self._CELL_SIZES.get(self.cell_size, 28.0)
        return float(self.cell_size)

    def _resolve_labels(self, which: str) -> Optional[List[str]]:
        labels = self.row_labels if which == "row" else self.col_labels
        n = self.rows if which == "row" else self.cols
        if labels is None:
            return None
        if labels == "auto":
            sub = "\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
            prefix = "i" if which == "row" else "j"
            return [f"{prefix}{sub[i]}" if i < len(sub) else f"{prefix}{i+1}"
                    for i in range(n)]
        return list(labels)

    def _label_space(self, theme: Theme, which: str) -> float:
        labels = self._resolve_labels(which)
        if not labels:
            return 0.0
        if which == "row":
            return max(theme.text_width(lbl, "small") for lbl in labels) + theme.unit
        else:
            return theme.text_height("small") + theme.unit * 0.5

    def _value_range(self) -> Tuple[float, float]:
        if self._vmin is not None and self._vmax is not None:
            return self._vmin, self._vmax
        flat = [v for row in self.data for v in row]
        if self.absolute:
            flat = [abs(v) for v in flat]
        vmin = min(flat) if self._vmin is None else self._vmin
        vmax = max(flat) if self._vmax is None else self._vmax
        if vmax == vmin:
            vmax = vmin + 1e-6
        return vmin, vmax

    def measure(self, theme: Theme) -> BBox:
        c = self._cell_px(theme)
        row_lbl = self._label_space(theme, "row")
        col_lbl = self._label_space(theme, "col")
        w = row_lbl + self.cols * c
        h = col_lbl + self.rows * c
        if self.caption:
            h += theme.text_height("small") + theme.unit
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        c = self._cell_px(theme)
        row_lbl_w = self._label_space(theme, "row")
        col_lbl_h = self._label_space(theme, "col")
        mx = x + row_lbl_w
        my = y + col_lbl_h
        vmin, vmax = self._value_range()

        # column labels
        col_labels = self._resolve_labels("col")
        if col_labels:
            sz = theme.size_px("small")
            for j, lbl in enumerate(col_labels):
                cx = mx + j * c + c / 2
                baseline = y + col_lbl_h - theme.unit * 0.3
                is_hl = j in self.highlight_cols
                canvas.text(
                    cx, baseline, lbl,
                    size=sz,
                    fill=theme.color_of("highlight" if is_hl else "light"),
                    weight="700" if is_hl else "500",
                    anchor="middle",
                )

        # row labels
        row_labels = self._resolve_labels("row")
        if row_labels:
            sz = theme.size_px("small")
            for i, lbl in enumerate(row_labels):
                baseline = my + i * c + c / 2 + sz * 0.35
                is_hl = i in self.highlight_rows
                canvas.text(
                    mx - theme.unit * 0.7, baseline, lbl,
                    size=sz,
                    fill=theme.color_of("highlight" if is_hl else "light"),
                    weight="700" if is_hl else "500",
                    anchor="end",
                )

        # cells
        for i in range(self.rows):
            for j in range(self.cols):
                val = self.data[i][j]
                masked = (self.mask is not None and self.mask[i][j])
                is_pruned = (i in self.highlight_rows) or (j in self.highlight_cols)
                cx, cy = mx + j * c, my + i * c
                use_val = abs(val) if self.absolute else val
                # pruned/masked cells render as disabled
                if masked or is_pruned:
                    canvas.rect(
                        cx + 1, cy + 1, c - 2, c - 2,
                        fill=theme.color_of("#f8fafc"),
                        stroke=theme.color_of("border_strong"),
                        stroke_width=0.6, rx=2, dasharray="2,1.5",
                    )
                else:
                    color = theme.color_scale(use_val, self.palette, vmin, vmax)
                    canvas.rect(
                        cx + 1, cy + 1, c - 2, c - 2,
                        fill=color,
                        stroke="#1e3a8a" if self.palette == "blues" else "none",
                        stroke_width=0.3, rx=2, opacity=0.95,
                    )
                if self.show_values and not masked and not is_pruned:
                    text_color = "white" if use_val > (vmin + vmax) / 2 else theme.text
                    canvas.text(
                        cx + c / 2, cy + c / 2 + theme.size_px("tiny") * 0.33,
                        f"{val:.2f}",
                        size=theme.size_px("tiny"),
                        fill=text_color if text_color.startswith("#") else theme.color_of(text_color),
                        anchor="middle",
                    )

        # highlighted rows
        for i in self.highlight_rows:
            canvas.rect(
                mx - 1, my + i * c + 1, self.cols * c + 2, c - 2,
                fill="none", stroke=theme.highlight,
                stroke_width=1.8, rx=3, dasharray="5,3",
            )
        # highlighted columns
        for j in self.highlight_cols:
            canvas.rect(
                mx + j * c + 1, my - 1, c - 2, self.rows * c + 2,
                fill="none", stroke=theme.highlight,
                stroke_width=1.8, rx=3, dasharray="5,3",
            )

        # caption
        if self.caption:
            baseline = my + self.rows * c + theme.text_height("small")
            canvas.text(
                x + (row_lbl_w + self.cols * c) / 2, baseline,
                self.caption, size=theme.size_px("small"),
                fill=theme.color_of("highlight"),
                weight="600", anchor="middle",
            )


