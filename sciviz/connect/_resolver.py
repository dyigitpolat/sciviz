"""Implicit resolver: container that collects pending ``Connect`` specs.

This is the lifted-up version of the old ``Flowed``. It's automatically
installed by ``Diagram.render`` wrapping the body, so authors never need
to wrap their subtree in ``Flowed(...)`` themselves.

Mechanics (mirroring ``Flowed``):

1. Pre-measure pass scans the subtree and calls
   :meth:`Flow._bump_margin` / :meth:`Bus`-equivalent on anchors so each
   connection has visible space.
2. During render, a fresh registry is pushed on the anchor context-var
   stack so ``Anchor`` registers its children into it.
3. Pending ``Connect``/``Bus`` specs are collected as the tree renders
   (via :func:`push_pending_connection`).
4. After the child renders, each pending spec is dispatched to its
   ``_render`` method with the registry.
"""
from __future__ import annotations

import contextvars as _cv
from typing import List, Optional, Union

from ..core import BBox, Canvas, Element, Theme
from ..composition import Anchor, Flow, Bus, _anchor_stack
from ..composition._flow import _assign_edge_shares


Pending = Union[Flow, Bus]


_pending_stack: _cv.ContextVar = _cv.ContextVar("_connect_pending_stack", default=None)


def push_pending_connection(spec: Pending) -> None:
    """Record a pending ``Flow``/``Bus`` on the innermost resolver."""
    stack = _pending_stack.get()
    if stack:
        stack[-1].append(spec)


def _collect_anchors(elem, out):
    """Walk the tree and index every ``Anchor`` by its name."""
    if isinstance(elem, Anchor):
        out.setdefault(elem.name, elem)
    for attr in ("children",):
        children = getattr(elem, attr, None)
        if children is not None:
            for c in children:
                if c is not None:
                    _collect_anchors(c, out)
    # Transparent semantic wrappers use different names for their primary
    # element.  Connector discovery must follow all of them; otherwise an
    # Anchor inside Card.body or Banner.body silently disappears.
    for attr in (
        "child", "body", "header", "footer", "above", "below",
        "decoration", "source",
    ):
        child = getattr(elem, attr, None)
        if isinstance(child, Element):
            _collect_anchors(child, out)
    # Connect holds auto-wrapped anchors in _wrapped.
    wrapped = getattr(elem, "_wrapped", None)
    if wrapped:
        for a in wrapped:
            if a is not None:
                _collect_anchors(a, out)
    cols = getattr(elem, "columns", None)
    if isinstance(cols, list):
        for col in cols:
            if isinstance(col, dict):
                for key, val in col.items():
                    if isinstance(key, str) and key.startswith("_"):
                        continue
                    if isinstance(val, Element):
                        _collect_anchors(val, out)


def _collect_pending(elem, out):
    """Walk the tree and collect all ``Connect`` routed/bus placeholders."""
    from .routed import _RoutedConnect
    from .bus import _BusConnect
    from .connector import Connect
    if isinstance(elem, (_RoutedConnect, _BusConnect)):
        out.append(elem)
    elif isinstance(elem, Connect):
        impl = getattr(elem, "_impl", None)
        if isinstance(impl, (_RoutedConnect, _BusConnect)):
            out.append(impl)
    for attr in ("children",):
        children = getattr(elem, attr, None)
        if children is not None:
            for c in children:
                if c is not None:
                    _collect_pending(c, out)
    for attr in (
        "child", "body", "header", "footer", "above", "below",
        "decoration", "source",
    ):
        child = getattr(elem, attr, None)
        if isinstance(child, Element):
            _collect_pending(child, out)
    cols = getattr(elem, "columns", None)
    if isinstance(cols, list):
        for col in cols:
            if isinstance(col, dict):
                for key, val in col.items():
                    if isinstance(key, str) and key.startswith("_"):
                        continue
                    if isinstance(val, Element):
                        _collect_pending(val, out)


def _facing_extent_for(spec, src, dst, theme) -> float:
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


