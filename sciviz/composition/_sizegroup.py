"""SizeGroup: one shared size for siblings that live in different parents."""

from __future__ import annotations

from typing import List, Optional

from ..core import BBox, Canvas, Element, Theme

_AXES = ("width", "height", "both")


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

    Parameters
    ----------
    axis : str
        ``"width"`` (default), ``"height"``, or ``"both"``.
    """

    def __init__(self, axis: str = "width"):
        if axis not in _AXES:
            raise ValueError(
                f"SizeGroup.axis must be one of {', '.join(_AXES)}; got {axis!r}")
        self.axis = axis
        self.members: List["_SizeGroupMember"] = []
        # Guard against re-entry: resolving the group measures its members,
        # and a member's measure asks the group to resolve.
        self._resolving = False

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


class _SizeGroupMember(Element):
    """Transparent wrapper that resolves its group before measuring."""

    def __init__(self, child: Element, group: SizeGroup):
        self.child = child
        self.group = group

    @property
    def is_layout_invisible(self) -> bool:      # type: ignore[override]
        return getattr(self.child, "is_layout_invisible", False)

    @property
    def primary_anchor(self):                   # type: ignore[override]
        return getattr(self.child, "primary_anchor", None)

    def measure(self, theme: Theme) -> BBox:
        self.group.resolve(theme)
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self.group.resolve(theme)
        self.child.render(canvas, x, y, theme)

    def content_bbox(self, theme: Theme):
        self.group.resolve(theme)
        return self.child.content_bbox(theme)

    def primary_anchor_bbox(self, theme: Theme):
        self.group.resolve(theme)
        return self.child.primary_anchor_bbox(theme)

    def iter_primary_anchors(self, theme: Theme):
        self.group.resolve(theme)
        return self.child.iter_primary_anchors(theme)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.child.inflate_to(min_w, min_h)

    def __repr__(self) -> str:                  # pragma: no cover - debug aid
        return f"SizeGroup.member({self.child!r})"
