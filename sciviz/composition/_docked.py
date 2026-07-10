"""Docked: edge-straddling semantic decorations around one primary child."""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme


class Docked(Element):
    """Attach decorations to a child's corners or centre without coordinates.

    Decorations straddle the requested child boundary: ``top_right`` and
    ``bottom_right`` are centred on those corners, while ``center`` overlays
    the child's optical centre. The measured bbox contains every decoration,
    but content/primary-anchor alignment continues to expose the primary
    child. Rows therefore align node bodies even when their tabs differ.
    """

    def __init__(self, child: Element, *,
                 top_right: Optional[Element] = None,
                 bottom_right: Optional[Element] = None,
                 center: Optional[Element] = None,
                 center_fit: Optional[str] = None,
                 center_position: str = "center"):
        if not isinstance(child, Element):
            raise TypeError("Docked.child must be an Element")
        for name, value in (
            ("top_right", top_right),
            ("bottom_right", bottom_right),
            ("center", center),
        ):
            if value is not None and not isinstance(value, Element):
                raise TypeError(f"Docked.{name} must be an Element or None")
        if center_fit not in (None, "width", "height", "both"):
            raise ValueError(
                "Docked.center_fit must be None, width, height, or both"
            )
        if center_position not in ("upper", "center", "lower"):
            raise ValueError(
                "Docked.center_position must be upper, center, or lower"
            )
        if center is None and (center_fit is not None
                               or center_position != "center"):
            raise ValueError(
                "center_fit/center_position require a center decoration"
            )
        self.child = child
        self.top_right = top_right
        self.bottom_right = bottom_right
        self.center = center
        self.center_fit = center_fit
        self.center_position = center_position
        # Generic tree walkers discover routed Anchor decorations through the
        # standard ``children`` protocol.
        self.children = [
            element for element in (top_right, bottom_right, center)
            if element is not None
        ]

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.child.inflate_to(min_w, min_h)

    def _geometry(self, theme: Theme):
        child = self.child.measure(theme)
        placements: list[tuple[Element, float, float, BBox]] = []
        if self.top_right is not None:
            size = self.top_right.measure(theme)
            cx, cy, cw, ch = self.top_right.content_bbox(theme)
            placements.append((
                self.top_right,
                child.w - (cx + cw / 2),
                -(cy + ch / 2),
                size,
            ))
        if self.bottom_right is not None:
            size = self.bottom_right.measure(theme)
            cx, cy, cw, ch = self.bottom_right.content_bbox(theme)
            placements.append((
                self.bottom_right,
                child.w - (cx + cw / 2),
                child.h - (cy + ch / 2),
                size,
            ))
        if self.center is not None:
            fit_w = child.w if self.center_fit in ("width", "both") else 0.0
            fit_h = child.h if self.center_fit in ("height", "both") else 0.0
            self.center.inflate_to(fit_w, fit_h)
            size = self.center.measure(theme)
            cx, cy, cw, ch = self.center.content_bbox(theme)
            center_y = {
                "upper": child.h / 3.0,
                "center": child.h / 2.0,
                "lower": child.h * 2.0 / 3.0,
            }[self.center_position]
            placements.append((
                self.center,
                child.w / 2 - (cx + cw / 2),
                center_y - (cy + ch / 2),
                size,
            ))

        x0 = min([0.0] + [px for _e, px, _py, _s in placements])
        y0 = min([0.0] + [py for _e, _px, py, _s in placements])
        x1 = max([child.w] + [px + s.w for _e, px, _py, s in placements])
        y1 = max([child.h] + [py + s.h for _e, _px, py, s in placements])
        return child, placements, x0, y0, x1 - x0, y1 - y0

    def measure(self, theme: Theme) -> BBox:
        _child, _placements, _x0, _y0, w, h = self._geometry(theme)
        return BBox(w, h)

    def content_bbox(self, theme: Theme):
        _child, _placements, x0, y0, _w, _h = self._geometry(theme)
        cx, cy, cw, ch = self.child.content_bbox(theme)
        return (cx - x0, cy - y0, cw, ch)

    def primary_anchor_bbox(self, theme: Theme):
        _child, _placements, x0, y0, _w, _h = self._geometry(theme)
        primary = self.child.primary_anchor_bbox(theme)
        if primary is None:
            primary = self.child.content_bbox(theme)
        px, py, pw, ph = primary
        return (px - x0, py - y0, pw, ph)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        _child, placements, x0, y0, _w, _h = self._geometry(theme)
        child_x, child_y = x - x0, y - y0
        self.child.render(canvas, child_x, child_y, theme)
        for element, px, py, _size in placements:
            element.render(canvas, child_x + px, child_y + py, theme)
