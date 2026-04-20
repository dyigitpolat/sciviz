"""AlignedStack: stack children while sharing per-column widths.

The canonical use case: two comparison matrices (``Table``s, ``Row``s of
chips, or ``Grid``s) stacked vertically in a figure, whose authors want
column 3 of row group A to align with column 3 of row group B -- even
when the individual tables have different intrinsic column widths.

Without :class:`AlignedStack`, naive :class:`Column` composition places
every child at its own intrinsic width and column boundaries drift from
row to row. :class:`AlignedStack` consults every child for a list of
*shared columns*, takes the max-per-column across children, and feeds
that back into every child via an opt-in hook::

    element._apply_shared_columns(widths: list[float]) -> None

Children without the hook (plain :class:`Box`, :class:`Text`, etc.) are
placed as-is. The stack behaves exactly like :class:`Column` for them.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Union

from ..core import BBox, Canvas, Element, Theme


class AlignedStack(Element):
    """Stack children vertically (or horizontally) with shared column widths.

    Parameters
    ----------
    *children : Element
    axis : str
        ``"vertical"`` (default) or ``"horizontal"``. ``"horizontal"`` is
        useful when you have two column-oriented children that should
        share per-row heights; for the common row-oriented case leave
        this at ``"vertical"``.
    gap : str or float
        Spacing between children, semantic or px.
    align : str
        Cross-axis alignment of shorter children: ``"start"``,
        ``"center"`` (default), or ``"end"``.
    column_widths : str
        ``"shared"`` (default) broadcasts max-per-column back into every
        child that implements the hook. ``"independent"`` disables the
        shared-width pass; the stack then behaves exactly like a
        :class:`Column` / :class:`Row`.
    """

    def __init__(self, *children: Element,
                 axis: str = "vertical",
                 gap: Union[str, float] = "md",
                 align: str = "center",
                 column_widths: str = "shared",
                 stretch: bool = False):
        if axis not in ("vertical", "horizontal"):
            raise ValueError(
                f"axis must be 'vertical' or 'horizontal'; got {axis!r}")
        if column_widths not in ("shared", "independent"):
            raise ValueError(
                f"column_widths must be 'shared' or 'independent'; "
                f"got {column_widths!r}")
        self.children: List[Element] = [c for c in children if c is not None]
        self.axis = axis
        self.gap = gap
        self.align = align
        self.column_widths = column_widths
        # ``stretch`` turns the shared-slot behaviour from "centre child
        # in a wider slot" into "inflate child's width to match slot".
        # Useful when the shared columns are actual panels (Box /
        # Anchor(Box)) that should paint at the same outer width.
        self.stretch = stretch

    # ---- cross-row shape normalisation ------------------------------------

    def _normalize_cross_child_shapes(self, theme: Theme) -> None:
        """Equalize shape-key elements across *all* children in the stack.

        Within a single :class:`Row`, siblings with the same ``shape_key``
        are already equalised. But when two Rows are stacked in an
        ``AlignedStack``, corresponding elements (e.g. output-tile cards
        in a language row vs. a spatial row) can have different intrinsic
        sizes. This pass collects every shape-key-bearing descendant from
        every child and equalises globally, so the cards render at a
        uniform size across stacked rows.
        """
        from ._row import Row  # local import to avoid circular
        groups: dict = {}
        for child in self.children:
            # Check the child itself (for stacked individual elements).
            peer = Row._find_shape_peer(child)
            if peer is not None and getattr(peer, "shape_key", ""):
                groups.setdefault(peer.shape_key, []).append(peer)
            # Check the child's children (for stacked Rows).
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
                if getattr(p, "width", None) is None:
                    if getattr(p, "min_width", None) is None or p.min_width < tw:
                        p.min_width = tw
                if getattr(p, "height", None) is None:
                    if getattr(p, "min_height", None) is None or p.min_height < th:
                        p.min_height = th

    # ---- shared-column plumbing ------------------------------------------

    def _collect_column_widths(self, theme: Theme) -> List[List[float]]:
        out: List[List[float]] = []
        for c in self.children:
            fn = getattr(c, "_shared_column_widths", None)
            if fn is not None:
                try:
                    widths = list(fn(theme))
                    out.append([float(w) for w in widths])
                    continue
                except Exception:  # pragma: no cover - defensive
                    pass
            out.append([])
        return out

    def _propagate_shared_widths(self, theme: Theme) -> None:
        if self.column_widths != "shared":
            return
        per_child = self._collect_column_widths(theme)
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
                except Exception:  # pragma: no cover - defensive
                    pass
            if self.stretch:
                stretch = getattr(child, "_stretch_visible_to_slots", None)
                if stretch is not None:
                    try:
                        stretch(shared)
                    except Exception:  # pragma: no cover - defensive
                        pass

    # ---- Element interface -----------------------------------------------

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        self._normalize_cross_child_shapes(theme)
        self._propagate_shared_widths(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        if self.axis == "vertical":
            w = max(s.w for s in sizes)
            h = sum(s.h for s in sizes) + g * (len(sizes) - 1)
        else:
            w = sum(s.w for s in sizes) + g * (len(sizes) - 1)
            h = max(s.h for s in sizes)
        return BBox(w, h)

    def _child_offsets(self, theme: Theme):
        """Per-child ``(ox, oy, size)`` in the stack's local frame.

        Cross-axis positions use the **outer** bbox so that children
        whose column widths have been equalised by the shared-width
        pass start at the same coordinate — preserving per-column
        vertical alignment.  Content-aware alignment is left to the
        ``content_bbox`` propagation that parents read.
        """
        if not self.children:
            return []
        self._propagate_shared_widths(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        bbox = self.measure(theme)
        offsets: list = []
        if self.axis == "vertical":
            W = bbox.w
            my = 0.0
            for child, size in zip(self.children, sizes):
                if self.align == "start":
                    ox = 0.0
                elif self.align == "end":
                    ox = W - size.w
                else:
                    ox = (W - size.w) / 2
                offsets.append((ox, my, size))
                my += size.h + g
        else:
            H = bbox.h
            mx = 0.0
            for child, size in zip(self.children, sizes):
                if self.align == "start":
                    oy = 0.0
                elif self.align == "end":
                    oy = H - size.h
                else:
                    oy = (H - size.h) / 2
                offsets.append((mx, oy, size))
                mx += size.w + g
        return offsets

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        for (ox, oy, _size), child in zip(
                self._child_offsets(theme), self.children):
            child.render(canvas, x + ox, y + oy, theme)

    def content_bbox(self, theme: Theme):
        """Union of children's content rectangles in the stack's frame.

        Lets parent containers (:class:`Row`, :class:`Column`) align on
        the stacked content — not the full extent including floating
        decorations — mirroring what :class:`Row.content_bbox` does.
        """
        if not self.children:
            b = self.measure(theme)
            return (0.0, 0.0, b.w, b.h)
        offsets = self._child_offsets(theme)
        xs_lo, ys_lo, xs_hi, ys_hi = [], [], [], []
        for (ox, oy, _size), child in zip(offsets, self.children):
            cx, cy, cw, ch = child.content_bbox(theme)
            xs_lo.append(ox + cx)
            ys_lo.append(oy + cy)
            xs_hi.append(ox + cx + cw)
            ys_hi.append(oy + cy + ch)
        x0, y0 = min(xs_lo), min(ys_lo)
        x1, y1 = max(xs_hi), max(ys_hi)
        return (x0, y0, x1 - x0, y1 - y0)
