"""Region: labeled bordered container with outside label."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

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
                 label_size: str = "label",
                 label_position: str = "top",
                 balance_label_padding: bool = False,
                 annotations: Optional[Sequence] = None,
                 corner_badge: Optional[Element] = None):
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
        # Historic visual-balance padding doubled the label height inside
        # the bottom of the border, which produced very asymmetric
        # whitespace in dense paper figures. Default off; opt in via
        # ``balance_label_padding=True`` for legacy decorative regions.
        self.balance_label_padding = balance_label_padding
        if label_position not in ("top", "left", "right", "bottom"):
            raise ValueError(
                "label_position must be 'top', 'left', 'right', or 'bottom'; "
                f"got {label_position!r}")
        self.label_position = label_position
        self.annotations: List[Tuple[str, str]] = []
        for ann in (annotations or []):
            if isinstance(ann, tuple) and len(ann) == 2 and all(
                    isinstance(x, str) for x in ann):
                side, text = ann
                if side not in ("top", "left", "right", "bottom"):
                    raise ValueError(
                        "annotation side must be top/left/right/bottom; "
                        f"got {side!r}")
                self.annotations.append((side, text))
            else:
                raise TypeError(
                    f"annotation must be (side_str, text_str); got {ann!r}")
        if corner_badge is not None and not isinstance(corner_badge, Element):
            raise TypeError(
                f"corner_badge must be an Element; got {type(corner_badge)}")
        self.corner_badge = corner_badge

    def _label_h(self, theme: Theme) -> float:
        if not self.label:
            return 0.0
        return theme.text_height(self.label_size) + theme.unit * 0.4

    def _ann_h(self, theme: Theme) -> float:
        return theme.text_height("small") + theme.unit * 0.25

    def _label_w(self, theme: Theme) -> float:
        if not self.label:
            return 0.0
        # Side-mounted label: horizontal text; reserve its width plus gap.
        return theme.text_width(self.label, self.label_size, bold=True) \
            + theme.unit * 0.8

    def _anns_by_side(self):
        by_side = {"top": [], "bottom": [], "left": [], "right": []}
        for side, text in self.annotations:
            by_side[side].append(text)
        return by_side

    def _reserve(self, theme: Theme):
        """Per-side outer space needed for label + annotations + margins.

        Returns ``(top, bot, left, right, inner_bottom_pad)``.  The
        ``inner_bottom_pad`` is extra padding inside the border on the
        bottom edge -- preserved for the default ``label_position="top"``
        to keep the historic visually-balanced layout.
        """
        top = self.margin_y
        bot = self.margin_y
        left = 0.0
        right = self.margin_x
        inner_bottom = 0.0
        lh = self._label_h(theme)
        ann = self._anns_by_side()
        if self.label and self.label_position == "top":
            top += lh
            # Optional: pad the inside-bottom by the label height for
            # the historic visually-balanced look. Off by default so
            # paper figures don't carry extra dead whitespace.
            if self.balance_label_padding:
                inner_bottom = lh
        elif self.label and self.label_position == "bottom":
            bot += lh
        elif self.label and self.label_position == "left":
            left += self._label_w(theme)
        elif self.label and self.label_position == "right":
            right += self._label_w(theme)
        ah = self._ann_h(theme)
        top += ah * len(ann["top"])
        bot += ah * len(ann["bottom"])
        if ann["left"]:
            left += max(theme.text_width(t, "small") for t in ann["left"]) \
                + theme.unit * 0.6
        if ann["right"]:
            right += max(theme.text_width(t, "small") for t in ann["right"]) \
                + theme.unit * 0.6
        return top, bot, left, right, inner_bottom

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        top, bot, left, right, inner_bottom = self._reserve(theme)
        w = b.w + self.pad_x + right + left
        h = b.h + 2 * self.pad_y + top + bot + inner_bottom
        return BBox(w, h)

    def content_bbox(self, theme: Theme):
        """Report the child's footprint inside the region.

        Sibling containers (:class:`Row` / :class:`Column`) align on
        ``content_bbox``, so this keeps the decoration (outside label,
        annotations, bottom padding for the label) from pushing the
        child off the shared midline of its peers. A ``Region`` that
        wraps a horizontal pipeline next to a plain LLM box will thus
        center on the pipeline, not on the region's geometric center.
        """
        b = self.child.measure(theme)
        top, _bot, left, _right, _inner_bottom = self._reserve(theme)
        return (left, top + self.pad_y, b.w, b.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b = self.child.measure(theme)
        top, bot, left, right, inner_bottom = self._reserve(theme)
        col = theme.color_of(self.color)
        fill_col = theme.color_of(self.fill) if self.fill is not None else "none"

        left_encroach = self.pad_x if left == 0 else 0.0
        border_x = x + left - left_encroach
        border_w = b.w + left_encroach + self.pad_x
        border_top = y + top
        border_h = b.h + 2 * self.pad_y + inner_bottom
        canvas.rect(
            border_x, border_top, border_w, border_h,
            fill=fill_col, stroke=col,
            stroke_width=theme.hairline,
            rx=theme.panel_radius * 1.5,
            dasharray="4,3" if self.dashed else None,
        )

        # Publish the region's full footprint -- border rectangle PLUS
        # the outer label/annotation strips -- to every active anchor
        # registry under a `__region_<id>` key.  Connector routers
        # consult these keys to avoid crossing through labels.
        stack = _anchor_stack.get()
        if stack is not None:
            key = f"__region_{id(self):x}"
            # Publish the border rectangle plus the top label strip so
            # connectors don't route through the label text.  Matches
            # the historic footprint when label_position defaults.
            reg_top = y + self.margin_y
            reg_h = (border_top + border_h) - reg_top
            for regmap in stack:
                regmap[key] = (border_x, reg_top, border_w, reg_h)

        self._render_label(canvas, border_x, border_top, border_w, border_h,
                           theme, col)
        self._render_annotations(canvas, border_x, border_top, border_w,
                                  border_h, theme)
        self._render_corner_badge(canvas, border_x, border_top, border_w,
                                   theme)

        self.child.render(canvas, x + left, border_top + self.pad_y, theme)

    def _render_label(self, canvas: Canvas, bx: float, by: float,
                       bw: float, bh: float, theme: Theme, col: str) -> None:
        if not self.label:
            return
        sz = theme.size_px(self.label_size)
        pos = self.label_position
        if pos in ("top", "bottom"):
            lbl_w = theme.text_width(self.label, self.label_size, bold=True)
            if self.label_align == "center":
                lx = bx + (bw - lbl_w) / 2
            elif self.label_align == "end":
                lx = bx + bw - theme.unit - lbl_w
            else:
                lx = bx + theme.unit
            if pos == "top":
                # Historic baseline: margin_y + 0.85*sz above the diagram
                # y-origin.  Keep ``by - (lh - 0.85*sz)`` so legacy
                # gallery hashes remain stable.
                ly = by - (self._label_h(theme) - sz * 0.85)
            else:
                ly = by + bh + sz * 0.9
            canvas.text(lx, ly, self.label, size=sz, fill=col,
                        weight="700", anchor="start")
        else:
            mid_y = by + bh / 2 + sz * 0.3
            if pos == "left":
                lx = bx - theme.unit * 0.5
                anchor = "end"
            else:
                lx = bx + bw + theme.unit * 0.5
                anchor = "start"
            canvas.text(lx, mid_y, self.label, size=sz, fill=col,
                        weight="700", anchor=anchor)

    def _render_annotations(self, canvas: Canvas, bx: float, by: float,
                             bw: float, bh: float, theme: Theme) -> None:
        if not self.annotations:
            return
        sz = theme.size_px("small")
        col = theme.color_of("muted")
        ah = self._ann_h(theme)
        by_side = self._anns_by_side()
        # Top -- stack above the border if label doesn't occupy that slot.
        cursor = by - theme.unit * 0.35
        if self.label and self.label_position == "top":
            cursor -= self._label_h(theme)
        for text in reversed(by_side["top"]):
            canvas.text(bx + bw / 2, cursor, text, size=sz, fill=col,
                        anchor="middle", italic=True)
            cursor -= ah
        cursor = by + bh + sz * 0.9
        if self.label and self.label_position == "bottom":
            cursor += self._label_h(theme)
        for text in by_side["bottom"]:
            canvas.text(bx + bw / 2, cursor, text, size=sz, fill=col,
                        anchor="middle", italic=True)
            cursor += ah
        # Left / right -- single-column vertical list.
        for text in by_side["left"]:
            canvas.text(bx - theme.unit * 0.5, by + bh / 2 + sz * 0.3,
                        text, size=sz, fill=col, anchor="end", italic=True)
        for text in by_side["right"]:
            canvas.text(bx + bw + theme.unit * 0.5, by + bh / 2 + sz * 0.3,
                        text, size=sz, fill=col, anchor="start", italic=True)

    def _render_corner_badge(self, canvas: Canvas, bx: float, by: float,
                              bw: float, theme: Theme) -> None:
        if self.corner_badge is None:
            return
        bb = self.corner_badge.measure(theme)
        badge_x = bx + bw - bb.w - theme.unit * 0.4
        badge_y = by - bb.h / 2
        self.corner_badge.render(canvas, badge_x, badge_y, theme)


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


