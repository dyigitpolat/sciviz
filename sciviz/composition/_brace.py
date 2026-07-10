"""Brace: semantic horizontal or vertical grouping brace.

Two construction modes:

* ``Brace(span, label=...)`` -- explicit pixel span (the historic API).
* ``Brace.spanning(element, label=...)`` -- defer span computation until
  measure time. The returned ``Brace`` measures the child first, then
  inherits its width as the brace span. Compose this with a
  :class:`~sciviz.Column` to render the brace directly below (or above)
  any element without hard-coding widths.
"""

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
        if direction not in ("down", "up", "left", "right"):
            raise ValueError("Brace.direction must be down/up/left/right")
        self.span = float(span)
        self.label = label
        self.direction = direction
        self.color = color
        self.height = float(height)
        self.label_size = label_size
        # Deferred span source; when set, ``span`` is recomputed at
        # measure() time from the element's width.
        self._span_source: Optional[Element] = None

    @classmethod
    def spanning(cls, element: Element, label: Optional[str] = None, *,
                 direction: str = "down",
                 color="muted",
                 height: float = 6.0,
                 label_size: str = "small") -> "Brace":
        """Return a :class:`Brace` whose ``span`` matches ``element``'s width.

        The span is resolved lazily at :meth:`measure`, so the brace
        stays in sync even if the element's size changes between
        construction and rendering (e.g. inside an :class:`AlignedStack`).
        """
        if not isinstance(element, Element):
            raise TypeError(
                f"Brace.spanning(...) needs an Element; got {type(element)}")
        # Start with a throwaway span; refreshed each measure.
        brace = cls(1.0, label=label, direction=direction, color=color,
                    height=height, label_size=label_size)
        brace._span_source = element
        return brace

    def _refresh_span(self, theme: Theme) -> None:
        if self._span_source is not None:
            source = self._span_source.measure(theme)
            self.span = float(
                source.h if self.direction in ("left", "right") else source.w
            )

    def _label_lines(self) -> list[str]:
        return self.label.splitlines() if self.label else []

    def _vertical_label_width(self, theme: Theme) -> float:
        lines = self._label_lines()
        return max(
            (theme.text_width(line, self.label_size) for line in lines),
            default=0.0,
        )

    def measure(self, theme: Theme) -> BBox:
        self._refresh_span(theme)
        if self.direction in ("left", "right"):
            label_w = self._vertical_label_width(theme)
            label_gap = theme.unit * 0.5 if self.label else 0.0
            w = self.height + 3 + label_gap + label_w
            label_h = len(self._label_lines()) * theme.text_height(
                self.label_size)
            return BBox(w, max(self.span, label_h))
        h = self.height + 2
        if self.label:
            h += theme.text_height(self.label_size) + theme.unit * 0.4
        return BBox(self.span, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._refresh_span(theme)
        col = theme.color_of(self.color)
        sz = theme.size_px(self.label_size)
        if self.direction in ("left", "right"):
            self._render_vertical(canvas, x, y, theme, col, sz)
            return
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
            # Overbrace: endpoints at bottom, tip projects upward, label
            # sits above the tip.  Shift every y coordinate down by the
            # reserved label-strip height so the label fits inside the
            # bbox (previously it rendered above ``y`` and got clipped by
            # sibling containers).
            label_h = (theme.text_height(self.label_size)
                       + theme.unit * 0.4) if self.label else 0.0
            offset = label_h + 3  # +3 so the tip stays inside the bbox
            bot = y + offset + self.height
            shoulder = y + offset + self.height * 0.45
            tip = y + offset - 3
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
                canvas.text(mid, y + sz * 0.85, self.label,
                           size=sz, fill=col, anchor="middle")

    def _render_vertical(self, canvas: Canvas, x: float, y: float,
                         theme: Theme, color: str, size_px: float) -> None:
        """Render a side brace whose span tracks a sibling's height."""
        size = self.measure(theme)
        top = y + (size.h - self.span) / 2
        bottom = top + self.span
        mid = (top + bottom) / 2
        shoulder_offset = self.height * 0.55
        tip_offset = self.height + 3
        label_gap = theme.unit * 0.5

        if self.direction == "right":
            base = x
            shoulder = base + shoulder_offset
            tip = base + tip_offset
            label_x = tip + label_gap
            label_anchor = "start"
        else:
            base = x + size.w
            shoulder = base - shoulder_offset
            tip = base - tip_offset
            label_x = tip - label_gap
            label_anchor = "end"

        d = (
            f"M {base:.2f},{top:.2f} "
            f"Q {shoulder:.2f},{top:.2f} {shoulder:.2f},{top + 6:.2f} "
            f"L {shoulder:.2f},{mid - 6:.2f} "
            f"Q {shoulder:.2f},{mid:.2f} {tip:.2f},{mid:.2f} "
            f"Q {shoulder:.2f},{mid:.2f} {shoulder:.2f},{mid + 6:.2f} "
            f"L {shoulder:.2f},{bottom - 6:.2f} "
            f"Q {shoulder:.2f},{bottom:.2f} {base:.2f},{bottom:.2f}"
        )
        canvas.path(d, stroke=color, fill="none",
                    stroke_width=theme.hairline)

        lines = self._label_lines()
        if not lines:
            return
        line_h = theme.text_height(self.label_size)
        first_baseline = mid - len(lines) * line_h / 2 + size_px * 0.82
        for index, line in enumerate(lines):
            canvas.text(
                label_x,
                first_baseline + index * line_h,
                line,
                size=size_px,
                fill=color,
                anchor=label_anchor,
            )


