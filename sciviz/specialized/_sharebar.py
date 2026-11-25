"""ShareBar: one thin bar showing a share of a whole.

A light track of fixed length stands for the whole and a solid fill for the
share, starting at a short origin tick; a share of zero leaves only the
track and the tick, so "none" stays visible. For inline measurements beside
a label and a number (``Table`` rows), where a chart would be too much.
"""

from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme


class ShareBar(Element):
    """A thin horizontal bar: ``share`` (0 to 1) of a track ``width`` px long.

    Parameters
    ----------
    share : float
        The filled share of the track, 0 to 1.
    width : float
        Track length in px (the whole).
    height : float, optional
        Bar thickness in px; default 0.45 of the ``small`` text size.
    color : str
        Fill colour (a palette role or hex), e.g. a status colour.
    track : bool
        Draw the light track for the whole (default true).
    """

    def __init__(self, share: float, *, width: float = 60.0,
                 height: Optional[float] = None, color: str = "text_muted",
                 track: bool = True):
        share = float(share)
        if not 0.0 <= share <= 1.0:
            raise ValueError(f"ShareBar.share must be within 0 and 1; got {share!r}")
        if width <= 0:
            raise ValueError(f"ShareBar.width must be positive; got {width!r}")
        self.share = share
        self.width = float(width)
        self.height = height
        self.color = color
        self.track = track

    def _h(self, theme: Theme) -> float:
        return (float(self.height) if self.height is not None
                else theme.size_px("small") * 0.45)

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width, self._h(theme) + 1.6)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        h = self._h(theme)
        top = y + 0.8
        if self.track:
            canvas.rect(x, top, self.width, h, fill=_light(theme.color_of("border")))
        if self.share > 0:
            canvas.rect(x, top, self.width * self.share, h, fill=theme.color_of(self.color))
        canvas.line(x, y, x, y + h + 1.6, stroke=theme.color_of("text_muted"),
                    stroke_width=theme.hairline)


def _light(hex_color: str, amount: float = 0.78) -> str:
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return hex_color
    rgb = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(v + (255 - v) * amount):02x}" for v in rgb)
