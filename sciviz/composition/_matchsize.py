"""MatchSize: stretch siblings to share a major-axis dimension."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

class MatchSize(Element):
    """Wrap a list of children, stretching them to a common dimension.

    Eliminates the manual ``height=132`` repetition that authors otherwise
    do to make sibling boxes line up.  Wrap them in MatchSize and the
    container computes the max intrinsic dimension and forces every child
    to it via :class:`FixedSize`.

    Parameters
    ----------
    *children : Element
        The siblings to equalise.
    axis : str
        ``"height"`` (default) -- equalise heights.  Useful when laying out
        in a Row.
        ``"width"``  -- equalise widths.  Useful when laying out in a Column.
    arrange : str or None
        If ``"row"`` or ``"column"``, the equalised children are also wrapped
        in the corresponding container so the user doesn't write the
        ``Row(...)`` themselves.  Default ``None`` returns just the
        equalised children laid out by the surrounding parent.
    gap : str or float
        Used only when ``arrange`` is set.
    align : str
        Cross-axis alignment when ``arrange`` is set.
    """

    def __init__(self, *children: Element,
                 axis: str = "height",
                 arrange: Optional[str] = None,
                 gap: Union[str, float] = "md",
                 align: str = "center"):
        self.children = list(children)
        self.axis = axis
        self.arrange = arrange
        self.gap = gap
        self.align = align

    def _equalised(self, theme: Theme):
        from ..layout import FixedSize, Row, Column
        sizes = [c.measure(theme) for c in self.children]
        if self.axis == "height":
            target = max(s.h for s in sizes) if sizes else 0
            return [FixedSize(c, height=target) for c in self.children]
        else:
            target = max(s.w for s in sizes) if sizes else 0
            return [FixedSize(c, width=target) for c in self.children]

    def _arranged(self, theme: Theme):
        from ..layout import Row, Column
        children = self._equalised(theme)
        if self.arrange == "row":
            return Row(*children, gap=self.gap, align=self.align)
        if self.arrange == "column":
            return Column(*children, gap=self.gap, align=self.align)
        # No explicit arrangement: pack into a Row by default for height,
        # Column for width.
        if self.axis == "height":
            return Row(*children, gap=self.gap, align=self.align)
        return Column(*children, gap=self.gap, align=self.align)

    def measure(self, theme: Theme) -> BBox:
        return self._arranged(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._arranged(theme).render(canvas, x, y, theme)



