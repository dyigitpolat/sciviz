"""Schematic primitives for spiking hardware: chips of cores, step rasters, small networks.

Three elements that draw an execution schedule as a picture rather than a chart:

* :class:`StepRaster` -- rows over discrete time steps where every step is one
  small block: a row's ``window`` lights its blocks in the row's hue, ``marks``
  are spike dots, a ``store`` row is a dashed buffer, and ``links`` are thin
  arrows between dots. ``cuts`` split the columns into phases side by side
  (e.g. two passes of one program) with a dashed vertical rule between them.
* :class:`CoreChip` -- a chip drawn as a row (or grid) of core blocks; a core
  carries a label, a hue and a strip of step cells under it with its window
  lit; an idle core is a dashed outline. ``links`` draw arrows between cores,
  straight between neighbours and as an arc over the cores for a skip.
* :class:`LayerNet` -- a small layered network: one column of nodes per layer,
  a label under each, fan edges between consecutive layers and skip edges as
  arcs over the top.

All three share one arrow (a thin line with a small solid head) and one dot.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from ..core import BBox, Canvas, Element, Theme
from ._steplanes import _arrow, _curved_arrow, _mix

ROW_KINDS = ("cells", "store", "blank")


def _register(canvas: Canvas, name: Optional[str], key, x: float, y: float, r: float) -> None:
    """Record a named point for :class:`PointArrows` (a no-op outside one)."""
    reg = getattr(canvas, "_sv_points", None)
    if name and reg is not None:
        reg[f"{name}:{key}"] = (x, y, r)


def _hue(theme: Theme, color) -> str:
    return theme.color_of(color) if color is not None else theme.color_of("text_muted")


# ---------------------------------------------------------------------------
# StepRaster
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RasterRow:
    """One row of a :class:`StepRaster`.

    ``window`` is a set of column indices, or ``(first, last)`` inclusive,
    whose blocks are lit in ``color``; the other blocks are faint outlines.
    ``marks`` are column indices with a spike dot. ``kind="store"`` draws a
    dashed buffer over the row's ``window`` (or every column) with its dots
    inside; ``kind="blank"`` keeps the row's place and draws only its dots.
    ``span = (first, last)`` limits the row to those columns (default all),
    and ``line`` puts it on a given line of the raster (default its order),
    so one line can hold a different row in each phase. ``tag`` is a short
    muted label (or any element, e.g. a styled outcome) right of the grid on
    the row's line.
    """

    label: str = ""
    color: Optional[str] = None
    window: Optional[Sequence[int]] = None
    marks: Sequence[int] = ()
    kind: str = "cells"
    span: Optional[Tuple[int, int]] = None
    line: Optional[int] = None
    tag: object = ""

    def __post_init__(self):
        if self.kind not in ROW_KINDS:
            raise ValueError(f"RasterRow.kind must be one of {ROW_KINDS}; got {self.kind!r}")

    def cols(self, n: int) -> range:
        a, b = self.span if self.span is not None else (0, n - 1)
        return range(int(a), int(b) + 1)

    def lit(self, n: int) -> set:
        if self.window is None:
            return set(self.cols(n)) if self.kind == "store" else set()
        w = list(self.window)
        if isinstance(self.window, tuple) and len(w) == 2:
            return set(range(int(w[0]), int(w[1]) + 1))
        return {int(c) for c in w}


@dataclass(frozen=True)
class RasterLink:
    """An arrow from dot ``src = (row, column)`` to dot ``dst = (row, column)``.

    Columns are indices into the raster's columns (step labels may repeat
    across phases). ``bend`` bows the arrow (a share of its length, positive
    to the left of travel); ``dashed`` dashes it.
    """

    src: Tuple[int, int]
    dst: Tuple[int, int]
    bend: float = 0.0
    dashed: bool = False
    color: Optional[str] = None


class StepRaster(Element):
    """Rows of step blocks: a schedule drawn as lit hardware over time.

    Parameters
    ----------
    rows : sequence of RasterRow
    steps : sequence
        Column labels left to right (e.g. ``[0, 1, 2, 3, 4]``; may repeat
        across phases).
    cell : float
        Column and row pitch in px; a block is ``block`` of it.
    cuts : sequence of int or (int, bool)
        Column indices before which the grid breaks: a gap of ``cut_gap``
        pitches with a dashed vertical hairline through it (``(index,
        False)``: the gap alone, e.g. between two scenarios).
    titles : sequence of (column, str)
        Phase titles above the grid, centred over the columns from that
        index to the next title (or cut).
    links : sequence of RasterLink
    axis : bool
        Step labels under the grid.
    axis_title : str, optional
        Set right of the last step label.
    axis_side : str
        ``"bottom"`` (default) or ``"top"``: the side of the step labels.
    name : str, optional
        Registers every cell centre as ``"name:row,col"`` for
        :class:`PointArrows`.
    label_size : str
        Size token of every text.
    """

    def __init__(self, rows: Sequence[RasterRow], steps: Sequence, *,
                 cell: float = 11.0, block: float = 0.74, cuts: Sequence[int] = (),
                 cut_gap: float = 1.6, titles: Sequence[Tuple[int, str]] = (),
                 links: Sequence[RasterLink] = (), axis: bool = True,
                 axis_title: Optional[str] = None, label_size: str = "small",
                 dot: float = 0.36, row_gap: float = 0.0, axis_side: str = "bottom",
                 name: Optional[str] = None):
        self.rows = list(rows)
        self.steps = list(steps)
        self.cell = float(cell)
        self.block = float(block)
        self.cuts, self.rules = [], {}
        for c in cuts:
            k, dashed = (c, True) if isinstance(c, int) else (int(c[0]), bool(c[1]))
            self.cuts.append(k)
            self.rules[k] = dashed
        self.cuts.sort()
        self.cut_gap = float(cut_gap)
        self.titles = [(int(c), str(t)) for c, t in titles]
        self.links = list(links)
        self.axis = bool(axis)
        self.axis_title = axis_title
        self.label_size = label_size
        self.dot = float(dot)
        self.row_gap = float(row_gap)
        if axis_side not in ("bottom", "top"):
            raise ValueError(f"StepRaster.axis_side must be 'bottom' or 'top'; got {axis_side!r}")
        self.axis_side = axis_side
        self.name = name
        n = len(self.steps)
        for lk in self.links:
            for (r, c) in (lk.src, lk.dst):
                if not (0 <= r < len(self.rows) and 0 <= c < n):
                    raise ValueError(f"RasterLink endpoint {(r, c)} outside the raster")

    # geometry ---------------------------------------------------------------
    def _label_w(self, theme: Theme) -> float:
        w = max((theme.text_width(r.label, self.label_size) for r in self.rows if r.label),
                default=0.0)
        return w + theme.unit * 0.8 if w else 0.0

    def _col_x(self, c: int) -> float:
        """Left edge of column ``c`` from the grid origin."""
        gaps = sum(1 for k in self.cuts if k <= c)
        return (c + gaps * self.cut_gap) * self.cell

    def _grid_w(self) -> float:
        return self._col_x(len(self.steps) - 1) + self.cell

    def _line(self, r: int) -> int:
        row = self.rows[r]
        return row.line if row.line is not None else r

    def _n_lines(self) -> int:
        return max((self._line(r) for r in range(len(self.rows))), default=-1) + 1

    def _row_y(self, r: int) -> float:
        return self._line(r) * self.cell * (1.0 + self.row_gap)

    def _grid_h(self) -> float:
        n = self._n_lines()
        return (n - 1) * self.cell * (1.0 + self.row_gap) + self.cell if n else 0.0

    def _title_h(self, theme: Theme) -> float:
        h = theme.text_height(self.label_size) + theme.unit * 0.3 if self.titles else 0.0
        return h + (self._axis_h(theme) if self.axis_side == "top" else 0.0)

    def _axis_h(self, theme: Theme) -> float:
        return theme.text_height(self.label_size) + theme.unit * 0.2 if self.axis else 0.0

    def _tail_w(self, theme: Theme) -> float:
        widths = [r.tag.measure(theme).w if isinstance(r.tag, Element)
                  else theme.text_width(r.tag, self.label_size) for r in self.rows if r.tag]
        if self.axis and self.axis_title:
            widths.append(theme.text_width(self.axis_title, self.label_size))
        if not widths:
            return 0.0
        return theme.unit * 0.6 + max(widths)

    def _arc_pad(self) -> float:
        """Room an arc between rows may bow out of the grid (left/right)."""
        pad = 0.0
        for lk in self.links:
            if lk.bend:
                (r0, c0), (r1, c1) = lk.src, lk.dst
                length = math.hypot((c1 - c0) * self.cell, (r1 - r0) * self.cell)
                pad = max(pad, abs(lk.bend) * length)
        return pad

    def measure(self, theme: Theme) -> BBox:
        w = self._label_w(theme) + self._grid_w() + self._tail_w(theme)
        for c, t in self.titles:
            w = max(w, self._label_w(theme) + self._col_x(c) + theme.text_width(t, self.label_size))
        h = self._title_h(theme) + self._grid_h()
        if self.axis_side == "bottom":
            h += self._axis_h(theme)
        return BBox(w, h)

    def cell_center(self, theme: Theme, row: int, col: int) -> Tuple[float, float]:
        """Centre of block (row, col) relative to the element's top left."""
        return (self._label_w(theme) + self._col_x(col) + self.cell / 2,
                self._title_h(theme) + self._row_y(row) + self.cell / 2)

    # paint ------------------------------------------------------------------
    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = theme.size_px(self.label_size)
        above, below = theme.text_ink_extents(self.label_size)
        asc = above - below
        ink, muted = theme.color_of("text"), theme.color_of("text_muted")
        border = theme.color_of("border")
        faint = _mix(border, 0.55)
        n = len(self.steps)
        gx = x + self._label_w(theme)
        gy = y + self._title_h(theme)
        side = self.cell * self.block
        inset = (self.cell - side) / 2
        r_dot = self.cell * self.dot / 2

        # phase titles
        bounds = sorted({c for c, _ in self.titles} | set(self.cuts) | {n})
        for c, t in self.titles:
            stop = min(b for b in bounds if b > c)
            x0, x1 = gx + self._col_x(c), gx + self._col_x(stop - 1) + self.cell
            canvas.text((x0 + x1) / 2, y + asc / 2 + self._title_h(theme) / 2 - theme.unit * 0.15,
                        t, size=size, fill=ink, anchor="middle")

        # cuts: a dashed vertical hairline through the middle of each gap
        for k in self.cuts:
            if not self.rules.get(k, True):
                continue
            cx = gx + self._col_x(k) - self.cut_gap * self.cell / 2
            top = y + (0.0 if self.titles else 0.0)
            bottom = gy + self._grid_h() + (self._axis_h(theme) if self.axis_side == "bottom" else 0)
            canvas.line(cx, top, cx, bottom,
                        stroke=border, stroke_width=theme.hairline, dasharray="1.6,1.6")

        # rows: labels, blocks, stores
        for r, row in enumerate(self.rows):
            ry = gy + self._row_y(r)
            if row.label:
                canvas.text(x, ry + self.cell / 2 + asc / 2, row.label, size=size,
                            fill=ink, anchor="start")
            if isinstance(row.tag, Element):
                tb = row.tag.measure(theme)
                row.tag.render(canvas, gx + self._grid_w() + theme.unit * 0.6,
                               ry + (self.cell - tb.h) / 2, theme)
            elif row.tag:
                canvas.text(gx + self._grid_w() + theme.unit * 0.6, ry + self.cell / 2 + asc / 2,
                            row.tag, size=size, fill=muted, anchor="start")
            lit = row.lit(n)
            hue = _hue(theme, row.color)
            if row.kind == "cells":
                for c in row.cols(n):
                    bx = gx + self._col_x(c) + inset
                    if c in lit:
                        canvas.rect(bx, ry + inset, side, side, fill=_mix(hue, 0.72),
                                    stroke=hue, stroke_width=theme.hairline, rx=0.6)
                    else:
                        canvas.rect(bx, ry + inset, side, side, fill="none",
                                    stroke=faint, stroke_width=theme.hairline, rx=0.6)
            elif row.kind == "store":
                cols = sorted(lit)
                runs, start = [], None
                for c in cols:
                    if start is None:
                        start = prev = c
                    elif c == prev + 1 and not any(k == c for k in self.cuts):
                        prev = c
                    else:
                        runs.append((start, prev))
                        start = prev = c
                if start is not None:
                    runs.append((start, prev))
                for a, b in runs:
                    x0 = gx + self._col_x(a) + inset
                    x1 = gx + self._col_x(b) + self.cell - inset
                    canvas.rect(x0, ry + inset, x1 - x0, side, fill="none", stroke=muted,
                                stroke_width=theme.hairline, dasharray="1.8,1.2", rx=0.6)

        # links, then dots on top
        for lk in self.links:
            sx, sy = self.cell_center(theme, *lk.src)
            dx, dy = self.cell_center(theme, *lk.dst)
            sx, sy, dx, dy = sx + x, sy + y, dx + x, dy + y
            color = theme.color_of(lk.color) if lk.color else ink
            dash = "2.2,1.4" if lk.dashed else None
            gap_end = r_dot + 0.6
            vx, vy = dx - sx, dy - sy
            length = math.hypot(vx, vy)
            if length < 2 * gap_end + 1.0:
                continue
            ux, uy = vx / length, vy / length
            if lk.bend:
                off = 2.0 * float(lk.bend) * length
                qx, qy = (sx + dx) / 2 - uy * off, (sy + dy) / 2 + ux * off
                _curved_arrow(canvas, sx, sy, qx, qy, dx, dy, gap_end, color, theme, dash)
            else:
                _arrow(canvas, sx + ux * gap_end, sy + uy * gap_end,
                       dx - ux * gap_end, dy - uy * gap_end, color, theme, dash)
        for r, row in enumerate(self.rows):
            for c in row.marks:
                cx, cy = self.cell_center(theme, r, int(c))
                canvas.circle(x + cx, y + cy, r_dot, fill=ink)
            for c in row.cols(n):
                cx, cy = self.cell_center(theme, r, c)
                _register(canvas, self.name, f"{r},{c}", x + cx, y + cy,
                          r_dot if c in row.marks else side / 2)

        # axis
        if self.axis:
            if self.axis_side == "top":
                ay = gy - self._axis_h(theme) / 2 + asc / 2
            else:
                ay = gy + self._grid_h() + self._axis_h(theme) / 2 + asc / 2
            for c, s in enumerate(self.steps):
                canvas.text(gx + self._col_x(c) + self.cell / 2, ay, str(s), size=size,
                            fill=muted, anchor="middle")
            if self.axis_title:
                canvas.text(gx + self._grid_w() + theme.unit * 0.6, ay, self.axis_title,
                            size=size, fill=muted, anchor="start")


