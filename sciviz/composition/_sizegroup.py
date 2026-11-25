"""SizeGroup: one shared size for siblings that live in different parents."""

from __future__ import annotations

from typing import List, Optional

from ..core import BBox, Canvas, Element, Theme

_AXES = ("width", "height", "both")
_FITS = ("grow", "slot")
_SLOT_ALIGN = ("start", "center", "end", "baseline")


class SizeGroup:
    """Give blocks in *different* parents one shared width (or height).

    :class:`~sciviz.composition.MatchSize` equalizes children it lays out
    itself, so it can only reach siblings that sit in the same container.
    The blocks that most need equalizing usually do not: they are one per
    row of a :class:`~sciviz.charts.Table`, one per cell of a
    :class:`~sciviz.grid.Grid`, one per branch of a tree. Auto-sized boxes
    in that position come out ragged, each as wide as its own longest word,
    and a column of ragged blocks reads as five unrelated objects rather
    than five rungs of one ladder.

    A ``SizeGroup`` is the membership those blocks are missing. Register
    each block with :meth:`add` and place what ``add`` returns; at measure
    time the group takes the widest (tallest) member and grows every member
    to it, so the column aligns on both edges::

        rungs = SizeGroup()                      # axis="width"
        rows = [[rungs.add(Box(title=f"Rung {n}", label=name,
                               wrap=True, max_width=90)),
                 TextBlock(reports)]
                for n, name, reports in ladder]
        body = Table(rows, col_align=("start", "start"))

    The shared size is recomputed for whichever theme is measuring, so a
    figure that compresses towards ``target_width_pt`` re-equalizes at the
    width it actually prints; members are grown with
    :meth:`Element.inflate_to`, the same request ``Row``/``Column``
    ``align="stretch"`` uses, so a member that cannot grow (leaf text) is
    left at its natural size instead of being centred in an empty slot.

    Shared bands (``fit="slot"``)
        Growing is right for boxes but wrong for *bands*: the title,
        picture and caption rows of side-by-side cards. Growing a picture
        distorts it, and a grown text column centres its lone caption, so
        a one-line caption sits lower than its two-line neighbours. With
        ``fit="slot"`` every member occupies a slot of the group's shared
        size while its child keeps its natural size and sits in the slot
        at ``align``. One group per band makes the bands of all the cards
        line up, and the cards come out equally tall with no surplus left
        for their columns to spread into empty gaps::

            heads = SizeGroup("height", fit="slot", align="baseline")
            pics = SizeGroup("height", fit="slot", align="center")
            notes = SizeGroup("height", fit="slot", align="start")
            cards = [Region(Column(heads(title), pics(picture),
                                   notes(caption), align="start"))
                     for title, picture, caption in stations]
            Row(*cards, gap="md", equal_widths=True)

    Parameters
    ----------
    axis : str
        ``"width"`` (default), ``"height"``, or ``"both"``.
    fit : str
        ``"grow"`` (default) grows every member to the shared size with
        ``inflate_to``; ``"slot"`` gives every member a slot of the shared
        size and draws its child at natural size inside it.
    align : str
        Where a child sits in its slot (``fit="slot"`` only): ``"start"``
        (default), ``"center"``, ``"end"``, or ``"baseline"``, which puts
        the members' first text baselines on one line (``axis="height"``
        only; members without text are centred). Applies on each grown
        axis.
    """

    def __init__(self, axis: str = "width", fit: str = "grow",
                 align: str = "start"):
        if axis not in _AXES:
            raise ValueError(
                f"SizeGroup.axis must be one of {', '.join(_AXES)}; got {axis!r}")
        if fit not in _FITS:
            raise ValueError(
                f"SizeGroup.fit must be one of {', '.join(_FITS)}; got {fit!r}")
        if align not in _SLOT_ALIGN:
            raise ValueError(
                f"SizeGroup.align must be one of {', '.join(_SLOT_ALIGN)}; "
                f"got {align!r}")
        if align == "baseline" and axis != "height":
            raise ValueError(
                "SizeGroup(align='baseline') needs axis='height': text "
                "baselines are horizontal lines")
        if align != "start" and fit != "slot":
            raise ValueError(
                "SizeGroup.align places a child inside its slot, so it "
                "needs fit='slot'")
        self.axis = axis
        self.fit = fit
        self.align = align
        self.members: List["_SizeGroupMember"] = []
        # Guard against re-entry: resolving the group measures its members,
        # and a member's measure asks the group to resolve.
        self._resolving = False
        self._slot_theme = None
        self._slot_key = None
        self._slot_value = (None, None, None)

    def add(self, child: Element) -> Element:
        """Register ``child`` and return the element to place in the tree.

        The returned wrapper is transparent -- it measures, renders, and
        reports its anchors as the child does -- but it is what triggers
        equalization, so placing the raw child instead silently opts it out.
        """
        member = _SizeGroupMember(child, self)
        self.members.append(member)
        return member

    # ``group(box)`` reads well at a call site that is already a list of
    # cells, where ``group.add(box)`` would be the third verb in the line.
    __call__ = add

    def resolve(self, theme: Theme) -> None:
        """Grow every member to the group's shared size under ``theme``."""
        if self.fit == "slot":
            return
        if self._resolving or not self.members:
            return
        self._resolving = True
        try:
            children = [m.child for m in self.members]
            if self.axis in ("width", "both"):
                target_w = max(c.measure(theme).w for c in children)
                for c in children:
                    c.inflate_to(target_w, 0.0)
            if self.axis in ("height", "both"):
                # Measured after any widening: a wider box re-wraps its
                # label onto fewer lines, so the tallest member is only
                # known once the widths have settled.
                target_h = max(c.measure(theme).h for c in children)
                for c in children:
                    c.inflate_to(0.0, target_h)
        finally:
            self._resolving = False


    def slot(self, theme: Theme):
        """``(width, height, baseline)`` of the shared slot (``fit="slot"``).

        ``width``/``height`` are ``None`` on an axis the group does not
        share; ``baseline`` is the shared line below the slot top when
        ``align="baseline"`` and some member has text, else ``None``.
        """
        from ..layout._baseline import baseline_in_frame
        children = [m.child for m in self.members]
        sizes = [c.measure(theme) for c in children]
        # Every member asks for the slot on every measure; the answer
        # only changes when a member's natural size (or the theme) does,
        # so the baseline walk below runs once per layout state.
        key = (tuple((sz.w, sz.h) for sz in sizes),)
        if self._slot_theme is theme and key == self._slot_key:
            return self._slot_value
        w = h = base = None
        if self.axis in ("width", "both"):
            w = max(sz.w for sz in sizes)
        if self.axis in ("height", "both"):
            h = max(sz.h for sz in sizes)
            if self.align == "baseline":
                bases = [baseline_in_frame(c, theme, 0.0) for c in children]
                part = [(b, sz.h) for b, sz in zip(bases, sizes)
                        if b is not None]
                if part:
                    base = max(b for b, _h in part)
                    h = max(h, base + max(hh - b for b, hh in part))
        self._slot_theme = theme
        self._slot_key, self._slot_value = key, (w, h, base)
        return w, h, base


