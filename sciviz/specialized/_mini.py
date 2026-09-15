"""Tiny vector primitives for in-card thumbnails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from ..core import BBox, Canvas, Element, Theme


def _soft(theme: Theme, role) -> str:
    return theme.color_of(role.soft()) if hasattr(role, "soft") else theme.role(str(role), "soft")


@dataclass(frozen=True)
class SparkLine:
    points: Sequence[Tuple[float, float]]
    color: object = "text"
    width: float = 1.4
    dash: str | None = None


class Sparkline(Element):
    """Axis-free polyline thumbnail."""

    def __init__(self, lines: Sequence[SparkLine], *,
                 width: float | str = "auto", height: float | str = "auto",
                 domain: Tuple[float, float] = (0.0, 1.0),
                 range: Tuple[float, float] = (0.0, 1.0),
                 markers: Sequence[Tuple[float, float, object, float]] = ()):
        self.lines = list(lines)
        self.width = width
        self.height = height
        self.domain = domain
        self.range = range
        self.markers = list(markers)

    def _size(self, theme: Theme) -> tuple[float, float]:
        w = theme.unit * 8 if self.width == "auto" else float(self.width)
        h = theme.unit * 5 if self.height == "auto" else float(self.height)
        return w, h

    def measure(self, theme: Theme) -> BBox:
        w, h = self._size(theme)
        return BBox(w, h)

    def _to_px(self, x0: float, y0: float, w: float, h: float,
               px: float, py: float) -> Tuple[float, float]:
        xmin, xmax = self.domain
        ymin, ymax = self.range
        return (
            x0 + (px - xmin) / (xmax - xmin) * w,
            y0 + h - (py - ymin) / (ymax - ymin) * h,
        )

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        w, h = self._size(theme)
        for line in self.lines:
            points = [self._to_px(x, y, w, h, *p) for p in line.points]
            color = theme.color_of(line.color)
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


class MiniRaster(Element):
    def __init__(self, grid: Sequence[Sequence[int]], *, cell: float = 3.6,
                 role="primary"):
        self.grid = [list(row) for row in grid]
        self.cell = float(cell)
        self.role = role

    def measure(self, theme: Theme) -> BBox:
        rows = len(self.grid)
        cols = max((len(r) for r in self.grid), default=0)
        return BBox(cols * self.cell, rows * self.cell)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        on = theme.color_of(self.role)
        off = theme.bg_subtle
        for r, row in enumerate(self.grid):
            for c, val in enumerate(row):
                canvas.rect(x + c * self.cell, y + r * self.cell,
                            self.cell * 0.82, self.cell * 0.82,
                            fill=on if val else off, stroke="none", rx=0.3)


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
    """

    def __init__(self, points: Sequence, *,
                 domain: Tuple[float, float] = (0.0, 1.0),
                 range: Tuple[float, float] = (0.0, 1.0),
                 width: float = 52.0, height: float = 34.0,
                 role="primary", radius: float = 1.5,
                 path: Sequence[Tuple[float, float]] = (),
                 path_color=None, path_dash: str | None = None,
                 vectors: Sequence[Tuple[float, float, float, float]] = (),
                 vector_color=None,
                 corner: bool = True,
                 pad: float = 2.0):
        self.points = [p if isinstance(p, MiniPoint) else MiniPoint(*p)
                       for p in points]
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

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
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
            for a, b in zip(pts, pts[1:]):
                canvas.line(a[0], a[1], b[0], b[1], stroke=color,
                            stroke_width=theme.hairline,
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
        for p in self.points:
            cxp, cyp = self._to_px(x, y, p.x, p.y)
            color = theme.color_of(p.color if p.color is not None else self.role)
            r = p.size if p.size is not None else self.radius
            if p.hollow:
                canvas.circle(cxp, cyp, r, fill=theme.bg,
                              stroke=color, stroke_width=theme.hairline)
            else:
                canvas.circle(cxp, cyp, r, fill=color, stroke="none")