# ---------------------------------------------------------------------------
# CoreChip
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Core:
    """One core of a :class:`CoreChip`: ``color=None`` is an idle core.

    ``window`` (first, last) lights those cells of the core's step strip;
    ``marks`` are steps with a spike dot in the strip.
    """

    label: str = ""
    color: Optional[str] = None
    window: Optional[Tuple[int, int]] = None
    marks: Sequence[int] = ()


@dataclass(frozen=True)
class CoreLink:
    """An arrow from core ``src`` to core ``dst`` (indices); ``bend`` > 0 arcs it
    over the cores by that share of the distance (a skip)."""

    src: int
    dst: int
    bend: float = 0.0
    dashed: bool = False


class CoreChip(Element):
    """A chip as a row (or grid) of core blocks with step windows.

    Parameters
    ----------
    cores : sequence of Core
    columns : int, optional
        Cores per row (default: all in one row).
    steps : int
        Cells of the window strip under each core (0: no strip).
    core : float
        Side of a core block in px.
    gap : float
        Space between cores in px (default: the core's side times 0.55).
    links : sequence of CoreLink
    label_size : str
    strip_h : float, optional
        Height of the step strip (default nine tenths of a cell's width).
    name : str, optional
        Registers ``"name:core"`` (block centre) and ``"name:core,step"``
        (strip cell centre) for :class:`PointArrows`.
    """

    def __init__(self, cores: Sequence[Core], *, columns: Optional[int] = None,
                 steps: int = 0, core: float = 20.0, gap: Optional[float] = None,
                 links: Sequence[CoreLink] = (), label_size: str = "small",
                 pad: float = 4.0, strip_h: Optional[float] = None,
                 name: Optional[str] = None):
        self.cores = list(cores)
        self.columns = int(columns or max(1, len(self.cores)))
        self.steps = int(steps)
        self.core = float(core)
        self.gap = float(gap if gap is not None else core * 0.55)
        self.links = list(links)
        self.label_size = label_size
        self.pad = float(pad)
        self.strip_h = strip_h
        self.name = name
        for lk in self.links:
            if not (0 <= lk.src < len(self.cores) and 0 <= lk.dst < len(self.cores)):
                raise ValueError(f"CoreLink {lk.src}->{lk.dst} names no core")

    def _strip_h(self) -> float:
        if not self.steps:
            return 0.0
        return float(self.strip_h) if self.strip_h is not None else self.core / self.steps * 0.9

    def _strip_gap(self) -> float:
        return self.core * 0.12 if self.steps else 0.0

    def _unit_h(self) -> float:
        return self.core + self._strip_gap() + self._strip_h()

    def _rows(self) -> int:
        return math.ceil(len(self.cores) / self.columns)

    def _arc_h(self) -> float:
        h = 0.0
        for lk in self.links:
            if lk.bend > 0:
                d = abs(self._pos(lk.dst)[0] - self._pos(lk.src)[0])
                h = max(h, lk.bend * d)
        return h

    def _pos(self, i: int) -> Tuple[float, float]:
        """Top left of core ``i`` relative to the chip outline's inner origin."""
        r, c = divmod(i, self.columns)
        return (c * (self.core + self.gap), r * (self._unit_h() + self.gap))

    def _inner(self) -> Tuple[float, float]:
        cols = min(self.columns, len(self.cores))
        w = cols * self.core + (cols - 1) * self.gap
        h = self._rows() * self._unit_h() + (self._rows() - 1) * self.gap
        return w, h

    def measure(self, theme: Theme) -> BBox:
        w, h = self._inner()
        return BBox(w + 2 * self.pad, h + 2 * self.pad + self._arc_h())

    def core_box(self, i: int) -> Tuple[float, float, float, float]:
        """(x, y, w, h) of core ``i``'s block relative to the element's top left."""
        px, py = self._pos(i)
        return (self.pad + px, self.pad + self._arc_h() + py, self.core, self.core)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = theme.size_px(self.label_size)
        above, below = theme.text_ink_extents(self.label_size)
        asc = above - below
        ink = theme.color_of("text")
        border = theme.color_of("border")
        faint = _mix(border, 0.55)
        w, h = self._inner()
        canvas.rect(x, y, w + 2 * self.pad, h + 2 * self.pad + self._arc_h(),
                    fill=_mix(border, 0.93), stroke=border, stroke_width=theme.hairline, rx=1.5)
        ox, oy = x + self.pad, y + self.pad + self._arc_h()
        for i, core in enumerate(self.cores):
            px, py = self._pos(i)
            cx, cy = ox + px, oy + py
            if core.color is None:
                canvas.rect(cx, cy, self.core, self.core, fill="#ffffff", stroke=faint,
                            stroke_width=theme.hairline, dasharray="1.6,1.2", rx=0.8)
            else:
                hue = theme.color_of(core.color)
                canvas.rect(cx, cy, self.core, self.core, fill=_mix(hue, 0.72), stroke=hue,
                            stroke_width=theme.hairline * 1.2, rx=0.8)
                if core.label:
                    canvas.text(cx + self.core / 2, cy + self.core / 2 + asc / 2, core.label,
                                size=size, fill=ink, anchor="middle")
            _register(canvas, self.name, f"{i}", cx + self.core / 2, cy + self.core / 2,
                      self.core / 2)
            if self.steps and core.color is not None:
                sw = self.core / self.steps
                sh = self._strip_h()
                sy = cy + self.core + self._strip_gap()
                win = core.window
                hue = theme.color_of(core.color)
                r_dot = min(sw, sh) * 0.27
                for s in range(self.steps):
                    on = win is not None and win[0] <= s <= win[1]
                    canvas.rect(cx + s * sw + 0.35, sy, sw - 0.7, sh,
                                fill=_mix(hue, 0.72) if on else "#ffffff",
                                stroke=hue if on else faint, stroke_width=theme.hairline * 0.8)
                    mx, my = cx + (s + 0.5) * sw, sy + sh / 2
                    if s in core.marks:
                        canvas.circle(mx, my, r_dot, fill=ink)
                    _register(canvas, self.name, f"{i},{s}", mx, my,
                              r_dot if s in core.marks else sh / 2)
        # links
        for lk in self.links:
            (sx, sy), (dx, dy) = self._pos(lk.src), self._pos(lk.dst)
            color = ink
            dash = "2.2,1.4" if lk.dashed else None
            if lk.bend > 0:
                x0, x1 = ox + sx + self.core / 2, ox + dx + self.core / 2
                y0 = oy + sy
                hgt = lk.bend * abs(x1 - x0)
                qx, qy = (x0 + x1) / 2, y0 - 2 * hgt
                _curved_arrow(canvas, x0, y0, qx, qy, x1, y0, 0.0, color, theme, dash)
            else:
                ymid = oy + sy + self.core / 2
                x0 = ox + sx + self.core + 0.8
                x1 = ox + dx - 0.8
                _arrow(canvas, x0, ymid, x1, ymid, color, theme, dash)


