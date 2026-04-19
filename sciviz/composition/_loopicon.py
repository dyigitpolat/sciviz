"""LoopIcon: '↻' glyph used for 'repeat N times' annotations."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

class LoopIcon(Element):
    """A small circular arrow drawn as vector paths.

    Used as a visual "repeat N times" marker without relying on a
    symbol-capable font.  The equivalent unicode glyph (``\u21bb``) is
    only rendered correctly if the host system ships a font that
    covers the Miscellaneous Symbols and Arrows block; drawing the
    shape as SVG paths sidesteps that portability question.

    Parameters
    ----------
    size : float
        Overall bounding-box diameter in pixels.
    color : ColorRef or str
        Stroke and arrowhead colour (default ``"info"``).
    fill : ColorRef or str, optional
        Background disc colour.  ``None`` (default) draws just the
        arrow on a transparent background.
    stroke_width : float, optional
        Arrow stroke width.  Defaults to ``max(1.2, size * 0.08)``.
    """

    def __init__(self, *, size: float = 20.0,
                 color = "info",
                 fill = None,
                 stroke_width: Optional[float] = None):
        self.size = size
        self.color = color
        self.fill = fill
        self.stroke_width = stroke_width

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.size, self.size)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        import math as _math
        s = self.size
        cx = x + s / 2
        cy = y + s / 2
        stroke_col = theme.color_of(self.color)
        if self.fill is not None:
            canvas.circle(cx, cy, s / 2,
                          fill=theme.color_of(self.fill),
                          stroke="none")
        sw = self.stroke_width if self.stroke_width is not None \
            else max(1.2, s * 0.1)
        r = s * 0.34

        # Near-full-circle "repeat / refresh" glyph.  Arc sweeps
        # clockwise (visually) through the bottom and both sides,
        # leaving a gap at the TOP where the arrowhead caps the
        # head.  The arrowhead tail-tips point tangentially away
        # from the arc head (along the direction of motion).
        #
        # Endpoints live on the upper half of the circle, symmetric
        # about the vertical axis: tail angle = -90 - half_gap,
        # head angle = -90 + half_gap (SVG y-down).  large_arc=1
        # picks the LONG path; sweep=0 picks the mathematically CCW
        # direction, which in SVG screen space renders as the
        # visually CLOCKWISE direction -- so the arc passes under
        # the centre first, then up the right and through the gap.
        half_gap_deg = 45.0
        tail_deg = -90.0 - half_gap_deg
        head_deg = -90.0 + half_gap_deg
        tr = _math.radians(tail_deg)
        hr = _math.radians(head_deg)
        tx, ty = cx + r * _math.cos(tr), cy + r * _math.sin(tr)
        hx, hy = cx + r * _math.cos(hr), cy + r * _math.sin(hr)
        d = (f"M {tx:.2f},{ty:.2f} "
             f"A {r:.2f},{r:.2f} 0 1 0 {hx:.2f},{hy:.2f}")
        canvas.path(d, stroke=stroke_col, fill="none", stroke_width=sw)

        # Arrowhead at the head end.  The arc arrives at `head_deg`
        # travelling in the mathematically CCW direction, whose
        # screen-space tangent is (+sin(head), -cos(head)).  That is
        # UP-AND-RIGHT at head_deg = -45 deg, which matches the
        # conventional "refresh arrow" tail-pointing-right-and-up.
        tang = (_math.sin(hr), -_math.cos(hr))
        head_len = s * 0.26
        head_w = s * 0.22
        tip_x = hx + tang[0] * head_len
        tip_y = hy + tang[1] * head_len
        # Arrowhead base straddles the arc endpoint, perpendicular
        # to the tangent.
        perp = (-tang[1], tang[0])
        bx, by = hx, hy
        p1 = (bx + perp[0] * head_w / 2, by + perp[1] * head_w / 2)
        p2 = (bx - perp[0] * head_w / 2, by - perp[1] * head_w / 2)
        canvas.polygon([(tip_x, tip_y), p1, p2],
                       fill=stroke_col, stroke="none")



