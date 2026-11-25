"""Tiny vector primitives for in-card thumbnails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from ..core import BBox, Canvas, Element, Theme


def _soft(theme: Theme, role) -> str:
    return theme.color_of(role.soft()) if hasattr(role, "soft") else theme.role(str(role), "soft")


@dataclass(frozen=True)
class SparkLine:
    """One polyline of a :class:`Sparkline`.

    ``fill`` paints the area between the line and the level ``fill_to``
    (data units; the bottom of the sparkline's ``range`` when omitted), so
    a density or a share reads as a filled shape rather than as an
    outline. ``fill_opacity`` keeps overlapping shapes readable; several
    filled lines stacked at different baselines make a ridgeline.

    ``label`` (a string or any element) is the line's direct label, drawn
    by the :class:`Sparkline` beside the plot at the line's level: its
    ``fill_to`` baseline, or its last point when it has none.
    """

    points: Sequence[Tuple[float, float]]
    color: object = "text"
    width: float = 1.4
    dash: str | None = None
    fill: object = None
    fill_to: float | None = None
    fill_opacity: float = 1.0
    label: object = None


class Sparkline(Element):
    """Axis-free polyline thumbnail.

    Lines that carry a ``label`` are labelled directly, one label per
    line in a column on ``label_side``, each label's first text baseline
    on its line's level (its ``fill_to``, else its last point); a label
    without text is centred on the level. A label set is a rigid stack
    (its pitch is fixed by the font), so the chart stretches its vertical
    scale until the closest two labelled levels are at least one label
    apart: ``height`` is then a minimum, and every label meets its line
    at any size the figure is fitted to. The labels' ink above the top
    level or below the bottom one is part of the measured box.
    """

    def __init__(self, lines: Sequence[SparkLine], *,
                 width: float | str = "auto", height: float | str = "auto",
                 domain: Tuple[float, float] = (0.0, 1.0),
                 range: Tuple[float, float] = (0.0, 1.0),
                 markers: Sequence[Tuple[float, float, object, float]] = (),
                 label_side: str = "left",
                 label_gap: str | float = "xs"):
        if label_side not in ("left", "right"):
            raise ValueError(
                f"Sparkline.label_side must be 'left' or 'right'; "
                f"got {label_side!r}")
        self.lines = list(lines)
        self.width = width
        self.height = height
        self.domain = domain
        self.range = range
        self.markers = list(markers)
        self.label_side = label_side
        self.label_gap = label_gap
        self._label_elems = {}
        self._geometry_cache = (None, None)

    def _size(self, theme: Theme) -> tuple[float, float]:
        w = theme.unit * 8 if self.width == "auto" else float(self.width)
        h = theme.unit * 5 if self.height == "auto" else float(self.height)
        return w, h

    def _labels(self):
        """``[(level, element)]`` for every labelled line."""
        from ..elements import Text
        out = []
        for i, line in enumerate(self.lines):
            if line.label is None:
                continue
            el = self._label_elems.get(i)
            if el is None:
                el = (Text(line.label, size="tiny")
                      if isinstance(line.label, str) else line.label)
                self._label_elems[i] = el
            level = (line.fill_to if line.fill_to is not None
                     else line.points[-1][1] if line.points
                     else self.range[0])
            out.append((float(level), el))
        return out

    def _geometry(self, theme: Theme):
        """``(plot_w, plot_h, plot_dx, plot_dy, W, H, placed)``.

        ``placed`` lists ``(element, dx, dy)`` label offsets from the
        element origin; ``plot_dx``/``plot_dy`` offset the plot itself.
        """
        from ..layout._baseline import first_baseline
        w, h = self._size(theme)
        labels = self._labels()
        if not labels:
            return w, h, 0.0, 0.0, w, h, []
        # The labels belong to the chart and nothing outside resizes
        # them, so their placement is fixed per theme.
        if self._geometry_cache[0] is theme:
            return self._geometry_cache[1]
        ymin, ymax = self.range
        span = (ymax - ymin) or 1.0
        levels = sorted(set(lv for lv, _el in labels))
        pitch = max(el.measure(theme).h for _lv, el in labels)
        steps = [b - a for a, b in zip(levels, levels[1:]) if b > a]
        if steps:
            h = max(h, span * pitch / min(steps))
        lw = max(el.measure(theme).w for _lv, el in labels)
        gap = theme.gap_px(self.label_gap)
        tops = []
        for lv, el in labels:
            y_lv = h - (lv - ymin) / span * h
            cb = el.content_bbox(theme)
            b = first_baseline(el, theme)
            anchor = cb[1] + (b if b is not None else cb[3] / 2)
            tops.append((el, y_lv - anchor))
        over_top = max(0.0, -min(t for _el, t in tops))
        over_bot = max(0.0, max(t + el.measure(theme).h for el, t in tops) - h)
        plot_dx = lw + gap if self.label_side == "left" else 0.0
        label_x = 0.0 if self.label_side == "left" else w + gap
        placed = [(el, label_x, t + over_top) for el, t in tops]
        geo = (w, h, plot_dx, over_top, w + lw + gap,
               h + over_top + over_bot, placed)
        self._geometry_cache = (theme, geo)
        return geo

    def measure(self, theme: Theme) -> BBox:
        _w, _h, _dx, _dy, W, H, _placed = self._geometry(theme)
        return BBox(W, H)

    def _to_px(self, x0: float, y0: float, w: float, h: float,
               px: float, py: float) -> Tuple[float, float]:
        xmin, xmax = self.domain
        ymin, ymax = self.range
        return (
            x0 + (px - xmin) / (xmax - xmin) * w,
            y0 + h - (py - ymin) / (ymax - ymin) * h,
        )

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        w, h, dx, dy, _W, _H, placed = self._geometry(theme)
        for el, lx, ly in placed:
            el.render(canvas, x + lx, y + ly, theme)
        x, y = x + dx, y + dy
        for line in self.lines:
            points = [self._to_px(x, y, w, h, *p) for p in line.points]
            color = theme.color_of(line.color)
            if line.fill is not None and len(points) >= 2:
                level = self.range[0] if line.fill_to is None else line.fill_to
                _, base = self._to_px(x, y, w, h, self.domain[0], level)
                ring = ([(points[0][0], base)] + points
                        + [(points[-1][0], base)])
                canvas.polygon(ring, fill=theme.paint_of(line.fill),
                               stroke="none", opacity=line.fill_opacity)
            for a, b in zip(points, points[1:]):
                canvas.line(a[0], a[1], b[0], b[1], stroke=color,
                            stroke_width=line.width, dasharray=line.dash)
        for px, py, color, radius in self.markers:
            cx, cy = self._to_px(x, y, w, h, px, py)
            c = theme.color_of(color)
            canvas.circle(cx, cy, radius, fill=c, stroke=c, stroke_width=theme.hairline)


class MiniMatrix(Element):
    def __init__(self, shape=(4, 4), *, disabled_rows=(), disabled_cols=(),
                 role="primary", cell: float = 5.0):
        self.rows, self.cols = shape
        self.disabled_rows = set(disabled_rows)
        self.disabled_cols = set(disabled_cols)
        self.role = role
        self.cell = float(cell)

    def measure(self, theme: Theme) -> BBox:
        gap = self.cell * 0.18
        return BBox(self.cols * self.cell + (self.cols - 1) * gap,
                    self.rows * self.cell + (self.rows - 1) * gap)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        gap = self.cell * 0.18
        for r in range(self.rows):
            for c in range(self.cols):
                off = r in self.disabled_rows or c in self.disabled_cols
                fill = theme.disabled_fill if off else _soft(theme, self.role)
                stroke = theme.disabled_stroke if off else theme.color_of(self.role)
                canvas.rect(x + c * (self.cell + gap), y + r * (self.cell + gap),
                            self.cell, self.cell, fill=fill, stroke=stroke,
                            stroke_width=theme.hairline, rx=0.8)


class MiniGraph(Element):
    _SIZES = {
        "sm": (8.0, 5.0, 1.0),
        "md": (12.0, 8.0, 1.15),
        "lg": (16.0, 11.0, 1.35),
        "xl": (20.0, 14.0, 1.55),
    }

    def __init__(self, nodes: Sequence[Tuple[float, float]], edges: Sequence[Tuple[int, int]],
                 *, role="primary", width: float | str = "auto",
                 height: float | str = "auto", size: str = "sm",
                 filled: bool = False):
        if size not in self._SIZES:
            allowed = ", ".join(self._SIZES)
            raise ValueError(f"MiniGraph.size must be one of {allowed}")
        self.nodes = list(nodes)
        self.edges = list(edges)
        self.role = role
        self.width = width
        self.height = height
        self.size = size
        self.filled = bool(filled)

    def _size(self, theme: Theme) -> tuple[float, float]:
        width_units, height_units, _scale = self._SIZES[self.size]
        return (
            theme.unit * width_units if self.width == "auto" else float(self.width),
            theme.unit * height_units if self.height == "auto" else float(self.height),
        )

    def measure(self, theme: Theme) -> BBox:
        w, h = self._size(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        w, h = self._size(theme)
        pts = [(x + nx * w, y + ny * h) for nx, ny in self.nodes]
        c = theme.color_of(self.role)
        _wu, _hu, scale = self._SIZES[self.size]
        for a, b in self.edges:
            x1, y1 = pts[a]
            x2, y2 = pts[b]
            canvas.line(x1, y1, x2, y2, stroke=c,
                        stroke_width=theme.hairline * min(scale, 1.4))
        for px, py in pts:
            node_fill = c if self.filled else _soft(theme, self.role)
            canvas.circle(px, py, 2.4 * scale, fill=node_fill,
                          stroke=c, stroke_width=theme.hairline)


class MiniTimeline(Element):
    def __init__(self, segments: Sequence[Tuple[float, float, int]], *,
                 lanes: int = 2, role="primary", width: float | str = "auto"):
        self.segments = list(segments)
        self.lanes = lanes
        self.role = role
        self.width = width

    def measure(self, theme: Theme) -> BBox:
        w = theme.unit * 8 if self.width == "auto" else float(self.width)
        return BBox(w, self.lanes * theme.unit * 1.2)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        lane_h = size.h / max(1, self.lanes)
        for lane in range(self.lanes):
            cy = y + lane * lane_h + lane_h / 2
            canvas.line(x, cy, x + size.w, cy, stroke=theme.border,
                        stroke_width=theme.hairline, opacity=0.65)
        for start, end, lane in self.segments:
            yy = y + (lane % self.lanes) * lane_h + lane_h * 0.25
            canvas.rect(x + start * size.w, yy, max(1.0, (end - start) * size.w),
                        lane_h * 0.5, fill=_soft(theme, self.role),
                        stroke=theme.color_of(self.role), stroke_width=theme.hairline,
                        rx=1.2)


@dataclass(frozen=True)
class MiniCell:
    """One entry of a :class:`MiniRaster` that says how it is drawn.

    ``MiniCell(color)`` is the same cell as the bare colour.
    ``hollow=True`` draws the square open: an outline in ``color`` and no
    fill, the conventional encoding for a unit that was not measured (not
    reached, not checked within a limit), as ``MiniPoint(hollow=True)`` is
    for a scatter. The outline lies inside the filled square, so an open
    unit has the same extent and pitch as a filled one.
    """

    color: object = "primary"
    hollow: bool = False


class MiniRaster(Element):
    """A grid of small square cells: a raster, a mask, or a row of units.

    Each entry is truthy/falsy (drawn in ``role`` or the subtle off
    colour), a colour of its own, or a :class:`MiniCell` (a colour drawn
    filled or open), so one raster can say *which kind* each unit is -- a
    row of seats coloured by who holds them, a categorical mask, a row of
    members some of which were not checked. A filled cell whose colour
    would vanish on the page (the palest classes of a palette) gets the
    theme's contrast edge (:meth:`Theme.edge_for_fill`), so every unit
    stays countable.

    Parameters
    ----------
    grid : sequence of sequences
        Rows of cells; each an int/bool, a colour (``"#rrggbb"``, a role
        name, a :class:`ColorRef`) or a :class:`MiniCell`. ``None`` leaves
        the slot empty.
    cell : float
        Pitch of one cell in px (cell plus gutter).
    role : ColorRef or str
        Colour of truthy entries.
    gap : float
        Gutter between cells as a fraction of ``cell``.
    spans : sequence of (first, stop, label), optional
        Runs of columns ``first <= c < stop`` to mark under the grid with a
        hairline bracket and a caption (``"reserved"`` under the held
        seats of a row): the caption starts at the bracket and may run
        past it, since a run of a few small cells is narrower than any
        word that names it.
    """

    def __init__(self, grid: Sequence[Sequence[object]], *, cell: float = 3.6,
                 role="primary", gap: float = 0.18,
                 spans: Sequence[Tuple[int, int, str]] = (),
                 text_size: str = "tiny"):
        self.grid = [list(row) for row in grid]
        self.cell = float(cell)
        self.role = role
        self.gap = max(0.0, min(0.6, float(gap)))
        self.spans = [(int(a), int(b), str(t)) for a, b, t in spans]
        self.text_size = text_size

    @classmethod
    def from_counts(cls, counts: Sequence[Tuple[int, object]], *,
                    columns: Optional[int] = None, **kwargs) -> "MiniRaster":
        """A raster of ``count`` cells per colour, packed row-major into
        ``columns`` cells per row with each colour in one contiguous run:
        a waffle of a composition. ``columns=None`` picks a squarish block
        (about 1.6 wide per tall). Other keywords go to the constructor.
        """
        import math
        cells = [paint for n, paint in counts for _ in range(max(0, int(n)))]
        if columns is None:
            columns = max(1, math.ceil(math.sqrt(len(cells) * 1.6)))
        columns = max(1, int(columns))
        grid = [cells[i:i + columns] for i in range(0, len(cells), columns)]
        return cls(grid, **kwargs)

    def _span_band(self, theme: Theme) -> float:
        """Height of the bracket and caption band under the grid."""
        if not self.spans:
            return 0.0
        return self.cell * 0.7 + theme.text_height(self.text_size)

    def measure(self, theme: Theme) -> BBox:
        rows = len(self.grid)
        cols = max((len(r) for r in self.grid), default=0)
        w = cols * self.cell
        for first, _stop, label in self.spans:
            w = max(w, first * self.cell + theme.text_width(label, self.text_size))
        return BBox(w, rows * self.cell + self._span_band(theme))

    def _paint(self, theme: Theme, val) -> str | None:
        if val is None:
            return None
        if isinstance(val, MiniCell):
            return theme.paint_of(val.color)
        if isinstance(val, bool) or isinstance(val, (int, float)):
            return theme.color_of(self.role) if val else theme.bg_subtle
        return theme.paint_of(val)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        side = self.cell * (1.0 - self.gap)
        rx = min(0.3, side * 0.12)
        for r, row in enumerate(self.grid):
            for c, val in enumerate(row):
                fill = self._paint(theme, val)
                if fill is None:
                    continue
                if isinstance(val, MiniCell) and val.hollow:
                    # the outline's outer edge on the filled square
                    sw = theme.hairline
                    canvas.rect(x + c * self.cell + sw / 2, y + r * self.cell + sw / 2,
                                side - sw, side - sw, fill="none", stroke=fill,
                                stroke_width=sw, rx=rx)
                    continue
                edge = theme.edge_for_fill(fill)
                inset = theme.hairline * 0.35 if edge else 0.0
                canvas.rect(x + c * self.cell + inset, y + r * self.cell + inset,
                            side - 2 * inset, side - 2 * inset,
                            fill=fill, stroke=edge or "none",
                            stroke_width=theme.hairline * 0.7, rx=rx)
        if not self.spans:
            return
        ink = theme.color_of("text_muted")
        base = y + len(self.grid) * self.cell
        tick = self.cell * 0.35
        size = theme.size_px(self.text_size)
        for first, stop, label in self.spans:
            x0 = x + first * self.cell
            x1 = x + stop * self.cell - (self.cell - side)
            by = base + tick
            canvas.line(x0, by, x1, by, stroke=ink, stroke_width=theme.hairline)
            canvas.line(x0, by - tick, x0, by, stroke=ink,
                        stroke_width=theme.hairline)
            canvas.line(x1, by - tick, x1, by, stroke=ink,
                        stroke_width=theme.hairline)
            if label:
                canvas.text(x0, by + tick * 0.6 + size * 0.88, label,
                            size=size, fill=ink, anchor="start")


@dataclass(frozen=True)
class MiniPoint:
    """One member of a :class:`MiniScatter` cloud.

    Parameters
    ----------
    x, y : float
        Position in the thumbnail's own data domain.
    color : ColorRef or str, optional
        Per-point colour; falls back to the scatter's ``role``.
    size : float, optional
        Radius in px; falls back to the scatter's ``radius``.
    hollow : bool
        Draw the point as an open ring, the conventional encoding for a
        member that is derived, dominated, or not yet measured.
    """

    x: float
    y: float
    color: object = None
    size: float | None = None
    hollow: bool = False
    edge: object = "auto"


@dataclass(frozen=True)
class MiniArea:
    """A filled region of a :class:`MiniScatter`, in data units.

    The encoding for *area* in a data plane: a feasible region, a confidence
    band. Drawn under every path and point, and
    clipped to the thumbnail's window like the rest of its ink.

    Parameters
    ----------
    points : sequence of (x, y)
        The polygon's vertices, in the thumbnail's data domain.
    color : ColorRef or str, optional
        Fill colour; falls back to the scatter's ``role``.
    opacity : float
        Fill opacity, so an area never hides the points drawn over it.
    edge : ColorRef or str, optional
        Hairline outline; ``None`` draws none.
    """

    points: Sequence[Tuple[float, float]]
    color: object = None
    opacity: float = 0.35
    edge: object = None


class MiniScatter(Element):
    """Axis-free point-cloud thumbnail, with optional displacement arrows.

    The scatter counterpart of :class:`Sparkline`: a cloud small enough to
    live inside a card, drawn with no ticks and no axis titles, because a
    thumbnail carries a *shape* and its parent card carries the words. An
    optional hairline corner marks the two directions when the cloud sits
    in an objective plane.

    ``vectors`` draws a short arrow from a point toward a second position,
    both in data units: where each member came from, or where the next
    step is taking it. It is the encoding for a set that is being nudged
    rather than replaced.

    Parameters
    ----------
    points : sequence
        :class:`MiniPoint` values or bare ``(x, y)`` pairs.
    domain, range : (float, float)
        The data window the thumbnail shows.
    width, height : float
        Extent in px.
    role : ColorRef or str
        Default point colour.
    radius : float
        Default point radius in px.
    path : sequence, optional
        ``(x, y)`` pairs joined by a hairline, e.g. a front through the
        non-dominated members.
    vectors : sequence, optional
        ``(x, y, dx, dy)`` displacement arrows in data units.
    corner : bool
        Draw the hairline left/bottom axis corner.
    areas : sequence of :class:`MiniArea`, optional
        Filled regions drawn under the paths and points.
    clip : bool
        Keep every mark inside the thumbnail's box (the data window plus
        ``pad``): areas are clipped as polygons, paths as polylines, and
        a point is drawn only when its centre is inside. On by default,
        because a thumbnail's window is a crop the author chose and ink
        outside it would break the element's measured box.

    declutter : None or "dodge"
        ``"dodge"`` keeps points from piling on each other in a small
        window. Points are placed from the last drawn to the first, so the
        one the reader sees on top keeps its true position. A point that
        collides with a placed one is: dropped when it is a true
        duplicate (same colour, same hollow state, centres closer than
        half a radius) or a hollow point whose colour another point still
        shows; otherwise nudged to the nearest free spot no farther than
        ``r_i + r_j`` from its true position; and, when no spot is free, drawn as a ring in its own
        colour around the point it hides. No colour present in
        ``points`` ever disappears. ``None`` (default) draws every point
        where it is.
    declutter_gap : float
        How close two points may come, as a fraction of the smaller
        radius beyond touching, before they count as colliding.

    Points whose fill would vanish on the page get a hairline edge in a
    darker shade of their own colour (:meth:`Theme.edge_for_fill`);
    ``MiniPoint(edge=...)`` names the edge explicitly and
    ``edge="none"`` suppresses it.
    """

    def __init__(self, points: Sequence, *,
                 domain: Tuple[float, float] = (0.0, 1.0),
                 range: Tuple[float, float] = (0.0, 1.0),
                 width: float = 52.0, height: float = 34.0,
                 role="primary", radius: float = 1.5,
                 path: Sequence[Tuple[float, float]] = (),
                 path_color=None, path_dash: str | None = None,
                 path_width: float | None = None,
                 vectors: Sequence[Tuple[float, float, float, float]] = (),
                 vector_color=None,
                 corner: bool = True,
                 pad: float = 2.0,
                 areas: Sequence[MiniArea] = (),
                 clip: bool = True,
                 declutter: str | None = None,
                 declutter_gap: float = 0.25):
        if declutter not in (None, "dodge"):
            raise ValueError(
                f"MiniScatter.declutter must be None or 'dodge'; got {declutter!r}")
        self.declutter = declutter
        self.declutter_gap = max(0.0, float(declutter_gap))
        self.points = [p if isinstance(p, MiniPoint) else MiniPoint(*p)
                       for p in points]
        self.areas = list(areas)
        self.clip = bool(clip)
        self.path_width = None if path_width is None else float(path_width)
        self.domain = (float(domain[0]), float(domain[1]))
        self.range = (float(range[0]), float(range[1]))
        self.width = float(width)
        self.height = float(height)
        self.role = role
        self.radius = float(radius)
        self.path = [(float(a), float(b)) for a, b in path]
        self.path_color = path_color
        self.path_dash = path_dash
        self.vectors = [tuple(float(v) for v in vec) for vec in vectors]
        self.vector_color = vector_color
        self.corner = bool(corner)
        self.pad = float(pad)

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width, self.height)

    def _to_px(self, x0: float, y0: float, px: float, py: float):
        xmin, xmax = self.domain
        ymin, ymax = self.range
        w = self.width - self.pad * 2
        h = self.height - self.pad * 2
        fx = 0.0 if xmax == xmin else (px - xmin) / (xmax - xmin)
        fy = 0.0 if ymax == ymin else (py - ymin) / (ymax - ymin)
        return x0 + self.pad + fx * w, y0 + self.pad + (1.0 - fy) * h

    def _window(self, x: float, y: float) -> Tuple[float, float, float, float]:
        """The clip rectangle in px: the element's own box."""
        return (x, y, x + self.width, y + self.height)

    def _placements(self, x: float, y: float):
        """``(point, cx, cy, ring)`` per drawn point, in draw order.

        ``ring`` is ``None`` for a disc at ``(cx, cy)``, or the radius of
        the ring drawn around ``(cx, cy)`` for a point that had no free
        spot (see ``declutter``).
        """
        import math
        px = [self._to_px(x, y, p.x, p.y) for p in self.points]
        if self.declutter is None:
            return [(p, cx, cy, None) for p, (cx, cy) in zip(self.points, px)]
        radius = [p.size if p.size is not None else self.radius
                  for p in self.points]
        colour = [p.color if p.color is not None else self.role
                  for p in self.points]
        x0, y0, x1, y1 = self._window(x, y)
        placed: list = []          # (index, cx, cy)
        rings: dict = {}           # index -> ring radius around a winner
        dropped: set = set()

        def clearance(i, j, gap=self.declutter_gap):
            return radius[i] + radius[j] + gap * min(radius[i], radius[j])

        def hits(i, cx, cy, gap=self.declutter_gap):
            return [(j, qx, qy) for j, qx, qy in placed
                    if math.hypot(cx - qx, cy - qy) < clearance(i, j, gap) - 1e-9]

        order = list(range(len(self.points)))[::-1]
        for i in order:
            cx, cy = px[i]
            clash = hits(i, cx, cy)
            if not clash:
                placed.append((i, cx, cy))
                continue
            j, qx, qy = clash[0]
            d = math.hypot(cx - qx, cy - qy)
            p, q = self.points[i], self.points[j]
            shown_elsewhere = any(
                colour[k] == colour[i] for k in range(len(self.points))
                if k != i and k not in dropped)
            if ((colour[i] == colour[j] and p.hollow == q.hollow
                 and d < 0.5 * min(radius[i], radius[j]))
                    or (p.hollow and shown_elsewhere)):
                dropped.add(i)
                continue
            # A nudge never exceeds r_i + r_j: far enough to clear the
            # point it hid, never far enough to change what it says.
            reach = clearance(i, j, 0.0)
            base = (math.atan2(cy - qy, cx - qx) if d > 1e-9
                    else -math.pi / 2)
            spot = None
            for f in (0.35, 0.7, 1.0):
                for k in range(12):
                    a = base + (k + 1) // 2 * (1 if k % 2 else -1) * math.pi / 6
                    sx = cx + math.cos(a) * reach * f
                    sy = cy + math.sin(a) * reach * f
                    if not (x0 + radius[i] <= sx <= x1 - radius[i]
                            and y0 + radius[i] <= sy <= y1 - radius[i]):
                        continue
                    if math.hypot(sx - cx, sy - cy) > reach + 1e-9:
                        continue
                    if not hits(i, sx, sy, 0.0):
                        spot = (sx, sy)
                        break
                if spot:
                    break
            if spot:
                placed.append((i, spot[0], spot[1]))
            else:
                ring_r = radius[j] + radius[i] * 0.6
                rings[i] = (qx, qy, ring_r)
        where = {i: (cx, cy) for i, cx, cy in placed}
        out = []
        for i, p in enumerate(self.points):
            if i in where:
                out.append((p, where[i][0], where[i][1], None))
            elif i in rings:
                qx, qy, ring_r = rings[i]
                out.append((p, qx, qy, ring_r))
        return out

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        from ._clip import clip_polygon, clip_polyline, contains
        window = self._window(x, y)
        for area in self.areas:
            ring = [self._to_px(x, y, *p) for p in area.points]
            if self.clip:
                ring = clip_polygon(ring, window)
            if len(ring) < 3:
                continue
            fill = theme.paint_of(area.color if area.color is not None
                                  else self.role)
            canvas.polygon(ring, fill=fill, stroke="none",
                           opacity=area.opacity)
            if area.edge is not None:
                closed = ring + [ring[0]]
                for a, b in zip(closed, closed[1:]):
                    canvas.line(a[0], a[1], b[0], b[1],
                                stroke=theme.paint_of(area.edge),
                                stroke_width=theme.hairline * 0.8)
        if self.corner:
            edge = theme.color_of("border")
            canvas.line(x + self.pad * 0.4, y, x + self.pad * 0.4,
                        y + self.height - self.pad * 0.4,
                        stroke=edge, stroke_width=theme.hairline)
            canvas.line(x + self.pad * 0.4, y + self.height - self.pad * 0.4,
                        x + self.width, y + self.height - self.pad * 0.4,
                        stroke=edge, stroke_width=theme.hairline)
        if len(self.path) > 1:
            color = theme.color_of(self.path_color if self.path_color is not None
                                   else self.role)
            pts = [self._to_px(x, y, *p) for p in self.path]
            runs = clip_polyline(pts, window) if self.clip else [pts]
            for run in runs:
                for a, b in zip(run, run[1:]):
                    canvas.line(a[0], a[1], b[0], b[1], stroke=color,
                                stroke_width=(self.path_width
                                              if self.path_width is not None
                                              else theme.hairline),
                                dasharray=self.path_dash)
        if self.vectors:
            color = theme.color_of(self.vector_color
                                   if self.vector_color is not None
                                   else self.role)
            head = canvas.define_arrow_marker(
                color=color, stroke_width=theme.hairline,
                arrow_size=max(2.4, theme.arrow_size * 0.6),
                name_hint="mininudge")
            for vx, vy, dx, dy in self.vectors:
                ax, ay = self._to_px(x, y, vx, vy)
                bx, by = self._to_px(x, y, vx + dx, vy + dy)
                canvas.line(ax, ay, bx, by, stroke=color,
                            stroke_width=theme.hairline, marker_end=head)
        for p, cxp, cyp, ring in self._placements(x, y):
            if self.clip and not contains(window, (cxp, cyp)):
                continue
            color = theme.color_of(p.color if p.color is not None else self.role)
            r = p.size if p.size is not None else self.radius
            if ring is not None:
                # No free spot: the point rings the one that hides it.
                canvas.circle(cxp, cyp, ring, fill="none", stroke=color,
                              stroke_width=max(theme.hairline, r * 0.45))
                continue
            if p.hollow:
                canvas.circle(cxp, cyp, r, fill=theme.bg,
                              stroke=color, stroke_width=theme.hairline)
                continue
            if p.edge == "auto":
                edge = theme.edge_for_fill(color)
            elif p.edge in (None, "none"):
                edge = None
            else:
                edge = theme.paint_of(p.edge)
            if edge:
                # The edge is drawn inside the nominal radius, so an edged
                # point has the same footprint as a plain one.
                sw = theme.hairline * 0.7
                canvas.circle(cxp, cyp, max(0.2, r - sw / 2), fill=color,
                              stroke=edge, stroke_width=sw)
            else:
                canvas.circle(cxp, cyp, r, fill=color, stroke="none")