# ---------------------------------------------------------------------------
# LayerNet
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NetLayer:
    """One layer of a :class:`LayerNet`: ``nodes`` in one column, a label under it."""

    label: str = ""
    nodes: int = 3
    color: Optional[str] = None


class LayerNet(Element):
    """A small layered network: node columns, fan edges, skip arcs, labels.

    Parameters
    ----------
    layers : sequence of NetLayer
    skips : sequence of (int, int)
        Layer pairs joined by an arc over the top (top node to top node).
    spacing : float
        Horizontal distance between layer columns in px.
    node : float
        Node diameter in px.
    pitch : float
        Vertical distance between nodes of one layer in px.
    skip_bend : float
        Height of a skip arc as a share of its span.
    """

    def __init__(self, layers: Sequence[NetLayer], *, skips: Sequence[Tuple[int, int]] = (),
                 spacing: float = 22.0, node: float = 5.0, pitch: float = 8.0,
                 skip_bend: float = 0.28, label_size: str = "small"):
        self.layers = list(layers)
        self.skips = [(int(a), int(b)) for a, b in skips]
        self.spacing = float(spacing)
        self.node = float(node)
        self.pitch = float(pitch)
        self.skip_bend = float(skip_bend)
        self.label_size = label_size

    def _span_h(self) -> float:
        n = max((ly.nodes for ly in self.layers), default=1)
        return (n - 1) * self.pitch + self.node

    def _arc_h(self) -> float:
        h = 0.0
        for a, b in self.skips:
            h = max(h, self.skip_bend * abs(b - a) * self.spacing)
        return h

    def _label_band(self, theme: Theme) -> float:
        return theme.text_height(self.label_size) + theme.unit * 0.3

    def measure(self, theme: Theme) -> BBox:
        w = (len(self.layers) - 1) * self.spacing + self.node
        for i, ly in enumerate(self.layers):
            tw = theme.text_width(ly.label, self.label_size)
            w = max(w, i * self.spacing + self.node / 2 + tw / 2)
        lw0 = theme.text_width(self.layers[0].label, self.label_size) if self.layers else 0
        self._lpad = max(0.0, lw0 / 2 - self.node / 2)
        return BBox(w + self._lpad, self._arc_h() + self._span_h() + self._label_band(theme))

    def node_xy(self, theme: Theme, layer: int, k: int) -> Tuple[float, float]:
        self.measure(theme)
        ly = self.layers[layer]
        y0 = self._arc_h() + (self._span_h() - ((ly.nodes - 1) * self.pitch + self.node)) / 2
        return (self._lpad + layer * self.spacing + self.node / 2,
                y0 + self.node / 2 + k * self.pitch)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = theme.size_px(self.label_size)
        above, below = theme.text_ink_extents(self.label_size)
        asc = above - below
        ink, edge = theme.color_of("text"), _mix(theme.color_of("border"), 0.25)
        r = self.node / 2
        for i in range(len(self.layers) - 1):
            for a in range(self.layers[i].nodes):
                for b in range(self.layers[i + 1].nodes):
                    x0, y0 = self.node_xy(theme, i, a)
                    x1, y1 = self.node_xy(theme, i + 1, b)
                    canvas.line(x + x0, y + y0, x + x1, y + y1, stroke=edge,
                                stroke_width=theme.hairline * 0.8)
        for a, b in self.skips:
            x0, y0 = self.node_xy(theme, a, 0)
            x1, y1 = self.node_xy(theme, b, 0)
            top = min(y0, y1) - r
            hgt = self.skip_bend * abs(b - a) * self.spacing
            qx, qy = (x0 + x1) / 2, top - 2 * hgt + r
            canvas.path(f"M {x + x0:.3f} {y + y0 - r:.3f} Q {x + qx:.3f} {y + qy:.3f} "
                        f"{x + x1:.3f} {y + y1 - r:.3f}", stroke=edge,
                        stroke_width=theme.hairline * 1.2,
                        ink_bbox=(x + x0, y + top - hgt, x + x1, y + y0))
        for i, ly in enumerate(self.layers):
            hue = _hue(theme, ly.color)
            for k in range(ly.nodes):
                nx, ny = self.node_xy(theme, i, k)
                canvas.circle(x + nx, y + ny, r, fill=_mix(hue, 0.72), stroke=hue,
                              stroke_width=theme.hairline)
            lx = x + self._lpad + i * self.spacing + self.node / 2
            ly_ = y + self._arc_h() + self._span_h() + self._label_band(theme) / 2 + asc / 2 \
                + theme.unit * 0.15
            canvas.text(lx, ly_, ly.label, size=size, fill=ink, anchor="middle")


