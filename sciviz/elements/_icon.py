"""Icon: compact stroke-based pictogram drawn from a bundled icon bank.

Authors call ``Icon("camera")`` -- no SVG authoring required. The icon
renders at the requested ``size`` square while preserving the linecap /
linejoin look of its source family.

Two banks back the lookup, checked in order:

1. :data:`sciviz._assets.LUCIDE_ICONS` -- a curated ~50-icon subset with
   path data baked into a Python dict (see :mod:`sciviz._assets._lucide`).
2. The Hugeicons stroke-rounded free bank (~5,500 icons, see
   :mod:`sciviz._assets._hugeicons`) -- SVG files loaded from disk and
   parsed lazily on first use. Search
   ``sciviz/_assets/hugeicons/manifest.json`` (or
   :func:`sciviz._assets.search_hugeicons`) to find a name by keyword.

Unknown names raise with the full list of available icons so typos are
self-diagnosing at measure time.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional, Union

from .._assets import (
    HUGEICONS_VIEWBOX,
    LUCIDE_ICONS,
    LUCIDE_VIEWBOX,
    has_hugeicon,
    hugeicons_names,
    load_hugeicon_shapes,
)
from ..core import BBox, Canvas, Element, Theme


class Icon(Element):
    """A pictogram at a fixed square size, resolved from the Lucide subset
    or the larger Hugeicons bank.

    Parameters
    ----------
    name : str
        Icon name. Checked against :data:`sciviz._assets.LUCIDE_ICONS`
        first, then the Hugeicons bank. Unknown names raise
        :class:`KeyError` at construction time with counts for both banks.
    size : float or str
        Side length in px, or a semantic size token resolved against the
        theme (``"small"``, ``"label"``, ``"title"``, ...). Defaults to
        ``"label"`` so icons typographically match inline text.
    color : str or ColorRef
        Stroke color. Semantic tokens preferred (``"dark"``, ``"muted"``,
        ``"highlight"``, a palette role).
    stroke_width : float or None
        Stroke width in the *viewBox* coordinate system (24 units). For
        Lucide icons this is an absolute width (default 1.75, mirroring
        Lucide's own). For Hugeicons icons, ``None`` (default) keeps each
        shape's authored width -- some icons deliberately vary stroke
        weight per shape (e.g. a bold dot) -- and an explicit value scales
        every shape's width proportionally rather than replacing it.
    opacity : float
    """

    def __init__(self, name: str, *,
                 size: Union[float, str] = "label",
                 color: str = "dark",
                 stroke_width: Optional[float] = None,
                 fill: str = "none",
                 opacity: float = 1.0):
        if name in LUCIDE_ICONS:
            self._bank = "lucide"
        elif has_hugeicon(name):
            self._bank = "hugeicons"
        else:
            lucide_options = ", ".join(sorted(LUCIDE_ICONS)[:10])
            raise KeyError(
                f"Unknown icon {name!r}. "
                f"Available: {len(LUCIDE_ICONS)} Lucide icons (e.g. {lucide_options} ...) "
                f"+ {len(hugeicons_names())} Hugeicons icons. "
                f"Search sciviz/_assets/hugeicons/manifest.json by keyword, or see "
                f"sciviz._assets.LUCIDE_ICONS / sciviz._assets.hugeicons_names() for the full lists."
            )
        self.name = name
        self.size = size
        self.color = color
        self.stroke_width = None if stroke_width is None else float(stroke_width)
        # ``"none"`` (default) -- pure-stroke look.
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

    @staticmethod
    def _shape_points(tag: str, attrs: dict) -> list[tuple[float, float]]:
        if tag == "path" and "d" in attrs:
            return Icon._path_points(attrs["d"])
        if tag == "circle":
            cx, cy, r = float(attrs.get("cx", 0)), float(attrs.get("cy", 0)), float(attrs.get("r", 0))
            return [(cx - r, cy - r), (cx + r, cy + r)]
        if tag == "ellipse":
            cx, cy = float(attrs.get("cx", 0)), float(attrs.get("cy", 0))
            rx, ry = float(attrs.get("rx", 0)), float(attrs.get("ry", 0))
            return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
        if tag == "rect":
            x0, y0 = float(attrs.get("x", 0)), float(attrs.get("y", 0))
            w, h = float(attrs.get("width", 0)), float(attrs.get("height", 0))
            return [(x0, y0), (x0 + w, y0 + h)]
        return []

    @staticmethod
    @lru_cache(maxsize=256)
    def _hugeicon_bounds(name: str) -> tuple[float, float, float, float]:
        """Approximate the visible shape bounds in Hugeicons viewBox units.

        Falls back to the full viewBox for the rare icon using a shape
        ``transform`` (matrices aren't applied here -- exact centering for
        those icons trades off against the complexity of inverting an
        arbitrary transform for what is only an alignment heuristic).
        """
        shapes = load_hugeicon_shapes(name)
        points: list[tuple[float, float]] = []
        for tag, attr_pairs in shapes:
            attrs = dict(attr_pairs)
            if "transform" in attrs:
                return HUGEICONS_VIEWBOX
            points.extend(Icon._shape_points(tag, attrs))
        if not points:
            return HUGEICONS_VIEWBOX
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        vx, vy, vw, vh = HUGEICONS_VIEWBOX
        pad = 1.0
        x0 = max(vx, min(xs) - pad)
        y0 = max(vy, min(ys) - pad)
        x1 = min(vx + vw, max(xs) + pad)
        y1 = min(vy + vh, max(ys) + pad)
        return (x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))

    def content_bbox(self, theme: Theme) -> tuple[float, float, float, float]:
        s = self._size_px(theme)
        if self._bank == "lucide":
            vx, vy, vw, vh = LUCIDE_VIEWBOX
            bx, by, bw, bh = self._viewbox_bounds(self.name)
        else:
            vx, vy, vw, vh = HUGEICONS_VIEWBOX
            bx, by, bw, bh = self._hugeicon_bounds(self.name)
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

        if self._bank == "lucide":
            canvas.svg_path(
                x, y, s, s,
                paths=LUCIDE_ICONS[self.name],
                viewbox=LUCIDE_VIEWBOX,
                stroke=stroke,
                stroke_width=1.75 if self.stroke_width is None else self.stroke_width,
                fill=fill,
                opacity=self.opacity,
            )
        else:
            canvas.svg_shapes(
                x, y, s, s,
                shapes=load_hugeicon_shapes(self.name),
                viewbox=HUGEICONS_VIEWBOX,
                color=stroke,
                stroke_width=self.stroke_width,
                fill=fill,
                opacity=self.opacity,
            )
