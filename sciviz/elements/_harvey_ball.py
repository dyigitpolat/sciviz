"""Fractional-coverage disc glyphs (Harvey balls)."""

from __future__ import annotations

import math
from typing import Union

from ..core import BBox, Canvas, Element, Theme


class HarveyBall(Element):
    """A fraction-filled disc for categorical coverage / completion states.

    The classic comparison-table glyph: a thin ring whose interior is
    filled by a clockwise pie wedge that starts at twelve o'clock and
    covers ``fraction`` of the disc.  ``0.0`` reads as a quiet hollow
    ring (absent), ``0.5`` as half coverage (partial, by proxy), and
    ``1.0`` as a solid disc (full coverage).  Any fraction in ``[0, 1]``
    is valid, so quarter or three-quarter states need no special casing.

    ``color`` paints the wedge; ``ring`` (default: ``color``) paints the
    outline, so an empty state can carry a muted ring while filled states
    keep a semantic hue.  Size accepts a theme token (``"tiny"``,
    ``"small"``, ...) like :class:`ConditionGlyph`, or explicit pixels.
    """

    def __init__(self, fraction: float, *, size: Union[str, float] = "tiny",
                 color="muted", ring=None, stroke_width: float = 1.2):
        try:
            fraction = float(fraction)
        except (TypeError, ValueError) as exc:
            raise ValueError("HarveyBall.fraction must be a number") from exc
        if not math.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
            raise ValueError("HarveyBall.fraction must lie in [0, 1]")
        self.fraction = fraction
        self.size = size
        self.color = color
        self.ring = ring if ring is not None else color
        self.stroke_width = float(stroke_width)

    def _size_px(self, theme: Theme) -> float:
        if isinstance(self.size, (int, float)):
            return float(self.size)
        return theme.size_px(self.size) * 1.35

    def measure(self, theme: Theme) -> BBox:
        s = self._size_px(theme)
        return BBox(s, s)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        s = self._size_px(theme)
        sw = self.stroke_width
        cx, cy = x + s / 2, y + s / 2
        r = (s - sw) / 2
        fill = theme.color_of(self.color)
        ring = theme.color_of(self.ring)

        # A wedge whose endpoint nearly coincides with its start point
        # degenerates in SVG arc space, so treat near-full as solid.
        if self.fraction >= 1.0 - 1e-6:
            canvas.circle(cx, cy, r, fill=fill, stroke="none")
        elif self.fraction > 1e-6:
            theta = self.fraction * 2.0 * math.pi
            ex = cx + r * math.sin(theta)
            ey = cy - r * math.cos(theta)
            large = 1 if self.fraction > 0.5 else 0
            canvas.path(
                f"M {cx:.3f} {cy:.3f} L {cx:.3f} {cy - r:.3f} "
                f"A {r:.3f} {r:.3f} 0 {large} 1 {ex:.3f} {ey:.3f} Z",
                fill=fill,
                ink_bbox=(cx - r, cy - r, cx + r, cy + r),
            )
        canvas.circle(cx, cy, r, fill="none", stroke=ring, stroke_width=sw)
