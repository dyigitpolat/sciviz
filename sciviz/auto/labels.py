"""Shared connector-label measurement, placement, and obstacle registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

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


def segment_rects(points: Sequence[Point], pad: float = 0.0) -> list[Rect]:
    """Bounding rectangles (one per polyline segment), inflated by ``pad``.

    Used to register drawn wires as obstacles for label placement so a
    connector label never sits on top of another connector's line.
    """
    out: list[Rect] = []
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        if abs(x1 - x2) < 0.25 and abs(y1 - y2) < 0.25:
            continue
        out.append((min(x1, x2) - pad, min(y1, y2) - pad,
                    max(x1, x2) + pad, max(y1, y2) + pad))
    return out


def place_polyline_label(points: Sequence[Point], label: LabelBox,
                         obstacles: Sequence[Rect], *,
                         prefer: str = "above",
                         gap: float = 6.0,
                         allow_rotation: bool = True,
                         wire_width: float = 0.0) -> PlacedLabel:
    """Place a connector label along the best segment of a polyline.

    Generalises :func:`place_segment_label` from "the longest segment"
    to "whichever segment admits a collision-free offset placement":
    segments are tried longest-first and the first placement that
    overlaps no obstacle wins, so labels nudge themselves onto another
    leg of the wire when the longest leg is hemmed in by cards, other
    labels, or other wires. When every candidate overlaps something,
    the minimum-overlap candidate (ties: longer segment) is returned.

    The polyline's *other* segments are treated as obstacles for each
    candidate (inflated by ``wire_width``), so a label never sits on a
    perpendicular leg of its own wire.

    Orientation follows the wire: horizontal legs take horizontal
    labels; vertical legs prefer a 90-degree rotated label that reads
    along the wire, but when the rotated label cannot find a
    collision-free slot (typically a short vertical hop between two
    stacked cards) a horizontal label beside the leg is tried as a
    fallback and the lower-overlap orientation wins.
    """
    if len(points) < 2:
        raise ValueError("place_polyline_label requires at least two points")
    own_rects = []
    seg_indices = []
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        pad = max(0.5, wire_width)
        own_rects.append((min(x1, x2) - pad, min(y1, y2) - pad,
                          max(x1, x2) + pad, max(y1, y2) + pad))
        if length > 1.0:
            seg_indices.append((length, i))
    if not seg_indices:
        seg_indices = [(0.0, 0)]
    seg_indices.sort(key=lambda t: -t[0])

    best: Optional[Tuple[float, int, float, PlacedLabel]] = None
    for length, i in seg_indices:
        seg = (points[i], points[i + 1])
        others = [r for j, r in enumerate(own_rects) if j != i]
        cand_obstacles = list(obstacles) + others
        p1, p2 = seg
        is_horizontal = abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1])
        attempts: list[Tuple[int, float]] = [(0, 0.0)]  # (pref_pen, rotation)
        if not is_horizontal and allow_rotation:
            attempts = [(0, 90.0), (1, 0.0)]
        for pref_pen, rotation in attempts:
            if rotation:
                rect, anchor, overlap = _try_place(
                    seg, label.height, label.width, cand_obstacles,
                    prefer, gap)
            else:
                rect, anchor, overlap = _try_place(
                    seg, label.width, label.height, cand_obstacles,
                    prefer, gap)
            placed = PlacedLabel(rect=rect, anchor=anchor, rotation=rotation)
            if overlap <= 0.0 and pref_pen == 0:
                return placed
            score = (overlap, pref_pen, -length)
            if best is None or score < (best[0], best[1], -best[2]):
                best = (overlap, pref_pen, length, placed)
            if overlap <= 0.0:
                break
    assert best is not None
    return best[3]


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
