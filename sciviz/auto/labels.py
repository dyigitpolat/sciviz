"""Shared connector-label measurement, placement, and obstacle registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from ..core import Theme
from .._labelplacer import place_label


Rect = Tuple[float, float, float, float]
Point = Tuple[float, float]


@dataclass(frozen=True)
class LabelBox:
    text: str
    width: float
    height: float
    size_px: float


@dataclass(frozen=True)
class PlacedLabel:
    """A placed label rectangle.

    ``rotation`` is degrees clockwise: ``0`` for horizontal text and
    ``90`` for text rotated to read top-to-bottom. Renderers use this
    flag to draw rotated SVG ``<text>`` glyphs when the placer found
    that vertical orientation gave better clearance than horizontal.
    """

    rect: Rect
    anchor: str
    rotation: float = 0.0

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.rect
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def measure_label(text: str, theme: Theme, size="small", *,
                  bold: bool = False) -> LabelBox:
    return LabelBox(
        text=text,
        width=theme.text_width(text, size, bold=bold),
        height=theme.text_height(size),
        size_px=theme.size_px(size),
    )


def _try_place(segment, label_w, label_h, obstacles, prefer, gap):
    """Return ``(rect, anchor, total_overlap)`` from ``place_label``."""
    rect, anchor = place_label(
        segment=segment, label_w=label_w, label_h=label_h,
        obstacles=list(obstacles), prefer=prefer, gap=gap,
    )

    def _overlap(rect_a, rect_b):
        ax0, ay0, ax1, ay1 = rect_a
        bx0, by0, bx1, by1 = rect_b
        ox = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        oy = max(0.0, min(ay1, by1) - max(ay0, by0))
        return ox * oy

    total_overlap = sum(_overlap(rect, ob) for ob in obstacles)
    return rect, anchor, total_overlap


def place_segment_label(segment: Tuple[Point, Point], label: LabelBox,
                        obstacles: Sequence[Rect], *,
                        prefer: str = "above",
                        gap: float = 6.0,
                        allow_rotation: bool = True) -> PlacedLabel:
    """Place a connector label oriented along the segment direction.

    The placer's orientation rule is now semantic, not opportunistic:

    * **Horizontal segments** (``|dx| > |dy|``) take a horizontal label.
      It is placed above (or below) the wire. The parent layout is
      responsible for sizing the gap large enough; rotating the label
      sideways here would be visually misleading.
    * **Vertical segments** take a 90-degree rotated label, aligned
      with the wire and placed to its left (or right).

    Pass ``allow_rotation=False`` to force a horizontal label even on
    vertical wires (rare; mostly for legacy callers).
    """
    p1, p2 = segment
    is_horizontal = abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1])
    if is_horizontal or not allow_rotation:
        rect_h, anchor_h, _ = _try_place(
            segment, label.width, label.height, obstacles, prefer, gap,
        )
        return PlacedLabel(rect=rect_h, anchor=anchor_h, rotation=0.0)
    # Vertical wire: rotate the label to read along the wire.
    rect_v, anchor_v, _ = _try_place(
        segment, label.height, label.width, obstacles, prefer, gap,
    )
    return PlacedLabel(rect=rect_v, anchor=anchor_v, rotation=90.0)


def place_curve_label(points: Sequence[Point], label: LabelBox,
                      obstacles: Sequence[Rect], *,
                      prefer: str = "above",
                      gap: float = 6.0,
                      allow_rotation: bool = True) -> PlacedLabel:
    if len(points) < 2:
        raise ValueError("place_curve_label requires at least two points")
    mid = len(points) // 2
    a = points[max(0, mid - 1)]
    b = points[min(len(points) - 1, mid)]
    if a == b and len(points) >= 2:
        a, b = points[0], points[-1]
    return place_segment_label((a, b), label, obstacles, prefer=prefer,
                               gap=gap, allow_rotation=allow_rotation)


def register_label_obstacle(registry: dict, rect: Rect, owner_id: str = "label") -> None:
    labels = registry.setdefault("__label_obstacles__", [])
    labels.append(rect)
    idx = len(labels)
    x0, y0, x1, y1 = rect
    registry[f"__label_{idx}_{owner_id}"] = (x0, y0, x1 - x0, y1 - y0)


def registry_label_obstacles(registry: dict) -> list[Rect]:
    out = list(registry.get("__label_obstacles__", []))
    for name, b in registry.items():
        if name.startswith("__label_") and isinstance(b, tuple) and len(b) == 4:
            x, y, w, h = b
            out.append((x, y, x + w, y + h))
    return out
