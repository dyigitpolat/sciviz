"""Icon: compact stroke-based pictogram drawn from the Lucide subset.

Authors call ``Icon("camera")`` -- no SVG authoring required. The icon
renders at the requested ``size`` square while preserving the linecap /
linejoin look of the Lucide family.

Unknown names raise with the full list of available icons so typos are
self-diagnosing at measure time.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Union

from .._assets import LUCIDE_ICONS, LUCIDE_VIEWBOX
from ..core import BBox, Canvas, Element, Theme


class Icon(Element):
    """A Lucide-family pictogram at a fixed square size.

    Parameters
    ----------
    name : str
        Icon name (see :data:`sciviz._assets.LUCIDE_ICONS`). Unknown names
        raise :class:`KeyError` at construction time with the available
        set in the message.
    size : float or str
        Side length in px, or a semantic size token resolved against the
        theme (``"small"``, ``"label"``, ``"title"``, ...). Defaults to
        ``"label"`` so icons typographically match inline text.
    color : str or ColorRef
        Stroke color. Semantic tokens preferred (``"dark"``, ``"muted"``,
        ``"highlight"``, a palette role).
    stroke_width : float
        Stroke width in the *viewBox* coordinate system (24 units). The
        default 1.75 mirrors Lucide's own.
    opacity : float
    """

    def __init__(self, name: str, *,
                 size: Union[float, str] = "label",
                 color: str = "dark",
                 stroke_width: float = 1.75,
                 fill: str = "none",
                 opacity: float = 1.0):
        if name not in LUCIDE_ICONS:
            options = ", ".join(sorted(LUCIDE_ICONS)[:10])
            raise KeyError(
                f"Unknown icon {name!r}. "
                f"Available: {len(LUCIDE_ICONS)} icons, e.g. {options} ... "
                f"(see sciviz._assets.LUCIDE_ICONS for the full list)."
            )
        self.name = name
        self.size = size
        self.color = color
        self.stroke_width = float(stroke_width)
        # ``"none"`` (default) -- Lucide's pure-stroke look.
        # ``"match"``          -- fill the shape with ``color`` (solid glyph).
        # Any colour string    -- explicit fill colour.
        self.fill = fill
        self.opacity = float(opacity)

    def _size_px(self, theme: Theme) -> float:
        if isinstance(self.size, (int, float)):
            return float(self.size)
        return theme.size_px(self.size) * 1.2

    def measure(self, theme: Theme) -> BBox:
        s = self._size_px(theme)
        return BBox(s, s)

    @staticmethod
    def _path_points(path: str) -> list[tuple[float, float]]:
        tokens = re.findall(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", path)
        points: list[tuple[float, float]] = []
        i = 0
        cmd = ""
        x = y = 0.0
        start_x = start_y = 0.0

        def is_cmd(tok: str) -> bool:
            return len(tok) == 1 and tok.isalpha()

        def need(n: int) -> bool:
            return i + n <= len(tokens) and all(not is_cmd(t) for t in tokens[i:i + n])

        def num() -> float:
            nonlocal i
            v = float(tokens[i])
            i += 1
            return v

        while i < len(tokens):
            if is_cmd(tokens[i]):
                cmd = tokens[i]
                i += 1
            if not cmd:
                break
            rel = cmd.islower()
            c = cmd.upper()

            if c == "M":
                first = True
                while need(2):
                    nx, ny = num(), num()
                    x = x + nx if rel else nx
                    y = y + ny if rel else ny
                    points.append((x, y))
                    if first:
                        start_x, start_y = x, y
                        first = False
                continue
            if c == "L":
                while need(2):
                    nx, ny = num(), num()
                    x = x + nx if rel else nx
                    y = y + ny if rel else ny
                    points.append((x, y))
                continue
            if c == "H":
                while need(1):
                    nx = num()
                    x = x + nx if rel else nx
                    points.append((x, y))
                continue
            if c == "V":
                while need(1):
                    ny = num()
                    y = y + ny if rel else ny
                    points.append((x, y))
                continue
            if c == "C":
                while need(6):
                    vals = [num() for _ in range(6)]
                    pts = [(vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])]
                    abs_pts = [(x + px, y + py) if rel else (px, py) for px, py in pts]
                    points.extend(abs_pts)
                    x, y = abs_pts[-1]
                continue
            if c == "S" or c == "Q":
                n = 4
                while need(n):
                    vals = [num() for _ in range(n)]
                    pts = [(vals[0], vals[1]), (vals[2], vals[3])]
                    abs_pts = [(x + px, y + py) if rel else (px, py) for px, py in pts]
                    points.extend(abs_pts)
                    x, y = abs_pts[-1]
                continue
            if c == "T":
                while need(2):
                    nx, ny = num(), num()
                    x = x + nx if rel else nx
                    y = y + ny if rel else ny
                    points.append((x, y))
                continue
            if c == "A":
                while need(7):
                    rx, ry, _rot, _large, _sweep = (num(), num(), num(), num(), num())
                    sx, sy = x, y
                    nx, ny = num(), num()
                    ex = x + nx if rel else nx
                    ey = y + ny if rel else ny
                    for px, py in ((sx, sy), (ex, ey)):
                        points.extend([
                            (px - rx, py - ry),
                            (px + rx, py + ry),
                        ])
                    x, y = ex, ey
                    points.append((x, y))
                continue
            if c == "Z":
                x, y = start_x, start_y
                points.append((x, y))
                continue
            # Unknown or malformed command: stop rather than inventing bounds.
            break
        return points

    @staticmethod
    @lru_cache(maxsize=256)
    def _viewbox_bounds(name: str) -> tuple[float, float, float, float]:
        """Approximate the visible path bounds in Lucide viewBox units.

        Lucide icons share a 24x24 viewBox but not every glyph is optically
        centered inside that square. Row/Column alignment should follow the
        visible glyph, not the full transparent viewBox.
        """
        points: list[tuple[float, float]] = []
        for path in LUCIDE_ICONS[name]:
            points.extend(Icon._path_points(path))
        if not points:
            return LUCIDE_VIEWBOX
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        vx, vy, vw, vh = LUCIDE_VIEWBOX
        pad = 1.0
        x0 = max(vx, min(xs) - pad)
        y0 = max(vy, min(ys) - pad)
        x1 = min(vx + vw, max(xs) + pad)
        y1 = min(vy + vh, max(ys) + pad)
        return (x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))

    def content_bbox(self, theme: Theme) -> tuple[float, float, float, float]:
        s = self._size_px(theme)
        vx, vy, vw, vh = LUCIDE_VIEWBOX
        bx, by, bw, bh = self._viewbox_bounds(self.name)
        sx = s / vw
        sy = s / vh
        return ((bx - vx) * sx, (by - vy) * sy, bw * sx, bh * sy)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        s = self._size_px(theme)
        stroke = theme.color_of(self.color)
        if self.fill == "match":
            fill = stroke
        elif self.fill == "none":
            fill = "none"
        else:
            fill = theme.color_of(self.fill)
        canvas.svg_path(
            x, y, s, s,
            paths=LUCIDE_ICONS[self.name],
            viewbox=LUCIDE_VIEWBOX,
            stroke=stroke,
            stroke_width=self.stroke_width,
            fill=fill,
            opacity=self.opacity,
        )
