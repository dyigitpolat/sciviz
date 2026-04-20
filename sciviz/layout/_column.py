"""Column: vertical layout container."""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme
from ._row import Row


class Column(Element):
    """Vertical container. See :class:`sciviz.layout.Row` for details.

    Parameters
    ----------
    equal_widths : bool
        If True, every visible child is inflated to the widest child's
        intrinsic width via :meth:`Element.inflate_to`, so siblings like
        captioner cards or tinted panels paint at the same outer width
        instead of just sharing a centring slot. Children that don't
        support inflation are still rendered at intrinsic width and
        centred within the column.
    """

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center", equal_widths: bool = False):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align
        self.equal_widths = equal_widths
        self._equalised = False
        # Floor on the column's rendered width, set by ``inflate_to``.
        # Honoured in ``measure`` / ``render``; children retain their
        # alignment within the (possibly widened) column frame.
        self._min_width: float = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Grow the Column's outer width so a ``start``-aligned stack of
        chips stays hugged to the left of the enclosing Box when the Box
        is inflated to match a sibling. ``min_h`` is currently ignored --
        Columns stretch in the main axis via child sizes, not a floor.
        """
        if min_w > self._min_width:
            self._min_width = float(min_w)

    def _visible_children(self):
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    # ---- AlignedStack-style normalisation (always-on) --------------------
    # Column inherits the two key AlignedStack behaviours so that authors
    # get cross-child shape equalisation and shared column widths without
    # reaching for AlignedStack explicitly.  Both passes are no-ops when
    # children don't carry shape keys or don't implement the shared-width
    # hooks (i.e. the common Text / Box / Icon case is untouched).

    def _normalize_cross_child_shapes(self, theme: Theme) -> None:
        groups: dict = {}
        for child in self.children:
            peer = Row._find_shape_peer(child)
            if peer is not None and getattr(peer, "shape_key", ""):
                groups.setdefault(peer.shape_key, []).append(peer)
            for sub in getattr(child, "children", []):
                peer = Row._find_shape_peer(sub)
                if peer is not None and getattr(peer, "shape_key", ""):
                    groups.setdefault(peer.shape_key, []).append(peer)
        for peers in groups.values():
            if len(peers) < 2:
                continue
            sizes = [p.measure(theme) for p in peers]
            tw = max(s.w for s in sizes)
            th = max(s.h for s in sizes)
            for p in peers:
                # Skip elements with explicit dimensions — the author
                # set a deliberate size that shouldn't be overridden.
                if getattr(p, "width", None) is None:
                    if getattr(p, "min_width", None) is None or p.min_width < tw:
                        p.min_width = tw
                if getattr(p, "height", None) is None:
                    if getattr(p, "min_height", None) is None or p.min_height < th:
                        p.min_height = th

    def _propagate_shared_widths(self, theme: Theme) -> None:
        # Trigger within-Row shape normalisation first so the column
        # widths we collect reflect the *post-equalisation* sizes.
        for c in self.children:
            norm = getattr(c, "_normalize_shape_peers", None)
            if norm is not None:
                norm(theme)
        per_child = []
        for c in self.children:
            fn = getattr(c, "_shared_column_widths", None)
            if fn is not None:
                try:
                    per_child.append([float(w) for w in fn(theme)])
                    continue
                except Exception:
                    pass
            per_child.append([])
        # Only propagate when at least two children contribute column
        # widths — a single Row has nothing to align against, and
        # forcing slot widths on it changes centering semantics.
        contributing = sum(1 for w in per_child if w)
        if contributing < 2:
            return
        max_cols = max((len(w) for w in per_child), default=0)
        if max_cols == 0:
            return
        shared = [0.0] * max_cols
        for widths in per_child:
            for i, w in enumerate(widths):
                if w > shared[i]:
                    shared[i] = w
        for child in self.children:
            apply = getattr(child, "_apply_shared_columns", None)
            if apply is not None:
                try:
                    apply(shared)
                except Exception:
                    pass

    def _maybe_equalise_widths(self, theme: Theme) -> None:
        """Broadcast the widest child's width to siblings via ``inflate_to``.
        Idempotent: only fires once per Column instance.
        """
        if not self.equal_widths or self._equalised or not self.children:
            return
        self._equalised = True
        sizes = [c.measure(theme) for c in self._visible_children()]
        if not sizes:
            return
        target = max(s.w for s in sizes)
        for c in self._visible_children():
            c.inflate_to(target, 0.0)

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        self._normalize_cross_child_shapes(theme)
        self._propagate_shared_widths(theme)
        self._maybe_equalise_widths(theme)
        sizes = [c.measure(theme) for c in self.children]
        visible = self._visible_children()
        vis_sizes = [c.measure(theme) for c in visible]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        content_w = max(cb[2] for cb in content)
        max_left = max(cb[0] for cb in content)
        max_right = max(s.w - cb[0] - cb[2] for s, cb in zip(sizes, content))
        w = max(content_w + max_left + max_right, max(s.w for s in sizes))
        if self._min_width > w:
            w = self._min_width
        n_vis = max(len(visible), 1)
        h = sum(s.h for s in vis_sizes) + g * (n_vis - 1)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        self._maybe_equalise_widths(theme)
        # Give cross-axis stretchers (horizontal separators etc.) the
        # column's full width so they render as full-width rules.
        W = self.measure(theme).w
        for c in self.children:
            if getattr(c, "stretch_main_axis", False) and hasattr(c, "set_stretched_length"):
                c.set_stretched_length(W)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        _content_w = max(cb[2] for cb in content)
        _max_left = max(cb[0] for cb in content)
        cy = y
        for child, size, cb in zip(self.children, sizes, content):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_x = cb[0]
            cb_w = cb[2]
            if self.align == "start":
                cx = x - cb_x
            elif self.align == "end":
                cx = x + W - (cb_x + cb_w)
            else:
                col_content_center_x = x + _max_left + _content_w / 2
                cx = col_content_center_x - (cb_x + cb_w / 2)
            child.render(canvas, cx, cy, theme)
            if not invisible:
                cy += size.h + g
