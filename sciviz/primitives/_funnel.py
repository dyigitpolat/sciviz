"""Funnel: a staged narrowing of one population.

A funnel is the shape of *selection*: a set enters at the top, a rule
keeps part of it, and the survivors leave at the bottom. Drawing that as
a row of boxes with counts loses the one thing the reader wants, which is
how much was dropped; drawing it as a taper puts the ratio in the
silhouette itself.

Every stage is ``(label, value)``. The first value sets the full width,
so each later stage's edge width is its share of the population that
entered. A straight *neck* below the last stage keeps a two-stage funnel
reading as a funnel rather than as one trapezoid.

Three optional layers make the funnel say more than a ratio:

* **Members.** ``FunnelStage(marks=[...])`` draws the population itself,
  one dot per member in its own colour, packed inside the band the stage
  occupies (the last stage's members sit in the neck). The reader counts
  what entered and what was kept instead of dividing two numbers.
* **Lanes.** With ``lanes=True`` the members of each colour travel in a
  lane of their own, and every lane narrows on its own: the shape of a
  selection made *within* each group rather than between groups (each
  group keeps its best few). Lanes are separated by page-coloured gutters.
* **Bypass.** ``bypass="label"`` draws a dashed arc over the body from a
  bracket that spans the whole mouth (every lane, so the whole inlet steps
  aside, not one group) to the far end of the neck: a selection that can
  be skipped, with the condition as the arc's caption. With
  ``bypass_to="outlet"`` the arc leaves the bracket at the mouth's centre
  and lands on the outlet's own end, so it reads as the whole pool
  passing the selection by rather than as one lane joining the kept.

``orientation="horizontal"`` lays the funnel on its side, mouth on the
left, so it can sit in a left-to-right pipeline; its stage captions are
set under the bands they name.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass(frozen=True)
class FunnelStage:
    """One level of a :class:`Funnel`.

    Parameters
    ----------
    label : str
        The name of the population at this level. Empty means unlabelled.
    value : float
        Its size, in any unit shared by the stages. Non-negative.
    color : optional
        Per-stage override of the funnel's role colour.
    marks : sequence, optional
        The members at this level, one colour per member (a hex string, a
        role name or a :class:`ColorRef`). Drawn as dots inside the band
        this stage occupies; members of the last stage sit in the neck.
    mark_size : float, optional
        Radius of this stage's dots in px; the funnel's ``mark_radius``
        when omitted (survivors are often drawn a size up).
    """

    label: str
    value: float
    color: object = None
    marks: Sequence = field(default_factory=tuple)
    mark_size: Optional[float] = None


StageLike = Union[FunnelStage, Tuple]

# (u0, v_top0, u1, v_top1, v_bot1, v_bot0): a lane quadrilateral in the
# funnel's own frame -- u runs along the flow, v across it, centred.
_Quad = Tuple[float, float, float, float, float, float]


class Funnel(Element):
    """A tapering silhouette over a sequence of shrinking stages.

    Parameters
    ----------
    stages : sequence
        Two or more :class:`FunnelStage` values, or ``(label, value)`` /
        ``(label, value, color)`` tuples. Values need not decrease, but a
        funnel that widens is usually a sign the stages are in the wrong
        order.
    width, height : float
        The taper's own extent, before labels.
    role : ColorRef or str
        The colour family of the body (filled soft, stroked solid).
    orientation : {"vertical", "horizontal"}
        ``"vertical"`` (default) narrows downward; ``"horizontal"`` narrows
        left to right, the mouth on the left.
    label_position : {"right", "below", "above", "none"}, optional
        Where stage labels are written. A vertical funnel writes each label
        beside its own edge (``"right"``, its default) and widens its box by
        the label column; a horizontal funnel centres each label under
        (``"below"``, its default) or over its own band.
    show_values : bool
        Whether the value is written after the label.
    value_format : str
        ``format`` spec for the value, e.g. ``"{:g}"`` or ``"{:.0f}"``.
    neck_ratio : float
        Fraction of the length given to a straight neck after the last
        stage. ``0.0`` ends the figure on the taper. A neck that carries
        members grows to fit them.
    min_ratio : float
        Floor on an edge's width as a fraction of the widest edge, so a
        stage that keeps almost nothing is still visible as an edge.
    lanes : bool
        Give every mark colour its own lane (see the module docstring).
    mark_radius : float
        Radius of a member dot in px. Dots shrink (never below 40% of this)
        only when a band cannot hold its members at this size.
    bypass : str or bool, optional
        Draw the dashed bypass arc; a string is its caption (``"\n"``
        breaks it into lines, so a condition can stay within the body's
        own width).
    bypass_to : str
        Where the bypass lands: ``"neck"`` (default) on the neck's edge at
        its middle, from the bracket's end; ``"outlet"`` on the outlet's
        end, from the bracket's centre (the mouth's centre line), so the
        arc spans the whole selection, inlet to outlet.
    """

    def __init__(self, stages: Sequence[StageLike], *,
                 width: float = 64.0, height: float = 40.0,
                 role="primary",
                 orientation: str = "vertical",
                 label_position: Optional[str] = None,
                 show_values: bool = True,
                 value_format: str = "{:g}",
                 neck_ratio: float = 0.22,
                 min_ratio: float = 0.08,
                 text_size: str = "tiny",
                 lanes: bool = False,
                 mark_radius: float = 1.2,
                 bypass: Union[str, bool, None] = None,
                 bypass_to: str = "neck"):
        if bypass_to not in ("neck", "outlet"):
            raise ValueError('Funnel bypass_to must be "neck" or "outlet"')
        self.bypass_to = bypass_to
        self.stages = [self._normalise(s) for s in stages]
        if len(self.stages) < 2:
            raise ValueError("Funnel needs at least two stages")
        if any(s.value < 0 for s in self.stages):
            raise ValueError("Funnel stage values must be non-negative")
        if orientation not in ("vertical", "horizontal"):
            raise ValueError('Funnel orientation must be "vertical" or '
                             '"horizontal"')
        self.orientation = orientation
        if label_position is None:
            label_position = "right" if orientation == "vertical" else "below"
        allowed = (("right", "none") if orientation == "vertical"
                   else ("below", "above", "none"))
        if label_position not in allowed:
            raise ValueError(
                f"Funnel label_position for a {orientation} funnel must be "
                + " or ".join(f'"{a}"' for a in allowed))
        self.width = float(width)
        self.height = float(height)
        self.role = role
        self.label_position = label_position
        self.show_values = bool(show_values)
        self.value_format = value_format
        self.neck_ratio = max(0.0, min(0.6, float(neck_ratio)))
        self.min_ratio = max(0.0, min(0.9, float(min_ratio)))
        self.text_size = text_size
        self.lanes = bool(lanes)
        self.mark_radius = max(0.3, float(mark_radius))
        self.bypass = bypass

    # -- data ----------------------------------------------------------

    @staticmethod
    def _normalise(s: StageLike) -> FunnelStage:
        if isinstance(s, FunnelStage):
            return s
        if len(s) == 2:
            return FunnelStage(str(s[0]), float(s[1]))
        if len(s) == 3:
            return FunnelStage(str(s[0]), float(s[1]), s[2])
        raise ValueError(f"Funnel stage: (label, value[, color]); got {s!r}")

    def _caption(self, stage: FunnelStage) -> str:
        if not self.show_values:
            return stage.label
        value = self.value_format.format(stage.value)
        return f"{stage.label} {value}".strip()

    def _ratios(self) -> list[float]:
        top = max((s.value for s in self.stages), default=0.0)
        if top <= 0:
            return [1.0] * len(self.stages)
        return [max(self.min_ratio, s.value / top) for s in self.stages]

    def _has_marks(self) -> bool:
        return any(len(s.marks) for s in self.stages)

    # -- frame ---------------------------------------------------------

    @property
    def _along(self) -> float:
        return self.height if self.orientation == "vertical" else self.width

    @property
    def _across(self) -> float:
        return self.width if self.orientation == "vertical" else self.height

    def _point(self, ox: float, oy: float, u: float, v: float
               ) -> Tuple[float, float]:
        """Map the funnel's own (along, across) frame to canvas px."""
        mid = self._across / 2.0
        if self.orientation == "vertical":
            return ox + mid + v, oy + u
        return ox + u, oy + mid + v

    # -- member layout -------------------------------------------------

    def _groups(self, theme: Theme) -> List[str]:
        """Mark colours in order of first appearance: the lane order."""
        order: List[str] = []
        for stage in self.stages:
            for mark in stage.marks:
                paint = theme.paint_of(mark)
                if paint not in order:
                    order.append(paint)
        return order

    def _counts(self, theme: Theme, groups: List[str]) -> List[List[int]]:
        out = []
        for stage in self.stages:
            paints = [theme.paint_of(m) for m in stage.marks]
            out.append([paints.count(g) for g in groups])
        return out

    def _radius(self, stage: FunnelStage) -> float:
        return float(stage.mark_size) if stage.mark_size else self.mark_radius

    def _pitch(self, r: float) -> float:
        return 2.0 * r + max(0.5, r * 0.55)

    def _inset(self, theme: Theme) -> float:
        """Clear space between a member and the outline or a lane gutter."""
        return theme.hairline * 1.2

    def _lane_floor(self, theme: Theme, radius: float,
                    extents: List[float], taper: float) -> float:
        """Thinnest lane (measured across the flow) that holds one row.

        A lane follows the taper, so it runs at an angle; a row of discs
        needs its clearance *perpendicular* to the lane's edges, which is
        more than the same clearance measured straight across the flow.
        The steepest edge of the body bounds that angle.
        """
        n = len(extents)
        band = taper / max(1, n - 1)
        slope = 0.0
        if band > 1e-6:
            slope = max(abs(extents[i] - extents[i + 1]) / 2.0 / band
                        for i in range(n - 1))
        cos = 1.0 / math.sqrt(1.0 + slope * slope)
        need = 2.0 * (radius + self._inset(theme)) + radius * 0.35
        return need / cos

    def _geometry(self, theme: Theme):
        """Edges, neck and lane splits in the funnel's own frame.

        Returns ``(u_edges, extents, neck_start, lane_bounds)`` where
        ``lane_bounds[i]`` lists ``(v_top, v_bot)`` per lane at edge ``i``
        (a single lane spanning the edge when lanes are off).
        """
        n = len(self.stages)
        along, across = self._along, self._across
        ratios = self._ratios()
        extents = [across * r for r in ratios]
        groups = self._groups(theme) if self._has_marks() else []
        counts = self._counts(theme, groups) if groups else []
        use_lanes = self.lanes and len(groups) > 0

        # The neck carries the last stage's members, so it must be thick
        # enough for one row of them per lane and long enough for the
        # longest row; it grows (the taper shortens) rather than letting
        # the survivors overflow.
        neck = along * self.neck_ratio
        last = self.stages[-1]
        if last.marks:
            r_last = self._radius(last)
            pitch = self._pitch(r_last)
            inset = self._inset(theme)
            # The lanes reach the neck along the taper, so each needs the
            # tilted floor; the slope of the unadjusted body bounds it.
            row_thick = self._lane_floor(theme, r_last, extents,
                                         along * (1.0 - self.neck_ratio))
            if use_lanes:
                need = [c for c in counts[-1] if c > 0]
                thick = row_thick * len(need)
                row = max(need, default=0)
            else:
                total = len(last.marks)
                rows = max(1, int((extents[-1] - 2 * inset) // pitch))
                thick = pitch * min(rows, total) + 2 * inset
                row = math.ceil(total / max(1, rows))
            extents[-1] = min(across, max(extents[-1], thick))
            neck = max(neck, (row - 1) * pitch + 2.0 * (r_last + inset)
                       + r_last * 0.5)
        neck = min(neck, along * 0.7)
        # An edge before the neck is never thinner than the neck itself.
        for i in range(n - 2, -1, -1):
            extents[i] = max(extents[i], extents[i + 1])
        taper = along - neck
        u_edges = [taper * i / (n - 1) for i in range(n)]

        lane_bounds: List[List[Tuple[float, float]]] = []
        for i in range(n):
            e = extents[i]
            if not use_lanes:
                lane_bounds.append([(-e / 2, e / 2)])
                continue
            row = counts[i]
            total = sum(row)
            if total <= 0:
                lane_bounds.append([(-e / 2 + e * k / len(row),
                                     -e / 2 + e * (k + 1) / len(row))
                                    for k in range(len(row))])
                continue
            radius = self._radius(self.stages[i])
            floor = self._lane_floor(theme, radius, extents, taper)
            # Proportional shares, then every lane that has members is
            # raised to hold one row of them, paid for by the widest lanes.
            share = [e * c / total for c in row]
            short = [k for k, c in enumerate(row) if c > 0 and share[k] < floor]
            if short and floor * len(short) < e:
                debt = sum(floor - share[k] for k in short)
                rich = [k for k in range(len(row)) if k not in short and row[k] > 0]
                pool = sum(share[k] for k in rich)
                for k in short:
                    share[k] = floor
                for k in rich:
                    share[k] -= debt * share[k] / pool if pool > 0 else 0.0
            bounds, cursor = [], -e / 2
            for k in range(len(row)):
                bounds.append((cursor, cursor + share[k]))
                cursor += share[k]
            lane_bounds.append(bounds)
        return u_edges, extents, taper, lane_bounds, groups, counts

    @staticmethod
    def _interval(quad: _Quad, u: float) -> Tuple[float, float]:
        u0, t0, u1, t1, b1, b0 = quad
        f = 0.0 if u1 == u0 else (u - u0) / (u1 - u0)
        f = max(0.0, min(1.0, f))
        return t0 + (t1 - t0) * f, b0 + (b1 - b0) * f

    @staticmethod
    def _clear_interval(quad: _Quad, u: float, clear: float
                        ) -> Tuple[float, float]:
        """Centres at ``u`` whose perpendicular distance to both lane
        edges is at least ``clear``."""
        u0, t0, u1, t1, b1, b0 = quad
        span = (u1 - u0) or 1e-9
        f = max(0.0, min(1.0, (u - u0) / span))
        top = t0 + (t1 - t0) * f
        bot = b0 + (b1 - b0) * f
        ct = math.sqrt(1.0 + ((t1 - t0) / span) ** 2)
        cb = math.sqrt(1.0 + ((b1 - b0) / span) ** 2)
        return top + clear * ct, bot - clear * cb

    def _pack(self, quad: _Quad, n: int, r: float, inset: float
              ) -> Tuple[List[Tuple[float, float]], float]:
        """Place ``n`` discs of radius ``r`` inside a lane quadrilateral.

        Columns are filled from the mouth end, each centred across the
        lane, so a population reads as an orderly crowd entering the band.
        Shrinks the pitch to touching, then the radius (to 40%), when the
        lane cannot hold ``n`` at the requested size. Returns the centres
        and the radius actually used.
        """
        if n <= 0:
            return [], r
        u0, _t0, u1, _t1, _b1, _b0 = quad
        radius = r
        floor = r * 0.4
        while True:
            for pitch in (self._pitch(radius), 2.0 * radius * 1.04):
                slots: List[Tuple[float, float]] = []
                u = u0 + inset + radius
                while u + radius * 0.5 <= u1 + 1e-9:
                    lo, hi = self._clear_interval(quad, u, radius + inset)
                    if hi >= lo - 1e-9:
                        m = int((hi - lo) // pitch) + 1
                        mid = (lo + hi) / 2
                        col = [mid + (k - (m - 1) / 2) * pitch for k in range(m)]
                        slots.append((u, col))
                    u += pitch * 0.92
                capacity = sum(len(c) for _u, c in slots)
                if capacity >= n:
                    placed: List[Tuple[float, float]] = []
                    for u, col in slots:
                        need = n - len(placed)
                        if need <= 0:
                            break
                        if len(col) > need:
                            # A partial last column keeps its middle slots.
                            start = (len(col) - need) // 2
                            col = col[start:start + need]
                        placed.extend((u, v) for v in col)
                    return placed, radius
            if radius <= floor + 1e-9:
                break
            radius = max(floor, radius * 0.9)
        # Nothing fits even at the floor: stack what cannot be placed on
        # the lane's centre line rather than drop members.
        mid_u = (u0 + u1) / 2
        ta, ba = self._interval(quad, mid_u)
        return [(mid_u, (ta + ba) / 2)] * n, floor

    # -- layout --------------------------------------------------------

    def _label_width(self, theme: Theme) -> float:
        if self.label_position != "right":
            return 0.0
        widths = [theme.text_width(self._caption(s), self.text_size)
                  for s in self.stages]
        return max(widths, default=0.0) + theme.unit * 0.7

    def _label_centres(self, theme: Theme) -> list[float]:
        """Each caption's centre, as an offset below the funnel's top.

        A caption names the edge its stage starts at, but a line centred
        on the top edge would put half its ink above the funnel (over
        whatever sits there), and on a short funnel two neighbouring edges
        can be closer than one line. So each centre is kept half a line
        inside the funnel's height and a full line below the caption
        before it; the funnel's measured height grows by what that costs.
        """
        n = len(self.stages)
        band_h = self.height * (1.0 - self.neck_ratio) / (n - 1)
        line = theme.text_height(self.text_size)
        half = line / 2
        centres: list[float] = []
        for i in range(n):
            c = min(max(i * band_h, half), max(half, self.height - half))
            if centres:
                c = max(c, centres[-1] + line)
            centres.append(c)
        return centres

    def _band_centres(self, theme: Theme) -> List[float]:
        """Along-axis centre of every stage's band (the neck for the last)."""
        u_edges, _e, taper, *_ = self._geometry(theme)
        n = len(self.stages)
        out = [(u_edges[i] + u_edges[i + 1]) / 2 for i in range(n - 1)]
        out.append((taper + self._along) / 2)
        return out

    def _side_label_lines(self, theme: Theme) -> List[Tuple[float, int, str]]:
        """Horizontal funnel captions as ``(centre_u, line, text)``.

        Captions sit on one line under (or over) their bands; a caption
        that would touch the one before it drops to the next line.
        """
        out: List[Tuple[float, int, str]] = []
        gap = theme.unit * 0.6
        right_edge: dict[int, float] = {}
        for stage, cu in zip(self.stages, self._band_centres(theme)):
            text = self._caption(stage)
            if not text:
                continue
            w = theme.text_width(text, self.text_size)
            left = max(0.0, min(cu - w / 2, self._along - w))
            line = 0
            while right_edge.get(line, -1e9) + gap > left:
                line += 1
            right_edge[line] = left + w
            out.append((left + w / 2, line, text))
        return out

    def _bypass_lines(self) -> List[str]:
        if isinstance(self.bypass, str) and self.bypass:
            return self.bypass.split("\n")
        return []

    def _bypass_reserve(self, theme: Theme) -> Tuple[float, float]:
        """(arc rise, caption height) reserved on the bypass side."""
        if not self.bypass:
            return 0.0, 0.0
        rise = max(theme.unit * 1.2, self._across * 0.12)
        cap = theme.text_height(self.text_size) * len(self._bypass_lines())
        return rise, cap

    def _bypass_lead(self, theme: Theme) -> float:
        """Room before the mouth, along the flow, for the bracket the
        bypass leaves from (``0`` without a bypass)."""
        return theme.unit * 0.9 if self.bypass else 0.0

    def _body_offset(self, theme: Theme) -> Tuple[float, float]:
        """The taper body's top-left corner in the funnel's own frame."""
        rise, cap = self._bypass_reserve(theme)
        lead = self._bypass_lead(theme)
        if self.orientation == "horizontal":
            b = self.measure(theme)
            return (b.w - self.width + lead) / 2.0, rise + cap
        return rise + cap, lead

    def _side_label_height(self, theme: Theme) -> float:
        if self.orientation != "horizontal" or self.label_position == "none":
            return 0.0
        lines = self._side_label_lines(theme)
        if not lines:
            return 0.0
        count = max(line for _c, line, _t in lines) + 1
        return theme.unit * 0.35 + count * theme.text_height(self.text_size)

    def _bypass_width(self, theme: Theme) -> float:
        return max((theme.text_width(line, self.text_size)
                    for line in self._bypass_lines()), default=0.0)

    def measure(self, theme: Theme) -> BBox:
        rise, cap = self._bypass_reserve(theme)
        lead = self._bypass_lead(theme)
        if self.orientation == "horizontal":
            h = self.height + self._side_label_height(theme) + rise + cap
            w = max(self.width + lead, self._bypass_width(theme))
            return BBox(w, h)
        h = self.height
        if self.label_position != "none":
            half = theme.text_height(self.text_size) / 2
            h = max(h, self._label_centres(theme)[-1] + half)
        return BBox(self.width + self._label_width(theme) + rise + cap,
                    h + lead)

    def content_bbox(self, theme: Theme):
        """The taper body itself, without stage captions or the bypass arc
        and its caption: siblings align on the funnel's visible face (a
        centred row puts its neighbour level with the neck, where wires
        leave), the way a :class:`Region` aligns on its child."""
        dx, dy = self._body_offset(theme)
        return (dx, dy, self.width, self.height)

    def port_bbox(self, theme: Theme, side: str):
        """Wires land on the taper, not on the edge of the box widened by
        the bypass or stage captions (see :meth:`Element.port_bbox`); a
        side whose captions sit between taper and layout edge falls back
        to the layout box at the connector.

        The two ends of the flow are narrower than the taper's box: a
        wire leaves through the outlet (the neck opening at the narrow
        end) and arrives through the mouth (the first stage at the wide
        end), so on those two sides the face spans only that opening.
        A wire then leaves at the outlet's centre, or runs straight
        wherever the facing element overlaps it, instead of from a
        corner of the taper's box. With a bypass, the mouth's face is the
        bracket the bypass leaves from.
        """
        x, y, w, h = self.content_bbox(theme)
        horizontal = self.orientation == "horizontal"
        outlet, inlet = (("right", "left") if horizontal
                         else ("bottom", "top"))
        if side not in (outlet, inlet):
            return (x, y, w, h)
        extents = self._geometry(theme)[1]
        span = extents[-1] if side == outlet else extents[0]
        mid = self._across / 2.0
        # With a bypass the inlet face is the bracket before the mouth,
        # which the bypass leaves from: what enters the funnel meets it.
        lead = self._bypass_lead(theme) * 0.6 if side == inlet else 0.0
        if horizontal:
            return (x - lead, y + mid - span / 2.0, w + lead, span)
        return (x + mid - span / 2.0, y - lead, span, h + lead)

    # -- paint ---------------------------------------------------------

    def _body_paints(self, theme: Theme) -> Tuple[str, str]:
        body = theme.color_of(self.role)
        soft = (theme.color_of(self.role.soft())
                if hasattr(self.role, "soft")
                else theme.role(str(self.role), "soft"))
        return body, soft

    def _stage_soft(self, theme: Theme, stage: FunnelStage, soft: str) -> str:
        if stage.color is None:
            return soft
        ref = stage.color
        return (theme.color_of(ref.soft()) if hasattr(ref, "soft")
                else theme.role(str(ref), "soft"))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self.orientation == "horizontal" or self._has_marks() or self.bypass:
            self._render_general(canvas, x, y, theme)
            return
        self._render_vertical_plain(canvas, x, y, theme)

    def _render_vertical_plain(self, canvas: Canvas, x: float, y: float,
                               theme: Theme) -> None:
        """The historic vertical funnel (no members, no bypass)."""
        ratios = self._ratios()
        n = len(self.stages)
        taper_h = self.height * (1.0 - self.neck_ratio)
        band_h = taper_h / (n - 1)
        cx = x + self.width / 2
        body, soft = self._body_paints(theme)

        def edge(i: int) -> Tuple[float, float]:
            half = self.width * ratios[i] / 2
            return cx - half, cx + half

        for i in range(n - 1):
            top_y = y + i * band_h
            bot_y = top_y + band_h
            l0, r0 = edge(i)
            l1, r1 = edge(i + 1)
            fill = self._stage_soft(theme, self.stages[i], soft)
            canvas.polygon([(l0, top_y), (r0, top_y), (r1, bot_y), (l1, bot_y)],
                           fill=fill, stroke=body,
                           stroke_width=theme.hairline)

        if self.neck_ratio > 0:
            l1, r1 = edge(n - 1)
            neck_y = y + taper_h
            canvas.rect(l1, neck_y, max(r1 - l1, 0.4),
                        self.height - taper_h,
                        fill=soft, stroke=body, stroke_width=theme.hairline)

        self._render_right_labels(canvas, x, y, theme)

    def _render_right_labels(self, canvas: Canvas, x: float, y: float,
                             theme: Theme) -> None:
        if self.label_position != "right":
            return
        size = theme.size_px(self.text_size)
        tx = x + self.width + theme.unit * 0.55
        for stage, centre in zip(self.stages, self._label_centres(theme)):
            canvas.text(tx, y + centre + size * 0.36, self._caption(stage),
                        size=size, fill=theme.color_of("text_muted"),
                        anchor="start")

    def _render_general(self, canvas: Canvas, x: float, y: float,
                        theme: Theme) -> None:
        n = len(self.stages)
        rise, cap = self._bypass_reserve(theme)
        horizontal = self.orientation == "horizontal"
        # The body's own top-left corner: the bypass arc and its caption sit
        # over a horizontal funnel and left of a vertical one.
        dx, dy = self._body_offset(theme)
        ox, oy = x + dx, y + dy
        (u_edges, extents, taper, lanes, groups, counts) = \
            self._geometry(theme)
        along = self._along
        body, soft = self._body_paints(theme)
        P = lambda u, v: self._point(ox, oy, u, v)  # noqa: E731

        # Body: one outline through every edge and the neck.
        top = [P(u_edges[i], -extents[i] / 2) for i in range(n)]
        bot = [P(u_edges[i], extents[i] / 2) for i in range(n)]
        if along - taper > 1e-6:
            top.append(P(along, -extents[-1] / 2))
            bot.append(P(along, extents[-1] / 2))
        for i in range(n - 1):
            fill = self._stage_soft(theme, self.stages[i], soft)
            canvas.polygon([top[i], top[i + 1], bot[i + 1], bot[i]],
                           fill=fill, stroke="none")
        if along - taper > 1e-6:
            canvas.polygon([top[n - 1], top[n], bot[n], bot[n - 1]],
                           fill=soft, stroke="none")
        outline = top + list(reversed(bot))
        closed = outline + [outline[0]]
        for a, b in zip(closed, closed[1:]):
            canvas.line(a[0], a[1], b[0], b[1], stroke=body,
                        stroke_width=theme.hairline)

        # Lane gutters: page-coloured lines between neighbouring lanes.
        if self.lanes and len(lanes[0]) > 1:
            for k in range(len(lanes[0]) - 1):
                pts = [P(u_edges[i], lanes[i][k][1]) for i in range(n)]
                if along - taper > 1e-6:
                    pts.append(P(along, lanes[-1][k][1]))
                for a, b in zip(pts, pts[1:]):
                    canvas.line(a[0], a[1], b[0], b[1], stroke=theme.bg,
                                stroke_width=theme.hairline * 1.6)

        # Members.
        inset = theme.hairline * 1.2
        for i, stage in enumerate(self.stages):
            if not stage.marks:
                continue
            u0 = u_edges[i]
            u1 = u_edges[i + 1] if i < n - 1 else along
            if u1 - u0 <= 1e-6:
                continue
            nxt = lanes[i + 1] if i < n - 1 else lanes[i]
            paints = [theme.paint_of(m) for m in stage.marks]
            fill_bg = self._stage_soft(theme, stage, soft)
            if self.lanes and groups:
                jobs = []
                for k, g in enumerate(groups):
                    count = paints.count(g)
                    if count:
                        t0, b0 = lanes[i][k]
                        t1, b1 = nxt[k]
                        jobs.append(((u0, t0, u1, t1, b1, b0), [g] * count))
            else:
                ordered = sorted(paints, key=lambda p: groups.index(p)
                                 if p in groups else len(groups))
                t0, b0 = lanes[i][0][0], lanes[i][-1][1]
                t1, b1 = nxt[0][0], nxt[-1][1]
                jobs = [((u0, t0, u1, t1, b1, b0), ordered)]
            for quad, members in jobs:
                centres, r = self._pack(quad, len(members), self._radius(stage),
                                        inset)
                for (u, v), paint in zip(centres, members):
                    cx, cy = P(u, v)
                    edge = theme.edge_for_fill(paint, ground=fill_bg)
                    if edge:
                        sw = theme.hairline * 0.6
                        canvas.circle(cx, cy, max(0.2, r - sw / 2), fill=paint,
                                      stroke=edge, stroke_width=sw)
                    else:
                        canvas.circle(cx, cy, r, fill=paint, stroke="none")

        if self.bypass:
            self._render_bypass(canvas, ox, oy, extents, theme, rise, cap)

        if horizontal and self.label_position in ("below", "above"):
            size = theme.size_px(self.text_size)
            line_h = theme.text_height(self.text_size)
            muted = theme.color_of("text_muted")
            for centre, line, text in self._side_label_lines(theme):
                cx = ox + centre
                if self.label_position == "below":
                    base = (oy + self.height + theme.unit * 0.35
                            + line * line_h + size * 0.88)
                else:  # pragma: no cover - symmetrical, rarely used
                    base = oy - theme.unit * 0.35 - line * line_h
                canvas.text(cx, base, text, size=size, fill=muted,
                            anchor="middle")
        elif not horizontal:
            self._render_right_labels(canvas, ox, oy, theme)

    def _render_bypass(self, canvas: Canvas, ox: float, oy: float,
                       extents: List[float], theme: Theme,
                       rise: float, cap: float) -> None:
        along = self._along
        # The arc leaves a bracket that spans the whole mouth, every lane,
        # just before it: the whole inlet steps aside, not the group in
        # the lane nearest the arc. It lands on the neck's near edge at
        # its middle, pointing into the survivors, never on the outlet
        # corner where the wire leaving the funnel starts.
        taper = self._geometry(theme)[2]
        lead = self._bypass_lead(theme)
        spine_u, tick_u = -lead * 0.6, -lead * 0.15
        end_u = (taper + along) / 2.0
        half = extents[0] / 2
        stroke = theme.color_of("text_muted")
        bracket = [self._point(ox, oy, tick_u, -half),
                   self._point(ox, oy, spine_u, -half),
                   self._point(ox, oy, spine_u, half),
                   self._point(ox, oy, tick_u, half)]
        canvas.path("M " + " L ".join(f"{px:.3f},{py:.3f}"
                                      for px, py in bracket),
                    fill="none", stroke=stroke, stroke_width=theme.hairline)
        s = bracket[1]
        e = self._point(ox, oy, end_u, -extents[-1] / 2)
        lead_in = ""
        if self.bypass_to == "outlet":
            # From the bracket's centre (the mouth's centre line) out past
            # the bracket and up level with the mouth's corner, then over
            # the body to the outlet's own end: the whole pool steps aside.
            mid = self._point(ox, oy, spine_u, 0.0)
            out = self._point(ox, oy, -lead, 0.0)
            s = self._point(ox, oy, -lead, -half)
            e = self._point(ox, oy, along, -extents[-1] / 2)
            lead_in = (f"M {mid[0]:.3f},{mid[1]:.3f} L {out[0]:.3f},"
                       f"{out[1]:.3f} L ")
        head = canvas.define_arrow_marker(
            color=stroke, stroke_width=theme.hairline,
            arrow_size=max(2.4, theme.arrow_size * 0.75),
            name_hint="funnelbypass")
        # the outlet landing leaves and arrives square to the flow, so the
        # arc clears the mouth's corner and ends on the outlet's end
        k1, k2 = (0.0, 1.0) if self.bypass_to == "outlet" else (0.18, 0.86)
        if self.orientation == "horizontal":
            apex = oy - rise * 0.92
            c1 = (s[0] + (e[0] - s[0]) * k1, apex)
            c2 = (s[0] + (e[0] - s[0]) * k2, apex)
            ink = (min(s[0], e[0]), apex, max(s[0], e[0]), max(s[1], e[1]))
        else:
            apex = ox - rise * 0.92
            c1 = (apex, s[1] + (e[1] - s[1]) * k1)
            c2 = (apex, s[1] + (e[1] - s[1]) * k2)
            ink = (apex, min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
        if lead_in:
            ink = (min(ink[0], mid[0], out[0]), min(ink[1], mid[1], out[1]),
                   max(ink[2], mid[0], out[0]), max(ink[3], mid[1], out[1]))
        d = (f"{lead_in or 'M '}{s[0]:.3f},{s[1]:.3f} C {c1[0]:.3f},{c1[1]:.3f} "
             f"{c2[0]:.3f},{c2[1]:.3f} {e[0]:.3f},{e[1]:.3f}")
        canvas.path(d, fill="none", stroke=stroke,
                    stroke_width=theme.hairline, dasharray="1.6,1.2",
                    marker_end=head, ink_bbox=ink)
        lines = self._bypass_lines()
        if lines:
            size = theme.size_px(self.text_size)
            line_h = theme.text_height(self.text_size)
            muted = theme.color_of("text_muted")
            if self.orientation == "horizontal":
                # Centred over the box (the bracket and the body); the
                # measured box is at least as wide as the caption, so it
                # never leaves the box. It sits
                # clear of the arc, whose peak (a Bezier with both controls
                # at ``apex``) reaches three quarters of the way up.
                cx = (ox - self._body_offset(theme)[0]
                      + self.measure(theme).w / 2)
                for k, line in enumerate(lines):
                    base = oy - rise - cap + k * line_h + size * 0.88
                    canvas.text(cx, base, line, size=size, fill=muted,
                                anchor="middle")
            else:
                cy = oy + self.height / 2
                for k, line in enumerate(lines):
                    cx = ox - rise - cap + k * line_h + line_h / 2
                    canvas.text(cx, cy, line, size=size, fill=muted,
                                anchor="middle", rotate=-90)
