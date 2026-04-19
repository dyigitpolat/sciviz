"""Aligned layout helpers: Table and BarChart.

These address the core alignment problem: when you have rows of
``(label, value, bar)`` triples whose label widths differ, naive horizontal
composition via :class:`Row` will leave the bars starting at different x-positions.
:class:`Table` fixes the column widths to the max-across-column width, producing
real alignment.

:class:`BarChart` is an opinionated variant of Table for the common
"label | horizontal bar | value" pattern used in memory/cost comparisons.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from .core import Element, BBox, Canvas, Theme
from .elements import Text


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class Table(Element):
    """A grid of elements with per-column widths fixed to the column max.

    Unlike :class:`Grid` (which uses one size per row/col) this lets you
    specify per-column *alignment* ('start', 'center', 'end') independently.

    Parameters
    ----------
    rows : list of list of Element
        Row-major list of rows; each row is a list of children.  All rows
        must have the same length.
    col_align : list of str, optional
        Per-column horizontal alignment.  Default: all 'start'.
    row_align : str
        Vertical alignment of cells within their row's max height.
    gap_x, gap_y : str or float
        Column gap and row gap (semantic or px).
    """

    def __init__(self, rows: Sequence[Sequence], *,
                 col_align: Optional[Sequence[str]] = None,
                 row_align: str = "center",
                 gap_x: Union[str, float] = "sm",
                 gap_y: Union[str, float] = "sm",
                 header_rule: bool = False,
                 row_rules: bool = False,
                 column_styles: Optional[Sequence[dict]] = None):
        raw_rows = [list(r) for r in rows]
        if not raw_rows:
            self.n_cols = 0
        else:
            widths = {len(r) for r in raw_rows}
            if len(widths) != 1:
                raise ValueError(
                    f"Table rows must all have equal length; got {widths}")
            self.n_cols = len(raw_rows[0])
        self.col_align = list(col_align) if col_align else ["start"] * self.n_cols
        if len(self.col_align) != self.n_cols:
            raise ValueError("col_align length must equal number of columns")
        if column_styles is not None and len(column_styles) != self.n_cols:
            raise ValueError(
                f"column_styles must have length {self.n_cols}; "
                f"got {len(column_styles)}")
        self.column_styles = (
            [dict(cs) if cs else {} for cs in column_styles]
            if column_styles is not None else None)
        self.row_align = row_align
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.header_rule = header_rule
        self.row_rules = row_rules
        self.rows = [
            [self._coerce_cell(cell, j) for j, cell in enumerate(r)]
            for r in raw_rows
        ]

    def _coerce_cell(self, cell, col_idx: int) -> Element:
        """String cells in a column with a configured style become ``Text``.

        Element cells are always passed through unchanged so authors can
        override the column default by explicitly constructing the cell.
        """
        if isinstance(cell, Element):
            return cell
        if not isinstance(cell, str):
            raise TypeError(
                f"Table cells must be Element or str; got {type(cell)}")
        from .elements import Text
        style = {}
        if self.column_styles is not None:
            style = dict(self.column_styles[col_idx] or {})
        return Text(cell, **style)

    def _extents(self, theme: Theme):
        col_w = [0.0] * self.n_cols
        row_h = [0.0] * len(self.rows)
        sizes = []
        for i, row in enumerate(self.rows):
            row_sizes = []
            for j, cell in enumerate(row):
                s = cell.measure(theme)
                row_sizes.append(s)
                if s.w > col_w[j]:
                    col_w[j] = s.w
                if s.h > row_h[i]:
                    row_h[i] = s.h
            sizes.append(row_sizes)
        return sizes, col_w, row_h

    def measure(self, theme: Theme) -> BBox:
        if not self.rows:
            return BBox(0, 0)
        _, col_w, row_h = self._extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        W = sum(col_w) + gx * (self.n_cols - 1)
        H = sum(row_h) + gy * (len(self.rows) - 1)
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.rows:
            return
        sizes, col_w, row_h = self._extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        # precompute cumulative column starts
        col_x = [0.0]
        for w in col_w[:-1]:
            col_x.append(col_x[-1] + w + gx)
        cur_y = y
        total_w = sum(col_w) + gx * (self.n_cols - 1)
        for i, row in enumerate(self.rows):
            for j, cell in enumerate(row):
                s = sizes[i][j]
                a = self.col_align[j]
                if a == "start":
                    dx = 0.0
                elif a == "end":
                    dx = col_w[j] - s.w
                else:
                    dx = (col_w[j] - s.w) / 2
                if self.row_align == "start":
                    dy = 0.0
                elif self.row_align == "end":
                    dy = row_h[i] - s.h
                else:
                    dy = (row_h[i] - s.h) / 2
                cell.render(canvas, x + col_x[j] + dx, cur_y + dy, theme)
            # rule below header row
            if self.header_rule and i == 0:
                rule_y = cur_y + row_h[i] + gy * 0.5
                canvas.line(x, rule_y, x + total_w, rule_y,
                           stroke=theme.color_of("text"),
                           stroke_width=theme.hairline)
            elif self.row_rules and i < len(self.rows) - 1:
                rule_y = cur_y + row_h[i] + gy * 0.5
                canvas.line(x, rule_y, x + total_w, rule_y,
                           stroke=theme.color_of("border"),
                           stroke_width=theme.hairline)
            cur_y += row_h[i] + gy


# ---------------------------------------------------------------------------
# AlignedColumns
# ---------------------------------------------------------------------------


class AlignedColumns(Element):
    """Force multiple rows to share per-column widths (centred by default).

    This is :class:`Table` configured for the common "parallel rows share
    the same grid" case used for top/middle/bottom label bands, labelled
    token strips, and similar aligned compositions.  All rows must have
    the same number of children.

    Parameters
    ----------
    rows : list of lists of Element
        Row-major cells.
    col_align : str or list of str
        Either a single alignment used for every column (``"center"``,
        ``"start"``, ``"end"``) or a per-column list.  Default ``"center"``.
    gap_x, gap_y : str or float
        Column / row spacing.
    row_align : str
        Vertical alignment of cells within their row band.
    """

    def __init__(self, rows: Sequence[Sequence[Element]], *,
                 col_align: Union[str, Sequence[str]] = "center",
                 gap_x: Union[str, float] = "sm",
                 gap_y: Union[str, float] = "xs",
                 row_align: str = "center"):
        raw = [list(r) for r in rows]
        if raw:
            widths = {len(r) for r in raw}
            if len(widths) != 1:
                raise ValueError(
                    f"AlignedColumns rows must all have equal length; "
                    f"got {widths}")
        n_cols = len(raw[0]) if raw else 0
        if isinstance(col_align, str):
            col_align_list = [col_align] * n_cols
        else:
            col_align_list = list(col_align)
        self._table = Table(
            raw,
            col_align=col_align_list,
            gap_x=gap_x,
            gap_y=gap_y,
            row_align=row_align,
        )

    def measure(self, theme: Theme) -> BBox:
        return self._table.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._table.render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# BarChart
# ---------------------------------------------------------------------------

class BarChart(Element):
    """Horizontal bar chart with properly aligned label / bar / value columns.

    Values are scaled so the max value renders at ``bar_width`` px.  Each
    ``item`` may optionally specify its own color.

    Parameters
    ----------
    items : list of tuples
        Each item is either ``(label, value)`` or
        ``(label, value, value_text)`` or ``(label, value, value_text, color)``.
    bar_width : float
        Pixel width of the bar corresponding to ``vmax``.
    bar_height : float
        Pixel height of each bar.
    vmax : float, optional
        Override the bar scaling.  Defaults to the max value in ``items``.
    palette : str
        Default palette used to shade bars when no explicit color is given
        (``"blues"``, ``"grays"``, etc.).  Each bar is shaded by its own
        value magnitude.
    label_align : str
        ``"start"`` or ``"end"``.
    value_align : str
        Usually ``"end"`` so numeric values line up.
    show_axis : bool
        Draw a thin baseline under the bars.
    """

    def __init__(self, items: Sequence[tuple], *,
                 bar_width: float = 220.0,
                 bar_height: float = 10.0,
                 vmax: Optional[float] = None,
                 palette: str = "blues",
                 label_align: str = "start",
                 value_align: str = "end",
                 baseline: bool = False,
                 gap_x: Union[str, float] = "sm",
                 gap_y: Union[str, float] = "xs",
                 highlight_first: bool = False,
                 color: Optional[str] = None,
                 auto_color: bool = False):
        # normalise items
        norm = []
        for it in items:
            if len(it) == 2:
                lbl, v = it
                vt = f"{v:g}"
                col = None
            elif len(it) == 3:
                lbl, v, vt = it
                col = None
            elif len(it) == 4:
                lbl, v, vt, col = it
            else:
                raise ValueError(
                    f"BarChart item must be (label, value[, value_text[, color]]); got {it}")
            norm.append((lbl, float(v), str(vt), col))
        self.items = norm
        self.bar_width = bar_width
        self.bar_height = bar_height
        self._vmax = vmax
        self.palette = palette
        self.label_align = label_align
        self.value_align = value_align
        self.baseline = baseline
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.highlight_first = highlight_first
        # 'color' applies a single role to every bar (shaded by magnitude).
        # 'auto_color' assigns a different role per bar via Theme.role_for_index.
        # Per-item color always wins over both.
        self.color = color
        self.auto_color = auto_color

    def _vmax_resolved(self) -> float:
        if self._vmax is not None:
            return float(self._vmax)
        return max((v for _, v, _, _ in self.items), default=1.0) or 1.0

    def measure(self, theme: Theme) -> BBox:
        # Column widths: labels, bar area, values
        label_w = max((theme.text_width(lbl, "label", bold=False)
                       for lbl, _, _, _ in self.items), default=0.0)
        value_w = max((theme.text_width(vt, "small")
                       for _, _, vt, _ in self.items), default=0.0)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        row_h = max(self.bar_height, theme.text_height("label"))
        H = len(self.items) * row_h + gy * (len(self.items) - 1)
        if self.baseline:
            H += 2
        W = label_w + gx + self.bar_width + gx + value_w
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        vmax = self._vmax_resolved()
        label_w = max((theme.text_width(lbl, "label", bold=False)
                       for lbl, _, _, _ in self.items), default=0.0)
        value_w = max((theme.text_width(vt, "small")
                       for _, _, vt, _ in self.items), default=0.0)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        row_h = max(self.bar_height, theme.text_height("label"))

        bar_col_x = x + label_w + gx
        value_col_x = bar_col_x + self.bar_width + gx

        for i, (lbl, v, vt, col) in enumerate(self.items):
            cy = y + i * (row_h + gy)
            text_y = cy + row_h / 2 + theme.size_px("label") * 0.33
            # label
            if self.label_align == "end":
                canvas.text(x + label_w, text_y, lbl,
                           size=theme.size_px("label"),
                           fill=theme.color_of("text"),
                           anchor="end")
            else:
                canvas.text(x, text_y, lbl,
                           size=theme.size_px("label"),
                           fill=theme.color_of("text"))
            # bar
            bar_len = self.bar_width * (v / vmax) if vmax > 0 else 0
            # color resolution: per-item > auto-cycle > single role > palette
            if col is not None:
                fill = theme.color_of(col)
            elif self.highlight_first and i == 0:
                fill = theme.color_of("highlight_fill")
            elif self.auto_color:
                fill = theme.role(theme.role_for_index(i), "fill")
            elif self.color is not None:
                # single role tinted by magnitude
                base = theme.color_of(self.color)
                t = v / vmax if vmax > 0 else 0.5
                fill = theme._lighten(base, 0.55 - 0.55 * t)
            else:
                fill = theme.color_scale(v, self.palette, 0, vmax)
            bar_y = cy + (row_h - self.bar_height) / 2
            canvas.rect(bar_col_x, bar_y, max(bar_len, 1.0), self.bar_height,
                       fill=fill,
                       stroke=theme.color_of("border_strong"),
                       stroke_width=theme.hairline)
            # value
            if self.value_align == "end":
                canvas.text(value_col_x + value_w, text_y, vt,
                           size=theme.size_px("small"),
                           fill=theme.color_of("text_muted"),
                           anchor="end")
            else:
                canvas.text(value_col_x, text_y, vt,
                           size=theme.size_px("small"),
                           fill=theme.color_of("text_muted"))

        if self.baseline:
            base_y = y + len(self.items) * (row_h + gy) - gy + 1
            canvas.line(bar_col_x, base_y, bar_col_x + self.bar_width, base_y,
                       stroke=theme.color_of("border_strong"),
                       stroke_width=theme.hairline)
