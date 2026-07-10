"""Row: horizontal layout container.

A Row measures every child, arranges them left-to-right with automatic
spacing, and reports a bounding box that contains all of them. See
:class:`Column` for the vertical analogue.
"""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme


class Row(Element):
    """Horizontal container.

    Parameters
    ----------
    *children : Element
        The child elements, laid out left-to-right. ``None`` children are
        silently dropped, which is handy for optional pieces.
    gap : str or float
        Spacing between children. Semantic tokens (``"xs"``, ``"sm"``,
        ``"md"``, ``"lg"``, ``"xl"``, ``"2xl"``) are resolved against the
        theme's base unit.
    align : str
        Cross-axis (vertical) placement of children: ``"start"``,
        ``"center"``, ``"end"``, or ``"stretch"``. ``"stretch"`` first
        inflates every child to the tallest child's height (via
        ``inflate_to``) so side-by-side siblings -- e.g. two ``Panel``\\ s
        -- share one outer height, then top-aligns them; leaf children
        that cannot grow vertically are left at their natural height.
    equal_widths : bool
        If True, every child gets the same horizontal slot (the max child
        width). Critical for visually aligning columns of differing-width
        labels (e.g. tokens, bars, pictograms). Each child is centered
        within its slot.
    balance_outer : bool
        For a three-part bilateral composition, reserve equal-width slots
        for the first and third visible children and keep the middle child
        on the exact row centreline.  The outer children pack inward, so an
        unequal legend/system pair does not push the semantic centre off
        axis.  Layout-invisible children such as ``Connect`` are ignored.
    """

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center", equal_widths: bool = False,
                 balance_outer: bool = False):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align
        self.equal_widths = equal_widths
        self.balance_outer = bool(balance_outer)
        if self.balance_outer and self.equal_widths:
            raise ValueError(
                "balance_outer and equal_widths are alternative Row slot "
                "contracts; choose one"
            )
        self._shape_normalized = False
        # Tracks whether ``_maybe_equalise_widths`` has already fired for
        # this Row so we never inflate twice (which would compound the
        # widths and make later measures drift).
        self._equalised = False
        # Optional row-width floor set by ``inflate_to`` so the Row
        # rendered width can grow to match a sibling slot width.
        self._min_width: float = 0.0
        # Cross-axis floor set when a parent stretches this nested Row.
        self._min_height: float = 0.0
        # Per-child widths forced by a containing AlignedStack. When set,
        # each visible child occupies at least ``forced_slot_w[i]`` px.
        self._forced_slot_w: List[float] | None = None
        # Whether align="stretch" has broadcast the tallest height to children.
        self._stretched = False

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Grow the Row's outer width when a parent (Card / Region /
        AlignedStack) inflates a sibling to a larger slot. The width
        floor is honoured by ``measure`` and propagated to children via
        ``_maybe_equalise_widths`` when ``equal_widths=True``.

        A height floor is forwarded to structural Column children while
        compact accessories remain centred in the taller row.
        """
        if min_w > self._min_width:
            self._min_width = float(min_w)
            self._equalised = False
        if min_h > self._min_height:
            self._min_height = float(min_h)
            self._stretched = False

    def _apply_height_floor(self, theme: Theme) -> None:
        if self._min_height <= 0.0:
            return
        natural = max(
            (child.measure(theme).h for child in self._visible_children()),
            default=0.0,
        )
        if natural >= self._min_height - 0.5:
            return
        absorbers = [
            child for child in self._visible_children()
            if getattr(child, "absorbs_cross_axis_stretch", False)
        ]
        for child in absorbers:
            child.inflate_to(0.0, self._min_height)

    @staticmethod
    def _find_shape_peer(elem):
        """Unwrap wrappers (``Anchor``, ``Banner``, ``Captioned``, …) to
        find a shape-key-bearing child (e.g. ``Box``) so sibling-
        normalisation reaches into ``Banner(Box(…))`` without the
        author wrapping things differently.
        """
        seen = 0
        cur = elem
        while cur is not None and seen < 6:
            if getattr(cur, "shape_key", None):
                return cur
            # Structural containers own an outer silhouette (padding,
            # border, header band). Their inner Box is not a visual peer of
            # adjacent leaf boxes; unwrapping through that boundary creates
            # a feedback loop where each equalisation pass adds container
            # padding again.
            if getattr(cur, "shape_peer_boundary", False):
                return None
            # Try common wrapper attributes: .child (Anchor, Captioned),
            # .body (Banner), .label (Box with Element label).
            nxt = getattr(cur, "child", None) or getattr(cur, "body", None)
            if nxt is None:
                break
            cur = nxt
            seen += 1
        return None

    def _normalize_shape_peers(self, theme: Theme) -> None:
        """Siblings in this row sharing the same ``shape_key`` get equalised
        min_width / min_height so they render at the same box size --
        regardless of label length or sub_label length.
        """
        if self._shape_normalized:
            return
        self._shape_normalized = True
        groups: dict = {}
        for c in self.children:
            peer = self._find_shape_peer(c)
            if peer is None:
                continue
            key = peer.shape_key
            if not key:
                continue
            groups.setdefault(key, []).append(peer)
        for key, peers in groups.items():
            if len(peers) < 2:
                continue
            sizes = [p.measure(theme) for p in peers]
            target_w = max(s.w for s in sizes)
            target_h = max(s.h for s in sizes)
            for p in peers:
                if getattr(p, "min_width", None) is None or p.min_width < target_w:
                    p.min_width = target_w
                if getattr(p, "min_height", None) is None or p.min_height < target_h:
                    p.min_height = target_h

    def _visible_children(self):
        """Children that participate in main-axis layout. Invisible ones
        are still rendered at the running cursor, but consume no gap."""
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    @staticmethod
    def _is_inline_connector(child) -> bool:
        """An inline ``Connect``/``Arrow`` opts out of equal-width slot
        stretching so cards equalise while the connector keeps its
        intrinsic compact width.
        """
        return bool(getattr(child, "is_inline_connector", False))

    def _stretch_children(self):
        """Children that want to fill the main axis (:class:`Separator` et al.)."""
        return [c for c in self.children
                if getattr(c, "stretch_main_axis", False)]

    def _slot_widths_for_visible(self, vis_sizes) -> List[float]:
        """Per-visible-child slot width, honouring :attr:`_forced_slot_w`."""
        slots: List[float] = []
        forced = self._forced_slot_w or []
        for i, s in enumerate(vis_sizes):
            base = s.w
            if i < len(forced) and forced[i] > base:
                slots.append(forced[i])
            else:
                slots.append(base)
        return slots

    def _balanced_outer_geometry(self, theme: Theme):
        """Return inward-packed x offsets for a bilateral three-part row.

        This is the single source of truth used by measurement, rendering,
        anchor publication, and content-bbox propagation.  Keeping the
        geometry here prevents the centreline from drifting between those
        phases when the two outer systems have unequal intrinsic widths.
        """
        visible = self._visible_children()
        if len(visible) != 3:
            raise ValueError(
                "Row(balance_outer=True) requires exactly three visible "
                f"children; got {len(visible)}"
            )
        sizes = [child.measure(theme) for child in visible]
        g = theme.gap_px(self.gap)
        side_slot = max(sizes[0].w, sizes[2].w)
        natural_w = 2.0 * side_slot + sizes[1].w + 2.0 * g
        if self._min_width > natural_w:
            side_slot += (self._min_width - natural_w) / 2.0
        offsets = (
            side_slot - sizes[0].w,
            side_slot + g,
            side_slot + g + sizes[1].w + g,
        )
        width = 2.0 * side_slot + sizes[1].w + 2.0 * g
        return offsets, width

    def _x_in_shared_slot(self, child: Element,
                          slot_x: float, slot_w: float,
                          content_bbox, visible_index: int,
                          visible_count: int, theme: Theme) -> float:
        """Place content inside a cross-row shared column.

        Shared columns normally centre corresponding stages.  When an outer
        stage is much narrower than its peer in another row, pure centring
        creates a conspicuous moat at the *inside* of the pipeline.  Bias
        only those large-surplus outer slots inward: the leftmost stage ends
        at its column boundary and the rightmost starts there.  Middle
        columns and small discrepancies remain centred, preserving ordinary
        table-like rhythm.
        """
        cb_x, _cb_y, cb_w, _cb_h = content_bbox
        slack = max(0.0, slot_w - cb_w)
        material_slack = max(theme.unit * 2.0,
                             theme.gap_px(self.gap) * 1.5)
        # Inward packing is for composite stages (streams, grouped panels),
        # not leaf nodes. A bare/anchored Box in a shared tower column should
        # stay centred under its encoder rather than hugging the centre gap.
        composite = hasattr(child, "children") or hasattr(child, "body")
        if composite and visible_count > 1 and slack > material_slack:
            if visible_index == 0:
                return slot_x + slot_w - (cb_x + cb_w)
            if visible_index == visible_count - 1:
                return slot_x - cb_x
        return slot_x + slot_w / 2.0 - (cb_x + cb_w / 2.0)

    def _auto_top_aligned_indices(self, content) -> set[int]:
        """Identify tall peer structures around a compact accessory.

        Architecture rows often contain two large nested systems separated
        by a small bridge/NIC/legend. Geometrically centring every child
        makes the systems' header bands drift. When at least two peers are
        similarly tall *and* a genuinely compact accessory is present,
        align those tall content boxes at the top while leaving the compact
        item optically centred. Ordinary rows retain centre alignment.
        """
        if self.align != "center":
            return set()
        visible = [
            (index, cb)
            for index, (child, cb) in enumerate(zip(self.children, content))
            if not getattr(child, "is_layout_invisible", False)
        ]
        if len(visible) < 3:
            return set()
        max_h = max((cb[3] for _index, cb in visible), default=0.0)
        if max_h <= 0.0:
            return set()
        tall = {index for index, cb in visible if cb[3] >= max_h * 0.72}
        has_compact = any(cb[3] <= max_h * 0.55 for _index, cb in visible)
        return tall if len(tall) >= 2 and has_compact else set()

    # ---- AlignedStack hooks ---------------------------------------------

    def _shared_column_widths(self, theme: Theme) -> List[float]:
        """Intrinsic per-visible-child widths."""
        vis_sizes = [c.measure(theme) for c in self._visible_children()]
        return [s.w for s in vis_sizes]

    def _apply_shared_columns(self, widths: List[float]) -> None:
        self._forced_slot_w = list(widths)

    def _stretch_visible_to_slots(self, widths: List[float]) -> None:
        """Inflate each visible child so its rendered width matches the
        slot it sits in. Called by :class:`AlignedStack` (``stretch=True``)
        after broadcasting shared column widths -- this turns the
        "centred-in-empty-slot" behaviour into actual same-width painting
        for Box-like children that implement ``inflate_to``.
        """
        for child, w in zip(self._visible_children(), widths):
            if w > 0:
                child.inflate_to(w, 0.0)

    def _equal_slot_width(self, theme: Theme) -> float:
        """Compute the equal-width slot value: the widest non-connector
        child's intrinsic width. Connectors keep their compact size and
        do NOT contribute to the slot. Returns 0 if no eligible children
        exist (the layout is degenerate).
        """
        visible = self._visible_children()
        if not visible:
            return 0.0
        vis_sizes = [c.measure(theme) for c in visible]
        eligible = [s.w for c, s in zip(visible, vis_sizes)
                    if not self._is_inline_connector(c)]
        if eligible:
            return max(eligible)
        return max((s.w for s in vis_sizes), default=0.0)

    def _maybe_equalise_widths(self, theme: Theme) -> None:
        """Inflate non-connector visible children so they all reach the
        widest peer's width. Idempotent per Row instance: only fires
        once unless a later ``inflate_to`` raises the floor.

        Without this step, ``equal_widths=True`` only allocates equal
        *slots* and centres children within them -- so cards of unequal
        intrinsic width leave uneven visible gaps even though the slots
        are uniform. Inflating peers to a common slot width is what
        Column has always done; Row now does the same so the two
        containers behave symmetrically.
        """
        if not self.equal_widths or self._equalised or not self.children:
            return
        self._equalised = True
        slot = self._equal_slot_width(theme)
        # If a parent has raised our floor (``inflate_to``) above the
        # natural slot, distribute the surplus to the non-connector
        # children so the Row actually fills the requested width.
        if self._min_width > 0:
            visible = self._visible_children()
            connectors_w = sum(c.measure(theme).w for c in visible
                               if self._is_inline_connector(c))
            n_eligible = sum(1 for c in visible
                             if not self._is_inline_connector(c))
            if n_eligible > 0:
                g = theme.gap_px(self.gap)
                gaps = g * max(0, len(visible) - 1)
                available = max(0.0,
                                self._min_width - connectors_w - gaps)
                wide_slot = available / n_eligible
                slot = max(slot, wide_slot)
        if slot <= 0.0:
            return
        for c in self._visible_children():
            if self._is_inline_connector(c):
                continue
            c.inflate_to(slot, 0.0)

    def _maybe_stretch_heights(self, theme: Theme) -> None:
        """For ``align="stretch"``: grow every child to the tallest child's
        height (cross-axis stretch) so side-by-side siblings share one outer
        height. Mirrors :meth:`_maybe_equalise_widths`; idempotent per
        instance. Children without a height-honouring ``inflate_to`` (most
        leaf elements) are simply left unaffected.
        """
        if self.align != "stretch" or self._stretched or not self.children:
            return
        self._stretched = True
        target_h = max(
            self._min_height,
            max((c.measure(theme).h for c in self.children), default=0.0),
        )
        if target_h <= 0.0:
            return
        for c in self.children:
            c.inflate_to(0.0, target_h)

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        # Width equalisation runs FIRST so that wrap-aware children
        # (e.g. ``Box(wrap=True)``) re-flow their labels to the shared
        # slot width before shape peers lock in a common min_height;
        # otherwise heights would be pinned at the taller, narrow-wrap
        # measurements.
        self._maybe_equalise_widths(theme)
        self._maybe_stretch_heights(theme)
        self._apply_height_floor(theme)
        self._normalize_shape_peers(theme)
        visible = self._visible_children()
        vis_sizes = [c.measure(theme) for c in visible]
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        n_vis = max(len(visible), 1)
        if self.balance_outer:
            _offsets, w = self._balanced_outer_geometry(theme)
        elif self.equal_widths and visible:
            # Inline connectors keep their intrinsic width while card-like
            # siblings equalise. The slot is taken from non-connector
            # children only; if every child is a connector, fall back to
            # the widest visible child so the row is still well-defined.
            eligible_sizes = [s for c, s in zip(visible, vis_sizes)
                              if not self._is_inline_connector(c)]
            if eligible_sizes:
                slot = max(s.w for s in eligible_sizes)
            else:
                slot = max(s.w for s in vis_sizes)
            w = 0.0
            for c, s in zip(visible, vis_sizes):
                w += s.w if self._is_inline_connector(c) else slot
            w += g * (len(visible) - 1)
        elif self._forced_slot_w is not None:
            slots = self._slot_widths_for_visible(vis_sizes)
            w = sum(slots) + g * (len(slots) - 1)
        else:
            w = sum(s.w for s in vis_sizes) + g * (n_vis - 1)
        # Row height must accommodate the TALLEST content bbox plus the
        # asymmetric out-of-band margins of any individual child, so that
        # content-axis centering still fits every child inside the row.
        content = [c.content_bbox(theme) for c in self.children]
        content_h = max(cb[3] for cb in content)
        max_top = max(cb[1] for cb in content)
        max_bot = max(s.h - cb[1] - cb[3] for s, cb in zip(sizes, content))
        h = max(
            self._min_height,
            content_h + max_top + max_bot,
            max(s.h for s in sizes),
        )
        if self._min_width > w:
            w = self._min_width
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        # Width equalisation runs FIRST so that wrap-aware children
        # (e.g. ``Box(wrap=True)``) re-flow their labels to the shared
        # slot width before shape peers lock in a common min_height;
        # otherwise heights would be pinned at the taller, narrow-wrap
        # measurements.
        self._maybe_equalise_widths(theme)
        self._maybe_stretch_heights(theme)
        self._apply_height_floor(theme)
        self._normalize_shape_peers(theme)
        # Resolve cross-axis stretchers (vertical separators etc.) to Row height
        # BEFORE taking measurements, so their measured height fits the row.
        H = self.measure(theme).h
        for c in self.children:
            if getattr(c, "stretch_main_axis", False) and hasattr(c, "set_stretched_length"):
                c.set_stretched_length(H)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        slot = None
        if self.equal_widths:
            vis_children = self._visible_children()
            vis_sizes = [c.measure(theme) for c in vis_children]
            eligible = [s for c, s in zip(vis_children, vis_sizes)
                        if not self._is_inline_connector(c)]
            if eligible:
                slot = max(s.w for s in eligible)
            else:
                slot = max((s.w for s in vis_sizes), default=0.0)
        # AlignedStack-forced per-slot widths (visible children only).
        forced_slots = None
        if (not self.equal_widths and not self.balance_outer
                and self._forced_slot_w is not None):
            visible_children = self._visible_children()
            vis_sizes = [c.measure(theme) for c in visible_children]
            forced_slots = self._slot_widths_for_visible(vis_sizes)
            visible_count = len(visible_children)
        else:
            visible_count = len(self._visible_children())
        balanced_offsets = None
        if self.balance_outer:
            balanced_offsets, _balanced_width = self._balanced_outer_geometry(theme)
        # Pre-compute the content-axis centre so that children with
        # asymmetric decoration margins (e.g. a Banner header above
        # but nothing below) stay inside the Row's reported bbox.
        _content_h = max(c[3] for c in content)
        _max_top = max(c[1] for c in content)
        top_aligned = self._auto_top_aligned_indices(content)
        cx = x
        vis_idx = 0
        for child_index, (child, size, cb) in enumerate(
                zip(self.children, sizes, content)):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_y = cb[1]
            cb_h = cb[3]
            if self.align in ("start", "stretch"):
                # Align CONTENT tops while retaining the largest asymmetric
                # decoration reserve (Region labels, badges, headers) above
                # them.  Using ``y - cb_y`` leaked decorated siblings above
                # the Row's measured bbox.
                cy = y + _max_top - cb_y
            elif self.align == "end":
                # The shared content baseline excludes the largest bottom
                # decoration reserve just as start excludes the top reserve.
                cy = y + _max_top + _content_h - (cb_y + cb_h)
            elif child_index in top_aligned:
                cy = y + _max_top - cb_y
            else:
                row_content_center_y = y + _max_top + _content_h / 2
                cy = row_content_center_y - (cb_y + cb_h / 2)
            if self.balance_outer and not invisible:
                child.render(canvas, x + balanced_offsets[vis_idx], cy, theme)
                vis_idx += 1
            elif self.equal_widths and not invisible:
                cb_x = cb[0]
                cb_w = cb[2]
                if self._is_inline_connector(child):
                    child.render(canvas, cx, cy, theme)
                    cx += size.w + g
                else:
                    slot_cx = cx + slot / 2
                    child.render(canvas, slot_cx - (cb_x + cb_w / 2), cy, theme)
                    cx += slot + g
            elif forced_slots is not None and not invisible:
                slot_w = forced_slots[vis_idx]
                child_x = self._x_in_shared_slot(
                    child, cx, slot_w, cb, vis_idx, visible_count, theme
                )
                child.render(canvas, child_x, cy, theme)
                cx += slot_w + g
                vis_idx += 1
            else:
                child.render(canvas, cx, cy, theme)
                if not invisible:
                    cx += size.w + g
                    vis_idx += 1

    def _child_offsets(self, theme: Theme):
        """Same x/y placement math as :meth:`render`, but returns the
        per-child offsets ``(ox, oy)`` in the Row's local frame.
        """
        if not self.children:
            return []
        # Width equalisation runs FIRST so that wrap-aware children
        # (e.g. ``Box(wrap=True)``) re-flow their labels to the shared
        # slot width before shape peers lock in a common min_height;
        # otherwise heights would be pinned at the taller, narrow-wrap
        # measurements.
        self._maybe_equalise_widths(theme)
        self._maybe_stretch_heights(theme)
        self._apply_height_floor(theme)
        self._normalize_shape_peers(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        H = self.measure(theme).h
        slot = None
        if self.equal_widths:
            vis_children = self._visible_children()
            vis_sizes = [c.measure(theme) for c in vis_children]
            eligible = [s for c, s in zip(vis_children, vis_sizes)
                        if not self._is_inline_connector(c)]
            if eligible:
                slot = max(s.w for s in eligible)
            else:
                slot = max((s.w for s in vis_sizes), default=0.0)
        forced_slots = None
        if (not self.equal_widths and not self.balance_outer
                and self._forced_slot_w is not None):
            visible_children = self._visible_children()
            vis_sizes = [c.measure(theme) for c in visible_children]
            forced_slots = self._slot_widths_for_visible(vis_sizes)
            visible_count = len(visible_children)
        else:
            visible_count = len(self._visible_children())
        balanced_offsets = None
        if self.balance_outer:
            balanced_offsets, _balanced_width = self._balanced_outer_geometry(theme)
        _content_h = max(c[3] for c in content)
        _max_top = max(c[1] for c in content)
        top_aligned = self._auto_top_aligned_indices(content)
        offs = []
        cx = 0.0
        vis_idx = 0
        for child_index, (child, size, cb) in enumerate(
                zip(self.children, sizes, content)):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_y = cb[1]
            cb_h = cb[3]
            if self.align in ("start", "stretch"):
                oy = 0.0 - cb_y
            elif self.align == "end":
                oy = H - (cb_y + cb_h)
            elif child_index in top_aligned:
                oy = _max_top - cb_y
            else:
                oy = (_max_top + _content_h / 2) - (cb_y + cb_h / 2)
            if self.balance_outer and not invisible:
                offs.append((balanced_offsets[vis_idx], oy, size))
                vis_idx += 1
            elif self.equal_widths and not invisible:
                if self._is_inline_connector(child):
                    offs.append((cx, oy, size))
                    cx += size.w + g
                else:
                    slot_cx = cx + slot / 2
                    ox = slot_cx - (cb[0] + cb[2] / 2)
                    offs.append((ox, oy, size))
                    cx += slot + g
            elif forced_slots is not None and not invisible:
                slot_w = forced_slots[vis_idx]
                ox = self._x_in_shared_slot(
                    child, cx, slot_w, cb, vis_idx, visible_count, theme
                )
                offs.append((ox, oy, size))
                cx += slot_w + g
                vis_idx += 1
            else:
                offs.append((cx, oy, size))
                if not invisible:
                    cx += size.w + g
                    vis_idx += 1
        return offs

    def primary_anchor_bbox(self, theme: Theme):
        """The Row's primary anchor is the union of its children's primary
        anchors -- the smallest rectangle containing every visible face.
        """
        if not self.children:
            return None
        offs = self._child_offsets(theme)
        xs_lo, ys_lo, xs_hi, ys_hi = [], [], [], []
        for (ox, oy, _size), child in zip(offs, self.children):
            for ax, ay, aw, ah in child.iter_primary_anchors(theme):
                xs_lo.append(ox + ax)
                ys_lo.append(oy + ay)
                xs_hi.append(ox + ax + aw)
                ys_hi.append(oy + ay + ah)
        if not xs_lo:
            return None
        x0, y0 = min(xs_lo), min(ys_lo)
        x1, y1 = max(xs_hi), max(ys_hi)
        return (x0, y0, x1 - x0, y1 - y0)

    def iter_primary_anchors(self, theme: Theme):
        out = []
        offs = self._child_offsets(theme)
        for (ox, oy, _size), child in zip(offs, self.children):
            for ax, ay, aw, ah in child.iter_primary_anchors(theme):
                out.append((ox + ax, oy + ay, aw, ah))
        return out

    def content_bbox(self, theme: Theme):
        """Union of children's content rectangles, translated into the
        Row's local frame. Used by Column alignment to stack rows on
        their visible content axis.
        """
        if not self.children:
            b = self.measure(theme)
            return (0.0, 0.0, b.w, b.h)
        offs = self._child_offsets(theme)
        xs_lo, ys_lo, xs_hi, ys_hi = [], [], [], []
        for (ox, oy, _size), child in zip(offs, self.children):
            cx, cy, cw, ch = child.content_bbox(theme)
            xs_lo.append(ox + cx)
            ys_lo.append(oy + cy)
            xs_hi.append(ox + cx + cw)
            ys_hi.append(oy + cy + ch)
        x0, y0 = min(xs_lo), min(ys_lo)
        x1, y1 = max(xs_hi), max(ys_hi)
        return (x0, y0, x1 - x0, y1 - y0)
