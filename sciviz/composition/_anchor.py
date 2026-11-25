"""Anchor: register a child's rendered bbox under a name.

Exposes the ``_anchor_stack`` ContextVar and the ``_side_point`` /
``_side_point_frac`` geometry helpers used by :class:`Flow` and
:class:`Bus` to tap arrow endpoints onto named edges.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

from ..core._routing_context import routing_registry_stack as _anchor_stack


#: Registry key prefix under which :class:`Anchor` records the body
#: ports (``{side: (x, y, w, h)}``) of a child whose ``port_bbox``
#: differs from its layout box.
PORT_PREFIX = "__port_"


class Anchor(Element):
    """Wrap a child and register its rendered bbox under a name.

    The author tags elements they want to draw flows between::

        Anchor("ae", encoder_box)

    A surrounding :class:`Flowed` then routes :class:`Flow` arrows between
    the named anchors.  The author writes no coordinates by hand.

    Anchors also carry per-side *margins* (default 0) that are added to
    the anchor's bbox in layout.  :class:`Flowed` automatically inflates
    these margins for flow-connected anchors during a pre-measure pass
    so every Flow has visible space for its arrow shaft.  The arrow
    endpoints remain at the *child's* boundary, not the padded bbox --
    registration records the child's true position.
    """

    def __init__(self, name: str, child: Element, *,
                 margin_left: float = 0.0,
                 margin_right: float = 0.0,
                 margin_top: float = 0.0,
                 margin_bottom: float = 0.0):
        self.name = name
        self.child = child
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        return BBox(b.w + self.margin_left + self.margin_right,
                    b.h + self.margin_top + self.margin_bottom)

    @property
    def absorbs_main_axis_stretch(self) -> bool:
        """An anchor is transparent to the grow protocol: it absorbs a
        parent column's surplus height when the wrapped child does."""
        return bool(getattr(self.child, "absorbs_main_axis_stretch", False))

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Forward inflate requests to the wrapped child, accounting for
        the anchor's own margins. The Anchor's outer bbox grows because
        the child grows; the registered anchor still tracks the child."""
        adj_w = max(0.0, min_w - self.margin_left - self.margin_right)
        adj_h = max(0.0, min_h - self.margin_top - self.margin_bottom)
        self.child.inflate_to(adj_w, adj_h)

    def stretch_decoration(self, theme: Theme) -> tuple[float, float]:
        """Immovable outer decoration (w, h) preserved by cross-axis
        stretch: the anchor's flow-lane margins. A stretch container
        equalises the *painted faces* of its children; margined anchors
        therefore receive their face target plus these margins."""
        return (self.margin_left + self.margin_right,
                self.margin_top + self.margin_bottom)

    def stretch_decoration_sides(self, theme: Theme
                                 ) -> tuple[float, float, float, float]:
        """Per-side split of :meth:`stretch_decoration` (left, right,
        top, bottom). Flow-lane margins are asymmetric by nature (a
        feedback corridor lives on ONE side), and a stretch container
        needs the split to co-locate painted faces: every sibling's
        face starts past the widest same-side corridor, so the corridor
        is a real container-level lane instead of a per-child indent."""
        return (self.margin_left, self.margin_right,
                self.margin_top, self.margin_bottom)

    def frame_bbox(self, theme: Theme):
        """The wrapped child's wall rectangle (the ``frame_bbox``
        protocol: a region titled on its border line), translated past
        the anchor's margins; ``None`` when the child declares none. An
        anchor is transparent to it, so a named region aligns and
        equalises on its walls like a bare one."""
        fn = getattr(self.child, "frame_bbox", None)
        frame = fn(theme) if fn is not None else None
        if frame is None:
            return None
        fx, fy, fw, fh = frame
        return (self.margin_left + fx, self.margin_top + fy, fw, fh)

    def wall_overhang(self, theme: Theme) -> tuple[float, float]:
        """The wrapped child's overhang (top, bottom) outside its walls
        (the ``wall_overhang`` protocol), where it reaches the anchor's
        own edge: a flow-lane margin on a side keeps its room, so nothing
        rides in a neighbour's gap past it."""
        fn = getattr(self.child, "wall_overhang", None)
        if fn is None:
            return 0.0, 0.0
        top, bottom = fn(theme)
        return (top if self.margin_top <= 0.0 else 0.0,
                bottom if self.margin_bottom <= 0.0 else 0.0)

    def content_bbox(self, theme: Theme):
        """The inner child bbox, excluding margins.  Layout containers use
        this to align siblings on their *content* box, not on the
        margin-inflated outer box -- so asymmetric flow-margin bumps
        don't shift the rendered child.

        When the child itself exposes a narrower content (e.g.
        ``StackedBoxes`` whose content_bbox is the FRONT face), inherit
        that so that Anchor doesn't undo the child's own content-vs-outer
        distinction.
        """
        child_cb = self.child.content_bbox(theme)
        cx, cy, cw, ch = child_cb
        return (self.margin_left + cx, self.margin_top + cy, cw, ch)

    def primary_anchor_bbox(self, theme: Theme):
        """Delegate to the child's primary anchor (if any), translated
        into our local frame; otherwise fall back to the child's content
        bbox.  This lets composites like ``Anchor(StackedBoxes(...))``
        expose the stack's FRONT FACE as the primary anchor, so Grid
        centres columns on the visible face rather than the silhouette.
        """
        pa = self.child.primary_anchor_bbox(theme)
        if pa is not None:
            px, py, pw, ph = pa
            return (self.margin_left + px, self.margin_top + py, pw, ph)
        return self.content_bbox(theme)

    def port_bbox(self, theme: Theme, side: str):
        """The child's body port on ``side`` (see
        :meth:`Element.port_bbox`), translated past the anchor margins."""
        port = self.child.port_bbox(theme, side)
        if port is None:
            return None
        px, py, pw, ph = port
        return (self.margin_left + px, self.margin_top + py, pw, ph)

    def iter_primary_anchors(self, theme: Theme):
        out = []
        for px, py, pw, ph in self.child.iter_primary_anchors(theme):
            out.append((self.margin_left + px, self.margin_top + py, pw, ph))
        return out

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b = self.child.measure(theme)
        child_x = x + self.margin_left
        child_y = y + self.margin_top
        # Register the CHILD's position, not the padded anchor bbox, so
        # flow endpoints land on the child's actual boundary.
        layout = (child_x, child_y, b.w, b.h)
        stack = _anchor_stack.get()
        ports = {}
        if stack is not None:
            for side in ("top", "bottom", "left", "right"):
                port = self.child.port_bbox(theme, side)
                if port is None:
                    continue
                px, py, pw, ph = port
                box = (child_x + px, child_y + py, pw, ph)
                if box != layout:
                    ports[side] = box
            for reg in stack:
                reg[self.name] = layout
        ink = getattr(canvas, "ink_items", None)
        first_ink = len(ink()) if (ports and ink is not None) else 0
        self.child.render(canvas, child_x, child_y, theme)
        if ports:
            # Body ports ride beside the layout box: obstacles, flow
            # margins and label obstacles keep the layout box, and only
            # the tap point moves onto the drawing. A side whose run out
            # to the layout edge crosses the child's OWN ink (a caption,
            # a bypass arc) keeps the layout box.
            own = ink()[first_ink:] if ink is not None else []
            for side in list(ports):
                blocked = _blocked_spans(layout, ports[side], side, own)
                if blocked:
                    ports[blocked_key(side)] = blocked
            if ports:
                for reg in stack:
                    reg[PORT_PREFIX + self.name] = ports

    def _bump_margin(self, side: str, amount: float) -> None:
        if side in ("left",):
            self.margin_left = max(self.margin_left, amount)
        elif side in ("right",):
            self.margin_right = max(self.margin_right, amount)
        elif side in ("top", "topleft", "topright"):
            self.margin_top = max(self.margin_top, amount)
        elif side in ("bottom", "bottomleft", "bottomright"):
            self.margin_bottom = max(self.margin_bottom, amount)


