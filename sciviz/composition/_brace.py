"""Brace: horizontal curly brace with an optional label."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme

class Brace(Element):
    """A horizontal curly brace with an optional label.

    Used to visually group a set of items above or below the brace.  Common
    in math figures (\\underbrace, \\overbrace) and in diagrams to show
    groupings like "Visual Tokens" or "Action Tokens".

    Parameters
    ----------
    span : float
        Pixel width spanned by the brace.
    label : str, optional
        Text label, placed below ("down") or above ("up") the brace.
    direction : str
        ``"down"`` (default, label below) or ``"up"`` (label above).
    color : ColorRef or str
        Stroke + label colour.
    height : float
        Vertical extent of the brace's curve.
    """

    def __init__(self, span: float, label: Optional[str] = None, *,
                 direction: str = "down",
                 color = "muted",
                 height: float = 6.0,
                 label_size: str = "small"):
        self.span = float(span)
        self.label = label
        self.direction = direction
        self.color = color
        self.height = float(height)
        self.label_size = label_size

    def measure(self, theme: Theme) -> BBox:
        h = self.height + 2
        if self.label:
            h += theme.text_height(self.label_size) + theme.unit * 0.4
        return BBox(self.span, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        col = theme.color_of(self.color)
        sz = theme.size_px(self.label_size)
        if self.direction == "down":
            # Brace points downward (label below).  Side endpoints sit at the
            # TOP of the brace region; the central tip drops below.
            top = y                              # endpoints level
            shoulder = y + self.height * 0.55    # where side curves meet horizontals
            tip = y + self.height + 3            # central tip drops past base
            mid = x + self.span / 2
            d = (
                f"M {x:.2f},{top:.2f} "
                f"Q {x:.2f},{shoulder:.2f} {x + 6:.2f},{shoulder:.2f} "
                f"L {mid - 6:.2f},{shoulder:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid:.2f},{tip:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid + 6:.2f},{shoulder:.2f} "
                f"L {x + self.span - 6:.2f},{shoulder:.2f} "
                f"Q {x + self.span:.2f},{shoulder:.2f} {x + self.span:.2f},{top:.2f}"
            )
            canvas.path(d, stroke=col, fill="none", stroke_width=theme.hairline)
            if self.label:
                canvas.text(mid, tip + sz + 2, self.label,
                           size=sz, fill=col, anchor="middle")
        else:  # "up"
            bot = y + self.height
            shoulder = y + self.height * 0.45
            tip = y - 3
            mid = x + self.span / 2
            d = (
                f"M {x:.2f},{bot:.2f} "
                f"Q {x:.2f},{shoulder:.2f} {x + 6:.2f},{shoulder:.2f} "
                f"L {mid - 6:.2f},{shoulder:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid:.2f},{tip:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid + 6:.2f},{shoulder:.2f} "
                f"L {x + self.span - 6:.2f},{shoulder:.2f} "
                f"Q {x + self.span:.2f},{shoulder:.2f} {x + self.span:.2f},{bot:.2f}"
            )
            canvas.path(d, stroke=col, fill="none", stroke_width=theme.hairline)
            if self.label:
                canvas.text(mid, tip - 6, self.label,
                           size=sz, fill=col, anchor="middle")



