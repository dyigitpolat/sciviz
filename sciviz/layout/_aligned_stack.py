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
                 column_widths: str = "shared"):
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

    # ---- Element interface -----------------------------------------------

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
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

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        self._propagate_shared_widths(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        if self.axis == "vertical":
            W = max(s.w for s in sizes)
            cy = y
            for child, size in zip(self.children, sizes):
                if self.align == "start":
                    cx = x
                elif self.align == "end":
                    cx = x + (W - size.w)
                else:
                    cx = x + (W - size.w) / 2
                child.render(canvas, cx, cy, theme)
                cy += size.h + g
        else:
            H = max(s.h for s in sizes)
            cx = x
            for child, size in zip(self.children, sizes):
                if self.align == "start":
                    cy = y
                elif self.align == "end":
                    cy = y + (H - size.h)
                else:
                    cy = y + (H - size.h) / 2
                child.render(canvas, cx, cy, theme)
                cx += size.w + g
