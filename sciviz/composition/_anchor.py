"""Anchor: register a child's rendered bbox under a name.

Exposes the ``_anchor_stack`` ContextVar and the ``_side_point`` /
``_side_point_frac`` geometry helpers used by :class:`Flow` and
:class:`Bus` to tap arrow endpoints onto named edges.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

import contextvars as _cv

# Stack of active registries. Each Flowed pushes a fresh dict; Anchor
# registers itself in ALL active registries, so nested Flowed's anchors
# remain reachable from outer flows.
_anchor_stack: _cv.ContextVar = _cv.ContextVar("_anchor_stack", default=None)


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
        stack = _anchor_stack.get()
        if stack is not None:
            for reg in stack:
                reg[self.name] = (child_x, child_y, b.w, b.h)
        self.child.render(canvas, child_x, child_y, theme)

    def _bump_margin(self, side: str, amount: float) -> None:
        if side in ("left",):
            self.margin_left = max(self.margin_left, amount)
        elif side in ("right",):
            self.margin_right = max(self.margin_right, amount)
        elif side in ("top", "topleft", "topright"):
            self.margin_top = max(self.margin_top, amount)
        elif side in ("bottom", "bottomleft", "bottomright"):
            self.margin_bottom = max(self.margin_bottom, amount)


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

