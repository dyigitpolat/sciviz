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
from typing import List, Optional, Sequence, Tuple, Union

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
    """

    points: Sequence[Tuple[float, float]]
    label: Optional[str] = None
    color: str = "auto"
    dash: Optional[str] = None
    width: Optional[float] = None


@dataclass
class Annotate:
    """A single inline annotation pinned to a data coordinate.

    Parameters
    ----------
    x, y : float
        Data-space position of the anchor.
    text : str
        Label.
    dx, dy : float
        Pixel offset of the text from the anchor (to avoid overlap).
    color : str
        Text color; default "muted".
    size : str
        Text size token; default "small".
    """

    x: float
    y: float
    text: str
    dx: float = 8.0
    dy: float = -10.0
    color: str = "muted"
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

    def __init__(self, series: Sequence[Union[Series, dict]], *,
                 x_range: Tuple[float, float] = (0.0, 1.0),
                 y_range: Tuple[float, float] = (0.0, 1.0),
                 width: float = 300.0,
                 height: float = 180.0,
                 x_label: str = "",
                 y_label: str = "",
                 log_x: bool = False,
                 log_y: bool = False,
                 grid: bool = True,
                 annotations: Optional[Sequence[Annotate]] = None,
                 legend: Optional[str] = None):
        self.series = [self._coerce_series(s) for s in series]
        self.x_range = x_range
        self.y_range = y_range
        self.width = float(width)
        self.height = float(height)
        self.x_label = x_label
        self.y_label = y_label
        self.log_x = log_x
        self.log_y = log_y
        self.grid = grid
        self.annotations = list(annotations) if annotations else []
        if legend not in (None, "top", "bottom", "right"):
            raise ValueError(
                f"legend must be None, 'top', 'bottom', or 'right'; got {legend!r}")
        self.legend = legend

    @staticmethod
    def _coerce_series(s) -> Series:
        if isinstance(s, Series):
            return s
        if isinstance(s, dict):
            return Series(**s)
        raise TypeError(
            f"LineChart series must be Series or dict; got {type(s)}")

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

    # ---- layout ----------------------------------------------------------

    def _pad(self, theme: Theme) -> Tuple[float, float, float, float]:
        """Return padding (left, top, right, bottom) around the plot area."""
        left = 42.0 + (theme.text_height("small") + 4 if self.y_label else 0)
        bot = theme.text_height("small") * 2.3 + (
            theme.text_height("small") + 4 if self.x_label else 0)
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
        x_ticks = self._axis_ticks(*self.x_range, self.log_x)
        y_ticks = self._axis_ticks(*self.y_range, self.log_y)

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
        for xv in x_ticks:
            px = plot_x + self._x_to_px(xv)
            label = self._fmt_tick(xv, self.log_x)
            canvas.text(px, plot_y + self.height + theme.text_height("small"),
                        label, size=theme.size_px("small"),
                        fill=muted, anchor="middle")
        for yv in y_ticks:
            py = plot_y + self._y_to_px(yv)
            label = self._fmt_tick(yv, self.log_y)
            canvas.text(plot_x - 4.0,
                        py + theme.size_px("small") * 0.33,
                        label, size=theme.size_px("small"),
                        fill=muted, anchor="end")

        # axis labels
        if self.x_label:
            canvas.text(plot_x + self.width / 2,
                        plot_y + self.height + theme.text_height("small") * 2.2,
                        self.x_label, size=theme.size_px("small"),
                        fill=text_col, anchor="middle")
        if self.y_label:
            cx = plot_x - 36.0
            cy = plot_y + self.height / 2
            canvas.raw(
                f'<text x="{cx:.2f}" y="{cy:.2f}" '
                f'font-size="{theme.size_px("small"):.2f}" '
                f'fill="{text_col}" text-anchor="middle" '
                f'transform="rotate(-90 {cx:.2f} {cy:.2f})">'
                f'{self.y_label}</text>'
            )

        # series
        for i, ser in enumerate(self.series):
            color_name = ser.color if ser.color != "auto" else theme.role_for_index(i)
            stroke = theme.color_of(color_name)
            sw = ser.width if ser.width is not None else theme.line
            pts = [(plot_x + self._x_to_px(vx),
                    plot_y + self._y_to_px(vy))
                   for vx, vy in ser.points]
            if len(pts) >= 2:
                d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}" + "".join(
                    f" L {px:.2f} {py:.2f}" for px, py in pts[1:])
                canvas.path(d, fill="none", stroke=stroke, stroke_width=sw,
                            dasharray=ser.dash)

        # annotations
        for ann in self.annotations:
            ax = plot_x + self._x_to_px(ann.x)
            ay = plot_y + self._y_to_px(ann.y)
            canvas.circle(ax, ay, 2.0, fill=axis_color, stroke="none")
            canvas.text(ax + ann.dx, ay + ann.dy, ann.text,
                        size=theme.size_px(ann.size),
                        fill=theme.color_of(ann.color))

        # legend
        if self.legend:
            self._render_legend(canvas, plot_x, plot_y, L, T, R, B, theme)

    def _render_legend(self, canvas: Canvas, plot_x: float, plot_y: float,
                       L: float, T: float, R: float, B: float, theme: Theme) -> None:
        items = [(i, s) for i, s in enumerate(self.series) if s.label]
        if not items:
            return
        line_h = theme.text_height("small")
        if self.legend == "right":
            lx = plot_x + self.width + 16.0
            ly = plot_y + 4.0
            for i, s in items:
                color_name = s.color if s.color != "auto" else theme.role_for_index(i)
                stroke = theme.color_of(color_name)
                canvas.line(lx, ly + line_h * 0.5, lx + 16, ly + line_h * 0.5,
                            stroke=stroke, stroke_width=theme.line,
                            dasharray=s.dash)
                canvas.text(lx + 22, ly + line_h * 0.75, s.label,
                            size=theme.size_px("small"),
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
                canvas.line(lx, ly + line_h * 0.5, lx + 16, ly + line_h * 0.5,
                            stroke=stroke, stroke_width=theme.line,
                            dasharray=s.dash)
                canvas.text(lx + 22, ly + line_h * 0.75, s.label,
                            size=theme.size_px("small"),
                            fill=theme.color_of("text"))
                lx += 22 + theme.text_width(s.label, "small") + 20
