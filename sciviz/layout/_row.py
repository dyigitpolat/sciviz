"""Row: horizontal layout container.

A Row measures every child, arranges them left-to-right with automatic
spacing, and reports a bounding box that contains all of them. See
:class:`Column` for the vertical analogue.
"""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme


class Row(Element):
    """Horizontal container.

    Parameters
    ----------
    *children : Element
        The child elements, laid out left-to-right. ``None`` children are
        silently dropped, which is handy for optional pieces.
    gap : str or float
        Spacing between children. Semantic tokens (``"xs"``, ``"sm"``,
        ``"md"``, ``"lg"``, ``"xl"``, ``"2xl"``) are resolved against the
        theme's base unit.
    align : str
        Vertical alignment of shorter children: ``"start"``, ``"center"``,
        or ``"end"``.
    equal_widths : bool
        If True, every child gets the same horizontal slot (the max child
        width). Critical for visually aligning columns of differing-width
        labels (e.g. tokens, bars, pictograms). Each child is centered
        within its slot.
    """

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center", equal_widths: bool = False):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align
        self.equal_widths = equal_widths
        self._shape_normalized = False
        # Per-child widths forced by a containing AlignedStack. When set,
        # each visible child occupies at least ``forced_slot_w[i]`` px.
        self._forced_slot_w: List[float] | None = None

    @staticmethod
    def _find_shape_peer(elem):
        """Unwrap wrappers (``Anchor``, ``Banner``, ``Captioned``, …) to
        find a shape-key-bearing child (e.g. ``Box``) so sibling-
        normalisation reaches into ``Banner(Box(…))`` without the
        author wrapping things differently.
        """
        seen = 0
        cur = elem
        while cur is not None and seen < 6:
            if getattr(cur, "shape_key", None):
                return cur
            # Try common wrapper attributes: .child (Anchor, Captioned),
            # .body (Banner), .label (Box with Element label).
            nxt = getattr(cur, "child", None) or getattr(cur, "body", None)
            if nxt is None:
                break
            cur = nxt
            seen += 1
        return None

    def _normalize_shape_peers(self, theme: Theme) -> None:
        """Siblings in this row sharing the same ``shape_key`` get equalised
        min_width / min_height so they render at the same box size --
        regardless of label length or sub_label length.
        """
        if self._shape_normalized:
            return
        self._shape_normalized = True
        groups: dict = {}
        for c in self.children:
            peer = self._find_shape_peer(c)
            if peer is None:
                continue
            key = peer.shape_key
            if not key:
                continue
            groups.setdefault(key, []).append(peer)
        for key, peers in groups.items():
            if len(peers) < 2:
                continue
            sizes = [p.measure(theme) for p in peers]
            target_w = max(s.w for s in sizes)
            target_h = max(s.h for s in sizes)
            for p in peers:
                if getattr(p, "min_width", None) is None or p.min_width < target_w:
                    p.min_width = target_w
                if getattr(p, "min_height", None) is None or p.min_height < target_h:
                    p.min_height = target_h

    def _visible_children(self):
        """Children that participate in main-axis layout. Invisible ones
        are still rendered at the running cursor, but consume no gap."""
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    def _stretch_children(self):
        """Children that want to fill the main axis (:class:`Separator` et al.)."""
        return [c for c in self.children
                if getattr(c, "stretch_main_axis", False)]

    def _slot_widths_for_visible(self, vis_sizes) -> List[float]:
        """Per-visible-child slot width, honouring :attr:`_forced_slot_w`."""
        slots: List[float] = []
        forced = self._forced_slot_w or []
        for i, s in enumerate(vis_sizes):
            base = s.w
            if i < len(forced) and forced[i] > base:
                slots.append(forced[i])
            else:
                slots.append(base)
        return slots

    # ---- AlignedStack hooks ---------------------------------------------

    def _shared_column_widths(self, theme: Theme) -> List[float]:
        """Intrinsic per-visible-child widths."""
        vis_sizes = [c.measure(theme) for c in self._visible_children()]
        return [s.w for s in vis_sizes]

    def _apply_shared_columns(self, widths: List[float]) -> None:
        self._forced_slot_w = list(widths)

    def _stretch_visible_to_slots(self, widths: List[float]) -> None:
        """Inflate each visible child so its rendered width matches the
        slot it sits in. Called by :class:`AlignedStack` (``stretch=True``)
        after broadcasting shared column widths -- this turns the
        "centred-in-empty-slot" behaviour into actual same-width painting
        for Box-like children that implement ``inflate_to``.
        """
        for child, w in zip(self._visible_children(), widths):
            if w > 0:
                child.inflate_to(w, 0.0)

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        self._normalize_shape_peers(theme)
        visible = self._visible_children()
        vis_sizes = [c.measure(theme) for c in visible]
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        n_vis = max(len(visible), 1)
        if self.equal_widths and visible:
            slot = max(s.w for s in vis_sizes)
            w = slot * len(visible) + g * (len(visible) - 1)
        elif self._forced_slot_w is not None:
            slots = self._slot_widths_for_visible(vis_sizes)
            w = sum(slots) + g * (len(slots) - 1)
        else:
            w = sum(s.w for s in vis_sizes) + g * (n_vis - 1)
        # Row height must accommodate the TALLEST content bbox plus the
        # asymmetric out-of-band margins of any individual child, so that
        # content-axis centering still fits every child inside the row.
        content = [c.content_bbox(theme) for c in self.children]
        content_h = max(cb[3] for cb in content)
        max_top = max(cb[1] for cb in content)
        max_bot = max(s.h - cb[1] - cb[3] for s, cb in zip(sizes, content))
        h = max(content_h + max_top + max_bot, max(s.h for s in sizes))
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        self._normalize_shape_peers(theme)
        # Resolve cross-axis stretchers (vertical separators etc.) to Row height
        # BEFORE taking measurements, so their measured height fits the row.
        H = self.measure(theme).h
        for c in self.children:
            if getattr(c, "stretch_main_axis", False) and hasattr(c, "set_stretched_length"):
                c.set_stretched_length(H)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        slot = None
        if self.equal_widths:
            vis_sizes = [c.measure(theme) for c in self._visible_children()]
            slot = max(s.w for s in vis_sizes) if vis_sizes else 0.0
        # AlignedStack-forced per-slot widths (visible children only).
        forced_slots = None
        if not self.equal_widths and self._forced_slot_w is not None:
            vis_sizes = [c.measure(theme) for c in self._visible_children()]
            forced_slots = self._slot_widths_for_visible(vis_sizes)
        # Pre-compute the content-axis centre so that children with
        # asymmetric decoration margins (e.g. a Banner header above
        # but nothing below) stay inside the Row's reported bbox.
        _content_h = max(c[3] for c in content)
        _max_top = max(c[1] for c in content)
        cx = x
        vis_idx = 0
        for child, size, cb in zip(self.children, sizes, content):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_y = cb[1]
            cb_h = cb[3]
            if self.align == "start":
                cy = y - cb_y
            elif self.align == "end":
                cy = y + H - (cb_y + cb_h)
            else:
                row_content_center_y = y + _max_top + _content_h / 2
                cy = row_content_center_y - (cb_y + cb_h / 2)
            if self.equal_widths and not invisible:
                cb_x = cb[0]
                cb_w = cb[2]
                slot_cx = cx + slot / 2
                child.render(canvas, slot_cx - (cb_x + cb_w / 2), cy, theme)
                cx += slot + g
            elif forced_slots is not None and not invisible:
                slot_w = forced_slots[vis_idx]
                cb_x = cb[0]
                cb_w = cb[2]
                slot_cx = cx + slot_w / 2
                child.render(canvas, slot_cx - (cb_x + cb_w / 2), cy, theme)
                cx += slot_w + g
                vis_idx += 1
            else:
                child.render(canvas, cx, cy, theme)
                if not invisible:
                    cx += size.w + g
                    vis_idx += 1

    def _child_offsets(self, theme: Theme):
        """Same x/y placement math as :meth:`render`, but returns the
        per-child offsets ``(ox, oy)`` in the Row's local frame.
        """
        if not self.children:
            return []
        self._normalize_shape_peers(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        content = [c.content_bbox(theme) for c in self.children]
        H = self.measure(theme).h
        slot = None
        if self.equal_widths:
            vis_sizes = [c.measure(theme) for c in self._visible_children()]
            slot = max(s.w for s in vis_sizes) if vis_sizes else 0.0
        forced_slots = None
        if not self.equal_widths and self._forced_slot_w is not None:
            vis_sizes = [c.measure(theme) for c in self._visible_children()]
            forced_slots = self._slot_widths_for_visible(vis_sizes)
        _content_h = max(c[3] for c in content)
        _max_top = max(c[1] for c in content)
        offs = []
        cx = 0.0
        vis_idx = 0
        for child, size, cb in zip(self.children, sizes, content):
            invisible = getattr(child, "is_layout_invisible", False)
            cb_y = cb[1]
            cb_h = cb[3]
            if self.align == "start":
                oy = 0.0 - cb_y
            elif self.align == "end":
                oy = H - (cb_y + cb_h)
            else:
                oy = (_max_top + _content_h / 2) - (cb_y + cb_h / 2)
            if self.equal_widths and not invisible:
                slot_cx = cx + slot / 2
                ox = slot_cx - (cb[0] + cb[2] / 2)
                offs.append((ox, oy, size))
                cx += slot + g
            elif forced_slots is not None and not invisible:
                slot_w = forced_slots[vis_idx]
                slot_cx = cx + slot_w / 2
                ox = slot_cx - (cb[0] + cb[2] / 2)
                offs.append((ox, oy, size))
                cx += slot_w + g
                vis_idx += 1
            else:
                offs.append((cx, oy, size))
                if not invisible:
                    cx += size.w + g
                    vis_idx += 1
        return offs

    def primary_anchor_bbox(self, theme: Theme):
        """The Row's primary anchor is the union of its children's primary
        anchors -- the smallest rectangle containing every visible face.
        """
        if not self.children:
            return None
        offs = self._child_offsets(theme)
        xs_lo, ys_lo, xs_hi, ys_hi = [], [], [], []
        for (ox, oy, _size), child in zip(offs, self.children):
            for ax, ay, aw, ah in child.iter_primary_anchors(theme):
                xs_lo.append(ox + ax)
                ys_lo.append(oy + ay)
                xs_hi.append(ox + ax + aw)
                ys_hi.append(oy + ay + ah)
        if not xs_lo:
            return None
        x0, y0 = min(xs_lo), min(ys_lo)
        x1, y1 = max(xs_hi), max(ys_hi)
        return (x0, y0, x1 - x0, y1 - y0)

    def iter_primary_anchors(self, theme: Theme):
        out = []
        offs = self._child_offsets(theme)
        for (ox, oy, _size), child in zip(offs, self.children):
            for ax, ay, aw, ah in child.iter_primary_anchors(theme):
                out.append((ox + ax, oy + ay, aw, ah))
        return out

    def content_bbox(self, theme: Theme):
        """Union of children's content rectangles, translated into the
        Row's local frame. Used by Column alignment to stack rows on
        their visible content axis.
        """
        if not self.children:
            b = self.measure(theme)
            return (0.0, 0.0, b.w, b.h)
        offs = self._child_offsets(theme)
        xs_lo, ys_lo, xs_hi, ys_hi = [], [], [], []
        for (ox, oy, _size), child in zip(offs, self.children):
            cx, cy, cw, ch = child.content_bbox(theme)
            xs_lo.append(ox + cx)
            ys_lo.append(oy + cy)
            xs_hi.append(ox + cx + cw)
            ys_hi.append(oy + cy + ch)
        x0, y0 = min(xs_lo), min(ys_lo)
        x1, y1 = max(xs_hi), max(ys_hi)
        return (x0, y0, x1 - x0, y1 - y0)
