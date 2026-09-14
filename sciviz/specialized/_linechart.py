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
from ..elements._marker import draw_marker, marker_radius
from ..palette import ColorRef
from ._clip import clamp_rect, clip_polygon, clip_polyline, contains


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
    axis : str
        Which y axis this series is measured against: ``"left"``
        (default) or ``"right"``. Put a series on the right axis when it
        carries a *different quantity* from the left ones (a hazard next
        to a transfer curve, a cost next to an accuracy). The chart then
        grows a secondary axis with its own range, ticks, and title;
        see :class:`LineChart`.
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
    axis: str = "left"


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
    y2_range : tuple (low, high), optional
        Range of the secondary (right) y axis, which exists whenever any
        series sets ``axis="right"``. ``None`` (default) auto-fits it to
        the right-axis series exactly as the left axis auto-fits. The
        secondary axis is always linear, carries its own ticks and
        title, and never draws gridlines, so the two quantities stay
        visually distinguishable.
    y2_label : str
        Title of the secondary axis.
    y2_ticks, y2_tick_format
        As ``y_ticks`` / ``y_tick_format``, for the secondary axis.
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
                 y_tick_format: Union[str, Callable[[float], str]] = "g",
                 y2_range: Optional[Tuple[float, float]] = None,
                 y2_label: str = "",
                 y2_ticks: Union[str, Sequence[float]] = "auto",
                 y2_tick_format: Union[str, Callable[[float], str]] = "g"):
        self.series = [self._coerce_series(s) for s in series]
        self.x_range = x_range
        self.y_range = y_range
        self.y2_range = y2_range
        self.y2_label = y2_label
        self.y2_ticks = y2_ticks
        self.y2_tick_format = y2_tick_format
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
        axis_of = {k: s.axis for k, s in zip(keys, self.series)}
        for series in self.series:
            if series.axis not in ("left", "right"):
                raise ValueError(
                    f"Series.axis must be 'left' or 'right'; got {series.axis!r}")
        for fill in self.fills:
            if fill.lower not in known or fill.upper not in known:
                raise ValueError(
                    f"FillBetween references unknown series: "
                    f"{fill.lower!r}, {fill.upper!r}")
            if axis_of[fill.lower] != axis_of[fill.upper]:
                raise ValueError(
                    "FillBetween spans two axes; the area between series on "
                    "different y axes has no meaning")
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
            if axis_of[delta.source] != axis_of[delta.target]:
                raise ValueError(
                    "SeriesDelta spans two axes; a difference between series "
                    "on different y axes has no meaning")
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

    # ---- axis membership -------------------------------------------------

    def has_secondary_axis(self) -> bool:
        """True when any series is measured against the right axis."""
        return any(s.axis == "right" for s in self.series)

    def _data_extent(self) -> Tuple[Optional[Tuple[float, float]],
                                    Optional[Tuple[float, float]],
                                    Optional[Tuple[float, float]]]:
        """Return ``(x, y_left, y_right)`` data extents (None when empty).

        Annotations are authored in left-axis coordinates and extend the
        left extent only.
        """
        xs: List[float] = []
        ys: List[float] = []
        ys2: List[float] = []
        for s in self.series:
            target = ys2 if s.axis == "right" else ys
            for px, py in s.points:
                xs.append(float(px))
                target.append(float(py))
        for ann in self.annotations:
            xs.append(float(ann.x))
            ys.append(float(ann.y))
        return (
            (min(xs), max(xs)) if xs else None,
            (min(ys), max(ys)) if ys else None,
            (min(ys2), max(ys2)) if ys2 else None,
        )

    def _resolve_ranges(self) -> None:
        """Fix the ranges used for projection this render.

        Explicit ``x_range``/``y_range``/``y2_range`` pass through
        verbatim. ``None`` (automatic) axes fit their own data extent and
        snap outward to a nice tick step; the step is kept so auto ticks
        land on round values. The secondary axis resolves independently,
        which is the point of having it.
        """
        x_ext, y_ext, y2_ext = self._data_extent()
        self._x_step: Optional[float] = None
        self._y_step: Optional[float] = None
        self._y2_step: Optional[float] = None
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
        if not self.has_secondary_axis():
            self._yr2: Optional[Tuple[float, float]] = None
        elif self.y2_range is not None:
            self._yr2 = tuple(self.y2_range)
        elif y2_ext is None:
            self._yr2 = (0.0, 1.0)
        else:
            lo, hi, self._y2_step = self._nice_bounds(*y2_ext, False)
            self._yr2 = (lo, hi)

    # ---- projection helpers ---------------------------------------------

    def _x_to_px(self, v: float) -> float:
        x0, x1 = self._xr
        if self.log_x:
            v = _m.log10(max(v, 1e-12))
            x0 = _m.log10(max(x0, 1e-12))
            x1 = _m.log10(max(x1, 1e-12))
        return (v - x0) / (x1 - x0) * self.width

    def _y_to_px(self, v: float, right: bool = False) -> float:
        if right and self._yr2 is not None:
            y0, y1 = self._yr2
            return self.height - (v - y0) / (y1 - y0) * self.height
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

    # The marker vocabulary is shared with Scatter, Slopegraph, and the
    # standalone Marker element a legend pairs with a label, so a legend
    # glyph can never drift from the mark the chart plots.
    _marker_radius = staticmethod(marker_radius)

    def _draw_marker(self, canvas: Canvas, marker: str, px: float, py: float,
                     radius: float, color: str, theme: Theme,
                     fill_mode: str = "solid") -> None:
        draw_marker(canvas, marker, px, py, radius, color, theme, fill_mode)

    # ---- layout ----------------------------------------------------------

    _TICK_GAP = 4.0            # axis -> tick-label gap

    def _axis_gap(self, theme: Theme) -> float:
        """Tick-label -> axis-title gap."""
        return theme.unit * 0.75

    def _y_axis_ticks(self, right: bool = False) -> List[float]:
        if right:
            if self._yr2 is None:
                return []
            return self._ticks(self.y2_ticks, self._yr2, False, self._y2_step)
        return self._ticks(self.y_ticks, self._yr, self.log_y, self._y_step)

    def _y_tick_width(self, theme: Theme, right: bool = False) -> float:
        """Measured width of the widest resolved y tick label."""
        log = False if right else self.log_y
        fmt = self.y2_tick_format if right else self.y_tick_format
        return max((theme.text_width(self._tick_label(v, log, fmt), "small")
                    for v in self._y_axis_ticks(right)), default=0.0)

    _TITLE_SIZE = "label"
    _X_TITLE_BASELINE = 0.78   # first x-title baseline, in title line-heights

    def _axis_title_lines(self, label: str, theme: Theme,
                          budget: float) -> List[str]:
        """Wrap one axis title to the span it is centred over."""
        return theme.wrap_lines(label, self._TITLE_SIZE, max(budget, 1.0))

    @staticmethod
    def _lines_overflow(lines: List[str], theme: Theme, size: str,
                        span: float, near: float, far: float) -> float:
        """Extra room one side needs so a centred label block stays inside.

        ``lines`` are centred over ``span`` with ``near``/``far`` already
        reserved on the two sides; the return value is how much more the
        block's half-width demands than the smaller reservation offers.
        """
        if not lines:
            return 0.0
        widest = max(theme.text_width(line, size) for line in lines)
        return max(0.0, widest / 2.0 - (span / 2.0 + min(near, far)))

    # The top and right gutters exist only to hold ink that overhangs the
    # plot rectangle, so their floor is the axis stroke's own half width
    # plus a hairline of relief.
    _EDGE_FLOOR = 1.5

    def _edge_overhang(self, theme: Theme) -> Tuple[float, float]:
        """How far ink reaches above and to the right of the plot area.

        The left and bottom gutters hold the tick labels and axis titles
        that live there. Nothing lives above or right of the plot, so
        those two gutters only have to hold what the chart itself pushes
        past the edge: a marker centred on the top row, a stroke on the
        last x value, the topmost y tick label (centred on its tick), the
        right-most x tick label (also centred on its tick), and any
        annotation pinned near a corner. Reserving a flat constant
        instead costs a short paper figure a fifth of its plot height,
        which is exactly the height such a figure has least of.

        Ranges must already be resolved; :meth:`_pad` does that first.
        """
        top = self._EDGE_FLOOR
        right = self._EDGE_FLOOR
        window = (0.0, 0.0, self.width, self.height)

        # Only ink that survives clipping counts: a curve leaving the
        # declared window is cut at the edge, so it can overhang by no
        # more than its own stroke.
        for series in self.series:
            on_right = series.axis == "right"
            radius = (self._marker_radius(series.marker_size, theme)
                      if series.marker else 0.0)
            stroke = (series.width if series.width is not None
                      else theme.line) / 2.0
            projected = [(self._x_to_px(float(vx)),
                          self._y_to_px(float(vy), on_right))
                         for vx, vy in series.points]
            drawn: List[Tuple[Tuple[float, float], float]] = []
            if series.show_line and len(projected) >= 2:
                for run in clip_polyline(projected, window):
                    drawn.extend((point, stroke) for point in run)
            if series.marker:
                drawn.extend((point, radius) for point in projected
                             if contains(window, point))
            for (px, py), reach in drawn:
                top = max(top, reach - py)
                right = max(right, px + reach - self.width)

        # Tick labels: y labels are centred on their tick, x labels on
        # theirs, so a tick at an edge spills half a line past it.
        tick_px = theme.size_px("small")
        ascent, _descent = theme.text_ink_extents("small")
        for on_right in (False, True):
            for value in self._y_axis_ticks(right=on_right):
                py = self._y_to_px(value, right=on_right)
                top = max(top, ascent - tick_px * 0.33 - py)
        for value in self._ticks(self.x_ticks, self._xr, self.log_x,
                                 self._x_step):
            px = self._x_to_px(value)
            label = self._tick_label(value, self.log_x, self.x_tick_format)
            half = theme.text_width(label, "small") / 2.0
            right = max(right, px + half - self.width)

        for ann in self.annotations:
            lines = ann.text.splitlines() or [ann.text]
            width = max(theme.text_width(line, ann.size) for line in lines)
            x0 = self._x_to_px(float(ann.x)) + ann.dx
            if ann.anchor == "middle":
                x0 -= width / 2.0
            elif ann.anchor == "end":
                x0 -= width
            ink_top = (self._y_to_px(float(ann.y)) + ann.dy
                       - theme.text_height(ann.size) * 0.75)
            top = max(top, -ink_top)
            right = max(right, x0 + width - self.width)

        return top, right

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

        Axis titles are prose, so they wrap to the span they are centred
        over (the plot plus its own margins) instead of spilling out of
        the chart's measured box: a long title claims another title line
        in its gutter rather than silently drawing over a neighbour. A
        single word too wide to wrap grows the box symmetrically, so the
        bbox always contains every glyph :meth:`render` draws.
        """
        self._resolve_ranges()
        self._place_inside_legend(theme)
        tick_h = theme.text_height("small")
        title_h = theme.text_height(self._TITLE_SIZE)
        gap = self._axis_gap(theme)
        top, right = self._edge_overhang(theme)
        if self.legend == "top":
            top += theme.text_height("small") + 6
        if self.legend == "bottom":
            extra_bottom_legend = theme.text_height("small") + 6
        else:
            extra_bottom_legend = 0.0
        if self.legend == "right":
            right += 92.0

        # A rotated title line inks `ascent` to one side of its anchor and
        # `descent` to the other, which is wider than the line's layout
        # height; reserve the ink, not the layout box.
        ascent, descent = theme.text_ink_extents(self._TITLE_SIZE)
        y_lines = self._axis_title_lines(
            self.y_label, theme, self.height + 2.0 * top) if self.y_label else []
        left = self._TICK_GAP + self._y_tick_width(theme) + (
            gap + (len(y_lines) - 1) * title_h + ascent + descent
            if y_lines else 0.0) + 2.0
        bot = tick_h * 1.35 + extra_bottom_legend

        # The secondary axis claims a mirrored gutter on the right.
        y2_lines = self._axis_title_lines(
            self.y2_label, theme, self.height + 2.0 * top) if (
                self.y2_label and self.has_secondary_axis()) else []
        if self.has_secondary_axis():
            right += self._TICK_GAP + self._y_tick_width(theme, right=True) + (
                gap + (len(y2_lines) - 1) * title_h + ascent + descent
                if y2_lines else 0.0)

        x_lines = self._axis_title_lines(
            self.x_label, theme, self.width + 2.0 * right) if self.x_label else []
        if x_lines:
            bot += (gap * 0.6 + title_h * self._X_TITLE_BASELINE
                    + (len(x_lines) - 1) * title_h + descent)

        # A word wider than its wrap budget still has to fit in the box.
        spill_x = self._lines_overflow(
            x_lines, theme, self._TITLE_SIZE, self.width, left, right)
        left += spill_x
        right += spill_x
        spill_y = max(
            self._lines_overflow(
                y_lines, theme, self._TITLE_SIZE, self.height, top, bot),
            self._lines_overflow(
                y2_lines, theme, self._TITLE_SIZE, self.height, top, bot),
        )
        top += spill_y
        bot += spill_y
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
        if self.has_secondary_axis():
            canvas.line(plot_x + self.width, plot_y,
                        plot_x + self.width, plot_y + self.height,
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
            canvas.text(plot_x - self._TICK_GAP,
                        py + tick_px * 0.33,
                        label, size=tick_px,
                        fill=muted, anchor="end")
        for yv in self._y_axis_ticks(right=True):
            py = plot_y + self._y_to_px(yv, right=True)
            label = self._tick_label(yv, False, self.y2_tick_format)
            canvas.text(plot_x + self.width + self._TICK_GAP,
                        py + tick_px * 0.33,
                        label, size=tick_px,
                        fill=muted, anchor="start")

        # axis titles sit one small gap beyond the tick labels they follow,
        # wrapped by _pad to the span they are centred over.
        title_h = theme.text_height(self._TITLE_SIZE)
        title_px = theme.size_px(self._TITLE_SIZE)
        gap = self._axis_gap(theme)
        _ascent, descent = theme.text_ink_extents(self._TITLE_SIZE)
        if self.x_label:
            x_lines = self._axis_title_lines(
                self.x_label, theme, self.width + 2.0 * R)
            base = (plot_y + self.height + tick_h * 1.35
                    + gap * 0.6 + title_h * self._X_TITLE_BASELINE)
            for row, line in enumerate(x_lines):
                canvas.text(plot_x + self.width / 2, base + row * title_h,
                            line, size=title_px,
                            fill=text_col, anchor="middle")
        if self.y_label:
            # canvas.text (not raw SVG) so the rotated label's ink is
            # tracked -- otherwise auto-trim can crop the y-axis title.
            y_lines = self._axis_title_lines(
                self.y_label, theme, self.height + 2.0 * T)
            inner = (plot_x - self._TICK_GAP - self._y_tick_width(theme)
                     - gap - descent)
            for row, line in enumerate(y_lines):
                canvas.text(inner - (len(y_lines) - 1 - row) * title_h,
                            plot_y + self.height / 2,
                            line, size=title_px,
                            fill=text_col, anchor="middle", rotate=-90)
        if self.y2_label and self.has_secondary_axis():
            y2_lines = self._axis_title_lines(
                self.y2_label, theme, self.height + 2.0 * T)
            inner = (plot_x + self.width + self._TICK_GAP
                     + self._y_tick_width(theme, right=True) + gap + descent)
            for row, line in enumerate(y2_lines):
                canvas.text(inner + (len(y2_lines) - 1 - row) * title_h,
                            plot_y + self.height / 2,
                            line, size=title_px,
                            fill=text_col, anchor="middle", rotate=90)

        # relational fills are painted beneath all line work.
        series_by_key = {
            self._series_key(series, i): series
            for i, series in enumerate(self.series)
        }
        # The axis range is the window the figure declares, so every piece
        # of series geometry is clipped to the plot rectangle before it is
        # drawn; see sciviz.specialized._clip. With an automatic range the
        # rectangle already holds the data and this changes nothing.
        window = (plot_x, plot_y, plot_x + self.width, plot_y + self.height)

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
            fill_right = upper.axis == "right"
            points = clip_polygon([
                (plot_x + self._x_to_px(px),
                 plot_y + self._y_to_px(py, fill_right))
                for px, py in data_polygon
            ], window)
            if len(points) < 3:
                continue
            canvas.polygon(points, fill=theme.color_of(color_name),
                           stroke="none", opacity=fill.opacity)

        # series
        for i, ser in enumerate(self.series):
            color_name = ser.color if ser.color != "auto" else theme.role_for_index(i)
            stroke = theme.color_of(color_name)
            sw = ser.width if ser.width is not None else theme.line
            right = ser.axis == "right"
            pts = [(plot_x + self._x_to_px(vx),
                    plot_y + self._y_to_px(vy, right))
                   for vx, vy in ser.points]
            if len(pts) >= 2 and ser.show_line:
                for run in clip_polyline(pts, window):
                    d = f"M {run[0][0]:.2f} {run[0][1]:.2f}" + "".join(
                        f" L {px:.2f} {py:.2f}" for px, py in run[1:])
                    canvas.path(d, fill="none", stroke=stroke,
                                stroke_width=sw, dasharray=ser.dash)
            if ser.marker:
                radius = self._marker_radius(ser.marker_size, theme)
                for px, py in pts:
                    if not contains(window, (px, py)):
                        continue
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
                py = plot_y + self._y_to_px(value, upper.axis == "right")
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
            delta_right = series_by_key[delta.target].axis == "right"
            source_y = plot_y + self._y_to_px(source_value, delta_right)
            target_y = plot_y + self._y_to_px(target_value, delta_right)
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
        """Inside-legend font in px: one ladder step under tick text.

        The legend competes with data for plot area, and an oversized
        box forces large headroom expansion when no corner is clear, so
        the inside legend runs compact by default. It steps down the
        theme's own size ladder rather than scaling tick text by a
        factor: an off-ladder size is the one text a figure can carry
        below the legibility floor without any token being set there.
        """
        return min(theme.size_px("small"), theme.size_px("micro"))

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

        Returns ``(rects, left_cons, right_cons)``. ``rects`` are obstacle
        bboxes used to score legend corners. Long polyline segments are
        subdivided so a diagonal's bbox does not block corners the line
        never visits. Each ``*_cons`` is a ``(top, bot)`` pair of
        constraint lists for that y axis, since only its own axis's
        range can move ink off a corner. Each constraint is
        ``(x0, x1, v, off)``: over the x-pixel span ``[x0, x1]`` the ink
        tied to data value ``v`` reaches ``off`` pixels above (top) or
        below (bottom) that value's projection, which the headroom
        solver must clear.
        """
        rects: List[Tuple[float, float, float, float]] = []
        cons = {"left": ([], []), "right": ([], [])}

        def inv_y(py: float, axis: str) -> float:
            y0, y1 = (self._yr2 if axis == "right" and self._yr2 is not None
                      else self._yr)
            return y0 + (self.height - py) / self.height * (y1 - y0)

        for s in self.series:
            right = s.axis == "right"
            top_cons, bot_cons = cons[s.axis]
            pts = [(self._x_to_px(float(px)), self._y_to_px(float(py), right))
                   for px, py in s.points]
            r = (self._marker_radius(s.marker_size, theme)
                 if s.marker else 0.0)
            pad = max(r, (s.width if s.width is not None else theme.line)) + 2.0

            def add_ink(x0: float, py0: float, x1: float, py1: float,
                        axis: str = s.axis, top_cons=top_cons,
                        bot_cons=bot_cons, pad: float = pad) -> None:
                rects.append((min(x0, x1) - pad, min(py0, py1) - pad,
                              max(x0, x1) + pad, max(py0, py1) + pad))
                span = (min(x0, x1) - pad, max(x0, x1) + pad)
                top_cons.append((*span, inv_y(min(py0, py1), axis), pad))
                bot_cons.append((*span, inv_y(max(py0, py1), axis), pad))

            if s.show_line and len(pts) >= 2:
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    n = max(1, int(_m.ceil(_m.hypot(bx - ax, by - ay) / 10.0)))
                    for i in range(n):
                        t0, t1 = i / n, (i + 1) / n
                        add_ink(ax + (bx - ax) * t0, ay + (by - ay) * t0,
                                ax + (bx - ax) * t1, ay + (by - ay) * t1)
            for px, py in pts:
                add_ink(px, py, px, py)

        top_cons, bot_cons = cons["left"]
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
            top_cons.append((x0, x0 + w, inv_y(ay, "left"), ay - ry0))
            bot_cons.append((x0, x0 + w, inv_y(ay, "left"), (ry0 + h) - ay))
            if ann.dot:
                rects.append((ax - 3.0, ay - 3.0, ax + 3.0, ay + 3.0))
        # render() clips ink to the plot rectangle, so ink the window cuts
        # away must not block a legend corner either.
        window = (0.0, 0.0, self.width, self.height)
        on_plot = [clamp_rect(rect, window) for rect in rects]
        return ([rect for rect in on_plot if rect is not None],
                cons["left"], cons["right"])

    def _expand_y_for_corner(self, corner: str, rect, cons, margin: float,
                             right: bool = False) -> bool:
        """Grow one automatic y range so ``rect`` clears the data under it.

        Solves in data space: for a top corner, the range top ``y1`` rises
        until every constrained value projects below the legend bottom
        plus ``margin`` (symmetrically, the bottom drops for a bottom
        corner). The result snaps outward to the auto tick step. Only the
        named axis moves, and only when it is automatic: an axis with an
        explicit range is never mutated, so it reports failure instead
        (unless it has no ink under the corner at all). Returns False
        when no finite expansion can clear the corner.
        """
        x0, _, x1, _ = rect
        active = [(v, off) for (cx0, cx1, v, off) in cons
                  if cx1 >= x0 - margin and cx0 <= x1 + margin]
        if not active:
            return True                       # this axis inks nothing here
        explicit = (self.y2_range if right else self.y_range) is not None
        if explicit or (self.log_y and not right):
            return False
        y0, y1 = self._yr2 if right else self._yr
        H = self.height
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
            step = ((self._y2_step if right else self._y_step)
                    or self._nice_step((needed - y0) / 4.0))
            # Snap the expansion outward on the half-step grid: ticks stay
            # nice while the range grows no more than necessary.
            half_step = step / 2.0
            grown = (y0, y0 + _m.ceil((needed - y0) / half_step - 1e-9)
                     * half_step)
            if right:
                self._yr2 = grown
            else:
                self._yr = grown
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
            step = ((self._y2_step if right else self._y_step)
                    or self._nice_step((y1 - needed) / 4.0))
            half_step = step / 2.0
            grown = (y1 - _m.ceil((y1 - needed) / half_step - 1e-9)
                     * half_step, y1)
            if right:
                self._yr2 = grown
            else:
                self._yr = grown
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
        obstacles, left_cons, right_cons = self._legend_obstacles(theme)
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
        # Every axis with ink under the corner must be able to move it;
        # each clears its own series, so they expand independently.
        side = 0 if preferred.startswith("top") else 1
        before = (self._yr, self._yr2)
        if all(self._expand_y_for_corner(preferred, rects[preferred],
                                         cons[side], margin, right=is_right)
               for cons, is_right in ((left_cons, False),
                                      (right_cons, True))):
            self._legend_rect = rects[preferred]
            return
        self._yr, self._yr2 = before          # partial expansion is not a fix
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
