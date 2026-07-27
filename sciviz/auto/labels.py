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
    #: Individual lines ("\n"-split); single-line labels carry one entry.
    lines: Tuple[str, ...] = ()

    def __post_init__(self):
        if not self.lines:
            object.__setattr__(self, "lines", tuple(self.text.split("\n")))


@dataclass(frozen=True)
class PlacedLabel:
    """A placed label rectangle.

    ``rotation`` is degrees clockwise: ``0`` for horizontal text and
    ``90`` for text rotated to read top-to-bottom. Renderers use this
    flag to draw rotated SVG ``<text>`` glyphs when the placer found
    that vertical orientation gave better clearance than horizontal.

    ``inline`` marks the walled-corridor fallback: the label sits
    centred *on* its own wire (schematic convention) and the renderer
    must paint a background halo so the wire reads as passing behind
    the text. Offset placements keep ``inline=False``.

    ``overlapped`` marks a placement that could not clear every
    obstacle. It is the placer's admission of defeat, and it obliges the
    renderer to paint the same halo: a caption may end up sitting over
    ink, but it must never be *struck through* by it. Legibility is the
    one thing the placer is not allowed to lose.
    """

    rect: Rect
    anchor: str
    rotation: float = 0.0
    inline: bool = False
    overlapped: bool = False

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.rect
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def measure_label(text: str, theme: Theme, size="small", *,
                  bold: bool = False) -> LabelBox:
    """Measure a connector label; ``"\\n"`` splits it into stacked lines.

    Multi-line labels measure as a block (widest line by the summed line
    heights), letting long captions ride short corridors that a one-line
    label could never fit.
    """
    lines = tuple(text.split("\n"))
    line_h = theme.text_height(size)
    return LabelBox(
        text=text,
        width=max(theme.text_width(line, size, bold=bold) for line in lines),
        height=line_h * len(lines) * (1.0 if len(lines) == 1 else 1.12),
        size_px=theme.size_px(size),
        lines=lines,
    )


def wrap_label(text: str, theme: Theme, size="small", *,
               max_width: float, bold: bool = False) -> str:
    """Greedily re-wrap a caption to ``max_width``, honouring hard breaks.

    A caption's job is to sit next to its wire and be read; how its
    words are distributed over lines is the layout's business, not the
    author's. Authors used to insert ``"\n"`` by hand to make a caption
    fit a narrow corridor -- and, failing that, deleted words. Both are
    layout decisions leaking into content.

    A word wider than the budget still gets its own line: the longest
    word is the hard floor on how narrow a caption can be made, and the
    corridor reservation is sized from exactly that floor.
    """
    out_lines = []
    for hard in text.split("\n"):
        words = hard.split()
        if not words:
            continue
        line = words[0]
        for word in words[1:]:
            trial = f"{line} {word}"
            if theme.text_width(trial, size, bold=bold) <= max_width:
                line = trial
            else:
                out_lines.append(line)
                line = word
        out_lines.append(line)
    return "\n".join(out_lines) if out_lines else text


def narrowest_wrap(text: str, theme: Theme, size="small", *,
                   bold: bool = False) -> str:
    """The narrowest block a caption can be set in: one word per line."""
    widest_word = 0.0
    for hard in text.split("\n"):
        for word in hard.split():
            widest_word = max(widest_word,
                              theme.text_width(word, size, bold=bold))
    if widest_word <= 0.0:
        return text
    return wrap_label(text, theme, size, max_width=widest_word, bold=bold)


@dataclass(frozen=True)
class CaptionFit:
    """How a caption will be set: the measured block and its orientation.

    ``upright`` means the text reads horizontally. Beside a horizontal
    wire that is the *along* form (the legible one, worth corridor);
    beside a vertical wire it is the *across* form (also the legible
    one, and free). Rotation is what is left when neither fits.
    """

    label: LabelBox
    upright: bool


