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

    ``title=`` heads the block with a line of its own::

        Box(title="Rung 4", label="Cycle-accurate simulation",
            wrap=True, max_width=90)

    which is the alternative to folding both into one string
    (``"Rung 4: Cycle-accurate simulation"``), where the wrap decides where
    the name ends and lands it mid-line. To give a column of such blocks one
    shared width, register them with a
    :class:`~sciviz.composition.SizeGroup`.
    """

    # Keep wrapping and intrinsic measurement on one outer-width contract.
    # This is deliberately a theme-relative bearing, not a public per-box
    # layout knob: paper nodes should remain balanced without author tuning.
    _SIDE_PAD_UNITS = 1.2
    _SIZE_FLOORS = {
        "sm": (6.0, 4.0),
        "md": (9.0, 6.0),
        "lg": (13.0, 9.0),
        "xl": (18.0, 13.0),
        "2xl": (22.0, 16.0),
    }

    def __init__(self, label: Optional[str] = None, *,
                 width: Optional[float] = None,
                 height: Optional[float] = None,
                 size: Optional[str] = None,
                 min_width: Optional[float] = None,
                 min_height: Optional[float] = None,
                 fill: str = "none",
                 stroke: str = "text",
                 stroke_width: Optional[float] = None,
                 text_color: str = "auto",
                 text_size: Optional[Union[str, float]] = None,
                 text_weight: Optional[str] = None,
                 radius: Optional[Union[str, float]] = None,
                 title: Optional[str] = None,
                 title_size: Optional[Union[str, float]] = None,
                 title_weight: str = "700",
                 title_color: Optional[str] = None,
                 sub_label: Optional[str] = None,
                 sub_color: str = "muted",
                 badge: Optional[Union[str, Sequence[str]]] = None,
                 badge_color: str = "muted",
                 dashed: bool = False,
                 opacity: float = 1.0,
                 vertical_text: bool = False,
                 aspect: Optional[str] = None,
                 shape_key: Optional[str] = None,
                 wrap: bool = False,
                 max_width: Optional[float] = None):
        self.label = label
        self.width = width
        self.height = height
        if size is not None and size not in self._SIZE_FLOORS:
            allowed = ", ".join(self._SIZE_FLOORS)
            raise ValueError(f"Box.size must be one of {allowed} or None")
        self.semantic_size = size
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
        if isinstance(radius, str) and radius != "pill":
            raise ValueError("Box.radius must be numeric, 'pill', or None")
        self.radius = radius
        # ``title`` HEADS the block: it is drawn on its own line(s) above the
        # label, in its own weight, so "Rung 4" names the block and
        # "Cycle-accurate simulation" is what the block says. Running the two
        # together into one wrapped label makes the name a random prefix of
        # whichever line it lands on. Both halves share the box's wrapping
        # rules, so a titled block still auto-sizes and still honours
        # ``max_width`` / ``wrap``.
        if title is not None and vertical_text:
            raise ValueError(
                "Box(title=...) is not supported with vertical_text=True")
        self.title = title
        self.title_size = title_size
        self.title_weight = title_weight
        self.title_color = title_color
        self.sub_label = sub_label
        self.sub_color = sub_color
        # ``badge`` is a small chip in the TOP-RIGHT corner, the
        # semantic counterpart to ``sub_label`` (bottom-right). Good
        # for section-number tags like "§2" or version chips like
        # "v2.0" without composing a Row + Spacer by hand. A sequence
        # of tags stacks, one per line, so a box tagged with several
        # things stays as wide as its widest TAG rather than as wide as
        # all of them joined -- a single-line run of tags otherwise sets
        # the box's minimum width and, through sibling equalisation,
        # every box beside it.
        self.badge = badge
        self.badge_color = badge_color
        self.dashed = dashed
        self.opacity = opacity
        self.vertical_text = vertical_text
        if aspect not in (None, "square", "portrait", "landscape"):
            raise ValueError(
                "Box.aspect must be square, portrait, landscape, or None"
            )
        self.aspect = aspect
        self.wrap = bool(wrap)
        self.max_width = max_width
        self._wrap_cache = {}
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
                f"::{self.aspect or 'auto'}::{self.semantic_size or 'auto'}"
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

    def _title_size(self) -> Union[str, float]:
        """The title's font size: its own token, or the label's by default."""
        return self.title_size if self.title_size is not None else self.text_size

    def _title_lines(self, theme: Optional[Theme] = None):
        """The title's lines, wrapped on the same budget as the label."""
        if not self.title:
            return []
        return self._wrapped_lines(self.title, self._title_size(),
                                   self.title_weight, theme)

    def _label_lines(self, theme: Optional[Theme] = None):
        if not self.label or self._label_is_element():
            return []
        return self._wrapped_lines(self.label, self.text_size,
                                   self.text_weight, theme)

    def _wrapped_lines(self, text: str, size, weight, theme: Optional[Theme]):
        """Word-wrap one run of the box's text onto the box's own budget.

        Shared by the label and the title so a titled block wraps as one
        object: both halves see the same budget, so neither can silently
        widen the box past the other.
        """
        raw = text.split("\n")
        if not self.wrap or theme is None:
            return raw
        # The default wrap budget is theme-derived
        # (``theme.wrap_budget_px()``), so the cache key must carry the
        # theme's wrap-relevant tokens too -- the same Box is re-measured
        # under derived themes when a Diagram compresses its layout
        # towards ``target_width_pt``.
        # A forced outer width (explicit ``width=`` or an ``inflate_to``
        # raised ``min_width``) widens the wrap budget so the label fills
        # the box it was actually given, so it participates in the key.
        forced_w = self.width if self.width is not None else self.min_width
        key = (text, size, weight, self.max_width,
               forced_w,
               round(theme.unit, 4),
               round(theme.wrap_budget_px(), 4),
               round(theme.size_px(size), 4))
        if key in self._wrap_cache:
            return self._wrap_cache[key]
        bold = weight in ("bold", "600", "700", "800", "900")
        # When a parent has stretched this Box to a wider slot (sibling
        # equalisation, AlignedStack stretch, ...) the label should
        # re-wrap to fill the box's actual inner width instead of
        # staying at the intrinsic budget and leaving the extra width
        # as dead margin around a tall, narrow text column.
        forced_avail = 0.0
        if forced_w:
            sub_w, _ = self._sub_metrics(theme)
            sub_gap = theme.unit * 0.6 if self.sub_label else 0.0
            forced_avail = (float(forced_w)
                            - theme.unit * (2 * self._SIDE_PAD_UNITS)
                            - sub_w - sub_gap)
        out = []
        for line in raw:
            words = line.split(" ")
            if len(words) <= 1:
                out.append(line)
                continue
            longest = max(theme.text_width(w, size, bold=bold) for w in words)
            total = theme.text_width(line, size, bold=bold)
            if self.max_width is not None:
                target = float(self.max_width)
            else:
                target = max(longest, min(total, theme.wrap_budget_px()),
                             min(total, forced_avail))
            cur = ""
            for word in words:
                trial = (cur + " " + word).strip()
                if not cur or theme.text_width(trial, size, bold=bold) <= target:
                    cur = trial
                else:
                    out.append(cur)
                    cur = word
            if cur:
                out.append(cur)
        self._wrap_cache[key] = out
        return out

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

    def _badge_lines(self) -> Tuple[str, ...]:
        """The badge as a tuple of tag lines (empty when there is none)."""
        if not self.badge:
            return ()
        if isinstance(self.badge, str):
            return (self.badge,)
        return tuple(str(tag) for tag in self.badge if str(tag))

    def _badge_metrics(self, theme: Theme) -> Tuple[float, float]:
        lines = self._badge_lines()
        if not lines:
            return 0.0, 0.0
        bw = max(theme.text_width(t, self._BADGE_SIZE, bold=True) for t in lines)
        bh = theme.text_height(self._BADGE_SIZE) * len(lines)
        return bw, bh

    # Air between a title and the body it heads, in theme units. A title is
    # part of the same block, so this is a hair of separation, not a gap
    # wide enough to read as two stacked boxes.
    _TITLE_GAP_UNITS = 0.35

    def _title_metrics(self, theme: Theme, has_body: bool) -> Tuple[float, float, float]:
        """Width, height and trailing gap of the title strip, or zeros."""
        lines = self._title_lines(theme)
        if not lines:
            return 0.0, 0.0, 0.0
        size = self._title_size()
        bold = self.title_weight in ("bold", "600", "700", "800", "900")
        line_h = theme.text_height(size)
        w = max(theme.text_width(l, size, bold=bold) for l in lines)
        h = line_h * len(lines) + line_h * 0.05 * max(0, len(lines) - 1)
        gap = theme.unit * self._TITLE_GAP_UNITS if has_body else 0.0
        return w, h, gap

    def _intrinsic(self, theme: Theme) -> Tuple[float, float]:
        bold = self.text_weight in ("bold", "600", "700")
        lines = self._label_lines(theme)
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
        # The title heads the block, so it widens the box like any other line
        # and adds its own strip to the height.
        title_w, title_h, title_gap = self._title_metrics(
            theme, has_body=label_h > 0.0)
        if title_h:
            label_w = max(label_w, title_w)
            label_h = title_h + title_gap + label_h
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
            # Paper boxes need enough side bearing to survive rasterisation
            # and print reduction.  The old 0.8-unit pad let wide title and
            # monospace labels visually collide with their borders.
            right_pad = theme.unit * self._SIDE_PAD_UNITS
            left_pad = theme.unit * self._SIDE_PAD_UNITS
            reserved_bottom = (sub_h + theme.unit * 0.25) if self.sub_label else 0.0
            # Badge (top-right): reserve a top strip and make sure the
            # box is at least wide enough for the badge plus padding.
            reserved_top = (badge_h + theme.unit * 0.3) if self.badge else 0.0
            badge_min_w = (badge_w + left_pad + right_pad) if self.badge else 0.0
            w = max(label_w + sub_gap + sub_w + left_pad + right_pad,
                    badge_min_w)
            # Paper nodes need enough vertical air to separate their text
            # from the border after column-width reduction.  The historical
            # 0.9-unit allowance made single-line nodes look like UI chips.
            h = label_h + reserved_bottom + reserved_top + theme.unit * 1.35
        w = max(w, theme.unit * 6)
        h = max(h, theme.unit * 4.0)
        landscape_ratio = 2.4
        if self.semantic_size is not None:
            floor_w, floor_h = self._SIZE_FLOORS[self.semantic_size]
            if self.aspect == "landscape":
                # Preserve the established long-axis scale while letting a
                # large landscape stage grow *wider*, not UI-card taller.
                # xl/2xl commonly hold equations or multi-clause workflow
                # stages; their extra semantic size should buy line length.
                landscape_ratio = (
                    3.2 if self.semantic_size in ("xl", "2xl") else 2.4
                )
                long_floor = max(floor_w, floor_h * 2.4)
                w = max(w, theme.unit * long_floor)
                h = max(h, theme.unit * long_floor / landscape_ratio)
            else:
                w = max(w, theme.unit * floor_w)
                h = max(h, theme.unit * floor_h)
        # Semantic silhouettes replace repeated hand-authored width/height
        # pairs. They are floors, so long labels still grow naturally.
        if self.aspect == "square":
            side = max(w, h, theme.unit * 6)
            w = h = side
        elif self.aspect == "portrait":
            w = max(w, theme.unit * 7)
            # A 5:4 card is technically taller than wide but does not read
            # as a deliberate portrait silhouette after paper reduction.
            # Use a clear 3:2 ratio so vertical links, device towers, and
            # state lanes remain recognisably upright without pixel heights.
            h = max(h, w * 1.5, theme.unit * 10.5)
        elif self.aspect == "landscape":
            h = max(h, theme.unit * 5)
            # A semantic landscape stage should read as a workflow bar, not
            # a nearly-square card. Larger tiers become broader rather than
            # taller, using the ratio resolved with their semantic size.
            w = max(w, h * landscape_ratio, theme.unit * 9)
        return w, h

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
        """The label colour, judged against this box's own fill.

        ``"auto"`` picks the theme's dark or light text by contrast with
        the fill; a box without a fill of its own inherits the enclosing
        container's background. An explicit colour is resolved with the
        box's fill pushed as the background context, so the theme's
        white-on-light rescue looks at this box and not at the card it
        sits in: a dark tag inside a pale card body keeps its light label.
        """
        fill_hex = theme.paint_of(self.fill)
        own = isinstance(fill_hex, str) and fill_hex.startswith("#")
        if self.text_color == "auto":
            if own:
                return theme.text_on(fill_hex)
            bg = theme.current_bg()
            return theme.text_on(bg) if bg else theme.color_of("text")
        if not own:
            return theme.color_of(self.text_color)
        theme.push_bg(fill_hex)
        try:
            return theme.color_of(self.text_color)
        finally:
            theme.pop_bg()

    def _render_title(self, canvas: Canvas, x: float, top: float,
                      width: float, theme: Theme) -> None:
        """Draw the title strip whose top edge is ``top``, centred on ``x``."""
        lines = self._title_lines(theme)
        if not lines:
            return
        sz = theme.size_px(self._title_size())
        _, strip_h, _ = self._title_metrics(theme, has_body=False)
        line_h = sz * 1.15
        drawn = line_h * len(lines)
        first = top + max(0.0, (strip_h - drawn) / 2)
        fill = (theme.color_of(self.title_color) if self.title_color
                else self._resolved_text_color(theme))
        for i, ln in enumerate(lines):
            canvas.text(
                x + width / 2, first + i * line_h + sz * 0.85, ln,
                size=sz, fill=fill, weight=self.title_weight, anchor="middle",
            )

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        if self.radius == "pill":
            r = size.h / 2
        else:
            r = self.radius if self.radius is not None else theme.panel_radius
        dasharray = "3,2" if self.dashed else None
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        fill = theme.paint_of(self.fill)
        stroke = theme.paint_of(self.stroke)
        canvas.rect(
            x, y, size.w, size.h,
            fill=fill,
            stroke=stroke,
            stroke_width=sw,
            rx=r, dasharray=dasharray, opacity=self.opacity,
        )
        if fill != "none" or stroke != "none":
            if self._label_is_element():
                # An element-labelled Box is a semantic container: routed
                # anchors may legitimately live inside it. Publish ancestry
                # instead of an uncrossable anonymous obstacle so a relation
                # can enter the container boundary exactly once.
                from ..core._routing_context import register_routing_region
                register_routing_region(self, x, y, size.w, size.h)
            else:
                _register_implicit_obstacle(x, y, size.w, size.h)
        badge_lines = self._badge_lines()
        if badge_lines:
            # Top-right corner chip. Same bump-in as sub_label on the
            # bottom so the box feels symmetric; several tags stack
            # downward from the corner, one line each.
            pad = theme.unit * 0.25
            bsz = theme.size_px(self._BADGE_SIZE)
            line_h = theme.text_height(self._BADGE_SIZE)
            for i, tag in enumerate(badge_lines):
                canvas.text(
                    x + size.w - pad, y + pad + bsz * 0.85 + i * line_h, tag,
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
            title_w, title_h, title_gap = self._title_metrics(
                theme, has_body=True)
            region_h = size.h - bottom_reserve - top_reserve
            block_h = title_h + title_gap + eb.h
            block_top = y + top_reserve + max(0.0, (region_h - block_h) / 2)
            if title_h:
                self._render_title(canvas, x, block_top, size.w, theme)
            ex = x + (size.w - eb.w) / 2
            ey = block_top + title_h + title_gap
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
        lines = self._label_lines(theme)
        if not lines and not self.title:
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
            title_w, title_h, title_gap = self._title_metrics(
                theme, has_body=bool(lines))
            block_h = title_h + title_gap + line_h * len(lines)
            region_h = size.h - bottom_reserve - top_reserve
            block_top = y + top_reserve + max(0.0, (region_h - block_h) / 2)
            if title_h:
                self._render_title(canvas, x, block_top, size.w, theme)
            body_top = block_top + title_h + title_gap
            for i, ln in enumerate(lines):
                baseline_y = body_top + i * line_h + sz * 0.85
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
