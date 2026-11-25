"""``Blank``: the place of an element without its drawing.

A figure that withholds a value (a value still to be read, drawn in no form) must keep its geometry: every
neighbour of the withheld element stands where it stood with it. ``Blank(element)`` measures as the element,
reports the element's content box, first text baseline, primary anchor and ports, and renders nothing, so a
row that aligns its children on their baselines, a table that sizes its rows on their cells and a connector that
lands on a port all lay out exactly as with the element. Nothing of the element reaches the page: no text, no
stroke, no fill.

``Blank(element, stand_in=other)`` renders ``other`` centred in the element's box instead of nothing (a tag that
stands in for a withheld value at its place), with the element's geometry all the same.

``Blank`` is a new element: no existing element or default changes.
"""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme


class Blank(Element):
    """The measured place of ``element``, empty, or holding ``stand_in`` centred in it."""

    def __init__(self, element: Element, stand_in: Optional[Element] = None):
        if not isinstance(element, Element):
            raise TypeError(f"Blank takes an Element; got {type(element).__name__}")
        if stand_in is not None and not isinstance(stand_in, Element):
            raise TypeError(f"Blank's stand_in is an Element; got {type(stand_in).__name__}")
        self.element = element
        self.stand_in = stand_in

    @property
    def primary_anchor(self):
        return getattr(self.element, "primary_anchor", None)

    def measure(self, theme: Theme) -> BBox:
        return self.element.measure(theme)

    def content_bbox(self, theme: Theme) -> "tuple[float, float, float, float]":
        return self.element.content_bbox(theme)

    def first_baseline(self, theme: Theme) -> Optional[float]:
        from ..layout._baseline import first_baseline
        return first_baseline(self.element, theme)

    def primary_anchor_bbox(self, theme: Theme):
        return self.element.primary_anchor_bbox(theme)

    def port_bbox(self, theme: Theme, side: str):
        return self.element.port_bbox(theme, side)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self.stand_in is None:
            return None
        outer, inner = self.element.measure(theme), self.stand_in.measure(theme)
        self.stand_in.render(canvas, x + (outer.w - inner.w) / 2.0, y + (outer.h - inner.h) / 2.0, theme)
