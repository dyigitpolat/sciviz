"""Banner: a body element with an optional floating header and/or footer.

The key publication-diagram property of a :class:`Banner` is that its
``content_bbox`` reports **only the body**. Sibling containers like
:class:`Row` and :class:`Column` that center on content bbox therefore
ignore the banner's header/footer when aligning siblings:

    Row(
        Banner(pe_panel, above=header("Large-Scale", ...)),  # body = panel
        side_column,                                          # aligns on panel
    )

This is what lets a headline sit above one of several rows without
pushing that row vertically off-centre relative to its siblings.

Compared to :class:`Captioned`, :class:`Banner` accepts arbitrary
:class:`Element` headers/footers (not just a single text kicker) and
always reports body-only content bbox.
"""
from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Banner(Element):
    """Stack ``above`` / ``body`` / ``below`` vertically, but align
    externally on the body alone.

    Parameters
    ----------
    body : Element
        The main element. Its ``content_bbox`` is what the surrounding
        layout container sees when centering siblings.
    above, below : Element, optional
        Header and footer decorations. Each is horizontally centered
        relative to the body by default (configurable via ``align``).
    gap : str or float
        Vertical gap between the body and each decoration. A semantic
        token (``"xs"``, ``"sm"``, ``"md"`` ...) is resolved against
        the theme.
    align : str
        Horizontal alignment of the narrower of (header/footer, body)
        within the wider one: ``"start"``, ``"center"`` (default), or
        ``"end"``.
    """

    def __init__(self, body: Element, *,
                 above: Optional[Element] = None,
                 below: Optional[Element] = None,
                 gap: Union[str, float] = "sm",
                 align: str = "center"):
        self.body = body
        self.above = above
        self.below = below
        self.gap = gap
        if align not in ("start", "center", "end"):
            raise ValueError(
                f"align must be 'start', 'center', or 'end'; got {align!r}")
        self.align = align

    def _parts(self, theme: Theme):
        body_bb = self.body.measure(theme)
        above_bb = self.above.measure(theme) if self.above else BBox(0, 0)
        below_bb = self.below.measure(theme) if self.below else BBox(0, 0)
        gap_px = theme.gap_px(self.gap)
        outer_w = max(body_bb.w, above_bb.w, below_bb.w)
        return body_bb, above_bb, below_bb, gap_px, outer_w

    def measure(self, theme: Theme) -> BBox:
        body_bb, above_bb, below_bb, gap_px, outer_w = self._parts(theme)
        total_h = body_bb.h
        if self.above is not None:
            total_h += above_bb.h + gap_px
        if self.below is not None:
            total_h += below_bb.h + gap_px
        return BBox(outer_w, total_h)

    def _hx(self, inner_w: float, outer_w: float) -> float:
        if self.align == "start":
            return 0.0
        if self.align == "end":
            return outer_w - inner_w
        return (outer_w - inner_w) / 2

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        body_bb, above_bb, below_bb, gap_px, outer_w = self._parts(theme)
        cy = y
        if self.above is not None:
            self.above.render(canvas,
                              x + self._hx(above_bb.w, outer_w), cy, theme)
            cy += above_bb.h + gap_px
        self.body.render(canvas, x + self._hx(body_bb.w, outer_w), cy, theme)
        cy += body_bb.h
        if self.below is not None:
            cy += gap_px
            self.below.render(canvas,
                              x + self._hx(below_bb.w, outer_w), cy, theme)

    # ---- alignment contract ------------------------------------------------

    def content_bbox(self, theme: Theme):
        """Report only the body's content_bbox so sibling :class:`Row` /
        :class:`Column` containers align on the body's midline. The
        ``above``/``below`` decorations are treated as floating labels."""
        body_bb, above_bb, _below_bb, gap_px, outer_w = self._parts(theme)
        bx, by, bw, bh = self.body.content_bbox(theme)
        body_x = self._hx(body_bb.w, outer_w)
        body_y = above_bb.h + gap_px if self.above is not None else 0.0
        return (body_x + bx, body_y + by, bw, bh)
