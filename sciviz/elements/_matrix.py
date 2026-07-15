"""Matrix data cells, shared colour scales, selections, and colorbars."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme
from ._obstacles import _register_implicit_obstacle


_PALETTE_NAMES = frozenset(
    {"blues", "emeralds", "ambers", "grays", "diverging"}
)


@dataclass(frozen=True)
class ColorScale:
    """Immutable numeric colour normalization shared by data displays.

    ``center`` gives a meaningful midpoint (usually zero) half of the
    palette even when the domain is asymmetric.  Values outside ``domain``
    are clamped.  ``reverse`` reverses colour meaning without changing the
    numeric direction shown by a :class:`ColorBar`.
    """

    domain: Tuple[float, float]
    palette: str = "diverging"
    center: Optional[float] = None
    reverse: bool = False

    def __post_init__(self) -> None:
        try:
            lo, hi = self.domain
        except (TypeError, ValueError) as exc:
            raise ValueError("ColorScale.domain must be a (low, high) pair") from exc
        lo, hi = float(lo), float(hi)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError("ColorScale.domain endpoints must be finite")
        if not lo < hi:
            raise ValueError("ColorScale.domain must satisfy low < high")
        if self.palette not in _PALETTE_NAMES:
            allowed = ", ".join(sorted(_PALETTE_NAMES))
            raise ValueError(
                f"unknown ColorScale palette {self.palette!r}; expected one of {allowed}"
            )
        center = self.center
        if center is not None:
            center = float(center)
            if not math.isfinite(center) or not lo < center < hi:
                raise ValueError("ColorScale.center must lie strictly inside domain")
        object.__setattr__(self, "domain", (lo, hi))
        object.__setattr__(self, "center", center)

    def normalized(self, value: float) -> float:
        """Map ``value`` to a clamped palette coordinate in ``[0, 1]``."""
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("ColorScale values must be finite")
        lo, hi = self.domain
        value = max(lo, min(hi, value))
        if self.center is None:
            t = (value - lo) / (hi - lo)
        elif value <= self.center:
            t = 0.5 * (value - lo) / (self.center - lo)
        else:
            t = 0.5 + 0.5 * (value - self.center) / (hi - self.center)
        return 1.0 - t if self.reverse else t

    def color(self, theme: Theme, value: float) -> str:
        """Resolve ``value`` to one of the theme palette's colours."""
        palette = theme.palette(self.palette)
        if not palette:  # pragma: no cover - Theme always supplies colours
            return theme.color_of("muted")
        idx = int(round(self.normalized(value) * (len(palette) - 1)))
        return palette[idx]

    def gradient_stops(self, theme: Theme) -> List[Tuple[float, str]]:
        """Return data-axis offsets and colours for a matching SVG gradient."""
        palette = theme.palette(self.palette)
        if len(palette) <= 1:  # pragma: no cover - built-in palettes have >1
            return [(0.0, palette[0]), (1.0, palette[0])]
        lo, hi = self.domain
        center_fraction = (
            None if self.center is None else (self.center - lo) / (hi - lo)
        )

        def data_fraction(palette_fraction: float) -> float:
            # ``normalized`` applies reverse last, so undo it before
            # inverting the centred piecewise-linear normalization.
            u = 1.0 - palette_fraction if self.reverse else palette_fraction
            if center_fraction is None:
                return u
            if u <= 0.5:
                return (u / 0.5) * center_fraction
            return center_fraction + ((u - 0.5) / 0.5) * (1.0 - center_fraction)

        stops = [
            (data_fraction(i / (len(palette) - 1)), color)
            for i, color in enumerate(palette)
        ]
        return sorted(stops, key=lambda item: item[0])


@dataclass(frozen=True)
class MatrixCell:
    """One structured matrix cell.

    ``value`` drives numeric colour independently from ``label`` and
    ``detail``.  ``role`` overrides numeric colour for categorical states.
    ``mark`` may be a short string or any measured :class:`Element`.
    """

    value: Optional[float] = None
    label: Optional[str] = None
    detail: Optional[str] = None
    role: Any = None
    emphasis: bool = False
    mark: Optional[Union[str, Element]] = None

    def __post_init__(self) -> None:
        if self.value is not None:
            value = float(self.value)
            if not math.isfinite(value):
                raise ValueError("MatrixCell.value must be finite or None")
            object.__setattr__(self, "value", value)
        if self.label is not None:
            object.__setattr__(self, "label", str(self.label))
        if self.detail is not None:
            object.__setattr__(self, "detail", str(self.detail))
        if self.mark is not None and not isinstance(self.mark, (str, Element)):
            raise TypeError("MatrixCell.mark must be str, Element, or None")


@dataclass(frozen=True)
class MatrixSelection:
    """A non-destructive rectangular selection in matrix index space."""

    rows: Union[int, slice]
    cols: Union[int, slice]
    name: Optional[str] = None
    role: Any = "highlight"
    style: str = "solid"
    label: Optional[str] = None
    label_position: str = "auto"

    def __post_init__(self) -> None:
        for axis, spec in (("rows", self.rows), ("cols", self.cols)):
            if isinstance(spec, bool) or not isinstance(spec, (int, slice)):
                raise TypeError(
                    f"MatrixSelection.{axis} must be an int or slice"
                )
            if isinstance(spec, slice) and spec.step not in (None, 1):
                raise ValueError(
                    f"MatrixSelection.{axis} slice step must be 1 or None"
                )
        if self.name is not None:
            if not isinstance(self.name, str) or not self.name:
                raise ValueError("MatrixSelection.name must be a non-empty string")
        if self.style not in ("solid", "dashed", "none"):
            raise ValueError(
                "MatrixSelection.style must be solid, dashed, or none"
            )
        if self.label is not None:
            object.__setattr__(self, "label", str(self.label))
        if self.label_position not in ("auto", "top", "center", "left", "right"):
            raise ValueError(
                "MatrixSelection.label_position must be auto/top/center/left/right"
            )


@dataclass(frozen=True)
class MatrixGroup:
    """A labelled contiguous range on a matrix row or column axis."""

    label: str
    start: int
    stop: int
    role: Any = "muted"

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("MatrixGroup.label must be a non-empty string")
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise TypeError("MatrixGroup.start must be an integer")
        if isinstance(self.stop, bool) or not isinstance(self.stop, int):
            raise TypeError("MatrixGroup.stop must be an integer")
        if self.start < 0 or self.stop <= self.start:
            raise ValueError("MatrixGroup requires 0 <= start < stop")


