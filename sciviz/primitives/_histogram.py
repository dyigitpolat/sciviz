"""Histogram: vertical bar histogram of a discrete distribution."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


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