def blocked_key(side: str) -> str:
    """Key under which an anchor's port record lists the stretches of
    ``side`` whose run out to the layout edge crosses the child's own ink."""
    return side + "_blocked"


def _blocked_spans(layout, port, side: str, ink):
    """Stretches ``(lo, hi)`` along ``side`` where the run from ``port``
    out to the ``layout`` edge crosses the child's own ``ink`` (an outside
    label, a frame tab, a caption). A wire tapping there stops at the
    layout edge instead of cutting through that text."""
    if not _run_crosses_ink(layout, port, side, ink):
        return []
    px, py, pw, ph = port
    lx, ly, lw, lh = layout
    horizontal = side in ("top", "bottom")
    lo, hi = (px, px + pw) if horizontal else (py, py + ph)
    strip = {"left": (lx, px), "right": (px + pw, lx + lw),
             "top": (ly, py), "bottom": (py + ph, ly + lh)}[side]
    out = []
    for (x0, y0, x1, y1, *_kind) in ink:
        a0, a1, c0, c1 = (x0, x1, y0, y1) if horizontal else (y0, y1, x0, x1)
        if min(c1, strip[1]) - max(c0, strip[0]) > 0.5 \
                and min(a1, hi) - max(a0, lo) > 0.5:
            out.append((max(a0, lo), min(a1, hi)))
    return sorted(out)


