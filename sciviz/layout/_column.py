"""Column: vertical layout container."""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme
from ._row import Row, _validate_align


_VALID_JUSTIFY = ("start", "center", "end", "between")


def _validate_justify(container: str, justify: str) -> str:
    if justify not in _VALID_JUSTIFY:
        raise ValueError(
            f"{container}(justify={justify!r}) is not a recognised justify "
            f"value; expected one of {_VALID_JUSTIFY}.")
    return justify


class Column(Element):
    """Vertical container. See :class:`sciviz.layout.Row` for details.

    Parameters
    ----------
    align : str
        Cross-axis (horizontal) placement of children: ``"start"``,
        ``"center"``, ``"end"``, or ``"stretch"``. ``"stretch"`` first
        inflates every child to the widest child's width (via
        ``inflate_to``) so stacked siblings -- e.g. a spine of ``Card``\\ s
        -- share one outer width, then left-aligns them; leaf children
        that cannot grow horizontally are left at their natural width.
        Mirrors ``Row(align="stretch")``, which stretches heights.
    equal_widths : bool
        If True, every visible child is inflated to the widest child's
        intrinsic width via :meth:`Element.inflate_to`, so siblings like
        captioner cards or tinted panels paint at the same outer width
        instead of just sharing a centring slot. Children that don't
        support inflation are still rendered at intrinsic width and
        centred within the column.
    justify : str
        Main-axis (vertical) distribution of surplus height when a parent
        grants the column more room than its natural content needs (e.g.
        ``Row(align="stretch")`` equalising zone heights): ``"between"``
        (default, the historical behaviour) grows the existing gaps so
        the first child stays pinned to the top and the last to the
        bottom; ``"start"`` packs children at the top, ``"center"``
        centres the block in the frame, ``"end"`` packs at the bottom.
        A lone child centres under every mode except the pins. Surplus
        is offered to ``grow`` children first; ``justify`` distributes
        only the residual, so negative space is laid out deliberately
        instead of pooling wherever content happens to stop.
    grow : bool
        Mark this column as the child that absorbs its parent column's
        surplus main-axis height (the ``absorbs_main_axis_stretch``
        protocol, previously internal). The canonical zone grammar is
        ``Column(header, Column(*content, grow=True, justify=...))``:
        the header stays in the shared top band while the content column
        receives the zone's remaining height and distributes its
        negative space per its own ``justify``.
    """

    # A Row that is itself stretched by a parent may contain a major stage
    # Column beside a small accessory (cache, badge, legend). The stage is
    # the child that should absorb cross-axis height; the accessory remains
    # optically centred.
    absorbs_cross_axis_stretch = True

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center", equal_widths: bool = False,
                 justify: str = "between", grow: bool = False):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = _validate_align("Column", align)
        self.justify = _validate_justify("Column", justify)
        if grow:
            self.absorbs_main_axis_stretch = True
        self.equal_widths = equal_widths
        self._equalised = False
        # Whether align="stretch" has broadcast the widest width to children.
        self._stretched = False
        # Floor on the column's rendered width, set by ``inflate_to``.
        # Honoured in ``measure`` / ``render``; children retain their
        # alignment within the (possibly widened) column frame.
        self._min_width: float = 0.0
        # Main-axis floor used by Row(align="stretch"). Structural panels
        # inside the column absorb this height before we fall back to
        # distributing it across gaps.
        self._min_height: float = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Grow the Column's outer frame to a requested width and height.

        Height is primarily absorbed by structural panel children (for
        aligned architecture stages); any residual is distributed through
        the existing gaps.  This keeps first/last stage landmarks aligned
        without authors inserting pixel spacers.
        """
        if min_w > self._min_width:
            self._min_width = float(min_w)
            # A parent may raise the floor after our intrinsic pass. Re-run
            # equalisation / stretching so painted children, not just the
            # column frame, receive the new shared width.
            self._equalised = False
            self._stretched = False
        if min_h > self._min_height:
            self._min_height = float(min_h)

    def _apply_height_floor(self, theme: Theme) -> None:
        """Offer surplus height to semantic structural children first."""
        if self._min_height <= 0.0:
            return
        visible = self._visible_children()
        if not visible:
            return
        g = theme.gap_px(self.gap)
        sizes = [child.measure(theme) for child in visible]
        natural = sum(size.h for size in sizes) + g * (len(visible) - 1)
        surplus = self._min_height - natural
        if surplus <= 0.5:
            return
        absorbers = [
            child for child in visible
            if getattr(child, "absorbs_main_axis_stretch", False)
        ]
        if not absorbers:
            return
        share = surplus / len(absorbers)
        for child in absorbers:
            child.inflate_to(0.0, child.measure(theme).h + share)

    def _visible_children(self):
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    # ---- AlignedStack-style normalisation (always-on) --------------------
    # Column inherits the two key AlignedStack behaviours so that authors
    # get cross-child shape equalisation and shared column widths without
    # reaching for AlignedStack explicitly.  Both passes are no-ops when
    # children don't carry shape keys or don't implement the shared-width
    # hooks (i.e. the common Text / Box / Icon case is untouched).

    def _normalize_cross_child_shapes(self, theme: Theme) -> None:
        groups: dict = {}
        for child in self.children:
            peer = Row._find_shape_peer(child)
            if peer is not None and getattr(peer, "shape_key", ""):
                groups.setdefault(peer.shape_key, []).append(peer)
            for sub in getattr(child, "children", []):
                peer = Row._find_shape_peer(sub)
                if peer is not None and getattr(peer, "shape_key", ""):
                    groups.setdefault(peer.shape_key, []).append(peer)
        for peers in groups.values():
            if len(peers) < 2:
                continue
            sizes = [p.measure(theme) for p in peers]
            tw = max(s.w for s in sizes)
            th = max(s.h for s in sizes)
            for p in peers:
                # Skip elements with explicit dimensions — the author
                # set a deliberate size that shouldn't be overridden.
                if getattr(p, "width", None) is None:
                    if getattr(p, "min_width", None) is None or p.min_width < tw:
                        p.min_width = tw
                if getattr(p, "height", None) is None:
                    if getattr(p, "min_height", None) is None or p.min_height < th:
                        p.min_height = th

    def _propagate_shared_widths(self, theme: Theme) -> None:
        # Trigger within-Row shape normalisation first so the column
        # widths we collect reflect the *post-equalisation* sizes.
        for c in self.children:
            norm = getattr(c, "_normalize_shape_peers", None)
            if norm is not None:
                norm(theme)
        per_child = []
        for c in self.children:
            fn = getattr(c, "_shared_column_widths", None)
            if fn is not None:
                try:
                    per_child.append([float(w) for w in fn(theme)])
                    continue
                except Exception:
                    pass
            per_child.append([])
        # Only propagate when at least two children contribute column
        # widths — a single Row has nothing to align against, and
        # forcing slot widths on it changes centering semantics.
        contributing = sum(1 for widths in per_child if widths)
        if contributing < 2:
            return
        max_cols = max((len(widths) for widths in per_child), default=0)
        if max_cols == 0:
            return
        shared = [0.0] * max_cols
        for widths in per_child:
            for index, width in enumerate(widths):
                shared[index] = max(shared[index], width)
        for child in self.children:
            apply = getattr(child, "_apply_shared_columns", None)
            if apply is not None:
                try:
                    apply(shared)
                except Exception:
                    pass

    def _shared_column_widths(self, theme: Theme) -> List[float]:
        """Expose aggregate semantic columns from nested row children."""
        per_child = []
        for child in self.children:
            probe = getattr(child, "_shared_column_widths", None)
            if probe is None:
                continue
            try:
                widths = [float(width) for width in probe(theme)]
            except Exception:  # pragma: no cover - defensive wrapper
                continue
            if widths:
                per_child.append(widths)
        max_cols = max((len(widths) for widths in per_child), default=0)
        shared = [0.0] * max_cols
        for widths in per_child:
            for index, width in enumerate(widths):
                shared[index] = max(shared[index], width)
        return shared

    def _apply_shared_columns(self, widths) -> None:
        for child in self.children:
            apply = getattr(child, "_apply_shared_columns", None)
            if apply is not None:
                apply(widths)

    def _stretch_visible_to_slots(self, widths) -> None:
        for child in self.children:
            stretch = getattr(child, "_stretch_visible_to_slots", None)
            if stretch is not None:
                stretch(widths)

    def _maybe_equalise_widths(self, theme: Theme) -> None:
        """Broadcast the widest child's width to siblings via ``inflate_to``.
        Idempotent: only fires once per Column instance.
        """
        if not self.equal_widths or self._equalised or not self.children:
            return
        self._equalised = True
        sizes = [c.measure(theme) for c in self._visible_children()]
        if not sizes:
            return
        target = max(max(s.w for s in sizes), self._min_width)
        for c in self._visible_children():
            c.inflate_to(target, 0.0)

    def _maybe_stretch_widths(self, theme: Theme) -> None:
        """For ``align="stretch"``: grow every child to the widest child's
        width (cross-axis stretch) so stacked siblings share one outer
        width. Mirrors :meth:`Row._maybe_stretch_heights`; idempotent per
        instance. Children without a width-honouring ``inflate_to`` (most
        leaf elements) are simply left unaffected.

        Stretch equalises the *painted faces* of its children.  A
        child's face is its outer width minus any immovable outer
        decoration it declares through the ``stretch_decoration``
        protocol (:class:`Anchor` returns its flow-lane margins there,
        so margined cards keep faces flush with their unmargined
        siblings).  Decoration is an explicit wrapper contract, never
        inferred from content bboxes: a Row that centres its content
        between flexible slots reports a content box narrower than its
        paint, and treating that interior slack as decoration used to
        re-widen the target on every pass until stacked cards
        overshot their widest member by half the narrowest child's
        slack.
        """
        if self.align != "stretch" or self._stretched or not self.children:
            return
        self._stretched = True
        sizes = [c.measure(theme) for c in self.children]
        decorations = []
        for c in self.children:
            deco_fn = getattr(c, "stretch_decoration", None)
            if deco_fn is not None:
                decorations.append(max(0.0, float(deco_fn(theme)[0])))
            else:
                decorations.append(0.0)
        target_w = max(
            self._min_width,
            max((size.w - deco
                 for size, deco in zip(sizes, decorations)), default=0.0),
        )
        if target_w <= 0.0:
            return
        for c, deco in zip(self.children, decorations):
            c.inflate_to(target_w + deco, 0.0)

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        self._normalize_cross_child_shapes(theme)
        self._propagate_shared_widths(theme)
        self._maybe_equalise_widths(theme)
        self._maybe_stretch_widths(theme)
        self._apply_height_floor(theme)
        sizes = [c.measure(theme) for c in self.children]
        visible = self._visible_children()
        vis_sizes = [c.measure(theme) for c in visible]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        left_extent, right_extent = self._cross_extents(sizes, content)
        w = left_extent + right_extent
        if self._min_width > w:
            w = self._min_width
        n_vis = max(len(visible), 1)
        h = sum(s.h for s in vis_sizes) + g * (n_vis - 1)
        h = max(h, self._min_height)
        return BBox(w, h)

    def _cross_extents(self, sizes, content) -> tuple[float, float]:
        """Outer space required on each side of the shared content axis.

        Computing independent maxima for content width, left decoration,
        and right decoration over-counted space when those maxima belonged
        to different children.  Expressing every child relative to the
        actual alignment axis gives the exact union instead.
        """
        if self.align == "stretch":
            # Stretched children share one outer width and fill their
            # slot edge to edge, so the union is the plain outer union.
            # Aligning on content landmarks here double-counts the
            # centring slack a stretched Row keeps around its content
            # (each inflated sibling re-widens the union, which re-
            # inflates the siblings) and can overshoot the true width
            # by half the narrowest child's slack.
            left = 0.0
            right = max(size.w for size in sizes)
        elif self.align == "start":
            left = max(cb[0] for cb in content)
            right = max(size.w - cb[0]
                        for size, cb in zip(sizes, content))
        elif self.align == "end":
            left = max(cb[0] + cb[2] for cb in content)
            right = max(size.w - cb[0] - cb[2]
                        for size, cb in zip(sizes, content))
        else:
            left = max(cb[0] + cb[2] / 2 for cb in content)
            right = max(size.w - cb[0] - cb[2] / 2
                        for size, cb in zip(sizes, content))
        return left, right

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        self._maybe_equalise_widths(theme)
        self._maybe_stretch_widths(theme)
        self._apply_height_floor(theme)
        # Give cross-axis stretchers (horizontal separators etc.) the
        # column's full width so they render as full-width rules.
        W = self.measure(theme).w
        for c in self.children:
            if getattr(c, "stretch_main_axis", False) and hasattr(c, "set_stretched_length"):
                c.set_stretched_length(W)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        left_extent, right_extent = self._cross_extents(sizes, content)
        natural_w = left_extent + right_extent
        # ``inflate_to`` widens the column's frame without widening its
        # children.  Keep the natural content band centred inside that
        # extra frame; otherwise all surplus width accumulates on the
        # right and a centred stack appears left-aligned.
        extra_cross_space = max(0.0, W - natural_w)
        visible = self._visible_children()
        natural_h = (
            sum(c.measure(theme).h for c in visible)
            + g * max(0, len(visible) - 1)
        )
        residual = max(0.0, self.measure(theme).h - natural_h)
        effective_gap = g
        lead = 0.0
        if residual > 0.0:
            if len(visible) == 1:
                # A lone child keeps optical centring in every mode except
                # the explicit pins ("between" has no gaps to grow).
                lead = (0.0 if self.justify == "start"
                        else residual if self.justify == "end"
                        else residual / 2)
            elif self.justify == "between":
                effective_gap += residual / (len(visible) - 1)
            elif self.justify == "center":
                lead = residual / 2
            elif self.justify == "end":
                lead = residual
        cy = y + lead
        visible_index = 0
        for child, size, cb in zip(self.children, sizes, content):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_x = cb[0]
            cb_w = cb[2]
            if self.align == "stretch":
                # Stretched children fill the shared slot from the
                # column origin (see the outer-union in _cross_extents).
                cx = x
            elif self.align == "start":
                axis_x = x + left_extent
                cx = axis_x - cb_x
            elif self.align == "end":
                axis_x = x + extra_cross_space + left_extent
                cx = axis_x - (cb_x + cb_w)
            else:
                axis_x = x + extra_cross_space / 2 + left_extent
                cx = axis_x - (cb_x + cb_w / 2)
            child.render(canvas, cx, cy, theme)
            if not invisible:
                visible_index += 1
                cy += size.h
                if visible_index < len(visible):
                    cy += effective_gap
