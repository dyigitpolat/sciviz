"""Spacer / FixedSize: inert layout primitives."""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme


class Spacer(Element):
    """Invisible element that occupies fixed space."""

    def __init__(self, w: float = 0.0, h: float = 0.0):
        self.w = float(w)
        self.h = float(h)

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.w, self.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        pass


class FixedSize(Element):
    """Force a child into a specific bounding box (useful for alignment)."""

    def __init__(self, child: Element, *, width: Optional[float] = None,
                 height: Optional[float] = None, align: str = "center"):
        self.child = child
        self.width = width
        self.height = height
        self.align = align

    def measure(self, theme: Theme) -> BBox:
        inner = self.child.measure(theme)
        return BBox(self.width if self.width is not None else inner.w,
                    self.height if self.height is not None else inner.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        inner = self.child.measure(theme)
        outer = self.measure(theme)
        if self.align in ("center", "middle"):
            dx = (outer.w - inner.w) / 2
            dy = (outer.h - inner.h) / 2
        elif self.align == "start":
            dx, dy = 0, 0
        elif self.align == "end":
            dx = outer.w - inner.w
            dy = outer.h - inner.h
        else:
            dx = (outer.w - inner.w) / 2
            dy = (outer.h - inner.h) / 2
        self.child.render(canvas, x + dx, y + dy, theme)
