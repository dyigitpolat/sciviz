"""LineChart: paper-friendly multi-series line plot with inline annotations.

Scope is deliberately tight: one set of x/y axes, N named line series
(each a list of ``(x, y)`` points), optional in-plot annotations
(``Annotate(x, y, text)``), and a compact legend. Log scales, tick
format, and gridlines are inherited from :class:`Scatter`'s conventions
so the two elements read as one family.
"""

from __future__ import annotations

import math as _m
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass
class Series:
    """One line series.

    Parameters
    ----------
    points : list of ``(x, y)``
    label : str, optional
        Label shown in the legend (if any). ``None`` hides from legend.
    color : str
        Theme colour role; defaults to "auto" which cycles through
        :meth:`Theme.role_for_index`.
    dash : str, optional
        SVG ``stroke-dasharray`` string, e.g. ``"4,3"``.
    width : float, optional
        Stroke width. Defaults to ``theme.line``.
    marker_fill : str
        ``"solid"`` (default) fills markers with the series colour;
        ``"hollow"`` draws open markers (background fill, series-colour
        outline). The conventional encoding for measured vs.
        derived/projected points: overlay a hollow marker-only series on
        the same line.
    show_line : bool
        When ``False`` the connecting polyline is suppressed and only
        markers render — a marker-only overlay series. The legend sample
        then shows just the marker.
    """

    points: Sequence[Tuple[float, float]]
    label: Optional[str] = None
    color: str = "auto"
    dash: Optional[str] = None
    width: Optional[float] = None
    key: Optional[str] = None
    marker: Optional[str] = None
    marker_size: Union[str, float] = "xs"
    marker_fill: str = "solid"
    show_line: bool = True


@dataclass(frozen=True)
class FillBetween:
    """A semantic area between two keyed series.

    ``lower`` and ``upper`` resolve against :attr:`Series.key` (falling back
    to the series label).  The polygon is interpolated over the shared x
    domain and rendered beneath every line.
    """

    lower: str
    upper: str
    color: Optional[str] = None
    opacity: float = 0.14
    labels: Optional[Callable[[float, float, float], str]] = None


@dataclass
class Annotate:
    """A single inline annotation pinned to a data coordinate.

    Parameters
    ----------
    x, y : float
        Data-space position of the anchor.
    text : str
        Label. May contain newlines; lines are stacked downward.
    dx, dy : float
        Pixel offset of the text from the anchor (to avoid overlap).
    color : str
        Text color; default "muted".
    size : str
        Text size token; default "small".
    dot : bool
        Draw the small anchor dot at ``(x, y)``. Set ``False`` when the
        annotation is pinned to an existing series marker, or when the
        note is free-floating and references no single datum (a dot
        would read as a data point).
    anchor : str
        SVG text anchor applied to every line: ``"start"`` (default),
        ``"middle"``, or ``"end"``.
    """

    x: float
    y: float
    text: str
    dx: float = 8.0
    dy: float = -10.0
    color: str = "muted"
    size: str = "small"
    dot: bool = True
    anchor: str = "start"


@dataclass(frozen=True)
class SeriesDelta:
    """A directed difference between two series at one x coordinate.

    The chart interpolates both series, draws the vertical relationship,
    chooses an inward arrow lane near plot edges, and places the label on
    whichever side has room.  Authors declare the compared series and the
    meaning; no pixel offsets or duplicate y values are required.
    """

    x: float
    source: str
    target: str
    label: str
    color: str = "text"
    size: str = "small"


