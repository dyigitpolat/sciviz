"""Additional generic primitives that span domains.

* :class:`Heatmap`  -- general 2D scalar field (replaces ad-hoc Matrix uses
                       for diffusion noise tiles, attention maps, image
                       gradients, anything where each cell is a scalar).
* :class:`Histogram` -- vertical bar histogram of a discrete distribution
                       (the missing companion to BarChart for FP-distributions
                       and similar).
* :class:`MeshArray` -- a 2D grid of cells with optional peripheral row /
                       column / corner annotations.  Generalises the analog
                       crossbar shape -- usable for systolic arrays, NoC
                       tiles, spreadsheet headers, quantization plots, etc.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from .core import Element, BBox, Canvas, Theme


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------

class Histogram(Element):
    """Vertical bar histogram.

    Bins may be auto-counted from raw samples (pass ``samples=...``) or
    given as pre-counted ``(label, height, color?)`` tuples.

    Parameters
    ----------
    bins : list of tuple, optional
        ``(label, height, color?)``.  ``color`` defaults to a depth-shaded
        version of ``color`` parameter or theme default.
    samples : list of float, optional
        Raw samples; histogrammed into ``n_bins`` equal-width bins.
    n_bins : int
        Number of bins when histogramming raw samples.
    width, height : float
        Plot area.
    color : ColorRef or str, optional
        Single colour for all bars (overridden by per-bin color).
    show_axis : bool
        Draw a baseline.
    bar_gap : float
        Gap between bars in px.
    """

    def __init__(self, *, bins: Optional[Sequence[tuple]] = None,
                 samples: Optional[Sequence[float]] = None,
                 n_bins: int = 10,
                 width: float = 280.0, height: float = 120.0,
                 color = None,
                 show_axis: bool = True,
                 bar_gap: float = 1.5,
                 x_label: Optional[str] = None,
                 y_label: Optional[str] = None):
        if bins is None and samples is None:
            raise ValueError("Histogram needs either bins or samples")
        if bins is not None:
            self.bins = [self._normalise(b) for b in bins]
        else:
            self.bins = self._from_samples(samples, n_bins)
        self.width = width
        self.height = height
        self.color = color
        self.show_axis = show_axis
        self.bar_gap = bar_gap
        self.x_label = x_label
        self.y_label = y_label

    @staticmethod
    def _normalise(b):
        if len(b) == 2:
            return (str(b[0]), float(b[1]), None)
        if len(b) == 3:
            return (str(b[0]), float(b[1]), b[2])
        raise ValueError(f"bin: (label, height[, color]); got {b}")

    @staticmethod
    def _from_samples(samples, n_bins):
        if not samples:
            return []
        lo, hi = min(samples), max(samples)
        if hi == lo:
            hi = lo + 1e-9
        counts = [0] * n_bins
        for v in samples:
            idx = min(n_bins - 1, int((v - lo) / (hi - lo) * n_bins))
            counts[idx] += 1
        return [(f"{lo + (i + 0.5) * (hi - lo) / n_bins:.2g}", c, None)
                for i, c in enumerate(counts)]

    def _x_label_h(self, theme):
        return theme.text_height("small") + theme.unit * 0.4 if self.x_label else 0.0

    def _tick_h(self, theme):
        return theme.text_height("tiny") + theme.unit * 0.3

    def measure(self, theme: Theme) -> BBox:
        h = self.height + self._tick_h(theme) + self._x_label_h(theme)
        return BBox(self.width, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.bins:
            return
        n = len(self.bins)
        gap = self.bar_gap
        bw = max((self.width - gap * (n - 1)) / n, 1)
        max_h = max((b[1] for b in self.bins), default=1)
        if max_h <= 0:
            max_h = 1
        base_y = y + self.height
        # base color
        if self.color is not None:
            base_col = theme.color_of(self.color)
        else:
            base_col = theme.color_of("primary_fill")
        # bars
        for i, (lbl, h, col) in enumerate(self.bins):
            bh = (h / max_h) * (self.height - 2)
            bx = x + i * (bw + gap)
            by = base_y - bh
            if col is not None:
                fill = theme.color_of(col)
            else:
                # subtle shade by relative height
                shade = h / max_h
                if hasattr(theme, "_lighten"):
                    fill = theme._lighten(base_col, 0.5 - 0.5 * shade)
                else:
                    fill = base_col
            canvas.rect(bx, by, bw, bh, fill=fill,
                       stroke=theme.color_of("border_strong"),
                       stroke_width=theme.hairline)
        # axis
        if self.show_axis:
            canvas.line(x, base_y, x + self.width, base_y,
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
        # tick labels
        ty = base_y + theme.size_px("tiny") * 1.0
        for i, (lbl, _, _) in enumerate(self.bins):
            cx = x + i * (bw + gap) + bw / 2
            canvas.text(cx, ty, lbl,
                       size=theme.size_px("tiny"),
                       fill=theme.color_of("text_muted"),
                       anchor="middle")
        # axis label
        if self.x_label:
            canvas.text(x + self.width / 2,
                       base_y + self._tick_h(theme) + theme.size_px("small") * 1.0,
                       self.x_label, size=theme.size_px("small"),
                       fill=theme.color_of("text"), anchor="middle")


# ---------------------------------------------------------------------------
# MeshArray
# ---------------------------------------------------------------------------

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
                 cell_border = True):
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
        self._validate()

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
                               rx=1)

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


# ---------------------------------------------------------------------------
# VectorTiles -- a 1D tensor visualised as a stack of coloured cells
# ---------------------------------------------------------------------------

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
                 stroke = None,
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
        stroke_col = theme.color_of(self.stroke) if self.stroke is not None else "none"
        sw = theme.hairline if self.stroke is not None else 0.0
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


# ---------------------------------------------------------------------------
# StackedBoxes -- N identical boxes with a slight 3D offset (depth visual)
# ---------------------------------------------------------------------------

class StackedBoxes(Element):
    """A stack of ``n`` identical rounded boxes, drawn with a slight offset
    so the stack reads as "this thing repeats ``n`` times".

    Used for visualising a sequence of identical layers (e.g. "Transformer
    Block × L").  The *front* (label-bearing) box sits at the bottom-left;
    subsequent boxes are offset up-and-right, creating a parallax stack.

    Parameters
    ----------
    n : int
        Number of stacked boxes (depth).
    label : str
        Text on the front-most box.
    fill : ColorRef or str
        Fill colour for each box.
    stroke : ColorRef or str, optional
        Stroke colour; defaults to a slight darken of ``fill``.
    width, height : float
        Dimensions of a single box.
    offset : float
        Pixel offset between successive boxes (up-right direction).
    radius : float
        Corner radius.
    text_size, text_weight : theme-size, weight string
        Label typography.
    sub_label : str, optional
        Small italic caption beneath the main label (e.g. precision tag).
    """

    def __init__(self, n: int, label: str, *,
                 fill,
                 stroke = None,
                 stroke_width: Optional[float] = None,
                 width: float = 150.0,
                 height: float = 30.0,
                 offset: float = 4.0,
                 radius: float = 6.0,
                 text_size: str = "small",
                 text_weight: str = "500",
                 sub_label: Optional[str] = None,
                 sub_color = "muted"):
        self.n = max(1, int(n))
        self.label = label
        self.fill = fill
        # Default stroke matches plain :class:`Box` -- the theme's text
        # color -- so a stack in a row with regular boxes reads as a
        # single, consistent visual family (not a differently-bordered
        # sibling).  Authors can still override with an explicit stroke.
        if stroke is not None:
            self.stroke = stroke
        else:
            self.stroke = "text"
        self.stroke_width = stroke_width
        self.width = width
        self.height = height
        self.offset = offset
        self.radius = radius
        self.text_size = text_size
        self.text_weight = text_weight
        self.sub_label = sub_label
        self.sub_color = sub_color

    def measure(self, theme: Theme) -> BBox:
        total = (self.n - 1) * self.offset
        return BBox(self.width + total, self.height + total)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        fill_hex = theme.color_of(self.fill)
        stroke_hex = theme.color_of(self.stroke)
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        total = (self.n - 1) * self.offset
        # Each box has a visible border -- the stack reads as N distinct layers
        # (not one blended silhouette).  Back-to-front so the front box sits
        # on top in z-order.
        for i in range(self.n):
            dx = (self.n - 1 - i) * self.offset
            dy = i * self.offset
            canvas.rect(x + dx, y + dy, self.width, self.height,
                       fill=fill_hex, stroke=stroke_hex,
                       stroke_width=sw,
                       rx=self.radius)
        # Label on front box
        sz = theme.size_px(self.text_size)
        label_cx = x + self.width / 2
        label_cy = y + total + self.height / 2
        canvas.text(label_cx, label_cy + sz * 0.33, self.label,
                   size=sz, fill=theme.color_of("text"),
                   weight=self.text_weight, anchor="middle")
        # Optional sub-label (precision tag) on the right of the front box
        if self.sub_label:
            sub_sz = theme.size_px("tiny")
            sub_x = x + self.width - theme.unit
            sub_y = y + total + self.height - sub_sz * 0.3
            canvas.text(sub_x, sub_y, self.sub_label,
                       size=sub_sz, fill=theme.color_of(self.sub_color),
                       weight="normal", italic=True, anchor="end")
