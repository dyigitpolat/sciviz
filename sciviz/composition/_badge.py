"""Badge: small filled circle with centred text (used by Captioned)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

class Badge(Element):
    """A small filled circle with centred text.

    Used for both purposes that turn up constantly in figures:

    * **Numbered/lettered markers** that link a panel to a table row
      (``Badge("1", color=Palette.alert)``).
    * **Inline mathematical operators** drawn as circles, like a residual
      add (``Badge("+")``) or a concatenation (``Badge("c")``).

    Parameters
    ----------
    label : str
        Text inside the badge.  Keep short -- 1-3 characters typically.
    color : ColorRef or str
        Fill colour.  Text colour is auto-chosen for contrast.
    size : float
        Diameter in pixels.
    text_size : str
        Theme size token for the label.
    text_weight : str
        Font weight for the label.
    bordered : bool
        If True, draw a thin stroke around the badge.
    """

    # Sentinel: "auto" means "pick a fill based on bordered-ness".
    # Bordered=True is the paper-style operator glyph (+, c, ×) -- drawn
    # as a ring with a dark glyph; so the interior should be the page
    # colour ("none" = transparent) rather than the info blue.
    _AUTO_COLOR = "__auto__"

    def __init__(self, label: str = "", *,
                 color = _AUTO_COLOR,
                 size: float = 18.0,
                 text_size: str = "small",
                 text_weight: str = "700",
                 bordered: bool = False,
                 stroke_color = None):
        self.label = str(label)
        self.color = color
        self.size = size
        self.text_size = text_size
        self.text_weight = text_weight
        self.bordered = bordered
        self.stroke_color = stroke_color

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.size, self.size)

    def _resolved_fill(self, theme: Theme) -> str:
        if self.color is Badge._AUTO_COLOR:
            # No explicit colour: bordered => transparent paper interior,
            # un-bordered => classic info-blue fill.
            return "none" if self.bordered else theme.color_of("info")
        return theme.color_of(self.color)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        fill = self._resolved_fill(theme)
        cx = x + self.size / 2
        cy = y + self.size / 2
        stroke = "none"
        sw = 0.0
        if self.bordered:
            stroke = theme.color_of(self.stroke_color or "text")
            sw = theme.hairline
        canvas.circle(cx, cy, self.size / 2,
                     fill=fill, stroke=stroke, stroke_width=sw)
        if self.label:
            # For a transparent paper-style operator badge, the glyph
            # sits on the page background -- use the dark text colour
            # rather than "text_on(transparent)" which is undefined.
            if fill == "none":
                text_color = theme.color_of("text")
            else:
                text_color = theme.text_on(fill)
            canvas.text(cx, cy, self.label,
                       size=theme.size_px(self.text_size),
                       fill=text_color,
                       weight=self.text_weight,
                       anchor="middle", baseline="middle")



