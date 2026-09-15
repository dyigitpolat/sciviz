"""Gauge: one bounded scalar reading, with the limits that bound it.

A number that lives inside a declared range -- a share, a utilisation, a
duty cycle, a confidence -- carries two facts: where it sits, and what
stops it from going further. A bare number states the first and hides the
second. A gauge states both, because the floor and the ceiling are marks
on the same track the reading is drawn on.

Two styles, one geometry: ``"dial"`` sweeps a half-circle and points a
needle at the value; ``"bar"`` lays the same track out straight. Marks
are declared in data units and may carry their own captions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass(frozen=True)
class GaugeMark:
    """A limit drawn on a gauge's track.

    Parameters
    ----------
    value : float
        Where the mark sits, in the gauge's own units.
    label : str, optional
        A short caption under (bar) or beside (dial) the mark.
    color : optional
        Colour override; defaults to the theme's strong border.
    dashed : bool
        Draw the mark dashed, the convention for a soft limit.
    """

    value: float
    label: str = ""
    color: object = None
    dashed: bool = False


MarkLike = Union[GaugeMark, Tuple, float]


class Gauge(Element):
    """A bounded reading on a dial or a straight track.

    Parameters
    ----------
    value : float
        The reading. Clamped to ``range`` for drawing; the caption still
        reports what was passed.
    range : (float, float)
        The declared bounds of the quantity.
    marks : sequence, optional
        :class:`GaugeMark` values, ``(value, label)`` tuples, or bare
        floats: the limits that bound the reading.
    style : {"dial", "bar"}
        ``"dial"`` is the half-circle form and reads as an instrument;
        ``"bar"`` is the straight form and packs into a table row.
    width, height : float
        The track's extent, before captions.
    role : ColorRef or str
        Colour of the filled span and the needle.
    show_value : bool
        Whether the reading is written in the gauge.
    value_format : str
        ``format`` spec for the reading and for end captions.
    end_labels : (str, str), optional
        Captions at the two ends of the track, in place of the numeric
        bounds.
    """

    def __init__(self, value: float, *,
                 range: Tuple[float, float] = (0.0, 1.0),
                 marks: Sequence[MarkLike] = (),
                 style: str = "dial",
                 width: float = 58.0, height: float = 34.0,
                 role="primary",
                 show_value: bool = True,
                 value_format: str = "{:g}",
                 end_labels: Optional[Tuple[str, str]] = None,
                 text_size: str = "tiny"):
        lo, hi = float(range[0]), float(range[1])
        if not hi > lo:
            raise ValueError("Gauge range must be increasing")
        if style not in ("dial", "bar"):
            raise ValueError('Gauge style must be "dial" or "bar"')
        self.value = float(value)
        self.range = (lo, hi)
        self.marks = [self._normalise(m) for m in marks]
        self.style = style
        self.width = float(width)
        self.height = float(height)
        self.role = role
        self.show_value = bool(show_value)
        self.value_format = value_format
        self.end_labels = end_labels
        self.text_size = text_size

    @staticmethod
    def _normalise(m: MarkLike) -> GaugeMark:
        if isinstance(m, GaugeMark):
            return m
        if isinstance(m, (int, float)):
            return GaugeMark(float(m))
        if len(m) == 2:
            return GaugeMark(float(m[0]), str(m[1]))
        raise ValueError(f"Gauge mark: GaugeMark, (value, label) or float; got {m!r}")

    # -- geometry ------------------------------------------------------

    def _frac(self, v: float) -> float:
        lo, hi = self.range
        return min(1.0, max(0.0, (v - lo) / (hi - lo)))

    def _caption_h(self, theme: Theme) -> float:
        rows = 0
        if self.end_labels or any(m.label for m in self.marks):
            rows += 1
        if self.show_value and self.style == "dial":
            # A dial paints only the upper half of its box, but the reading
            # is written under the pivot, so it claims a row of its own.
            rows += 1
        return theme.text_height(self.text_size) * 1.05 * rows

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width, self.height + self._caption_h(theme))

    # -- render --------------------------------------------------------

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self.style == "dial":
            self._render_dial(canvas, x, y, theme)
        else:
            self._render_bar(canvas, x, y, theme)
        self._render_end_labels(canvas, x, y, theme)

    def _colors(self, theme: Theme) -> Tuple[str, str, str]:
        body = theme.color_of(self.role)
        soft = (theme.color_of(self.role.soft()) if hasattr(self.role, "soft")
                else theme.role(str(self.role), "soft"))
        return body, soft, theme.color_of("border")

    def _render_end_labels(self, canvas: Canvas, x: float, y: float,
                           theme: Theme) -> None:
        if not self.end_labels:
            return
        size = theme.size_px(self.text_size)
        base = y + self.height + size * 0.82
        canvas.text(x, base, self.end_labels[0], size=size,
                    fill=theme.color_of("text_muted"), anchor="start")
        canvas.text(x + self.width, base, self.end_labels[1], size=size,
                    fill=theme.color_of("text_muted"), anchor="end")

    def _render_dial(self, canvas: Canvas, x: float, y: float,
                     theme: Theme) -> None:
        body, soft, track = self._colors(theme)
        r = min(self.width / 2, self.height)
        cx = x + self.width / 2
        cy = y + r
        ring = max(theme.line, r * 0.16)

        def point(frac: float, radius: float) -> Tuple[float, float]:
            ang = math.pi * (1.0 - frac)
            return cx + radius * math.cos(ang), cy - radius * math.sin(ang)

        def arc(frac_a: float, frac_b: float, color: str, w: float) -> None:
            ax, ay = point(frac_a, r - ring / 2)
            bx, by = point(frac_b, r - ring / 2)
            canvas.path(f"M {ax:.2f} {ay:.2f} A {r - ring / 2:.2f} "
                        f"{r - ring / 2:.2f} 0 0 1 {bx:.2f} {by:.2f}",
                        stroke=color, stroke_width=w, fill="none",
                        ink_bbox=(cx - r, cy - r, cx + r, cy))

        arc(0.0, 1.0, theme.color_of("bg_subtle"), ring)
        arc(0.0, 1.0, track, theme.hairline)
        frac = self._frac(self.value)
        if frac > 0:
            arc(0.0, frac, soft, ring)

        for mark in self.marks:
            mf = self._frac(mark.value)
            inner = point(mf, r - ring * 1.15)
            outer = point(mf, r + ring * 0.12)
            canvas.line(inner[0], inner[1], outer[0], outer[1],
                        stroke=theme.color_of(mark.color) if mark.color is not None
                        else theme.color_of("border_strong"),
                        stroke_width=theme.line,
                        dasharray="1.6,1.2" if mark.dashed else None)

        nx, ny = point(frac, r - ring * 1.25)
        canvas.line(cx, cy, nx, ny, stroke=body, stroke_width=theme.thick)
        canvas.circle(cx, cy, max(1.2, ring * 0.28), fill=body, stroke="none")

        self._render_mark_labels_dial(canvas, x, cx, cy, r, theme)

        if self.show_value:
            # Under the pivot: the needle owns the half-disc above it, so
            # the reading cannot be written inside the sweep at any angle.
            size = theme.size_px(self.text_size)
            canvas.text(cx, cy + size * 0.95, self.value_format.format(self.value),
                        size=size, fill=theme.color_of("text"), anchor="middle")

    def _render_mark_labels_dial(self, canvas: Canvas, x: float, cx: float,
                                 cy: float, r: float, theme: Theme) -> None:
        """Mark captions outside the sweep, clamped to the measured box.

        A caption that ran past the box edge would be ink the parent never
        reserved, so a mark near either end of the sweep gives up its
        outward offset rather than its containment. Long captions belong
        on the bar style, whose track carries them under the mark.
        """
        size = theme.size_px(self.text_size)
        for mark in self.marks:
            if not mark.label:
                continue
            mf = self._frac(mark.value)
            ang = math.pi * (1.0 - mf)
            lx = cx + (r + size * 0.32) * math.cos(ang)
            ly = cy - (r + size * 0.32) * math.sin(ang) + size * 0.34
            anchor = "end" if mf < 0.5 else "start"
            width = theme.text_width(mark.label, self.text_size)
            if anchor == "end":
                lx = max(lx, x + width)
            else:
                lx = min(lx, x + self.width - width)
            canvas.text(lx, ly, mark.label, size=size, anchor=anchor,
                        fill=theme.color_of("text_muted"))

    def _render_bar(self, canvas: Canvas, x: float, y: float,
                    theme: Theme) -> None:
        body, soft, track = self._colors(theme)
        h = self.height
        canvas.rect(x, y, self.width, h, fill=theme.color_of("bg_subtle"),
                    stroke=track, stroke_width=theme.hairline, rx=1.0)
        frac = self._frac(self.value)
        if frac > 0:
            canvas.rect(x, y, self.width * frac, h, fill=soft,
                        stroke=body, stroke_width=theme.hairline, rx=1.0)
        size = theme.size_px(self.text_size)
        for mark in self.marks:
            mx = x + self.width * self._frac(mark.value)
            canvas.line(mx, y - h * 0.16, mx, y + h * 1.16,
                        stroke=theme.color_of(mark.color) if mark.color is not None
                        else theme.color_of("border_strong"),
                        stroke_width=theme.line,
                        dasharray="1.6,1.2" if mark.dashed else None)
            if mark.label and not self.end_labels:
                canvas.text(mx, y + h + size * 0.98, mark.label, size=size,
                            anchor="middle", fill=theme.color_of("text_muted"))
        if self.show_value:
            size = theme.size_px(self.text_size)
            canvas.text(x + self.width * frac, y + h * 0.5 + size * 0.34,
                        " " + self.value_format.format(self.value),
                        size=size, fill=theme.color_of("text"), anchor="start")