# ---------------------------------------------------------------------------
# ThinArrow
# ---------------------------------------------------------------------------
class ThinArrow(Element):
    """A short horizontal arrow drawn like the links of these schematics.

    The thin line with a small solid head that :class:`StepRaster`,
    :class:`CoreChip` and :class:`StepLanes` draw inside, as an inline element
    between blocks of a ``Row``, so one figure keeps one arrow style.
    """

    def __init__(self, length: float = 14.0, *, color: Optional[str] = None,
                 pad: float = 2.0):
        self.length = float(length)
        self.color = color
        self.pad = float(pad)

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.length + 2 * self.pad, 6.0)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        color = theme.color_of(self.color) if self.color else theme.color_of("text")
        _arrow(canvas, x + self.pad, y + 3.0, x + self.pad + self.length, y + 3.0, color, theme)


# ---------------------------------------------------------------------------
# PointArrows
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PointArrow:
    """An arrow between two named points (``"element-name:key"``).

    ``bend`` bows it (a share of its length, positive to the left of travel);
    ``dashed`` dashes it. ``enter`` (``"below"``, ``"above"``, ``"left"``,
    ``"right"``) makes it a curve that leaves the source level, towards the
    destination, and enters the destination from that side, so an arrow into
    one cell of a strip arrives across the strip instead of along it. Both
    ends stop at the radius the point registered (a dot's edge, a cell's half
    height) plus a small clearance.
    """

    src: str
    dst: str
    bend: float = 0.0
    dashed: bool = False
    color: Optional[str] = None
    enter: Optional[str] = None

    def __post_init__(self):
        if self.enter not in (None, "below", "above", "left", "right"):
            raise ValueError(f"PointArrow.enter must be below, above, left, right or None; "
                             f"got {self.enter!r}")


