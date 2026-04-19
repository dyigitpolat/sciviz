"""Caption: labeled note attached beneath a diagram."""

from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Caption(Element):
    """Subtle centred caption text."""

    def __init__(self, content: str, *, color: str = "muted"):
        self.content = content
        self.color = color

    def measure(self, theme: Theme) -> BBox:
        w = theme.text_width(self.content, "small", bold=False)
        h = theme.text_height("small")
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px("small")
        bbox = self.measure(theme)
        canvas.text(
            x + bbox.w / 2, y + sz * 0.88, self.content,
            size=sz, fill=theme.color_of(self.color),
            italic=True, anchor="middle",
        )


