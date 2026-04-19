"""StackedBoxes: a small stack of labeled rectangles drawn front-to-back."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


class StackedBoxes(Element):
    """A stack of ``n`` identical rounded boxes, drawn with a slight offset
    so the stack reads as "this thing repeats ``n`` times".

    Used for visualising a sequence of identical layers (e.g. "Transformer
    Block × L").  The *front* (label-bearing) box sits at the bottom-left;
    subsequent boxes are offset up-and-right, creating a parallax stack.

    Parameters
    ----------
    n : int
        Number of stacked boxes (depth).
    label : str
        Text on the front-most box.
    fill : ColorRef or str
        Fill colour for each box.
    stroke : ColorRef or str, optional
        Stroke colour; defaults to a slight darken of ``fill``.
    width, height : float
        Dimensions of a single box.
    offset : float
        Pixel offset between successive boxes (up-right direction).
    radius : float
        Corner radius.
    text_size, text_weight : theme-size, weight string
        Label typography.
    sub_label : str, optional
        Small italic caption beneath the main label (e.g. precision tag).
    """

    def __init__(self, n: int, label: str, *,
                 fill,
                 stroke = None,
                 stroke_width: Optional[float] = None,
                 width: float = 150.0,
                 height: float = 30.0,
                 offset: float = 4.0,
                 radius: float = 6.0,
                 text_size: str = "small",
                 text_weight: str = "500",
                 sub_label: Optional[str] = None,
                 sub_color = "muted"):
        self.n = max(1, int(n))
        self.label = label
        self.fill = fill
        # Default stroke matches plain :class:`Box` -- the theme's text
        # color -- so a stack in a row with regular boxes reads as a
        # single, consistent visual family (not a differently-bordered
        # sibling).  Authors can still override with an explicit stroke.
        if stroke is not None:
            self.stroke = stroke
        else:
            self.stroke = "text"
        self.stroke_width = stroke_width
        self.width = width
        self.height = height
        self.offset = offset
        self.radius = radius
        self.text_size = text_size
        self.text_weight = text_weight
        self.sub_label = sub_label
        self.sub_color = sub_color

    def measure(self, theme: Theme) -> BBox:
        total = (self.n - 1) * self.offset
        return BBox(self.width + total, self.height + total)

    def _front_face(self) -> Tuple[float, float, float, float]:
        """Position of the FRONT (labeled) box inside the outer silhouette.

        The stack draws ``n`` offset copies; the front box sits at the
        bottom-left of the silhouette at ``(0, total)`` with dimensions
        ``(width, height)``.  This is the box a reader visually "latches
        onto" as the stack's face, so layout primitives should align on
        it rather than on the silhouette centre.
        """
        total = (self.n - 1) * self.offset
        return (0.0, total, self.width, self.height)

    def content_bbox(self, theme: Theme):
        return self._front_face()

    def primary_anchor_bbox(self, theme: Theme):
        return self._front_face()

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        fill_hex = theme.color_of(self.fill)
        stroke_hex = theme.color_of(self.stroke)
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        total = (self.n - 1) * self.offset
        # Each box has a visible border -- the stack reads as N distinct layers
        # (not one blended silhouette).  Back-to-front so the front box sits
        # on top in z-order.
        for i in range(self.n):
            dx = (self.n - 1 - i) * self.offset
            dy = i * self.offset
            canvas.rect(x + dx, y + dy, self.width, self.height,
                       fill=fill_hex, stroke=stroke_hex,
                       stroke_width=sw,
                       rx=self.radius)
        # Label on front box
        sz = theme.size_px(self.text_size)
        label_cx = x + self.width / 2
        label_cy = y + total + self.height / 2
        canvas.text(label_cx, label_cy + sz * 0.33, self.label,
                   size=sz, fill=theme.color_of("text"),
                   weight=self.text_weight, anchor="middle")
        # Optional sub-label (precision tag) on the right of the front box
        if self.sub_label:
            sub_sz = theme.size_px("tiny")
            sub_x = x + self.width - theme.unit
            sub_y = y + total + self.height - sub_sz * 0.3
            canvas.text(sub_x, sub_y, self.sub_label,
                       size=sub_sz, fill=theme.color_of(self.sub_color),
                       weight="normal", italic=True, anchor="end")

