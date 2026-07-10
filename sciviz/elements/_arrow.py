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
    # Four units (24 px at the paper default) keeps relationships visually
    # local.  The historical 48 px shaft turned compact scientific flows
    # into long corridors and made arrows compete with the actual nodes.
    _DEFAULT_SHAFT_UNITS: float = 4.0
    _SEMANTIC_LENGTHS = {"xs": 2.0, "sm": 3.0, "md": 4.0, "lg": 6.0}

    # Inline ``Connect`` wrappers mark themselves so that
    # ``Row(equal_widths=True)`` does not stretch the connector into a
    # card-sized slot.
    is_inline_connector: bool = True

    def __init__(self, label: Optional[Union[str, List[str]]] = None, *,
                 direction: str = "right",
                 length: Optional[Union[str, float]] = None,
                 color: str = "text_muted",
                 label_color: str = "muted",
                 label_side: str = "auto",
                 label_weight: str = "normal",
                 italic: bool = True,
                 size: Union[str, float] = "small",
                 head: Union[bool, str] = True):
        if isinstance(label, str):
            self.labels = [label]
        elif label is None:
            self.labels = []
        else:
            self.labels = list(label)
        self.direction = direction  # "right", "left", "down", "up"
        if isinstance(length, str) and length not in self._SEMANTIC_LENGTHS:
            allowed = ", ".join(self._SEMANTIC_LENGTHS)
            raise ValueError(
                f"arrow length must be numeric or one of {allowed}"
            )
        self.length = length
        self.color = color
        self.label_color = label_color
        if label_side not in ("auto", "left", "right", "above", "below"):
            raise ValueError(
                "label_side must be auto/left/right/above/below"
            )
        self.label_side = label_side
        self.label_weight = label_weight
        self.italic = italic
        self.size = size
        self.head = head

    def _head_flags(self) -> tuple[bool, bool]:
        """Return ``(start, end)`` marker flags for the semantic spec."""
        if self.head is True or self.head == "end":
            return False, True
        if self.head is False or self.head == "none":
            return False, False
        if self.head == "start":
            return True, False
        if self.head == "both":
            return True, True
        raise ValueError("head must be bool or one of none/start/end/both")

    # ------------- layout helpers -------------

    def _shaft_len(self, theme: Theme) -> float:
        """Length of the visible drawn shaft in pixels.

        Decoupled from label width: an explicit ``length=`` always wins,
        otherwise a compact default keeps the arrow short. Labels live in
        a separate cross/axis band; they may extend past the shaft, but
        the bbox is what controls layout neighbours, not the shaft.
        """
        if self.length is not None:
            if isinstance(self.length, str):
                return theme.unit * self._SEMANTIC_LENGTHS[self.length]
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
        # A vertical arrow's label sits BESIDE the shaft.  Its width is a
        # cross-axis reservation and must never lengthen the shaft or push
        # the connected nodes farther apart.  The old transposed horizontal
        # formula did exactly that for long labels such as "Reward
        # Modeling", making otherwise identical feedback pairs misalign.
        left_w, right_w = self._vertical_label_widths(theme)
        side_gap = theme.unit * 0.8
        core_w = theme.unit * 3.0
        w = core_w
        if left_w:
            w += left_w + side_gap
        if right_w:
            w += right_w + side_gap
        label_h = max(
            (self._vertical_label_block(label, theme)[1]
             for label in self.labels),
            default=0.0,
        )
        return BBox(w, max(shaft, label_h))

    def _vertical_label_groups(self):
        """Return label groups painted to the left and right of the shaft."""
        if not self.labels:
            return [], []
        if self.label_side == "left":
            return self.labels, []
        if self.label_side == "right":
            return [], self.labels
        # ``above``/``below`` describe horizontal shafts.  Retain the
        # historical balanced split if they reach a vertical arrow.
        cut = (len(self.labels) + 1) // 2
        return self.labels[:cut], self.labels[cut:]

    def _vertical_label_widths(self, theme: Theme) -> tuple[float, float]:
        left, right = self._vertical_label_groups()
        step = theme.size_px(self.size) * 1.2
        left_w = max(
            (self._vertical_label_block(label, theme)[0] + i * step
             for i, label in enumerate(left)),
            default=0.0,
        )
        right_w = max(
            (self._vertical_label_block(label, theme)[0] + i * step
             for i, label in enumerate(right)),
            default=0.0,
        )
        return left_w, right_w

    def _vertical_label_lines(self, label: str, theme: Theme) -> list[str]:
        """Wrap prose beside a vertical shaft without an author width knob."""
        max_width = theme.unit * 8.0
        lines: list[str] = []
        for paragraph in label.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                trial = f"{current} {word}"
                if theme.text_width(trial, self.size) <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _vertical_label_block(self, label: str,
                              theme: Theme) -> tuple[float, float]:
        lines = self._vertical_label_lines(label, theme)
        width = max(
            (theme.text_width(line, self.size) for line in lines),
            default=0.0,
        )
        height = len(lines) * theme.text_height(self.size) * 0.95
        return width, height

    def _vertical_axis_x(self, x: float, theme: Theme) -> float:
        left_w, _right_w = self._vertical_label_widths(theme)
        left_reserve = left_w + theme.unit * 0.8 if left_w else 0.0
        return x + left_reserve + theme.unit * 1.5

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        color = theme.color_of(self.color)
        marker_start, marker_end = self._head_flags()
        marker = (canvas.define_arrow_marker(
                      color=color, stroke_width=theme.connector,
                      arrow_size=getattr(theme, "arrow_size", None))
                  if marker_start or marker_end else None)
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
                       marker_end=marker if marker_end else None,
                       marker_start=marker if marker_start else None)
            self._draw_labels_horizontal(canvas, x, y, size, axis_y, theme)
        else:
            axis_x = self._vertical_axis_x(x, theme)
            mid_y = y + size.h / 2
            shaft_lo = mid_y - shaft / 2
            shaft_hi = mid_y + shaft / 2
            if self.direction == "down":
                y1, y2 = shaft_lo, shaft_hi
            else:
                y1, y2 = shaft_hi, shaft_lo
            canvas.line(axis_x, y1, axis_x, y2,
                       stroke=color, stroke_width=theme.connector,
                       marker_end=marker if marker_end else None,
                       marker_start=marker if marker_start else None)
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
                       weight=self.label_weight,
                       anchor="middle", italic=self.italic)
        for i, lbl in enumerate(below):
            baseline = axis_y + theme.unit * 0.6 + sz + i * line_h
            canvas.text(cx, baseline, lbl, size=sz, fill=color,
                       weight=self.label_weight,
                       anchor="middle", italic=self.italic)

    def _draw_labels_vertical(self, canvas, x, y, size, axis_x, theme):
        if not self.labels:
            return
        sz = theme.size_px(self.size)
        line_h = theme.text_height(self.size) * 0.95
        color = theme.color_of(self.label_color)
        cy = y + size.h / 2
        left, right = self._vertical_label_groups()
        for i, lbl in enumerate(left):
            rx = axis_x - theme.unit * 0.8 - i * (sz * 1.2)
            lines = self._vertical_label_lines(lbl, theme)
            first = cy - (len(lines) - 1) * line_h / 2.0 + sz * 0.35
            for line_index, line in enumerate(lines):
                canvas.text(
                    rx, first + line_index * line_h, line,
                    size=sz, fill=color, weight=self.label_weight,
                    anchor="end", italic=self.italic,
                )
        for i, lbl in enumerate(right):
            rx = axis_x + theme.unit * 0.8 + i * (sz * 1.2)
            lines = self._vertical_label_lines(lbl, theme)
            first = cy - (len(lines) - 1) * line_h / 2.0 + sz * 0.35
            for line_index, line in enumerate(lines):
                canvas.text(
                    rx, first + line_index * line_h, line,
                    size=sz, fill=color, weight=self.label_weight,
                    anchor="start", italic=self.italic,
                )


# convenience alias for readability: `Connector("map to", "hardware")`
class Connector(Arrow):
    """An :class:`Arrow` that accepts labels as positional args."""

    def __init__(self, *labels: str, **kwargs):
        super().__init__(label=list(labels) if labels else None, **kwargs)
