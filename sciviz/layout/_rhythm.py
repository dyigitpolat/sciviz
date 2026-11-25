"""Rhythm: one gutter shared by every gap it spaces.

A :class:`Rhythm` is passed as ``gap=`` to a :class:`~sciviz.Row` or a
:class:`~sciviz.Column`. Every consecutive pair of visible children in
every container that shares the object is then set the same
content-to-content distance, the gutter ``G``::

    G = max(gap token, the largest lane need of any member pair)

so sister cards read as one beat whatever wires cross between them, and
two facing flow lanes (a wire leaving the bottom of one card and entering
the top of the next) share one gutter instead of stacking tail lane, gap
and head lane.

Lane needs come from the flow lanes the children already carry (an
:class:`~sciviz.Anchor`'s margins, surfaced through nested rows and
columns). A wire whose two ends face each other across the gutter is
counted once: its need is the larger end reservation, or both halves of
its caption corridor when it carries a caption. Lanes of different wires
on the two sides still add up, since they run side by side. Lanes the
resolver did not itemise (a :class:`~sciviz.Flowed` scope, a bus tap) are
kept whole, which is the summed spacing of an ordinary token gap.

A Rhythm spaces one axis: sharing one object between a Row and a Column
raises ``ValueError`` (a horizontal caption corridor must not set the
vertical beat). Use one Rhythm per axis.
"""

from __future__ import annotations

import itertools
import weakref
from numbers import Real
from typing import Dict, List, Tuple, Union

from ..core import Theme

__all__ = ["Rhythm"]

_SIDES = {"top": "top", "topleft": "top", "topright": "top",
          "bottom": "bottom", "bottomleft": "bottom",
          "bottomright": "bottom", "left": "left", "right": "right"}
_SIDE_INDEX = {"left": 0, "right": 1, "top": 2, "bottom": 3}
_END_KEYS = itertools.count()


def note_lane(anchor, side: str, amount: float, *, key=None,
              full: float = None) -> None:
    """Record what one wire end reserves on ``anchor``'s ``side``.

    Called by the flow resolver beside every margin bump, on the same
    anchor and in the same pass, so the record lives exactly as long as
    the margin it itemises. ``key`` identifies the wire: the two ends of
    a facing wire share it, every other end gets its own. ``full`` is
    what the wire needs from a gutter it crosses (defaults to
    ``amount``).
    """
    side = _SIDES.get(side)
    if side is None:
        return
    if key is None:
        key = ("end", next(_END_KEYS))
    wires = anchor.__dict__.get("_lane_wires")
    if wires is None:
        wires = {}
        anchor._lane_wires = wires
    per_side = wires.setdefault(side, {})
    old = per_side.get(key)
    full = float(amount if full is None else full)
    if old is not None:
        amount = max(old[0], amount)
        full = max(old[1], full)
    per_side[key] = (float(amount), full)


def side_lane(child, theme: Theme, side: str
              ) -> Tuple[float, Dict[object, Tuple[float, float]]]:
    """``(lane, wires)`` a child carries at its outer ``side``.

    ``lane`` is the flow-lane margin at that edge; ``wires`` maps each
    recorded wire end in it to ``(amount, full need)``. Follows the
    anchors that sit at the child's edge: a column's first (top) or last
    (bottom) child, a row's first (left) or last (right) child, and the
    band all of a row's children leave free at its top or bottom. Never
    measures, so a Rhythm
    can resolve while its own containers measure. Anything else reports
    no lane, which only keeps a gap as wide as a token gap would make it.
    """
    from ._column import Column
    from ._row import Row
    sides = getattr(child, "stretch_decoration_sides", None)
    if sides is not None:
        try:
            lane = float(sides(theme)[_SIDE_INDEX[side]])
        except Exception:  # pragma: no cover - defensive
            return 0.0, {}
        wires = child.__dict__.get("_lane_wires", {}).get(side, {})
        return lane, dict(wires)
    visible = [c for c in getattr(child, "children", ())
               if c is not None
               and not getattr(c, "is_layout_invisible", False)]
    if not visible:
        return 0.0, {}
    if isinstance(child, Column):
        if side == "top":
            return side_lane(visible[0], theme, side)
        if side == "bottom":
            return side_lane(visible[-1], theme, side)
        return 0.0, {}
    if isinstance(child, Row):
        if side == "left":
            return side_lane(visible[0], theme, side)
        if side == "right":
            return side_lane(visible[-1], theme, side)
        # Top and bottom: the lane band every child leaves free at that
        # edge. A top-aligned row lines its content up below the deepest
        # top lane, so that lane spans the row; otherwise only the
        # shallowest lane is sure to (a shorter child sits inside).
        lanes, wires = [], {}
        for c in visible:
            l, w = side_lane(c, theme, side)
            lanes.append(l)
            wires.update(w)
        deepest = side == "top" and child.align in ("start", "stretch")
        return (max(lanes) if deepest else min(lanes)), wires
    return 0.0, {}


