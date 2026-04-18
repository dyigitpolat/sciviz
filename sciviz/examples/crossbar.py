"""Crossbar: example of a specialized element built on top of sciviz.

This module is intentionally placed under :mod:`sciviz.examples` rather than
the library core: the abstraction it codifies (an analog in-memory compute
crossbar with DAC/ADC peripherals and structured pruning) is much narrower
than the rest of the library.  It is shipped as a reference for how to wrap a
non-trivial domain visualisation into a reusable :class:`Element`.
"""

from __future__ import annotations
from typing import List, Optional, Sequence, Union

from ..core import Element, BBox, Canvas, Theme
from ..elements import _normalise_matrix


class Crossbar(Element):
    """Analog in-memory computing crossbar.

    The element renders a grid of conductance cells (one per matrix entry),
    with optional DACs on the left and ADCs on the bottom.  Structured pruning
    is expressed declaratively: pass ``prune_rows`` / ``prune_cols`` and set
    ``show_savings=True`` to draw red "hardware saved" callouts.

    Parameters
    ----------
    weights : 2D array-like or ``(rows, cols)`` tuple
    cell_size : str or float
    show_peripherals : bool
        Render DAC and ADC blocks around the array.
    prune_rows, prune_cols : list[int]
        Indices that are pruned; their DACs/ADCs are gated off.
    show_savings : bool
        Draw red callouts pointing to the saved hardware.
    show_mvm : bool
        Print the y = Wx / Kirchhoff equation below the crossbar.
    input_labels, output_labels : list[str] | "auto" | None
        Vector labels on input (x_i) and output (y_j) sides.
    """

    _CELL = {"xs": 18.0, "sm": 22.0, "md": 25.0, "lg": 30.0}

    def __init__(self, weights, *,
                 cell_size: Union[str, float] = "md",
                 show_peripherals: bool = True,
                 prune_rows: Optional[Sequence[int]] = None,
                 prune_cols: Optional[Sequence[int]] = None,
                 show_savings: bool = False,
                 show_mvm: bool = False,
                 input_labels: Union[str, Sequence[str], None] = "auto",
                 output_labels: Union[str, Sequence[str], None] = "auto",
                 annotate_cell: bool = False):
        self.weights = _normalise_matrix(weights)
        self.cell_size = cell_size
        self.show_peripherals = show_peripherals
        self.prune_rows = set(prune_rows or [])
        self.prune_cols = set(prune_cols or [])
        self.show_savings = show_savings
        self.show_mvm = show_mvm
        self.input_labels = input_labels
        self.output_labels = output_labels
        self.annotate_cell = annotate_cell

    @property
    def M(self) -> int:
        return len(self.weights)

    @property
    def N(self) -> int:
        return len(self.weights[0]) if self.weights else 0

    def _cell_px(self, theme: Theme) -> float:
        if isinstance(self.cell_size, str):
            return self._CELL.get(self.cell_size, 25.0)
        return float(self.cell_size)

    def _dac_w(self, theme: Theme) -> float:
        return 32.0 if self.show_peripherals else 0.0

    def _adc_h(self, theme: Theme) -> float:
        return 30.0 if self.show_peripherals else 0.0

    def _left_label_w(self, theme: Theme) -> float:
        if self.input_labels is None or not self.show_peripherals:
            return 0.0
        return theme.text_width("x88", "small") + theme.unit

    def _output_label_h(self, theme: Theme) -> float:
        if self.output_labels is None or not self.show_peripherals:
            return 0.0
        return theme.text_height("small") + theme.unit * 0.5

    def _mvm_h(self, theme: Theme) -> float:
        if not self.show_mvm:
            return 0.0
        return theme.text_height("label") + theme.text_height("small") + theme.unit

    def _savings_side_w(self, theme: Theme) -> float:
        return 170.0 if self.show_savings else 0.0

    def measure(self, theme: Theme) -> BBox:
        c = self._cell_px(theme)
        grid_w = self.N * c
        grid_h = self.M * c
        left = self._left_label_w(theme) + self._dac_w(theme)
        bottom = self._adc_h(theme) + self._output_label_h(theme)
        right = self._savings_side_w(theme)
        top = 0.0
        if self.annotate_cell:
            right = max(right, 110.0)
        if self.show_savings:
            # callouts occupy vertical slots, need top padding for first callout
            top = 46.0
        w = left + grid_w + right
        h = top + grid_h + bottom + self._mvm_h(theme)
        return BBox(w, h)

    def _resolve_axis_labels(self, labels, n: int, prefix: str) -> Optional[List[str]]:
        if labels is None:
            return None
        if labels == "auto":
            sub = "\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
            return [f"{prefix}{sub[i]}" if i < len(sub) else f"{prefix}{i+1}"
                    for i in range(n)]
        return list(labels)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        c = self._cell_px(theme)
        size = self.measure(theme)
        left_lbl_w = self._left_label_w(theme)
        dac_w = self._dac_w(theme)
        adc_h = self._adc_h(theme)
        out_lbl_h = self._output_label_h(theme)
        top_pad = 46.0 if self.show_savings else 0.0

        gx = x + left_lbl_w + dac_w
        gy = y + top_pad

        # value range (by magnitude)
        flat = [abs(v) for row in self.weights for v in row]
        vmax = max(flat) if flat else 1.0
        vmin = 0.0

        # --- Word lines and DACs ---
        if self.show_peripherals:
            for i in range(self.M):
                yy = gy + i * c + c / 2
                pruned = i in self.prune_rows
                line_color = theme.color_of("disabled_stroke" if pruned else "grid")
                dash = "3,2" if pruned else None
                # word line (into the array)
                canvas.line(gx, yy, gx + self.N * c, yy,
                           stroke=line_color, stroke_width=1.0, dasharray=dash)
                # DAC
                dfill = theme.color_of("disabled_fill" if pruned else "primary_fill")
                dstroke = theme.color_of("disabled_stroke" if pruned else "primary")
                dtext = theme.color_of("disabled_text" if pruned else "inverse")
                dx0 = gx - dac_w
                canvas.rect(dx0, yy - 9, dac_w, 18,
                           fill=dfill, stroke=dstroke, stroke_width=0.8, rx=2)
                canvas.text(dx0 + dac_w / 2, yy + 3, "DAC",
                           size=9, fill=dtext, weight="700", anchor="middle")
                # wire from DAC to line
                canvas.line(dx0 + dac_w, yy, gx, yy,
                           stroke=line_color, stroke_width=1.0, dasharray=dash)
                # input label
                in_labels = self._resolve_axis_labels(
                    self.input_labels, self.M, "x")
                if in_labels:
                    canvas.text_with_sub(
                        dx0 - theme.unit * 0.6, yy + 3.5,
                        "x", str(i + 1),
                        size=theme.size_px("small"),
                        fill=theme.color_of("disabled_text" if pruned else "text"),
                        anchor="end",
                    )
                # X through pruned DAC
                if pruned and self.show_savings:
                    canvas.line(dx0 + 4, yy - 5, dx0 + dac_w - 4, yy + 5,
                               stroke=theme.highlight_fill, stroke_width=1.3)
                    canvas.line(dx0 + 4, yy + 5, dx0 + dac_w - 4, yy - 5,
                               stroke=theme.highlight_fill, stroke_width=1.3)

        # --- Bit lines and ADCs ---
        if self.show_peripherals:
            for j in range(self.N):
                xx = gx + j * c + c / 2
                pruned = j in self.prune_cols
                line_color = theme.color_of("disabled_stroke" if pruned else "grid")
                dash = "3,2" if pruned else None
                canvas.line(xx, gy, xx, gy + self.M * c,
                           stroke=line_color, stroke_width=1.0, dasharray=dash)
                ay0 = gy + self.M * c + theme.unit
                dfill = theme.color_of("disabled_fill" if pruned else "accent_fill")
                dstroke = theme.color_of("disabled_stroke" if pruned else "accent")
                dtext = theme.color_of("disabled_text" if pruned else "inverse")
                canvas.rect(xx - 10, ay0, 20, adc_h - 2,
                           fill=dfill, stroke=dstroke, stroke_width=0.8, rx=2)
                canvas.text(xx, ay0 + adc_h / 2 + 1, "ADC",
                           size=9, fill=dtext, weight="700", anchor="middle")
                canvas.line(xx, gy + self.M * c, xx, ay0,
                           stroke=line_color, stroke_width=1.0, dasharray=dash)
                # output label
                out_labels = self._resolve_axis_labels(
                    self.output_labels, self.N, "y")
                if out_labels:
                    canvas.text_with_sub(
                        xx - theme.text_width(out_labels[j], "small") / 2,
                        ay0 + adc_h + theme.text_height("small") * 0.8,
                        "y", str(j + 1),
                        size=theme.size_px("small"),
                        fill=theme.color_of("disabled_text" if pruned else "text"),
                    )
                if pruned and self.show_savings:
                    canvas.line(xx - 7, ay0 + 6, xx + 7, ay0 + adc_h - 8,
                               stroke=theme.highlight_fill, stroke_width=1.3)
                    canvas.line(xx - 7, ay0 + adc_h - 8, xx + 7, ay0 + 6,
                               stroke=theme.highlight_fill, stroke_width=1.3)

        # --- Cells ---
        for i in range(self.M):
            for j in range(self.N):
                cxc = gx + j * c + c / 2
                cyc = gy + i * c + c / 2
                pruned = (i in self.prune_rows) or (j in self.prune_cols)
                if pruned:
                    canvas.rect(
                        cxc - 5, cyc - 5, 10, 10,
                        fill=theme.color_of("disabled_fill"),
                        stroke=theme.color_of("disabled_stroke"),
                        stroke_width=0.4, rx=1.5, dasharray="1.5,1",
                    )
                else:
                    mag = abs(self.weights[i][j])
                    color = theme.color_scale(mag, "blues", vmin, vmax)
                    canvas.rect(
                        cxc - 5, cyc - 5, 10, 10,
                        fill=color, stroke=theme.text,
                        stroke_width=0.4, rx=1.5, opacity=0.95,
                    )

        # --- Pruned highlight bands ---
        if self.show_savings:
            for i in self.prune_rows:
                canvas.rect(
                    gx - dac_w - 4, gy + i * c - 2,
                    self.N * c + dac_w + 8, c + 4,
                    fill=theme.color_of("highlight_soft"),
                    stroke=theme.color_of("highlight_fill"),
                    stroke_width=0.8, opacity=0.45, rx=2, dasharray="4,2",
                )
            for j in self.prune_cols:
                canvas.rect(
                    gx + j * c - 2, gy - 2,
                    c + 4, self.M * c + adc_h + 4,
                    fill=theme.color_of("highlight_soft"),
                    stroke=theme.color_of("highlight_fill"),
                    stroke_width=0.8, opacity=0.45, rx=2, dasharray="4,2",
                )

        # --- Callouts on the right ---
        if self.show_savings and (self.prune_rows or self.prune_cols):
            callout_x = gx + self.N * c + 12
            if self.prune_rows:
                self._draw_callout(
                    canvas, callout_x, y,
                    title="Row pruning",
                    body="DAC + driver gated off",
                    theme=theme,
                )
                # arrow from callout to first pruned DAC
                first = min(self.prune_rows)
                dac_cx = gx - dac_w / 2
                dac_cy = gy + first * c + c / 2
                canvas.line(callout_x + 4, y + 20, dac_cx, dac_cy,
                           stroke=theme.highlight_fill, stroke_width=0.9,
                           dasharray="2,2",
                           marker_end=canvas.define_marker(color=theme.highlight_fill, size=5, name_hint="hlArr"))
            if self.prune_cols:
                cy_btm = gy + self.M * c + adc_h + out_lbl_h + 10
                self._draw_callout(
                    canvas, callout_x, cy_btm,
                    title="Column pruning",
                    body="ADC + S&H removed (largest win)",
                    theme=theme,
                )
                first = min(self.prune_cols)
                adc_cx = gx + first * c + c / 2
                adc_cy = gy + self.M * c + adc_h / 2 + theme.unit
                canvas.line(callout_x + 4, cy_btm + 18, adc_cx + 10, adc_cy,
                           stroke=theme.highlight_fill, stroke_width=0.9,
                           dasharray="2,2",
                           marker_end=canvas.define_marker(color=theme.highlight_fill, size=5, name_hint="hlArr"))

        # --- Cell annotation ---
        if self.annotate_cell:
            ann_x = gx + self.N * c + theme.unit * 1.5
            ann_y = gy + theme.unit * 0.5
            canvas.text(ann_x, ann_y + 8, "Cell (memristor)",
                       size=theme.size_px("small"), fill=theme.primary,
                       weight="700")
            canvas.text(ann_x, ann_y + 8 + theme.text_height("small"),
                       "G\u1d62\u2c7c \u221d |w\u1d62\u2c7c|",
                       size=theme.size_px("small"),
                       fill=theme.text_muted)

        # --- MVM annotation ---
        if self.show_mvm:
            my0 = gy + self.M * c + adc_h + out_lbl_h + theme.unit * 1.5
            canvas.text(
                gx + self.N * c / 2, my0 + theme.size_px("label") * 0.7,
                "y = Wx   \u27f6   I\u2c7c = \u03a3\u1d62 G\u1d62\u2c7c \u00b7 V\u1d62",
                size=theme.size_px("label"), fill=theme.text,
                weight="600", anchor="middle",
            )

    def _draw_callout(self, canvas, x, y, *, title, body, theme):
        w, h = 160, 38
        canvas.rect(
            x, y, w, h,
            fill=theme.highlight_soft,
            stroke=theme.highlight_fill,
            stroke_width=1.0, rx=4,
        )
        canvas.text(
            x + w / 2, y + theme.size_px("small") * 1.2,
            title, size=theme.size_px("small"),
            fill=theme.highlight_fill, weight="700", anchor="middle",
        )
        canvas.text(
            x + w / 2, y + theme.size_px("small") * 1.2 + theme.text_height("small"),
            body, size=theme.size_px("small"),
            fill=theme.text, anchor="middle",
        )


# ---------------------------------------------------------------------------
# NNLayer
# ---------------------------------------------------------------------------
