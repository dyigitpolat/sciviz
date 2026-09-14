"""Panel: a framed sub-region with tag, title, and header rule."""

from __future__ import annotations

from ..core import BBox, Canvas, Element, Theme
from ..core._routing_context import register_routing_region


class _PanelText(Element):
    """Core-only adapter for legacy string panel headers."""

    def __init__(self, content: str, *, weight: str):
        self.content = content
        self.weight = weight

    def measure(self, theme: Theme) -> BBox:
        return BBox(
            theme.text_width(
                self.content,
                "panel",
                bold=self.weight in ("600", "700", "bold"),
            ),
            theme.text_height("panel"),
        )

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        canvas.text(
            x,
            y + theme.size_px("panel") * 0.85,
            self.content,
            size=theme.size_px("panel"),
            fill=theme.color_of("text"),
            weight=self.weight,
        )


class Panel(Element):
    """A framed sub-region with a small tag and title.

    Paper-style default: 0.5-px border, sharp corners, no filled background,
    compact header. Tag and title share a single line at the top, left-aligned,
    with a thin baseline rule separating them from the content area.

    Example
    -------
    >>> Panel("a", "Weight Matrix", Matrix(...))
    """

    # Framed siblings in a Row share one height (sibling-frame rule).
    frame_sibling = True

    #: Legal ``content_align`` values (see :meth:`__init__`).
    CONTENT_ALIGNS = ("auto", "start", "center", "end")

    def __init__(self, tag: str | Element, title: str | Element,
                 child: Element, *,
                 min_width: float = 0, min_height: float = 0,
                 rule: bool = True,
                 content_align: str = "auto",
                 footer: Element | None = None,
                 footer_gap: str | float = "sm"):
        """``content_align`` places the child in surplus content height
        (a peer-matched panel is taller than its own content).

        ``"auto"`` keeps the structural heuristic: a structural body (a
        Column/Card stack) pins to the content top so its first semantic
        row lines up with a comparative neighbour's, while compact leaf
        visuals centre. Panels holding *independent* diagrams -- where
        row i of one panel means nothing to row i of the other -- want
        an explicit ``"center"``; ``"start"`` / ``"end"`` pin.
        """
        if not isinstance(tag, (str, Element)):
            raise TypeError("Panel.tag must be a string or Element")
        if not isinstance(title, (str, Element)):
            raise TypeError("Panel.title must be a string or Element")
        if content_align not in self.CONTENT_ALIGNS:
            raise ValueError(
                f"Panel content_align must be one of {self.CONTENT_ALIGNS}, "
                f"got {content_align!r}")
        self.tag = self._normalize_tag(tag) if isinstance(tag, str) else tag
        self.title = title
        self.child = child
        self.min_width = min_width
        self.min_height = min_height
        self.rule = rule
        self.content_align = content_align
        if footer is not None and not isinstance(footer, Element):
            raise TypeError("Panel.footer must be an Element or None")
        self.footer = footer
        self.footer_gap = footer_gap

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        t = tag.strip()
        if t.startswith("(") and t.endswith(")"):
            return t
        return f"({t})"

    def _tag_element(self) -> Element:
        if isinstance(self.tag, Element):
            return self.tag
        return _PanelText(self.tag, weight="700")

    def _title_element(self) -> Element:
        if isinstance(self.title, Element):
            return self.title
        return _PanelText(self.title, weight="500")

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Honour a sibling-driven size floor (e.g. ``Row(align="stretch")``):
        grow the panel's outer box; :meth:`render` then centres the child
        vertically in the enlarged content area."""
        if min_w > self.min_width:
            self.min_width = float(min_w)
        if min_h > self.min_height:
            self.min_height = float(min_h)

    def _header_h(self, theme: Theme) -> float:
        tag = self._tag_element().measure(theme)
        title = self._title_element().measure(theme)
        return max(tag.h, title.h) + theme.unit * 1.4

    def measure(self, theme: Theme) -> BBox:
        pad = theme.panel_padding
        inner = self.child.measure(theme)
        footer = self.footer.measure(theme) if self.footer is not None else BBox(0, 0)
        footer_gap = theme.gap_px(self.footer_gap) if self.footer is not None else 0.0
        tag_w = self._tag_element().measure(theme).w
        title_w = self._title_element().measure(theme).w
        header_w = tag_w + theme.unit * 0.9 + title_w
        content_w = max(inner.w, footer.w, header_w)
        w = max(content_w + 2 * pad, self.min_width)
        content_h = inner.h + footer_gap + footer.h
        h = max(self._header_h(theme) + content_h + 2 * pad, self.min_height)
        return BBox(w, h)

    def _content_offset(self, surplus: float, theme: Theme) -> float:
        """Where the child sits in ``surplus`` spare content height."""
        if self.content_align == "start":
            return 0.0
        if self.content_align == "end":
            return surplus
        if self.content_align == "center":
            return surplus / 2
        # "auto": a structural body pins to the content top so its first
        # semantic row aligns with a comparative neighbour's, and
        # centring a short Column would read as a false blank header
        # band. Compact leaf visuals centre.
        structural_body = (
            hasattr(self.child, "children") or hasattr(self.child, "body")
        )
        if structural_body and surplus > theme.unit * 2.0:
            return 0.0
        return surplus / 2

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = theme.panel_padding
        tag = self._tag_element()
        title = self._title_element()
        tag_bb = tag.measure(theme)
        title_bb = title.measure(theme)
        header_content_h = max(tag_bb.h, title_bb.h)
        canvas.rect(
            x, y, size.w, size.h,
            fill="none",
            stroke=theme.color_of("border"),
            stroke_width=theme.hairline,
            rx=theme.panel_radius,
        )
        # Panel is a logical routing boundary, not merely another obstacle:
        # flows whose endpoints live inside may cross its own border, while
        # unrelated wires should route around it.
        register_routing_region(self, x, y, size.w, size.h)
        tag.render(
            canvas,
            x + pad,
            y + pad + (header_content_h - tag_bb.h) / 2,
            theme,
        )
        title.render(
            canvas,
            x + pad + tag_bb.w + theme.unit * 0.9,
            y + pad + (header_content_h - title_bb.h) / 2,
            theme,
        )
        if self.rule:
            ry = y + pad + header_content_h + theme.unit * 0.6
            canvas.line(
                x + pad, ry, x + size.w - pad, ry,
                stroke=theme.color_of("border"),
                stroke_width=theme.hairline,
            )
        inner = self.child.measure(theme)
        footer = self.footer.measure(theme) if self.footer is not None else BBox(0, 0)
        footer_gap = theme.gap_px(self.footer_gap) if self.footer is not None else 0.0
        header_h = self._header_h(theme)
        content_top = y + pad + header_h
        natural_content_h = inner.h + footer_gap + footer.h
        content_area_h = max(
            natural_content_h,
            size.h - 2 * pad - header_h,
        )
        inner_w = size.w - 2 * pad
        child_x = x + pad + (inner_w - inner.w) / 2
        body_area_h = max(inner.h, content_area_h - footer_gap - footer.h)
        surplus = max(0.0, body_area_h - inner.h)
        child_y = content_top + self._content_offset(surplus, theme)
        self.child.render(canvas, child_x, child_y, theme)
        if self.footer is not None:
            footer_x = x + pad + (inner_w - footer.w) / 2
            footer_y = content_top + content_area_h - footer.h
            self.footer.render(canvas, footer_x, footer_y, theme)
