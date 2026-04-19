"""Pyramid: stacked-trapezoid layout (memory hierarchies, taxonomies)."""

from __future__ import annotations

import math as _m
from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


class Pyramid(Element):
    """A stack of trapezoidal layers, widest at the bottom.

    Each level is ``(label, side_cells)`` with an optional colour.
    Useful for cache hierarchies, memory pyramids, storage tiers, ...

    Parameters
    ----------
    levels : list of tuples
        Each level is ``(label, side, color?)`` where ``side`` may be either
        a single string (rendered as one right-aligned annotation) or a list
        of strings (rendered as aligned columns).
    width : float
        Maximum (base) width of the pyramid in px.
    tip_width : float
        Width of the topmost trapezoid in px.
    level_h : float
        Height of each level.
    palette : str
        Used to shade levels by position when no explicit colour is given.
    side_col_gap : float
        Horizontal gap between side-annotation columns in px.
    """

    def __init__(self, levels: Sequence[tuple], *,
                 width: float = 240.0,
                 tip_width: float = 80.0,
                 level_h: float = 28.0,
                 palette: str = "blues",
                 gap: float = 0.0,
                 side_col_gap: float = 14.0,
                 color: Optional[str] = None):
        self.levels = [self._normalise(lv) for lv in levels]
        self.width = width
        self.tip_width = tip_width
        self.level_h = level_h
        self.palette = palette
        self.gap = gap
        self.side_col_gap = side_col_gap
        # 'color' overrides the per-level color when no explicit color is given.
        # If both color and per-level color are unset, the sequential palette
        # is used to shade by depth.
        self.color = color

    @staticmethod
    def _normalise(lv):
        if isinstance(lv, str):
            return (lv, [], None)
        if len(lv) == 1:
            return (str(lv[0]), [], None)
        if len(lv) == 2:
            return (str(lv[0]), lv[1], None)
        if len(lv) == 3:
            return (str(lv[0]), lv[1], lv[2])
        raise ValueError(f"Pyramid level must be 1-, 2-, or 3-tuple, got {lv!r}")

    @staticmethod
    def _side_cells(side) -> List[str]:
        if isinstance(side, str):
            return [side]
        return [str(s) for s in side]

    @staticmethod
    def _is_light(hex_color: str) -> bool:
        """Return True if color is 'light' -> black text, else white text."""
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return True
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        # luminance (sRGB relative)
        L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return L > 0.58

    def _side_col_widths(self, theme: Theme) -> List[float]:
        # global column widths -> same alignment across all levels
        cells_per_level = [self._side_cells(lv[1]) for lv in self.levels]
        n_cols = max((len(c) for c in cells_per_level), default=0)
        widths = [0.0] * n_cols
        for cells in cells_per_level:
            for j, c in enumerate(cells):
                w = theme.text_width(c, "small")
                if w > widths[j]:
                    widths[j] = w
        return widths

    def measure(self, theme: Theme) -> BBox:
        n = len(self.levels)
        col_widths = self._side_col_widths(theme)
        side_total = sum(col_widths) + self.side_col_gap * max(0, len(col_widths) - 1)
        # total width: pyramid + a gap + side block on the right
        w = self.width + theme.unit * 2 + side_total + theme.unit
        h = n * self.level_h + (n - 1) * self.gap
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        n = len(self.levels)
        if n == 0:
            return
        col_widths = self._side_col_widths(theme)
        side_total = sum(col_widths) + self.side_col_gap * max(0, len(col_widths) - 1)
        # Center the pyramid base within the pyramid region (width)
        # Layout: [pyramid area W] [gap] [side block side_total]
        cx = x + self.width / 2
        side_start_x = x + self.width + theme.unit * 2

        for i, (label, side, col) in enumerate(self.levels):
            # trapezoid widths: top at i/n, bottom at (i+1)/n interpolation
            w_top = self.tip_width + (self.width - self.tip_width) * (i / n)
            w_bot = self.tip_width + (self.width - self.tip_width) * ((i + 1) / n)
            top_y = y + i * (self.level_h + self.gap)
            bot_y = top_y + self.level_h
            pts = [
                (cx - w_top / 2, top_y),
                (cx + w_top / 2, top_y),
                (cx + w_bot / 2, bot_y),
                (cx - w_bot / 2, bot_y),
            ]
            # colour
            if col is None:
                if self.color is not None:
                    # single role tinted by depth
                    base = theme.color_of(self.color)
                    # shade lighter at top, darker at bottom
                    t = i / max(1, n - 1)
                    fill_hex = theme._lighten(base, 0.7 - 0.7 * t)
                else:
                    fill_hex = theme.color_scale(i / max(1, n - 1),
                                                 self.palette, 0, 1)
            else:
                fill_hex = theme.color_of(col)
            canvas.polygon(pts, fill=fill_hex, stroke=theme.color_of("text"),
                          stroke_width=theme.hairline, opacity=1.0)
            # text colour from luminance
            text_color = theme.text_on(fill_hex)
            txt_y = (top_y + bot_y) / 2 + theme.size_px("label") * 0.33
            canvas.text(cx, txt_y, label,
                       size=theme.size_px("label"),
                       fill=text_color, weight="600", anchor="middle")

            # side-annotation columns (right-aligned within each column)
            cells = self._side_cells(side)
            col_x = side_start_x
            for j, c in enumerate(cells):
                cw = col_widths[j] if j < len(col_widths) else 0
                cx_right = col_x + cw
                canvas.text(cx_right, txt_y, c,
                           size=theme.size_px("small"),
                           fill=theme.color_of("text_muted"),
                           weight="400", anchor="end")
                col_x += cw + self.side_col_gap