_ENTER = {"below": (0.0, -1.0), "above": (0.0, 1.0), "left": (1.0, 0.0), "right": (-1.0, 0.0)}


class PointArrows(Element):
    """``child`` with arrows between points its elements register by name.

    A :class:`StepRaster` or :class:`CoreChip` given ``name=`` registers its
    cells (``"name:row,col"``, ``"name:core,step"``) while it renders; the
    arrows are drawn over the child afterwards, so one arrow can join a dot
    of one element to a cell of another (a stored spike entering a core's
    window at its step) without coordinates.
    """

    def __init__(self, child: Element, arrows: Sequence[PointArrow] = ()):
        self.child = child
        self.arrows = list(arrows)

    def measure(self, theme: Theme) -> BBox:
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        outer = getattr(canvas, "_sv_points", None)
        canvas._sv_points = {} if outer is None else outer
        try:
            self.child.render(canvas, x, y, theme)
            points = dict(canvas._sv_points)
        finally:
            canvas._sv_points = outer
        for a in self.arrows:
            for key in (a.src, a.dst):
                if key not in points:
                    raise KeyError(f"PointArrows: no element registered the point {key!r}")
            sx, sy, sr = points[a.src]
            dx, dy, dr = points[a.dst]
            color = theme.color_of(a.color) if a.color else theme.color_of("text")
            dash = "2.2,1.4" if a.dashed else None
            vx, vy = dx - sx, dy - sy
            length = math.hypot(vx, vy)
            if length < 1e-6:
                continue
            ux, uy = vx / length, vy / length
            if a.enter:
                _entering_arrow(canvas, (sx, sy, sr), (dx, dy, dr), _ENTER[a.enter],
                                color, theme, dash)
            elif a.bend:
                off = 2.0 * float(a.bend) * length
                qx, qy = (sx + dx) / 2 - uy * off, (sy + dy) / 2 + ux * off
                _curved_arrow_ends(canvas, sx, sy, qx, qy, dx, dy, sr + 0.6, dr + 0.6,
                                   color, theme, dash)
            else:
                _arrow(canvas, sx + ux * (sr + 0.6), sy + uy * (sr + 0.6),
                       dx - ux * (dr + 0.6), dy - uy * (dr + 0.6), color, theme, dash)


