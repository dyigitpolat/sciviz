"""Arrow / Connector: internal straight-arrow primitives (now hidden
behind :class:`sciviz.connect.Connect` in the public API)."""

from __future__ import annotations

from typing import List, Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Arrow(Element):
    """A simple directed arrow with optional label(s) running along it.

    When used inside a :class:`Row` or :class:`Column` the arrow occupies a
    fixed axis length; labels stack perpendicular to the arrow so they fit in
    the gap between neighbours.
    """

    def __init__(self, label: Optional[Union[str, List[str]]] = None, *,
                 direction: str = "right",
                 length: Optional[float] = None,
                 color: str = "text_muted",
                 label_color: str = "muted",
                 italic: bool = True,
                 size: Union[str, float] = "small",
                 head: bool = True):
        if isinstance(label, str):
            self.labels = [label]
        elif label is None:
            self.labels = []
        else:
            self.labels = list(label)
        self.direction = direction  # "right", "left", "down", "up"
        self.length = length
        self.color = color
        self.label_color = label_color
        self.italic = italic
        self.size = size
        self.head = head

    # ------------- layout helpers -------------

    def _axis_len(self, theme: Theme) -> float:
        if self.length is not None:
            return float(self.length)
        # Default: enough room for the longest label, clamped
        sz = self.size
        bold = False
        longest = max((theme.text_width(l, sz, bold=bold) for l in self.labels),
                      default=0.0)
        return max(48.0, longest + theme.unit * 2)

    def _label_band(self, theme: Theme) -> float:
        if not self.labels:
            return 0.0
        line_h = theme.text_height(self.size) * 0.95
        return line_h * len(self.labels) + theme.unit * 0.5

    # ------------- measure & render -------------

    def measure(self, theme: Theme) -> BBox:
        axis = self._axis_len(theme)
        band = self._label_band(theme)
        if self.direction in ("right", "left"):
            return BBox(axis, max(band * 2 + theme.unit, theme.unit * 3))
        return BBox(max(band * 2 + theme.unit, theme.unit * 3), axis)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        color = theme.color_of(self.color)
        marker = (canvas.define_arrow_marker(
                      color=color, stroke_width=theme.connector,
                      arrow_size=getattr(theme, "arrow_size", None))
                  if self.head else None)

        if self.direction in ("right", "left"):
            axis_y = y + size.h / 2
            if self.direction == "right":
                x1, x2 = x, x + size.w
            else:
                x1, x2 = x + size.w, x
            canvas.line(x1, axis_y, x2, axis_y,
                       stroke=color, stroke_width=theme.connector,
                       marker_end=marker)
            self._draw_labels_horizontal(canvas, x, y, size, axis_y, theme)
        else:
            axis_x = x + size.w / 2
            if self.direction == "down":
                y1, y2 = y, y + size.h
            else:
                y1, y2 = y + size.h, y
            canvas.line(axis_x, y1, axis_x, y2,
                       stroke=color, stroke_width=theme.connector,
                       marker_end=marker)
            self._draw_labels_vertical(canvas, x, y, size, axis_x, theme)

    def _draw_labels_horizontal(self, canvas, x, y, size, axis_y, theme):
        if not self.labels:
            return
        sz = theme.size_px(self.size)
        line_h = theme.text_height(self.size) * 0.95
        color = theme.color_of(self.label_color)
        cx = x + size.w / 2
        n = len(self.labels)
        # split: first half above, second half below (if odd, middle one above)
        above = self.labels[:(n + 1) // 2]
        below = self.labels[(n + 1) // 2:]
        # draw above, stacked upward from axis
        for i, lbl in enumerate(above):
            yy = axis_y - theme.unit * 0.6 - (len(above) - 1 - i) * line_h
            baseline = yy
            canvas.text(cx, baseline, lbl, size=sz, fill=color,
                       anchor="middle", italic=self.italic)
        for i, lbl in enumerate(below):
            baseline = axis_y + theme.unit * 0.6 + sz + i * line_h
            canvas.text(cx, baseline, lbl, size=sz, fill=color,
                       anchor="middle", italic=self.italic)

    def _draw_labels_vertical(self, canvas, x, y, size, axis_x, theme):
        if not self.labels:
            return
        sz = theme.size_px(self.size)
        line_h = theme.text_height(self.size) * 0.95
        color = theme.color_of(self.label_color)
        cy = y + size.h / 2
        n = len(self.labels)
        left = self.labels[:(n + 1) // 2]
        right = self.labels[(n + 1) // 2:]
        for i, lbl in enumerate(left):
            rx = axis_x - theme.unit * 0.8 - i * (sz * 1.2)
            canvas.text(rx, cy + sz * 0.35, lbl, size=sz, fill=color,
                       anchor="end", italic=self.italic)
        for i, lbl in enumerate(right):
            rx = axis_x + theme.unit * 0.8 + i * (sz * 1.2)
            canvas.text(rx, cy + sz * 0.35, lbl, size=sz, fill=color,
                       anchor="start", italic=self.italic)


# convenience alias for readability: `Connector("map to", "hardware")`
class Connector(Arrow):
    """An :class:`Arrow` that accepts labels as positional args."""

    def __init__(self, *labels: str, **kwargs):
        super().__init__(label=list(labels) if labels else None, **kwargs)

