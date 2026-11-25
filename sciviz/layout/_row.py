"""Row: horizontal layout container.

A Row measures every child, arranges them left-to-right with automatic
spacing, and reports a bounding box that contains all of them. See
:class:`Column` for the vertical analogue.
"""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme

#: Align values understood by :class:`Row` and :class:`Column`.  Anything
#: else used to degrade silently to centring, which shipped figures where
#: the author believed e.g. ``align="stretch"`` was active when it wasn't.
VALID_ALIGN = ("start", "center", "end", "stretch")

#: :class:`Row` additionally aligns on text baselines (CSS
#: ``align-items: baseline``); a vertical stack has no shared baseline.
ROW_ALIGN = VALID_ALIGN + ("baseline",)


def _validate_align(container: str, align: str,
                    allowed: tuple = VALID_ALIGN) -> str:
    if align == "baseline" and "baseline" not in allowed:
        raise ValueError(
            f"{container}(align='baseline') is not supported: children "
            f"stacked along the main axis share no text baseline; use "
            f"Row(align='baseline') to line up the titles of side-by-side "
            f"children"
        )
    if align not in allowed:
        raise ValueError(
            f"{container}(align={align!r}) is not a recognised align value; "
            f"expected one of: {', '.join(repr(v) for v in allowed)}"
        )
    return align


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
        ``"center"``, ``"end"``, ``"stretch"`` or ``"baseline"``.
        ``"stretch"`` first
        inflates every child to the tallest child's height (via
        ``inflate_to``) so side-by-side siblings -- e.g. two ``Panel``\\ s
        -- share one outer height, then top-aligns them; leaf children
        that cannot grow vertically are left at their natural height.
        ``"baseline"`` (CSS ``align-items: baseline``) puts the first
        text baseline of every child on one line, whatever sits beside
        or above that text (a marker, an icon, a badge): tiles whose
        titles carry different decorations keep one title line, and the
        bodies under them start level when the titles match. A child
        with no text baseline (an icon, a chart) is centred on the band
        the aligned children occupy. Children report baselines through
        ``first_baseline(theme)`` (see :mod:`sciviz.layout._baseline`).
    gap : str, float or Rhythm
        Spacing between consecutive children: a token (``"md"``), a
        number of pixels, or a :class:`~sciviz.Rhythm`, which sets every
        gutter of every row sharing it to one content-to-content distance
        and lets the facing flow lanes of neighbours share that gutter.
    equal_widths : bool or "painted"
        If True, every child gets the same horizontal slot (the max child
        width). Critical for visually aligning columns of differing-width
        labels (e.g. tokens, bars, pictograms). Each child is centered
        within its slot. ``"painted"`` equalises the painted faces
        instead of the outer boxes: a child carrying a routed wire's lane
        gets the shared face plus its lane, so framed siblings paint one
        width with equal gutters. With ``justify="between"`` a stretched
        equal-width row widens its gutters instead of its slots.
    balance_outer : bool
        For a three-part bilateral composition, reserve equal-width slots
        for the first and third visible children and keep the middle child
        on the exact row centreline.  The outer children pack inward, so an
        unequal legend/system pair does not push the semantic centre off
        axis.  Layout-invisible children such as ``Connect`` are ignored.
    equal_heights : bool or None
        Height equalisation of siblings (the cross-axis analogue of
        ``equal_widths``). ``True`` grows every child to the tallest
        child's height via ``inflate_to``; ``False`` never does. The
        default ``None`` applies the *sibling-frame rule*: when a row
        holds two or more framed siblings (``Panel``, ``Card``,
        ``StepCell``; anything declaring ``frame_sibling = True``) and
        nothing else, their frames automatically share one height, so a
        flow of side-by-side panels or step cells reads as one balanced
        band without per-figure sizing work.
    grow : bool
        Mark this row as the child that takes a stretched parent
        ``Column``'s surplus height (the ``absorbs_main_axis_stretch``
        protocol, as ``Column(grow=True)`` and ``Region(grow=True)``).
        The row is then granted the height, and an ``align="stretch"``
        row passes it on to its children, so a band of cards under a
        heading fills an enclosure that a sibling made taller. The
        default ``False`` leaves the surplus to the column's
        ``justify``.
    """

    def __init__(self, *children: Element,
                 gap: Union[str, float, "Rhythm"] = "md",
                 align: str = "center", equal_widths: bool = False,
                 balance_outer: bool = False,
                 equal_heights: Union[bool, None] = None,
                 justify: str = "start",
                 grow: bool = False):
        from ._rhythm import Rhythm
        self.children: List[Element] = [c for c in children if c is not None]
        if isinstance(gap, Rhythm):
            if balance_outer:
                raise ValueError(
                    "Row(balance_outer=True) sizes its own two gaps "
                    "symmetrically; it does not take a Rhythm")
            gap._join(self, "x")
        self.gap = gap
        if justify not in ("start", "center", "end", "between"):
            raise ValueError(
                "Row justify must be 'start', 'center', 'end' or 'between'; "
                f"got {justify!r}")
        # Where a Row granted more width than its content (a stretched
        # Column, an inflated card) puts the surplus: after the children
        # (``start``, the historic behaviour), split around them, before
        # them, or ``between`` them -- a name flush left and its note flush
        # right on one line, without a spacer sized by hand.
        self.justify = justify
        if grow:
            # A parent Column offers its surplus height to this row
            # before distributing it by ``justify``.
            self.absorbs_main_axis_stretch = True
        self.align = _validate_align("Row", align, ROW_ALIGN)
        if equal_widths not in (False, True, "painted"):
            raise ValueError(
                "Row equal_widths must be False, True or 'painted'; "
                f"got {equal_widths!r}")
        self.equal_widths = equal_widths
        self.equal_heights = equal_heights
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

    def __setstate__(self, state):
        # A copy joins the copy of its Rhythm (see ``Rhythm._rejoin``).
        from ._rhythm import Rhythm
        Rhythm._rejoin(self, state, "x")

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

    def _justify_offsets(self, theme: Theme) -> tuple[float, float]:
        """``(lead, extra_gap)`` that place the width surplus per ``justify``.

        Only the plain packing path justifies: equal-width, balanced and
        AlignedStack-forced rows already own their slot geometry.
        """
        # An equal-width row justifies only ``between``: its slots are
        # fixed, and the surplus widens the gutters instead of the slots.
        equal_between = self.equal_widths and self.justify == "between"
        if (self.justify == "start" or self.balance_outer
                or (self.equal_widths and not equal_between)
                or self._forced_slot_w is not None):
            return 0.0, 0.0
        visible = self._visible_children()
        if not visible:
            return 0.0, 0.0
        if equal_between:
            slot = self._equal_slot_width(theme)
            natural = (sum(c.measure(theme).w
                           if self._is_inline_connector(c) else slot
                           for c in visible)
                       + self._gaps_total(theme, len(visible)))
        else:
            natural = (sum(c.measure(theme).w for c in visible)
                       + self._gaps_total(theme, len(visible)))
        surplus = max(0.0, self._min_width - natural)
        if surplus <= 1e-9:
            return 0.0, 0.0
        if self.justify == "between":
            if len(visible) == 1:
                return 0.0, 0.0
            return 0.0, surplus / (len(visible) - 1)
        if self.justify == "center":
            return surplus / 2.0, 0.0
        return surplus, 0.0

    def _visible_children(self):
        """Children that participate in main-axis layout. Invisible ones
        are still rendered at the running cursor, but consume no gap."""
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    def _is_rhythm(self) -> bool:
        from ._rhythm import Rhythm
        return isinstance(self.gap, Rhythm)

    def _gap_scalar(self, theme: Theme) -> float:
        """The gap as one number: the token, or a Rhythm's gutter."""
        if self._is_rhythm():
            return self.gap.gutter(theme)
        return theme.gap_px(self.gap)

    def _gap_list(self, theme: Theme) -> List[float]:
        """Spacing after each visible child (one entry per child)."""
        if self._is_rhythm():
            from ..core._measure_memo import memo_value
            return list(memo_value(
                self, "_gap_list", theme,
                lambda: self.gap.spacings(self, theme,
                                          self._placement_lanes(theme))))
        return [theme.gap_px(self.gap)] * len(self._visible_children())

    def _placement_lanes(self, theme: Theme) -> List[tuple]:
        """``(left, right)`` empty band between each visible child's slot
        edge and its content, as this row places it: the child's own flow
        lanes plus, in an equal-width (or shared-column) slot, the room
        the slot leaves beside the child's box once it is centred."""
        from ._rhythm import side_lane
        visible = self._visible_children()
        sizes = [c.measure(theme) for c in visible]
        slots = None
        if self.equal_widths and visible:
            eligible = [s.w for c, s in zip(visible, sizes)
                        if not self._is_inline_connector(c)]
            slot = max(eligible) if eligible else max(s.w for s in sizes)
            slots = [None if self._is_inline_connector(c) else slot
                     for c in visible]
        elif self._forced_slot_w is not None:
            slots = self._slot_widths_for_visible(sizes)
        out = []
        for i, (child, size) in enumerate(zip(visible, sizes)):
            left = side_lane(child, theme, "left")[0]
            right = side_lane(child, theme, "right")[0]
            slot = slots[i] if slots is not None else None
            if slot is not None:
                cb_x, _y, cb_w, _h = child.content_bbox(theme)
                offset = slot / 2.0 - (cb_x + cb_w / 2.0)
                left += offset
                right += slot - offset - size.w
            out.append((left, right))
        return out

    def _gaps_total(self, theme: Theme, n_visible: int) -> float:
        """Sum of the spacings between ``n_visible`` visible children."""
        if self._is_rhythm():
            return sum(self._gap_list(theme)[:-1])
        return theme.gap_px(self.gap) * (n_visible - 1)

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
                             self._gap_scalar(theme) * 1.5)
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
        """Intrinsic per-visible-child widths.

        A justified row (``justify`` other than ``"start"``) spreads its
        children across whatever width it is given, and a row spaced by a
        :class:`~sciviz.Rhythm` sets content-to-content gutters, which
        slot columns shared with a stacked neighbour would override; each
        is a layout of its own, not a row of a stacked grid, so it offers
        no columns to share and accepts none.
        """
        if not self._shares_columns():
            return []
        vis_sizes = [c.measure(theme) for c in self._visible_children()]
        return [s.w for s in vis_sizes]

    def _shares_columns(self) -> bool:
        """Whether this row takes part in a stacked grid's columns."""
        return self.justify == "start" and not self._is_rhythm()

    def _apply_shared_columns(self, widths: List[float]) -> None:
        if not self._shares_columns():
            return
        self._forced_slot_w = list(widths)

    def _stretch_visible_to_slots(self, widths: List[float]) -> None:
        """Inflate each visible child so its rendered width matches the
        slot it sits in. Called by :class:`AlignedStack` (``stretch=True``)
        after broadcasting shared column widths -- this turns the
        "centred-in-empty-slot" behaviour into actual same-width painting
        for Box-like children that implement ``inflate_to``.
        """
        if not self._shares_columns():
            return
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
        # ``equal_widths="painted"`` equalises PAINTED widths: a child
        # that declares immovable side decoration (an Anchor's flow-lane
        # margins, which the router adds where a wire enters a card)
        # measures wider than its face. The target is then the widest
        # face, and each child receives that face plus its own decoration
        # -- the width analogue of :meth:`_maybe_stretch_heights`.
        # ``True`` keeps the historic contract (equal OUTER boxes), which
        # paints a lane-less card wider than its laned sisters by exactly
        # their lanes.
        visible = self._visible_children()
        painted = self.equal_widths == "painted"
        decos = {id(c): (0.0 if (self._is_inline_connector(c) or not painted)
                         else self._stretch_decoration_w(c, theme))
                 for c in visible}
        faces = [c.measure(theme).w - decos[id(c)] for c in visible
                 if not self._is_inline_connector(c)]
        face = max(faces) if faces else self._equal_slot_width(theme)
        max_deco = max(decos.values(), default=0.0)
        slot = face + max_deco
        # If a parent has raised our floor (``inflate_to``) above the
        # natural slot, distribute the surplus to the non-connector
        # children so the Row actually fills the requested width --
        # unless ``justify="between"`` asks for the surplus to widen the
        # gutters instead (cards keep their natural shared width).
        if self._min_width > 0 and self.justify != "between":
            visible = self._visible_children()
            connectors_w = sum(c.measure(theme).w for c in visible
                               if self._is_inline_connector(c))
            n_eligible = sum(1 for c in visible
                             if not self._is_inline_connector(c))
            if n_eligible > 0:
                gaps = self._gaps_total(theme, max(1, len(visible)))
                available = max(0.0,
                                self._min_width - connectors_w - gaps)
                wide_slot = available / n_eligible
                slot = max(slot, wide_slot)
        if slot <= 0.0:
            return
        face = slot - max_deco
        for c in self._visible_children():
            if self._is_inline_connector(c):
                continue
            c.inflate_to(face + decos[id(c)], 0.0)

    @staticmethod
    def _stretch_decoration_w(child, theme: Theme) -> float:
        """Width of the immovable side decoration a child declares
        through the ``stretch_decoration`` protocol; zero otherwise."""
        fn = getattr(child, "stretch_decoration", None)
        if fn is None:
            return 0.0
        try:
            return float(fn(theme)[0])
        except (TypeError, IndexError, ValueError):
            return 0.0

    def _wants_height_equalisation(self) -> bool:
        """Whether sibling heights should be equalised for this row.

        ``align="stretch"`` and ``equal_heights=True`` always qualify;
        ``equal_heights=False`` never does. With the default
        ``equal_heights=None`` the *sibling-frame rule* applies: a row of
        two or more framed siblings (elements declaring
        ``frame_sibling = True``, i.e. Panel/Card/StepCell) and nothing
        else equalises automatically, because uneven frame heights in one
        band read as an accident rather than a choice.
        """
        if self.align == "stretch" or self.equal_heights is True:
            return True
        if self.equal_heights is False:
            return False
        peers = [
            c for c in self._visible_children()
            if not self._is_inline_connector(c)
        ]
        return (
            len(peers) >= 2
            and all(getattr(c, "frame_sibling", False) for c in peers)
        )

    def _maybe_stretch_heights(self, theme: Theme) -> None:
        """Grow every child to the tallest child's height (cross-axis
        stretch) so side-by-side siblings share one outer height. Fires
        for ``align="stretch"``, ``equal_heights=True``, or automatically
        for a row of framed siblings (see :meth:`_wants_height_equalisation`).
        Mirrors :meth:`_maybe_equalise_widths`; idempotent per instance.
        Children without a height-honouring ``inflate_to`` (most leaf
        elements) are simply left unaffected.
        """
        if self._stretched or not self.children:
            return
        if not self._wants_height_equalisation():
            return
        self._stretched = True
        # Equalise the painted faces, not the outer boxes: a child that
        # declares immovable decoration (an Anchor's flow-lane margins)
        # measures taller than its face, so the target is the tallest
        # face and each child receives that face plus its own decoration.
        # Equalising outer boxes instead left a margin-less card taller
        # than its margined siblings by exactly their margins.
        decos = [self._stretch_decoration_h(c, theme) for c in self.children]
        faces = [c.measure(theme).h - d for c, d in zip(self.children, decos)]
        face = max(
            self._min_height - max(decos, default=0.0),
            max(faces, default=0.0),
        )
        if face <= 0.0:
            return
        for c, d in zip(self.children, decos):
            c.inflate_to(0.0, face + d)

    @staticmethod
    def _stretch_decoration_h(child, theme: Theme) -> float:
        """Height of the immovable outer decoration a child declares
        through the ``stretch_decoration`` protocol (an Anchor's flow-lane
        margins); zero for everything else."""
        fn = getattr(child, "stretch_decoration", None)
        base = 0.0
        if fn is not None:
            try:
                base = float(fn(theme)[1])
            except (TypeError, IndexError, ValueError):
                base = 0.0
        # A child titled on its border line (``frame_bbox``) equalises on
        # its walls: whatever its box holds outside them (the half title
        # riding above the wall) is decoration too.
        frame = Row._frame_box(child, theme)
        if frame is not None:
            return max(base, child.measure(theme).h - frame[3])
        return base

    @staticmethod
    def _frame_box(child, theme: Theme):
        """The wall rectangle of a child that asks to be aligned and
        equalised on its walls (the ``frame_bbox`` protocol: a
        :class:`~sciviz.Region` titled on its border line, or an
        :class:`~sciviz.Anchor` around one); ``None`` for every other
        child, which keeps its content box."""
        fn = getattr(child, "frame_bbox", None)
        if fn is None:
            return None
        try:
            return fn(theme)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None

    def _alignment_boxes(self, theme: Theme, content):
        """``content`` with the walls of a wall-aligned child in place of
        its content box on the cross axis (the horizontal extent stays the
        content's). The same list object when no child declares a frame,
        so every other row is placed exactly as before. Baselines are
        measured from content tops, so a baseline row keeps them."""
        if self.align == "baseline":
            return content
        out = None
        for i, (child, cb) in enumerate(zip(self.children, content)):
            frame = self._frame_box(child, theme)
            if frame is None:
                continue
            if out is None:
                out = list(content)
            out[i] = (cb[0], frame[1], cb[2], frame[3])
        return content if out is None else out

    def _wall_envelope(self, theme: Theme, content, sizes):
        """``(line, height)`` of a row that holds a wall-aligned child:
        the alignment line below the row's top (the shared top, centre or
        bottom of the alignment boxes) and the exact height that contains
        every child placed on it. ``None`` for every other row.

        The general rule adds the largest margin above and the largest
        below to the tallest content box, whichever children they belong
        to. Here a margin is the half title above a wall: it rides in the
        room a taller neighbour leaves free and adds to the row's height
        only where nothing leaves it room."""
        if self.align == "baseline":
            return None
        if not any(self._frame_box(c, theme) is not None
                   for c in self.children):
            return None
        pairs = list(zip(sizes, content))
        if self.align in ("start", "stretch"):
            line = max(cb[1] for _s, cb in pairs)
            below = max(s.h - cb[1] for s, cb in pairs)
        elif self.align == "end":
            line = max(cb[1] + cb[3] for _s, cb in pairs)
            below = max(s.h - cb[1] - cb[3] for s, cb in pairs)
        else:
            if self._auto_top_aligned_indices(content):
                return None
            line = max(cb[1] + cb[3] / 2.0 for _s, cb in pairs)
            below = max(s.h - cb[1] - cb[3] / 2.0 for s, cb in pairs)
        return line, line + below

    @staticmethod
    def _reserve_box(child, cb, size, theme: Theme):
        """``cb`` with the flow lanes ``child`` surfaces counted as content.

        A container (a :class:`Column`, a nested row, a :class:`Region`)
        reports the lanes of the anchors at its ends through
        ``flow_lanes`` and leaves them out of its ``content_bbox``, so
        siblings line their content up past a corridor one of them
        carries. That alignment spends the row's slack; it never sizes
        the row. The row's height is taken from these reserve boxes (the
        lanes kept inside the child), and each child's alignment offset is
        clamped into its slack (:meth:`_clamp_to_slack`), so a lane can
        hang into space a sibling leaves free but never adds or removes
        height. An :class:`Anchor`'s own margins are not surfaced lanes:
        its content box has always excluded them.
        """
        lanes = getattr(child, "flow_lanes", None)
        if lanes is None or hasattr(child, "stretch_decoration_sides"):
            return cb
        top, bottom = lanes(theme)
        if top <= 0.0 and bottom <= 0.0:
            return cb
        x, y, w, h = cb
        y0 = max(0.0, y - top)
        y1 = min(size.h, y + h + bottom)
        return (x, y0, w, max(0.0, y1 - y0))

    @staticmethod
    def _clamp_to_slack(oy: float, h_child: float, h_row: float) -> float:
        """An alignment offset kept inside the row: ``[0, h_row - h]``."""
        return min(max(oy, 0.0), max(0.0, h_row - h_child))

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
        n_vis = max(len(visible), 1)
        gaps_total = self._gaps_total(theme, n_vis)
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
            w += gaps_total
        elif self._forced_slot_w is not None:
            slots = self._slot_widths_for_visible(vis_sizes)
            w = sum(slots) + gaps_total
        else:
            w = sum(s.w for s in vis_sizes) + gaps_total
        # Row height must accommodate the TALLEST content bbox plus the
        # asymmetric out-of-band margins of any individual child, so that
        # content-axis centering still fits every child inside the row.
        content = [c.content_bbox(theme) for c in self.children]
        content = self._alignment_boxes(theme, content)
        if self.align == "baseline":
            _dys, content_h = self._baseline_band(theme, content)
        else:
            # Lanes a container surfaces align its content but never
            # size the row (see :meth:`_reserve_box`).
            content = [self._reserve_box(c, cb, s, theme)
                       for c, cb, s in zip(self.children, content, sizes)]
            content_h = max(cb[3] for cb in content)
        max_top = max(cb[1] for cb in content)
        max_bot = max(s.h - cb[1] - cb[3] for s, cb in zip(sizes, content))
        h = max(
            self._min_height,
            content_h + max_top + max_bot,
            max(s.h for s in sizes),
        )
        envelope = self._wall_envelope(theme, content, sizes)
        if envelope is not None:
            # A row with a wall-aligned child takes its exact envelope.
            h = max(self._min_height, envelope[1],
                    max(s.h for s in sizes))
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
        gaps = self._gap_list(theme)
        content = [c.content_bbox(theme) for c in self.children]
        content = self._alignment_boxes(theme, content)
        # One placement for drawing and for every layout query
        # (content_bbox, first_baseline, flow_lanes, anchors).
        placed = self._place(theme, H, sizes, content, gaps, x, y)
        for (cx, cy, _size), child in zip(placed, self.children):
            child.render(canvas, cx, cy, theme)

    def _child_offsets(self, theme: Theme):
        """Per-child ``(ox, oy, size)`` in the Row's local frame: where
        :meth:`render` draws each child (both place through
        :meth:`_place`).
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
        gaps = self._gap_list(theme)
        content = [c.content_bbox(theme) for c in self.children]
        content = self._alignment_boxes(theme, content)
        H = self.measure(theme).h
        return self._place(theme, H, sizes, content, gaps, 0.0, 0.0)

    def _place(self, theme: Theme, H: float, sizes, content, gaps,
               x: float, y: float):
        """The Row's placement: per-child ``(x, y, size)`` for a row whose
        box starts at ``(x, y)``, from the row height ``H`` and the
        children's measured ``sizes``, content boxes and ``gaps``. The
        single source of truth for :meth:`render` (at the draw origin)
        and every layout query (at the local origin ``(0, 0)``).

        Callers measure first, each in its own historic order: a child
        whose measure is not idempotent (a stretched shared-column stack
        that re-inflates its members on every pass) then sees exactly as
        many passes as before, so placing through one function adds no
        measure pass and changes no size.
        """
        gi = 0
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
        band_dy = (self._baseline_band(theme, content)[0]
                   if self.align == "baseline" else None)
        top_aligned = self._auto_top_aligned_indices(content)
        # The exact alignment line of a row with a wall-aligned child
        # (``None`` for every other row: the general rule below).
        envelope = self._wall_envelope(theme, content, sizes)
        offs = []
        lead, extra = self._justify_offsets(theme)
        cx = x + lead
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
                oy = y + _max_top - cb_y
            elif self.align == "end":
                # The shared content baseline excludes the largest bottom
                # decoration reserve just as start excludes the top reserve.
                if envelope is not None:
                    oy = y + envelope[0] - (cb_y + cb_h)
                else:
                    oy = y + _max_top + _content_h - (cb_y + cb_h)
            elif band_dy is not None:
                oy = y + _max_top + band_dy[child_index] - cb_y
            elif child_index in top_aligned:
                oy = y + _max_top - cb_y
            elif envelope is not None:
                oy = y + envelope[0] - (cb_y + cb_h / 2)
            else:
                row_content_center_y = y + _max_top + _content_h / 2
                oy = row_content_center_y - (cb_y + cb_h / 2)
            # Every alignment is kept inside the row's slack.
            oy = y + self._clamp_to_slack(oy - y, size.h, H)
            if self.balance_outer and not invisible:
                offs.append((x + balanced_offsets[vis_idx], oy, size))
                vis_idx += 1
            elif self.equal_widths and not invisible:
                if self._is_inline_connector(child):
                    offs.append((cx, oy, size))
                    cx += size.w + gaps[gi] + extra
                    gi += 1
                else:
                    slot_cx = cx + slot / 2
                    ox = slot_cx - (cb[0] + cb[2] / 2)
                    offs.append((ox, oy, size))
                    cx += slot + gaps[gi] + extra
                    gi += 1
            elif forced_slots is not None and not invisible:
                slot_w = forced_slots[vis_idx]
                ox = self._x_in_shared_slot(
                    child, cx, slot_w, cb, vis_idx, visible_count, theme
                )
                offs.append((ox, oy, size))
                cx += slot_w + gaps[gi]
                gi += 1
                vis_idx += 1
            else:
                offs.append((cx, oy, size))
                if not invisible:
                    cx += size.w + gaps[gi] + extra
                    gi += 1
                    vis_idx += 1
        return offs

    def _baseline_band(self, theme: Theme, content):
        """Content-top offsets and band height for ``align="baseline"``.

        Returns ``(dy, band_h)``: child ``i``'s content box starts ``dy[i]``
        below the band's top.  Children with a first baseline share the
        line ``B = max(b_i)`` (``dy_i = B - b_i``); children without one
        are centred on the band.  With no baseline at all the row falls
        back to centring, so ``"baseline"`` never loses a child.
        """
        from ._baseline import first_baseline
        # Rows are measured many times per layout; the band only changes
        # when a child's content box (or the theme) does.
        key = tuple(tuple(cb) for cb in content)
        cached_theme, cached_key, cached = getattr(
            self, "_band_cache", (None, None, None))
        if cached_theme is theme and cached_key == key:
            return cached
        visible = set(id(c) for c in self._visible_children())
        bases = [first_baseline(c, theme) if id(c) in visible else None
                 for c in self.children]
        part = [b for b in bases if b is not None]
        if not part:
            h = max(cb[3] for cb in content)
            return [(h - cb[3]) / 2 for cb in content], h
        B = max(part)
        aligned_h = max(B - b + cb[3]
                        for b, cb in zip(bases, content) if b is not None)
        band_h = max([aligned_h] + [cb[3] for b, cb in zip(bases, content)
                                    if b is None])
        shift = (band_h - aligned_h) / 2
        dys = [shift + B - b if b is not None else (band_h - cb[3]) / 2
               for b, cb in zip(bases, content)]
        self._band_cache = (theme, key, (dys, band_h))
        return dys, band_h

    def first_baseline(self, theme: Theme):
        """First text baseline below the Row's content-box top.

        Taken from the first child (in order) that has one, where the
        Row places it, so nested rows keep their titles aligned.
        """
        from ._baseline import first_baseline
        if not self.children:
            return None
        if self.align == "baseline":
            # Every aligned child's baseline is the band's line.
            content = [c.content_bbox(theme) for c in self.children]
            visible = set(id(c) for c in self._visible_children())
            dys, _band_h = self._baseline_band(theme, content)
            for dy, child in zip(dys, self.children):
                if id(child) in visible:
                    b = first_baseline(child, theme)
                    if b is not None:
                        return dy + b - min(dys)
            return None
        offs = self._child_offsets(theme)
        top = self.content_bbox(theme)[1]
        for (_ox, oy, _s), child in zip(offs, self.children):
            if getattr(child, "is_layout_invisible", False):
                continue
            b = first_baseline(child, theme)
            if b is not None:
                return oy + child.content_bbox(theme)[1] + b - top
        return None

    def flow_lanes(self, theme: Theme) -> tuple[float, float]:
        """Flow-lane margins (top, bottom) the row carries at its edges.

        A top-aligned row lines its children's content tops up below the
        deepest top lane among them (see :meth:`Column.flow_lanes`), so
        that lane is the row's own top lane: a column holding this row
        first can then align it with sibling columns. A row aligned any
        other way reports the part of a child's lane that reaches past
        the row's content (a small anchored badge centred beside a taller
        title), and nothing when its lanes stay within that content.
        """
        from ._column import _end_lane
        if self.align in ("start", "stretch"):
            top = max((_end_lane(c, theme, 0)
                       for c in self._visible_children()), default=0.0)
            return top, 0.0
        # Centred (or end-aligned) rows: a child's lane is the row's own
        # outer lane only where it reaches past the row's content -- a
        # small anchored badge centred beside a taller title carries its
        # corridor above the title line, and only that overhang is lane.
        visible = set(id(c) for c in self._visible_children())
        tops, bottoms, lane_tops, lane_bottoms = [], [], [], []
        for (_ox, oy, _size), child in zip(self._child_offsets(theme),
                                           self.children):
            if id(child) not in visible:
                continue
            _cx, cy, _cw, ch = child.content_bbox(theme)
            top, bottom = oy + cy, oy + cy + ch
            tops.append(top)
            bottoms.append(bottom)
            lane_tops.append(top - _end_lane(child, theme, 0))
            lane_bottoms.append(bottom + _end_lane(child, theme, 1))
        if not tops:
            return 0.0, 0.0
        return (max(0.0, min(tops) - min(lane_tops)),
                max(0.0, max(lane_bottoms) - max(bottoms)))

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
