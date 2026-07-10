"""Repeat: lay out one semantic element as a connected repeated chain."""

from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Repeat(Element):
    """Repeat an element along a row or column with automatic connectors.

    ``Repeat`` expresses sequential repetition; :class:`StackedTiles`
    expresses an overlapping deck.  The distinction matters in scientific
    figures because a chain communicates information flow while a deck only
    communicates multiplicity.

    Parameters
    ----------
    item:
        The repeated semantic element. It is rendered ``count`` times.
    count:
        Number of visible occurrences.
    axis:
        ``"vertical"`` or ``"horizontal"``.
    direction:
        Optional connector direction (``"up"``, ``"down"``, ``"left"``,
        or ``"right"``). ``None`` leaves occurrences unconnected.
    gap:
        Semantic spacing between occurrences and connectors.
    """

    absorbs_main_axis_stretch = True

    def __init__(self, item: Element, *, count: int,
                 axis: str = "vertical",
                 direction: Optional[str] = None,
                 gap: Union[str, float] = "xs"):
        if not isinstance(item, Element):
            raise TypeError(f"Repeat.item must be an Element; got {type(item)}")
        if count < 1:
            raise ValueError("Repeat.count must be at least 1")
        if axis not in ("vertical", "horizontal"):
            raise ValueError("Repeat.axis must be vertical or horizontal")
        valid_directions = (None, "up", "down", "left", "right")
        if direction not in valid_directions:
            raise ValueError(
                "Repeat.direction must be up/down/left/right or None"
            )
        if direction in ("up", "down") and axis != "vertical":
            raise ValueError("up/down repetition requires axis='vertical'")
        if direction in ("left", "right") and axis != "horizontal":
            raise ValueError("left/right repetition requires axis='horizontal'")
        self.item = item
        self.count = int(count)
        self.axis = axis
        self.direction = direction
        self.gap = gap
        self._min_w = 0.0
        self._min_h = 0.0

    def _layout(self):
        from ..connect import Connect
        from ..layout import Column, Row

        children = []
        for index in range(self.count):
            children.append(self.item)
            if self.direction is not None and index < self.count - 1:
                children.append(Connect(direction=self.direction))
        if self.axis == "vertical":
            layout = Column(
                *children, gap=self.gap, align="center", equal_widths=True
            )
        else:
            layout = Row(
                *children, gap=self.gap, align="center", equal_widths=True
            )
        layout.inflate_to(self._min_w, self._min_h)
        return layout

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def measure(self, theme: Theme) -> BBox:
        return self._layout().measure(theme)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        self._layout().render(canvas, x, y, theme)

    def content_bbox(self, theme: Theme):
        return self._layout().content_bbox(theme)

    def primary_anchor_bbox(self, theme: Theme):
        return self._layout().primary_anchor_bbox(theme)