class LineChart(Element):
    """Multi-series line chart with axes, gridlines, and inline annotations.

    Parameters
    ----------
    series : list of :class:`Series`
    x_range, y_range : tuple (low, high)
    width, height : float
        Plot area (excluding axis labels).
    x_label, y_label : str
    log_x, log_y : bool
    grid : bool
    annotations : list of :class:`Annotate`, optional
    legend : str or None
        Where to render the legend: ``"top"``, ``"bottom"``, ``"right"``,
        or ``None`` (default -- use an external :class:`Legend`).
    """

    _PLOT_SIZES = {
        "sm": (240.0, 144.0),
        "md": (300.0, 180.0),
        "lg": (360.0, 210.0),
        "xl": (440.0, 260.0),
    }

    def __init__(self, series: Sequence[Union[Series, dict]], *,
                 x_range: Tuple[float, float] = (0.0, 1.0),
                 y_range: Tuple[float, float] = (0.0, 1.0),
                 width: Optional[float] = None,
                 height: Optional[float] = None,
                 size: str = "md",
                 x_label: str = "",
                 y_label: str = "",
                 log_x: bool = False,
                 log_y: bool = False,
                 grid: bool = True,
                 annotations: Optional[Sequence[Annotate]] = None,
                 deltas: Optional[Sequence[SeriesDelta]] = None,
                 legend: Optional[str] = None,
                 fills: Optional[Sequence[FillBetween]] = None,
                 x_ticks: Union[str, Sequence[float]] = "auto",
                 y_ticks: Union[str, Sequence[float]] = "auto",
                 x_tick_format: Union[str, Callable[[float], str]] = "g",
                 y_tick_format: Union[str, Callable[[float], str]] = "g"):
        self.series = [self._coerce_series(s) for s in series]
        self.x_range = x_range
        self.y_range = y_range
        if size not in self._PLOT_SIZES:
            allowed = ", ".join(self._PLOT_SIZES)
            raise ValueError(f"LineChart.size must be one of {allowed}")
        default_width, default_height = self._PLOT_SIZES[size]
        self.width = float(default_width if width is None else width)
        self.height = float(default_height if height is None else height)
        self.x_label = x_label
        self.y_label = y_label
        self.log_x = log_x
        self.log_y = log_y
        self.grid = grid
        self.annotations = list(annotations) if annotations else []
        self.deltas = list(deltas) if deltas else []
        self.fills = list(fills) if fills else []
        self.x_ticks = x_ticks
        self.y_ticks = y_ticks
        self.x_tick_format = x_tick_format
        self.y_tick_format = y_tick_format
        if legend not in (
            None,
            "top",
            "bottom",
            "right",
            "inside-top-left",
            "inside-top-right",
            "inside-bottom-right",
        ):
            raise ValueError(
                "legend must be None, 'top', 'bottom', 'right', "
                "'inside-top-left', 'inside-top-right', or "
                f"'inside-bottom-right'; got {legend!r}"
            )
        self.legend = legend
        self._validate_relations()

    @staticmethod
    def _coerce_series(s) -> Series:
        if isinstance(s, Series):
            return s
        if isinstance(s, dict):
            return Series(**s)
        raise TypeError(
            f"LineChart series must be Series or dict; got {type(s)}")

    def _series_key(self, series: Series, index: int) -> str:
        return series.key or series.label or f"series_{index}"

    def _validate_relations(self) -> None:
        keys = [self._series_key(series, i)
                for i, series in enumerate(self.series)]
        if len(keys) != len(set(keys)):
            raise ValueError("LineChart series keys/labels must be unique")
        known = set(keys)
        for fill in self.fills:
            if fill.lower not in known or fill.upper not in known:
                raise ValueError(
                    f"FillBetween references unknown series: "
                    f"{fill.lower!r}, {fill.upper!r}")
            if not (0.0 <= fill.opacity <= 1.0):
                raise ValueError("FillBetween opacity must be between 0 and 1")
            if fill.labels is not None and not callable(fill.labels):
                raise TypeError("FillBetween.labels must be callable or None")
        for delta in self.deltas:
            if delta.source not in known or delta.target not in known:
                raise ValueError(
                    "SeriesDelta references unknown series: "
                    f"{delta.source!r}, {delta.target!r}"
                )
        for series in self.series:
            if series.marker not in (None, "circle", "square", "triangle", "diamond"):
                raise ValueError(
                    "Series.marker must be circle, square, triangle, diamond, or None")
            if series.marker_fill not in ("solid", "hollow"):
                raise ValueError(
                    "Series.marker_fill must be 'solid' or 'hollow'")

    # ---- projection helpers ---------------------------------------------

    def _x_to_px(self, v: float) -> float:
        x0, x1 = self.x_range
        if self.log_x:
            v = _m.log10(max(v, 1e-12))
            x0 = _m.log10(max(x0, 1e-12))
            x1 = _m.log10(max(x1, 1e-12))
        return (v - x0) / (x1 - x0) * self.width

    def _y_to_px(self, v: float) -> float:
        y0, y1 = self.y_range
        if self.log_y:
            v = _m.log10(max(v, 1e-12))
            y0 = _m.log10(max(y0, 1e-12))
            y1 = _m.log10(max(y1, 1e-12))
        return self.height - (v - y0) / (y1 - y0) * self.height

    def _axis_ticks(self, lo: float, hi: float, log: bool) -> List[float]:
        if log:
            lo_p = int(_m.floor(_m.log10(max(lo, 1e-12))))
            hi_p = int(_m.ceil(_m.log10(max(hi, 1e-12))))
            return [10 ** p for p in range(lo_p, hi_p + 1)
                    if lo <= 10 ** p <= hi]
        # Linear ticks: 4 divisions.
        step = (hi - lo) / 4.0
        if step <= 0:
            return [lo]
        return [lo + step * i for i in range(5)]

    @staticmethod
    def _fmt_tick(v: float, log: bool) -> str:
        if log:
            p = int(round(_m.log10(max(v, 1e-12))))
            if -3 <= p <= 3:
                return f"{v:g}"
            return f"10^{p}"
        if abs(v - round(v)) < 1e-6 and abs(v) < 1e4:
            return str(int(round(v)))
        return f"{v:g}"

    def _ticks(self, explicit, value_range, log: bool) -> List[float]:
        if explicit == "auto":
            return self._axis_ticks(*value_range, log)
        if isinstance(explicit, str):
            raise ValueError("ticks must be 'auto' or a sequence of values")
        return [float(value) for value in explicit]

    def _tick_label(self, value: float, log: bool,
                    formatter: Union[str, Callable[[float], str]]) -> str:
        if callable(formatter):
            return str(formatter(value))
        if formatter == "g":
            return self._fmt_tick(value, log)
        return format(value, formatter)

    @staticmethod
    def _interpolate(points: Sequence[Tuple[float, float]], x: float) -> float:
        ordered = sorted((float(px), float(py)) for px, py in points)
        if not ordered or x < ordered[0][0] or x > ordered[-1][0]:
            raise ValueError("interpolation point lies outside series domain")
        for px, py in ordered:
            if abs(px - x) <= 1e-12:
                return py
        for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
            if x0 <= x <= x1:
                if x1 == x0:
                    return y1
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return ordered[-1][1]

    def _fill_polygon(self, fill: FillBetween,
                      series_by_key: dict[str, Series]) -> list[tuple[float, float]]:
        lower = series_by_key[fill.lower]
        upper = series_by_key[fill.upper]
        lower_x = [float(x) for x, _ in lower.points]
        upper_x = [float(x) for x, _ in upper.points]
        lo = max(min(lower_x), min(upper_x))
        hi = min(max(lower_x), max(upper_x))
        if hi < lo:
            return []
        xs = sorted({x for x in lower_x + upper_x if lo <= x <= hi}
                    | {lo, hi})
        upper_points = [(x, self._interpolate(upper.points, x)) for x in xs]
        lower_points = [(x, self._interpolate(lower.points, x)) for x in xs]
        return upper_points + list(reversed(lower_points))

    @staticmethod
    def _marker_radius(marker_size: Union[str, float], theme: Theme) -> float:
        if isinstance(marker_size, (int, float)):
            return max(0.5, float(marker_size))
        factors = {"xs": 0.42, "sm": 0.58, "md": 0.75, "lg": 0.95}
        if marker_size not in factors:
            raise ValueError("marker_size must be xs/sm/md/lg or a number")
        return theme.unit * factors[marker_size]

    def _draw_marker(self, canvas: Canvas, marker: str, px: float, py: float,
                     radius: float, color: str, theme: Theme,
                     fill_mode: str = "solid") -> None:
        if fill_mode == "hollow":
            fill = theme.color_of("bg")
            stroke = color
            sw = theme.line
        else:
            fill = color
            stroke = "white"
            sw = theme.hairline
        if marker == "circle":
            canvas.circle(px, py, radius, fill=fill, stroke=stroke,
                          stroke_width=sw)
        elif marker == "square":
            canvas.rect(px - radius, py - radius, 2 * radius, 2 * radius,
                        fill=fill, stroke=stroke, stroke_width=sw)
        elif marker == "triangle":
            canvas.polygon([(px, py - radius),
                            (px + radius, py + radius),
                            (px - radius, py + radius)],
                           fill=fill, stroke=stroke,
                           stroke_width=sw)
        elif marker == "diamond":
            canvas.polygon([(px, py - radius), (px + radius, py),
                            (px, py + radius), (px - radius, py)],
                           fill=fill, stroke=stroke,
                           stroke_width=sw)

    # ---- layout ----------------------------------------------------------

    def _pad(self, theme: Theme) -> Tuple[float, float, float, float]:
        """Return padding (left, top, right, bottom) around the plot area."""
        left = 42.0 + (theme.text_height("small") + 4 if self.y_label else 0)
        bot = theme.text_height("small") * 2.3 + (
            theme.text_height("label") + 4 if self.x_label else 0)
        top = 10.0
        right = 8.0
        if self.legend == "top":
            top += theme.text_height("small") + 6
        if self.legend == "bottom":
            bot += theme.text_height("small") + 6
        if self.legend == "right":
            right += 92.0
        return left, top, right, bot

    def measure(self, theme: Theme) -> BBox:
        L, T, R, B = self._pad(theme)
        return BBox(L + self.width + R, T + self.height + B)

    # ---- render ----------------------------------------------------------

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        L, T, R, B = self._pad(theme)
        plot_x = x + L
        plot_y = y + T

        grid_color = theme.color_of("grid")
        axis_color = theme.color_of("border_strong")
        text_col = theme.color_of("text")
        muted = theme.color_of("text_muted")

        # gridlines + ticks
        x_ticks = self._ticks(self.x_ticks, self.x_range, self.log_x)
        y_ticks = self._ticks(self.y_ticks, self.y_range, self.log_y)

        if self.grid:
            for xv in x_ticks:
                px = plot_x + self._x_to_px(xv)
                canvas.line(px, plot_y, px, plot_y + self.height,
                            stroke=grid_color, stroke_width=theme.hairline,
                            opacity=0.35)
            for yv in y_ticks:
                py = plot_y + self._y_to_px(yv)
                canvas.line(plot_x, py, plot_x + self.width, py,
                            stroke=grid_color, stroke_width=theme.hairline,
                            opacity=0.35)

        # axes
        canvas.line(plot_x, plot_y + self.height,
                    plot_x + self.width, plot_y + self.height,
                    stroke=axis_color, stroke_width=theme.line)
        canvas.line(plot_x, plot_y, plot_x, plot_y + self.height,
                    stroke=axis_color, stroke_width=theme.line)

        # tick labels
        tick_h = theme.text_height("small")
        tick_px = theme.size_px("small")
        for xv in x_ticks:
            px = plot_x + self._x_to_px(xv)
            label = self._tick_label(xv, self.log_x, self.x_tick_format)
            canvas.text(px, plot_y + self.height + tick_h,
                        label, size=tick_px,
                        fill=muted, anchor="middle")
        for yv in y_ticks:
            py = plot_y + self._y_to_px(yv)
            label = self._tick_label(yv, self.log_y, self.y_tick_format)
            canvas.text(plot_x - 4.0,
                        py + tick_px * 0.33,
                        label, size=tick_px,
                        fill=muted, anchor="end")

        # axis labels
        if self.x_label:
            canvas.text(plot_x + self.width / 2,
                        plot_y + self.height + tick_h * 2.2,
                        self.x_label, size=theme.size_px("label"),
                        fill=text_col, anchor="middle")
        if self.y_label:
            # canvas.text (not raw SVG) so the rotated label's ink is
            # tracked -- otherwise auto-trim can crop the y-axis title.
            canvas.text(plot_x - 36.0, plot_y + self.height / 2,
                        self.y_label, size=theme.size_px("label"),
                        fill=text_col, anchor="middle", rotate=-90)

        # relational fills are painted beneath all line work.
        series_by_key = {
            self._series_key(series, i): series
            for i, series in enumerate(self.series)
        }
        for fill in self.fills:
            data_polygon = self._fill_polygon(fill, series_by_key)
            if len(data_polygon) < 3:
                continue
            upper = series_by_key[fill.upper]
            upper_i = self.series.index(upper)
            color_name = fill.color
            if color_name is None:
                color_name = (upper.color if upper.color != "auto"
                              else theme.role_for_index(upper_i))
            points = [
                (plot_x + self._x_to_px(px),
                 plot_y + self._y_to_px(py))
                for px, py in data_polygon
            ]
            canvas.polygon(points, fill=theme.color_of(color_name),
                           stroke="none", opacity=fill.opacity)

        # series
        for i, ser in enumerate(self.series):
            color_name = ser.color if ser.color != "auto" else theme.role_for_index(i)
            stroke = theme.color_of(color_name)
            sw = ser.width if ser.width is not None else theme.line
            pts = [(plot_x + self._x_to_px(vx),
                    plot_y + self._y_to_px(vy))
                   for vx, vy in ser.points]
            if len(pts) >= 2 and ser.show_line:
                d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}" + "".join(
                    f" L {px:.2f} {py:.2f}" for px, py in pts[1:])
                canvas.path(d, fill="none", stroke=stroke, stroke_width=sw,
                            dasharray=ser.dash)
            if ser.marker:
                radius = self._marker_radius(ser.marker_size, theme)
                for px, py in pts:
                    self._draw_marker(canvas, ser.marker, px, py, radius,
                                      stroke, theme, ser.marker_fill)

        # A fill owns relational labels because their values and positions are
        # derived from both series.  Authors provide only the formatter.
        for fill in self.fills:
            if fill.labels is None:
                continue
            lower = series_by_key[fill.lower]
            upper = series_by_key[fill.upper]
            lower_x = [float(px) for px, _ in lower.points]
            upper_x = [float(px) for px, _ in upper.points]
            lo = max(min(lower_x), min(upper_x))
            hi = min(max(lower_x), max(upper_x))
            xs = sorted({px for px in lower_x + upper_x if lo <= px <= hi})
            upper_i = self.series.index(upper)
            color_name = fill.color
            if color_name is None:
                color_name = (
                    upper.color
                    if upper.color != "auto"
                    else theme.role_for_index(upper_i)
                )
            for index, xv in enumerate(xs):
                low_value = self._interpolate(lower.points, xv)
                high_value = self._interpolate(upper.points, xv)
                label = str(fill.labels(xv, low_value, high_value))
                if not label:
                    continue
                px = plot_x + self._x_to_px(xv)
                value = low_value + (high_value - low_value) * 0.48
                py = plot_y + self._y_to_px(value)
                anchor = "middle"
                if index == 0:
                    anchor = "start"
                elif index == len(xs) - 1:
                    anchor = "end"
                canvas.text(
                    px,
                    py,
                    label,
                    size=theme.size_px("small"),
                    fill=theme.color_of(color_name),
                    weight="700",
                    anchor=anchor,
                )

        # annotations
        for index, delta in enumerate(self.deltas):
            source = series_by_key[delta.source]
            target = series_by_key[delta.target]
            source_value = self._interpolate(source.points, delta.x)
            target_value = self._interpolate(target.points, delta.x)
            data_x = plot_x + self._x_to_px(delta.x)
            edge_inset = theme.unit * 1.7
            arrow_x = max(
                plot_x + edge_inset,
                min(plot_x + self.width - edge_inset, data_x),
            )
            source_y = plot_y + self._y_to_px(source_value)
            target_y = plot_y + self._y_to_px(target_value)
            # When the endpoints draw markers and the arrow runs in the
            # marker's column, stop at the marker edge instead of its
            # centre so the arrowhead never occludes the data point.
            if abs(arrow_x - data_x) < 1e-6 and target_y != source_y:
                direction = 1.0 if target_y > source_y else -1.0

                def _marker_r(ser: Series) -> float:
                    if not ser.marker:
                        return 0.0
                    return self._marker_radius(ser.marker_size, theme)

                src_r = _marker_r(source)
                tgt_r = _marker_r(target)
                if abs(target_y - source_y) > src_r + tgt_r + theme.unit:
                    source_y += direction * src_r
                    target_y -= direction * (tgt_r + theme.hairline)
            delta_color = theme.color_of(delta.color)
            marker = canvas.define_arrow_marker(
                color=delta_color,
                stroke_width=theme.line,
                arrow_size=getattr(theme, "arrow_size", None),
                name_hint=f"series_delta_{index}",
            )
            canvas.line(
                arrow_x, source_y, arrow_x, target_y,
                stroke=delta_color,
                stroke_width=theme.line,
                marker_end=marker,
            )

            lines = delta.label.splitlines() or [delta.label]
            label_w = max(
                theme.text_width(line, delta.size, bold=True)
                for line in lines
            )
            gap = theme.unit * 0.75
            right_room = plot_x + self.width - arrow_x
            if right_room >= label_w + 2 * gap:
                label_x = arrow_x + gap
                anchor = "start"
            else:
                label_x = arrow_x - gap
                anchor = "end"
            line_h = theme.text_height(delta.size)
            centre_y = (source_y + target_y) / 2
            first_y = centre_y - len(lines) * line_h / 2 \
                + theme.size_px(delta.size) * 0.82
            for line_index, line in enumerate(lines):
                canvas.text(
                    label_x,
                    first_y + line_index * line_h,
                    line,
                    size=theme.size_px(delta.size),
                    fill=delta_color,
                    weight="700",
                    anchor=anchor,
                )

        for ann in self.annotations:
            ax = plot_x + self._x_to_px(ann.x)
            ay = plot_y + self._y_to_px(ann.y)
            if ann.dot:
                canvas.circle(ax, ay, 2.0, fill=axis_color, stroke="none")
            ann_line_h = theme.text_height(ann.size)
            for line_index, line in enumerate(
                    ann.text.splitlines() or [ann.text]):
                canvas.text(ax + ann.dx, ay + ann.dy + line_index * ann_line_h,
                            line,
                            size=theme.size_px(ann.size),
                            fill=theme.color_of(ann.color),
                            anchor=ann.anchor)

        # legend
        if self.legend:
            self._render_legend(
                canvas, plot_x, plot_y, L, T, R, B, theme,
            )

    def _render_legend(self, canvas: Canvas, plot_x: float, plot_y: float,
                       L: float, T: float, R: float, B: float,
                       theme: Theme) -> None:
        items = [(i, s) for i, s in enumerate(self.series) if s.label]
        if not items:
            return
        legend_size = "small"
        line_h = theme.text_height(legend_size)
        if self.legend in (
            "inside-top-left", "inside-top-right", "inside-bottom-right"
        ):
            pad = theme.unit * 0.7
            sample_w = theme.unit * 3.0
            text_w = max(theme.text_width(s.label, legend_size) for _, s in items)
            box_w = pad * 2 + sample_w + theme.unit + text_w
            box_h = pad * 2 + len(items) * line_h + max(0, len(items) - 1) * 2
            if self.legend == "inside-top-left":
                lx = plot_x + theme.unit
            else:
                lx = plot_x + self.width - box_w - theme.unit
            if self.legend in ("inside-top-left", "inside-top-right"):
                box_y = plot_y + theme.unit
            else:
                box_y = plot_y + self.height - box_h - theme.unit
            canvas.rect(
                lx,
                box_y,
                box_w,
                box_h,
                fill=theme.color_of("bg"),
                stroke=theme.color_of("border"),
                stroke_width=theme.hairline,
                rx=2,
                opacity=0.96,
            )
            ly = box_y + pad
            for i, s in items:
                color_name = s.color if s.color != "auto" else theme.role_for_index(i)
                stroke = theme.color_of(color_name)
                cy = ly + line_h * 0.5
                if s.show_line:
                    canvas.line(
                        lx + pad,
                        cy,
                        lx + pad + sample_w,
                        cy,
                        stroke=stroke,
                        stroke_width=s.width if s.width is not None else theme.line,
                        dasharray=s.dash,
                    )
                if s.marker:
                    self._draw_marker(
                        canvas,
                        s.marker,
                        lx + pad + sample_w / 2,
                        cy,
                        self._marker_radius(s.marker_size, theme),
                        stroke,
                        theme,
                        s.marker_fill,
                    )
                canvas.text(
                    lx + pad + sample_w + theme.unit,
                    ly + line_h * 0.75,
                    s.label,
                    size=theme.size_px(legend_size),
                    fill=theme.color_of("text"),
                )
                ly += line_h + 2
            return
        if self.legend == "right":
            lx = plot_x + self.width + 16.0
            ly = plot_y + 4.0
            for i, s in items:
                color_name = s.color if s.color != "auto" else theme.role_for_index(i)
                stroke = theme.color_of(color_name)
                if s.show_line:
                    canvas.line(lx, ly + line_h * 0.5, lx + 16,
                                ly + line_h * 0.5,
                                stroke=stroke, stroke_width=theme.line,
                                dasharray=s.dash)
                if s.marker:
                    self._draw_marker(
                        canvas, s.marker, lx + 8, ly + line_h * 0.5,
                        self._marker_radius(s.marker_size, theme), stroke,
                        theme, s.marker_fill)
                canvas.text(lx + 22, ly + line_h * 0.75, s.label,
                            size=theme.size_px(legend_size),
                            fill=theme.color_of("text"))
                ly += line_h + 2
        else:
            if self.legend == "top":
                ly = plot_y - T + 4
            else:
                ly = plot_y + self.height + B - line_h - 2
            lx = plot_x
            for i, s in items:
                color_name = s.color if s.color != "auto" else theme.role_for_index(i)
                stroke = theme.color_of(color_name)
                if s.show_line:
                    canvas.line(lx, ly + line_h * 0.5, lx + 16,
                                ly + line_h * 0.5,
                                stroke=stroke, stroke_width=theme.line,
                                dasharray=s.dash)
                if s.marker:
                    self._draw_marker(
                        canvas, s.marker, lx + 8, ly + line_h * 0.5,
                        self._marker_radius(s.marker_size, theme), stroke,
                        theme, s.marker_fill)
                canvas.text(lx + 22, ly + line_h * 0.75, s.label,
                            size=theme.size_px(legend_size),
                            fill=theme.color_of("text"))
                lx += 22 + theme.text_width(s.label, legend_size) + 20
