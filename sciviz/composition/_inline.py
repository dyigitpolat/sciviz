"""Inline: baseline-aligned mixed text/math sequence."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text


def _baseline_offset(child: Element, size: BBox, theme: Theme) -> float:
    """Return the visual baseline inside an inline child's measured box.

    Text and math use different renderers and therefore reserve different
    top/bottom safety bands.  Centring their *outer* boxes makes subscripts
    appear to collide with the neighbouring prose even when the measured
    widths are correct.  Keep this policy private to ``Inline``: arbitrary
    miniature elements still align on their optical centre, while text and
    math share a typographic baseline.
    """
    if isinstance(child, Text) and child.rotate not in (90, -90, 270, -270):
        return theme.size_px(child.size) * 0.88

    # Import lazily: the math module intentionally defers matplotlib setup.
    from ..math import Math
    if isinstance(child, Math):
        # Matplotlib mathtext includes a small crop pad in its SVG bbox.
        # Four fifths of that bbox is a stable approximation of its emitted
        # alphabetic baseline across ordinary formulae and sub/superscripts.
        return size.h * 0.80
    return size.h / 2.0

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
        baselines = [
            _baseline_offset(child, size, theme)
            for child, size in zip(kids, sizes)
        ]
        h = max(baselines) + max(
            size.h - baseline for size, baseline in zip(sizes, baselines)
        )
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        kids = self._children()
        if not kids:
            return
        sizes = [c.measure(theme) for c in kids]
        baselines = [
            _baseline_offset(child, size, theme)
            for child, size in zip(kids, sizes)
        ]
        shared_baseline = max(baselines)
        g = theme.gap_px(self.gap)
        cx = x
        for child, sz, baseline in zip(kids, sizes, baselines):
            cy = y + shared_baseline - baseline
            child.render(canvas, cx, cy, theme)
            cx += sz.w + g

