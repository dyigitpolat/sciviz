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
    border : {"single", "double"}
        ``"double"`` draws a second wall inside the first: the conventional
        mark of a *boundary* (a membrane, a cell wall, a trust or process
        boundary) rather than a mere grouping. The content keeps the same
        clearance from the inner wall.
    border_width : float, optional
        Stroke of each wall; the theme hairline when omitted.
    label_style : {"outside", "tab"}
        ``"tab"`` sets the label *on* the top or bottom wall, interrupting
        it (a fieldset legend), so the name sits where the boundary is
        rather than above the box. A tab label may be a string or any
        element (e.g. a :class:`Text` with a bold name and a plain gloss).
    tab_fill : ColorRef or str, optional
        Knockout behind a tab label; the page colour when omitted.
    tab_outline : bool
        Frame the tab in the wall's colour (default), so it reads as a name
        plate mounted on the boundary. ``False`` leaves a plain knockout:
        the label simply interrupts the wall, the way a fieldset legend
        titles the group it frames.
    tabs : mapping, optional
        Tab labels keyed by wall (``"top"``, ``"bottom"``), for a boundary
        that carries a name on both walls -- what it is on one, what it
        does on the other. Each value is a string or an element, or a
        ``(start, end)`` pair that sets one tab at each end of the wall;
        a tab given by ``label`` with ``label_style="tab"`` joins them.
    tab_style : {"plate", "legend"}
        ``"plate"`` (default) mounts a tab on a rounded plate. ``"legend"``
        sets the title on the border line itself, the way a fieldset
        legend titles its group: the wall alone is interrupted under the
        text, with a small pad on each side, and no plate is drawn. The
        outer half of the gap takes the page colour and the inner half
        the region's fill, so a filled region's ground runs on under its
        title.
    tab_inset : float, optional
        A stated position: the distance (px) from the border's outer edge
        to a tab at the start or end of its wall. The automatic inset
        (past the corner arc) when omitted.
    tab_pad : float, optional
        The pad (px) on each side of a tab's label; half a theme unit
        when omitted.
    tab_align : str or mapping, optional
        Where each tab sits along its wall (``"start"``, ``"center"``,
        ``"end"``), one value for all or one per wall; ``label_align``
        when omitted.
    open_side : {"top", "bottom", "left", "right"}, optional
        Leave one wall out: a tray open at the top, a shelf open at the
        bottom. The content runs flush to the open edge (no padding
        there), so a tray's first row lines up with siblings outside it
        -- a group bracket that holds several titled stages without
        pushing their titles below their neighbours'. Single border only.
    grow : bool
        Take the surplus height a stretched parent column offers (the
        ``absorbs_main_axis_stretch`` protocol): the walls extend to the
        column's foot instead of the column opening a gap above or below
        the region, so a band stacked flush under a sibling keeps its
        seam closed and its foot level with a taller neighbour's.
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
                 corner_badge: Optional[Element] = None,
                 border: str = "single",
                 border_width: Optional[float] = None,
                 double_gap: Optional[float] = None,
                 label_style: str = "outside",
                 label_color=None,
                 tab_fill=None,
                 tab_outline: bool = True,
                 tabs=None,
                 tab_align=None,
                 tab_style: str = "plate",
                 tab_inset: Optional[float] = None,
                 tab_pad: Optional[float] = None,
                 open_side: Optional[str] = None,
                 grow: bool = False):
        if grow:
            self.absorbs_main_axis_stretch = True
        if border not in ("single", "double"):
            raise ValueError(
                f"border must be 'single' or 'double'; got {border!r}")
        if label_style not in ("outside", "tab"):
            raise ValueError(
                f"label_style must be 'outside' or 'tab'; got {label_style!r}")
        if label_style == "tab" and label_position not in ("top", "bottom"):
            raise ValueError("a tab label sits on the top or bottom wall; "
                             f"got label_position={label_position!r}")
        if isinstance(label, Element) and label_style != "tab":
            raise TypeError("an element label is supported with "
                            "label_style='tab'; pass a string otherwise")
        if open_side not in (None, "top", "bottom", "left", "right"):
            raise ValueError("open_side must be 'top', 'bottom', 'left' or "
                             f"'right'; got {open_side!r}")
        if open_side is not None and border != "single":
            raise ValueError("an open side needs a single border")
        self.open_side = open_side
        tabs = dict(tabs or {})
        for side in tabs:
            if side not in ("top", "bottom"):
                raise ValueError("tabs sit on the top or bottom wall; "
                                 f"got {side!r}")
        if label and label_style == "tab":
            if label_position in tabs:
                raise ValueError(f"two tabs on the {label_position} wall "
                                 "(label and tabs)")
            tabs[label_position] = label
        if open_side in tabs:
            raise ValueError(f"a tab needs a wall; the {open_side} side "
                             "is open")
        # A pair ``(start, end)`` puts one tab at each end of its wall
        # (a name at one end, a key or a note at the other).
        self._tab_labels = {k: (tuple(v) if isinstance(v, (list, tuple))
                                else v)
                            for k, v in tabs.items() if v}
        for k, v in self._tab_labels.items():
            if isinstance(v, tuple) and len(v) != 2:
                raise ValueError(f"the {k} wall takes one tab or a "
                                 f"(start, end) pair; got {len(v)}")
        self.tab_align = tab_align
        self.border = border
        self.border_width = border_width
        self.double_gap = double_gap
        self.label_style = label_style
        self.label_color = label_color
        self.tab_fill = tab_fill
        self.tab_outline = bool(tab_outline)
        if tab_style not in ("plate", "legend"):
            raise ValueError(
                f"tab_style must be 'plate' or 'legend'; got {tab_style!r}")
        for _name, _v in (("tab_inset", tab_inset), ("tab_pad", tab_pad)):
            if _v is not None and float(_v) < 0.0:
                raise ValueError(f"{_name} must be >= 0; got {_v!r}")
        self.tab_style = tab_style
        self.tab_inset = None if tab_inset is None else float(tab_inset)
        self.tab_pad = None if tab_pad is None else float(tab_pad)
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
        # Width / height floors forwarded to the inner child via
        # ``_apply_inflate``. Used when a parent (Column with
        # ``equal_widths=True``, EqualGrid, AlignedStack, …) wants the
        # Region to fill a larger slot so the bordered area expands
        # together with the content rather than centring narrow content
        # inside an unchanged box.
        self._min_w: float = 0.0
        self._min_h: float = 0.0
        self._inflated_with: tuple[float, float] | None = None

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Record an outer width / height floor.

        The actual propagation to the child runs in ``_apply_inflate``
        (called from ``measure`` / ``render`` once we know the theme),
        so the inner padding and reservations can be subtracted with
        the same arithmetic the renderer uses.
        """
        if min_w > self._min_w:
            self._min_w = float(min_w)
            self._inflated_with = None
        if min_h > self._min_h:
            self._min_h = float(min_h)
            self._inflated_with = None

    def _apply_inflate(self, theme: Theme) -> None:
        """Forward the outer-width/height floor to the child, subtracting
        the same reservations ``measure`` uses to size the border.
        Idempotent until ``inflate_to`` raises the floor again.
        """
        if self._min_w <= 0.0 and self._min_h <= 0.0:
            return
        key = (self._min_w, self._min_h)
        if self._inflated_with == key:
            return
        self._inflated_with = key
        top, bot, left, right, inner_bottom = self._reserve(theme)
        pt, pb, pl, pr = self._pads(theme)
        inner_w = max(0.0, self._min_w - pl - pr - left - right)
        inner_h = max(
            0.0,
            self._min_h - pt - pb - top - bot - inner_bottom
            - self._inner_top(theme),
        )
        self.child.inflate_to(inner_w, inner_h)

    # -- walls and tabs ------------------------------------------------

    def _stroke(self, theme: Theme) -> float:
        return (float(self.border_width) if self.border_width is not None
                else theme.hairline)

    def _wall(self, theme: Theme) -> float:
        """Inset of the inner wall of a double border (0 when single)."""
        if self.border != "double":
            return 0.0
        if self.double_gap is not None:
            return float(self.double_gap)
        return max(self._stroke(theme) * 2.6, theme.hairline * 2.4)

    def _px(self, theme: Theme) -> float:
        return self.pad_x + self._wall(theme)

    def _py(self, theme: Theme) -> float:
        return self.pad_y + self._wall(theme)

    def _pads(self, theme: Theme) -> tuple[float, float, float, float]:
        """Inner clearance ``(top, bottom, left, right)`` between the
        walls and the content; none on an open side."""
        px, py = self._px(theme), self._py(theme)
        open_ = self.open_side
        return (0.0 if open_ == "top" else py,
                0.0 if open_ == "bottom" else py,
                0.0 if open_ == "left" else px,
                0.0 if open_ == "right" else px)

    def _child_offset(self, theme: Theme, child: BBox, border_w: float,
                      border_h: float) -> tuple[float, float]:
        """Child origin relative to the border rectangle: past the
        clearance and any inner tab halves, centred in whatever room an
        inflated or label-widened border leaves."""
        pt, pb, pl, pr = self._pads(theme)
        inner_top = self._inner_top(theme)
        _top, _bot, _l, _r, inner_bottom = self._reserve(theme)
        return (pl + (border_w - pl - pr - child.w) / 2.0,
                pt + inner_top
                + (border_h - pt - pb - inner_top - inner_bottom
                   - child.h) / 2.0)

    def _is_tab(self) -> bool:
        """Whether the author's ``label`` is set as a tab on a wall."""
        return bool(self.label) and self.label_style == "tab"

    def _tab_size(self, theme: Theme, side: Optional[str] = None
                  ) -> tuple[float, float]:
        """Width and height of one tab label's own ink (the ``label``'s
        own wall when ``side`` is omitted); ``(0, 0)`` for a bare wall."""
        label = self._tab_labels.get(side or self.label_position)
        if not label:
            return 0.0, 0.0
        if isinstance(label, tuple):
            # a start tab and an end tab on one wall: their widths, the
            # plates' padding and a clear run of wall between them
            sizes = [self._one_tab_size(theme, one) for one in label]
            gap = 4.0 * self._tab_pad(theme) + 2.0 * theme.unit
            return (sum(w for w, _ in sizes) + gap,
                    max(h for _, h in sizes))
        return self._one_tab_size(theme, label)

    def _one_tab_size(self, theme: Theme, label) -> tuple[float, float]:
        if isinstance(label, Element):
            b = label.measure(theme)
            return b.w, b.h
        if getattr(self, "tab_style", "plate") == "legend":
            # no plate: the title's capitals, centred on the wall, are
            # all that rides above and below it
            return (theme.text_width(label, self.label_size, bold=True),
                    theme.size_px(self.label_size) * 0.76)
        return (theme.text_width(label, self.label_size, bold=True),
                theme.text_height(self.label_size))

    def wall_offsets(self, theme: Theme) -> tuple[float, float]:
        """Distance from the top and from the bottom of the measured box
        to the top and bottom walls: the outside label strip, the half of
        a tab or legend title that rides outside its wall, annotations.
        A sibling inset by these amounts lines up with the walls."""
        top, bot, _left, _right, _inner = self._reserve(theme)
        return top, bot

    def _titled_on_wall(self) -> bool:
        """Whether a legend title rides on a wall of a closed frame: the
        region then reads as a titled card, and a row or column treats
        its walls, not its measured box, as its frame."""
        return (getattr(self, "tab_style", "plate") == "legend"
                and bool(self._tab_labels) and self.open_side is None)

    def frame_bbox(self, theme: Theme):
        """The wall rectangle a row aligns and equalises this region on
        (the ``frame_bbox`` protocol), when its title is set on the
        border line (``tab_style="legend"``); ``None`` otherwise, and the
        region then aligns on its content box as before.

        The half of the title above the wall is neither content nor
        frame. In a row the walls line up with the neighbours' frames and
        take the row's shared height, and the half title rides above
        them, in room a taller neighbour leaves free or in the row's own
        reserve when there is none."""
        if not self._titled_on_wall():
            return None
        b = self.child.measure(theme)
        top, _bot, left, _right, _inner = self._reserve(theme)
        border_w, border_h = self._border_extent(theme, b)
        return (left, top, border_w, border_h)

    def wall_overhang(self, theme: Theme) -> tuple[float, float]:
        """What the measured box holds above the top wall and below the
        bottom wall of a region titled on its border line (the
        ``wall_overhang`` protocol): a column lets it ride in the gap to
        the neighbour on that side instead of adding it to the gap.
        ``(0, 0)`` for every other region."""
        if not self._titled_on_wall():
            return 0.0, 0.0
        return self.wall_offsets(theme)

    def _tab_half(self, theme: Theme, side: str) -> float:
        """Half a tab's height: the part riding on each side of its wall."""
        return self._tab_size(theme, side)[1] / 2.0

    def _tab_alignment(self, side: str) -> str:
        align = self.tab_align
        if isinstance(align, dict):
            align = align.get(side)
        return align or self.label_align

    def _tab_pad(self, theme: Theme) -> float:
        if getattr(self, "tab_pad", None) is not None:
            return self.tab_pad
        return theme.unit * 0.5

    def _inner_top(self, theme: Theme) -> float:
        """Room inside the top wall for the inner half of a top tab (and,
        with ``balance_label_padding``, the mirror of a bottom tab's)."""
        half = self._tab_half(theme, "top")
        if self.balance_label_padding and self._tab_labels:
            half = max(half, self._tab_half(theme, "bottom"))
        return half

    def _label_h(self, theme: Theme) -> float:
        if not self.label:
            return 0.0
        if self._is_tab():
            return self._tab_size(theme)[1] / 2.0
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

        Note that ``left`` / ``right`` here are *outer* reservations for
        side labels/annotations -- the border's inner padding
        (``pad_x``) is added by ``measure``/``render`` directly so the
        border ink always stays inside the measured bbox.
        """
        top = self.margin_y
        bot = self.margin_y
        left = 0.0
        right = self.margin_x
        inner_bottom = 0.0
        lh = self._label_h(theme)
        badge_h = (
            self.corner_badge.measure(theme).h + theme.unit * 0.15
            if self.corner_badge is not None
            else 0.0
        )
        ann = self._anns_by_side()
        # Half of each tab rides outside its wall, half inside it.
        top += self._tab_half(theme, "top")
        bot += self._tab_half(theme, "bottom")
        inner_bottom = self._tab_half(theme, "bottom")
        if self.balance_label_padding and self._tab_labels:
            # The inner half of a title on one wall is mirrored inside
            # the opposite wall: the content keeps even bands above and
            # below it and stands centred between the walls.
            inner_bottom = max(inner_bottom, self._tab_half(theme, "top"))
        if self._is_tab():
            pass
        elif self.label and self.label_position == "top":
            top += lh
            # Optional: pad the inside-bottom by the label height for
            # the historic visually-balanced look. Off by default so
            # paper figures don't carry extra dead whitespace.
            if self.balance_label_padding:
                inner_bottom = max(inner_bottom, lh)
        elif self.label and self.label_position == "bottom":
            bot += lh
        elif self.label and self.label_position == "left":
            left += self._label_w(theme)
        elif self.label and self.label_position == "right":
            right += self._label_w(theme)
        # A corner badge is decoration outside the top border. Reserve its
        # full height (or share the existing label strip) so it never covers
        # the region's child or leaks into the preceding layout row.
        if badge_h:
            if self.label and self.label_position == "top":
                top += max(0.0, badge_h - lh)
            else:
                top += badge_h
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

    def _border_width(self, theme: Theme, child: BBox) -> float:
        """Width that contains child ink and all top/bottom decoration."""
        _pt, _pb, pl, pr = self._pads(theme)
        width = child.w + pl + pr
        for side in self._tab_labels:
            tab_w = self._tab_size(theme, side)[0] + 2 * self._tab_pad(theme)
            reach = max(theme.panel_radius * 1.5, theme.unit * 3.0)
            tab_h = self._tab_size(theme, side)[1]
            width = max(width,
                        tab_w + 2 * self._tab_inset(theme, reach, tab_h))
        if self._is_tab():
            pass
        elif self.label and self.label_position in ("top", "bottom"):
            label_w = theme.text_width(
                self.label, self.label_size, bold=True
            )
            badge_w = (
                self.corner_badge.measure(theme).w + theme.unit * 0.8
                if self.corner_badge is not None
                and self.label_position == "top"
                else 0.0
            )
            width = max(width, label_w + badge_w + 2 * theme.unit)
        annotations = self._anns_by_side()
        for side in ("top", "bottom"):
            if annotations[side]:
                width = max(
                    width,
                    max(theme.text_width(text, "small")
                        for text in annotations[side]) + 2 * theme.unit,
                )
        if self.corner_badge is not None:
            width = max(
                width,
                self.corner_badge.measure(theme).w + 2 * theme.unit,
            )
        return width

    def measure(self, theme: Theme) -> BBox:
        self._apply_inflate(theme)
        b = self.child.measure(theme)
        top, bot, left, right, inner_bottom = self._reserve(theme)
        # The border lives inside the measured bbox on BOTH sides: this
        # keeps the rendered ink contained in the bbox even when Region
        # sits inside a tight Card or Row gap. The historic
        # "encroach into the parent's gap" behaviour was a footgun
        # because the rendered footprint was bigger than the reported
        # extent, so sibling layout could collide with the border.
        pt, pb, _pl, _pr = self._pads(theme)
        w = self._border_width(theme, b) + right + left
        h = (b.h + pt + pb + top + bot + inner_bottom
             + self._inner_top(theme))
        return BBox(max(w, self._min_w), max(h, self._min_h))

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
        top, bot, left, right, inner_bottom = self._reserve(theme)
        border_w, border_h = self._border_extent(theme, b)
        # A label-widened (or inflated) border centres its child rather
        # than leaving an arbitrary empty strip on the right or below.
        dx, dy = self._child_offset(theme, b, border_w, border_h)
        lane_top, lane_bottom = self.flow_lanes(theme)
        return (left + dx, top + dy + lane_top, b.w,
                max(0.0, b.h - lane_top - lane_bottom))

    def port_bbox(self, theme: Theme, side: str):
        """The frame rectangle wires land on (see :meth:`Element.port_bbox`).

        The measured box also holds the outside label, annotations and
        open-edge flow lanes; an arrow into the region should meet the
        drawn frame, not stop short of it at the label's edge.
        """
        b = self.child.measure(theme)
        top, _bot, left, _right, _inner = self._reserve(theme)
        border_w, border_h = self._border_extent(theme, b)
        lane_top, lane_bottom = self.flow_lanes(theme)
        return (left, top + lane_top, border_w,
                max(0.0, border_h - lane_top - lane_bottom))

    def first_baseline(self, theme: Theme):
        """The child's first text baseline below this region's content top.

        The region's content box is its child's footprint (see
        :meth:`content_bbox`), so the label, badge and padding above it
        are not counted: a ``Row(align="baseline")`` of regions lines up
        the text inside them. ``None`` when the child has no baseline.
        """
        from ..layout._baseline import first_baseline
        b = first_baseline(self.child, theme)
        if b is None:
            return None
        lane_top, _lane_bottom = self.flow_lanes(theme)
        return self.child.content_bbox(theme)[1] + b - lane_top

    def flow_lanes(self, theme: Theme) -> tuple[float, float]:
        """Flow-lane margins (top, bottom) at an open edge.

        With a wall there, a wire corridor reserved at the child's edge is
        inside the region: part of what the region holds. At an open edge
        with no clearance, label or margin in between, the child's lane is
        the region's own outer lane -- so a tray of titled stages whose
        titles carry wires keeps those titles level with siblings outside
        it, the way the stages would line up without the tray.
        """
        from ..layout._column import _end_lane
        if self.open_side not in ("top", "bottom"):
            return 0.0, 0.0
        top, bot, _left, _right, inner_bottom = self._reserve(theme)
        if self.open_side == "top" and top <= 0.0 \
                and self._inner_top(theme) <= 0.0:
            return _end_lane(self.child, theme, 0), 0.0
        if self.open_side == "bottom" and bot <= 0.0 and inner_bottom <= 0.0:
            return 0.0, _end_lane(self.child, theme, 1)
        return 0.0, 0.0

    def _border_extent(self, theme: Theme, child: BBox):
        """Border rectangle ``(w, h)``: the content's own need, grown to
        any floor a parent set through :meth:`inflate_to`.

        A child that cannot grow (leaf text) leaves the inflated surplus
        to the Region itself, so a stretched Region's border fills the
        slot its bbox reports instead of hugging the text inside a
        wider, invisible footprint (anchors and wires attach to the
        reported bbox, so the two must coincide).
        """
        top, bot, left, right, inner_bottom = self._reserve(theme)
        w = self._border_width(theme, child)
        pt, pb, _pl, _pr = self._pads(theme)
        h = (child.h + pt + pb + inner_bottom + self._inner_top(theme))
        return (max(w, self._min_w - left - right),
                max(h, self._min_h - top - bot))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._apply_inflate(theme)
        b = self.child.measure(theme)
        top, bot, left, right, inner_bottom = self._reserve(theme)
        col = theme.paint_of(self.color)
        fill_col = theme.paint_of(self.fill) if self.fill is not None else "none"

        # Border ink lives entirely inside the measured bbox now.
        border_x = x + left
        border_w, border_h = self._border_extent(theme, b)
        border_top = y + top
        # Wide grouping surfaces need visibly softened corners at paper
        # scale; the tiny panel-radius token is appropriate for compact
        # boxes but makes broad state/workflow bands look like table cells.
        radius = self._corner_radius(theme, border_w, border_h)
        stroke_w = self._stroke(theme)
        # A lane at an open edge is an outer corridor (see flow_lanes):
        # the walls stop where the content starts, so wires may run in it.
        lane_top, lane_bottom = self.flow_lanes(theme)
        wall_top = border_top + lane_top
        wall_h = max(0.0, border_h - lane_top - lane_bottom)
        if self.open_side is None:
            canvas.rect(
                border_x, border_top, border_w, border_h,
                fill=fill_col, stroke=col,
                stroke_width=stroke_w,
                rx=radius,
                dasharray="4,3" if self.dashed else None,
            )
        else:
            self._render_open_walls(canvas, border_x, wall_top, border_w,
                                    wall_h, radius, fill_col, col, stroke_w)
        wall = self._wall(theme)
        if wall > 0.0:
            canvas.rect(
                border_x + wall, border_top + wall,
                max(0.0, border_w - 2 * wall), max(0.0, border_h - 2 * wall),
                fill="none", stroke=col, stroke_width=stroke_w,
                rx=max(0.0, radius - wall),
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
            reg_top = y + self.margin_y + lane_top
            reg_h = (wall_top + wall_h) - reg_top
            for regmap in stack:
                regmap[key] = (border_x, reg_top, border_w, reg_h)

        for side in self._tab_labels:
            self._render_tab(canvas, border_x, wall_top, border_w,
                             wall_h, theme, col, side)
        if not self._is_tab():
            self._render_label(canvas, border_x, border_top, border_w,
                               border_h, theme, col)
        self._render_annotations(canvas, border_x, wall_top, border_w,
                                  wall_h, theme)
        self._render_corner_badge(canvas, border_x, border_top, border_w,
                                   theme)

        dx, dy = self._child_offset(theme, b, border_w, border_h)
        self.child.render(canvas, border_x + dx, border_top + dy, theme)

    def _render_open_walls(self, canvas: Canvas, x: float, y: float,
                           w: float, h: float, radius: float, fill: str,
                           stroke: str, stroke_w: float) -> None:
        """Fill the region and draw every wall but the open one, rounding
        only the corners the walls close."""
        if fill != "none":
            canvas.rect(x, y, w, h, fill=fill, stroke="none", rx=radius)
        r = max(0.0, min(radius, w / 2.0, h / 2.0))
        # Corners clockwise from top-left; each wall runs corner to corner.
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        walls = {"top": 0, "right": 1, "bottom": 2, "left": 3}
        start = (walls[self.open_side] + 1) % 4   # corner after the gap
        order = [pts[(start + i) % 4] for i in range(4)]

        def toward(a, b, dist):
            ax, ay = a
            bx, by = b
            length = max(1e-9, ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5)
            return ax + (bx - ax) * dist / length, ay + (by - ay) * dist / length

        f = lambda v: f"{v:.3f}"
        d = [f"M {f(order[0][0])} {f(order[0][1])}"]
        for i in (1, 2):
            corner = order[i]
            a = toward(corner, order[i - 1], r)
            b = toward(corner, order[i + 1], r)
            d.append(f"L {f(a[0])} {f(a[1])}")
            d.append(f"Q {f(corner[0])} {f(corner[1])} {f(b[0])} {f(b[1])}")
        d.append(f"L {f(order[3][0])} {f(order[3][1])}")
        canvas.path(" ".join(d), stroke=stroke, stroke_width=stroke_w,
                    dasharray="4,3" if self.dashed else None,
                    ink_bbox=(x - stroke_w / 2, y - stroke_w / 2,
                              x + w + stroke_w / 2, y + h + stroke_w / 2))

    @staticmethod
    def _corner_radius(theme: Theme, border_w: float,
                       border_h: float) -> float:
        """Corner radius of the border (wide bands get softer corners)."""
        radius = theme.panel_radius * 1.5
        if border_w >= border_h * 2.4:
            radius = max(radius, min(theme.unit * 3.0, border_h * 0.13))
        return radius

    def _tab_inset(self, theme: Theme, radius: float,
                   plate_h: float = 0.0) -> float:
        """Distance from the border's outer edge to a tab's plate: the
        plate starts past the corner arc (and the inner wall of a double
        border) by at least half its own height, so a visible run of
        straight wall separates its rounded end from the rounded corner."""
        if getattr(self, "tab_inset", None) is not None:
            return self.tab_inset
        return max(theme.unit * 1.5,
                   radius + self._wall(theme)
                   + max(theme.unit * 0.5, plate_h / 2.0))

    def _render_tab(self, canvas: Canvas, bx: float, by: float,
                    bw: float, bh: float, theme: Theme, col: str,
                    side: str) -> None:
        """A label set on the wall itself, interrupting it."""
        label = self._tab_labels[side]
        if isinstance(label, tuple):
            # (start, end): one tab at each end of the wall
            th = self._tab_size(theme, side)[1]
            for one, align in zip(label, ("start", "end")):
                self._render_one_tab(canvas, bx, by, bw, bh, theme, col,
                                     side, one, align, th)
            return
        self._render_one_tab(canvas, bx, by, bw, bh, theme, col, side,
                             label, self._tab_alignment(side),
                             self._tab_size(theme, side)[1])

    def _render_one_tab(self, canvas: Canvas, bx: float, by: float,
                        bw: float, bh: float, theme: Theme, col: str,
                        side: str, label, align: str,
                        wall_h: float) -> None:
        tw, th = self._one_tab_size(theme, label)
        pad = self._tab_pad(theme)
        inset = self._tab_inset(theme, self._corner_radius(theme, bw, bh),
                                wall_h)
        if align == "center":
            lx = bx + (bw - tw) / 2
        elif align == "end":
            lx = bx + bw - inset - pad - tw
        else:
            lx = bx + inset + pad
        wall_y = by if side == "top" else by + bh
        # The knockout spans both walls of a double border.
        wall = self._wall(theme)
        mid = wall_y + (wall / 2 if side == "top" else -wall / 2)
        knock = theme.paint_of(self.tab_fill) if self.tab_fill is not None \
            else theme.bg
        if getattr(self, "tab_style", "plate") == "legend":
            # A fieldset legend: only the wall is interrupted. The gap's
            # outer half takes the knockout (the page colour by default)
            # and its inner half the region's fill, so the ground of a
            # filled region runs on under its title.
            sw = self._stroke(theme)
            ground = (theme.paint_of(self.fill) if self.fill is not None
                      else knock)
            out_y, in_y = ((wall_y - sw, wall_y) if side == "top"
                           else (wall_y, wall_y - wall - sw))
            canvas.rect(lx - pad, out_y, tw + 2 * pad, sw,
                        fill=knock, stroke="none")
            canvas.rect(lx - pad, in_y, tw + 2 * pad, wall + sw,
                        fill=ground, stroke="none")
            color = (theme.color_of(self.label_color)
                     if self.label_color is not None else col)
            if isinstance(label, Element):
                label.render(canvas, lx, mid - th / 2, theme)
                return
            sz = theme.size_px(self.label_size)
            # The title inks the capitals it reserves (``th``), centred on
            # the wall: the page is not grown for an ascent it never uses.
            canvas.text(lx, mid + sz * 0.33, label, size=sz, fill=color,
                        weight="700", anchor="start",
                        ink_ascent=0.33 + th / (2.0 * sz))
            return
        # A plate in the wall's own colour: the tab reads as a name mounted
        # on the boundary, not as a hole cut into the region's fill.
        canvas.rect(lx - pad, mid - th / 2, tw + 2 * pad, th,
                    fill=knock,
                    stroke=col if self.tab_outline else "none",
                    stroke_width=self._stroke(theme),
                    rx=th / 2)
        color = (theme.color_of(self.label_color)
                 if self.label_color is not None else col)
        if isinstance(label, Element):
            theme.push_bg(knock)
            try:
                label.render(canvas, lx, mid - th / 2, theme)
            finally:
                theme.pop_bg()
            return
        sz = theme.size_px(self.label_size)
        canvas.text(lx, mid + sz * 0.33, label, size=sz, fill=color,
                    weight="700", anchor="start")

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
        badge_y = by - bb.h + theme.hairline * 0.5
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