def pair_need(a, b, theme: Theme, axis: str) -> Tuple[float, float, float]:
    """``(need, lane_a, lane_b)`` of the gutter between ``a`` and ``b``.

    ``b`` follows ``a`` along ``axis`` (``"x"``: right of it, ``"y"``:
    below it). ``need`` is the content-to-content distance the wires in
    that gutter require.
    """
    far, near = ("right", "left") if axis == "x" else ("bottom", "top")
    la, wa = side_lane(a, theme, far)
    lb, wb = side_lane(b, theme, near)
    shared = wa.keys() & wb.keys()
    if not shared:
        return la + lb, la, lb
    facing = max(max(wa[k][1], wb[k][1]) for k in shared)

    def rest(lane, wires):
        # The part of a lane other wires run in. A lane wider than every
        # itemised end holds something nobody itemised: keep it whole.
        recorded = max((v[0] for v in wires.values()), default=0.0)
        if lane > recorded + 1e-6:
            return lane
        return min(lane, max((v[0] for k, v in wires.items()
                              if k not in shared), default=0.0))

    return max(facing, rest(la, wa) + rest(lb, wb)), la, lb


class Rhythm:
    """One gutter shared by every gap it spaces.

    Parameters
    ----------
    gap : str or float
        The beat: a spacing token (``"sm"``, ``"md"``, ...) or a number
        of pixels. The shared gutter is never narrower than this, and
        widens to the largest lane need among the member pairs.

    Pass the same object as ``gap=`` to every :class:`~sciviz.Row` (or
    every :class:`~sciviz.Column`) whose gutters should be one beat::

        cards = Rhythm("md")
        Row(Anchor("a", A), Anchor("b", B), Anchor("c", C), gap=cards)

    Only Row and Column accept a Rhythm.
    """

    def __init__(self, gap: Union[str, float] = "md"):
        if isinstance(gap, bool) or not isinstance(gap, (str, Real)):
            raise TypeError(
                f"Rhythm(gap={gap!r}): expected a spacing token or a number")
        self.gap = gap
        # Held weakly, and one member per run of children: a composite
        # that builds a fresh Row or Column around the same children on
        # every measure (and forwards its gap) replaces its previous
        # container instead of adding one, and a dropped container
        # leaves the beat. The membership never grows with repeated
        # measures, whatever keeps old containers alive.
        self._members = weakref.WeakSet()
        self._axis = None

    def __deepcopy__(self, memo):
        # A copied tree is a figure of its own: the copy starts with no
        # members and each copied container joins it as it is rebuilt
        # (see :meth:`_rejoin`), so a trial copy is spaced by its own
        # lanes, never by the containers of the tree it was copied from.
        dup = Rhythm(self.gap)
        dup._axis = self._axis
        memo[id(self)] = dup
        return dup

    def _join(self, container, axis: str) -> None:
        if self._axis is not None and axis != self._axis:
            raise ValueError(
                "A Rhythm spaces one axis: this one already spaces a "
                f"{'Row' if self._axis == 'x' else 'Column'}. Use one "
                "Rhythm for rows and another for columns.")
        self._axis = axis
        kids = list(getattr(container, "children", ()))
        for member in list(self._members):
            if member is container:
                continue
            other = getattr(member, "children", ())
            if (len(other) == len(kids)
                    and all(a is b for a, b in zip(other, kids))):
                self._members.discard(member)
        self._members.add(container)

    @staticmethod
    def _rejoin(container, state: dict, axis: str) -> None:
        """Restore a copied (or unpickled) container and join its Rhythm.

        Containers call this from ``__setstate__``: the constructor, which
        joins, does not run when an object is copied.
        """
        container.__dict__.update(state)
        gap = state.get("gap")
        if isinstance(gap, Rhythm):
            gap._join(container, axis)

    @staticmethod
    def _visible(container) -> list:
        return [c for c in container.children
                if not getattr(c, "is_layout_invisible", False)]

    def gutter(self, theme: Theme) -> float:
        """The shared content-to-content gutter under ``theme``.

        Reused within one render while nothing that could change it has
        been written (see :func:`~sciviz.core._measure_memo.memo_value`).
        """
        from ..core._measure_memo import memo_value

        def compute():
            g = theme.gap_px(self.gap)
            for member in list(self._members):
                vis = self._visible(member)
                for a, b in zip(vis, vis[1:]):
                    g = max(g, pair_need(a, b, theme, self._axis)[0])
            return g
        return memo_value(self, ("gutter", len(self._members)), theme,
                          compute)

    def spacings(self, container, theme: Theme,
                 lanes=None) -> List[float]:
        """Box-to-box spacing after each visible child of ``container``.

        The gutter minus the empty bands the two neighbours already carry
        between their box (or slot) edge and their content, so their
        content boxes sit exactly one gutter apart. ``lanes`` lists those
        ``(lead, trail)`` bands per visible child as the container places
        it (default: the children's flow lanes). A spacing can be
        negative: the empty lane bands of two neighbours overlap. The
        list has one entry per visible child (the last is ``0``).
        """
        G = self.gutter(theme)
        vis = self._visible(container)
        if lanes is None:
            near, far = (("left", "right") if self._axis == "x"
                         else ("top", "bottom"))
            lanes = [(side_lane(c, theme, near)[0],
                      side_lane(c, theme, far)[0]) for c in vis]
        out = [G - lanes[i][1] - lanes[i + 1][0]
               for i in range(len(vis) - 1)]
        return out + [0.0] if vis else []
