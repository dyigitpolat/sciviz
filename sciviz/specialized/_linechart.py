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

from ..auto.labelplacer import overlap_area
from ..core import BBox, Canvas, Element, Theme
from ..palette import ColorRef


@dataclass
class Series:
    """One line series.

    Parameters
    ----------
    points : list of ``(x, y)``
    label : str, optional
        Label shown in the legend (if any). ``None`` hides from legend.
    color : str or ColorRef
        Theme colour role, hex literal, or palette reference (e.g.
        ``Palette.red.faded()`` for a de-emphasized baseline series);
        defaults to "auto" which cycles through
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
    color: Union[str, ColorRef] = "auto"
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
    x_range, y_range : tuple (low, high), optional
        Axis ranges. Omit (``None``, the default) for automatic ranging:
        the axis is fitted snugly to the data and snapped outward to a
        "nice" tick step, so plots carry no dead whitespace and ticks
        land on round values. An explicit tuple is always honoured
        verbatim.
    width, height : float
        Plot area (excluding axis labels).
    x_label, y_label : str
    log_x, log_y : bool
    grid : bool
    annotations : list of :class:`Annotate`, optional
    legend : str or None
        Where to render the legend: ``"top"``, ``"bottom"``, ``"right"``,
        an inside corner (``"inside-top-left"``, ``"inside-top-right"``,
        ``"inside-bottom-left"``, ``"inside-bottom-right"``), or ``None``
        (default -- use an external :class:`Legend`). An inside corner is
        a *preference*, not a fixed position: if the legend box would
        cover data there, the chart relocates it to a clear corner, or,
        when the y range is automatic, keeps the corner and expands the
        range headroom just enough to clear the data. Legends never
        occlude series lines silently.
    """

    _PLOT_SIZES = {
        "sm": (240.0, 144.0),
        "md": (300.0, 180.0),
        "lg": (360.0, 210.0),
        "xl": (440.0, 260.0),
    }

    def __init__(self, series: Sequence[Union[Series, dict]], *,
                 x_range: Optional[Tuple[float, float]] = None,
                 y_range: Optional[Tuple[float, float]] = None,
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
            "inside-bottom-left",
            "inside-bottom-right",
        ):
            raise ValueError(
                "legend must be None, 'top', 'bottom', 'right', "
                "'inside-top-left', 'inside-top-right', "
                "'inside-bottom-left', or "
                f"'inside-bottom-right'; got {legend!r}"
            )
        self.legend = legend
        self._validate_relations()
        self._legend_rect: Optional[Tuple[float, float, float, float]] = None
        self._resolve_ranges()

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

    # ---- range resolution ------------------------------------------------

    @staticmethod
    def _nice_step(raw: float) -> float:
        """Round ``raw`` up to a 1/2/2.5/5 x 10^k tick step."""
        if raw <= 0:
            return 1.0
        mag = 10.0 ** _m.floor(_m.log10(raw))
        frac = raw / mag
        for nice in (1.0, 2.0, 2.5, 5.0, 10.0):
            if frac <= nice + 1e-9:
                return nice * mag
        return 10.0 * mag

    @classmethod
    def _nice_bounds(cls, lo: float, hi: float,
                     log: bool) -> Tuple[float, float, Optional[float]]:
        """Snap a data extent outward to nice bounds; return (lo, hi, step)."""
        if log:
            lo = 10.0 ** _m.floor(_m.log10(max(lo, 1e-12)))
            hi = 10.0 ** _m.ceil(_m.log10(max(hi, 1e-12)))
            if hi <= lo:
                hi = lo * 10.0
            return lo, hi, None
        if hi - lo < 1e-12:
            pad = max(abs(lo), 1.0) * 0.5
            lo, hi = lo - pad, hi + pad
        step = cls._nice_step((hi - lo) / 4.0)
        nlo = _m.floor(lo / step + 1e-9) * step
        nhi = _m.ceil(hi / step - 1e-9) * step
        if nhi <= nlo:
            nhi = nlo + step
        return nlo, nhi, step

    def _data_extent(self) -> Tuple[Optional[Tuple[float, float]],
                                    Optional[Tuple[float, float]]]:
        xs: List[float] = []
        ys: List[float] = []
        for s in self.series:
            for px, py in s.points:
                xs.append(float(px))
                ys.append(float(py))
        for ann in self.annotations:
            xs.append(float(ann.x))
            ys.append(float(ann.y))
        if not xs:
            return None, None
        return (min(xs), max(xs)), (min(ys), max(ys))

    def _resolve_ranges(self) -> None:
        """Fix the ranges used for projection this render.

        Explicit ``x_range``/``y_range`` pass through verbatim. ``None``
        (automatic) axes fit the data extent and snap outward to a nice
        tick step; the step is kept so auto ticks land on round values.
        """
        x_ext, y_ext = self._data_extent()
        self._x_step: Optional[float] = None
        self._y_step: Optional[float] = None
        if self.x_range is not None:
            self._xr: Tuple[float, float] = tuple(self.x_range)
        elif x_ext is None:
            self._xr = (0.0, 1.0)
        else:
            lo, hi, self._x_step = self._nice_bounds(*x_ext, self.log_x)
            self._xr = (lo, hi)
        if self.y_range is not None:
            self._yr: Tuple[float, float] = tuple(self.y_range)
        elif y_ext is None:
            self._yr = (0.0, 1.0)
        else:
            lo, hi, self._y_step = self._nice_bounds(*y_ext, self.log_y)
            self._yr = (lo, hi)

    # ---- projection helpers ---------------------------------------------

    def _x_to_px(self, v: float) -> float:
        x0, x1 = self._xr
        if self.log_x:
            v = _m.log10(max(v, 1e-12))
            x0 = _m.log10(max(x0, 1e-12))
            x1 = _m.log10(max(x1, 1e-12))
        return (v - x0) / (x1 - x0) * self.width

    def _y_to_px(self, v: float) -> float:
        y0, y1 = self._yr
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

    def _ticks(self, explicit, value_range, log: bool,
               step: Optional[float] = None) -> List[float]:
        if explicit == "auto":
            if step is not None and not log:
                # Ticks stay on the step grid; legend headroom expansion
                # may leave a range edge half a step off grid, so emit
                # only on-grid ticks inside the range.
                lo, hi = value_range
                start = _m.ceil(lo / step - 1e-9) * step
                count = max(0, int(_m.floor((hi - start) / step + 1e-9)))
                return [start + step * i for i in range(count + 1)]
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

    _TICK_GAP = 4.0            # axis -> tick-label gap

    def _axis_gap(self, theme: Theme) -> float:
        """Tick-label -> axis-title gap."""
        return theme.unit * 0.75

    def _y_tick_width(self, theme: Theme) -> float:
        """Measured width of the widest resolved y tick label."""
        y_ticks = self._ticks(self.y_ticks, self._yr, self.log_y,
                              self._y_step)
        return max((theme.text_width(
            self._tick_label(v, self.log_y, self.y_tick_format), "small")
            for v in y_ticks), default=0.0)

    def _pad(self, theme: Theme) -> Tuple[float, float, float, float]:
        """Return padding (left, top, right, bottom) around the plot area.

        The gutters are derived from the labels they must hold: the left
        pad is the measured width of the y tick labels plus the axis
        title band (when present), the bottom pad is the tick-label line
        plus the x title band. The plot area therefore claims every
        pixel the labels do not need, and axis titles sit a fixed small
        gap from the nearest tick label instead of a fixed distance from
        the axis. Resolves ranges and the inside legend first, so the
        gutters reflect the final ticks.
        """
        self._resolve_ranges()
        self._place_inside_legend(theme)
        tick_h = theme.text_height("small")
        title_h = theme.text_height("label")
        gap = self._axis_gap(theme)
        left = self._TICK_GAP + self._y_tick_width(theme) + (
            gap + title_h if self.y_label else 0.0) + 2.0
        bot = tick_h * 1.35 + (
            gap * 0.6 + title_h if self.x_label else 0.0)
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
        # _pad resolves ranges and the inside legend (which may expand an
        # automatic y range for headroom) before any geometry depends on
        # them, and derives the gutters from the resolved tick labels.
        L, T, R, B = self._pad(theme)
        plot_x = x + L
        plot_y = y + T

        grid_color = theme.color_of("grid")
        axis_color = theme.color_of("border_strong")
        text_col = theme.color_of("text")
        muted = theme.color_of("text_muted")

        # gridlines + ticks
        x_ticks = self._ticks(self.x_ticks, self._xr, self.log_x,
                              self._x_step)
        y_ticks = self._ticks(self.y_ticks, self._yr, self.log_y,
                              self._y_step)

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

        # axis titles sit one small gap beyond the tick labels they follow.
        title_h = theme.text_height("label")
        gap = self._axis_gap(theme)
        if self.x_label:
            canvas.text(plot_x + self.width / 2,
                        plot_y + self.height + tick_h * 1.35
                        + gap * 0.6 + title_h * 0.78,
                        self.x_label, size=theme.size_px("label"),
                        fill=text_col, anchor="middle")
        if self.y_label:
            # canvas.text (not raw SVG) so the rotated label's ink is
            # tracked -- otherwise auto-trim can crop the y-axis title.
            canvas.text(plot_x - self._TICK_GAP - self._y_tick_width(theme)
                        - gap - title_h / 2,
                        plot_y + self.height / 2,
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

    # ---- inside-legend placement ----------------------------------------

    _INSIDE_CORNERS = ("top-right", "top-left", "bottom-right", "bottom-left")

    def _legend_items(self) -> List[Tuple[int, Series]]:
        return [(i, s) for i, s in enumerate(self.series) if s.label]

    def _legend_font(self, theme: Theme) -> float:
        """Inside-legend font in px: slightly smaller than tick text.

        The legend competes with data for plot area, and an oversized
        box forces large headroom expansion when no corner is clear, so
        the inside legend runs compact by default.
        """
        return theme.size_px("small") * 0.85

    def _legend_box_size(self, theme: Theme) -> Optional[
            Tuple[float, float, float, float, float, float]]:
        """Return (box_w, box_h, pad, sample_w, line_h, font_px)."""
        items = self._legend_items()
        if not items:
            return None
        font = self._legend_font(theme)
        line_h = theme.text_height(font)
        pad = theme.unit * 0.6
        sample_w = theme.unit * 3.0
        text_w = max(theme.text_width(s.label, font) for _, s in items)
        box_w = pad * 2 + sample_w + theme.unit + text_w
        box_h = pad * 2 + len(items) * line_h + max(0, len(items) - 1) * 1.0
        return box_w, box_h, pad, sample_w, line_h, font

    def _corner_rect(self, corner: str, box_w: float, box_h: float,
                     theme: Theme) -> Tuple[float, float, float, float]:
        """Legend rect for a corner, relative to the plot origin."""
        u = theme.unit
        x0 = u if corner.endswith("left") else self.width - box_w - u
        y0 = u if corner.startswith("top") else self.height - box_h - u
        return (x0, y0, x0 + box_w, y0 + box_h)

    def _legend_obstacles(self, theme: Theme) -> Tuple[
            List[Tuple[float, float, float, float]],
            List[Tuple[float, float, float, float]],
            List[Tuple[float, float, float, float]]]:
        """Data ink in plot pixels, plus range-expansion constraints.

        Returns ``(rects, top_cons, bot_cons)``. ``rects`` are obstacle
        bboxes used to score legend corners. Long polyline segments are
        subdivided so a diagonal's bbox does not block corners the line
        never visits. Each constraint is ``(x0, x1, v, off)``: over the
        x-pixel span ``[x0, x1]`` the ink tied to data value ``v``
        reaches ``off`` pixels above (top) or below (bottom) that
        value's projection, which the headroom solver must clear.
        """
        rects: List[Tuple[float, float, float, float]] = []
        top_cons: List[Tuple[float, float, float, float]] = []
        bot_cons: List[Tuple[float, float, float, float]] = []
        y0, y1 = self._yr

        def inv_y(py: float) -> float:
            return y0 + (self.height - py) / self.height * (y1 - y0)

        for s in self.series:
            pts = [(self._x_to_px(float(px)), self._y_to_px(float(py)))
                   for px, py in s.points]
            r = (self._marker_radius(s.marker_size, theme)
                 if s.marker else 0.0)
            pad = max(r, (s.width if s.width is not None else theme.line)) + 2.0

            def add_ink(x0: float, py0: float, x1: float, py1: float) -> None:
                rects.append((min(x0, x1) - pad, min(py0, py1) - pad,
                              max(x0, x1) + pad, max(py0, py1) + pad))
                span = (min(x0, x1) - pad, max(x0, x1) + pad)
                top_cons.append((*span, inv_y(min(py0, py1)), pad))
                bot_cons.append((*span, inv_y(max(py0, py1)), pad))

            if s.show_line and len(pts) >= 2:
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    n = max(1, int(_m.ceil(_m.hypot(bx - ax, by - ay) / 10.0)))
                    for i in range(n):
                        t0, t1 = i / n, (i + 1) / n
                        add_ink(ax + (bx - ax) * t0, ay + (by - ay) * t0,
                                ax + (bx - ax) * t1, ay + (by - ay) * t1)
            for px, py in pts:
                add_ink(px, py, px, py)

        for ann in self.annotations:
            ax = self._x_to_px(float(ann.x))
            ay = self._y_to_px(float(ann.y))
            lines = ann.text.splitlines() or [ann.text]
            w = max(theme.text_width(line, ann.size) for line in lines)
            h = theme.text_height(ann.size) * len(lines)
            x0 = ax + ann.dx
            if ann.anchor == "middle":
                x0 -= w / 2
            elif ann.anchor == "end":
                x0 -= w
            ry0 = ay + ann.dy - theme.text_height(ann.size) * 0.75
            rects.append((x0, ry0, x0 + w, ry0 + h))
            top_cons.append((x0, x0 + w, inv_y(ay), ay - ry0))
            bot_cons.append((x0, x0 + w, inv_y(ay), (ry0 + h) - ay))
            if ann.dot:
                rects.append((ax - 3.0, ay - 3.0, ax + 3.0, ay + 3.0))
        return rects, top_cons, bot_cons

    def _expand_y_for_corner(self, corner: str, rect, cons, margin: float
                             ) -> bool:
        """Grow the automatic y range so ``rect`` clears the data under it.

        Solves in data space: for a top corner, the range top ``y1`` rises
        until every constrained value projects below the legend bottom
        plus ``margin`` (symmetrically, the bottom drops for a bottom
        corner). The result snaps outward to the auto tick step. Returns
        False when no finite expansion can clear the corner.
        """
        y0, y1 = self._yr
        H = self.height
        x0, _, x1, _ = rect
        active = [(v, off) for (cx0, cx1, v, off) in cons
                  if cx1 >= x0 - margin and cx0 <= x1 + margin]
        if not active:
            return True
        if corner.startswith("top"):
            B = rect[3] + margin          # legend bottom edge + clearance
            needed = y1
            for v, off in active:
                free = H - B - off
                if free <= 1.0:
                    return False
                if v <= y0:
                    continue
                needed = max(needed, y0 + (v - y0) * H / free)
            if needed > y1 + (y1 - y0) * 4.0:
                return False
            step = self._y_step or self._nice_step((needed - y0) / 4.0)
            # Snap the expansion outward on the half-step grid: ticks stay
            # nice while the range grows no more than necessary.
            half_step = step / 2.0
            self._yr = (y0, y0 + _m.ceil((needed - y0) / half_step - 1e-9)
                        * half_step)
        else:
            T = rect[1] - margin          # legend top edge - clearance
            if T <= 1.0:
                return False
            needed = y0
            for v, off in active:
                t_eff = T - off
                if t_eff <= 1.0:
                    return False
                q_eff = (H - t_eff) / H
                if v >= y1:
                    continue
                needed = min(needed, (v - q_eff * y1) / (1.0 - q_eff))
            if needed < y0 - (y1 - y0) * 4.0:
                return False
            step = self._y_step or self._nice_step((y1 - needed) / 4.0)
            half_step = step / 2.0
            self._yr = (y1 - _m.ceil((y1 - needed) / half_step - 1e-9)
                        * half_step, y1)
        return True

    def _place_inside_legend(self, theme: Theme) -> None:
        """Settle the inside legend so it never covers data ink.

        Cascade: keep the author's corner when it is clear; otherwise
        relocate to the first clear corner; otherwise, when the y range
        is automatic, keep the author's corner and expand headroom just
        enough to clear it; as a last resort take the least-covering
        corner. Explicit ranges are never mutated.
        """
        self._legend_rect = None
        if not (self.legend and self.legend.startswith("inside")):
            return
        size = self._legend_box_size(theme)
        if size is None:
            return
        box_w, box_h, *_ = size
        preferred = self.legend[len("inside-"):]
        order = [preferred] + [c for c in self._INSIDE_CORNERS
                               if c != preferred]
        rects = {c: self._corner_rect(c, box_w, box_h, theme) for c in order}
        obstacles, top_cons, bot_cons = self._legend_obstacles(theme)
        scores = {c: sum(overlap_area(rects[c], ob) for ob in obstacles)
                  for c in order}
        margin = theme.unit * 0.75
        if scores[preferred] <= 1e-9:
            self._legend_rect = rects[preferred]
            return
        for c in order:
            if scores[c] <= 1e-9:
                self._legend_rect = rects[c]
                return
        y_is_auto = self.y_range is None and not self.log_y
        if y_is_auto:
            cons = top_cons if preferred.startswith("top") else bot_cons
            if self._expand_y_for_corner(preferred, rects[preferred],
                                         cons, margin):
                self._legend_rect = rects[preferred]
                return
        best = min(order, key=lambda c: scores[c])
        self._legend_rect = rects[best]

    def _render_legend(self, canvas: Canvas, plot_x: float, plot_y: float,
                       L: float, T: float, R: float, B: float,
                       theme: Theme) -> None:
        items = self._legend_items()
        if not items:
            return
        legend_size = "small"
        line_h = theme.text_height(legend_size)
        if self.legend.startswith("inside"):
            size = self._legend_box_size(theme)
            assert size is not None
            box_w, box_h, pad, sample_w, line_h, font = size
            if self._legend_rect is None:
                # render() resolves placement; fall back for direct calls.
                self._place_inside_legend(theme)
            rx0, ry0, _, _ = self._legend_rect
            lx = plot_x + rx0
            box_y = plot_y + ry0
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
                    size=font,
                    fill=theme.color_of("text"),
                )
                ly += line_h + 1.0
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