class _FlowResolver(Element):
    """Wrap a child; resolve any ``Connect`` routed/bus specs after render.

    The element is a strict superset of the old ``Flowed``: any declarative
    ``flows=`` list is still honoured, and any ``Connect`` placeholder found
    in the subtree is also rendered at the end.
    """

    def __init__(self, child: Element, *,
                 min_flow_space: Optional[float] = None):
        self.child = child
        self.min_flow_space = min_flow_space
        self._margins_applied = False

    def _flow_space(self, theme: Theme) -> float:
        """Theme-proportional default wire margin (10 px at unit=6)."""
        if self.min_flow_space is not None:
            return float(self.min_flow_space)
        return theme.unit * (5.0 / 3.0)

    def _specs_from_tree(self) -> List[Pending]:
        pending: list = []
        _collect_pending(self.child, pending)
        return [p._flow if hasattr(p, "_flow") else p._bus for p in pending]

    def _apply_flow_margins(self, theme: Theme):
        if self._margins_applied:
            return
        self._margins_applied = True
        anchors: dict = {}
        _collect_anchors(self.child, anchors)
        m = self._flow_space(theme)
        # Auto-sided flows don't know which face will be chosen until
        # render-time -- by then layout is frozen. Reserve a lighter
        # margin on every face so the router always has at least a few
        # pixels of breathing room, regardless of the picked side.
        auto_m = m * 0.5
        from ..composition._flow import label_corridor_reservation
        for spec in self._specs_from_tree():
            if isinstance(spec, Flow):
                src = anchors.get(spec.src)
                dst = anchors.get(spec.dst)
                # A connector label needs a readable corridor in addition
                # to the arrow shaft itself. The reservation is sized from
                # the *measured* caption (see label_corridor_reservation):
                # labels are part of the route contract, so the corridor
                # between two facing pinned sides must fit the caption.
                flow_auto = auto_m * (1.6 if spec.label else 1.0)
                if src is not None:
                    if spec.src_side != "auto":
                        src._bump_margin(
                            spec.src_side,
                            label_corridor_reservation(
                                spec, theme, spec.src_side,
                                spec.dst_side, m,
                                _facing_extent_for(spec, src, dst, theme)))
                    else:
                        for side in ("top", "bottom", "left", "right"):
                            src._bump_margin(side, flow_auto)
                if dst is not None:
                    if spec.dst_side != "auto":
                        dst._bump_margin(
                            spec.dst_side,
                            label_corridor_reservation(
                                spec, theme, spec.dst_side,
                                spec.src_side, m,
                                _facing_extent_for(spec, src, dst, theme)))
                    else:
                        for side in ("top", "bottom", "left", "right"):
                            dst._bump_margin(side, flow_auto)
            elif isinstance(spec, Bus):
                label_mul = 1.6 if spec.label else 1.0
                bump = m * label_mul
                # Arrowheads land on the SINKS, and the gap one arrows
                # into must be able to hold a visible arrow: head plus
                # shaft. Without this floor the spine lands a point or
                # two from the sink's edge and the fan-in terminates in
                # a triangle glued to the border. Sources carry no head,
                # so they keep the thin spine clearance -- reserving the
                # stub on every member would pay for arrows that are
                # never drawn.
                stub = theme.arrow_stub_px if spec.arrow else 0.0
                # A bus member only needs enough room for its own tap to
                # leave its edge. The spine itself sits in the gap
                # BETWEEN the two clusters, which is a layout gap -- so
                # charging every member the full spine budget on both
                # faces inflates a stack of tags by its own height again
                # for clearance nothing uses.
                member = m * 0.3
                if spec.orientation == "auto":
                    light = m * (0.6 if spec.label else 0.3)
                    sides = ("top", "bottom", "left", "right")
                    for name in spec.sources:
                        a = anchors.get(name)
                        if a is not None:
                            for side in sides:
                                a._bump_margin(side, light)
                    for name in spec.sinks:
                        a = anchors.get(name)
                        if a is not None:
                            for side in sides:
                                a._bump_margin(side, max(light, stub))
                elif spec.orientation == "horizontal":
                    sink_bump = max(bump, stub)
                    for name in spec.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", member)
                        a._bump_margin("right", member)
                    for name in spec.sinks:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", sink_bump)
                        a._bump_margin("right", sink_bump)
                else:  # vertical
                    sink_bump = max(bump, stub)
                    for name in spec.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("top", member)
                        a._bump_margin("bottom", member)
                    for name in spec.sinks:
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
        anchor_token = _anchor_stack.set(new_stack)

        pending_list: list = []
        pending_existing = _pending_stack.get()
        pending_stack = (list(pending_existing) if pending_existing else []) + [pending_list]
        pending_token = _pending_stack.set(pending_stack)

        try:
            self.child.render(canvas, x, y, theme)
        finally:
            _anchor_stack.reset(anchor_token)
            _pending_stack.reset(pending_token)

        # Share-edge assignment for adjacent routed flows on the same edge
        # (mirrors Flowed._assign_edge_shares).
        self._assign_edge_shares(pending_list, my_registry)

        # Two-phase resolution: draw every wire first, then place every
        # label. Each label therefore sees the complete set of wires --
        # not merely the ones that happened to be drawn before it -- so
        # captions never straddle a later crossing.
        label_passes = []
        for spec in pending_list:
            finish = spec._render(canvas, theme, my_registry,
                                  defer_label=True)
            if callable(finish):
                label_passes.append(finish)
        for finish in label_passes:
            finish()

    def _assign_edge_shares(self, pending: list, registry: dict) -> None:
        _assign_edge_shares(pending, registry)


# Re-export the Anchor stack's context var so the resolver plays nicely
# with the existing Flowed machinery.
__all__ = ["_FlowResolver", "push_pending_connection"]
