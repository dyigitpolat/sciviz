"""Panel: a framed sub-region with tag, title, and header rule."""

from __future__ import annotations

from ..core import BBox, Canvas, Element, Theme


class Panel(Element):
    """A framed sub-region with a small tag and title.

    Paper-style default: 0.5-px border, sharp corners, no filled background,
    compact header. Tag and title share a single line at the top, left-aligned,
    with a thin baseline rule separating them from the content area.

    Example
    -------
    >>> Panel("a", "Weight Matrix", Matrix(...))
    """

    def __init__(self, tag: str, title: str, child: Element, *,
                 min_width: float = 0, min_height: float = 0,
                 rule: bool = True):
        self.tag = self._normalize_tag(tag)
        self.title = title
        self.child = child
        self.min_width = min_width
        self.min_height = min_height
        self.rule = rule

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        t = tag.strip()
        if t.startswith("(") and t.endswith(")"):
            return t
        return f"({t})"

    def _header_h(self, theme: Theme) -> float:
        return theme.text_height(theme.font_panel_title) + theme.unit * 1.4

    def measure(self, theme: Theme) -> BBox:
        pad = theme.panel_padding
        inner = self.child.measure(theme)
        tag_w = theme.text_width(self.tag, "panel", bold=True)
        title_w = theme.text_width(self.title, "panel", bold=False)
        header_w = tag_w + theme.unit * 0.6 + title_w
        content_w = max(inner.w, header_w)
        w = max(content_w + 2 * pad, self.min_width)
        h = max(self._header_h(theme) + inner.h + 2 * pad, self.min_height)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = theme.panel_padding
        canvas.rect(
            x, y, size.w, size.h,
            fill="none",
            stroke=theme.color_of("border"),
            stroke_width=theme.hairline,
            rx=theme.panel_radius,
        )
        header_baseline = y + pad + theme.font_panel_title * 0.85
        canvas.text(
            x + pad, header_baseline, self.tag,
            size=theme.font_panel_tag,
            fill=theme.color_of("text"),
            weight="700",
        )
        tag_w = theme.text_width(self.tag, "panel", bold=True)
        canvas.text(
            x + pad + tag_w + theme.unit * 0.9, header_baseline, self.title,
            size=theme.font_panel_title,
            fill=theme.color_of("text"),
            weight="500",
        )
        if self.rule:
            ry = y + pad + theme.font_panel_title + theme.unit * 0.6
            canvas.line(
                x + pad, ry, x + size.w - pad, ry,
                stroke=theme.color_of("border"),
                stroke_width=theme.hairline,
            )
        inner = self.child.measure(theme)
        content_y = y + pad + self._header_h(theme)
        inner_w = size.w - 2 * pad
        child_x = x + pad + (inner_w - inner.w) / 2
        self.child.render(canvas, child_x, content_y, theme)