def fitted_caption(text: str, theme: Theme, size="small", *,
                   src_side: str, dst_side: str,
                   neighbour_extent: Optional[float] = None,
                   bold: bool = False) -> LabelBox:
    """The caption as it will actually be set.

    This is the single place the orientation/wrapping question is
    answered. Corridor reservation and label placement both call it, so
    what the layout pays for and what the placer draws can no longer
    disagree -- that split was why captions ended up rotated inside
    corridors that had been sized for rotated captions, a decision that
    justified itself.

    Two *facing* pinned sides form a direct corridor between neighbours,
    which is narrow by construction. The caption is wrapped to its
    narrowest block there so it can be set UPRIGHT and read along the
    wire; rotation stays what it should be, a fallback for a corridor
    that is genuinely walled. Every other geometry keeps the author's
    line breaks: those routes have long arms in open space.
    """
    return caption_fit(text, theme, size, src_side=src_side,
                       dst_side=dst_side,
                       neighbour_extent=neighbour_extent,
                       bold=bold).label


def caption_fit(text: str, theme: Theme, size="small", *,
                src_side: str, dst_side: str,
                neighbour_extent: Optional[float] = None,
                bold: bool = False) -> CaptionFit:
    """Resolve caption wrapping and orientation in one place.

    On a facing pair the caption is wrapped to its narrowest block so it
    can be set upright and read along the wire. If even that block would
    open a corridor wider than ``caption_corridor_ratio`` of the
    narrower node it separates, the corridor would out-measure the
    things it is separating: the caption is then set on one line to be
    turned across the wire, which costs the corridor nothing.
    """
    sides = {src_side, dst_side}
    one_line = measure_label(text, theme, size, bold=bold)
    if sides == {"left", "right"}:
        # A left/right corridor is narrow horizontally and tall
        # vertically: wrapping the caption narrow buys exactly the
        # dimension that is scarce, so it can be set upright and read
        # along the wire.
        block = measure_label(narrowest_wrap(text, theme, size, bold=bold),
                              theme, size, bold=bold)
        if neighbour_extent:
            cap = float(neighbour_extent) * getattr(
                theme, "caption_corridor_ratio", 0.35)
            if block.width > cap:
                return CaptionFit(one_line, False)
        return CaptionFit(block, True)
    if sides == {"top", "bottom"}:
        # A top/bottom corridor is the mirror image: height is scarce
        # and width is free. Wrapping narrow here would stack the
        # caption into the one dimension that costs -- the caption stays
        # on one line and reads across the wire, which is upright.
        return CaptionFit(one_line, True)
    return CaptionFit(one_line, True)


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


def _route_side_preference(points: Sequence[Point], i: int,
                           fallback: str) -> str:
    """Prefer the convex side of a bent route for segment ``i``.

    A dog-leg's caption belongs on the outside of the bend -- the side
    away from the route's own other legs -- so it annotates its arm
    from open space instead of hovering over a perpendicular leg or
    sitting inside the elbow.  The signed perpendicular offsets of the
    route's *other* points mark the concave side; their sum picks the
    side to avoid (distance-weighted, so long legs dominate over stub
    legs on Z-shaped routes).  Straight routes -- no other points off
    the segment axis -- keep ``fallback``, the caller's preference.
    """
    (x1, y1), (x2, y2) = points[i], points[i + 1]
    is_horizontal = abs(x2 - x1) >= abs(y2 - y1)
    off = 0.0
    for j, (px, py) in enumerate(points):
        if j in (i, i + 1):
            continue
        off += (py - y1) if is_horizontal else (px - x1)
    if abs(off) < 1e-6:
        return fallback
    if is_horizontal:
        # SVG y grows downward: route mass below the arm -> caption above.
        return "above" if off > 0 else "below"
    return "left" if off > 0 else "right"


