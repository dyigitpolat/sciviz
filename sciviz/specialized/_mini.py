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
    def __init__(self, nodes: Sequence[Tuple[float, float]], edges: Sequence[Tuple[int, int]],
                 *, role="primary", width: float | str = "auto",
                 height: float | str = "auto"):
        self.nodes = list(nodes)
        self.edges = list(edges)
        self.role = role
        self.width = width
        self.height = height

    def _size(self, theme: Theme) -> tuple[float, float]:
        return (theme.unit * 8 if self.width == "auto" else float(self.width),
                theme.unit * 5 if self.height == "auto" else float(self.height))

    def measure(self, theme: Theme) -> BBox:
        w, h = self._size(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        w, h = self._size(theme)
        pts = [(x + nx * w, y + ny * h) for nx, ny in self.nodes]
        c = theme.color_of(self.role)
        for a, b in self.edges:
            x1, y1 = pts[a]
            x2, y2 = pts[b]
            canvas.line(x1, y1, x2, y2, stroke=c, stroke_width=theme.hairline)
        for px, py in pts:
            canvas.circle(px, py, 2.4, fill=_soft(theme, self.role),
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
