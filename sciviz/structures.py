"""High-level structural primitives.

Titled container blocks that absorb common manual work the author would
otherwise do with ``Spacer`` and ad-hoc ``Row``/``Column`` arithmetic:

* :class:`Section`    -- titled block with auto rule + spacing.
* :class:`BlockGroup` -- rounded grouping box with optional caption.
"""

from __future__ import annotations

from typing import Optional, Union

from .core import Element, BBox, Canvas, Theme
from .elements import Text, Box


# ---------------------------------------------------------------------------
# Section -- titled block with rule and auto-spacing
# ---------------------------------------------------------------------------

class Section(Element):
    """A titled block of content.

    Renders as:
        Title (optional kicker)
        ---------- (rule)
        body
        (caption)

    Spacing between title, rule, body, and caption is consistent and tuned
    by the theme.  Authors don't insert Spacers manually.

    Parameters
    ----------
    title : str
        Section title.
    body : Element
        The content.
    kicker : str, optional
        Small uppercase label above the title (like a tag).
    caption : str, optional
        Italic caption below the body.
    rule : bool
        Draw a hairline rule between title and body.  Default ``True``.
    align : str
        ``"start"`` (default), ``"center"``, ``"end"`` -- horizontal alignment
        of the title/caption relative to the body's measured width.
    """

    def __init__(self, title: str, body: Element, *,
                 kicker: Optional[str] = None,
                 caption: Optional[str] = None,
                 rule: bool = True,
                 align: str = "start"):
        self.title = title
        self.body = body
        self.kicker = kicker
        self.caption = caption
        self.rule = rule
        self.align = align

    # -------- internal layout helpers --------

    def _kicker_h(self, theme):
        return theme.text_height("tiny") + theme.unit * 0.4 if self.kicker else 0.0

    def _title_h(self, theme):
        return theme.text_height("section") + theme.unit * 0.6

    def _rule_h(self, theme):
        return theme.unit * 0.6 if self.rule else 0.0

    def _caption_h(self, theme):
        return theme.text_height("small") + theme.unit * 0.5 if self.caption else 0.0

    def measure(self, theme: Theme) -> BBox:
        b = self.body.measure(theme)
        title_w = theme.text_width(self.title, "section", bold=True)
        kicker_w = theme.text_width(self.kicker, "tiny", bold=True) if self.kicker else 0
        cap_w = theme.text_width(self.caption, "small") if self.caption else 0
        w = max(b.w, title_w, kicker_w, cap_w)
        h = (self._kicker_h(theme) + self._title_h(theme) + self._rule_h(theme)
             + b.h + self._caption_h(theme))
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        cur_y = y

        # kicker
        if self.kicker:
            canvas.text(x, cur_y + theme.size_px("tiny") * 0.85,
                       self.kicker.upper(),
                       size=theme.size_px("tiny"),
                       fill=theme.color_of("muted"),
                       weight="700", anchor="start")
            cur_y += self._kicker_h(theme)

        # title
        canvas.text(x, cur_y + theme.size_px("section") * 0.85,
                   self.title,
                   size=theme.size_px("section"),
                   fill=theme.color_of("text"),
                   weight="700", anchor="start")
        cur_y += theme.text_height("section")

        # rule
        if self.rule:
            cur_y += theme.unit * 0.3
            canvas.line(x, cur_y, x + size.w, cur_y,
                       stroke=theme.color_of("border"),
                       stroke_width=theme.hairline)
            cur_y += theme.unit * 0.3

        # body (centred horizontally if requested)
        b = self.body.measure(theme)
        if self.align == "center":
            bx = x + (size.w - b.w) / 2
        elif self.align == "end":
            bx = x + (size.w - b.w)
        else:
            bx = x
        self.body.render(canvas, bx, cur_y, theme)
        cur_y += b.h

        # caption
        if self.caption:
            cur_y += theme.unit * 0.5
            cap_baseline = cur_y + theme.size_px("small") * 0.85
            cap_x = x
            if self.align == "center":
                cap_x = x + size.w / 2
                anchor = "middle"
            elif self.align == "end":
                cap_x = x + size.w
                anchor = "end"
            else:
                anchor = "start"
            canvas.text(cap_x, cap_baseline, self.caption,
                       size=theme.size_px("small"),
                       fill=theme.color_of("text_muted"),
                       italic=True, anchor=anchor)


