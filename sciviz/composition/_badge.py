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

    _SIZE_FACTORS = {"sm": 3.0, "md": 4.0, "lg": 5.2, "xl": 6.4}

    def __init__(self, label: Union[str, Element] = "", *,
                 color = _AUTO_COLOR,
                 size: Union[str, float] = 18.0,
                 text_size: str = "small",
                 text_weight: str = "700",
                 bordered: bool = False,
                 stroke_color = None):
        if not isinstance(label, (str, Element)):
            raise TypeError(
                f"Badge.label must be str or Element; got {type(label)}"
            )
        if isinstance(size, str) and size not in self._SIZE_FACTORS:
            allowed = ", ".join(self._SIZE_FACTORS)
            raise ValueError(f"Badge.size must be numeric or one of {allowed}")
        self.label = label
        self.color = color
        self.size = size
        self.text_size = text_size
        self.text_weight = text_weight
        self.bordered = bordered
        self.stroke_color = stroke_color

    def _diameter(self, theme: Theme) -> float:
        if isinstance(self.size, str):
            floor = theme.unit * self._SIZE_FACTORS[self.size]
        else:
            floor = float(self.size)
        if isinstance(self.label, Element):
            label = self.label.measure(theme)
            floor = max(
                floor,
                label.w + theme.unit * 1.1,
                label.h + theme.unit * 1.1,
            )
        return floor

    def measure(self, theme: Theme) -> BBox:
        diameter = self._diameter(theme)
        return BBox(diameter, diameter)

    def _resolved_fill(self, theme: Theme) -> str:
        if self.color is Badge._AUTO_COLOR:
            # No explicit colour: bordered => transparent paper interior,
            # un-bordered => classic info-blue fill.
            return "none" if self.bordered else theme.color_of("info")
        return theme.color_of(self.color)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        fill = self._resolved_fill(theme)
        diameter = self._diameter(theme)
        cx = x + diameter / 2
        cy = y + diameter / 2
        stroke = "none"
        sw = 0.0
        if self.bordered:
            stroke = theme.color_of(self.stroke_color or "text")
            sw = theme.hairline
        canvas.circle(cx, cy, diameter / 2,
                     fill=fill, stroke=stroke, stroke_width=sw)
        if self.label:
            # For a transparent paper-style operator badge, the glyph
            # sits on the page background -- use the dark text colour
            # rather than "text_on(transparent)" which is undefined.
            if fill == "none":
                text_color = theme.color_of("text")
            else:
                text_color = theme.text_on(fill)
            if isinstance(self.label, Element):
                label = self.label.measure(theme)
                self.label.render(
                    canvas,
                    cx - label.w / 2,
                    cy - label.h / 2,
                    theme,
                )
            else:
                canvas.text(cx, cy, self.label,
                           size=theme.size_px(self.text_size),
                           fill=text_color,
                           weight=self.text_weight,
                           anchor="middle", baseline="middle")


