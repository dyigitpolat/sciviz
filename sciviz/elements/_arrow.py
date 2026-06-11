"""Arrow / Connector: internal straight-arrow primitives (now hidden
behind :class:`sciviz.connect.Connect` in the public API)."""

from __future__ import annotations

from typing import List, Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Arrow(Element):
    """A simple directed arrow with optional label(s) running along it.

    When used inside a :class:`Row` or :class:`Column` the arrow occupies a
    compact axis length even when labels are long; labels stack perpendicular
    to the arrow and the measured bbox grows in the cross direction to
    contain label ink, but the shaft itself stays short so neighbouring
    cards do not get pushed apart by verbose connector text.
    """

    # Default visible shaft length when ``length`` is not supplied,
    # expressed in theme units so it tracks the theme's spacing density.
    # Kept deliberately compact: arrows are visual hints, not stretchers.
    # 8 units equals the historical 48px at the default ``unit=6.0``, and
    # compresses with the layout when a Diagram fits ``target_width_pt``
    # by deriving a lower-density theme.
    _DEFAULT_SHAFT_UNITS: float = 8.0

    # Inline ``Connect`` wrappers mark themselves so that
    # ``Row(equal_widths=True)`` does not stretch the connector into a
    # card-sized slot.
    is_inline_connector: bool = True

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

    def _shaft_len(self, theme: Theme) -> float:
        """Length of the visible drawn shaft in pixels.

        Decoupled from label width: an explicit ``length=`` always wins,
        otherwise a compact default keeps the arrow short. Labels live in
        a separate cross/axis band; they may extend past the shaft, but
        the bbox is what controls layout neighbours, not the shaft.
        """
        if self.length is not None:
            return float(self.length)
        return theme.unit * self._DEFAULT_SHAFT_UNITS

    def _longest_label_width(self, theme: Theme) -> float:
        return max((theme.text_width(l, self.size, bold=False)
                    for l in self.labels), default=0.0)

    def _axis_len(self, theme: Theme) -> float:
        """Backwards-compatible measurement axis: now equals shaft length.

        Subclasses (and a handful of unit tests) treat this as the arrow's
        primary extent. With shaft/label decoupling, the *axis* is the
        shaft. The bbox may still grow to contain a wider label, but that
        is reported on the cross-axis-aware ``measure`` only.
        """
        return self._shaft_len(theme)

    def _label_band(self, theme: Theme) -> float:
        if not self.labels:
            return 0.0
        line_h = theme.text_height(self.size) * 0.95
        return line_h * len(self.labels) + theme.unit * 0.5

    # ------------- measure & render -------------

    def measure(self, theme: Theme) -> BBox:
        shaft = self._shaft_len(theme)
        band = self._label_band(theme)
        # Labels may protrude past the shaft along the arrow's axis; we
        # report only a *small* axis-side cushion (a fraction of the
        # label) so the row does not gain a card-sized arrow slot. The
        # remaining label ink is allowed to overlap the gap on either
        # side -- containers reserve their own gap on top of this bbox.
        label_w = self._longest_label_width(theme)
        axis_pad = min(label_w * 0.35, theme.unit * 1.5)
        axis_with_label = shaft + axis_pad
        cross = max(band * 2 + theme.unit, theme.unit * 3)
        if self.direction in ("right", "left"):
            return BBox(axis_with_label, cross)
        return BBox(cross, axis_with_label)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        color = theme.color_of(self.color)
        marker = (canvas.define_arrow_marker(
                      color=color, stroke_width=theme.connector,
                      arrow_size=getattr(theme, "arrow_size", None))
                  if self.head else None)
        shaft = self._shaft_len(theme)

        if self.direction in ("right", "left"):
            axis_y = y + size.h / 2
            # Centre the visible shaft within the measured bbox so the
            # label and the shaft share a midpoint.
            mid_x = x + size.w / 2
            shaft_lo = mid_x - shaft / 2
            shaft_hi = mid_x + shaft / 2
            if self.direction == "right":
                x1, x2 = shaft_lo, shaft_hi
            else:
                x1, x2 = shaft_hi, shaft_lo
            canvas.line(x1, axis_y, x2, axis_y,
                       stroke=color, stroke_width=theme.connector,
                       marker_end=marker)
            self._draw_labels_horizontal(canvas, x, y, size, axis_y, theme)
        else:
            axis_x = x + size.w / 2
            mid_y = y + size.h / 2
            shaft_lo = mid_y - shaft / 2
            shaft_hi = mid_y + shaft / 2
            if self.direction == "down":
                y1, y2 = shaft_lo, shaft_hi
            else:
                y1, y2 = shaft_hi, shaft_lo
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

