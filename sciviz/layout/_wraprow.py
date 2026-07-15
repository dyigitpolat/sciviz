"""WrapRow: a flow layout -- children run left-to-right and wrap onto
new lines within a width budget.

The budget is a *wrap threshold*, not a hard clip: a child wider than the
budget still gets a line of its own at natural width (the longest-child
floor, mirroring ``Box(wrap=True)``'s longest-word floor), so content is
never truncated or overdrawn.

Use it wherever a variable-length run of small peers (citation chips,
tags, tokens, badges) should consume bounded width and grow downward
instead of pushing the figure wider -- e.g. a taxonomy leaf label followed
by its representative-work chips.
"""

from __future__ import annotations

from typing import List, Union

from ..core import BBox, Canvas, Element, Theme

#: Cross-axis / line alignment values accepted by :class:`WrapRow`.
_LINE_ALIGN = ("start", "center", "end")


class WrapRow(Element):
    """Horizontal flow container with automatic line wrapping.

    Parameters
    ----------
    *children : Element
        Laid out left-to-right in declared (reading) order; a child that
        would overflow the width budget starts a new line. ``None``
        children are silently dropped.
    gap : str or float
        Spacing between items on one line (semantic tokens or px).
    line_gap : str or float, optional
        Spacing between lines. Defaults to ``gap``.
    max_width : float, optional
        The flow budget in px. ``None`` resolves to the theme's word-wrap
        budget (``theme.wrap_budget_px()``), the same knob the diagram
        target-width fitter compresses -- so an unbudgeted WrapRow
        tightens automatically when a figure must fit a physical width.
    align : str
        Cross-axis (vertical) placement of items within their line:
        ``"start"``, ``"center"``, or ``"end"``.
    line_align : str
        Horizontal placement of each line within the container frame:
        ``"start"``, ``"center"``, or ``"end"``.
    hang : str or float
        Hanging indent applied to every line after the first (semantic
        gap token or px). Marks continuation lines as belonging to the
        run above -- e.g. citation chips that wrapped past their leaf
        label -- instead of letting them masquerade as new siblings.
        Only meaningful with ``line_align="start"``.

    Notes
    -----
    Unlike :class:`Row`, a WrapRow performs no sibling shape
    equalisation: flow content keeps its intrinsic size so lines pack
    tightly. Layout-invisible children (:class:`Connect` specs) are
    rendered but consume no flow space.
    """

    def __init__(self, *children: Element, gap: Union[str, float] = "sm",
                 line_gap: Union[str, float, None] = None,
                 max_width: float | None = None,
                 align: str = "center", line_align: str = "start",
                 hang: Union[str, float] = 0.0):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.line_gap = gap if line_gap is None else line_gap
        self.max_width = max_width
        if align not in _LINE_ALIGN:
            raise ValueError(
                f"WrapRow(align={align!r}) is not recognised; expected one "
                f"of: {', '.join(repr(v) for v in _LINE_ALIGN)}")
        if line_align not in _LINE_ALIGN:
            raise ValueError(
                f"WrapRow(line_align={line_align!r}) is not recognised; "
                f"expected one of: {', '.join(repr(v) for v in _LINE_ALIGN)}")
        self.align = align
        self.line_align = line_align
        self.hang = hang
        # Width floor raised by a parent slot (Card / Column equalisation).
        self._min_width: float = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Honour a parent's width floor. Lines keep their flow breaks;
        the extra width is absorbed by :attr:`line_align` placement."""
        if min_w > self._min_width:
            self._min_width = float(min_w)

    # ---- flow geometry ---------------------------------------------------

    def _visible_children(self):
        return [c for c in self.children
                if not getattr(c, "is_layout_invisible", False)]

    def _budget(self, theme: Theme) -> float:
        if self.max_width is not None:
            return float(self.max_width)
        return theme.wrap_budget_px()

    def _lines(self, theme: Theme):
        """Greedy line-breaking over visible children.

        Returns a list of lines, each a list of ``(child, BBox)`` pairs.
        Continuation lines flow within the budget minus the hanging
        indent, so the indented line still respects ``max_width``.
        """
        budget = self._budget(theme)
        hang = theme.gap_px(self.hang)
        g = theme.gap_px(self.gap)
        lines: List[list] = []
        cur: list = []
        cur_w = 0.0
        for child in self._visible_children():
            size = child.measure(theme)
            line_budget = budget if not lines else budget - hang
            need = size.w if not cur else cur_w + g + size.w
            if cur and need > line_budget + 1e-6:
                lines.append(cur)
                cur = [(child, size)]
                cur_w = size.w
            else:
                cur.append((child, size))
                cur_w = need
        if cur:
            lines.append(cur)
        return lines

    @staticmethod
    def _line_width(line, g: float) -> float:
        return sum(s.w for _c, s in line) + g * (len(line) - 1)

    def measure(self, theme: Theme) -> BBox:
        lines = self._lines(theme)
        if not lines:
            return BBox(0, 0)
        g = theme.gap_px(self.gap)
        lg = theme.gap_px(self.line_gap)
        hang = theme.gap_px(self.hang)
        w = max((hang if i else 0.0) + self._line_width(line, g)
                for i, line in enumerate(lines))
        h = sum(max(s.h for _c, s in line) for line in lines)
        h += lg * (len(lines) - 1)
        return BBox(max(w, self._min_width), h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        lines = self._lines(theme)
        if not lines:
            return
        g = theme.gap_px(self.gap)
        lg = theme.gap_px(self.line_gap)
        hang = theme.gap_px(self.hang)
        outer_w = self.measure(theme).w
        cy = y
        for i, line in enumerate(lines):
            line_w = self._line_width(line, g)
            line_h = max(s.h for _c, s in line)
            if self.line_align == "center":
                cx = x + (outer_w - line_w) / 2.0
            elif self.line_align == "end":
                cx = x + outer_w - line_w
            else:
                cx = x + (hang if i else 0.0)
            for child, size in line:
                if self.align == "start":
                    oy = cy
                elif self.align == "end":
                    oy = cy + line_h - size.h
                else:
                    oy = cy + (line_h - size.h) / 2.0
                child.render(canvas, cx, oy, theme)
                cx += size.w + g
            cy += line_h + lg
        # Layout-invisible children (declarative Connect specs) still render
        # so walkers can collect them; they draw at the container origin.
        for child in self.children:
            if getattr(child, "is_layout_invisible", False):
                child.render(canvas, x, y, theme)
