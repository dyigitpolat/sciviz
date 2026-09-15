"""Balance: two quantities weighed against each other.

A bar chart of two numbers answers "how big is each". A balance answers
the question that is actually being asked when two channels, arms or
budgets are compared: *which one is winning, and by how much*. The beam
tilts toward the heavier side, so the verdict is in the silhouette and
the magnitudes stay legible in the pans.

The tilt is a bounded function of the relative difference
``(l - r) / (l + r)``, never of the raw values, so a balance between two
large numbers and a balance between two small ones read the same when the
ratio is the same, and no pair of values can tip the beam past
``max_tilt``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass(frozen=True)
class BalancePan:
    """One side of a :class:`Balance`.

    Parameters
    ----------
    label : str
        What is being weighed on this side.
    value : float
        Its weight, in units shared with the other pan. Non-negative.
    color : optional
        Colour of the pan and its caption.
    """

    label: str
    value: float
    color: object = None


PanLike = Union[BalancePan, Tuple]


class Balance(Element):
    """A beam that tilts toward the heavier of two pans.

    Parameters
    ----------
    left, right : BalancePan or tuple
        The two sides, as :class:`BalancePan` values or
        ``(label, value)`` / ``(label, value, color)`` tuples.
    width, height : float
        The instrument's extent, before captions.
    max_tilt : float
        The steepest beam angle, in degrees. A relative difference of
        ``1.0`` (one side empty) reaches exactly this angle.
    show_values : bool
        Whether each pan's value is written under its label.
    value_format : str
        ``format`` spec for the values.
    """

    def __init__(self, left: PanLike, right: PanLike, *,
                 width: float = 76.0, height: float = 40.0,
                 max_tilt: float = 14.0,
                 show_values: bool = True,
                 value_format: str = "{:g}",
                 text_size: str = "tiny"):
        self.left = self._normalise(left)
        self.right = self._normalise(right)
        if self.left.value < 0 or self.right.value < 0:
            raise ValueError("Balance pan values must be non-negative")
        self.width = float(width)
        self.height = float(height)
        self.max_tilt = abs(float(max_tilt))
        self.show_values = bool(show_values)
        self.value_format = value_format
        self.text_size = text_size

    @staticmethod
    def _normalise(p: PanLike) -> BalancePan:
        if isinstance(p, BalancePan):
            return p
        if len(p) == 2:
            return BalancePan(str(p[0]), float(p[1]))
        if len(p) == 3:
            return BalancePan(str(p[0]), float(p[1]), p[2])
        raise ValueError(f"Balance pan: (label, value[, color]); got {p!r}")

    # -- geometry ------------------------------------------------------

    @property
    def tilt(self) -> float:
        """Beam angle in degrees, positive when the left pan is heavier."""
        total = self.left.value + self.right.value
        if total <= 0:
            return 0.0
        rel = (self.left.value - self.right.value) / total
        return self.max_tilt * rel

    def _caption_lines(self, pan: BalancePan) -> list[str]:
        lines = [pan.label] if pan.label else []
        if self.show_values:
            lines.append(self.value_format.format(pan.value))
        return lines

    def _caption_h(self, theme: Theme) -> float:
        rows = max(len(self._caption_lines(self.left)),
                   len(self._caption_lines(self.right)))
        return rows * theme.text_height(self.text_size) * 1.02

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width, self.height + self._caption_h(theme))

    # -- render --------------------------------------------------------

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        ink = theme.color_of("border_strong")
        cx = x + self.width / 2
        base_y = y + self.height

        # The instrument is sized from its extremes inward, so no tilt in
        # [-max_tilt, max_tilt] can push a pan past the measured box: the
        # arm keeps half a pan's width clear of each side, and the pivot
        # sits exactly one full tilt travel below the top edge, leaving
        # the hanger just enough room to reach the base at the other end.
        pan_w = self.width * 0.28
        arm = (self.width - pan_w) / 2
        bowl = pan_w * 0.30
        travel = arm * math.sin(math.radians(self.max_tilt))
        pivot_y = y + travel + theme.hairline
        drop = max(2.0, base_y - pivot_y - travel - bowl)

        # stand: a pillar on a foot, the fixed part of the instrument
        foot_w = self.width * 0.20
        canvas.line(cx, pivot_y, cx, base_y - theme.hairline,
                    stroke=ink, stroke_width=theme.line)
        canvas.line(cx - foot_w / 2, base_y, cx + foot_w / 2, base_y,
                    stroke=ink, stroke_width=theme.line)

        angle = math.radians(self.tilt)
        dx, dy = arm * math.cos(angle), arm * math.sin(angle)
        # Positive tilt means the left pan is heavier, so it hangs lower:
        # screen y grows downward, hence the left end takes +dy.
        lx, ly = cx - dx, pivot_y + dy
        rx, ry = cx + dx, pivot_y - dy
        canvas.line(lx, ly, rx, ry, stroke=ink, stroke_width=theme.line)
        canvas.circle(cx, pivot_y, max(1.1, theme.line), fill=ink, stroke="none")

        self._pan(canvas, self.left, lx, ly, drop, pan_w, theme)
        self._pan(canvas, self.right, rx, ry, drop, pan_w, theme)

        size = theme.size_px(self.text_size)
        for pan, px, anchor in ((self.left, x, "start"),
                                (self.right, x + self.width, "end")):
            color = (theme.color_of(pan.color) if pan.color is not None
                     else theme.color_of("text_muted"))
            for i, line in enumerate(self._caption_lines(pan)):
                canvas.text(px, base_y + size * (0.96 + 1.02 * i), line,
                            size=size, fill=color, anchor=anchor)

    def _pan(self, canvas: Canvas, pan: BalancePan, px: float, py: float,
             drop: float, pan_w: float, theme: Theme) -> None:
        ink = theme.color_of("border_strong")
        color = pan.color if pan.color is not None else "primary"
        body = theme.color_of(color)
        soft = (theme.color_of(color.soft()) if hasattr(color, "soft")
                else theme.role(str(color), "soft"))
        canvas.line(px, py, px, py + drop, stroke=ink,
                    stroke_width=theme.hairline)
        top = py + drop
        half = pan_w / 2
        bowl = pan_w * 0.30
        canvas.path(
            f"M {px - half:.2f} {top:.2f} "
            f"A {half:.2f} {bowl:.2f} 0 0 0 {px + half:.2f} {top:.2f} Z",
            fill=soft, stroke=body, stroke_width=theme.hairline,
            ink_bbox=(px - half, top, px + half, top + bowl))