def _slot_offset(align: str, slot: float, natural: float) -> float:
    if align == "center":
        return (slot - natural) / 2
    if align == "end":
        return slot - natural
    return 0.0


class _SizeGroupMember(Element):
    """Transparent wrapper that resolves its group before measuring."""

    def __init__(self, child: Element, group: SizeGroup):
        self.child = child
        self.group = group
        self._geo_theme = None
        self._geo_key = None
        self._geo = (0.0, 0.0, 0.0, 0.0)

    @property
    def is_layout_invisible(self) -> bool:      # type: ignore[override]
        return getattr(self.child, "is_layout_invisible", False)

    @property
    def primary_anchor(self):                   # type: ignore[override]
        return getattr(self.child, "primary_anchor", None)

    @property
    def _slotted(self) -> bool:
        return self.group.fit == "slot"

    def _slot_geometry(self, theme: Theme):
        """``(W, H, dx, dy)``: the member's box and the child's offset."""
        from ..layout._baseline import baseline_in_frame
        nat = self.child.measure(theme)
        sw, sh, base = self.group.slot(theme)
        key = (nat.w, nat.h, sw, sh, base)
        if self._geo_theme is theme and key == self._geo_key:
            return self._geo
        W = max(nat.w, sw) if sw is not None else nat.w
        H = max(nat.h, sh) if sh is not None else nat.h
        align = self.group.align
        dx = _slot_offset(align, W, nat.w) if sw is not None else 0.0
        dy = 0.0
        if sh is not None:
            b = (baseline_in_frame(self.child, theme, 0.0)
                 if align == "baseline" else None)
            if b is not None and base is not None:
                dy = base - b
            else:
                dy = _slot_offset("center" if align == "baseline" else align,
                                  H, nat.h)
        self._geo_theme = theme
        self._geo_key, self._geo = key, (W, H, dx, dy)
        return W, H, dx, dy

    def measure(self, theme: Theme) -> BBox:
        if self._slotted:
            W, H, _dx, _dy = self._slot_geometry(theme)
            return BBox(W, H)
        self.group.resolve(theme)
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self._slotted:
            _W, _H, dx, dy = self._slot_geometry(theme)
            self.child.render(canvas, x + dx, y + dy, theme)
            return
        self.group.resolve(theme)
        self.child.render(canvas, x, y, theme)

    def port_bbox(self, theme: Theme, side: str):
        """The child's body port (see :meth:`Element.port_bbox`), offset
        to where the child sits in its slot."""
        port = self.child.port_bbox(theme, side)
        if port is None:
            return None
        dx = dy = 0.0
        if self._slotted:
            _W, _H, dx, dy = self._slot_geometry(theme)
        else:
            self.group.resolve(theme)
        px, py, pw, ph = port
        return (px + dx, py + dy, pw, ph)

    def content_bbox(self, theme: Theme):
        """The child's content box; along a shared axis, the whole slot.

        A slot is one band of a grid shared across parents, so the slot,
        not the child inside it, is what sibling containers align.
        """
        if self._slotted:
            W, H, dx, dy = self._slot_geometry(theme)
            cx, cy, cw, ch = self.child.content_bbox(theme)
            if self.group.axis in ("width", "both"):
                cx, cw = 0.0, W
            else:
                cx += dx
            if self.group.axis in ("height", "both"):
                cy, ch = 0.0, H
            else:
                cy += dy
            return (cx, cy, cw, ch)
        self.group.resolve(theme)
        return self.child.content_bbox(theme)

    def first_baseline(self, theme: Theme):
        """The child's first baseline, measured from this slot's content top."""
        from ..layout._baseline import baseline_in_frame
        if not self._slotted:
            self.group.resolve(theme)
            from ..layout._baseline import first_baseline
            return first_baseline(self.child, theme)
        _W, _H, _dx, dy = self._slot_geometry(theme)
        b = baseline_in_frame(self.child, theme, dy)
        if b is None:
            return None
        return b - self.content_bbox(theme)[1]

    def _offset(self, theme: Theme):
        if self._slotted:
            _W, _H, dx, dy = self._slot_geometry(theme)
            return dx, dy
        self.group.resolve(theme)
        return 0.0, 0.0

    def primary_anchor_bbox(self, theme: Theme):
        dx, dy = self._offset(theme)
        pa = self.child.primary_anchor_bbox(theme)
        if pa is None:
            return None
        return (pa[0] + dx, pa[1] + dy, pa[2], pa[3])

    def iter_primary_anchors(self, theme: Theme):
        dx, dy = self._offset(theme)
        return [(ax + dx, ay + dy, aw, ah)
                for ax, ay, aw, ah in self.child.iter_primary_anchors(theme)]

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        if self._slotted:
            # A slot keeps its child at natural size along the shared
            # axis; the other axis still honours a parent's stretch.
            if self.group.axis == "height":
                self.child.inflate_to(min_w, 0.0)
            elif self.group.axis == "width":
                self.child.inflate_to(0.0, min_h)
            return
        self.child.inflate_to(min_w, min_h)

    def __repr__(self) -> str:                  # pragma: no cover - debug aid
        return f"SizeGroup.member({self.child!r})"
