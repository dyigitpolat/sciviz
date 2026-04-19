"""Inline: baseline-aligned mixed text/math sequence."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text

class Inline(Element):
    """Lay out a sequence of text, math and small elements on a shared baseline.

    Replaces the ``Row(Text(...), Spacer(4, 0), Math(...), Spacer(4, 0), ...)``
    boilerplate with a single declarative call.  String children become
    :class:`Text` automatically; ``$...$`` strings become :class:`Math`.

    Parameters
    ----------
    *parts : Element or str
        Sequence to lay out.  Strings beginning and ending with ``$`` become
        :class:`Math`; other strings become :class:`Text`.
    size : str or float
        Default text/math size for string children.
    color : str
        Default text colour.
    weight : str
        Default text weight for string children.
    gap : str or float
        Whitespace between successive children (default ``"sm"`` ~ a wordspace).
    """

    def __init__(self, *parts, size="label", color="text",
                 weight="normal", gap="sm"):
        self.parts = list(parts)
        self.size = size
        self.color = color
        self.weight = weight
        self.gap = gap

    def _coerce(self, p):
        if isinstance(p, Element):
            return p
        if isinstance(p, str):
            s = p.strip()
            if len(s) >= 2 and s.startswith("$") and s.endswith("$"):
                from ..math import Math
                return Math(s, size=self.size, color=self.color)
            return Text(p, size=self.size, color=self.color, weight=self.weight)
        raise TypeError(f"Inline parts must be Element or str; got {type(p)}")

    def _children(self):
        return [self._coerce(p) for p in self.parts]

    def measure(self, theme: Theme) -> BBox:
        kids = self._children()
        if not kids:
            return BBox(0, 0)
        sizes = [c.measure(theme) for c in kids]
        g = theme.gap_px(self.gap)
        w = sum(s.w for s in sizes) + g * (len(sizes) - 1)
        h = max(s.h for s in sizes)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        kids = self._children()
        if not kids:
            return
        sizes = [c.measure(theme) for c in kids]
        H = max(s.h for s in sizes)
        g = theme.gap_px(self.gap)
        cx = x
        for child, sz in zip(kids, sizes):
            cy = y + (H - sz.h) / 2
            child.render(canvas, cx, cy, theme)
            cx += sz.w + g


