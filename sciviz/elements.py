"""Common diagram elements.

These are the generic building blocks used across every sciviz diagram.
Domain-specific elements (crossbars, attention heads, ...) live in
:mod:`sciviz.ml` and are built out of these primitives.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence, Tuple, Union

from .core import Element, BBox, Canvas, Theme
from .layout import Row, Column, Spacer


# Auto-counter for unnamed obstacles published into any active
# ``Flowed`` registry.  The planner only needs the rectangles, not the
# names -- a monotone string avoids dict-key collisions.
_AUTO_OBSTACLE_COUNTER = [0]


def _register_implicit_obstacle(x: float, y: float, w: float, h: float) -> None:
    """Publish a rendered primitive's bbox as an anonymous obstacle.

    Any :class:`Box` (or future primitive that calls this) shows up in
    the active :class:`Flowed` registry so the orthogonal router routes
    around it, even if the author never wrapped it in an explicit
    :class:`Anchor`.  Silently no-ops when no ``Flowed`` scope is
    active.
    """
    from .composition import _anchor_stack
    stack = _anchor_stack.get()
    if not stack:
        return
    _AUTO_OBSTACLE_COUNTER[0] += 1
    name = f"_auto_obstacle_{_AUTO_OBSTACLE_COUNTER[0]}"
    for reg in stack:
        reg[name] = (x, y, w, h)


# ---------------------------------------------------------------------------
# Text (single line) & TextBlock (multi-line)
# ---------------------------------------------------------------------------

class Text(Element):
    """Single-line text.  Semantic size and colour names are preferred.

    Parameters
    ----------
    content : str
    size : str or float
        Either a semantic name (``"title"``, ``"label"``, ``"small"``, ...)
        or an explicit px value.
    color : str
        Semantic colour (``"dark"``, ``"muted"``, ``"highlight"``, ...) or
        an explicit hex string.
    weight : str
        CSS font-weight keyword: ``"normal"``, ``"600"``, ``"700"``.
    italic : bool
    align : str
        ``"start"``, ``"middle"`` or ``"end"`` controls the SVG text-anchor,
        not the bounding box -- the bbox always matches the rendered width.
    """

    def __init__(self, content: str, *, size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 font: Optional[str] = None,
                 rotate: float = 0.0):
        self.content = content
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.font = font
        # Rotation angle in degrees (CW positive).  When set, the bbox is
        # the AXIS-ALIGNED bbox of the rotated text, so it composes
        # cleanly inside Row/Column.  Use -90 for "reads bottom-up", 90
        # for "reads top-down".
        self.rotate = rotate

    def _resolved_font(self, theme: Theme) -> Optional[str]:
        if self.font is None:
            return None
        if self.font == "mono":
            return getattr(theme, "font_mono", None) or \
                "ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
        return self.font

    def measure(self, theme: Theme) -> BBox:
        bold = self.weight in ("bold", "600", "700")
        w = theme.text_width(self.content, self.size, bold=bold)
        h = theme.text_height(self.size)
        if self.rotate in (90, -90, 270, -270):
            return BBox(h, w)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px(self.size)
        fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        bold = self.weight in ("bold", "600", "700")
        font_w = theme.text_width(self.content, self.size, bold=bold)
        font_h = theme.text_height(self.size)
        if self.rotate in (90, -90, 270, -270):
            cx = x + bbox.w / 2
            cy = y + bbox.h / 2
            anchor = "middle"
            # baseline goes through the centre after rotation
            extra = (
                'dominant-baseline="central"' +
                f' transform="rotate({self.rotate} {cx:.2f} {cy:.2f})"'
            )
            ff = self._resolved_font(theme)
            ff_attr = f' font-family="{ff}"' if ff else ""
            italic_attr = ' font-style="italic"' if self.italic else ""
            weight_attr = (f' font-weight="{self.weight}"'
                           if self.weight != "normal" else "")
            canvas.raw(
                f'<text x="{cx:.2f}" y="{cy:.2f}" '
                f'font-size="{sz:.1f}" fill="{fill}" '
                f'text-anchor="{anchor}"{ff_attr}{italic_attr}{weight_attr} '
                f'{extra}>{self.content}</text>'
            )
            return
        # default unrotated path
        baseline = y + sz * 0.88
        if self.align == "middle":
            tx = x + bbox.w / 2
        elif self.align == "end":
            tx = x + bbox.w
        else:
            tx = x
        canvas.text(tx, baseline, self.content, size=sz, fill=fill,
                   weight=self.weight, italic=self.italic, anchor=self.align,
                   font_family=self._resolved_font(theme))


class TextBlock(Element):
    """Multi-line text block.  Lines are separated by ``\\n``."""

    def __init__(self, content: str, *, size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 line_spacing: float = 1.35, max_width: Optional[float] = None):
        self.content = content
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.line_spacing = line_spacing
        self.max_width = max_width

    def _lines(self, theme: Theme) -> List[str]:
        raw_lines = self.content.split("\n")
        if self.max_width is None:
            return raw_lines
        out = []
        bold = self.weight in ("bold", "600", "700")
        for line in raw_lines:
            words = line.split(" ")
            cur = ""
            for w in words:
                trial = (cur + " " + w).strip()
                if theme.text_width(trial, self.size, bold=bold) <= self.max_width:
                    cur = trial
                else:
                    if cur:
                        out.append(cur)
                    cur = w
            out.append(cur)
        return out

    def measure(self, theme: Theme) -> BBox:
        lines = self._lines(theme)
        bold = self.weight in ("bold", "600", "700")
        widths = [theme.text_width(l, self.size, bold=bold) for l in lines]
        line_h = theme.size_px(self.size) * self.line_spacing
        w = max(widths) if widths else 0.0
        if self.max_width is not None:
            w = max(w, 0.0)
        h = line_h * len(lines)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        lines = self._lines(theme)
        sz = theme.size_px(self.size)
        line_h = sz * self.line_spacing
        fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        for i, line in enumerate(lines):
            baseline = y + sz * 0.88 + i * line_h
            # Accept both "middle" (internal name) and "center" (what
            # most authors reach for) as horizontal centre alignment.
            if self.align in ("middle", "center"):
                tx = x + bbox.w / 2
                svg_anchor = "middle"
            elif self.align == "end":
                tx = x + bbox.w
                svg_anchor = "end"
            else:
                tx = x
                svg_anchor = "start"
            canvas.text(tx, baseline, line, size=sz, fill=fill,
                       weight=self.weight, italic=self.italic,
                       anchor=svg_anchor)


# ---------------------------------------------------------------------------
# Box: a labeled rounded rectangle (layer blocks, stages, callouts)
# ---------------------------------------------------------------------------

class Box(Element):
    """A rounded rectangle with optional label text centred inside.

    Good defaults for diagrams of NN layers, pipeline stages, and callout
    cards.  The box will automatically grow to accommodate the label if no
    explicit width/height is given.
    """

    def __init__(self, label: Optional[str] = None, *,
                 width: Optional[float] = None,
                 height: Optional[float] = None,
                 min_width: Optional[float] = None,
                 min_height: Optional[float] = None,
                 fill: str = "none",
                 stroke: str = "text",
                 stroke_width: Optional[float] = None,
                 text_color: str = "auto",
                 text_size: Optional[Union[str, float]] = None,
                 text_weight: Optional[str] = None,
                 radius: Optional[float] = None,
                 sub_label: Optional[str] = None,
                 sub_color: str = "muted",
                 dashed: bool = False,
                 opacity: float = 1.0,
                 vertical_text: bool = False,
                 shape_key: Optional[str] = None):
        self.label = label
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.text_color = text_color
        # Smart defaults: vertical-text architecture blocks want bigger,
        # bolder labels by visual convention.  Authors writing
        # ``Box("Attention", vertical_text=True, fill=...)`` shouldn't have
        # to also specify text_size and text_weight every time.
        if text_size is None:
            self.text_size = "title" if vertical_text else "label"
        else:
            self.text_size = text_size
        if text_weight is None:
            self.text_weight = "700" if vertical_text else "500"
        else:
            self.text_weight = text_weight
        self.radius = radius
        self.sub_label = sub_label
        self.sub_color = sub_color
        self.dashed = dashed
        self.opacity = opacity
        self.vertical_text = vertical_text
        # ``shape_key`` groups semantically-equivalent boxes (e.g. several
        # RMSNorms in one Row) so a sibling-aware layout container can
        # equalise their heights without the author specifying widths.
        # Default: a tuple of visually-distinguishing fields stringified.
        # Pass ``shape_key=""`` to opt out, or a custom string to force
        # a grouping.
        if shape_key is None:
            # The shape_key must not depend on the label (which might be
            # an opaque Element).  Based on visual-style fields only.
            self.shape_key = (
                f"box::{repr(self.fill)}::{self.text_size}::{int(self.dashed)}"
            )
        else:
            self.shape_key = shape_key

    def _label_is_element(self) -> bool:
        """The label can be either a string or any :class:`Element`
        (e.g. :class:`Math`).  Element labels are measured + rendered
        as a unit, centred inside the box."""
        return self.label is not None and isinstance(self.label, Element)

    def _label_lines(self):
        if not self.label or self._label_is_element():
            return []
        return self.label.split("\n")

    # Size token used for bottom-right precision/metadata subscripts.
    # "micro" is smaller than "tiny" so these tags read as a subscript
    # even next to a 9-pt "small" main label.
    _SUB_LABEL_SIZE = "micro"

    def _sub_metrics(self, theme: Theme) -> Tuple[float, float]:
        """Width and height of the sub_label when rendered, or (0, 0)."""
        if not self.sub_label:
            return 0.0, 0.0
        sub_w = theme.text_width(self.sub_label, self._SUB_LABEL_SIZE)
        sub_h = theme.text_height(self._SUB_LABEL_SIZE)
        return sub_w, sub_h

    def _intrinsic(self, theme: Theme) -> Tuple[float, float]:
        bold = self.text_weight in ("bold", "600", "700")
        lines = self._label_lines()
        line_h = theme.text_height(self.text_size)
        if self._label_is_element():
            # Element label: measure as a single opaque block; the
            # box sizes itself to fit the element plus standard pads.
            eb = self.label.measure(theme)
            label_w = eb.w
            label_h = eb.h
        elif lines:
            label_w = max(theme.text_width(l, self.text_size, bold=bold) for l in lines)
            label_h = line_h * len(lines) + line_h * 0.05 * max(0, len(lines) - 1)
        else:
            label_w = 0.0
            label_h = 0.0
        sub_w, sub_h = self._sub_metrics(theme)
        if self.vertical_text:
            # rotated label: width <-> height swap
            w = label_h + theme.unit * 1.2
            h = max(label_w, sub_w) + theme.unit * 2.0
        else:
            # The sub_label sits in the bottom-right corner as a true
            # subscript tag.  Reserve a dedicated "sub zone" (its width
            # plus a gap) on the right of the main label area so the two
            # never overlap, and a dedicated bottom strip so the main
            # label's bottom is clear of the sub's top.
            sub_gap = theme.unit * 0.6 if self.sub_label else 0.0
            right_pad = theme.unit * 0.8
            left_pad = theme.unit * 0.8
            reserved_bottom = (sub_h + theme.unit * 0.25) if self.sub_label else 0.0
            w = label_w + sub_gap + sub_w + left_pad + right_pad
            h = label_h + reserved_bottom + theme.unit * 0.9
        return max(w, theme.unit * 6), max(h, theme.unit * 3.2)

    def measure(self, theme: Theme) -> BBox:
        w, h = self._intrinsic(theme)
        if self.width is not None:
            w = self.width
        if self.height is not None:
            h = self.height
        if self.min_width is not None and w < self.min_width:
            w = self.min_width
        if self.min_height is not None and h < self.min_height:
            h = self.min_height
        return BBox(w, h)

    def _resolved_text_color(self, theme: Theme) -> str:
        if self.text_color != "auto":
            return theme.color_of(self.text_color)
        fill_hex = theme.color_of(self.fill)
        if fill_hex == "none" or fill_hex.startswith("rgb"):
            return theme.color_of("text")
        return theme.text_on(fill_hex)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        r = self.radius if self.radius is not None else theme.panel_radius
        dasharray = "3,2" if self.dashed else None
        sw = self.stroke_width if self.stroke_width is not None else theme.line
        canvas.rect(
            x, y, size.w, size.h,
            fill=theme.color_of(self.fill),
            stroke=theme.color_of(self.stroke),
            stroke_width=sw,
            rx=r, dasharray=dasharray, opacity=self.opacity,
        )
        _register_implicit_obstacle(x, y, size.w, size.h)
        if self._label_is_element():
            # Element label: reserve the sub_label strip at the bottom
            # (if any) and centre the element in the remaining area.
            sub_w, sub_h = self._sub_metrics(theme)
            sub_pad = theme.unit * 0.25
            bottom_reserve = (sub_h + sub_pad) if self.sub_label else 0.0
            eb = self.label.measure(theme)
            region_h = size.h - bottom_reserve
            ex = x + (size.w - eb.w) / 2
            ey = y + max(0.0, (region_h - eb.h) / 2)
            self.label.render(canvas, ex, ey, theme)
            if self.sub_label:
                sub_sz = theme.size_px(self._SUB_LABEL_SIZE)
                sub_baseline = y + size.h - sub_pad - sub_sz * 0.35
                canvas.text(
                    x + size.w - sub_pad, sub_baseline, self.sub_label,
                    size=sub_sz, fill=theme.color_of(self.sub_color),
                    weight="normal", italic=True, anchor="end",
                )
            return
        lines = self._label_lines()
        if not lines:
            return
        text_fill = self._resolved_text_color(theme)
        sz = theme.size_px(self.text_size)
        if self.vertical_text:
            # render text rotated 90 degrees CCW (-90), one or multiple lines
            cx = x + size.w / 2
            cy = y + size.h / 2
            line_h = sz * 1.15
            block_h = line_h * len(lines)
            text_block_w = block_h
            for i, ln in enumerate(lines):
                offset = (i - (len(lines) - 1) / 2) * line_h
                # baseline coordinate computed in rotated frame
                canvas.raw(
                    f'<text x="{cx + offset:.2f}" y="{cy:.2f}" '
                    f'font-size="{sz:.1f}" '
                    f'fill="{text_fill}" '
                    f'font-weight="{self.text_weight}" '
                    f'text-anchor="middle" dominant-baseline="central" '
                    f'transform="rotate(-90 {cx + offset:.2f} {cy:.2f})">'
                    f'{ln}</text>'
                )
        else:
            sub_w, sub_h = self._sub_metrics(theme)
            sub_pad = theme.unit * 0.25
            bottom_reserve = (sub_h + sub_pad) if self.sub_label else 0.0
            line_h = sz * 1.15
            block_h = line_h * len(lines)
            region_h = size.h - bottom_reserve
            block_top = y + max(0.0, (region_h - block_h) / 2)
            for i, ln in enumerate(lines):
                baseline_y = block_top + i * line_h + sz * 0.85
                canvas.text(
                    x + size.w / 2, baseline_y, ln,
                    size=sz, fill=text_fill,
                    weight=self.text_weight, anchor="middle",
                )
            if self.sub_label:
                # Precision/metadata labels sit in the BOTTOM-RIGHT corner,
                # micro italic, acting like a subscript tag on the block.
                # The baseline is placed so the descender stays inside the
                # box: size.h - sub_pad - descender_estimate.
                sub_sz = theme.size_px(self._SUB_LABEL_SIZE)
                sub_baseline = y + size.h - sub_pad - sub_sz * 0.35
                canvas.text(
                    x + size.w - sub_pad, sub_baseline, self.sub_label,
                    size=sub_sz, fill=theme.color_of(self.sub_color),
                    weight="normal", italic=True, anchor="end",
                )


# ---------------------------------------------------------------------------
# Arrow / Connector
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

def _normalise_matrix(data) -> List[List[float]]:
    """Accept a nested list, numpy array, or tuple (rows, cols)."""
    # Numpy array?
    if hasattr(data, "tolist") and hasattr(data, "shape"):
        return [list(row) for row in data.tolist()]
    # (rows, cols) shape -> demo data
    if isinstance(data, tuple) and len(data) == 2 and all(isinstance(v, int) for v in data):
        rows, cols = data
        import random
        rng = random.Random(0)
        return [[rng.uniform(-1, 1) for _ in range(cols)] for _ in range(rows)]
    # List of lists
    return [list(row) for row in data]


class Matrix(Element):
    """A heat-mapped matrix with optional structured highlighting.

    This is the workhorse of weight/activation/attention visualisations.

    Parameters
    ----------
    data : nested list, numpy array, or ``(rows, cols)`` tuple
        The matrix values.  Cells are coloured by magnitude.
    cell_size : str or float
        ``"xs"`` .. ``"lg"`` token, or a px value.
    highlight_rows, highlight_cols : list of int
        Indices to outline with a dashed "prune" frame.
    row_labels, col_labels : "auto" | list[str] | None
        ``"auto"`` produces ``i₁, i₂, ...`` / ``j₁, j₂, ...`` subscripted labels.
    palette : str
        ``"blues"``, ``"emeralds"``, ``"ambers"``, ``"grays"``, ``"diverging"``.
    show_values : bool
        Write numeric values in each cell (small font).
    mask : 2D iterable of bool
        Where True, the cell is rendered as "pruned" (light/dashed).
    caption : str, optional
        A single-line caption below the matrix.
    """

    _CELL_SIZES = {"xs": 18.0, "sm": 22.0, "md": 28.0, "lg": 36.0}

    def __init__(self, data, *,
                 cell_size: Union[str, float] = "md",
                 highlight_rows: Optional[Sequence[int]] = None,
                 highlight_cols: Optional[Sequence[int]] = None,
                 row_labels: Union[str, Sequence[str], None] = "auto",
                 col_labels: Union[str, Sequence[str], None] = "auto",
                 palette: str = "blues",
                 show_values: bool = False,
                 mask: Optional[Sequence[Sequence[bool]]] = None,
                 caption: Optional[str] = None,
                 absolute: bool = True,
                 vmin: Optional[float] = None,
                 vmax: Optional[float] = None):
        self.data = _normalise_matrix(data)
        self.cell_size = cell_size
        self.highlight_rows = list(highlight_rows or [])
        self.highlight_cols = list(highlight_cols or [])
        self.row_labels = row_labels
        self.col_labels = col_labels
        self.palette = palette
        self.show_values = show_values
        self.mask = mask
        self.caption = caption
        self.absolute = absolute
        self._vmin = vmin
        self._vmax = vmax

    @property
    def rows(self) -> int:
        return len(self.data)

    @property
    def cols(self) -> int:
        return len(self.data[0]) if self.data else 0

    def _cell_px(self, theme: Theme) -> float:
        if isinstance(self.cell_size, str):
            return self._CELL_SIZES.get(self.cell_size, 28.0)
        return float(self.cell_size)

    def _resolve_labels(self, which: str) -> Optional[List[str]]:
        labels = self.row_labels if which == "row" else self.col_labels
        n = self.rows if which == "row" else self.cols
        if labels is None:
            return None
        if labels == "auto":
            sub = "\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
            prefix = "i" if which == "row" else "j"
            return [f"{prefix}{sub[i]}" if i < len(sub) else f"{prefix}{i+1}"
                    for i in range(n)]
        return list(labels)

    def _label_space(self, theme: Theme, which: str) -> float:
        labels = self._resolve_labels(which)
        if not labels:
            return 0.0
        if which == "row":
            return max(theme.text_width(lbl, "small") for lbl in labels) + theme.unit
        else:
            return theme.text_height("small") + theme.unit * 0.5

    def _value_range(self) -> Tuple[float, float]:
        if self._vmin is not None and self._vmax is not None:
            return self._vmin, self._vmax
        flat = [v for row in self.data for v in row]
        if self.absolute:
            flat = [abs(v) for v in flat]
        vmin = min(flat) if self._vmin is None else self._vmin
        vmax = max(flat) if self._vmax is None else self._vmax
        if vmax == vmin:
            vmax = vmin + 1e-6
        return vmin, vmax

    def measure(self, theme: Theme) -> BBox:
        c = self._cell_px(theme)
        row_lbl = self._label_space(theme, "row")
        col_lbl = self._label_space(theme, "col")
        w = row_lbl + self.cols * c
        h = col_lbl + self.rows * c
        if self.caption:
            h += theme.text_height("small") + theme.unit
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        c = self._cell_px(theme)
        row_lbl_w = self._label_space(theme, "row")
        col_lbl_h = self._label_space(theme, "col")
        mx = x + row_lbl_w
        my = y + col_lbl_h
        vmin, vmax = self._value_range()

        # column labels
        col_labels = self._resolve_labels("col")
        if col_labels:
            sz = theme.size_px("small")
            for j, lbl in enumerate(col_labels):
                cx = mx + j * c + c / 2
                baseline = y + col_lbl_h - theme.unit * 0.3
                is_hl = j in self.highlight_cols
                canvas.text(
                    cx, baseline, lbl,
                    size=sz,
                    fill=theme.color_of("highlight" if is_hl else "light"),
                    weight="700" if is_hl else "500",
                    anchor="middle",
                )

        # row labels
        row_labels = self._resolve_labels("row")
        if row_labels:
            sz = theme.size_px("small")
            for i, lbl in enumerate(row_labels):
                baseline = my + i * c + c / 2 + sz * 0.35
                is_hl = i in self.highlight_rows
                canvas.text(
                    mx - theme.unit * 0.7, baseline, lbl,
                    size=sz,
                    fill=theme.color_of("highlight" if is_hl else "light"),
                    weight="700" if is_hl else "500",
                    anchor="end",
                )

        # cells
        for i in range(self.rows):
            for j in range(self.cols):
                val = self.data[i][j]
                masked = (self.mask is not None and self.mask[i][j])
                is_pruned = (i in self.highlight_rows) or (j in self.highlight_cols)
                cx, cy = mx + j * c, my + i * c
                use_val = abs(val) if self.absolute else val
                # pruned/masked cells render as disabled
                if masked or is_pruned:
                    canvas.rect(
                        cx + 1, cy + 1, c - 2, c - 2,
                        fill=theme.color_of("#f8fafc"),
                        stroke=theme.color_of("border_strong"),
                        stroke_width=0.6, rx=2, dasharray="2,1.5",
                    )
                else:
                    color = theme.color_scale(use_val, self.palette, vmin, vmax)
                    canvas.rect(
                        cx + 1, cy + 1, c - 2, c - 2,
                        fill=color,
                        stroke="#1e3a8a" if self.palette == "blues" else "none",
                        stroke_width=0.3, rx=2, opacity=0.95,
                    )
                if self.show_values and not masked and not is_pruned:
                    text_color = "white" if use_val > (vmin + vmax) / 2 else theme.text
                    canvas.text(
                        cx + c / 2, cy + c / 2 + theme.size_px("tiny") * 0.33,
                        f"{val:.2f}",
                        size=theme.size_px("tiny"),
                        fill=text_color if text_color.startswith("#") else theme.color_of(text_color),
                        anchor="middle",
                    )

        # highlighted rows
        for i in self.highlight_rows:
            canvas.rect(
                mx - 1, my + i * c + 1, self.cols * c + 2, c - 2,
                fill="none", stroke=theme.highlight,
                stroke_width=1.8, rx=3, dasharray="5,3",
            )
        # highlighted columns
        for j in self.highlight_cols:
            canvas.rect(
                mx + j * c + 1, my - 1, c - 2, self.rows * c + 2,
                fill="none", stroke=theme.highlight,
                stroke_width=1.8, rx=3, dasharray="5,3",
            )

        # caption
        if self.caption:
            baseline = my + self.rows * c + theme.text_height("small")
            canvas.text(
                x + (row_lbl_w + self.cols * c) / 2, baseline,
                self.caption, size=theme.size_px("small"),
                fill=theme.color_of("highlight"),
                weight="600", anchor="middle",
            )


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

class LegendItem(Element):
    """Single entry in a :class:`Legend`: a swatch element + a text label.

    The swatch can be any :class:`Element` (a small :class:`Box`, a
    :class:`Badge`, a :class:`MiniGrid`, ...) -- this lets legends pair
    non-trivial icons with descriptions without reinventing the layout.

    Parameters
    ----------
    swatch : Element
        Visual swatch (rendered verbatim at its intrinsic size).
    text : str
        Label text, rendered to the right of the swatch.
    gap : str or float
        Horizontal spacing between swatch and text (default ``"xs"``).
    text_size : str
        Theme size token for the label.
    text_color : str
        Colour for the label (default ``"muted"``).
    """

    def __init__(self, swatch: Element, text: str, *,
                 gap: Union[str, float] = "xs",
                 text_size: str = "small",
                 text_color: str = "muted"):
        self.swatch = swatch
        self.text = text
        self.gap = gap
        self.text_size = text_size
        self.text_color = text_color

    def _row(self):
        from .layout import Row
        return Row(
            self.swatch,
            Text(self.text, size=self.text_size, color=self.text_color),
            gap=self.gap, align="center",
        )

    def measure(self, theme: Theme) -> BBox:
        return self._row().measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._row().render(canvas, x, y, theme)


class Legend(Element):
    """Compact horizontal key.

    Three forms (use whichever matches the data you have):

    * ``Legend(LegendItem(Box(...), "leaf page"), LegendItem(...), ...)`` --
      positional items with custom swatch elements.  Preferred form.
    * ``Legend(items=[("#3b82f6", "Active"), ("#e2e8f0", "Pruned")])`` --
      the legacy kwarg form: pairs of (colour, label) drawn as small
      rectangles.  Supported for backward compatibility.
    * ``Legend(scale=("blues", 5), label="|w|")`` -- a sequential colour
      ramp for heatmap-like data.
    """

    def __init__(self, *children,
                 items: Optional[List[Tuple[str, str]]] = None,
                 scale: Optional[Tuple[str, int]] = None,
                 label: Optional[str] = None,
                 swatch_size: float = 14.0,
                 orientation: str = "horizontal",
                 gap: Union[str, float] = "md"):
        self._children = list(children)
        self.items = items
        self.scale = scale
        self.label = label
        self.swatch_size = swatch_size
        self.orientation = orientation
        self.gap = gap

    def _resolved_items(self, theme: Theme) -> List[Tuple[str, str]]:
        if self.items is not None:
            out = []
            for col, lbl in self.items:
                out.append((theme.color_of(col), lbl))
            return out
        if self.scale is not None:
            palette_name, n = self.scale
            palette = theme.palette(palette_name)
            # Pick n evenly spaced samples
            if n <= 1:
                picks = [palette[-1]]
            else:
                picks = [palette[int(i * (len(palette) - 1) / (n - 1))]
                         for i in range(n)]
            labels = ["low"] + [""] * (n - 2) + ["high"] if n >= 2 else ["—"]
            return list(zip(picks, labels))
        return []

    def _positional_container(self):
        from .layout import Row, Column
        cls = Row if self.orientation == "horizontal" else Column
        return cls(*self._children, gap=self.gap, align="center")

    def measure(self, theme: Theme) -> BBox:
        if self._children:
            return self._positional_container().measure(theme)
        items = self._resolved_items(theme)
        sw = self.swatch_size
        pad = theme.unit * 0.6
        if self.orientation == "horizontal":
            w = 0.0
            if self.label:
                w += theme.text_width(self.label, "small", bold=True) + theme.unit
            for _, lbl in items:
                w += sw + pad
                if lbl:
                    w += theme.text_width(lbl, "small") + theme.unit
            h = max(sw, theme.text_height("small"))
            return BBox(w, h)
        else:
            w = sw + theme.unit
            if self.label:
                w = max(w, theme.text_width(self.label, "small", bold=True))
            for _, lbl in items:
                if lbl:
                    w = max(w, sw + theme.unit + theme.text_width(lbl, "small"))
            h = len(items) * (sw + pad)
            if self.label:
                h += theme.text_height("small") + pad
            return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self._children:
            self._positional_container().render(canvas, x, y, theme)
            return
        items = self._resolved_items(theme)
        sw = self.swatch_size
        pad = theme.unit * 0.6
        sz = theme.size_px("small")
        size = self.measure(theme)

        if self.orientation == "horizontal":
            cx = x
            cy_swatch = y + (size.h - sw) / 2
            cy_text = y + size.h / 2 + sz * 0.35
            if self.label:
                canvas.text(cx, cy_text, self.label,
                           size=sz, fill=theme.text_muted,
                           weight="600")
                cx += theme.text_width(self.label, "small", bold=True) + theme.unit
            for color, lbl in items:
                canvas.rect(cx, cy_swatch, sw, sw * 0.7,
                           fill=color, stroke=theme.color_of("border_strong"),
                           stroke_width=0.3, rx=1)
                cx += sw + pad
                if lbl:
                    canvas.text(cx, cy_text, lbl,
                               size=sz, fill=theme.text_muted)
                    cx += theme.text_width(lbl, "small") + theme.unit


# ---------------------------------------------------------------------------
# Note (callout card with title + body + optional illustration)
# ---------------------------------------------------------------------------

class Note(Element):
    """A labelled explanatory card, optionally with a small illustration.

    Typically used in the summary strip of a multi-panel diagram.
    """

    def __init__(self, title: str, body: str, *,
                 tone: str = "neutral",
                 illustration: Optional[Element] = None,
                 emphasis: Optional[str] = None,
                 width: float = 380.0):
        self.title = title
        self.body = body
        self.tone = tone  # "neutral", "primary", "accent", "highlight"
        self.illustration = illustration
        self.emphasis = emphasis
        self.width = width

    _TONE_COLORS = {
        "neutral": ("muted", "text", "muted"),
        "primary": ("primary", "text", "primary"),
        "accent": ("accent", "text", "accent"),
        "highlight": ("highlight", "text", "highlight"),
    }

    def measure(self, theme: Theme) -> BBox:
        inner = self._compose(theme)
        return inner.measure(theme)

    def _compose(self, theme: Theme):
        title_color, body_color, emph_color = self._TONE_COLORS.get(self.tone, self._TONE_COLORS["neutral"])
        parts = [
            Text(self.title, size="section", color=title_color, weight="700"),
            TextBlock(self.body, size="label", color=body_color,
                      max_width=self.width),
        ]
        if self.emphasis:
            parts.append(Spacer(0, theme.unit * 0.5))
            parts.append(Text(self.emphasis, size="label",
                              color=emph_color, weight="700"))
        if self.illustration is not None:
            parts.append(Spacer(0, theme.unit * 1.0))
            parts.append(self.illustration)
        return Column(*parts, gap="xs", align="start")

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._compose(theme).render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# Caption (small italic text under a figure)
# ---------------------------------------------------------------------------

class Caption(Element):
    """Subtle centred caption text."""

    def __init__(self, content: str, *, color: str = "muted"):
        self.content = content
        self.color = color

    def measure(self, theme: Theme) -> BBox:
        w = theme.text_width(self.content, "small", bold=False)
        h = theme.text_height("small")
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px("small")
        bbox = self.measure(theme)
        canvas.text(
            x + bbox.w / 2, y + sz * 0.88, self.content,
            size=sz, fill=theme.color_of(self.color),
            italic=True, anchor="middle",
        )


# ---------------------------------------------------------------------------
# MiniGrid (tiny illustrative matrix, for notes)
# ---------------------------------------------------------------------------

class MiniGrid(Element):
    """Tiny illustrative grid, smaller than :class:`Matrix`.

    Used for "what unstructured pruning looks like" thumbnails inside notes.
    """

    def __init__(self, rows: int, cols: int, *,
                 zero_cells: Optional[Sequence[Tuple[int, int]]] = None,
                 zero_rows: Optional[Sequence[int]] = None,
                 zero_cols: Optional[Sequence[int]] = None,
                 cell: float = 12.0,
                 active_color: str = "primary_fill",
                 zero_color: str = "disabled_fill"):
        self.rows = rows
        self.cols = cols
        self.zero_cells = set(tuple(x) for x in (zero_cells or []))
        self.zero_rows = set(zero_rows or [])
        self.zero_cols = set(zero_cols or [])
        self.cell = cell
        self.active_color = active_color
        self.zero_color = zero_color

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.cols * self.cell, self.rows * self.cell)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        c = self.cell
        for i in range(self.rows):
            for j in range(self.cols):
                is_zero = (
                    (i, j) in self.zero_cells or
                    i in self.zero_rows or
                    j in self.zero_cols
                )
                color = theme.color_of(self.zero_color if is_zero else self.active_color)
                canvas.rect(
                    x + j * c + 0.75, y + i * c + 0.75,
                    c - 1.5, c - 1.5,
                    fill=color, rx=1.5,
                )


# ---------------------------------------------------------------------------
# TokenRow (horizontal pill with math-typeset $t_i$ indices)
# ---------------------------------------------------------------------------

class TokenRow(Element):
    """A single rounded pill containing math-typeset indexed tokens.

    ``TokenRow(3, 4, 5, 6)`` renders as one continuous light-gray pill with
    ``$t_3$  $t_4$  $t_5$  $t_6$`` inside, equally spaced.  This mirrors the
    "input tokens"/"target tokens" ribbons in the DeepSeek-V3 paper: a single
    ribbon, not a table of cells.

    The caller supplies indices (ints or strings) and optionally overrides the
    base letter (``letter="x"`` -> ``x_3, x_4, ...``) or supplies raw LaTeX
    fragments via ``raw=[...]``.

    No layout/padding knobs are required: the pill auto-sizes to the content
    and honours the theme's :attr:`panel_soft` fill and :attr:`unit` spacing.
    """

    def __init__(self, *indices,
                 letter: str = "t",
                 raw: Optional[Sequence[str]] = None,
                 fill: str = "panel_soft",
                 fill_opacity: float = 0.35,
                 stroke: str = "panel_soft",
                 stroke_width: Optional[float] = None,
                 size: Union[str, float] = "math",
                 gap: Union[str, float] = "md",
                 padding: Union[str, float] = "sm"):
        if raw is not None:
            self._pieces = [str(r) for r in raw]
        else:
            if not indices:
                raise ValueError("TokenRow requires at least one index")
            self._pieces = [f"${letter}_{{{idx}}}$" for idx in indices]
        self.fill = fill
        self.fill_opacity = fill_opacity
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.size = size
        self.gap = gap
        self.padding = padding
        self._math_cache: Optional[list] = None

    def _tokens(self) -> list:
        if self._math_cache is not None:
            return self._math_cache
        from .math import Math
        self._math_cache = [Math(p, size=self.size) for p in self._pieces]
        return self._math_cache

    def measure(self, theme: Theme) -> BBox:
        tokens = self._tokens()
        g = theme.gap_px(self.gap)
        pad = theme.gap_px(self.padding)
        sizes = [t.measure(theme) for t in tokens]
        w = sum(s.w for s in sizes) + g * (len(sizes) - 1) + 2 * pad
        h = max(s.h for s in sizes) + 2 * pad
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        tokens = self._tokens()
        g = theme.gap_px(self.gap)
        pad = theme.gap_px(self.padding)
        bbox = self.measure(theme)
        fill = theme.color_of(self.fill)
        stroke = theme.color_of(self.stroke)
        sw = self.stroke_width if self.stroke_width is not None else theme.hairline
        rx = bbox.h / 2
        canvas.rect(
            x, y, bbox.w, bbox.h,
            fill=fill, stroke=stroke, stroke_width=sw,
            opacity=self.fill_opacity, rx=rx,
        )
        sizes = [t.measure(theme) for t in tokens]
        cursor = x + pad
        for tok, sz in zip(tokens, sizes):
            ty = y + (bbox.h - sz.h) / 2
            tok.render(canvas, cursor, ty, theme)
            cursor += sz.w + g