def _normalise_matrix(data) -> List[List[Any]]:
    """Accept a nested list, numpy array, or tuple ``(rows, cols)``."""
    if hasattr(data, "tolist") and hasattr(data, "shape"):
        return [list(row) for row in data.tolist()]
    if (
        isinstance(data, tuple)
        and len(data) == 2
        and all(isinstance(v, int) for v in data)
    ):
        rows, cols = data
        import random

        rng = random.Random(0)
        return [[rng.uniform(-1, 1) for _ in range(cols)] for _ in range(rows)]
    return [list(row) for row in data]


class Matrix(Element):
    """A heat-mapped matrix with optional structured cells and selections.

    Existing numeric matrices keep their historical rendering.  Supplying a
    :class:`MatrixCell`, ``scale``, or ``selections`` activates the structured
    path without changing legacy ``highlight_rows`` / ``highlight_cols`` or
    ``mask`` behavior.

    Row labels may contain newlines: the first line is the label proper and
    continuation lines render smaller and muted — sublabels for units,
    provenance, or grounding detail (the same convention as multiline
    Scatter point labels).  Column labels stay single-line because they can
    rotate.
    """

    _CELL_SIZES = {
        # Dense masks and adjacency matrices need sub-label-sized cells;
        # forcing authors back to numeric pixels defeats the semantic scale.
        "micro": 10.0,
        "tiny": 14.0,
        "xs": 18.0,
        "sm": 22.0,
        "md": 28.0,
        "lg": 36.0,
        "xl": 54.0,
    }

    def __init__(
        self,
        data,
        *,
        cell_size: Union[str, float] = "md",
        highlight_rows: Optional[Sequence[int]] = None,
        highlight_cols: Optional[Sequence[int]] = None,
        row_labels: Union[str, Sequence[str], None] = "auto",
        col_labels: Union[str, Sequence[str], None] = "auto",
        col_label_position: str = "top",
        col_label_angle: float = 0.0,
        row_groups: Optional[Sequence[MatrixGroup]] = None,
        col_groups: Optional[Sequence[MatrixGroup]] = None,
        row_partitions: Optional[Sequence[int]] = None,
        col_partitions: Optional[Sequence[int]] = None,
        palette: str = "blues",
        show_values: bool = False,
        mask: Optional[Sequence[Sequence[bool]]] = None,
        caption: Optional[str] = None,
        absolute: bool = True,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        scale: Optional[ColorScale] = None,
        selections: Optional[Sequence[MatrixSelection]] = None,
    ):
        self.data = _normalise_matrix(data)
        self.cell_size = cell_size
        self.highlight_rows = list(highlight_rows or [])
        self.highlight_cols = list(highlight_cols or [])
        self.row_labels = row_labels
        self.col_labels = col_labels
        if col_label_position not in ("top", "bottom"):
            raise ValueError(
                "Matrix.col_label_position must be 'top' or 'bottom'"
            )
        self.col_label_position = col_label_position
        self.col_label_angle = float(col_label_angle)
        if not -90.0 <= self.col_label_angle <= 90.0:
            raise ValueError("Matrix.col_label_angle must be between -90 and 90")
        self.row_groups = tuple(row_groups or ())
        self.col_groups = tuple(col_groups or ())
        if any(not isinstance(group, MatrixGroup) for group in self.row_groups):
            raise TypeError("Matrix.row_groups must contain MatrixGroup values")
        if any(not isinstance(group, MatrixGroup) for group in self.col_groups):
            raise TypeError("Matrix.col_groups must contain MatrixGroup values")
        self.row_partitions = tuple(row_partitions or ())
        self.col_partitions = tuple(col_partitions or ())
        self.palette = palette
        self.show_values = show_values
        self.mask = mask
        self.caption = caption
        self.absolute = absolute
        self._vmin = vmin
        self._vmax = vmax

        if scale is not None and not isinstance(scale, ColorScale):
            raise TypeError("Matrix.scale must be a ColorScale or None")
        if scale is not None and (vmin is not None or vmax is not None):
            raise ValueError("Matrix scale cannot be combined with vmin/vmax")
        self.scale = scale

        self.selections = tuple(selections or ())
        if any(not isinstance(item, MatrixSelection) for item in self.selections):
            raise TypeError("Matrix.selections must contain MatrixSelection values")
        names = [item.name for item in self.selections if item.name is not None]
        if len(names) != len(set(names)):
            raise ValueError("Matrix selection names must be unique within a matrix")

        has_cells = any(
            isinstance(cell, MatrixCell) for row in self.data for cell in row
        )
        self._structured = bool(has_cells or scale is not None or self.selections)
        if self._structured:
            self._validate_structured_data()
            # Resolve now so invalid or empty selections fail at construction,
            # not halfway through a render.
            for selection in self.selections:
                self._selection_bounds(selection)
        self._validate_axis_annotations()

    def _validate_axis_annotations(self) -> None:
        for axis, groups, count in (
            ("row", self.row_groups, self.rows),
            ("column", self.col_groups, self.cols),
        ):
            for group in groups:
                if group.stop > count:
                    raise IndexError(
                        f"MatrixGroup {axis} stop {group.stop} exceeds {count}"
                    )
        for axis, partitions, count in (
            ("row", self.row_partitions, self.rows),
            ("column", self.col_partitions, self.cols),
        ):
            for partition in partitions:
                if isinstance(partition, bool) or not isinstance(partition, int):
                    raise TypeError(f"Matrix {axis} partitions must be integers")
                if not 0 < partition < count:
                    raise ValueError(
                        f"Matrix {axis} partition must lie inside the axis"
                    )

    @property
    def rows(self) -> int:
        return len(self.data)

    @property
    def cols(self) -> int:
        return len(self.data[0]) if self.data else 0

    def _validate_structured_data(self) -> None:
        widths = {len(row) for row in self.data}
        if len(widths) > 1:
            raise ValueError("structured Matrix rows must all have equal length")
        for row in self.data:
            for cell in row:
                if isinstance(cell, MatrixCell):
                    continue
                try:
                    value = float(cell)
                except (TypeError, ValueError) as exc:
                    raise TypeError(
                        "Matrix cells must be numeric or MatrixCell values"
                    ) from exc
                if not math.isfinite(value):
                    raise ValueError("Matrix numeric values must be finite")

    def _cell_px(self, theme: Theme) -> float:
        if isinstance(self.cell_size, str):
            size = self._CELL_SIZES.get(self.cell_size, 28.0)
        else:
            size = float(self.cell_size)
        # A custom mark is an Element with an intrinsic bbox and cannot be
        # font-fitted like string content.  Treat ``cell_size`` as its minimum
        # only in that structured case; numeric legacy matrices stay exact.
        if getattr(self, "_structured", False):
            for row in self.data:
                for cell in row:
                    if isinstance(cell, MatrixCell) and isinstance(cell.mark, Element):
                        mark_size = cell.mark.measure(theme)
                        size = max(size, mark_size.w + 4.0, mark_size.h + 4.0)
        return size

    def _resolve_labels(self, which: str) -> Optional[List[str]]:
        labels = self.row_labels if which == "row" else self.col_labels
        n = self.rows if which == "row" else self.cols
        if labels is None:
            return None
        if labels == "auto":
            sub = "₁₂₃₄₅₆₇₈₉"
            prefix = "i" if which == "row" else "j"
            return [
                f"{prefix}{sub[i]}" if i < len(sub) else f"{prefix}{i + 1}"
                for i in range(n)
            ]
        return list(labels)

    @staticmethod
    def _row_label_lines(label: str) -> List[str]:
        """Split a row label into its main line and sublabel lines.

        Row labels may contain newlines: the first line is the label proper
        and continuation lines render smaller and muted — the same
        name-plus-detail convention Scatter point labels use.  Column labels
        stay single-line (they rotate).
        """
        return label.splitlines() or [label]

    def _label_space(self, theme: Theme, which: str) -> float:
        labels = self._resolve_labels(which)
        if not labels:
            return 0.0
        if which == "row":
            width = 0.0
            for lbl in labels:
                lines = self._row_label_lines(lbl)
                width = max(width, theme.text_width(lines[0], "small"))
                for sub in lines[1:]:
                    width = max(width, theme.text_width(sub, "tiny"))
            return width + theme.unit
        if abs(self.col_label_angle) < 0.5:
            return theme.text_height("small") + theme.unit * 0.5
        angle = math.radians(abs(self.col_label_angle))
        max_width = max(theme.text_width(lbl, "small") for lbl in labels)
        rotated_h = (
            max_width * math.sin(angle)
            + theme.text_height("small") * math.cos(angle)
        )
        return rotated_h + theme.unit * 0.6

    def _group_label_layout(
        self, theme: Theme, which: str
    ) -> Tuple[List[List[str]], float, float]:
        """Wrap each axis-group label to its span.

        Group labels annotate a fixed extent of cells, so unlike row/column
        labels they cannot claim more room sideways: neighbouring groups
        would collide.  Wrap words to the span first; if an unbreakable
        word still overflows, shrink one shared font so every group stays
        typographically consistent.  Returns per-group wrapped lines, the
        resolved font size, and the line advance.
        """
        groups = self.row_groups if which == "row" else self.col_groups
        preferred = theme.size_px("small")
        if not groups:
            return [], preferred, theme.text_height("small")
        c = self._cell_px(theme)
        pad = theme.unit * 0.8
        spans = [max((g.stop - g.start) * c - pad, c) for g in groups]
        lines_per_group = [
            self._wrap_label(group.label, theme, span)
            for group, span in zip(groups, spans)
        ]
        ratio = 1.0
        for span, lines in zip(spans, lines_per_group):
            for line in lines:
                width = theme.text_width(line, "small")
                if width > span:
                    ratio = min(ratio, span / width)
        floor = theme.size_px("micro") / preferred
        ratio = max(ratio, floor)
        font = preferred * ratio
        line_h = theme.text_height("small") * ratio
        return lines_per_group, font, line_h

    def _group_space(self, theme: Theme, which: str) -> float:
        groups = self.row_groups if which == "row" else self.col_groups
        if not groups:
            return 0.0
        lines_per_group, _font, line_h = self._group_label_layout(theme, which)
        depth = max(len(lines) for lines in lines_per_group) * line_h
        if which == "row":
            return depth + theme.unit * 1.25
        return depth + theme.unit * 1.15

    @staticmethod
    def _cell_value(cell) -> Optional[float]:
        if isinstance(cell, MatrixCell):
            return cell.value
        return float(cell)

    def _value_range(self) -> Tuple[float, float]:
        if self.scale is not None:
            return self.scale.domain
        if self._vmin is not None and self._vmax is not None:
            return self._vmin, self._vmax

        if not self._structured:
            flat = [v for row in self.data for v in row]
            if self.absolute:
                flat = [abs(v) for v in flat]
            vmin = min(flat) if self._vmin is None else self._vmin
            vmax = max(flat) if self._vmax is None else self._vmax
        else:
            flat = [
                value
                for row in self.data
                for cell in row
                if (value := self._cell_value(cell)) is not None
            ]
            if self.absolute:
                flat = [abs(v) for v in flat]
            vmin = (min(flat) if flat else 0.0) if self._vmin is None else self._vmin
            vmax = (max(flat) if flat else 1.0) if self._vmax is None else self._vmax
        if vmax == vmin:
            vmax = vmin + 1e-6
        return vmin, vmax

    def measure(self, theme: Theme) -> BBox:
        c = self._cell_px(theme)
        row_lbl = self._group_space(theme, "row") + self._label_space(theme, "row")
        col_lbl = self._group_space(theme, "col") + self._label_space(theme, "col")
        side_left = self._selection_side_space(theme, "left")
        side_right = self._selection_side_space(theme, "right")
        w = side_left + row_lbl + self.cols * c + side_right
        h = col_lbl + self.rows * c
        if self.caption:
            h += theme.text_height("small") + theme.unit
        return BBox(w, h)

    @staticmethod
    def _axis_bounds(spec: Union[int, slice], count: int, axis: str) -> Tuple[int, int]:
        if count <= 0:
            raise ValueError(f"cannot select {axis} from an empty Matrix")
        if isinstance(spec, int):
            index = spec + count if spec < 0 else spec
            if index < 0 or index >= count:
                raise IndexError(f"MatrixSelection {axis} index {spec} out of range")
            return index, index + 1
        start, stop, step = spec.indices(count)
        if step != 1:  # constructor rejects explicit non-unit steps
            raise ValueError(f"MatrixSelection {axis} slice must move forward by 1")
        if start >= stop:
            raise ValueError(f"MatrixSelection {axis} slice selects no cells")
        return start, stop

    def _selection_bounds(
        self, selection: MatrixSelection
    ) -> Tuple[int, int, int, int]:
        r0, r1 = self._axis_bounds(selection.rows, self.rows, "row")
        c0, c1 = self._axis_bounds(selection.cols, self.cols, "column")
        return r0, r1, c0, c1

    def _resolved_selection_label_position(
        self, selection: MatrixSelection, theme: Theme
    ) -> str:
        if selection.label_position != "auto":
            return selection.label_position
        if not selection.label:
            return "top"
        _r0, _r1, c0, c1 = self._selection_bounds(selection)
        available = (c1 - c0) * self._cell_px(theme) - 2 * theme.unit
        widest = max(
            (theme.text_width(line, "micro")
             for line in selection.label.splitlines()),
            default=0.0,
        )
        # Keep a compact internal header when it remains legible.  Otherwise
        # move the annotation outside, where it cannot obscure selected data.
        return "top" if widest <= available else "left"

    @staticmethod
    def _wrap_label(label: str, theme: Theme, target: float) -> list[str]:
        """Greedy word-wrap of ``label`` to ``target`` pixels at small size."""
        lines: list[str] = []
        for paragraph in label.splitlines():
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                trial = f"{current} {word}"
                if theme.text_width(trial, "small") <= target:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _side_label_lines(self, label: str, theme: Theme) -> list[str]:
        return self._wrap_label(label, theme, theme.unit * 7.0)

    def _selection_side_space(self, theme: Theme, side: str) -> float:
        labels = [
            selection.label
            for selection in self.selections
            if selection.label
            and self._resolved_selection_label_position(selection, theme) == side
        ]
        if not labels:
            return 0.0
        label_w = max(
            theme.text_width(line, "small")
            for label in labels
            for line in self._side_label_lines(label, theme)
        )
        return label_w + theme.unit * 3.6

    def selection_bboxes(self, theme: Theme) -> dict[str, Tuple[float, float, float, float]]:
        """Return named selection bboxes in this Matrix's local frame."""
        c = self._cell_px(theme)
        mx = (self._selection_side_space(theme, "left")
              + self._group_space(theme, "row")
              + self._label_space(theme, "row"))
        col_label_space = self._label_space(theme, "col")
        my = self._group_space(theme, "col") + (
            col_label_space if self.col_label_position == "top" else 0.0
        )
        result = {}
        for selection in self.selections:
            if selection.name is None:
                continue
            r0, r1, c0, c1 = self._selection_bounds(selection)
            result[selection.name] = (
                mx + c0 * c,
                my + r0 * c,
                (c1 - c0) * c,
                (r1 - r0) * c,
            )
        return result

    def _structured_fill(
        self, theme: Theme, cell, value: Optional[float], vmin: float, vmax: float
    ) -> str:
        if isinstance(cell, MatrixCell) and cell.role is not None:
            return theme.color_of(cell.role)
        if value is None:
            return theme.color_of("bg_subtle")
        if self.scale is not None:
            if self._is_binary_scale():
                # Binary masks are categorical diagrams, not magnitude
                # heatmaps. Keep their active cells at a print-safe middle
                # tone instead of consuming the darkest continuous endpoint.
                palette = theme.palette(self.scale.palette)
                # About two fifths of the sequential ramp gives binary ink
                # enough contrast to survive print while avoiding the visual
                # weight of a continuous heatmap maximum.
                t = self.scale.normalized(value) * 0.42
                index = int(round(t * (len(palette) - 1)))
                return palette[index]
            return self.scale.color(theme, value)
        use_value = abs(value) if self.absolute else value
        return theme.color_scale(use_value, self.palette, vmin, vmax)

    def _is_binary_scale(self) -> bool:
        if self.scale is None or self.scale.domain != (0.0, 1.0):
            return False
        values = {
            self._cell_value(cell)
            for row in self.data
            for cell in row
            if self._cell_value(cell) is not None
        }
        return bool(values) and values.issubset({0.0, 1.0})

    def _grid_mode(self, theme: Theme) -> bool:
        """Infer when a matrix is a discrete grid rather than a heatmap.

        Boolean masks, state tables, and selected/marked categorical cells
        should read as one coherent matrix with square shared boundaries.
        Rounded inset tiles are retained for annotated continuous heatmaps,
        where a small white gutter helps dense numeric labels breathe.
        """
        if not self._structured:
            return False
        cells = [cell for row in self.data for cell in row]
        categorical = bool(self.selections) or any(
            isinstance(cell, MatrixCell)
            and (cell.role is not None or cell.mark is not None)
            for cell in cells
        )
        if categorical:
            return True
        has_text = any(
            isinstance(cell, MatrixCell)
            and (cell.label not in (None, "") or cell.detail not in (None, ""))
            for cell in cells
        )
        return not has_text and self._cell_px(theme) <= self._CELL_SIZES["sm"]

    @staticmethod
    def _mark_text(mark: str) -> str:
        return {"check": "✓", "cross": "×", "x": "×"}.get(mark, mark)

    @staticmethod
    def _fit_text_size(text: str, preferred: float, available: float) -> float:
        """Fit one unwrapped SVG text run inside ``available`` pixels."""
        if not text:
            return preferred
        estimated = len(text) * preferred * 0.62
        if estimated <= available:
            return preferred
        return max(1.0, available / (len(text) * 0.62))

    def _render_mark(
        self,
        canvas: Canvas,
        cell: MatrixCell,
        cx: float,
        cy: float,
        c: float,
        theme: Theme,
        color: str,
        has_text: bool,
    ) -> None:
        if cell.mark is None:
            return
        if isinstance(cell.mark, Element):
            size = cell.mark.measure(theme)
            if has_text:
                px = cx + max(1.0, c - size.w - 2.0)
                py = cy + 1.5
            else:
                px = cx + (c - size.w) / 2
                py = cy + (c - size.h) / 2
            cell.mark.render(canvas, px, py, theme)
            return
        mark = self._mark_text(cell.mark)
        preferred = theme.size_px("micro" if len(mark) > 2 else "tiny")
        font = self._fit_text_size(mark, preferred, c - 5.0)
        if has_text:
            px = cx + c - 2.5
            py = cy + font + 1.0
            anchor = "end"
        else:
            px = cx + c / 2
            py = cy + c / 2 + font * 0.33
            anchor = "middle"
        canvas.text(px, py, mark, size=font, fill=color, weight="700", anchor=anchor)

    def _render_structured_cell(
        self,
        canvas: Canvas,
        cell,
        cx: float,
        cy: float,
        c: float,
        theme: Theme,
        vmin: float,
        vmax: float,
        masked: bool,
        is_pruned: bool,
        grid_mode: bool,
    ) -> None:
        value = self._cell_value(cell)
        fill = self._structured_fill(theme, cell, value, vmin, vmax)
        if grid_mode:
            border = theme.color_of("border")
            border_width = theme.hairline
            inset = border_width / 2.0
            cell_x, cell_y = cx + inset, cy + inset
            cell_w = cell_h = c - border_width
            radius = 0.0
        else:
            cell_x, cell_y, cell_w, cell_h = cx + 1, cy + 1, c - 2, c - 2
            radius = 1.5
            border = "none"
            border_width = 0.0

        if masked or is_pruned:
            fill = theme.color_of("#f8fafc")
            canvas.rect(
                cell_x,
                cell_y,
                cell_w,
                cell_h,
                fill=fill,
                stroke=theme.color_of("border_strong"),
                stroke_width=0.6,
                rx=radius,
                dasharray="2,1.5",
            )
        else:
            canvas.rect(
                cell_x,
                cell_y,
                cell_w,
                cell_h,
                fill=fill,
                stroke=(
                    border
                    if grid_mode
                    else (
                        "#1e3a8a"
                        if self.palette == "blues" and self.scale is None
                        else "none"
                    )
                ),
                stroke_width=border_width if grid_mode else 0.3,
                rx=radius,
                opacity=0.95,
            )
        if masked or is_pruned:
            return

        structured = cell if isinstance(cell, MatrixCell) else None
        label = structured.label if structured is not None else None
        detail = structured.detail if structured is not None else None
        if label is None and self.show_values and value is not None:
            label = f"{value:.2f}"
        has_label = label not in (None, "")
        has_detail = detail not in (None, "")
        text_color = theme.text_on(fill)
        if has_label and has_detail:
            primary_size = self._fit_text_size(
                str(label), theme.size_px("tiny"), c - 4.0
            )
            detail_size = self._fit_text_size(
                str(detail), theme.size_px("micro"), c - 4.0
            )
            canvas.text(
                cx + c / 2,
                cy + c / 2 - 1.0,
                str(label),
                size=primary_size,
                fill=text_color,
                weight="700" if structured and structured.emphasis else "500",
                anchor="middle",
            )
            canvas.text(
                cx + c / 2,
                cy + c / 2 + detail_size * 1.05,
                str(detail),
                size=detail_size,
                fill=text_color,
                anchor="middle",
            )
        elif has_label or has_detail:
            text = str(label if has_label else detail)
            size_name = "tiny" if has_label else "micro"
            font = self._fit_text_size(text, theme.size_px(size_name), c - 4.0)
            canvas.text(
                cx + c / 2,
                cy + c / 2 + font * 0.33,
                text,
                size=font,
                fill=text_color,
                weight=(
                    "700" if has_label and structured and structured.emphasis else "normal"
                ),
                anchor="middle",
            )
        if structured is not None:
            self._render_mark(
                canvas,
                structured,
                cx,
                cy,
                c,
                theme,
                text_color,
                has_label or has_detail,
            )

    def _render_selections(
        self, canvas: Canvas, mx: float, my: float, c: float, theme: Theme
    ) -> None:
        for selection in self.selections:
            r0, r1, c0, c1 = self._selection_bounds(selection)
            sx, sy = mx + c0 * c, my + r0 * c
            sw, sh = (c1 - c0) * c, (r1 - r0) * c
            color = theme.color_of(selection.role)
            inset = max(0.5, theme.thick / 2)
            if selection.style != "none":
                canvas.rect(
                    sx + inset,
                    sy + inset,
                    sw - 2 * inset,
                    sh - 2 * inset,
                    fill="none",
                    stroke=color,
                    stroke_width=theme.thick,
                    rx=2,
                    dasharray=(
                        "5,3" if selection.style == "dashed" else None
                    ),
                )
            if selection.label:
                position = self._resolved_selection_label_position(
                    selection, theme
                )
                if position in ("left", "right"):
                    continue
                lines = selection.label.splitlines()
                longest = max(lines, key=len, default="")
                preferred = theme.size_px(
                    "small" if position == "center" else "micro"
                )
                font = self._fit_text_size(longest, preferred, sw - 6.0)
                line_h = font * 1.15
                if position == "center":
                    first_y = (
                        sy + sh / 2
                        - (len(lines) - 1) * line_h / 2
                        + font * 0.33
                    )
                else:
                    first_y = sy + font + 2.0
                for index, line in enumerate(lines):
                    canvas.text(
                        sx + sw / 2,
                        first_y + index * line_h,
                        line,
                        size=font,
                        fill=color,
                        weight="700",
                        anchor="middle",
                    )

    def _render_selection_side_labels(
        self, canvas: Canvas, mx: float, my: float, c: float, theme: Theme
    ) -> None:
        matrix_right = mx + self.cols * c
        guide = theme.unit * 1.4
        label_gap = theme.unit * 0.7
        font = theme.size_px("small")
        line_h = theme.text_height("small") * 0.95
        for selection in self.selections:
            if not selection.label:
                continue
            position = self._resolved_selection_label_position(
                selection, theme
            )
            if position not in ("left", "right"):
                continue
            r0, r1, _c0, _c1 = self._selection_bounds(selection)
            top = my + r0 * c
            bottom = my + r1 * c
            mid = (top + bottom) / 2.0
            color = theme.color_of(selection.role)
            marker = canvas.define_arrow_marker(
                color=color,
                stroke_width=theme.hairline,
                arrow_size=theme.arrow_size * 0.78,
                name_hint="selection-extent",
            )
            if position == "left":
                edge = mx
                extent_x = mx - guide
                label_x = extent_x - label_gap
                anchor = "end"
            else:
                edge = matrix_right
                extent_x = matrix_right + guide
                label_x = extent_x + label_gap
                anchor = "start"
            dash = "4,3"
            canvas.line(
                extent_x, top, edge, top,
                stroke=color, stroke_width=theme.hairline,
                dasharray=dash,
            )
            canvas.line(
                extent_x, bottom, edge, bottom,
                stroke=color, stroke_width=theme.hairline,
                dasharray=dash,
            )
            canvas.line(
                extent_x, top + theme.unit * 0.3,
                extent_x, bottom - theme.unit * 0.3,
                stroke=color, stroke_width=theme.hairline,
                marker_start=marker, marker_end=marker,
            )
            lines = self._side_label_lines(selection.label, theme)
            first = mid - (len(lines) - 1) * line_h / 2.0 + font * 0.33
            for index, line in enumerate(lines):
                canvas.text(
                    label_x, first + index * line_h, line,
                    size=font, fill=color, weight="600", anchor=anchor,
                )
    def _publish_selection_bboxes(self, x: float, y: float, theme: Theme) -> None:
        named = self.selection_bboxes(theme)
        if not named:
            return
        # Anchor registration lives above the element layer.  Import it only
        # while rendering to avoid an import cycle; this mirrors Theme's late
        # palette resolution and lets named cell regions participate in the
        # existing routed-connection registry.
        from ..composition._anchor import _anchor_stack

        stack = _anchor_stack.get()
        if stack is None:
            return
        for registry in stack:
            for name, (bx, by, bw, bh) in named.items():
                registry[name] = (x + bx, y + by, bw, bh)

    def _render_axis_groups(self, canvas: Canvas, x: float, y: float,
                            mx: float, my: float, c: float,
                            theme: Theme) -> None:
        row_band = self._group_space(theme, "row")
        col_band = self._group_space(theme, "col")
        tick = theme.unit * 0.45
        if self.col_groups:
            lines_per_group, font, line_h = self._group_label_layout(
                theme, "col"
            )
            n_max = max(len(lines) for lines in lines_per_group)
            line_y = y + col_band - theme.unit * 0.35
            for group, lines in zip(self.col_groups, lines_per_group):
                start = mx + group.start * c
                stop = mx + group.stop * c
                color = theme.color_of(group.role)
                canvas.line(start, line_y, stop, line_y,
                            stroke=color, stroke_width=theme.line)
                canvas.line(start, line_y - tick, start, line_y + tick,
                            stroke=color, stroke_width=theme.line)
                canvas.line(stop, line_y - tick, stop, line_y + tick,
                            stroke=color, stroke_width=theme.line)
                # Bottom-align each stack so every group's last line sits
                # just above its extent bracket.
                for index, line in enumerate(lines):
                    canvas.text(
                        (start + stop) / 2,
                        y + font * 0.85
                        + (n_max - len(lines) + index) * line_h,
                        line,
                        size=font,
                        fill=color,
                        weight="700",
                        anchor="middle",
                    )
        if self.row_groups:
            lines_per_group, font, line_h = self._group_label_layout(
                theme, "row"
            )
            n_max = max(len(lines) for lines in lines_per_group)
            line_x = x + row_band - theme.unit * 0.35
            for group, lines in zip(self.row_groups, lines_per_group):
                start = my + group.start * c
                stop = my + group.stop * c
                color = theme.color_of(group.role)
                canvas.line(line_x, start, line_x, stop,
                            stroke=color, stroke_width=theme.line)
                canvas.line(line_x - tick, start, line_x + tick, start,
                            stroke=color, stroke_width=theme.line)
                canvas.line(line_x - tick, stop, line_x + tick, stop,
                            stroke=color, stroke_width=theme.line)
                # Rotated stacks advance rightward toward the bracket.
                for index, line in enumerate(lines):
                    canvas.text(
                        x + font * 0.6
                        + (n_max - len(lines) + index) * line_h,
                        (start + stop) / 2,
                        line,
                        size=font,
                        fill=color,
                        weight="700",
                        anchor="middle",
                        baseline="middle",
                        rotate=-90,
                    )

    def _render_partitions(self, canvas: Canvas, mx: float, my: float,
                           c: float, theme: Theme) -> None:
        color = theme.paint_of("border_strong")
        for partition in self.col_partitions:
            px = mx + partition * c
            canvas.line(
                px, my, px, my + self.rows * c,
                stroke=color, stroke_width=theme.thick,
            )
        for partition in self.row_partitions:
            py = my + partition * c
            canvas.line(
                mx, py, mx + self.cols * c, py,
                stroke=color, stroke_width=theme.thick,
            )

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        if any(selection.name is not None for selection in self.selections):
            # Named selections are connector endpoints INSIDE this matrix.
            # Treat the matrix as their owning region rather than an opaque
            # obstacle; otherwise the planner has no legal exit from the
            # selection to an external annotation.
            from ..core._routing_context import register_routing_region
            register_routing_region(self, x, y, size.w, size.h)
        else:
            _register_implicit_obstacle(x, y, size.w, size.h)
        c = self._cell_px(theme)
        row_group_w = self._group_space(theme, "row")
        col_group_h = self._group_space(theme, "col")
        row_lbl_w = self._label_space(theme, "row")
        col_lbl_h = self._label_space(theme, "col")
        side_left_w = self._selection_side_space(theme, "left")
        mx = x + side_left_w + row_group_w + row_lbl_w
        my = y + col_group_h + (
            col_lbl_h if self.col_label_position == "top" else 0.0
        )
        vmin, vmax = self._value_range()
        grid_mode = self._grid_mode(theme)

        self._render_axis_groups(canvas, x + side_left_w, y, mx, my, c, theme)

        col_labels = self._resolve_labels("col")
        if col_labels:
            sz = theme.size_px("small")
            for j, lbl in enumerate(col_labels):
                cx = mx + j * c + c / 2
                if self.col_label_position == "top":
                    baseline = y + col_group_h + col_lbl_h - theme.unit * 0.3
                else:
                    baseline = my + self.rows * c + sz
                is_hl = j in self.highlight_cols
                angle = self.col_label_angle
                canvas.text(
                    cx,
                    baseline,
                    lbl,
                    size=sz,
                    fill=theme.color_of("highlight" if is_hl else "light"),
                    weight="700" if is_hl else "500",
                    anchor=("start" if angle < -0.5 else
                            "end" if angle > 0.5 else "middle"),
                    rotate=angle,
                )

        row_labels = self._resolve_labels("row")
        if row_labels:
            sz = theme.size_px("small")
            sub_sz = theme.size_px("tiny")
            sub_advance = sub_sz * 1.3
            for i, lbl in enumerate(row_labels):
                lines = self._row_label_lines(lbl)
                is_hl = i in self.highlight_rows
                # Centre the whole line block on the row, not just line one.
                baseline = (
                    my + i * c + c / 2 + sz * 0.35
                    - (len(lines) - 1) * sub_advance / 2
                )
                for k, line in enumerate(lines):
                    canvas.text(
                        mx - theme.unit * 0.7,
                        baseline + k * sub_advance,
                        line,
                        size=sz if k == 0 else sub_sz,
                        fill=theme.color_of(
                            "highlight" if is_hl
                            else ("light" if k == 0 else "faint")
                        ),
                        weight="700" if is_hl else ("500" if k == 0 else "400"),
                        anchor="end",
                    )

        for i in range(self.rows):
            for j in range(self.cols):
                val = self.data[i][j]
                masked = self.mask is not None and self.mask[i][j]
                is_pruned = i in self.highlight_rows or j in self.highlight_cols
                cx, cy = mx + j * c, my + i * c
                if self._structured:
                    self._render_structured_cell(
                        canvas,
                        val,
                        cx,
                        cy,
                        c,
                        theme,
                        vmin,
                        vmax,
                        masked,
                        is_pruned,
                        grid_mode,
                    )
                    continue

                # Historical numeric rendering path.  Keep this deliberately
                # separate so existing Matrix output remains byte-compatible.
                use_val = abs(val) if self.absolute else val
                if masked or is_pruned:
                    canvas.rect(
                        cx + 1,
                        cy + 1,
                        c - 2,
                        c - 2,
                        fill=theme.color_of("#f8fafc"),
                        stroke=theme.color_of("border_strong"),
                        stroke_width=0.6,
                        rx=2,
                        dasharray="2,1.5",
                    )
                else:
                    color = theme.color_scale(use_val, self.palette, vmin, vmax)
                    canvas.rect(
                        cx + 1,
                        cy + 1,
                        c - 2,
                        c - 2,
                        fill=color,
                        stroke="#1e3a8a" if self.palette == "blues" else "none",
                        stroke_width=0.3,
                        rx=2,
                        opacity=0.95,
                    )
                if self.show_values and not masked and not is_pruned:
                    text_color = (
                        "white" if use_val > (vmin + vmax) / 2 else theme.text
                    )
                    canvas.text(
                        cx + c / 2,
                        cy + c / 2 + theme.size_px("tiny") * 0.33,
                        f"{val:.2f}",
                        size=theme.size_px("tiny"),
                        fill=(
                            text_color
                            if text_color.startswith("#")
                            else theme.color_of(text_color)
                        ),
                        anchor="middle",
                    )

        self._render_partitions(canvas, mx, my, c, theme)

        for i in self.highlight_rows:
            canvas.rect(
                mx - 1,
                my + i * c + 1,
                self.cols * c + 2,
                c - 2,
                fill="none",
                stroke=theme.highlight,
                stroke_width=1.8,
                rx=3,
                dasharray="5,3",
            )
        for j in self.highlight_cols:
            canvas.rect(
                mx + j * c + 1,
                my - 1,
                c - 2,
                self.rows * c + 2,
                fill="none",
                stroke=theme.highlight,
                stroke_width=1.8,
                rx=3,
                dasharray="5,3",
            )

        self._render_selections(canvas, mx, my, c, theme)
        self._render_selection_side_labels(canvas, mx, my, c, theme)
        self._publish_selection_bboxes(x, y, theme)

        if self.caption:
            content_bottom = y + col_group_h + col_lbl_h + self.rows * c
            baseline = content_bottom + theme.text_height("small")
            canvas.text(
                x + size.w / 2,
                baseline,
                self.caption,
                size=theme.size_px("small"),
                fill=theme.color_of("highlight"),
                weight="600",
                anchor="middle",
            )