def _run_crosses_ink(layout, port, side: str, ink) -> bool:
    """Whether the strip between ``port``'s ``side`` and ``layout``'s
    crosses any of the ``(x0, y0, x1, y1, kind)`` ink items."""
    px, py, pw, ph = port
    lx, ly, lw, lh = layout
    strip = {"left": (lx, py, px, py + ph),
             "right": (px + pw, py, lx + lw, py + ph),
             "top": (px, ly, px + pw, py),
             "bottom": (px, py + ph, px + pw, ly + lh)}.get(side)
    if strip is None:
        return True
    sx0, sy0, sx1, sy1 = strip
    if sx1 - sx0 <= 0.5 or sy1 - sy0 <= 0.5:
        return False
    eps = 0.5
    return any(min(x1, sx1) - max(x0, sx0) > eps
               and min(y1, sy1) - max(y0, sy0) > eps
               for (x0, y0, x1, y1, *_kind) in ink)


def port_face(registry: dict, name: str, side: str):
    """The box a wire to anchor ``name`` lands on at ``side``: the body
    port :class:`Anchor` recorded, else the registered layout box."""
    ports = registry.get(PORT_PREFIX + name)
    if ports and side in ports:
        return ports[side]
    return registry.get(name)


def _side_point(bbox, side: str):
    """Return (x, y) on a named side of an (x, y, w, h) bbox.

    Sides: ``top, bottom, left, right`` (midpoints) and the four corners
    ``topleft / topright / bottomleft / bottomright``.
    """
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    return {
        "top":         (cx, y),
        "bottom":      (cx, y + h),
        "left":        (x, cy),
        "right":       (x + w, cy),
        "topleft":     (x, y),
        "topright":    (x + w, y),
        "bottomleft":  (x, y + h),
        "bottomright": (x + w, y + h),
    }[side]


def _side_point_frac(bbox, side: str, frac: float):
    """Point on ``side`` at relative position ``frac`` (0..1) along the
    edge.  For ``top``/``bottom`` edges, frac=0 is the left corner and
    frac=1 is the right corner.  For ``left``/``right`` edges, frac=0
    is the top corner.  A small inset keeps the tap off the exact
    corner.
    """
    x, y, w, h = bbox
    inset_px = min(4.0, w * 0.2, h * 0.2)
    frac = max(0.0, min(1.0, frac))
    if side in ("top", "bottom"):
        lo = x + inset_px
        hi = x + w - inset_px
        if hi <= lo:
            lo, hi = x, x + w
        px = lo + (hi - lo) * frac
        py = y if side == "top" else y + h
        return (px, py)
    if side in ("left", "right"):
        lo = y + inset_px
        hi = y + h - inset_px
        if hi <= lo:
            lo, hi = y, y + h
        py = lo + (hi - lo) * frac
        px = x if side == "left" else x + w
        return (px, py)
    return _side_point(bbox, side)
