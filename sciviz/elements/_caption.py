"""Caption: a body-width-aware note attached beneath a diagram."""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme
from ._text import TextBlock


class Caption(Element):
    """A paper caption that automatically wraps to its diagram body.

    Authors provide one semantic string. :class:`~sciviz.Diagram` offers the
    measured body width through :meth:`fit_width`, so long captions wrap into
    a compact paragraph. A caption may be moderately wider than a narrow body
    (common for tall flowcharts), but it cannot become an unbounded one-line
    strip. ``max_width`` remains available for a Caption used outside Diagram,
    but ordinary figure code should not need it.
    """

    _BODY_WIDTH_FACTOR = 1.75

    def __init__(self, content: str, *, color: str = "muted",
                 size: str = "small", align: str = "start",
                 italic: bool = False, weight: str = "normal",
                 max_width: Optional[float] = None):
        self.content = content
        self.color = color
        self.size = size
        self.align = align
        self.italic = italic
        self.weight = weight
        self.max_width = max_width
        self._body_width: Optional[float] = None

    def fit_width(self, width: float) -> None:
        """Accept Diagram's measured body width as a wrapping ceiling."""
        self._body_width = max(0.0, float(width))

    def _block(self, theme: Theme) -> TextBlock:
        ceiling = self.max_width
        if self._body_width is not None:
            automatic = self._body_width * self._BODY_WIDTH_FACTOR
            # Very wide figures should not turn a caption into a single
            # hard-to-scan newspaper line. Cap the automatic measure at a
            # readable semantic line length while shorter captions retain
            # their intrinsic one-line form.
            # A two-column scientific figure legitimately needs a wider
            # caption than a single-column flowchart.  Ninety em remains a
            # readable line-length ceiling while allowing wide figures to
            # use their footprint instead of leaving a conspicuous centred
            # caption island underneath them.
            automatic = min(automatic, theme.size_px(self.size) * 90.0)
            ceiling = automatic if ceiling is None else min(ceiling, automatic)
        return TextBlock(
            self.content,
            size=self.size,
            color=self.color,
            weight=self.weight,
            italic=self.italic,
            align=self.align,
            line_spacing=1.22,
            max_width=ceiling,
        )

    def measure(self, theme: Theme) -> BBox:
        return self._block(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._block(theme).render(canvas, x, y, theme)