class ColorBar(Element):
    """Measured numeric legend for a shared :class:`ColorScale`."""

    def __init__(
        self,
        scale: ColorScale,
        *,
        orientation: str = "vertical",
        ticks: Union[str, Sequence[float]] = "auto",
        tick_format: Union[str, Callable[[float], str]] = "g",
        end_labels: Tuple[Optional[str], Optional[str]] = (None, None),
        label: Optional[str] = None,
    ):
        if not isinstance(scale, ColorScale):
            raise TypeError("ColorBar.scale must be a ColorScale")
        if orientation not in ("vertical", "horizontal"):
            raise ValueError("ColorBar.orientation must be 'vertical' or 'horizontal'")
        if isinstance(ticks, str):
            if ticks != "auto":
                raise ValueError("ColorBar.ticks must be 'auto' or a sequence")
            self.ticks: Union[str, Tuple[float, ...]] = ticks
        else:
            values = tuple(float(value) for value in ticks)
            if any(not math.isfinite(value) for value in values):
                raise ValueError("ColorBar ticks must be finite")
            lo, hi = scale.domain
            if any(value < lo or value > hi for value in values):
                raise ValueError("ColorBar ticks must lie inside scale.domain")
            self.ticks = values
        if not (isinstance(tick_format, str) or callable(tick_format)):
            raise TypeError("ColorBar.tick_format must be str or callable")
        if len(end_labels) != 2:
            raise ValueError("ColorBar.end_labels must contain (low, high)")
        self.scale = scale
        self.orientation = orientation
        self.tick_format = tick_format
        self.end_labels = tuple(
            None if value is None else str(value) for value in end_labels
        )
        self.label = None if label is None else str(label)

    def _resolved_ticks(self) -> Tuple[float, ...]:
        if self.ticks != "auto":
            return self.ticks
        lo, hi = self.scale.domain
        middle = self.scale.center if self.scale.center is not None else (lo + hi) / 2
        return (lo, middle, hi)

    def _format_tick(self, value: float) -> str:
        if callable(self.tick_format):
            return str(self.tick_format(value))
        return format(value, self.tick_format)

    @staticmethod
    def _text_width(theme: Theme, value: str, size: str = "small") -> float:
        font = theme.size_px(size)
        return max(theme.text_width(value, size), len(value) * font * 0.62)

    def _layout(self, theme: Theme) -> dict[str, float]:
        font = theme.size_px("small")
        gap = theme.unit * 0.55
        tick_len = theme.unit * 0.65
        tick_texts = [self._format_tick(value) for value in self._resolved_ticks()]
        tick_w = max(
            (self._text_width(theme, value) for value in tick_texts), default=0.0
        )
        end_w = max(
            (
                self._text_width(theme, value)
                for value in self.end_labels
                if value is not None
            ),
            default=0.0,
        )
        label_w = self._text_width(theme, self.label) if self.label else 0.0
        label_h = font * 1.4 if self.label else 0.0
        thickness = theme.unit * 1.5
        length = theme.unit * 12.0

        if self.orientation == "vertical":
            top_pad = font * 0.70
            bottom_pad = font * 0.70
            end_gap = gap if end_w else 0.0
            stroke_pad = theme.hairline / 2
            width = (
                thickness + tick_len + gap + tick_w + end_gap + end_w
                + 2 * stroke_pad
            )
            width = max(width, label_w)
            return {
                "w": width,
                "h": label_h + top_pad + length + bottom_pad,
                "bar_x": stroke_pad,
                "bar_y": label_h + top_pad,
                "bar_w": thickness,
                "bar_h": length,
                "tick_len": tick_len,
                "gap": gap,
                "tick_w": tick_w,
                "label_h": label_h,
                "font": font,
            }

        text_extent = max(tick_w, end_w)
        side_pad = text_extent / 2 + theme.unit * 0.25
        end_h = font * 1.35 if any(self.end_labels) else 0.0
        width = max(length + 2 * side_pad, label_w)
        bar_x = (width - length) / 2
        bar_y = label_h + end_h
        height = bar_y + thickness + tick_len + gap + font * 1.35
        return {
            "w": width,
            "h": height,
            "bar_x": bar_x,
            "bar_y": bar_y,
            "bar_w": length,
            "bar_h": thickness,
            "tick_len": tick_len,
            "gap": gap,
            "tick_w": tick_w,
            "label_h": label_h,
            "end_h": end_h,
            "font": font,
        }

    def measure(self, theme: Theme) -> BBox:
        layout = self._layout(theme)
        return BBox(layout["w"], layout["h"])

    def _gradient(self, canvas: Canvas, theme: Theme) -> str:
        gradient_id = canvas.gen_id("color-scale")
        if self.orientation == "vertical":
            vector = 'x1="0%" y1="100%" x2="0%" y2="0%"'
        else:
            vector = 'x1="0%" y1="0%" x2="100%" y2="0%"'
        stops = "".join(
            f'<stop offset="{offset * 100:.4g}%" stop-color="{color}"/>'
            for offset, color in self.scale.gradient_stops(theme)
        )
        canvas.raw_def(
            f'<linearGradient id="{gradient_id}" {vector}>{stops}</linearGradient>'
        )
        return gradient_id

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        layout = self._layout(theme)
        bx = x + layout["bar_x"]
        by = y + layout["bar_y"]
        bw, bh = layout["bar_w"], layout["bar_h"]
        font = layout["font"]
        if self.label:
            canvas.text(
                x + layout["w"] / 2,
                y + font,
                self.label,
                size=font,
                fill=theme.color_of("text"),
                weight="700",
                anchor="middle",
            )

        gradient_id = self._gradient(canvas, theme)
        canvas.rect(
            bx,
            by,
            bw,
            bh,
            fill=f"url(#{gradient_id})",
            stroke=theme.color_of("border_strong"),
            stroke_width=theme.hairline,
        )

        lo, hi = self.scale.domain
        ticks = self._resolved_ticks()
        if self.orientation == "vertical":
            tick_x0 = bx + bw
            tick_x1 = tick_x0 + layout["tick_len"]
            text_x = tick_x1 + layout["gap"]
            for value in ticks:
                fraction = (value - lo) / (hi - lo)
                ty = by + (1.0 - fraction) * bh
                canvas.line(
                    tick_x0,
                    ty,
                    tick_x1,
                    ty,
                    stroke=theme.color_of("border_strong"),
                    stroke_width=theme.hairline,
                )
                canvas.text(
                    text_x,
                    ty + font * 0.33,
                    self._format_tick(value),
                    size=font,
                    fill=theme.color_of("text_muted"),
                )
            end_x = text_x + layout["tick_w"] + (
                layout["gap"] if any(self.end_labels) else 0.0
            )
            low, high = self.end_labels
            if high:
                canvas.text(
                    end_x,
                    by + font * 0.33,
                    high,
                    size=font,
                    fill=theme.color_of("text_muted"),
                    italic=True,
                )
            if low:
                canvas.text(
                    end_x,
                    by + bh + font * 0.33,
                    low,
                    size=font,
                    fill=theme.color_of("text_muted"),
                    italic=True,
                )
            return

        tick_y0 = by + bh
        tick_y1 = tick_y0 + layout["tick_len"]
        text_y = tick_y1 + layout["gap"] + font
        for value in ticks:
            fraction = (value - lo) / (hi - lo)
            tx = bx + fraction * bw
            canvas.line(
                tx,
                tick_y0,
                tx,
                tick_y1,
                stroke=theme.color_of("border_strong"),
                stroke_width=theme.hairline,
            )
            canvas.text(
                tx,
                text_y,
                self._format_tick(value),
                size=font,
                fill=theme.color_of("text_muted"),
                anchor="middle",
            )
        low, high = self.end_labels
        end_y = y + layout["label_h"] + font
        if low:
            canvas.text(
                bx,
                end_y,
                low,
                size=font,
                fill=theme.color_of("text_muted"),
                italic=True,
            )
        if high:
            canvas.text(
                bx + bw,
                end_y,
                high,
                size=font,
                fill=theme.color_of("text_muted"),
                italic=True,
                anchor="end",
            )
