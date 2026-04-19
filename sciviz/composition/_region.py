"""Region: labeled bordered container with outside label."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text
from ._anchor import Anchor, _anchor_stack

class Region(Element):
    """A labeled bordered container with proper inside padding and outside label.

    Resolves three competing needs simultaneously:

    1. **Label sits above the border** (outside), like the original overlay --
       authors don't want the label visually inside the bordered box.

    2. **Inner padding on every side** -- children have visible breathing
       room from the border line.

    3. **Horizontal alignment with non-Region siblings is preserved.**
       The child inside Region stays flush with Region's bbox left edge;
       the border extends *leftward into the parent's gap* between Region
       and its preceding sibling.  This works because containers always
       reserve gap space between children anyway.  No other layout tricks
       required.

    The bbox is ``(child_w + pad_x, child_h + label_h + 2*pad_y)``.
    The *rendered* border spans ``(x - pad_x, y + label_h)`` to
    ``(x + child_w + pad_x, y + bbox_h)`` -- wider than the bbox by
    ``pad_x`` on the left, encroaching into the parent gap.

    Parameters
    ----------
    child : Element
        Content inside the region.
    label : str, optional
        Header text drawn above the top border.
    color : ColorRef or str
        Border and label colour.
    fill : ColorRef or str, optional
        Background tint behind the child.
    dashed : bool
        Border style.
    pad_x : float
        Horizontal padding (both sides; left side extends into parent gap).
    pad_y : float
        Vertical padding inside the border (top and bottom).
    label_align : str
        ``"start"`` (default), ``"center"``, or ``"end"``.
    label_size : str
        Theme size token for the label.
    """

    def __init__(self, child: Element, *,
                 label: Optional[str] = None,
                 color = "muted",
                 fill = None,
                 dashed: bool = True,
                 pad_x: float = 8.0,
                 pad_y: float = 5.0,
                 margin_x: float = 6.0,
                 margin_y: float = 6.0,
                 label_align: str = "start",
                 label_size: str = "label"):
        self.child = child
        self.label = label
        self.color = color
        self.fill = fill
        self.dashed = dashed
        self.pad_x = pad_x
        self.pad_y = pad_y
        # Outer margins: reserved space between Region's border and
        # neighbouring content.  margin_x adds to the bbox on the right only
        # (so the child stays flush-left for sibling alignment).  margin_y
        # is symmetric top/bottom.
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.label_align = label_align
        self.label_size = label_size

    def _label_h(self, theme: Theme) -> float:
        if not self.label:
            return 0.0
        return theme.text_height(self.label_size) + theme.unit * 0.4

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        lh = self._label_h(theme)
        # Horizontal: child + right-inner-pad + right-outer-margin
        # (left inner pad extends into parent gap; no left outer margin
        # so sibling alignment is preserved)
        w = b.w + self.pad_x + self.margin_x
        # Vertical: lh (label above border) + top_pad + child + bot_pad
        # where bot_pad = lh + pad_y to keep child at bbox vertical centre
        # (balances the label above the border).  Plus margin on each side.
        h = b.h + 2 * lh + 2 * self.pad_y + 2 * self.margin_y
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b = self.child.measure(theme)
        lh = self._label_h(theme)
        size = self.measure(theme)
        col = theme.color_of(self.color)
        fill_col = theme.color_of(self.fill) if self.fill is not None else "none"

        # Border top: below the label-h area and below the top margin_y
        border_x = x - self.pad_x
        border_w = b.w + 2 * self.pad_x
        border_top = y + self.margin_y + lh
        # Border height: pad_y + child + pad_y + lh  (lh extra at bottom
        # balances the label space above).
        border_h = b.h + 2 * self.pad_y + lh
        canvas.rect(
            border_x, border_top, border_w, border_h,
            fill=fill_col, stroke=col,
            stroke_width=theme.hairline,
            rx=theme.panel_radius * 1.5,
            dasharray="4,3" if self.dashed else None,
        )

        # Publish the region's full footprint -- border rectangle PLUS
        # the label strip above it -- to every active anchor registry
        # under a `__region_<id>` key.  Connector routers consult these
        # keys to compute required / forbidden boundary crossings, and
        # including the label strip here prevents connectors from
        # crossing THROUGH the label text on their way in or out.
        stack = _anchor_stack.get()
        if stack is not None:
            key = f"__region_{id(self):x}"
            region_top = y + self.margin_y  # includes the label strip
            region_h = (border_top + border_h) - region_top
            for reg in stack:
                reg[key] = (border_x, region_top, border_w, region_h)

        # Label in the lh space above the border (and below top margin_y).
        if self.label:
            lbl_w = theme.text_width(self.label, self.label_size, bold=True)
            if self.label_align == "center":
                lx = border_x + (border_w - lbl_w) / 2
            elif self.label_align == "end":
                lx = border_x + border_w - theme.unit - lbl_w
            else:
                lx = border_x + theme.unit
            canvas.text(lx,
                       y + self.margin_y + theme.size_px(self.label_size) * 0.85,
                       self.label, size=theme.size_px(self.label_size),
                       fill=col, weight="700", anchor="start")

        # Child: flush at bbox left (x), inside border with pad_y above it.
        self.child.render(canvas, x, border_top + self.pad_y, theme)


# ---------------------------------------------------------------------------
# Bus -- multi-source / multi-sink connector.
#
# Covers the "one-to-many" and "shared-by-all" cases that a pairwise Flow
# can only approximate.  Three common shapes:
#
#   1. Shared horizontal bus: all endpoints are roughly co-linear at
#      similar y -- draw a single horizontal line connecting them at
#      that y, with short taps down into each.
#
#   2. Fan-out tree: one source, many sinks -- a stem from the source
#      meets a horizontal spine; each sink is tapped off the spine.
#
#   3. Fan-in tree: many sources, one sink -- mirror of fan-out.
#
# The author writes only endpoint names; the library picks the shape.
# ---------------------------------------------------------------------------


