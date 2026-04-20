"""Box: a labeled rounded rectangle (layer blocks, stages, callouts)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme
from ._obstacles import _register_implicit_obstacle


class Box(Element):
    """A rounded rectangle with optional label text centred inside.

    Good defaults for diagrams of NN layers, pipeline stages, and callout
    cards.  The box will automatically grow to accommodate the label if no
    explicit width/height is given.
    """

    def __init__(self, label: Optional[str] = None, *,
                 width: Optional[float] = None,
                 height: Optional[float] = None,
                 min_width: Optional[float] = None,
                 min_height: Optional[float] = None,
                 fill: str = "none",
                 stroke: str = "text",
                 stroke_width: Optional[float] = None,
                 text_color: str = "auto",
                 text_size: Optional[Union[str, float]] = None,
                 text_weight: Optional[str] = None,
                 radius: Optional[float] = None,
                 sub_label: Optional[str] = None,
                 sub_color: str = "muted",
                 badge: Optional[str] = None,
                 badge_color: str = "muted",
                 dashed: bool = False,
                 opacity: float = 1.0,
                 vertical_text: bool = False,
                 shape_key: Optional[str] = None):
        self.label = label
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.text_color = text_color
        # Smart defaults: vertical-text architecture blocks want bigger,
        # bolder labels by visual convention.  Authors writing
        # ``Box("Attention", vertical_text=True, fill=...)`` shouldn't have
        # to also specify text_size and text_weight every time.
        if text_size is None:
            self.text_size = "title" if vertical_text else "label"
        else:
            self.text_size = text_size
        if text_weight is None:
            self.text_weight = "700" if vertical_text else "500"
        else:
            self.text_weight = text_weight
        self.radius = radius
        self.sub_label = sub_label
        self.sub_color = sub_color
        # ``badge`` is a small chip in the TOP-RIGHT corner, the
        # semantic counterpart to ``sub_label`` (bottom-right). Good
        # for section-number tags like "§2" or version chips like
        # "v2.0" without composing a Row + Spacer by hand.
        self.badge = badge
        self.badge_color = badge_color
        self.dashed = dashed
        self.opacity = opacity
        self.vertical_text = vertical_text
        # ``shape_key`` groups semantically-equivalent boxes (e.g. several
        # RMSNorms in one Row) so a sibling-aware layout container can
        # equalise their heights without the author specifying widths.
        # Default: a tuple of visually-distinguishing fields stringified.
        # Pass ``shape_key=""`` to opt out, or a custom string to force
        # a grouping.
        if shape_key is None:
            # The shape_key must not depend on the label (which might be
            # an opaque Element).  Based on visual-style fields only.
            self.shape_key = (
                f"box::{repr(self.fill)}::{self.text_size}::{int(self.dashed)}"
            )
        else:
            self.shape_key = shape_key

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Lift ``min_width``/``min_height`` so the Box renders at least
        the requested size. Honoured by sibling-aware layouts that want
        every Box in a row/column to render at the same outer dimension.

        For *element* labels (a Column of chips, a Row, ...), the
        inflation is forwarded to the label too, minus the Box's own
        paddings. This makes a Column-of-chips inside a Box grow with
        the Box rather than staying at intrinsic width and being
        centred in empty space -- so chips keep hugging the Box's left
        padding when the panel is stretched to match siblings.
        """
        if min_w and (self.min_width is None or min_w > self.min_width):
            self.min_width = float(min_w)
        if min_h and (self.min_height is None or min_h > self.min_height):
            self.min_height = float(min_h)
        if self._label_is_element():
            # Approximate paddings used by ``_intrinsic``; if a theme is
            # needed for exact values they'll reconcile on first measure.
            # We forward a slightly conservative inner rectangle so the
            # label doesn't over-fill and trigger unwanted reflow.
            self.label.inflate_to(max(0.0, min_w - 12.0),
                                  max(0.0, min_h - 12.0))

    def _label_is_element(self) -> bool:
        """The label can be either a string or any :class:`Element`
        (e.g. :class:`Math`).  Element labels are measured + rendered
        as a unit, centred inside the box."""
        return self.label is not None and isinstance(self.label, Element)

    def _label_lines(self):
        if not self.label or self._label_is_element():
            return []
        return self.label.split("\n")

    # Size token used for bottom-right precision/metadata subscripts.
    # "micro" is smaller than "tiny" so these tags read as a subscript
    # even next to a 9-pt "small" main label.
    _SUB_LABEL_SIZE = "micro"
    # Top-right corner chip: same size family, a hair bolder so it
    # reads as a tag rather than a subscript.
    _BADGE_SIZE = "tiny"

    def _sub_metrics(self, theme: Theme) -> Tuple[float, float]:
        """Width and height of the sub_label when rendered, or (0, 0)."""
        if not self.sub_label:
            return 0.0, 0.0
        sub_w = theme.text_width(self.sub_label, self._SUB_LABEL_SIZE)
        sub_h = theme.text_height(self._SUB_LABEL_SIZE)
        return sub_w, sub_h

    def _badge_metrics(self, theme: Theme) -> Tuple[float, float]:
        if not self.badge:
            return 0.0, 0.0
        bw = theme.text_width(self.badge, self._BADGE_SIZE, bold=True)
        bh = theme.text_height(self._BADGE_SIZE)
        return bw, bh

    def _intrinsic(self, theme: Theme) -> Tuple[float, float]:
        bold = self.text_weight in ("bold", "600", "700")
        lines = self._label_lines()
        line_h = theme.text_height(self.text_size)
        if self._label_is_element():
            # Element label: measure as a single opaque block; the
            # box sizes itself to fit the element plus standard pads.
            eb = self.label.measure(theme)
            label_w = eb.w
            label_h = eb.h
        elif lines:
            label_w = max(theme.text_width(l, self.text_size, bold=bold) for l in lines)
            label_h = line_h * len(lines) + line_h * 0.05 * max(0, len(lines) - 1)
        else:
            label_w = 0.0
            label_h = 0.0
        sub_w, sub_h = self._sub_metrics(theme)
        badge_w, badge_h = self._badge_metrics(theme)
        if self.vertical_text:
            # rotated label: width <-> height swap
            w = label_h + theme.unit * 1.2
            h = max(label_w, sub_w) + theme.unit * 2.0
        else:
            # The sub_label sits in the bottom-right corner as a true
            # subscript tag.  Reserve a dedicated "sub zone" (its width
            # plus a gap) on the right of the main label area so the two
            # never overlap, and a dedicated bottom strip so the main
            # label's bottom is clear of the sub's top.
            sub_gap = theme.unit * 0.6 if self.sub_label else 0.0
            right_pad = theme.unit * 0.8
            left_pad = theme.unit * 0.8
            reserved_bottom = (sub_h + theme.unit * 0.25) if self.sub_label else 0.0
            # Badge (top-right): reserve a top strip and make sure the
            # box is at least wide enough for the badge plus padding.
            reserved_top = (badge_h + theme.unit * 0.3) if self.badge else 0.0
            badge_min_w = (badge_w + left_pad + right_pad) if self.badge else 0.0
            w = max(label_w + sub_gap + sub_w + left_pad + right_pad,
                    badge_min_w)
            h = label_h + reserved_bottom + reserved_top + theme.unit * 0.9
        return max(w, theme.unit * 6), max(h, theme.unit * 3.2)

    def measure(self, theme: Theme) -> BBox:
        w, h = self._intrinsic(theme)
        if self.width is not None:
            w = self.width
        if self.height is not None:
            h = self.height
        if self.min_width is not None and w < self.min_width:
            w = self.min_width
        if self.min_height is not None and h < self.min_height:
            h = self.min_height
        return BBox(w, h)

    def _resolved_text_color(self, theme: Theme) -> str:
        if self.text_color != "auto":
            return theme.color_of(self.text_color)
        fill_hex = theme.color_of(self.fill)
        if fill_hex == "none" or fill_hex.startswith("rgb"):
            return theme.color_of("text")
        return theme.text_on(fill_hex)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        r = self.radius if self.radius is not None else theme.panel_radius
        dasharray = "3,2" if self.dashed else None
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        canvas.rect(
            x, y, size.w, size.h,
            fill=theme.color_of(self.fill),
            stroke=theme.color_of(self.stroke),
            stroke_width=sw,
            rx=r, dasharray=dasharray, opacity=self.opacity,
        )
        _register_implicit_obstacle(x, y, size.w, size.h)
        if self.badge:
            # Top-right corner chip. Same bump-in as sub_label on the
            # bottom so the box feels symmetric.
            bw, bh = self._badge_metrics(theme)
            pad = theme.unit * 0.25
            bsz = theme.size_px(self._BADGE_SIZE)
            canvas.text(
                x + size.w - pad, y + pad + bsz * 0.85, self.badge,
                size=bsz, fill=theme.color_of(self.badge_color),
                weight="700", anchor="end",
            )
        if self._label_is_element():
            # Element label: reserve the sub_label strip at the bottom
            # (if any) and centre the element in the remaining area.
            sub_w, sub_h = self._sub_metrics(theme)
            sub_pad = theme.unit * 0.25
            bottom_reserve = (sub_h + sub_pad) if self.sub_label else 0.0
            _, badge_h = self._badge_metrics(theme)
            top_reserve = (badge_h + sub_pad) if self.badge else 0.0
            eb = self.label.measure(theme)
            region_h = size.h - bottom_reserve - top_reserve
            ex = x + (size.w - eb.w) / 2
            ey = y + top_reserve + max(0.0, (region_h - eb.h) / 2)
            self.label.render(canvas, ex, ey, theme)
            if self.sub_label:
                sub_sz = theme.size_px(self._SUB_LABEL_SIZE)
                sub_baseline = y + size.h - sub_pad - sub_sz * 0.35
                canvas.text(
                    x + size.w - sub_pad, sub_baseline, self.sub_label,
                    size=sub_sz, fill=theme.color_of(self.sub_color),
                    weight="normal", italic=True, anchor="end",
                )
            return
        lines = self._label_lines()
        if not lines:
            return
        text_fill = self._resolved_text_color(theme)
        sz = theme.size_px(self.text_size)
        if self.vertical_text:
            # render text rotated 90 degrees CCW (-90), one or multiple lines
            cx = x + size.w / 2
            cy = y + size.h / 2
            line_h = sz * 1.15
            block_h = line_h * len(lines)
            text_block_w = block_h
            for i, ln in enumerate(lines):
                offset = (i - (len(lines) - 1) / 2) * line_h
                # baseline coordinate computed in rotated frame
                canvas.raw(
                    f'<text x="{cx + offset:.2f}" y="{cy:.2f}" '
                    f'font-size="{sz:.1f}" '
                    f'fill="{text_fill}" '
                    f'font-weight="{self.text_weight}" '
                    f'text-anchor="middle" dominant-baseline="central" '
                    f'transform="rotate(-90 {cx + offset:.2f} {cy:.2f})">'
                    f'{ln}</text>'
                )
        else:
            sub_w, sub_h = self._sub_metrics(theme)
            sub_pad = theme.unit * 0.25
            bottom_reserve = (sub_h + sub_pad) if self.sub_label else 0.0
            _, badge_h = self._badge_metrics(theme)
            top_reserve = (badge_h + sub_pad) if self.badge else 0.0
            line_h = sz * 1.15
            block_h = line_h * len(lines)
            region_h = size.h - bottom_reserve - top_reserve
            block_top = y + top_reserve + max(0.0, (region_h - block_h) / 2)
            for i, ln in enumerate(lines):
                baseline_y = block_top + i * line_h + sz * 0.85
                canvas.text(
                    x + size.w / 2, baseline_y, ln,
                    size=sz, fill=text_fill,
                    weight=self.text_weight, anchor="middle",
                )
            if self.sub_label:
                # Precision/metadata labels sit in the BOTTOM-RIGHT corner,
                # micro italic, acting like a subscript tag on the block.
                # The baseline is placed so the descender stays inside the
                # box: size.h - sub_pad - descender_estimate.
                sub_sz = theme.size_px(self._SUB_LABEL_SIZE)
                sub_baseline = y + size.h - sub_pad - sub_sz * 0.35
                canvas.text(
                    x + size.w - sub_pad, sub_baseline, self.sub_label,
                    size=sub_sz, fill=theme.color_of(self.sub_color),
                    weight="normal", italic=True, anchor="end",
                )


