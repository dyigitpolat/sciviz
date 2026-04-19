"""Group: Row with an automatic brace + label beneath."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text
from ..layout import Row, Column
from ._brace import Brace

class Group(Element):
    """A row of children with an automatic brace + label beneath.

    Replaces the manual three-step pattern::

        chips = Row(*chip_elements)
        brace = Brace(span=measure(chips).w, label=...)
        column = Column(chips, brace)

    Now: ``Group("Visual Tokens", *chips)``.

    The brace span auto-fits the children's combined width.
    """

    def __init__(self, label: str, *children: Element,
                 gap: Union[str, float] = "xs",
                 brace_color = "muted",
                 brace_height: float = 6.0,
                 spacing: float = 4.0):
        self.label = label
        self.children = list(children)
        self.gap = gap
        self.brace_color = brace_color
        self.brace_height = brace_height
        self.spacing = spacing

    def _row(self):
        from ..layout import Row
        return Row(*self.children, gap=self.gap, align="center")

    def measure(self, theme: Theme) -> BBox:
        from ..layout import Column, Spacer
        row = self._row()
        rb = row.measure(theme)
        brace = Brace(rb.w, self.label, direction="down",
                      color=self.brace_color, height=self.brace_height)
        bb = brace.measure(theme)
        return BBox(max(rb.w, bb.w), rb.h + self.spacing + bb.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        from ..layout import Column, Spacer
        row = self._row()
        rb = row.measure(theme)
        size = self.measure(theme)
        # center the row within the outer width
        rx = x + (size.w - rb.w) / 2
        row.render(canvas, rx, y, theme)
        brace = Brace(rb.w, self.label, direction="down",
                      color=self.brace_color, height=self.brace_height)
        brace.render(canvas, rx, y + rb.h + self.spacing, theme)



