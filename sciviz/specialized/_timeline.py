"""Timeline: horizontal time axis with labelled events and lanes."""

from __future__ import annotations

import math as _m
from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


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

    _WIDTH_UNITS = {
        "xs": 2.8,
        "sm": 3.4,
        "md": 4.0,
        "lg": 5.0,
        "xl": 6.2,
    }
    _LANE_HEIGHT_UNITS = {
        "xs": 2.4,
        "sm": 3.0,
        "md": 3.7,
        "lg": 4.5,
    }

    def __init__(self, lanes: Sequence[tuple], *,
                 t_min: float = 0.0, t_max: float = 10.0,
                 width: Union[str, float] = 500.0,
                 lane_h: Union[str, float] = 28.0,
                 tick_every: Optional[float] = None,
                 lane_label_width: Union[str, float] = 90.0,
                 show_axis: bool = True,
                 t_unit: str = "",
                 auto_color: bool = True,
                 color_by: str = "label",
                 milestones: Optional[Sequence[tuple]] = None):
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
        self.milestones = list(milestones or ())

    def _plot_width(self, theme: Theme) -> float:
        if isinstance(self.width, (int, float)):
            return float(self.width)
        if self.width == "auto":
            units = self._WIDTH_UNITS["md"]
        elif self.width in self._WIDTH_UNITS:
            units = self._WIDTH_UNITS[self.width]
        else:
            allowed = ", ".join((*self._WIDTH_UNITS, "auto"))
            raise ValueError(f"Timeline.width must be numeric or one of {allowed}")
        return max(
            theme.unit * 8.0,
            (self.t_max - self.t_min) * theme.unit * units,
        )

    def _lane_height(self, theme: Theme) -> float:
        if isinstance(self.lane_h, (int, float)):
            return float(self.lane_h)
        if self.lane_h not in self._LANE_HEIGHT_UNITS:
            allowed = ", ".join(self._LANE_HEIGHT_UNITS)
            raise ValueError(
                f"Timeline.lane_h must be numeric or one of {allowed}"
            )
        return theme.unit * self._LANE_HEIGHT_UNITS[self.lane_h]

    def _lane_label_width(self, theme: Theme) -> float:
        if isinstance(self.lane_label_width, (int, float)):
            return float(self.lane_label_width)
        if self.lane_label_width != "auto":
            raise ValueError(
                "Timeline.lane_label_width must be numeric or 'auto'"
            )
        label_w = max(
            (theme.text_width(str(label), "label", bold=True)
             for label, _tasks in self.lanes),
            default=0.0,
        )
        return label_w + theme.unit

    def _time_to_x(self, t: float, plot_width: float) -> float:
        return (t - self.t_min) / (self.t_max - self.t_min) * plot_width

    def measure(self, theme: Theme) -> BBox:
        n = len(self.lanes)
        axis_h = theme.text_height("small") + 6 if self.show_axis else 0
        lane_h = self._lane_height(theme)
        H = n * lane_h + axis_h + theme.unit
        W = (self._lane_label_width(theme) + self._plot_width(theme)
             + theme.unit * 2)
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        plot_width = self._plot_width(theme)
        lane_h = self._lane_height(theme)
        label_width = self._lane_label_width(theme)
        x0 = x + label_width

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
            ly = y + i * lane_h
            # lane label (left)
            canvas.text(x + label_width - theme.unit * 0.5,
                       ly + lane_h / 2 + theme.size_px("label") * 0.33,
                       lane_label,
                       size=theme.size_px("label"),
                       fill=theme.color_of("text"),
                       weight="500", anchor="end")
            # thin lane baseline
            canvas.line(x0, ly + lane_h - 1,
                       x0 + plot_width, ly + lane_h - 1,
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
                bx = x0 + self._time_to_x(start, plot_width)
                bw = (self._time_to_x(start + dur, plot_width)
                      - self._time_to_x(start, plot_width))
                bh = lane_h - 6
                by = ly + (lane_h - bh) / 2

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

        # Milestone guides are semantic time boundaries (phase ends,
        # synchronization points), drawn after bars so they remain legible.
        for milestone in self.milestones:
            if not isinstance(milestone, (tuple, list)) or not milestone:
                raise TypeError("Timeline milestones must be non-empty tuples")
            time = float(milestone[0])
            label = milestone[1] if len(milestone) > 1 else None
            role = milestone[2] if len(milestone) > 2 else "highlight"
            mx = x0 + self._time_to_x(time, plot_width)
            canvas.line(
                mx, y, mx, y + len(self.lanes) * lane_h,
                stroke=theme.color_of(role),
                stroke_width=theme.line,
                dasharray="3,2",
            )
            if label:
                canvas.text(
                    mx - theme.unit * 0.4,
                    y + theme.size_px("tiny") * 0.85,
                    str(label),
                    size=theme.size_px("tiny"),
                    fill=theme.color_of(role),
                    anchor="end",
                )

        # axis
        if self.show_axis:
            axis_y = y + len(self.lanes) * lane_h + 2
            canvas.line(x0, axis_y, x0 + plot_width, axis_y,
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline)
            dt = self.tick_every
            if dt is None:
                dt = (self.t_max - self.t_min) / 10
            t = self.t_min
            while t <= self.t_max + 1e-6:
                tx = x0 + self._time_to_x(t, plot_width)
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


