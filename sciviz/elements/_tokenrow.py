"""TokenRow: horizontal token strip used in NLP / sequence figures."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme


class TokenRow(Element):
    """A single rounded pill containing math-typeset indexed tokens.

    ``TokenRow(3, 4, 5, 6)`` renders as one continuous light-gray pill with
    ``$t_3$  $t_4$  $t_5$  $t_6$`` inside, equally spaced.  This mirrors the
    "input tokens"/"target tokens" ribbons in the DeepSeek-V3 paper: a single
    ribbon, not a table of cells.

    The caller supplies indices (ints or strings) and optionally overrides the
    base letter (``letter="x"`` -> ``x_3, x_4, ...``) or supplies raw LaTeX
    fragments via ``raw=[...]``.

    No layout/padding knobs are required: the pill auto-sizes to the content
    and honours the theme's :attr:`panel_soft` fill and :attr:`unit` spacing.
    """

    def __init__(self, *indices,
                 letter: str = "t",
                 raw: Optional[Sequence[str]] = None,
                 fill: str = "panel_soft",
                 fill_opacity: float = 0.35,
                 stroke: str = "panel_soft",
                 stroke_width: Optional[float] = None,
                 size: Union[str, float] = "math",
                 gap: Union[str, float] = "md",
                 padding: Union[str, float] = "sm"):
        if raw is not None:
            self._pieces = [str(r) for r in raw]
        else:
            if not indices:
                raise ValueError("TokenRow requires at least one index")
            self._pieces = [f"${letter}_{{{idx}}}$" for idx in indices]
        self.fill = fill
        self.fill_opacity = fill_opacity
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.size = size
        self.gap = gap
        self.padding = padding
        self._math_cache: Optional[list] = None

    def _tokens(self) -> list:
        if self._math_cache is not None:
            return self._math_cache
        from ..math import Math
        self._math_cache = [Math(p, size=self.size) for p in self._pieces]
        return self._math_cache

    def measure(self, theme: Theme) -> BBox:
        tokens = self._tokens()
        g = theme.gap_px(self.gap)
        pad = theme.gap_px(self.padding)
        sizes = [t.measure(theme) for t in tokens]
        w = sum(s.w for s in sizes) + g * (len(sizes) - 1) + 2 * pad
        h = max(s.h for s in sizes) + 2 * pad
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        tokens = self._tokens()
        g = theme.gap_px(self.gap)
        pad = theme.gap_px(self.padding)
        bbox = self.measure(theme)
        fill = theme.color_of(self.fill)
        stroke = theme.color_of(self.stroke)
        sw = self.stroke_width if self.stroke_width is not None else theme.hairline
        rx = bbox.h / 2
        canvas.rect(
            x, y, bbox.w, bbox.h,
            fill=fill, stroke=stroke, stroke_width=sw,
            opacity=self.fill_opacity, rx=rx,
        )
        sizes = [t.measure(theme) for t in tokens]
        cursor = x + pad
        for tok, sz in zip(tokens, sizes):
            ty = y + (bbox.h - sz.h) / 2
            tok.render(canvas, cursor, ty, theme)
            cursor += sz.w + g

