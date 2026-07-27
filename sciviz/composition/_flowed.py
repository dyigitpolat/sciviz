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
from ._flow import Flow, Labeled, _assign_edge_shares


def _facing_extent_for(flow, src, dst, theme) -> float:
    """Size of the narrower node a facing corridor separates.

    Mirrors ``Flow._neighbour_extent`` at margin-application time, where
    only the anchors (not their rendered boxes) are available, so the
    corridor cap is the same number in both passes.
    """
    if src is None or dst is None:
        return 0.0
    a = src.child.measure(theme)
    b = dst.child.measure(theme)
    return float(min(a.w, b.w, a.h, b.h))


def _facing_extent_for(spec, src, dst, theme) -> float:
    """``_facing_extent`` on the axis the corridor actually runs."""
    if src is None or dst is None:
        return 0.0
    a = src.child.measure(theme)
    b = dst.child.measure(theme)
    sides = {spec.src_side, spec.dst_side}
    if sides == {"left", "right"}:
        return float(min(a.w, b.w))
    if sides == {"top", "bottom"}:
        return float(min(a.h, b.h))
    return float(min(a.w, b.w, a.h, b.h))


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
        for attr in (
            "child", "body", "header", "footer", "above", "below",
            "decoration", "source",
        ):
            child = getattr(elem, attr, None)
            if isinstance(child, Element):
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
        from ._flow import label_corridor_reservation
        for flow in self.flows:
            if isinstance(flow, Flow):
                src = anchors.get(flow.src)
                dst = anchors.get(flow.dst)
                # If the flow's side is "auto", skip margin inflation --
                # we don't know which boundary the flow will attach to.
                # Pinned sides reserve caption-sized corridors (labels
                # are part of the route contract).
                if src is not None and flow.src_side != "auto":
                    src._bump_margin(
                        flow.src_side,
                        label_corridor_reservation(
                            flow, theme, flow.src_side, flow.dst_side, m))
                if dst is not None and flow.dst_side != "auto":
                    dst._bump_margin(
                        flow.dst_side,
                        label_corridor_reservation(
                            flow, theme, flow.dst_side, flow.src_side, m))
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
                # Arrowheads land on the sinks; only those need room for
                # a head plus a visible shaft.
                stub = theme.arrow_stub_px if flow.arrow else 0.0
                if flow.orientation == "auto":
                    # Unlabelled buses need only a thin gap for the spine,
                    # and we can't predict orientation yet -- bump every
                    # face by a very small amount so the spine always has
                    # some room, but don't spread the whole diagram.
                    light = m * (0.6 if flow.label else 0.3)
                    sides = ("top", "bottom", "left", "right")
                    for name in flow.sources:
                        a = anchors.get(name)
                        if a is not None:
                            for side in sides:
                                a._bump_margin(side, light)
                    for name in flow.sinks:
                        a = anchors.get(name)
                        if a is not None:
                            for side in sides:
                                a._bump_margin(side, max(light, stub))
                elif flow.orientation == "horizontal":
                    sink_bump = max(bump, stub)
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
                        a._bump_margin("left", sink_bump)
                        a._bump_margin("right", sink_bump)
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
                        a._bump_margin("top", sink_bump)
                        a._bump_margin("bottom", sink_bump)

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
        # Two-phase: wires first, labels after (see connect._resolver).
        label_passes = []
        for flow in self.flows:
            finish = flow._render(canvas, theme, my_registry,
                                  defer_label=True)
            if callable(finish):
                label_passes.append(finish)
        for finish in label_passes:
            finish()

    def _assign_edge_shares(self, registry: dict) -> None:
        _assign_edge_shares(self.flows, registry)


# ---------------------------------------------------------------------------
# MatchSize -- container that equalises children along an axis
# ---------------------------------------------------------------------------
