"""Named-row grid layout for parallel-column diagrams.

The canonical use case: an architecture with several parallel pipelines that
share some structural levels (e.g. "embedding", "output head", "loss") but
may have different intermediate levels.  Authoring with Row+Column+Spacer
forces the author to hand-tune heights so corresponding levels align across
columns.  Grid takes a description of the *row slots* and the *per-column
cell contents* and does the alignment automatically.

Example::

    Grid(
        rows=["tgt", "ce", "loss", "out", "tf", "proj", "cat", "rms", "emb", "inp"],
        row_labels={"tgt": "Target Tokens", "inp": "Input Tokens"},
        columns=[
            dict(
                _panel="Main Model",
                tgt=tokens("t2","t3","t4","t5"),
                ce=box("Cross-Entropy Loss"),
                loss=math(r"\\mathcal{L}_{\\text{Main}}"),
                out=shared_box("Output Head"),
                tf=("tf","proj","cat","rms"), stack("Transformer Block x L"),
                # ... etc
            ),
            dict(_panel="MTP Module 1", ...),
            ...
        ],
        trailer=text("..."),
    )

No widths, heights, gaps, or spacers appear in the author's code.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .core import BBox, Canvas, Element, Theme
from .palette import Palette


GridKey = Union[str, Tuple[str, ...]]


class Grid(Element):
    """Aligned parallel columns with named rows.

    Parameters
    ----------
    rows : sequence of str
        Row slot names in top-to-bottom order.
    columns : sequence of dict
        Each dict maps a row name (or tuple of row names for a spanning
        cell) to an Element.  Missing row names become empty cells of the
        row's natural height.  Special key ``"_panel"`` gives the column a
        BlockGroup-style dashed-blue panel label.
    row_labels : dict row_name -> str or Element, optional
        External labels rendered on the left edge, aligned with the row.
    trailer : Element, optional
        Element placed to the right of the last column (e.g. ``Text("...")``).
    row_gap, col_gap : str or float
        Gap tokens (default "md" and "lg").
    panel_color : ColorRef
        Colour for the per-column dashed panels.
    """

    def __init__(self, *,
                 rows: Sequence[str],
                 columns: Sequence[Dict[GridKey, Any]],
                 row_labels: Optional[Dict[str, Union[str, Element]]] = None,
                 trailer: Optional[Element] = None,
                 row_gap: Union[str, float] = "md",
                 col_gap: Union[str, float] = "lg",
                 panel_color = None,
                 column_flow: Optional[str] = None,
                 column_flow_skip_before: Optional[Sequence[str]] = None):
        self.rows = list(rows)
        self.columns = [dict(c) for c in columns]
        self.row_labels = row_labels or {}
        self.trailer = trailer
        self.row_gap = row_gap
        self.col_gap = col_gap
        self.panel_color = panel_color if panel_color is not None else Palette.literal("#9aa7b5")
        self.column_flow = column_flow
        # Auto-flow arrows are skipped when the DESTINATION row (the upper
        # row, in "up" flow) is in this list.  Use this when a downstream
        # custom flow (e.g. a Bus for concatenation) will replace the
        # default single-arrow connection.
        self.column_flow_skip_before = set(column_flow_skip_before or ())

    # ---- layout ----------------------------------------------------------

    def _gap(self, theme: Theme, g) -> float:
        return theme.gap_px(g) if isinstance(g, str) else float(g)

    def _resolve_column(self, col: Dict[GridKey, Any]) -> List[Optional[Tuple[Element, int]]]:
        """Return a list of (elem, span) or None for each row index."""
        n = len(self.rows)
        out: List[Optional[Tuple[Element, int]]] = [None] * n
        for key, elem in col.items():
            if key.startswith("_") if isinstance(key, str) else False:
                continue  # panel label etc
            if isinstance(key, tuple):
                first = key[0]
                span = len(key)
                # verify all rows in the tuple are in order
                if first in self.rows:
                    idx = self.rows.index(first)
                    out[idx] = (elem, span)
            elif isinstance(key, str):
                if key in self.rows:
                    idx = self.rows.index(key)
                    out[idx] = (elem, 1)
        return out

    def _panel_of(self, col: Dict[GridKey, Any]) -> Optional[str]:
        return col.get("_panel")

    def _layout(self, theme: Theme):
        n_rows = len(self.rows)
        n_cols = len(self.columns)
        row_gap = self._gap(theme, self.row_gap)
        col_gap = self._gap(theme, self.col_gap)

        col_cells = [self._resolve_column(c) for c in self.columns]

        col_widths = [0.0] * n_cols
        for c in range(n_cols):
            for r in range(n_rows):
                cell = col_cells[c][r]
                if cell is not None:
                    elem, _ = cell
                    col_widths[c] = max(col_widths[c], elem.measure(theme).w)

        row_heights = [0.0] * n_rows
        for r in range(n_rows):
            for c in range(n_cols):
                cell = col_cells[c][r]
                if cell is not None:
                    elem, span = cell
                    if span == 1:
                        row_heights[r] = max(row_heights[r], elem.measure(theme).h)

        # expand rows to fit spanning cells
        for r in range(n_rows):
            for c in range(n_cols):
                cell = col_cells[c][r]
                if cell is not None:
                    elem, span = cell
                    if span > 1:
                        needed = elem.measure(theme).h
                        total = (sum(row_heights[r:r + span])
                                 + row_gap * (span - 1))
                        if total < needed:
                            extra = needed - total
                            per = extra / span
                            for i in range(r, r + span):
                                row_heights[i] += per

        return col_widths, row_heights, col_cells

    # ---- measure / render ------------------------------------------------

    def _row_label_width(self, theme: Theme) -> float:
        if not self.row_labels:
            return 0.0
        widths = []
        for lbl in self.row_labels.values():
            if isinstance(lbl, str):
                widths.append(theme.text_width(lbl, "small", bold=True))
            else:
                widths.append(lbl.measure(theme).w)
        return max(widths) if widths else 0.0

    def _panel_overhead(self, theme: Theme) -> Tuple[float, float]:
        """Return (top_pad, bottom_pad) inside panel (for label + border breathing)."""
        has_panels = any(self._panel_of(c) for c in self.columns)
        if not has_panels:
            return 0.0, 0.0
        # Labels live INSIDE the dashed border at the top-left.  Count the
        # max number of lines across all panel labels so the reserved top
        # space fits multi-line headers like "Main Model\n(Next Token ...)"
        max_lines = 1
        for col in self.columns:
            p = self._panel_of(col)
            if p:
                max_lines = max(max_lines, p.count("\n") + 1)
        label_h = max_lines * (theme.text_height("small") + theme.unit * 0.25)
        return label_h + theme.unit * 0.7, theme.unit * 0.7

    def measure(self, theme: Theme) -> BBox:
        col_widths, row_heights, _ = self._layout(theme)
        row_gap = self._gap(theme, self.row_gap)
        col_gap = self._gap(theme, self.col_gap)
        top_pad, bot_pad = self._panel_overhead(theme)

        w = (sum(col_widths) + col_gap * max(0, len(col_widths) - 1))
        h = (sum(row_heights) + row_gap * max(0, len(row_heights) - 1)
             + top_pad + bot_pad)

        label_w = self._row_label_width(theme)
        if label_w > 0:
            w += label_w + col_gap

        if self.trailer is not None:
            w += self.trailer.measure(theme).w + col_gap

        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        col_widths, row_heights, col_cells = self._layout(theme)
        row_gap = self._gap(theme, self.row_gap)
        col_gap = self._gap(theme, self.col_gap)
        top_pad, bot_pad = self._panel_overhead(theme)

        label_w = self._row_label_width(theme)
        grid_x = x + (label_w + col_gap if label_w > 0 else 0)
        grid_y = y + top_pad

        col_xs = [grid_x]
        for cw in col_widths[:-1]:
            col_xs.append(col_xs[-1] + cw + col_gap)
        row_ys = [grid_y]
        for rh in row_heights[:-1]:
            row_ys.append(row_ys[-1] + rh + row_gap)

        grid_h_actual = sum(row_heights) + row_gap * max(0, len(row_heights) - 1)

        # --- row labels (left gutter) -----------------------------------
        if self.row_labels:
            for row_name, lbl in self.row_labels.items():
                if row_name not in self.rows:
                    continue
                r = self.rows.index(row_name)
                row_y = row_ys[r]
                row_h = row_heights[r]
                if isinstance(lbl, str):
                    sz = theme.size_px("small")
                    lw = theme.text_width(lbl, "small", bold=True)
                    lx = x + (label_w - lw)
                    ly = row_y + row_h / 2 + sz * 0.33
                    canvas.text(lx, ly, lbl, size=sz,
                               fill=theme.color_of("text"),
                               weight="700", anchor="start")
                else:
                    e_bbox = lbl.measure(theme)
                    lx = x + (label_w - e_bbox.w)
                    ly = row_y + (row_h - e_bbox.h) / 2
                    lbl.render(canvas, lx, ly, theme)

        # --- column panels (dashed blue enclosures + labels INSIDE the border)
        # Register each panel's bbox as a weak routing region so that
        # outer :class:`Flow` routers can detour around the dashed
        # border of an unrelated column instead of skimming along it.
        # Registration uses the ``__region_<id>`` prefix which the flow
        # router treats specially (panels are NOT obstacles for flows
        # whose src or dst lives inside them).
        try:
            from .composition import _anchor_stack as _as
        except Exception:  # pragma: no cover
            _as = None
        pad = theme.unit * 0.8
        for c, col in enumerate(self.columns):
            panel_label = self._panel_of(col)
            if panel_label is None:
                continue
            col_x = col_xs[c]
            col_w = col_widths[c]
            border_color = theme.color_of(self.panel_color)
            border_y = y + theme.unit * 0.2
            border_h = (grid_y + grid_h_actual + bot_pad) - border_y
            panel_bbox = (col_x - pad, border_y,
                          col_w + 2 * pad, border_h)
            if _as is not None:
                stk = _as.get()
                if stk is not None:
                    for reg in stk:
                        reg[f"__region_col{c}"] = panel_bbox
            canvas.rect(
                *panel_bbox,
                fill="none", stroke=border_color,
                stroke_width=theme.hairline,
                rx=theme.panel_radius * 1.5,
                dasharray="4,3",
            )
            # Multi-line label inside top-left of border
            lines = panel_label.split("\n")
            sz = theme.size_px("small")
            line_h = theme.text_height("small") + theme.unit * 0.25
            label_y = border_y + sz * 0.9
            for i, line in enumerate(lines):
                is_first = (i == 0)
                canvas.text(
                    col_x, label_y + i * line_h, line,
                    size=sz if is_first else theme.size_px("tiny"),
                    fill=border_color,
                    weight="700" if is_first else "normal",
                    italic=(not is_first),
                    anchor="start",
                )

        # --- cells -------------------------------------------------------
        for c in range(len(self.columns)):
            for r in range(len(self.rows)):
                cell = col_cells[c][r]
                if cell is None:
                    continue
                elem, span = cell
                cell_x = col_xs[c]
                cell_y = row_ys[r]
                cell_w = col_widths[c]
                if span == 1:
                    cell_h = row_heights[r]
                else:
                    cell_h = (sum(row_heights[r:r + span])
                              + row_gap * (span - 1))
                e_bbox = elem.measure(theme)
                ex = cell_x + (cell_w - e_bbox.w) / 2
                ey = cell_y + (cell_h - e_bbox.h) / 2
                elem.render(canvas, ex, ey, theme)

        # --- trailer -----------------------------------------------------
        if self.trailer is not None:
            t_bbox = self.trailer.measure(theme)
            tx = col_xs[-1] + col_widths[-1] + col_gap
            ty = grid_y + (grid_h_actual - t_bbox.h) / 2
            self.trailer.render(canvas, tx, ty, theme)

        # --- auto flow arrows between consecutive cells in each column --
        if self.column_flow:
            text_col = theme.color_of("text")
            sw = theme.line
            arrow_marker = canvas.define_arrow_marker(
                color=text_col, stroke_width=sw, name_hint="colflow")
            for c in range(len(self.columns)):
                # Collect rendered (top_y, bot_y, centre_x, row_index)
                rendered = []
                for r in range(len(self.rows)):
                    cell = col_cells[c][r]
                    if cell is None:
                        continue
                    elem, span = cell
                    cell_x = col_xs[c]
                    cell_y = row_ys[r]
                    cell_w = col_widths[c]
                    cell_h = (row_heights[r] if span == 1
                              else sum(row_heights[r:r + span])
                                   + row_gap * (span - 1))
                    e_bbox = elem.measure(theme)
                    ex = cell_x + (cell_w - e_bbox.w) / 2
                    ey = cell_y + (cell_h - e_bbox.h) / 2
                    # For a span cell, the "row index" that represents this
                    # cell is its first-row (for "up" flow, arrows to cells
                    # above should attach at the top of the span).
                    rendered.append((ey, ey + e_bbox.h,
                                     cell_x + cell_w / 2,
                                     r, r + span - 1))
                # Draw arrow between each adjacent pair (i, i+1)
                for i in range(len(rendered) - 1):
                    upper_top, upper_bot, upper_cx, upper_first, _ = rendered[i]
                    lower_top, lower_bot, lower_cx, _, _ = rendered[i + 1]
                    # Skip if the destination row (upper in "up" flow) is
                    # in the skip list.
                    upper_row_name = self.rows[upper_first]
                    if upper_row_name in self.column_flow_skip_before:
                        continue
                    if self.column_flow == "up":
                        canvas.line(lower_cx, lower_top,
                                    upper_cx, upper_bot,
                                    stroke=text_col, stroke_width=sw,
                                    marker_end=arrow_marker)
                    elif self.column_flow == "down":
                        canvas.line(upper_cx, upper_bot,
                                    lower_cx, lower_top,
                                    stroke=text_col, stroke_width=sw,
                                    marker_end=arrow_marker)
