"""Specialized paper-style visualisation elements.

Higher-level primitives for specific kinds of scientific diagrams that crop
up repeatedly but don't merit inclusion in :mod:`sciviz.elements`:

* :class:`Pyramid`  -- a stacked-trapezoid layout (memory hierarchies, taxonomies)
* :class:`Timeline` -- a horizontal time axis with labelled events and lanes
* :class:`Scatter`  -- 2D scatter plot with axes and gridlines
"""

from __future__ import annotations

import math as _m
from typing import List, Optional, Sequence, Tuple, Union

from .core import Element, BBox, Canvas, Theme


# ---------------------------------------------------------------------------
# Pyramid (memory hierarchy / taxonomy)
# ---------------------------------------------------------------------------

class Pyramid(Element):
    """A stack of trapezoidal layers, widest at the bottom.

    Each level is ``(label, side_cells)`` with an optional colour.
    Useful for cache hierarchies, memory pyramids, storage tiers, ...

    Parameters
    ----------
    levels : list of tuples
        Each level is ``(label, side, color?)`` where ``side`` may be either
        a single string (rendered as one right-aligned annotation) or a list
        of strings (rendered as aligned columns).
    width : float
        Maximum (base) width of the pyramid in px.
    tip_width : float
        Width of the topmost trapezoid in px.
    level_h : float
        Height of each level.
    palette : str
        Used to shade levels by position when no explicit colour is given.
    side_col_gap : float
        Horizontal gap between side-annotation columns in px.
    """

    def __init__(self, levels: Sequence[tuple], *,
                 width: float = 240.0,
                 tip_width: float = 80.0,
                 level_h: float = 28.0,
                 palette: str = "blues",
                 gap: float = 0.0,
                 side_col_gap: float = 14.0,
                 color: Optional[str] = None):
        self.levels = [self._normalise(lv) for lv in levels]
        self.width = width
        self.tip_width = tip_width
        self.level_h = level_h
        self.palette = palette
        self.gap = gap
        self.side_col_gap = side_col_gap
        # 'color' overrides the per-level color when no explicit color is given.
        # If both color and per-level color are unset, the sequential palette
        # is used to shade by depth.
        self.color = color

    @staticmethod
    def _normalise(lv):
        if isinstance(lv, str):
            return (lv, [], None)
        if len(lv) == 1:
            return (str(lv[0]), [], None)
        if len(lv) == 2:
            return (str(lv[0]), lv[1], None)
        if len(lv) == 3:
            return (str(lv[0]), lv[1], lv[2])
        raise ValueError(f"Pyramid level must be 1-, 2-, or 3-tuple, got {lv!r}")

    @staticmethod
    def _side_cells(side) -> List[str]:
        if isinstance(side, str):
            return [side]
        return [str(s) for s in side]

    @staticmethod
    def _is_light(hex_color: str) -> bool:
        """Return True if color is 'light' -> black text, else white text."""
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return True
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        # luminance (sRGB relative)
        L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return L > 0.58

    def _side_col_widths(self, theme: Theme) -> List[float]:
        # global column widths -> same alignment across all levels
        cells_per_level = [self._side_cells(lv[1]) for lv in self.levels]
        n_cols = max((len(c) for c in cells_per_level), default=0)
        widths = [0.0] * n_cols
        for cells in cells_per_level:
            for j, c in enumerate(cells):
                w = theme.text_width(c, "small")
                if w > widths[j]:
                    widths[j] = w
        return widths

    def measure(self, theme: Theme) -> BBox:
        n = len(self.levels)
        col_widths = self._side_col_widths(theme)
        side_total = sum(col_widths) + self.side_col_gap * max(0, len(col_widths) - 1)
        # total width: pyramid + a gap + side block on the right
        w = self.width + theme.unit * 2 + side_total + theme.unit
        h = n * self.level_h + (n - 1) * self.gap
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        n = len(self.levels)
        if n == 0:
            return
        col_widths = self._side_col_widths(theme)
        side_total = sum(col_widths) + self.side_col_gap * max(0, len(col_widths) - 1)
        # Center the pyramid base within the pyramid region (width)
        # Layout: [pyramid area W] [gap] [side block side_total]
        cx = x + self.width / 2
        side_start_x = x + self.width + theme.unit * 2

        for i, (label, side, col) in enumerate(self.levels):
            # trapezoid widths: top at i/n, bottom at (i+1)/n interpolation
            w_top = self.tip_width + (self.width - self.tip_width) * (i / n)
            w_bot = self.tip_width + (self.width - self.tip_width) * ((i + 1) / n)
            top_y = y + i * (self.level_h + self.gap)
            bot_y = top_y + self.level_h
            pts = [
                (cx - w_top / 2, top_y),
                (cx + w_top / 2, top_y),
                (cx + w_bot / 2, bot_y),
                (cx - w_bot / 2, bot_y),
            ]
            # colour
            if col is None:
                if self.color is not None:
                    # single role tinted by depth
                    base = theme.color_of(self.color)
                    # shade lighter at top, darker at bottom
                    t = i / max(1, n - 1)
                    fill_hex = theme._lighten(base, 0.7 - 0.7 * t)
                else:
                    fill_hex = theme.color_scale(i / max(1, n - 1),
                                                 self.palette, 0, 1)
            else:
                fill_hex = theme.color_of(col)
            canvas.polygon(pts, fill=fill_hex, stroke=theme.color_of("text"),
                          stroke_width=theme.hairline, opacity=1.0)
            # text colour from luminance
            text_color = theme.text_on(fill_hex)
            txt_y = (top_y + bot_y) / 2 + theme.size_px("label") * 0.33
            canvas.text(cx, txt_y, label,
                       size=theme.size_px("label"),
                       fill=text_color, weight="600", anchor="middle")

            # side-annotation columns (right-aligned within each column)
            cells = self._side_cells(side)
            col_x = side_start_x
            for j, c in enumerate(cells):
                cw = col_widths[j] if j < len(col_widths) else 0
                cx_right = col_x + cw
                canvas.text(cx_right, txt_y, c,
                           size=theme.size_px("small"),
                           fill=theme.color_of("text_muted"),
                           weight="400", anchor="end")
                col_x += cw + self.side_col_gap


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class Timeline(Element):
    """A horizontal time axis with labelled lanes and tasks.

    Parameters
    ----------
    lanes : list of tuples
        Each lane is ``(lane_label, [(start, duration, task_label, color?), ...])``.
    t_min, t_max : float
        Time range.  Bars' ``start`` and ``duration`` are in the same units.
    width : float
        Drawing width in px.
    lane_h : float
        Height per lane in px.
    tick_every : float, optional
        Tick spacing.  None = auto (10 ticks).
    """

    def __init__(self, lanes: Sequence[tuple], *,
                 t_min: float = 0.0, t_max: float = 10.0,
                 width: float = 500.0, lane_h: float = 28.0,
                 tick_every: Optional[float] = None,
                 lane_label_width: float = 90.0,
                 show_axis: bool = True,
                 t_unit: str = "",
                 auto_color: bool = True,
                 color_by: str = "label"):
        self.lanes = list(lanes)
        self.t_min = float(t_min)
        self.t_max = float(t_max)
        self.width = width
        self.lane_h = lane_h
        self.tick_every = tick_every
        self.lane_label_width = lane_label_width
        self.show_axis = show_axis
        self.t_unit = t_unit
        # if auto_color is True, tasks without an explicit colour are coloured
        # by `color_by`:
        #   "label" -- same label -> same colour (good for micro-batches)
        #   "lane"  -- same lane -> same colour
        #   "index" -- distinct colour per task (i.e. no sharing)
        self.auto_color = auto_color
        self.color_by = color_by

    def _time_to_x(self, t: float) -> float:
        return (t - self.t_min) / (self.t_max - self.t_min) * self.width

    def measure(self, theme: Theme) -> BBox:
        n = len(self.lanes)
        axis_h = theme.text_height("small") + 6 if self.show_axis else 0
        H = n * self.lane_h + axis_h + theme.unit
        W = self.lane_label_width + self.width + theme.unit * 2
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        x0 = x + self.lane_label_width

        # Build a key->role assignment for auto-coloring
        key_to_role: dict = {}
        if self.auto_color:
            seen = []
            for li, (lane_label, tasks) in enumerate(self.lanes):
                for t in tasks:
                    key = self._color_key(li, lane_label, t)
                    if key is None:
                        continue
                    if key not in key_to_role:
                        key_to_role[key] = theme.role_for_index(len(seen))
                        seen.append(key)

        # lane backgrounds + task bars
        for i, (lane_label, tasks) in enumerate(self.lanes):
            ly = y + i * self.lane_h
            # lane label (left)
            canvas.text(x + self.lane_label_width - theme.unit * 0.5,
                       ly + self.lane_h / 2 + theme.size_px("label") * 0.33,
                       lane_label,
                       size=theme.size_px("label"),
                       fill=theme.color_of("text"),
                       weight="500", anchor="end")
            # thin lane baseline
            canvas.line(x0, ly + self.lane_h - 1,
                       x0 + self.width, ly + self.lane_h - 1,
                       stroke=theme.color_of("border"),
                       stroke_width=theme.hairline)
            for t in tasks:
                if len(t) == 3:
                    start, dur, label = t
                    col = None
                elif len(t) == 4:
                    start, dur, label, col = t
                else:
                    raise ValueError(f"Timeline task needs 3 or 4 fields: {t!r}")
                bx = x0 + self._time_to_x(start)
                bw = self._time_to_x(start + dur) - self._time_to_x(start)
                bh = self.lane_h - 6
                by = ly + (self.lane_h - bh) / 2

                # color resolution
                if col is not None:
                    fill_hex = theme.color_of(col)
                else:
                    key = self._color_key(i, lane_label, t)
                    if key is not None and key in key_to_role:
                        fill_hex = theme.role(key_to_role[key], "fill")
                    else:
                        fill_hex = theme.color_of("primary_fill")
                stroke_hex = theme._darken(fill_hex, 0.30)
                text_hex = theme.text_on(fill_hex)
                canvas.rect(bx, by, bw, bh, fill=fill_hex, stroke=stroke_hex,
                           stroke_width=theme.hairline, rx=1.5)
                if label and bw > theme.text_width(label, "small") + 4:
                    canvas.text(bx + bw / 2, by + bh / 2 + theme.size_px("small") * 0.33,
                               label, size=theme.size_px("small"),
                               fill=text_hex,
                               weight="600", anchor="middle")

        # axis
        if self.show_axis:
            axis_y = y + len(self.lanes) * self.lane_h + 2
            canvas.line(x0, axis_y, x0 + self.width, axis_y,
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
            dt = self.tick_every
            if dt is None:
                dt = (self.t_max - self.t_min) / 10
            t = self.t_min
            while t <= self.t_max + 1e-6:
                tx = x0 + self._time_to_x(t)
                canvas.line(tx, axis_y, tx, axis_y + 3,
                           stroke=theme.color_of("text"),
                           stroke_width=theme.hairline)
                label = f"{t:g}{self.t_unit}"
                canvas.text(tx, axis_y + 3 + theme.size_px("tiny") * 1.1,
                           label, size=theme.size_px("tiny"),
                           fill=theme.color_of("text_muted"),
                           anchor="middle")
                t += dt

    def _color_key(self, lane_idx, lane_label, task):
        """Return the cache-key used by auto-coloring for a given task."""
        if self.color_by == "lane":
            return f"lane:{lane_label}"
        if self.color_by == "index":
            # always unique
            return None
        # default: by label
        if len(task) >= 3:
            return f"lbl:{task[2]}"
        return None


# ---------------------------------------------------------------------------
# Scatter
# ---------------------------------------------------------------------------

class Scatter(Element):
    """Simple 2D scatter plot with axis labels.

    Parameters
    ----------
    points : list of (x, y, label?, color?, size?)
        Each point may specify label/color/size individually.
    lines : list of (pts, color, dash?, width?), optional
        Separate line series drawn as polylines behind the scatter.  Each
        ``pts`` is a list of ``(x, y)`` pairs.  This lets you draw reference
        curves (a roofline, a budget line) independently of the markers.
    x_range, y_range : tuple (low, high)
    width, height : float
        Plot area in px (excluding axis labels).
    x_label, y_label : str
    log_x, log_y : bool
    grid : bool
    connect : bool
        Connect the *scatter* points in order.  For cleaner figures, use
        the ``lines`` argument instead and leave this off.
    """

    def __init__(self, points: Sequence[tuple], *,
                 lines: Optional[Sequence[tuple]] = None,
                 x_range: Tuple[float, float] = (0, 1),
                 y_range: Tuple[float, float] = (0, 1),
                 width: float = 300.0, height: float = 200.0,
                 x_label: str = "", y_label: str = "",
                 log_x: bool = False, log_y: bool = False,
                 grid: bool = True,
                 connect: bool = False,
                 connect_color: str = "primary"):
        self.points = list(points)
        self.lines = list(lines) if lines else []
        self.x_range = x_range
        self.y_range = y_range
        self.width = width
        self.height = height
        self.x_label = x_label
        self.y_label = y_label
        self.log_x = log_x
        self.log_y = log_y
        self.grid = grid
        self.connect = connect
        self.connect_color = connect_color

    def _x_to_px(self, v):
        x0, x1 = self.x_range
        if self.log_x:
            v = _m.log10(max(v, 1e-12))
            x0 = _m.log10(max(x0, 1e-12))
            x1 = _m.log10(max(x1, 1e-12))
        return (v - x0) / (x1 - x0) * self.width

    def _y_to_px(self, v):
        y0, y1 = self.y_range
        if self.log_y:
            v = _m.log10(max(v, 1e-12))
            y0 = _m.log10(max(y0, 1e-12))
            y1 = _m.log10(max(y1, 1e-12))
        return self.height - (v - y0) / (y1 - y0) * self.height

    @staticmethod
    def _log_ticks(lo, hi):
        """Return list of values at integer powers of 10 within [lo, hi]."""
        lo_p = int(_m.floor(_m.log10(max(lo, 1e-12))))
        hi_p = int(_m.ceil(_m.log10(max(hi, 1e-12))))
        return [10 ** p for p in range(lo_p, hi_p + 1)
                if lo <= 10 ** p <= hi]

    @staticmethod
    def _fmt_log(val):
        """Format a power-of-10 value as a clean string."""
        p = int(round(_m.log10(max(val, 1e-12))))
        if -3 <= p <= 3:
            return f"{val:g}"
        return f"10^{p}"

    def measure(self, theme: Theme) -> BBox:
        left_pad = 42.0 + (theme.text_height("small") + 4 if self.y_label else 0)
        bot_pad = theme.text_height("small") * 2.3 + (theme.text_height("small") + 4 if self.x_label else 0)
        return BBox(left_pad + self.width + 8,
                    self.height + bot_pad + 6)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        left_pad = 42.0 + (theme.text_height("small") + 4 if self.y_label else 0)
        plot_x = x + left_pad
        plot_y = y + 6

        # tick positions
        if self.log_x:
            x_ticks = self._log_ticks(*self.x_range)
        else:
            n_g = 5
            x_ticks = [self.x_range[0] + i * (self.x_range[1] - self.x_range[0]) / (n_g - 1)
                       for i in range(n_g)]
        if self.log_y:
            y_ticks = self._log_ticks(*self.y_range)
        else:
            n_g = 5
            y_ticks = [self.y_range[0] + i * (self.y_range[1] - self.y_range[0]) / (n_g - 1)
                       for i in range(n_g)]

        # gridlines
        if self.grid:
            for xv in x_ticks:
                gx = plot_x + self._x_to_px(xv)
                canvas.line(gx, plot_y, gx, plot_y + self.height,
                           stroke=theme.color_of("border"),
                           stroke_width=theme.hairline,
                           dasharray="2,3")
            for yv in y_ticks:
                gy = plot_y + self._y_to_px(yv)
                canvas.line(plot_x, gy, plot_x + self.width, gy,
                           stroke=theme.color_of("border"),
                           stroke_width=theme.hairline,
                           dasharray="2,3")

        # axes
        canvas.line(plot_x, plot_y, plot_x, plot_y + self.height,
                   stroke=theme.color_of("text"), stroke_width=theme.hairline)
        canvas.line(plot_x, plot_y + self.height, plot_x + self.width, plot_y + self.height,
                   stroke=theme.color_of("text"), stroke_width=theme.hairline)

        # ticks & tick labels
        for xv in x_ticks:
            xt = plot_x + self._x_to_px(xv)
            canvas.line(xt, plot_y + self.height, xt, plot_y + self.height + 3,
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
            label = self._fmt_log(xv) if self.log_x else f"{xv:g}"
            canvas.text(xt, plot_y + self.height + 3 + theme.size_px("tiny") * 1.1,
                       label, size=theme.size_px("tiny"),
                       fill=theme.color_of("text_muted"), anchor="middle")
        for yv in y_ticks:
            yt = plot_y + self._y_to_px(yv)
            canvas.line(plot_x - 3, yt, plot_x, yt,
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
            label = self._fmt_log(yv) if self.log_y else f"{yv:g}"
            canvas.text(plot_x - 5, yt + theme.size_px("tiny") * 0.33,
                       label, size=theme.size_px("tiny"),
                       fill=theme.color_of("text_muted"), anchor="end")

        # axis labels
        if self.x_label:
            canvas.text(plot_x + self.width / 2,
                       plot_y + self.height + theme.size_px("small") * 2.8,
                       self.x_label,
                       size=theme.size_px("small"),
                       fill=theme.color_of("text"), anchor="middle")
        if self.y_label:
            yl_x = plot_x - 34
            yl_y = plot_y + self.height / 2
            canvas.raw(
                f'<text x="{yl_x:.2f}" y="{yl_y:.2f}" '
                f'font-size="{theme.size_px("small"):.1f}" '
                f'fill="{theme.color_of("text")}" '
                f'text-anchor="middle" '
                f'transform="rotate(-90 {yl_x:.2f} {yl_y:.2f})">'
                f'{self.y_label}</text>'
            )

        # separate line series (drawn before markers so markers are on top)
        for lspec in self.lines:
            if len(lspec) == 2:
                pts, col = lspec; dash = None; lw = theme.line
            elif len(lspec) == 3:
                pts, col, dash = lspec; lw = theme.line
            elif len(lspec) == 4:
                pts, col, dash, lw = lspec
            else:
                raise ValueError(f"line spec: (pts, color[, dash[, width]]); got {lspec}")
            if not pts:
                continue
            mapped = [(plot_x + self._x_to_px(px), plot_y + self._y_to_px(py))
                      for px, py in pts]
            d = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in mapped)
            canvas.path(d, stroke=theme.color_of(col), stroke_width=lw,
                       dasharray=dash)

        # connect markers (legacy; discouraged)
        if self.connect and len(self.points) >= 2:
            col = theme.color_of(self.connect_color)
            pts = [(plot_x + self._x_to_px(p[0]), plot_y + self._y_to_px(p[1]))
                   for p in self.points]
            d = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in pts)
            canvas.path(d, stroke=col, stroke_width=theme.line)

        # points: collect first, then place labels avoiding collisions
        plotted = []
        for p in self.points:
            px_v = p[0]
            py_v = p[1]
            label = p[2] if len(p) >= 3 else None
            col = p[3] if len(p) >= 4 else "primary_fill"
            r = p[4] if len(p) >= 5 else 3.5
            anchor_hint = p[5] if len(p) >= 6 else None    # "ne","nw","se","sw","n","s","e","w" or None
            cx = plot_x + self._x_to_px(px_v)
            cy = plot_y + self._y_to_px(py_v)
            canvas.circle(cx, cy, r,
                         fill=theme.color_of(col),
                         stroke=theme.color_of("text"),
                         stroke_width=theme.hairline)
            if label:
                plotted.append((cx, cy, label, theme.color_of(col), r, anchor_hint))

        # collect every line-segment from self.lines for collision checks
        line_segments = []
        for lspec in self.lines:
            pts = lspec[0] if isinstance(lspec, tuple) else lspec
            mapped = [(plot_x + self._x_to_px(px), plot_y + self._y_to_px(py))
                      for px, py in pts]
            for i in range(len(mapped) - 1):
                line_segments.append((*mapped[i], *mapped[i + 1]))

        def _seg_rect_intersect(x1, y1, x2, y2, l, t, r, b):
            """True if line segment (x1,y1)->(x2,y2) intersects rect (l,t,r,b)."""
            # parametric: point = (1-u)*p1 + u*p2,  u in [0, 1]
            # find u-interval where x in [l, r] and y in [t, b]
            EPS = 1e-9
            # x interval
            if abs(x2 - x1) < EPS:
                if not (l - EPS <= x1 <= r + EPS):
                    return False
                ux_lo, ux_hi = 0.0, 1.0
            else:
                a = (l - x1) / (x2 - x1)
                bb = (r - x1) / (x2 - x1)
                ux_lo, ux_hi = (a, bb) if a < bb else (bb, a)
            # y interval
            if abs(y2 - y1) < EPS:
                if not (t - EPS <= y1 <= b + EPS):
                    return False
                uy_lo, uy_hi = 0.0, 1.0
            else:
                a = (t - y1) / (y2 - y1)
                bb = (b - y1) / (y2 - y1)
                uy_lo, uy_hi = (a, bb) if a < bb else (bb, a)
            lo = max(ux_lo, uy_lo, 0.0)
            hi = min(ux_hi, uy_hi, 1.0)
            return lo <= hi + EPS

        # collision-avoiding label placement
        plot_left, plot_right = plot_x, plot_x + self.width
        plot_top, plot_bottom = plot_y, plot_y + self.height
        placed_rects = []
        sz = theme.size_px("tiny")
        asc, desc = sz * 0.85, sz * 0.15
        gap = 2.0   # tight gap between marker edge and label edge

        def _place_at(name, cx, cy, r, tw):
            """Return (text_anchor, lx, baseline_y, bbox) for a given anchor name."""
            if name == "ne":
                bl = cy - r - gap
                lx = cx + r + gap
                return "start", lx, bl, (lx, bl - asc, lx + tw, bl + desc)
            if name == "nw":
                bl = cy - r - gap
                lx = cx - r - gap
                return "end", lx, bl, (lx - tw, bl - asc, lx, bl + desc)
            if name == "se":
                bl = cy + r + gap + asc
                lx = cx + r + gap
                return "start", lx, bl, (lx, bl - asc, lx + tw, bl + desc)
            if name == "sw":
                bl = cy + r + gap + asc
                lx = cx - r - gap
                return "end", lx, bl, (lx - tw, bl - asc, lx, bl + desc)
            if name == "e":
                bl = cy + sz * 0.33
                lx = cx + r + gap
                return "start", lx, bl, (lx, bl - asc, lx + tw, bl + desc)
            if name == "w":
                bl = cy + sz * 0.33
                lx = cx - r - gap
                return "end", lx, bl, (lx - tw, bl - asc, lx, bl + desc)
            if name == "n":
                bl = cy - r - gap
                return "middle", cx, bl, (cx - tw/2, bl - asc, cx + tw/2, bl + desc)
            # "s"
            bl = cy + r + gap + asc
            return "middle", cx, bl, (cx - tw/2, bl - asc, cx + tw/2, bl + desc)

        # candidate order: corners first (visually best), then cardinals
        all_candidates = ["ne", "nw", "se", "sw", "e", "w", "n", "s"]

        for cx, cy, label, fill, r, hint in plotted:
            tw = theme.text_width(label, "tiny")
            cands = [hint.lower()] if hint is not None else all_candidates
            chosen = None
            for name in cands:
                anchor, lx, baseline_y, bbox = _place_at(name, cx, cy, r, tw)
                # off-plot
                inside = (bbox[0] >= plot_left - 4 and bbox[2] <= plot_right + 4
                          and bbox[1] >= plot_top - 4 and bbox[3] <= plot_bottom + 4)
                if not inside and hint is None:
                    continue
                # collide with already-placed labels
                hit = False
                for rb in placed_rects:
                    if (bbox[0] < rb[2] and bbox[2] > rb[0]
                        and bbox[1] < rb[3] and bbox[3] > rb[1]):
                        hit = True; break
                # collide with other markers
                if not hit:
                    for cx2, cy2, _, _, r2, _ in plotted:
                        if (cx2, cy2) == (cx, cy):
                            continue
                        mbox = (cx2 - r2 - 1, cy2 - r2 - 1, cx2 + r2 + 1, cy2 + r2 + 1)
                        if (bbox[0] < mbox[2] and bbox[2] > mbox[0]
                            and bbox[1] < mbox[3] and bbox[3] > mbox[1]):
                            hit = True; break
                # collide with any line segment
                if not hit:
                    for x1, y1, x2, y2 in line_segments:
                        if _seg_rect_intersect(x1, y1, x2, y2, *bbox):
                            hit = True; break
                if not hit or hint is not None:
                    chosen = (anchor, lx, baseline_y, bbox); break
            if chosen is None:
                chosen = _place_at("ne", cx, cy, r, tw)   # fallback
            anchor, lx, baseline_y, bbox = chosen
            placed_rects.append(bbox)
            canvas.text(lx, baseline_y, label, size=sz,
                       fill=theme.color_of("text"), anchor=anchor)
