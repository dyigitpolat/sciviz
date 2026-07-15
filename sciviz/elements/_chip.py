"""Chip: a compact rounded tag that hugs its text.

:class:`~sciviz.elements.Box` enforces a paper-node minimum silhouette
(side bearing, a height floor) so structural nodes survive print
reduction. A Chip is the opposite kind of ink: a small annotation pill
-- citation tags, keywords, counts, states -- that must stay visually
subordinate to the node it annotates. Its padding scales with the text
size, its outline is always a pill, and it has no minimum silhouette,
so a run of chips packs tightly in a :class:`~sciviz.layout.Row` or
:class:`~sciviz.layout.WrapRow`.
"""

from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme

#: Horizontal / vertical padding as fractions of the chip's font size.
_PAD_X_EM = 0.72
_PAD_Y_EM = 0.36


class Chip(Element):
    """A small text pill.

    Parameters
    ----------
    label : str
        The chip text (a citation tag, keyword, count, ...).
    color : str or Palette role
        Outline colour. Defaults to the muted theme colour.
    fill : str or Palette paint
        Interior paint; default ``"none"`` (outline-only tag).
    text_color : str or Palette role, optional
        Defaults to ``"muted"`` -- annotation ink, subordinate to node
        labels.
    text_size : str or float
        Theme size token (default ``"tiny"``) or raw px.
    text_weight : str
        SVG font weight (default ``"500"``).
    dashed : bool
        Dash the outline (e.g. a provisional / inferred tag).
    """

    #: Chips opt out of sibling shape-equalisation: a run of tags should
    #: pack at intrinsic widths, not inflate to the widest peer.
    shape_key = ""

    def __init__(self, label: str, *,
                 color: str = "muted",
                 fill: str = "none",
                 text_color: Optional[str] = None,
                 text_size: Union[str, float] = "tiny",
                 text_weight: str = "500",
                 dashed: bool = False):
        self.label = str(label)
        self.color = color
        self.fill = fill
        self.text_color = text_color if text_color is not None else "muted"
        self.text_size = text_size
        self.text_weight = text_weight
        self.dashed = dashed

    def measure(self, theme: Theme) -> BBox:
        sz = theme.size_px(self.text_size)
        bold = self.text_weight in ("bold", "600", "700")
        text_w = theme.text_width(self.label, self.text_size, bold=bold)
        w = text_w + 2 * _PAD_X_EM * sz
        h = sz * 1.15 + 2 * _PAD_Y_EM * sz
        # A pill can never be narrower than it is tall (its two end caps).
        return BBox(max(w, h), h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        sz = theme.size_px(self.text_size)
        canvas.rect(
            x, y, size.w, size.h,
            fill=theme.paint_of(self.fill),
            stroke=theme.paint_of(self.color),
            stroke_width=theme.hairline,
            rx=size.h / 2,
            dasharray="3,2" if self.dashed else None,
        )
        canvas.text(
            x + size.w / 2, y + size.h / 2 + sz * 0.32, self.label,
            size=sz, fill=theme.color_of(self.text_color),
            weight=self.text_weight, anchor="middle",
        )
