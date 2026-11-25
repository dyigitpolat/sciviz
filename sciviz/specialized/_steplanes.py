"""StepLanes: lanes over discrete time steps, with windows, marks and links.

A schedule drawn on a step grid: each lane is one unit of work (a layer's
cores, a buffer, a stage), its *window* is the run of steps during which it
is enabled (a thin bar over exactly those steps), its *marks* are the steps
at which it emits or receives an event (a dot at the step centre), and
*links* are arrows from a mark in one lane to a step in another (or the
same) lane, so that "an event emitted at step t arrives at step t + d" is
drawn, not described. Faint vertical gridlines run through the step centres
under one axis of step numbers. Lanes are gathered into groups (one scenario
each) with a group label on the left; a group's note (an outcome) is set
either as the label's last line or right of the grid. A ``bar`` lane draws a
quantity on the grid's own width (a measured share) with its value after
the bar, so a measurement lines up with the schedule above it.

Unlike :class:`Timeline` (a continuous axis with task bars), the grid is
discrete: every step is a column of equal width, so the eye can compare one
step across all lanes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme

LANE_KINDS = ("window", "store", "bar")
MARK_SHAPES = ("dot", "tick")
MARK_KINDS = ("dot", "diamond")
NOTE_PLACES = ("label", "right")


@dataclass(frozen=True)
class StepMark:
    """A mark with its own shape or colour: ``StepLane(marks=[0, StepMark(2, "diamond")])``.

    ``shape`` is ``"dot"`` or ``"diamond"`` (e.g. the step where two streams
    meet); ``color`` overrides the lane's mark colour.
    """

    step: int
    shape: str = "dot"
    color: Optional[str] = None

    def __post_init__(self):
        if self.shape not in MARK_KINDS:
            raise ValueError(f"StepMark.shape must be one of {MARK_KINDS}; got {self.shape!r}")


def _mark(m) -> "StepMark":
    return m if isinstance(m, StepMark) else StepMark(int(m))


@dataclass(frozen=True)
class StepLane:
    """One lane of a :class:`StepLanes` grid.

    Parameters
    ----------
    label : str
        Lane label, left of the grid.
    window : (first, last), optional
        Inclusive step range during which the lane is enabled: a thin bar
        over exactly those steps (from the left edge of ``first``'s column
        to the right edge of ``last``'s).
    marks : sequence of int or StepMark
        Steps with an event mark at the column centre (a :class:`StepMark`
        gives one mark its own shape or colour).
    ghosts : sequence of int
        Steps with a ghost mark (hollow, in the structure colour): where an
        event would have been.
    color : str, optional
        Colour of the marks; default the text ink. For a ``bar`` lane, the
        bar's fill.
    window_color : str, optional
        Outline colour of the window bar (its fill stays the theme's light
        structure tint); default the border colour.
    kind : str
        ``"window"`` (default); ``"store"``: a buffer, a dashed outline over
        every step with its marks inside; ``"bar"``: a solid bar of
        ``share`` of the grid width from the grid's left edge, with
        ``value`` set after it.
    share : float
        ``bar`` lanes: the bar length as a share of the grid width (0 to 1).
    value : str or Element, optional
        ``bar`` lanes: the value set after the bar.
    key : str, optional
        Name that :class:`StepLink` endpoints use; defaults to ``label``.
    tag : str, optional
        A short muted tag right of the grid (e.g. the pass that runs the
        lane).
    """

    label: str
    window: Optional[Tuple[float, float]] = None
    marks: Sequence[int] = ()
    ghosts: Sequence[int] = ()
    color: Optional[str] = None
    window_color: Optional[str] = None
    kind: str = "window"
    share: float = 0.0
    value: Optional[Union[str, Element]] = None
    key: Optional[str] = None
    tag: Optional[str] = None

    def __post_init__(self):
        if self.kind not in LANE_KINDS:
            raise ValueError(f"StepLane.kind must be one of {LANE_KINDS}; "
                             f"got {self.kind!r}")
        if self.window is not None and self.window[1] < self.window[0]:
            raise ValueError(f"StepLane.window must be (first, last) with "
                             f"first <= last; got {self.window!r}")
        if not 0.0 <= float(self.share) <= 1.0:
            raise ValueError(f"StepLane.share must be within 0 and 1; got {self.share!r}")

    @property
    def name(self) -> str:
        return self.key if self.key is not None else self.label


@dataclass(frozen=True)
class StepGroup:
    """A group of lanes (one scenario) with a label and a note.

    ``label`` is set left of the lane labels; ``"\\n"`` breaks it into
    lines, vertically centred on the group. ``note`` (a string or any
    :class:`Element`, e.g. a styled outcome ``Text``) is set as the label's
    last line or right of the grid (``StepLanes(notes=...)``). A group grows
    taller than its lanes when its label and note need more lines than it
    has lanes. ``cuts`` lists lane indices after which a dashed hairline
    crosses the lane labels and the grid (e.g. a pass boundary).
    """

    label: str = ""
    lanes: Sequence[StepLane] = ()
    note: Optional[Union[str, Element]] = None
    cuts: Sequence[int] = ()


@dataclass(frozen=True)
class StepLink:
    """An arrow from ``src = (lane key, step)`` to ``dst = (lane key, step)``.

    Between two lanes the arrow runs from the edge of the source mark to the
    edge of the target mark along the line joining their centres; within one
    lane it runs horizontally. ``color`` defaults to the links' ink.
    ``bend`` curves the link (a quadratic arc whose middle leaves the straight
    line by ``bend`` times the link length; positive bends to the left of the
    direction of travel, i.e. below-left for a link running down and right),
    so a stream that skips a lane can pass beside the marks between; ``dashed``
    dashes its line. Both keep a second stream visibly apart from the first.
    """

    src: Tuple[str, int]
    dst: Tuple[str, int]
    color: Optional[str] = None
    bend: float = 0.0
    dashed: bool = False


class StepLanes(Element):
    """Lanes over a grid of discrete time steps.

    Parameters
    ----------
    groups : sequence of StepGroup or StepLane
        The lanes, top to bottom; bare lanes form one unlabelled group.
    steps : sequence of int
        The step labels, one column each, left to right (e.g. ``range(5)``).
        Windows, marks and links name steps by these labels.
    links : sequence of StepLink
        Arrows between marks.
    step_w : float, optional
        Column width in px. ``None`` with ``width`` given: the columns share
        what the labels (and right-hand notes) leave of ``width``; with
        neither: three units.
    width : float, optional
        Total width in px (see ``step_w``).
    lane_h : float, optional
        Lane pitch in px; default the label line height.
    label_size : str
        Size token of every label, step number, note and bar value.
    axis_title : str, optional
        Title of the step axis, set in the axis row.
    axis_title_side : str
        ``"left"`` (default): right-aligned against the first step number,
        in the label columns; ``"right"``: after the last step number.
    corner : Element, optional
        Content for the label columns of the axis row (top left); the label
        columns widen to hold it (and a left axis title after it).
    notes : str
        ``"label"`` (default): a group's note is the last line of its label;
        ``"right"``: notes form a column right of the grid.
    mark : str
        ``"dot"`` (default, a filled disc) or ``"tick"`` (a vertical bar).
    mark_size : float, optional
        Dot diameter (or tick height) in px; default a third of the text
        size.
    gridlines : bool
        Faint vertical lines through the step centres over every group that
        has a window or store lane.
    group_gap : float, optional
        Vertical room between groups (default a third of a unit), split by
        a hairline rule when ``rules`` is true.
    rules : bool
        Draw a hairline between groups.
    """

    def __init__(self, groups: Sequence[Union[StepGroup, StepLane]], *,
                 steps: Sequence[int],
                 links: Sequence[StepLink] = (),
                 step_w: Optional[float] = None,
                 width: Optional[float] = None,
                 lane_h: Optional[float] = None,
                 label_size: str = "small",
                 axis_title: Optional[str] = None,
                 axis_title_side: str = "left",
                 corner: Optional[Element] = None,
                 notes: str = "label",
                 mark: str = "dot",
                 mark_size: Optional[float] = None,
                 gridlines: bool = True,
                 group_gap: Optional[float] = None,
                 rules: bool = True):
        if axis_title_side not in ("left", "right"):
            raise ValueError("StepLanes.axis_title_side must be 'left' or 'right'; "
                             f"got {axis_title_side!r}")
        if notes not in NOTE_PLACES:
            raise ValueError(f"StepLanes.notes must be one of {NOTE_PLACES}; got {notes!r}")
        if mark not in MARK_SHAPES:
            raise ValueError(f"StepLanes.mark must be one of {MARK_SHAPES}; got {mark!r}")
        gs: List[StepGroup] = []
        loose: List[StepLane] = []
        for g in groups:
            if isinstance(g, StepLane):
                loose.append(g)
                continue
            if loose:
                gs.append(StepGroup(lanes=tuple(loose)))
                loose = []
            gs.append(g)
        if loose:
            gs.append(StepGroup(lanes=tuple(loose)))
        self.groups = gs
        self.steps = [int(s) for s in steps]
        if not self.steps:
            raise ValueError("StepLanes needs at least one step")
        self.links = list(links)
        self.step_w = step_w
        self.width = width
        self.lane_h = lane_h
        self.label_size = label_size
        self.axis_title = axis_title
        self.axis_title_side = axis_title_side
        self.corner = corner
        self.notes = notes
        self.mark = mark
        self.mark_size = mark_size
        self.gridlines = gridlines
        self.group_gap = group_gap
        self.rules = rules
        names = [ln.name for g in self.groups for ln in g.lanes]
        dup = {n for n in names if names.count(n) > 1}
        keyed = {ln.name for g in self.groups for ln in g.lanes if ln.key is not None}
        if dup & keyed:
            raise ValueError(f"StepLanes lane keys must be unique: {sorted(dup & keyed)}")
        self._names = set(names)
        self._dup = dup
        for lk in self.links:
            for end in (lk.src, lk.dst):
                if end[0] not in self._names:
                    raise ValueError(f"StepLink names an unknown lane {end[0]!r}")
                if end[0] in dup:
                    raise ValueError(f"StepLink lane {end[0]!r} is ambiguous; "
                                     f"give the lanes distinct keys")
                if int(end[1]) not in self.steps:
                    raise ValueError(f"StepLink step {end[1]!r} is not a step")

    # -- pieces ---------------------------------------------------------------
    def _line_h(self, theme: Theme) -> float:
        return theme.text_height(self.label_size) * 0.86

    def _pitch(self, theme: Theme) -> float:
        return float(self.lane_h) if self.lane_h is not None else self._line_h(theme)

    def _gap(self, theme: Theme) -> float:
        return (float(self.group_gap) if self.group_gap is not None
                else theme.unit / 3.0)

    def _text(self, content, color="text_muted") -> Optional[Element]:
        if content is None:
            return None
        if isinstance(content, Element):
            return content
        from ..elements import Text
        return Text(str(content), size=self.label_size, color=color)

    def _label_lines(self, g: StepGroup) -> List[str]:
        return g.label.split("\n") if g.label else []

    def _columns(self, theme: Theme):
        """(group label width, lane label width, right note width, column gap)."""
        sz = self.label_size
        cg = theme.unit * 0.8
        gw = max((theme.text_width(line, sz) for g in self.groups
                  for line in self._label_lines(g) if line), default=0.0)
        right = 0.0
        for g in self.groups:
            note = self._text(g.note)
            if note is None:
                continue
            if self.notes == "label":
                gw = max(gw, note.measure(theme).w)
            else:
                right = max(right, note.measure(theme).w)
        lw = max((theme.text_width(ln.label, sz) for g in self.groups
                  for ln in g.lanes), default=0.0)
        tags = max((theme.text_width(ln.tag, sz) for g in self.groups
                    for ln in g.lanes if ln.tag), default=0.0)
        if tags:
            right = tags + (cg + right if right else 0.0)
        left = gw + cg if gw else 0.0          # label room left of the lane labels
        # the axis row's label room holds the corner, then the axis title
        need = self.corner.measure(theme).w if self.corner is not None else 0.0
        if self.axis_title and self.axis_title_side == "left":
            need += (cg if need else 0.0) + theme.text_width(self.axis_title, sz)
        lw = max(lw, need - left)
        if self.axis_title and self.axis_title_side == "right":
            right = max(right, theme.text_width(self.axis_title, sz))
        return gw, lw, right, cg

    def _tag_w(self, theme: Theme) -> float:
        return max((theme.text_width(ln.tag, self.label_size) for g in self.groups
                    for ln in g.lanes if ln.tag), default=0.0)

    def _step_w(self, theme: Theme) -> float:
        if self.step_w is not None:
            return float(self.step_w)
        gw, lw, nw, cg = self._columns(theme)
        if self.width is not None:
            fixed = (gw + cg if gw else 0.0) + lw + cg + (cg + nw if nw else 0.0)
            return max(theme.unit * 2.0, (float(self.width) - fixed) / len(self.steps))
        return theme.unit * 3.0

    def _group_heights(self, theme: Theme) -> List[float]:
        pitch, line = self._pitch(theme), self._line_h(theme)
        out = []
        for g in self.groups:
            note = self._text(g.note)
            note_h = note.measure(theme).h if note is not None else 0.0
            text_h = len(self._label_lines(g)) * line
            if self.notes == "label" and note is not None:
                text_h += max(line, note_h)
                note_h = 0.0
            out.append(max(len(g.lanes) * pitch, text_h, note_h))
        return out

    def _overhang(self, theme: Theme) -> float:
        """Text ink reach beyond a centred line box, top and bottom."""
        above, below = theme.text_ink_extents(self.label_size)
        return max(0.0, (above + below - self._line_h(theme)) / 2)

    def _axis_h(self, theme: Theme) -> float:
        corner = self.corner.measure(theme).h if self.corner is not None else 0.0
        return max(self._line_h(theme), corner)

    def _mark_d(self, theme: Theme) -> float:
        return (float(self.mark_size) if self.mark_size is not None
                else theme.size_px(self.label_size) / 3.0)

    def _bar_h(self, theme: Theme) -> float:
        return min(self._pitch(theme) * 0.5, self._mark_d(theme) * 1.9)

    def _bar_overflow(self, theme: Theme, grid_w: float, right: float) -> float:
        """How far a bar's value reaches past the grid and its right column."""
        reach = max((grid_w * float(ln.share) + theme.unit * 0.6
                     + self._text(ln.value, "text").measure(theme).w
                     for g in self.groups for ln in g.lanes
                     if ln.kind == "bar" and ln.value is not None), default=0.0)
        return max(0.0, reach - grid_w - right)

    def measure(self, theme: Theme) -> BBox:
        gw, lw, nw, cg = self._columns(theme)
        sw = self._step_w(theme)
        right = cg + nw if nw else 0.0
        w = ((gw + cg if gw else 0.0) + lw + cg + sw * len(self.steps) + right
             + self._bar_overflow(theme, sw * len(self.steps), right))
        hs = self._group_heights(theme)
        h = (self._axis_h(theme) + sum(hs) + self._gap(theme) * max(0, len(hs) - 1)
             + 2 * self._overhang(theme))
        return BBox(w, h)

    # -- drawing ------------------------------------------------------------
    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        gw, lw, nw, cg = self._columns(theme)
        sw = self._step_w(theme)
        pitch, line = self._pitch(theme), self._line_h(theme)
        size = theme.size_px(self.label_size)
        above, below = theme.text_ink_extents(self.label_size)
        asc = above - below                        # 2 x baseline offset for centring
        y = y + self._overhang(theme)
        x_lane = x + (gw + cg if gw else 0.0)
        x_grid = x_lane + lw + cg
        grid_w = sw * len(self.steps)
        x_note = x_grid + grid_w + cg
        x_end = x_note - cg + (cg + nw if nw else 0.0)
        col = {s: x_grid + (i + 0.5) * sw for i, s in enumerate(self.steps)}
        ink = theme.color_of("text")
        muted = theme.color_of("text_muted")
        border = theme.color_of("border")
        faint = _mix(border, 0.62)
        light = _mix(border, 0.78)

        # axis row: step numbers over the gridlines, the title beside them
        axis_h = self._axis_h(theme)
        ay = y + axis_h / 2 + asc / 2
        for s, cx in col.items():
            canvas.text(cx, ay, str(s), size=size, fill=muted, anchor="middle")
        if self.axis_title and self.axis_title_side == "left":
            canvas.text(x_grid - cg, ay, self.axis_title, size=size,
                        fill=muted, anchor="end")
        elif self.axis_title:
            canvas.text(x_note, ay, self.axis_title, size=size, fill=muted,
                        anchor="start")
        if self.corner is not None:
            cb = self.corner.measure(theme)
            self.corner.render(canvas, x, y + (axis_h - cb.h) / 2, theme)

        # lane geometry
        hs = self._group_heights(theme)
        gap = self._gap(theme)
        lanes: Dict[str, Tuple[StepLane, float]] = {}
        placed: List[Tuple[StepLane, float]] = []
        spans: List[Tuple[float, float]] = []      # gridline extents
        gy = y + axis_h
        for gi, (g, gh) in enumerate(zip(self.groups, hs)):
            if gi and self.rules:
                ry = gy - gap / 2
                canvas.line(x, ry, x_end, ry, stroke=light,
                            stroke_width=theme.hairline)
            top = gy + (gh - len(g.lanes) * pitch) / 2
            for li, ln in enumerate(g.lanes):
                cy = top + (li + 0.5) * pitch
                placed.append((ln, cy))
                if ln.name not in self._dup:
                    lanes[ln.name] = (ln, cy)
                canvas.text(x_lane, cy + asc / 2, ln.label, size=size,
                            fill=ink, anchor="start")
                if ln.tag:
                    canvas.text(x_note, cy + asc / 2, ln.tag, size=size,
                                fill=muted, anchor="start")
            for k in g.cuts:
                if 0 <= k < len(g.lanes) - 1:
                    cut_y = top + (k + 1) * pitch
                    canvas.line(x_lane, cut_y, x_grid + grid_w, cut_y, stroke=border,
                                stroke_width=theme.hairline, dasharray="1.6,1.6")
            if any(ln.kind != "bar" for ln in g.lanes):
                spans.append((gy - (gap / 2 if gi else 0.0), gy + gh + gap / 2))
            rows = self._label_lines(g)
            note = self._text(g.note)
            n_rows = len(rows) + (1 if note is not None and self.notes == "label" else 0)
            y0 = gy + gh / 2 - n_rows * line / 2
            for k, row in enumerate(rows):
                canvas.text(x, y0 + (k + 0.5) * line + asc / 2, row,
                            size=size, fill=ink, anchor="start")
            if note is not None:
                nb = note.measure(theme)
                if self.notes == "label":
                    ny = y0 + len(rows) * line + (line - nb.h) / 2
                    note.render(canvas, x, ny, theme)
                else:
                    nx = x_note + (self._tag_w(theme) + cg if self._tag_w(theme) else 0.0)
                    note.render(canvas, nx, gy + (gh - nb.h) / 2, theme)
            gy += gh + gap

        # gridlines through the step centres, under everything else
        if self.gridlines:
            last = spans[-1][1] - gap / 2 if spans else None
            for (s0, s1) in spans:
                s1 = min(s1, last) if last is not None else s1
                for cx in col.values():
                    canvas.line(cx, s0, cx, s1, stroke=faint,
                                stroke_width=theme.hairline)

        bar_h = self._bar_h(theme)
        d = self._mark_d(theme)
        r = d / 2

        # windows, stores and bars
        for ln, cy in placed:
            if ln.kind == "store":
                canvas.rect(x_grid, cy - bar_h / 2, grid_w, bar_h, fill="none",
                            stroke=border, stroke_width=theme.hairline,
                            dasharray="1.8,1.2")
            if ln.kind == "bar":
                bw = grid_w * float(ln.share)
                canvas.line(x_grid, cy - bar_h / 2 - 0.8, x_grid, cy + bar_h / 2 + 0.8,
                            stroke=muted, stroke_width=theme.hairline)
                if bw > 0:
                    canvas.rect(x_grid, cy - bar_h / 2, bw, bar_h,
                                fill=theme.color_of(ln.color or "text_muted"))
                val = self._text(ln.value, "text")
                if val is not None:
                    vb = val.measure(theme)
                    val.render(canvas, x_grid + bw + theme.unit * 0.6, cy - vb.h / 2, theme)
                continue
            if ln.window is not None:
                wc = theme.color_of(ln.window_color) if ln.window_color else border
                a, b = ln.window
                x0 = x_grid + self.steps.index(int(a)) * sw
                x1 = x_grid + (self.steps.index(int(b)) + 1) * sw
                width = theme.hairline if ln.window_color is None else theme.line
                canvas.rect(x0, cy - bar_h / 2, x1 - x0, bar_h, fill=light,
                            stroke=wc, stroke_width=width)

        # links, then marks on top
        for lk in self.links:
            sl, sy = lanes[lk.src[0]]
            dl, dy = lanes[lk.dst[0]]
            color = theme.color_of(lk.color) if lk.color else ink
            sx, dx = col[int(lk.src[1])], col[int(lk.dst[1])]
            gap_end = (r if self.mark == "dot" else d / 2) + 0.6
            dash = "2.2,1.4" if lk.dashed else None
            if self.mark == "tick" and abs(sy - dy) > 1e-6 and not lk.bend:
                down = dy > sy
                _arrow(canvas, sx, sy + (d / 2 if down else -d / 2),
                       dx, dy - (d / 2 if down else -d / 2), color, theme, dash)
                continue
            vx, vy = dx - sx, dy - sy
            length = math.hypot(vx, vy)
            if length < 2 * gap_end + 1.0:
                continue
            ux, uy = vx / length, vy / length
            if lk.bend:
                # quadratic arc: control point off the chord's middle, so the
                # arc's middle leaves the chord by bend x length
                off = 2.0 * float(lk.bend) * length
                qx, qy = (sx + dx) / 2 - uy * off, (sy + dy) / 2 + ux * off
                _curved_arrow(canvas, sx, sy, qx, qy, dx, dy, gap_end, color, theme, dash)
                continue
            _arrow(canvas, sx + ux * gap_end, sy + uy * gap_end,
                   dx - ux * gap_end, dy - uy * gap_end, color, theme, dash)

        for ln, cy in placed:
            if ln.kind == "bar":
                continue
            color = theme.color_of(ln.color) if ln.color else ink
            for s in ln.ghosts:
                if self.mark == "dot":
                    canvas.circle(col[int(s)], cy, r, fill="#ffffff", stroke=muted,
                                  stroke_width=theme.hairline)
                else:
                    canvas.line(col[int(s)], cy - d / 2, col[int(s)], cy + d / 2,
                                stroke=muted, stroke_width=theme.hairline * 1.4,
                                dasharray="1.2,0.9")
            for m in map(_mark, ln.marks):
                mc = theme.color_of(m.color) if m.color else color
                mx = col[int(m.step)]
                if m.shape == "diamond":
                    k = r * 1.45
                    canvas.polygon([(mx, cy - k), (mx + k, cy), (mx, cy + k), (mx - k, cy)],
                                   fill=mc)
                elif self.mark == "dot":
                    canvas.circle(mx, cy, r, fill=mc)
                else:
                    tw = max(1.1, theme.line * 1.5)
                    canvas.rect(mx - tw / 2, cy - d / 2, tw, d, fill=mc)


def _head(canvas: Canvas, x1: float, y1: float, ux: float, uy: float,
          head: float, color: str) -> Tuple[float, float]:
    """A small solid head with its tip at (x1, y1) pointing along (ux, uy)."""
    half = head * 0.45
    bx, by = x1 - ux * head, y1 - uy * head
    canvas.polygon([(x1, y1), (bx - uy * half, by + ux * half),
                    (bx + uy * half, by - ux * half)], fill=color)
    return bx, by


def _arrow(canvas: Canvas, x0: float, y0: float, x1: float, y1: float,
           color: str, theme: Theme, dash: Optional[str] = None) -> None:
    """A thin straight arrow whose small solid head ends exactly at (x1, y1)."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    ux, uy = dx / length, dy / length
    head = min(2.4, length * 0.6)
    bx, by = x1 - ux * head, y1 - uy * head
    canvas.line(x0, y0, bx + ux * 0.2, by + uy * 0.2, stroke=color,
                stroke_width=theme.hairline * 1.2, dasharray=dash)
    _head(canvas, x1, y1, ux, uy, head, color)


def _curved_arrow(canvas: Canvas, sx: float, sy: float, qx: float, qy: float,
                  dx: float, dy: float, gap: float, color: str, theme: Theme,
                  dash: Optional[str] = None) -> None:
    """A quadratic arc from (sx, sy) to (dx, dy) via control (qx, qy).

    Both ends stop ``gap`` short of the marks along the arc's own tangents,
    and the head points along the end tangent.
    """
    def unit(ax, ay):
        n = math.hypot(ax, ay) or 1.0
        return ax / n, ay / n
    u0 = unit(qx - sx, qy - sy)
    u1 = unit(dx - qx, dy - qy)
    p0 = (sx + u0[0] * gap, sy + u0[1] * gap)
    p1 = (dx - u1[0] * gap, dy - u1[1] * gap)
    head = 2.4
    bx, by = p1[0] - u1[0] * head, p1[1] - u1[1] * head
    canvas.path(f"M {p0[0]:.3f} {p0[1]:.3f} Q {qx:.3f} {qy:.3f} {bx + u1[0] * 0.2:.3f} "
                f"{by + u1[1] * 0.2:.3f}", stroke=color,
                stroke_width=theme.hairline * 1.2, dasharray=dash,
                ink_bbox=(min(p0[0], qx, bx), min(p0[1], qy, by),
                          max(p0[0], qx, bx), max(p0[1], qy, by)))
    _head(canvas, p1[0], p1[1], u1[0], u1[1], head, color)


def _mix(hex_color: str, amount: float) -> str:
    """``hex_color`` mixed toward white by ``amount`` (0 keeps it)."""
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return hex_color
    rgb = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(v + (255 - v) * amount):02x}" for v in rgb)