def _curved_arrow_ends(canvas, sx, sy, qx, qy, dx, dy, gap0, gap1, color, theme, dash):
    """A quadratic arc whose two ends stop at their own clearances."""
    def unit(ax, ay):
        n = math.hypot(ax, ay) or 1.0
        return ax / n, ay / n
    u0 = unit(qx - sx, qy - sy)
    u1 = unit(dx - qx, dy - qy)
    p0 = (sx + u0[0] * gap0, sy + u0[1] * gap0)
    p1 = (dx - u1[0] * gap1, dy - u1[1] * gap1)
    _curved_arrow(canvas, p0[0], p0[1], qx, qy, p1[0], p1[1], 0.0, color, theme, dash)


def _entering_arrow(canvas, src, dst, enter, color, theme, dash):
    """A cubic from ``src`` (leaving level, towards ``dst``) entering ``dst``
    travelling along ``enter``; the head follows that direction."""
    from ._steplanes import _head
    (sx, sy, sr), (dx, dy, dr) = src, dst
    lx = 1.0 if dx >= sx else -1.0
    ex, ey = enter
    span = math.hypot(dx - sx, dy - sy)
    reach = max(4.0 * (dr + 0.6), 0.16 * span)
    p0 = (sx + lx * (sr + 0.6), sy)
    p1 = (dx - ex * (dr + 0.6), dy - ey * (dr + 0.6))
    c1 = (p0[0] + lx * 0.45 * abs(dx - sx), p0[1])
    c2 = (p1[0] - ex * reach, p1[1] - ey * reach)
    head = 2.4
    bx, by = p1[0] - ex * head, p1[1] - ey * head
    xs, ys = (p0[0], c1[0], c2[0], bx), (p0[1], c1[1], c2[1], by)
    canvas.path(f"M {p0[0]:.3f} {p0[1]:.3f} C {c1[0]:.3f} {c1[1]:.3f} {c2[0]:.3f} {c2[1]:.3f} "
                f"{bx + ex * 0.2:.3f} {by + ey * 0.2:.3f}", stroke=color,
                stroke_width=theme.hairline * 1.2, dasharray=dash,
                ink_bbox=(min(xs), min(ys), max(xs), max(ys)))
    _head(canvas, p1[0], p1[1], ex, ey, head, color)