# ---------------------------------------------------------------------------
# BlockGroup -- rounded "phase" container
# ---------------------------------------------------------------------------

class BlockGroup(Element):
    """A rounded box that visually groups its child with an optional label.

    Useful for "phase 1 / phase 2" groupings, "frozen / trainable" partitions,
    and other implicit-region indicators.

    Parameters
    ----------
    child : Element
        Content rendered inside.
    label : str, optional
        Header label drawn on the top edge.
    color : ColorRef or str
        Stroke colour for the border (and label, if shown).
    fill : ColorRef or str, optional
        Background fill behind the child.  Default ``None`` = transparent.
    dashed : bool
        Stroke style: dashed (default) or solid.
    padding : str or float
        Inset between border and child.
    label_align : str
        ``"start"`` (default), ``"center"``, ``"end"``.
    """

    def __init__(self, child: Element, *,
                 label: Optional[str] = None,
                 color = "muted",
                 fill = None,
                 dashed: bool = True,
                 padding: Union[str, float] = "md",
                 label_align: str = "start",
                 label_size: str = "small"):
        self.child = child
        self.label = label
        self.color = color
        self.fill = fill
        self.dashed = dashed
        self.padding = padding
        self.label_align = label_align
        self.label_size = label_size

    def _pad(self, theme):
        return theme.gap_px(self.padding) if isinstance(self.padding, str) else float(self.padding)

    def _label_h(self, theme):
        return theme.text_height(self.label_size) + theme.unit * 0.4 if self.label else 0.0

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        p = self._pad(theme)
        lbl_w = (theme.text_width(self.label, self.label_size, bold=True)
                 + theme.unit * 1.2) if self.label else 0
        w = max(b.w + 2 * p, lbl_w + 2 * p)
        h = b.h + 2 * p + self._label_h(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        p = self._pad(theme)
        lbl_h = self._label_h(theme)
        col = theme.color_of(self.color)
        fill_col = theme.color_of(self.fill) if self.fill is not None else "none"
        border_x = x
        border_y = y + lbl_h
        border_w = size.w
        border_h = size.h - lbl_h
        canvas.rect(
            border_x, border_y, border_w, border_h,
            fill=fill_col, stroke=col,
            stroke_width=theme.hairline,
            rx=theme.panel_radius * 1.5,
            dasharray="4,3" if self.dashed else None,
        )

        # Publish the border rectangle to every active anchor registry
        # under a `__region_<id>` key so connector routers can detect
        # required / forbidden boundary crossings.
        from .composition import _anchor_stack
        stack = _anchor_stack.get()
        if stack is not None:
            key = f"__region_{id(self):x}"
            for reg in stack:
                reg[key] = (border_x, border_y, border_w, border_h)

        if self.label:
            lbl_w = theme.text_width(self.label, self.label_size, bold=True)
            if self.label_align == "center":
                lx = x + (size.w - lbl_w) / 2
                anchor = "start"
            elif self.label_align == "end":
                lx = x + size.w - theme.unit - lbl_w
                anchor = "start"
            else:
                lx = x + theme.unit
                anchor = "start"
            # Label sits transparently on top of whatever is underneath.
            canvas.text(lx, y + theme.size_px(self.label_size) * 0.85, self.label,
                       size=theme.size_px(self.label_size),
                       fill=col, weight="700", anchor=anchor)
        b = self.child.measure(theme)
        cx = x + (size.w - b.w) / 2
        self.child.render(canvas, cx, y + lbl_h + p, theme)


