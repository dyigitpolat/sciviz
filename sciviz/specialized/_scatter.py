"""Scatter: 2D scatter plot with axes and gridlines."""

from __future__ import annotations

import math as _m
from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


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

