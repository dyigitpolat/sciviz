"""Small semantic glyphs for conditional/alternative steps."""

from __future__ import annotations

from typing import Union

from ..core import BBox, Canvas, Element, Theme


class ConditionGlyph(Element):
    """A tiny symbolic mark for conditional structure.

    The glyph is intentionally abstract: the legend explains the semantic
    once, while individual cards avoid code-like labels such as ``if act_q``.
    """

    _KINDS = {"branch", "toggle", "alternative", "verification"}

    def __init__(self, kind: str, *, size: Union[str, float] = "tiny",
                 color="muted", stroke_width: float = 1.2):
        if kind not in self._KINDS:
            raise ValueError(
                f"Unknown condition glyph {kind!r}; expected one of {sorted(self._KINDS)}"
            )
        self.kind = kind
        self.size = size
        self.color = color
        self.stroke_width = float(stroke_width)

    def _size_px(self, theme: Theme) -> float:
        if isinstance(self.size, (int, float)):
            return float(self.size)
        return theme.size_px(self.size) * 1.35

    def measure(self, theme: Theme) -> BBox:
        s = self._size_px(theme)
        return BBox(s, s)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        s = self._size_px(theme)
        c = theme.color_of(self.color)
        sw = self.stroke_width
        cx = x + s / 2
        cy = y + s / 2
        if self.kind == "toggle":
            canvas.rect(x + s * 0.12, y + s * 0.30, s * 0.76, s * 0.40,
                        fill="none", stroke=c, stroke_width=sw, rx=s * 0.20)
            canvas.circle(x + s * 0.62, cy, s * 0.14, fill=c, stroke=c,
                          stroke_width=sw)
        elif self.kind == "branch":
            canvas.line(x + s * 0.18, cy, x + s * 0.48, cy,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.48, cy, x + s * 0.78, y + s * 0.25,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.48, cy, x + s * 0.78, y + s * 0.75,
                        stroke=c, stroke_width=sw)
            canvas.circle(x + s * 0.80, y + s * 0.25, s * 0.08, fill=c, stroke=c)
            canvas.circle(x + s * 0.80, y + s * 0.75, s * 0.08, fill=c, stroke=c)
        elif self.kind == "alternative":
            canvas.line(x + s * 0.20, y + s * 0.35, x + s * 0.78, y + s * 0.35,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.68, y + s * 0.22, x + s * 0.80, y + s * 0.35,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.68, y + s * 0.48, x + s * 0.80, y + s * 0.35,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.80, y + s * 0.65, x + s * 0.22, y + s * 0.65,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.32, y + s * 0.52, x + s * 0.20, y + s * 0.65,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.32, y + s * 0.78, x + s * 0.20, y + s * 0.65,
                        stroke=c, stroke_width=sw)
        else:  # verification
            pts = [
                (cx, y + s * 0.12), (x + s * 0.78, y + s * 0.25),
                (x + s * 0.70, y + s * 0.75), (cx, y + s * 0.90),
                (x + s * 0.30, y + s * 0.75), (x + s * 0.22, y + s * 0.25),
            ]
            canvas.polygon(pts, fill="none", stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.34, y + s * 0.54, x + s * 0.46, y + s * 0.66,
                        stroke=c, stroke_width=sw)
            canvas.line(x + s * 0.46, y + s * 0.66, x + s * 0.68, y + s * 0.42,
                        stroke=c, stroke_width=sw)
