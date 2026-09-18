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

from ..core import Element, BBox, Canvas, Theme
from ..elements import Text
from ._donut import DonutChart, GroupSummary, Part

__all__ = [
    "Table", "AlignedColumns", "BarChart",
    "Part", "GroupSummary", "DonutChart",
]


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class Table(Element):
    """A grid of elements with per-column widths fixed to the column max.

    Unlike :class:`Grid` (which uses one size per row/col) this lets you
    specify per-column *alignment* ('start', 'center', 'end') independently.

    Beyond alignment, a Table can carry the furniture of a typeset table:
    a header row set in bold and ruled beneath, hairline rules between
    body rows, row bands (zebra tints or one highlighted row), cell
    padding, and per-column wrap budgets so a long cell wraps instead of
    widening its column. Everything is optional; the defaults give the
    plain aligned grid.

    Parameters
    ----------
    rows : list of list of Element or str
        Row-major list of rows; each row is a list of children.  All rows
        must have the same length. A string cell becomes a :class:`Text`
        styled by ``column_styles``, or a wrapped :class:`TextBlock` in a
        column that has a budget in ``col_widths``.
    col_align : list of str, optional
        Per-column horizontal alignment.  Default: all 'start'.
    row_align : str
        Vertical alignment of cells within their row's max height.
    gap_x, gap_y : str or float
        Column gap and row gap (semantic or px).
    header : bool
        Treat the first row as the header: its string cells are set in
        weight 700 unless the column style says otherwise, and a rule in
        the text colour separates it from the body.
    rules : str
        ``"none"`` (default), ``"header"``, ``"rows"`` (a hairline in the
        border colour between body rows) or ``"all"``. ``header_rule`` and
        ``row_rules`` are the older boolean spellings and still work.
    col_widths : sequence of float or None, optional
        Per-column wrap budget in px. A string cell in such a column wraps
        at the budget; Element cells are left as authored.
    column_styles : sequence of dict, optional
        Keyword arguments for the :class:`Text` / :class:`TextBlock` made
        from a string cell, per column (``size``, ``color``, ``weight``,
        ``italic``, ``align``).
    zebra : color, optional
        Band paint for every second body row.
    row_fills : dict, optional
        ``{row index: paint}`` bands for chosen rows (a highlighted row);
        the header row is index 0 when ``header`` is set.
    pad_x, pad_y : str or float
        Inner cell padding, the room between a band's edge and the cell
        content; added to every column width and row height.
    """

    def __init__(self, rows: Sequence[Sequence], *,
                 col_align: Optional[Sequence[str]] = None,
                 row_align: str = "center",
                 gap_x: Union[str, float] = "sm",
                 gap_y: Union[str, float] = "sm",
                 header: bool = False,
                 rules: str = "none",
                 header_rule: bool = False,
                 row_rules: bool = False,
                 col_widths: Optional[Sequence[Optional[float]]] = None,
                 column_styles: Optional[Sequence[dict]] = None,
                 zebra: Optional[str] = None,
                 row_fills: Optional[dict] = None,
                 pad_x: Union[str, float] = 0.0,
                 pad_y: Union[str, float] = 0.0):
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
        if col_widths is not None and len(col_widths) != self.n_cols:
            raise ValueError(
                f"col_widths must have length {self.n_cols}; "
                f"got {len(col_widths)}")
        self.column_styles = (
            [dict(cs) if cs else {} for cs in column_styles]
            if column_styles is not None else None)
        self.col_widths = (
            [float(w) if w else None for w in col_widths]
            if col_widths is not None else None)
        self.row_align = row_align
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.header = header
        if rules not in ("none", "header", "rows", "all"):
            raise ValueError(
                f"rules must be 'none', 'header', 'rows' or 'all'; got {rules!r}")
        if header_rule and rules == "none":
            rules = "header"
        elif header_rule and rules == "rows":
            rules = "all"
        if row_rules and rules == "none":
            rules = "rows"
        elif row_rules and rules == "header":
            rules = "all"
        self.rules = rules
        self.header_rule = rules in ("header", "all")
        self.row_rules = rules in ("rows", "all")
        self.zebra = zebra
        self.row_fills = dict(row_fills) if row_fills else {}
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.rows = [
            [self._coerce_cell(cell, j, i) for j, cell in enumerate(r)]
            for i, r in enumerate(raw_rows)
        ]
        # Per-column widths forced by a containing AlignedStack. When set,
        # supersedes the intrinsic max-column widths computed in
        # :meth:`_extents`.
        self._forced_col_w: Optional[List[float]] = None
        # Outer width floor set by a container (``Column(equal_widths=True)``
        # beside a wider sibling); the surplus is shared out over the
        # columns in proportion to their natural widths.
        self._min_width = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Grow the table to a container's width; rows keep their height."""
        if min_w > self._min_width:
            self._min_width = float(min_w)

    def _coerce_cell(self, cell, col_idx: int, row_idx: int = 0) -> Element:
        """String cells become ``Text`` (or a wrapped ``TextBlock`` in a
        column with a wrap budget), styled by the column's style and, on
        the header row, set in bold.

        Element cells are always passed through unchanged so authors can
        override the column default by explicitly constructing the cell.
        """
        if isinstance(cell, Element):
            return cell
        if not isinstance(cell, str):
            raise TypeError(
                f"Table cells must be Element or str; got {type(cell)}")
        from ..elements import Text, TextBlock
        style = {}
        if self.column_styles is not None:
            style = dict(self.column_styles[col_idx] or {})
        if self.header and row_idx == 0:
            style.setdefault("weight", "700")
        budget = self.col_widths[col_idx] if self.col_widths else None
        if budget:
            style.pop("font", None)
            style.pop("rotate", None)
            return TextBlock(cell, max_width=budget, **style)
        return Text(cell, **style)

    def _pads(self, theme: Theme) -> Tuple[float, float]:
        return theme.gap_px(self.pad_x), theme.gap_px(self.pad_y)

    def _extents(self, theme: Theme, *, fill_width: bool = True):
        px, py = self._pads(theme)
        col_w = [0.0] * self.n_cols
        row_h = [0.0] * len(self.rows)
        sizes = []
        for i, row in enumerate(self.rows):
            row_sizes = []
            for j, cell in enumerate(row):
                s = cell.measure(theme)
                row_sizes.append(s)
                if s.w + 2 * px > col_w[j]:
                    col_w[j] = s.w + 2 * px
                if s.h + 2 * py > row_h[i]:
                    row_h[i] = s.h + 2 * py
            sizes.append(row_sizes)
        if self._forced_col_w is not None:
            for j in range(min(len(col_w), len(self._forced_col_w))):
                if self._forced_col_w[j] > col_w[j]:
                    col_w[j] = self._forced_col_w[j]
        if fill_width and self._min_width > 0.0 and self.n_cols:
            gx = theme.gap_px(self.gap_x)
            natural = sum(col_w) + gx * (self.n_cols - 1)
            total = sum(col_w)
            if self._min_width > natural + 1e-6 and total > 0.0:
                extra = self._min_width - natural
                col_w = [w + extra * w / total for w in col_w]
        return sizes, col_w, row_h

    # ---- AlignedStack hooks ---------------------------------------------

    def _shared_column_widths(self, theme: Theme) -> List[float]:
        """Intrinsic per-column widths, used by :class:`AlignedStack`."""
        if not self.rows:
            return []
        # Compute without the forcing override so every sibling gets the
        # same intrinsic report.
        saved = self._forced_col_w
        self._forced_col_w = None
        try:
            _, col_w, _ = self._extents(theme, fill_width=False)
        finally:
            self._forced_col_w = saved
        return list(col_w)

    def _apply_shared_columns(self, widths: List[float]) -> None:
        self._forced_col_w = list(widths)

    def measure(self, theme: Theme) -> BBox:
        if not self.rows:
            return BBox(0, 0)
        _, col_w, row_h = self._extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        W = sum(col_w) + gx * (self.n_cols - 1)
        H = sum(row_h) + gy * (len(self.rows) - 1)
        return BBox(W, H)

    def _band_paint(self, i: int, theme: Theme) -> Optional[str]:
        """The band paint of row ``i``: an explicit row fill first, then
        the zebra tint on every second body row."""
        if i in self.row_fills:
            return theme.paint_of(self.row_fills[i])
        if self.zebra is not None:
            first_body = 1 if self.header else 0
            if i >= first_body and (i - first_body) % 2 == 1:
                return theme.paint_of(self.zebra)
        return None

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.rows:
            return
        sizes, col_w, row_h = self._extents(theme)
        px, py = self._pads(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        # precompute cumulative column starts
        col_x = [0.0]
        for w in col_w[:-1]:
            col_x.append(col_x[-1] + w + gx)
        total_w = sum(col_w) + gx * (self.n_cols - 1)
        n_rows = len(self.rows)
        row_y = [y]
        for h in row_h[:-1]:
            row_y.append(row_y[-1] + h + gy)
        # Bands first: a row's band runs from half a gap above it to half
        # a gap below, so neighbouring bands meet, clipped to the table.
        for i in range(n_rows):
            paint = self._band_paint(i, theme)
            if paint is None or paint == "none":
                continue
            top = row_y[i] - (gy / 2 if i > 0 else 0.0)
            bottom = row_y[i] + row_h[i] + (gy / 2 if i < n_rows - 1 else 0.0)
            canvas.rect(x, top, total_w, bottom - top, fill=paint,
                        stroke="none", stroke_width=0.0)
        # Rules: the header rule in the text colour, body rules in the
        # border colour, each centred in the gap below its row.
        for i in range(n_rows - 1):
            rule_y = row_y[i] + row_h[i] + gy * 0.5
            if i == 0 and self.header_rule:
                canvas.line(x, rule_y, x + total_w, rule_y,
                            stroke=theme.color_of("text"),
                            stroke_width=theme.hairline)
            elif self.row_rules and (i > 0 or not self.header_rule):
                canvas.line(x, rule_y, x + total_w, rule_y,
                            stroke=theme.color_of("border"),
                            stroke_width=theme.hairline)
        for i, row in enumerate(self.rows):
            inner_h = row_h[i] - 2 * py
            for j, cell in enumerate(row):
                s = sizes[i][j]
                inner_w = col_w[j] - 2 * px
                a = self.col_align[j]
                if a == "start":
                    dx = 0.0
                elif a == "end":
                    dx = inner_w - s.w
                else:
                    dx = (inner_w - s.w) / 2
                if self.row_align == "start":
                    dy = 0.0
                elif self.row_align == "end":
                    dy = inner_h - s.h
                else:
                    dy = (inner_h - s.h) / 2
                cell.render(canvas, x + col_x[j] + px + dx,
                            row_y[i] + py + dy, theme)


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
    label_size, value_size : str
        Theme size tokens for the two text columns. A chart that lives
        inside a card has to speak at the card's type size, so both are
        author-set rather than fixed to the body defaults.
    """

    def __init__(self, items: Sequence[tuple], *,
                 bar_width: float = 220.0,
                 bar_height: float = 10.0,
                 label_size: str = "label",
                 value_size: str = "small",
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
        self.label_size = label_size
        self.value_size = value_size
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
        label_w = max((theme.text_width(lbl, self.label_size, bold=False)
                       for lbl, _, _, _ in self.items), default=0.0)
        value_w = max((theme.text_width(vt, self.value_size)
                       for _, _, vt, _ in self.items), default=0.0)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        row_h = max(self.bar_height, theme.text_height(self.label_size))
        H = len(self.items) * row_h + gy * (len(self.items) - 1)
        if self.baseline:
            H += 2
        W = label_w + gx + self.bar_width + gx + value_w
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        vmax = self._vmax_resolved()
        label_w = max((theme.text_width(lbl, self.label_size, bold=False)
                       for lbl, _, _, _ in self.items), default=0.0)
        value_w = max((theme.text_width(vt, self.value_size)
                       for _, _, vt, _ in self.items), default=0.0)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        row_h = max(self.bar_height, theme.text_height(self.label_size))

        bar_col_x = x + label_w + gx
        value_col_x = bar_col_x + self.bar_width + gx

        for i, (lbl, v, vt, col) in enumerate(self.items):
            cy = y + i * (row_h + gy)
            text_y = cy + row_h / 2 + theme.size_px(self.label_size) * 0.33
            # label
            if self.label_align == "end":
                canvas.text(x + label_w, text_y, lbl,
                           size=theme.size_px(self.label_size),
                           fill=theme.color_of("text"),
                           anchor="end")
            else:
                canvas.text(x, text_y, lbl,
                           size=theme.size_px(self.label_size),
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
                           size=theme.size_px(self.value_size),
                           fill=theme.color_of("text_muted"),
                           anchor="end")
            else:
                canvas.text(value_col_x, text_y, vt,
                           size=theme.size_px(self.value_size),
                           fill=theme.color_of("text_muted"))

        if self.baseline:
            base_y = y + len(self.items) * (row_h + gy) - gy + 1
            canvas.line(bar_col_x, base_y, bar_col_x + self.bar_width, base_y,
                       stroke=theme.color_of("border_strong"),
                       stroke_width=theme.hairline)
