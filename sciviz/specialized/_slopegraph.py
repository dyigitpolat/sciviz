"""Slopegraph: paired before/after values joined by sloped lines.

A slopegraph compares one measurement across exactly two conditions
(before/after, claimed/measured, A/B).  Each record is a line from its
value on the left rail to its value on the right rail; values are
labelled directly at the endpoints (no y-axis), Tufte-style.  Endpoint
labels dodge vertically so nearby records stay legible, and coincident
duplicate labels collapse into one.

Scope is deliberately tight: one linear value scale shared by both
rails, N records (each with per-record colour/dash/marker so authors
can encode record classes), optional horizontal reference lines, and
direct endpoint labelling.  Log scales and axes are out of scope --
use :class:`LineChart` when an axis is the right reading aid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme

_MARKERS = (None, "circle", "square", "triangle", "diamond")


@dataclass
class SlopeRecord:
    """One paired record of a :class:`Slopegraph`.

    Parameters
    ----------
    label : str
        Record name, shown on the side selected by
        ``Slopegraph.name_side``.
    left, right : float
        The paired values.
    color : str
        Theme colour role, hex, or ``ColorRef``; ``"auto"`` cycles
        through :meth:`Theme.role_for_index`.
    dash : str, optional
        SVG ``stroke-dasharray`` for the slope line (e.g. ``"4,3"``).
    marker : str, optional
        ``"circle"`` (default), ``"square"``, ``"triangle"``,
        ``"diamond"``, or ``None``.
    width : float, optional
        Slope stroke width; defaults to ``theme.line``.
    annotation : str, optional
        Short note appended after the right-hand value (typically the
        signed change, e.g. ``"(-9.0 pt)"``).
    annotation_color : str, optional
        Colour for the annotation; defaults to the chart-level
        ``annotation_color``.
    """

    label: str
    left: float
    right: float
    color: str = "auto"
    dash: Optional[str] = None
    marker: Optional[str] = "circle"
    width: Optional[float] = None
    annotation: Optional[str] = None
    annotation_color: Optional[str] = None


@dataclass(frozen=True)
class SlopeReference:
    """A horizontal reference level spanning the slope area.

    Parameters
    ----------
    value : float
        Level in data units (shares the record scale).
    label : str
        Small caption for the level.
    color : str
        Theme colour role or hex (default ``"muted"``).
    dash : str
        Dash pattern (default dotted).
    label_side : str
        ``"left"`` / ``"right"`` place the caption in the label margin
        beside that rail (dodged with the endpoint labels, so it can
        never collide with slope lines); ``"center"`` draws it inside
        the slope area, above the line, dropping below when a slope
        line crosses it there.
    """

    value: float
    label: str = ""
    color: str = "muted"
    dash: str = "2,3"
    label_side: str = "right"


class Slopegraph(Element):
    """Two-rail before/after comparison with direct endpoint labels.

    Parameters
    ----------
    records : list of :class:`SlopeRecord`, tuple, or dict
        Tuples are ``(label, left, right)`` or
        ``(label, left, right, annotation)``.
    left_title, right_title : str
        Column headers above the two rails.
    value_range : "auto" or (low, high)
        Shared linear scale; ``"auto"`` pads the data (and reference)
        extent by 6%.
    size : str
        Semantic plot size (``"sm"``/``"md"``/``"lg"``/``"xl"``)
        controlling ``(slope_width, height)``; either can be overridden
        explicitly.
    name_side : str
        ``"left"`` (default), ``"right"``, or ``"none"`` -- which
        endpoint label carries the record name.
    show_values : bool
        Label each endpoint with its formatted value (default True).
    value_format : str or callable
        ``format()`` spec (default ``"g"``) or a callable
        ``f(value) -> str``.
    references : list of :class:`SlopeReference`
    annotation_color : str
        Default colour for record annotations (default ``"muted"``).
    rails : bool
        Draw the two vertical rails (default True).
    marker_size : str or float
        Marker radius token (``"xs"``/``"sm"``/``"md"``/``"lg"``) or px.
    label_size : str
        Text size token for endpoint labels (default ``"small"``).
    """

    _PLOT_SIZES = {
        "sm": (120.0, 120.0),
        "md": (150.0, 170.0),
        "lg": (190.0, 220.0),
        "xl": (240.0, 280.0),
    }
    _MARKER_FACTORS = {"xs": 0.42, "sm": 0.58, "md": 0.75, "lg": 0.95}

    def __init__(self, records: Sequence[Union[SlopeRecord, tuple, dict]], *,
                 left_title: str = "", right_title: str = "",
                 value_range: Union[str, Tuple[float, float]] = "auto",
                 size: str = "md",
                 slope_width: Optional[float] = None,
                 height: Optional[float] = None,
                 name_side: str = "left",
                 show_values: bool = True,
                 value_format: Union[str, Callable[[float], str]] = "g",
                 references: Sequence[SlopeReference] = (),
                 annotation_color: str = "muted",
                 rails: bool = True,
                 marker_size: Union[str, float] = "xs",
                 label_size: str = "small"):
        self.records = [self._coerce_record(r) for r in records]
        if not self.records:
            raise ValueError("Slopegraph needs at least one record")
        if size not in self._PLOT_SIZES:
            allowed = ", ".join(self._PLOT_SIZES)
            raise ValueError(f"Slopegraph.size must be one of {allowed}")
        default_w, default_h = self._PLOT_SIZES[size]
        self.slope_width = float(default_w if slope_width is None else slope_width)
        self.height = float(default_h if height is None else height)
        if name_side not in ("left", "right", "none"):
            raise ValueError(
                f"name_side must be 'left', 'right', or 'none'; got {name_side!r}")
        self.name_side = name_side
        self.left_title = left_title
        self.right_title = right_title
        self.value_range = value_range
        self.show_values = show_values
        self.value_format = value_format
        self.references = list(references)
        self.annotation_color = annotation_color
        self.rails = rails
        self.marker_size = marker_size
        self.label_size = label_size
        for ref in self.references:
            if ref.label_side not in ("left", "center", "right"):
                raise ValueError(
                    "SlopeReference.label_side must be 'left', 'center', "
                    f"or 'right'; got {ref.label_side!r}")
        for rec in self.records:
            if rec.marker not in _MARKERS:
                raise ValueError(
                    "SlopeRecord.marker must be circle, square, triangle, "
                    f"diamond, or None; got {rec.marker!r}")

    # ---- coercion ---------------------------------------------------------

    @staticmethod
    def _coerce_record(r) -> SlopeRecord:
        if isinstance(r, SlopeRecord):
            return r
        if isinstance(r, dict):
            return SlopeRecord(**r)
        if isinstance(r, (tuple, list)):
            if len(r) == 3:
                return SlopeRecord(str(r[0]), float(r[1]), float(r[2]))
            if len(r) == 4:
                return SlopeRecord(str(r[0]), float(r[1]), float(r[2]),
                                   annotation=str(r[3]))
            raise ValueError(
                "record tuple must be (label, left, right[, annotation]); "
                f"got {r!r}")
        raise TypeError(
            f"Slopegraph records must be SlopeRecord, tuple, or dict; got {type(r)}")

    # ---- scale ------------------------------------------------------------

    def _resolved_range(self) -> Tuple[float, float]:
        if self.value_range != "auto":
            lo, hi = self.value_range
            lo, hi = float(lo), float(hi)
            if hi <= lo:
                raise ValueError("value_range must satisfy low < high")
            return lo, hi
        values = [v for rec in self.records for v in (rec.left, rec.right)]
        values += [ref.value for ref in self.references]
        lo, hi = min(values), max(values)
        pad = (hi - lo) * 0.06 or 1.0
        return lo - pad, hi + pad

    def _fmt(self, v: float) -> str:
        if callable(self.value_format):
            return str(self.value_format(v))
        return format(v, self.value_format)

    # ---- label composition --------------------------------------------------
    # A side label is a list of (text, color_spec, weight) runs drawn on one
    # line: [name] value on the left, value [annotation] [name] on the right.

    def _side_runs(self, rec: SlopeRecord, side: str) -> List[Tuple[str, str, str]]:
        runs: List[Tuple[str, str, str]] = []
        value = rec.left if side == "left" else rec.right
        name = rec.label if (self.name_side == side and rec.label) else None
        if side == "left":
            if name:
                runs.append((name, "text", "400"))
            if self.show_values:
                runs.append((self._fmt(value), "text", "600"))
        else:
            if self.show_values:
                runs.append((self._fmt(value), "text", "600"))
            if rec.annotation:
                color = rec.annotation_color or self.annotation_color
                runs.append((rec.annotation, color, "400"))
            if name:
                runs.append((name, "text", "400"))
        return runs

    def _runs_width(self, runs, theme: Theme) -> float:
        if not runs:
            return 0.0
        gap = theme.unit * 0.8
        w = sum(theme.text_width(t, self.label_size, bold=(wt in ("600", "700")))
                for t, _, wt in runs)
        return w + gap * (len(runs) - 1)

    # ---- geometry -----------------------------------------------------------

    def _layout(self, theme: Theme) -> dict:
        left_w = max((self._runs_width(self._side_runs(r, "left"), theme)
                      for r in self.records), default=0.0)
        right_w = max((self._runs_width(self._side_runs(r, "right"), theme)
                       for r in self.records), default=0.0)
        for ref in self.references:
            if ref.label and ref.label_side == "left":
                left_w = max(left_w, theme.text_width(ref.label, self.label_size))
            elif ref.label and ref.label_side == "right":
                right_w = max(right_w, theme.text_width(ref.label, self.label_size))
        gap = theme.unit
        title_h = (theme.text_height("label") + theme.unit * 0.8
                   if (self.left_title or self.right_title) else theme.unit * 0.5)
        rail_left = left_w + (gap if left_w else 0.0)
        rail_right = rail_left + self.slope_width
        base_w = rail_right + (gap if right_w else 0.0) + right_w
        # Titles prefer to centre on their rails but are clamped into the
        # chart's own extent so a long header cannot inflate the width.
        def _title_center(rail_x: float, title: str) -> float:
            if not title:
                return rail_x
            tw = theme.text_width(title, "label", bold=True)
            lo_c, hi_c = tw / 2, max(tw / 2, base_w - tw / 2)
            return min(max(rail_x, lo_c), hi_c)

        lt_w = theme.text_width(self.left_title, "label", bold=True) if self.left_title else 0.0
        rt_w = theme.text_width(self.right_title, "label", bold=True) if self.right_title else 0.0
        title_lx = _title_center(rail_left, self.left_title)
        title_rx = _title_center(rail_right, self.right_title)
        # Titles must never overprint each other: split the deficit, keep
        # the left title inside the chart, and let the right title slide
        # right (growing the measured width only when unavoidable).
        if self.left_title and self.right_title:
            overlap = (title_lx + lt_w / 2 + gap) - (title_rx - rt_w / 2)
            if overlap > 0:
                title_lx -= overlap / 2
                title_rx += overlap / 2
                if title_lx - lt_w / 2 < 0:
                    shift = lt_w / 2 - title_lx
                    title_lx += shift
                    title_rx += shift
        max_x = max(base_w, title_lx + lt_w / 2, title_rx + rt_w / 2)
        return {
            "rail_left": rail_left,
            "rail_right": rail_right,
            "title_lx": title_lx,
            "title_rx": title_rx,
            "title_h": title_h,
            "w": max_x,
            "h": title_h + self.height + 2.0,
        }

    def _y_px(self, v: float, lo: float, hi: float) -> float:
        return (1.0 - (v - lo) / (hi - lo)) * self.height

    def _marker_radius(self, theme: Theme) -> float:
        if isinstance(self.marker_size, (int, float)):
            return max(0.5, float(self.marker_size))
        if self.marker_size not in self._MARKER_FACTORS:
            raise ValueError("marker_size must be xs/sm/md/lg or a number")
        return theme.unit * self._MARKER_FACTORS[self.marker_size]

    @staticmethod
    def _dodge(centers: List[float], half: float, lo: float, hi: float,
               sep: float = 1.0) -> List[float]:
        """Shift label centres apart (order-preserving) within [lo, hi]."""
        n = len(centers)
        if n == 0:
            return []
        order = sorted(range(n), key=lambda i: centers[i])
        pos = [centers[i] for i in order]
        step = 2 * half + sep
        for k in range(1, n):
            pos[k] = max(pos[k], pos[k - 1] + step)
        over = pos[-1] + half - hi
        if over > 0:
            pos[-1] -= over
            for k in range(n - 2, -1, -1):
                pos[k] = min(pos[k], pos[k + 1] - step)
        under = lo - (pos[0] - half)
        if under > 0:
            pos[0] += under
            for k in range(1, n):
                pos[k] = max(pos[k], pos[k - 1] + step)
        out = [0.0] * n
        for k, i in enumerate(order):
            out[i] = pos[k]
        return out

    # ---- element contract -----------------------------------------------------

    def measure(self, theme: Theme) -> BBox:
        lay = self._layout(theme)
        return BBox(lay["w"], lay["h"])

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        lay = self._layout(theme)
        lo, hi = self._resolved_range()
        rail_l = x + lay["rail_left"]
        rail_r = x + lay["rail_right"]
        plot_y = y + lay["title_h"]
        gap = theme.unit
        radius = self._marker_radius(theme)

        # rails ---------------------------------------------------------------
        if self.rails:
            for rx in (rail_l, rail_r):
                canvas.line(rx, plot_y, rx, plot_y + self.height,
                            stroke=theme.color_of("border_strong"),
                            stroke_width=theme.hairline)

        # column titles ---------------------------------------------------------
        if self.left_title or self.right_title:
            base = y + theme.size_px("label")
            for title, cx in ((self.left_title, x + lay["title_lx"]),
                              (self.right_title, x + lay["title_rx"])):
                if title:
                    canvas.text(cx, base, title,
                                size=theme.size_px("label"),
                                fill=theme.color_of("text"),
                                weight="600", anchor="middle")

        # reference levels (beneath slope lines) ----------------------------------
        def _slope_hits_band(x0: float, x1: float, top: float, bot: float) -> bool:
            """True if any record's slope line crosses the horizontal band
            [top, bot] within the x-span [x0, x1] (lines are straight, so
            the y-interval over the span decides exactly)."""
            span = rail_r - rail_l
            for rec in self.records:
                y_a = plot_y + self._y_px(rec.left, lo, hi)
                y_b = plot_y + self._y_px(rec.right, lo, hi)
                ys = [y_a + (y_b - y_a) * (xx - rail_l) / span for xx in (x0, x1)]
                if max(ys) >= top - 1.0 and min(ys) <= bot + 1.0:
                    return True
            return False

        for ref in self.references:
            ry = plot_y + self._y_px(ref.value, lo, hi)
            color = theme.color_of(ref.color)
            canvas.line(rail_l, ry, rail_r, ry,
                        stroke=color, stroke_width=theme.hairline,
                        dasharray=ref.dash)
            if ref.label and ref.label_side == "center":
                # The caption sits just above the line unless a slope line
                # crosses it there; then it drops just below (if that band
                # is free and inside the plot).  Margin-side captions are
                # handled with the endpoint labels below.
                lx = (rail_l + rail_r) / 2
                tw = theme.text_width(ref.label, "tiny")
                x0, x1 = lx - tw / 2, lx + tw / 2
                t_h = theme.text_height("tiny")
                pad = theme.unit * 0.5
                above = ry - pad                      # baseline above the line
                below = ry + pad + t_h * 0.82         # baseline below the line
                use_above = not _slope_hits_band(x0, x1, above - t_h * 0.82, above)
                if not use_above:
                    below_free = (
                        not _slope_hits_band(x0, x1, below - t_h * 0.82, below)
                        and below <= plot_y + self.height
                    )
                    if not below_free:
                        use_above = True
                canvas.text(lx, above if use_above else below, ref.label,
                            size=theme.size_px("tiny"),
                            fill=color, anchor="middle")

        # slope lines + markers -------------------------------------------------
        for i, rec in enumerate(self.records):
            color_name = rec.color if rec.color != "auto" else theme.role_for_index(i)
            stroke = theme.color_of(color_name)
            y_l = plot_y + self._y_px(rec.left, lo, hi)
            y_r = plot_y + self._y_px(rec.right, lo, hi)
            canvas.line(rail_l, y_l, rail_r, y_r,
                        stroke=stroke,
                        stroke_width=rec.width if rec.width is not None else theme.line,
                        dasharray=rec.dash)
            if rec.marker:
                for px, py in ((rail_l, y_l), (rail_r, y_r)):
                    self._draw_marker(canvas, rec.marker, px, py, radius,
                                      stroke, theme)

        # endpoint labels (deduplicated, then dodged per side) ---------------------
        line_h = theme.text_height(self.label_size)
        half = line_h / 2
        for side, rail_x, anchor_dir in (("left", rail_l, -1), ("right", rail_r, 1)):
            entries = {}   # (runs tuple, exact value) -> anchor y
            for rec in self.records:
                runs = tuple(self._side_runs(rec, side))
                if not runs:
                    continue
                value = rec.left if side == "left" else rec.right
                entries.setdefault((runs, value),
                                   plot_y + self._y_px(value, lo, hi))
            for ref in self.references:
                if ref.label and ref.label_side == side:
                    runs = ((ref.label, ref.color, "400"),)
                    entries.setdefault((runs, ref.value),
                                       plot_y + self._y_px(ref.value, lo, hi))
            if not entries:
                continue
            keys = list(entries)
            centers = self._dodge([entries[k] for k in keys], half,
                                  plot_y + half, plot_y + self.height + half)
            for (runs, _value), cy in zip(keys, centers):
                baseline = cy + theme.size_px(self.label_size) * 0.33
                total = self._runs_width(list(runs), theme)
                cursor = (rail_x + gap) if anchor_dir > 0 else (rail_x - gap - total)
                for t, color, weight in runs:
                    canvas.text(cursor, baseline, t,
                                size=theme.size_px(self.label_size),
                                fill=theme.color_of(color),
                                weight=weight, anchor="start")
                    cursor += theme.text_width(
                        t, self.label_size, bold=(weight in ("600", "700"))
                    ) + theme.unit * 0.8

    # ---- marker (shared vocabulary with LineChart) -----------------------------

    @staticmethod
    def _draw_marker(canvas: Canvas, marker: str, px: float, py: float,
                     radius: float, color: str, theme: Theme) -> None:
        if marker == "circle":
            canvas.circle(px, py, radius, fill=color, stroke="white",
                          stroke_width=theme.hairline)
        elif marker == "square":
            canvas.rect(px - radius, py - radius, 2 * radius, 2 * radius,
                        fill=color, stroke="white", stroke_width=theme.hairline)
        elif marker == "triangle":
            canvas.polygon([(px, py - radius),
                            (px + radius, py + radius),
                            (px - radius, py + radius)],
                           fill=color, stroke="white",
                           stroke_width=theme.hairline)
        elif marker == "diamond":
            canvas.polygon([(px, py - radius), (px + radius, py),
                            (px, py + radius), (px - radius, py)],
                           fill=color, stroke="white",
                           stroke_width=theme.hairline)