def place_polyline_label(points: Sequence[Point], label: LabelBox,
                         obstacles: Sequence[Rect], *,
                         prefer: str = "above",
                         gap: float = 6.0,
                         allow_rotation: bool = True,
                         wire_width: float = 0.0) -> PlacedLabel:
    """Place a connector label along the best segment of a polyline.

    Generalises :func:`place_segment_label` from "the longest segment"
    to "whichever segment admits a collision-free offset placement":
    readable horizontal segments are tried first when they are long enough
    to carry the label, then remaining segments are tried longest-first.
    This keeps paper-figure labels horizontal whenever the route provides a
    genuine caption lane, while preserving vertical labels for truly
    vertical routes.  The first collision-free placement wins; when every
    candidate overlaps something, the minimum-overlap candidate is used.

    The polyline's *other* segments are treated as obstacles for each
    candidate (inflated by ``wire_width``), so a label never sits on a
    perpendicular leg of its own wire.

    Orientation follows the wire: horizontal legs take horizontal
    labels. Vertical legs prefer a 90-degree rotated label that reads
    along the wire only when the leg is long enough to genuinely carry
    the rotated text (leg length >= label width plus clearance); short
    vertical hops -- e.g. the card-to-card gaps of a stacked column --
    prefer a horizontal label beside the leg, so one short edge in a
    stack never reads top-to-bottom while its sibling edges read
    left-to-right merely because its label happened to fit rotated.
    Multi-line captions never prefer rotation regardless of leg length:
    a block reads as stacked horizontal lines, and rotating it yields
    parallel columns of tilted text.
    Either way the non-preferred orientation remains a fallback and the
    lower-overlap orientation wins when the preferred one collides.

    Side preference is geometric on bent routes: each candidate segment
    prefers the convex side of the dog-leg -- the side away from the
    route's own other legs -- so a caption annotates its arm from the
    outside instead of hovering over a perpendicular leg or sitting
    inside the elbow.  Straight routes keep the caller's ``prefer``.
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
            is_horizontal = abs(x2 - x1) >= abs(y2 - y1)
            horizontal_caption_lane = (
                is_horizontal and length >= label.width + 2.0 * gap
            )
            seg_indices.append((length, i, horizontal_caption_lane))
    if not seg_indices:
        seg_indices = [(0.0, 0, False)]
    # Horizontal reading is substantially faster in dense research figures.
    # Prefer it only when the segment can actually carry the label; tiny
    # endpoint stubs must never steal captions from a useful vertical run.
    seg_indices.sort(key=lambda t: (not t[2], -t[0]))

    best: Optional[Tuple[float, int, float, PlacedLabel]] = None
    for length, i, _horizontal_caption_lane in seg_indices:
        seg = (points[i], points[i + 1])
        others = [r for j, r in enumerate(own_rects) if j != i]
        cand_obstacles = list(obstacles) + others
        p1, p2 = seg
        is_horizontal = abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1])
        seg_prefer = _route_side_preference(points, i, prefer)
        attempts: list[Tuple[int, float]] = [(0, 0.0)]  # (pref_pen, rotation)
        if is_horizontal and allow_rotation and len(label.lines) == 1:
            # A horizontal hand-off between two side-by-side nodes lives
            # in a tall, narrow corridor: there is plenty of room ACROSS
            # the wire and almost none along it. A rotated caption needs
            # only its line height of corridor width, so it is the
            # fallback that lets such a wire keep its caption instead of
            # forcing the corridor to grow to the caption's full length
            # -- or, worse, forcing the author to delete the words.
            # Horizontal reading still wins whenever it fits.
            attempts = [(0, 0.0), (1, 90.0)]
        elif not is_horizontal and allow_rotation:
            # A rotated label reads *along* its wire, which only earns the
            # reader's head-tilt when the leg genuinely carries the text.
            # Short vertical hops keep horizontal preference so their
            # orientation stays consistent with sibling edges in the same
            # stack (whose longer labels resolve horizontal anyway).
            # Multi-line captions never prefer rotation: a block reads as
            # stacked horizontal lines, and rotating it yields parallel
            # columns of tilted text -- for blocks the rotated orientation
            # remains a collision fallback only.
            carries_rotated = (len(label.lines) == 1
                               and length >= label.width + 2.0 * gap)
            if carries_rotated:
                attempts = [(0, 90.0), (1, 0.0)]
            else:
                attempts = [(0, 0.0), (1, 90.0)]
        for pref_pen, rotation in attempts:
            if rotation:
                rect, anchor, overlap = _try_place(
                    seg, label.height, label.width, cand_obstacles,
                    seg_prefer, gap)
            else:
                rect, anchor, overlap = _try_place(
                    seg, label.width, label.height, cand_obstacles,
                    seg_prefer, gap)
            placed = PlacedLabel(rect=rect, anchor=anchor, rotation=rotation)
            if overlap <= 0.0 and pref_pen == 0:
                return placed
            score = (overlap, pref_pen, -length)
            if best is None or score < (best[0], best[1], -best[2]):
                best = (overlap, pref_pen, length, placed)
            if overlap <= 0.0:
                break
    assert best is not None
    if best[0] > 0.5:
        # Walled corridor: every offset candidate collides with a card,
        # another wire, or free text. Fall back to the schematic
        # convention -- centre the label ON its own wire and let the
        # renderer paint a background halo behind it. The label's own
        # wire is not an obstacle here (it deliberately passes behind),
        # but everything else still is.
        inline = _place_inline(points, own_rects, label, obstacles, gap)
        if inline is not None:
            return inline
    if best[0] > 0.0:
        # No clear home and no on-wire fallback either: hand the
        # renderer a knockout so the caption still reads.
        from dataclasses import replace as _replace
        return _replace(best[3], overlapped=True)
    return best[3]


def _place_inline(points: Sequence[Point], own_rects: Sequence[Rect],
                  label: LabelBox, obstacles: Sequence[Rect],
                  gap: float) -> Optional[PlacedLabel]:
    """On-wire fallback placement (see :func:`place_polyline_label`).

    Walks segments longest-first and tries label rectangles centred on
    the wire at several fractions. A candidate is accepted only when it
    clears every *foreign* obstacle; the wire's own legs are exempt
    (the halo makes the wire read as passing behind the text).
    """
    order = []
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        order.append((length, i))
    order.sort(reverse=True)
    for length, i in order:
        p1, p2 = points[i], points[i + 1]
        is_horizontal = abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1])
        if is_horizontal or len(label.lines) > 1:
            # Blocks stay horizontal even on vertical legs (see
            # :func:`place_polyline_label`): a rotated multi-line block
            # reads as parallel columns of tilted text.
            w, h, rotation = label.width, label.height, 0.0
        else:
            w, h, rotation = label.height, label.width, 90.0
        # The wire must genuinely carry the text: the along-axis extent
        # of the label plus a small margin must fit inside the leg.
        along = w if is_horizontal else h
        if length < along + gap:
            continue
        for t in (0.5, 0.4, 0.6, 0.3, 0.7):
            cx = p1[0] + (p2[0] - p1[0]) * t
            cy = p1[1] + (p2[1] - p1[1]) * t
            rect = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            # Keep the whole rect within the leg's along-axis span.
            if is_horizontal:
                lo, hi = sorted((p1[0], p2[0]))
                if rect[0] < lo or rect[2] > hi:
                    continue
            else:
                lo, hi = sorted((p1[1], p2[1]))
                if rect[1] < lo or rect[3] > hi:
                    continue
            other_legs = [r for j, r in enumerate(own_rects) if j != i]
            blocked = any(
                (min(rect[2], ob[2]) > max(rect[0], ob[0])
                 and min(rect[3], ob[3]) > max(rect[1], ob[1]))
                for ob in list(obstacles) + other_legs
            )
            if blocked:
                continue
            return PlacedLabel(rect=rect, anchor="middle",
                               rotation=rotation, inline=True)
    return None


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
