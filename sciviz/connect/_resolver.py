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
    for attr in ("child",):
        child = getattr(elem, attr, None)
        if child is not None:
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
    for attr in ("child",):
        child = getattr(elem, attr, None)
        if child is not None:
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
        for spec in self._specs_from_tree():
            if isinstance(spec, Flow):
                src = anchors.get(spec.src)
                dst = anchors.get(spec.dst)
                if src is not None:
                    if spec.src_side != "auto":
                        src._bump_margin(spec.src_side, m)
                    else:
                        for side in ("top", "bottom", "left", "right"):
                            src._bump_margin(side, auto_m)
                if dst is not None:
                    if spec.dst_side != "auto":
                        dst._bump_margin(spec.dst_side, m)
                    else:
                        for side in ("top", "bottom", "left", "right"):
                            dst._bump_margin(side, auto_m)
            elif isinstance(spec, Bus):
                label_mul = 1.6 if spec.label else 1.0
                bump = m * label_mul
                if spec.orientation == "auto":
                    light = m * (0.6 if spec.label else 0.3)
                    sides = ("top", "bottom", "left", "right")
                    for name in list(spec.sources) + list(spec.sinks):
                        a = anchors.get(name)
                        if a is None:
                            continue
                        for side in sides:
                            a._bump_margin(side, light)
                elif spec.orientation == "horizontal":
                    for name in spec.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", bump)
                        a._bump_margin("right", bump)
                    for name in spec.sinks:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("left", bump)
                        a._bump_margin("right", bump)
                else:  # vertical
                    for name in spec.sources:
                        a = anchors.get(name)
                        if a is None:
                            continue
                        a._bump_margin("top", bump)
                        a._bump_margin("bottom", bump)
                    for name in spec.sinks:
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

        for spec in pending_list:
            spec._render(canvas, theme, my_registry)

    def _assign_edge_shares(self, pending: list, registry: dict) -> None:
        flow_endpoints = []
        for spec in pending:
            flow = getattr(spec, "_flow", None) if not isinstance(spec, Flow) else spec
            if flow is None:
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
            buckets.setdefault((flow.src, src_side), []).append(("src", entry))
            buckets.setdefault((flow.dst, dst_side), []).append(("dst", entry))

        for (anchor_name, side), members in buckets.items():
            if len(members) <= 1:
                for role, entry in members:
                    flow = entry[0]
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
                flow = entry[0]
                frac = (i + 1) / (n + 1)
                if role == "src":
                    flow._share_src_frac = frac
                else:
                    flow._share_dst_frac = frac


# Re-export the Anchor stack's context var so the resolver plays nicely
# with the existing Flowed machinery.
__all__ = ["_FlowResolver", "push_pending_connection"]
