"""Column: vertical layout container."""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme


class Column(Element):
    """Vertical container. See :class:`sciviz.layout.Row` for details."""

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center"):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align

    def _visible_children(self):
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        sizes = [c.measure(theme) for c in self.children]
        visible = self._visible_children()
        vis_sizes = [c.measure(theme) for c in visible]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        content_w = max(cb[2] for cb in content)
        max_left = max(cb[0] for cb in content)
        max_right = max(s.w - cb[0] - cb[2] for s, cb in zip(sizes, content))
        w = max(content_w + max_left + max_right, max(s.w for s in sizes))
        n_vis = max(len(visible), 1)
        h = sum(s.h for s in vis_sizes) + g * (n_vis - 1)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        # Give cross-axis stretchers (horizontal separators etc.) the
        # column's full width so they render as full-width rules.
        W = self.measure(theme).w
        for c in self.children:
            if getattr(c, "stretch_main_axis", False) and hasattr(c, "set_stretched_length"):
                c.set_stretched_length(W)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        cy = y
        for child, size, cb in zip(self.children, sizes, content):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_x = cb[0]
            cb_w = cb[2]
            if self.align == "start":
                cx = x - cb_x
            elif self.align == "end":
                cx = x + W - (cb_x + cb_w)
            else:
                col_content_center_x = x + W / 2
                cx = col_content_center_x - (cb_x + cb_w / 2)
            child.render(canvas, cx, cy, theme)
            if not invisible:
                cy += size.h + g
