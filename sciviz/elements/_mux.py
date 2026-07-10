"""Semantic multiplexer gate for hardware and data-path diagrams."""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme
from ._obstacles import _register_implicit_obstacle


class Mux(Element):
    """A tapered multiplexer with orientation-owned paper geometry."""

    _SIZES = {
        "sm": (4.2, 5.4),
        "md": (5.0, 6.5),
        "lg": (6.0, 7.8),
    }

    def __init__(self, label: str = "MUX", *, orientation: str = "down",
                 size: str = "md", fill="bg_subtle", stroke="text",
                 text_color="auto", text_size="tiny",
                 stroke_width: Optional[float] = None,
                 vertical_text: Optional[bool] = None,
                 wrap: bool = True):
        if orientation not in ("up", "down", "left", "right"):
            raise ValueError("Mux.orientation must be up/down/left/right")
        if size not in self._SIZES:
            raise ValueError("Mux.size must be sm/md/lg")
        self.label = str(label)
        self.orientation = orientation
        self.size = size
        self.fill = fill
        self.stroke = stroke
        self.text_color = text_color
        self.text_size = text_size
        self.stroke_width = stroke_width
        self.vertical_text = (
            orientation in ("up", "down")
            if vertical_text is None else bool(vertical_text)
        )
        self.wrap = bool(wrap)
        self._min_w = 0.0
        self._min_h = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def _label_lines(self, theme: Theme):
        explicit = self.label.split("\n") if self.label else []
        if self.vertical_text or not self.wrap:
            return explicit
        _short, long = self._SIZES[self.size]
        budget = long * theme.unit * 1.5 - theme.unit * 2.0
        lines = []
        for line in explicit:
            words = line.split()
            if len(words) <= 1:
                lines.append(line)
                continue
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if (not current or theme.text_width(
                        candidate, self.text_size, bold=True) <= budget):
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
        return lines

    def measure(self, theme: Theme) -> BBox:
        short, long = self._SIZES[self.size]
        if self.orientation in ("up", "down"):
            w, h = short * theme.unit, long * theme.unit
            if not self.vertical_text:
                # A horizontal label turns the up/down mux into the familiar
                # shallow tapered module. Give it a semantic line-length
                # budget before measuring text so multiword labels wrap
                # instead of flattening the silhouette.
                w, h = long * theme.unit * 1.5, short * theme.unit
        else:
            w, h = long * theme.unit, short * theme.unit
        lines = self._label_lines(theme)
        if lines:
            text_w = max(
                theme.text_width(line, self.text_size, bold=True)
                for line in lines
            )
            line_h = theme.text_height(self.text_size)
            text_h = line_h * len(lines) + line_h * 0.05 * max(0, len(lines) - 1)
            if self.vertical_text:
                w = max(w, text_h + theme.unit * 1.2)
                h = max(h, text_w + theme.unit * 2.0)
            else:
                w = max(w, text_w + theme.unit * 2.0)
                h = max(h, text_h + theme.unit * 1.2)
        return BBox(max(w, self._min_w), max(h, self._min_h))

    def _points(self, x: float, y: float, w: float, h: float):
        taper = 0.24
        if self.orientation == "down":
            return [(x, y), (x + w, y),
                    (x + w * (1 - taper), y + h),
                    (x + w * taper, y + h)]
        if self.orientation == "up":
            return [(x + w * taper, y), (x + w * (1 - taper), y),
                    (x + w, y + h), (x, y + h)]
        if self.orientation == "right":
            return [(x, y), (x + w, y + h * taper),
                    (x + w, y + h * (1 - taper)), (x, y + h)]
        return [(x + w, y), (x, y + h * taper),
                (x, y + h * (1 - taper)), (x + w, y + h)]

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        size = self.measure(theme)
        fill = theme.paint_of(self.fill)
        stroke = theme.paint_of(self.stroke)
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        canvas.polygon(
            self._points(x, y, size.w, size.h),
            fill=fill, stroke=stroke, stroke_width=sw,
        )
        _register_implicit_obstacle(x, y, size.w, size.h)
        text_color = (
            theme.text_on(fill)
            if self.text_color == "auto"
            else theme.color_of(self.text_color)
        )
        rotate = 0.0
        if self.vertical_text:
            rotate = 90.0 if self.orientation == "up" else -90.0
        lines = self._label_lines(theme)
        if rotate or len(lines) <= 1:
            canvas.text(
                x + size.w / 2.0, y + size.h / 2.0, self.label,
                size=theme.size_px(self.text_size), fill=text_color,
                weight="700", anchor="middle", baseline="middle",
                rotate=rotate,
            )
        else:
            line_h = theme.text_height(self.text_size)
            block_h = line_h * len(lines) + line_h * 0.05 * max(0, len(lines) - 1)
            top = y + (size.h - block_h) / 2.0
            for index, line in enumerate(lines):
                canvas.text(
                    x + size.w / 2.0,
                    top + line_h * (index + 0.5) + line_h * 0.05 * index,
                    line,
                    size=theme.size_px(self.text_size), fill=text_color,
                    weight="700", anchor="middle", baseline="middle",
                )


__all__ = ["Mux"]
