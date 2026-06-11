"""Flowed: container that resolves :class:`Flow` / :class:`Bus` specs
against the tree's registered :class:`Anchor` bboxes.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text, TextBlock
from ..layout import Row, Column, Spacer
from ._anchor import Anchor, _anchor_stack, _side_point, _side_point_frac
from ._bus import Bus
from ._flow import Flow, Labeled

class Flowed(Element):
    """Render ``child`` and overlay :class:`Flow` arrows between named anchors.

    Use with :class:`Anchor` to tag the elements you want to connect::

        diagram = Flowed(
            child=Row(
                Anchor("ae", action_encoder),
                Anchor("dt", diffusion_transformer),
            ),
            flows=[Flow("ae", "dt", src_side="bottom", dst_side="bottomright")],
        )

    Before rendering, Flowed runs a *pre-pass* that walks the child tree,
    finds all named anchors, and inflates their margins according to the
    flows that reference them.  This ensures every flow has visible space
    for its arrow shaft without the author having to tune Row/Column gaps
    by hand.  The ``min_flow_space`` parameter controls how much margin
    is added on the flow-connecting side.  The default (``None``)
    resolves to ``theme.unit * 5/3`` at measure time -- 10 px per side
    on the default theme, i.e. ~20 extra px between two horizontally-
    connected siblings -- so layout-compressed paper themes keep
    proportional wire space instead of a fixed pixel tax.
    """

    def __init__(self, child: Element, flows: Sequence = (),
                 min_flow_space: Optional[float] = None):
        self.child = child
        self.flows = list(flows)
        self.min_flow_space = min_flow_space
        self._margins_applied = False

    def _flow_space(self, theme: Theme) -> float:
        if self.min_flow_space is not None:
            return float(self.min_flow_space)
        return theme.unit * (5.0 / 3.0)

    def _collect_anchors(self, elem, out):
        if isinstance(elem, Anchor):
            out.setdefault(elem.name, elem)
        # Recurse into common container attributes.  This covers Row, Column,
        # Stack, BlockGroup, Region, Padded, Framed, FixedSize, etc.
        for attr in ("children",):
            children = getattr(elem, attr, None)
            if children is not None:
                for c in children:
                    if c is not None:
                        self._collect_anchors(c, out)
        for attr in ("child",):
            child = getattr(elem, attr, None)
            if child is not None:
                self._collect_anchors(child, out)
        # Grid stores cells in a list of dicts keyed by row name -- recurse
        # into every value (including tuple-keyed spanning cells).
        cols = getattr(elem, "columns", None)
        if isinstance(cols, list):
            for col in cols:
                if isinstance(col, dict):
                    for key, val in col.items():
                        if isinstance(key, str) and key.startswith("_"):
                            continue
                        if isinstance(val, Element):
                            self._collect_anchors(val, out)

    def _apply_flow_margins(self, theme: Theme):
        if self._margins_applied:
            return
        self._margins_applied = True
        anchors: dict = {}
        self._collect_anchors(self.child, anchors)
        m = self._flow_space(theme)
        for flow in self.flows:
            if isinstance(flow, Flow):
                src = anchors.get(flow.src)
                dst = anchors.get(flow.dst)
                # If the flow's side is "auto", skip margin inflation --
                # we don't know which boundary the flow will attach to.
                if src is not None and flow.src_side != "auto":
                    src._bump_margin(flow.src_side, m)
                if dst is not None and flow.dst_side != "auto":
                    dst._bump_margin(flow.dst_side, m)
            elif isinstance(flow, Bus):
                # A Bus chooses its orientation (horizontal or vertical
                # spine) at render time based on measured positions; at
                # margin-application time we inflate based on the hint.
                # Labelled buses need a bit more space for the side label
                # but over-inflation balloons the whole diagram, so we
                # add only ``min_flow_space`` per side (same budget as a
                # pairwise Flow), scaled up slightly when the bus carries
                # a label.
                label_mul = 1.6 if flow.label else 1.0
                bump = m * label_mul
                if flow.orientation == "auto":
                    # Unlabelled buses need only a thin gap for the spine,
                    # and we can't predict orientation yet -- bump every
                    # face by a very small amount so the spine always has
                    # some room, but don't spread the whole diagram.
                    light = m * (0.6 if flow.label else 0.3)
                    sides = ("top", "bottom", "left", "right")
                    for name in list(flow.sources) + list(flow.sinks):
                        a = anchors.get(name)
                        if a is None:
                            continue
                        for side in sides:
                            a._bump_margin(side, light)
                elif flow.orientation == "horizontal":
                    # Spine is vertical, between a source cluster on one
                    # side and a sink cluster on the other; source's
                    # left/right and sinks' opposite edges carry the gap.
                    for name in flow.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", bump)
                        a._bump_margin("right", bump)
                    for name in flow.sinks:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", bump)
                        a._bump_margin("right", bump)
                else:  # vertical -- spine is horizontal
                    for name in flow.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("top", bump)
                        a._bump_margin("bottom", bump)
                    for name in flow.sinks:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("top", bump)
                        a._bump_margin("bottom", bump)

    def measure(self, theme: Theme) -> BBox:
        self._apply_flow_margins(theme)
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._apply_flow_margins(theme)
        my_registry: dict = {}
        existing = _anchor_stack.get()
        new_stack = (list(existing) if existing else []) + [my_registry]
        token = _anchor_stack.set(new_stack)
        try:
            self.child.render(canvas, x, y, theme)
        finally:
            _anchor_stack.reset(token)
        self._assign_edge_shares(my_registry)
        for flow in self.flows:
            flow._render(canvas, theme, my_registry)

    def _assign_edge_shares(self, registry: dict) -> None:
        """Distribute multiple flows that attach to the same anchor edge
        along that edge, instead of piling them onto the midpoint.

        Groups flows by ``(anchor_name, resolved_side)`` and assigns
        fractional taps evenly: ``(i+1)/(n+1)`` for a group of ``n``.
        Within a group, flows are ordered by the *other* endpoint's
        perpendicular coordinate so neighbouring attachments correspond
        to neighbouring counterparts -- e.g. two flows entering a box's
        top from the left and right get their taps on the left and
        right of that top edge respectively.
        """
        flow_endpoints = []
        for flow in self.flows:
            if not isinstance(flow, Flow):
                continue
            sb = registry.get(flow.src)
            db = registry.get(flow.dst)
            if sb is None or db is None:
                continue
            src_side = (flow._auto_side(sb, db)
                        if flow.src_side == "auto" else flow.src_side)
            dst_side = (flow._auto_side(db, sb)
                        if flow.dst_side == "auto" else flow.dst_side)
            flow_endpoints.append((flow, sb, db, src_side, dst_side))

        buckets: dict = {}
        for entry in flow_endpoints:
            flow, sb, db, src_side, dst_side = entry
            buckets.setdefault((flow.src, src_side), []).append(
                ("src", entry))
            buckets.setdefault((flow.dst, dst_side), []).append(
                ("dst", entry))

        for (anchor_name, side), members in buckets.items():
            if len(members) <= 1:
                # Single flow on this edge -- keep the midpoint default.
                for role, entry in members:
                    flow, sb, db, ssd, dsd = entry
                    if role == "src":
                        flow._share_src_frac = 0.5
                    else:
                        flow._share_dst_frac = 0.5
                continue

            def sort_key(m):
                role, entry = m
                flow, sb, db, ssd, dsd = entry
                other = db if role == "src" else sb
                ox, oy, ow, oh = other
                return (ox + ow / 2) if side in ("top", "bottom") else (oy + oh / 2)

            members.sort(key=sort_key)
            n = len(members)
            for i, (role, entry) in enumerate(members):
                flow, sb, db, ssd, dsd = entry
                frac = (i + 1) / (n + 1)
                if role == "src":
                    flow._share_src_frac = frac
                else:
                    flow._share_dst_frac = frac


# ---------------------------------------------------------------------------
# MatchSize -- container that equalises children along an axis
# ---------------------------------------------------------------------------


