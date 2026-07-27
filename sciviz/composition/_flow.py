"""Flow: declarative curved/orthogonal arrow between named anchors.

Holds :class:`Labeled`, which composes ``Flow`` for its internal
label-to-source arrow.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text, TextBlock
from ..layout import Row, Column, Spacer
from ._anchor import Anchor, _side_point, _side_point_frac


def _draw_placed_label(canvas: Canvas, placed, text: str, size_px: float,
                       fill: str, halo_fill: str | None = None) -> None:
    """Render a connector label at the placer's chosen rectangle.

    Honours :attr:`PlacedLabel.rotation` so labels found by the placer
    to fit better vertically are drawn rotated 90 degrees clockwise --
    useful in narrow horizontal corridors. Anchored at "middle" by
    default so the placer's centred ``rect`` lines up correctly.

    When the placer fell back to an *inline* placement (label centred on
    its own wire), a ``halo_fill`` background rectangle is painted first
    so the wire reads as passing behind the text.
    """
    x0, y0, x1, y1 = placed.rect
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    if halo_fill is not None and (getattr(placed, "inline", False)
                                  or getattr(placed, "overlapped", False)):
        pad = max(1.5, size_px * 0.2)
        canvas.rect(x0 - pad, y0 - pad,
                    (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad,
                    fill=halo_fill, stroke="none")
    # Connector prose is annotation, not a mathematical variable.  Infer
    # the common case so authors do not need a typography flag on every
    # edge: short identifiers and symbolic expressions remain italic,
    # ordinary words/phrases are upright and substantially easier to read.
    stripped = text.strip()
    symbolic = (
        (" " not in stripped and len(stripped) <= 3)
        or any(ch in stripped for ch in "_{}^=+-×÷∑∏∈→←λμσ")
    )
    # "\n" stacks label lines as a block centred in the placed rect,
    # in both horizontal and rotated orientations.
    lines = text.split("\n")
    n = len(lines)
    line_h = size_px * (1.0 if n == 1 else 1.12)
    rotation = getattr(placed, "rotation", 0.0)
    for i, line in enumerate(lines):
        # This line's centre offset from the block centre, along the
        # reading-perpendicular axis.
        off = (i - (n - 1) / 2.0) * line_h
        if rotation:
            # Rotated block: successive lines advance along +x (the
            # rotated "downward" direction for 90-degree text).
            canvas.text(cx + off, cy, line,
                        size=size_px, fill=fill, italic=symbolic,
                        anchor="middle", baseline="middle",
                        rotate=rotation)
        else:
            # Horizontal text: baseline approximated from the line's
            # vertical centre (fonts have ~33% descender).
            baseline_y = cy + off + size_px * 0.33
            canvas.text(cx, baseline_y, line,
                        size=size_px, fill=fill, italic=symbolic,
                        anchor=placed.anchor)


class Flow:
    """A curved arrow specification between two named anchors.

    Resolved by :class:`Flowed` after the child has rendered.  The author
    never touches pixel coordinates -- routing is computed from bbox sides.
    """

    _STYLE_UNSET = object()

    def __init__(self, src: str, dst: str, *,
                 src_side: str = "auto",
                 dst_side: str = "auto",
                 color = "text",
                 label: Optional[str] = None,
                 label_color = None,
                 dashed: bool = False,
                 curvature: float = 0.5,
                 detour: float = 24.0,
                 arrow: bool = True,
                 auto_route: bool = True,
                 route_around_labels: bool = False,
                 clearance: Optional[float] = None,
                 style = _STYLE_UNSET):
        """
        ``src_side`` / ``dst_side`` -- which side of each bbox the flow
            attaches to.  Default ``"auto"`` picks the boundary side facing
            the other anchor: above/below/left/right.  Named sides:
            ``top/bottom/left/right`` (midpoints) and the four corners.

        ``curvature`` -- 0..1, how much the curve bows (0 = straight).
        ``detour``    -- pixels the curve bows beyond the larger of src/dst,
                         used when src and dst exit in the same direction.
        ``auto_route`` -- when True (default), the topological planner
            routes the wire as axis-aligned segments that dodge siblings.
            Set to False to fall back to a simple straight/curved segment;
            an explicit ``style=`` overrides this toggle.
        ``clearance`` -- preferred distance (px) between the routed wire
            and every obstacle that is not one of its own endpoints.
            Default ``None`` resolves at render time to a theme-
            proportional margin (``theme.unit * 4/3``; 8 px on the
            default theme) so compressed paper themes keep proportional
            breathing room. The planner degrades the margin gracefully
            when corridors are too narrow rather than failing.
        """
        if style is Flow._STYLE_UNSET:
            style = "orthogonal" if auto_route else "straight"
        self.src = src
        self.dst = dst
        self.src_side = src_side
        self.dst_side = dst_side
        self.color = color
        self.label = label
        self.label_color = label_color
        self.dashed = dashed
        self.curvature = curvature
        self.detour = detour
        self.arrow = arrow
        self.style = style
        self.route_around_labels = route_around_labels
        self.clearance = clearance

    def _head_flags(self) -> tuple[bool, bool]:
        if self.arrow is True or self.arrow == "end":
            return False, True
        if self.arrow is False or self.arrow == "none":
            return False, False
        if self.arrow == "start":
            return True, False
        if self.arrow == "both":
            return True, True
        raise ValueError("head must be bool or one of none/start/end/both")

    def _neighbour_extent(self, src_box, dst_box) -> float:
        """Size of the narrower node a facing corridor separates.

        The cap on how much corridor a caption may open is expressed
        relative to this, so it scales with the diagram instead of being
        an absolute constant that stops working when nodes grow.
        """
        if src_box is None or dst_box is None:
            return 0.0

        def _wh(box):
            if hasattr(box, "w"):
                return float(box.w), float(box.h)
            return float(box[2]), float(box[3])

        sw, sh = _wh(src_box)
        dw, dh = _wh(dst_box)
        sides = {self.src_side, self.dst_side}
        if sides == {"left", "right"}:
            return float(min(sw, dw))     # corridor runs horizontally
        if sides == {"top", "bottom"}:
            return float(min(sh, dh))     # corridor runs vertically
        return float(min(sw, dw, sh, dh))

    def _clearance_px(self, theme: Theme) -> float:
        """Resolve the obstacle-clearance margin for this flow."""
        if self.clearance is not None:
            return max(0.0, float(self.clearance))
        return theme.unit * (4.0 / 3.0)

    @staticmethod
    def _auto_side(self_bbox, other_bbox):
        """Return the side of ``self_bbox`` whose midpoint best faces other."""
        sx, sy, sw, sh = self_bbox
        ox, oy, ow, oh = other_bbox
        self_cx, self_cy = sx + sw / 2, sy + sh / 2
        other_cx, other_cy = ox + ow / 2, oy + oh / 2
        dx = other_cx - self_cx
        dy = other_cy - self_cy
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "bottom" if dy > 0 else "top"

    def _render(self, canvas: Canvas, theme: Theme, registry: dict,
                defer_label: bool = False):
        """Draw the wire; place the label now or return a label closure.

        With ``defer_label=False`` (legacy behaviour) the label is placed
        immediately after the wire. With ``defer_label=True`` the wire is
        drawn and a zero-argument closure is returned; the caller invokes
        it after *every* wire in the scope has been drawn, so each label
        sees the complete set of wires (and all free ink) as obstacles.
        This two-phase discipline is what keeps a label from landing on a
        wire that merely happened to be drawn later.
        """
        sb = registry.get(self.src)
        db = registry.get(self.dst)
        if sb is None or db is None:
            return None
        src_side = (
            registry.get(f"__preferred_side_{self.src}",
                         self._auto_side(sb, db))
            if self.src_side == "auto" else self.src_side
        )
        dst_side = (
            registry.get(f"__preferred_side_{self.dst}",
                         self._auto_side(db, sb))
            if self.dst_side == "auto" else self.dst_side
        )
        src_frac = getattr(self, "_share_src_frac", 0.5)
        dst_frac = getattr(self, "_share_dst_frac", 0.5)
        sx, sy = _side_point_frac(sb, src_side, src_frac)
        dx, dy = _side_point_frac(db, dst_side, dst_frac)

        col = theme.color_of(self.color)
        label_col = theme.color_of(
            self.label_color if self.label_color is not None else self.color
        )
        sw = theme.connector
        dash = "5,3" if self.dashed else None
        marker_start, marker_end = self._head_flags()
        marker = (canvas.define_arrow_marker(
                      color=col, stroke_width=sw,
                      arrow_size=getattr(theme, "arrow_size", None),
                      name_hint="flow")
                  if marker_start or marker_end else None)

        # Orthogonal routing is delegated to the shared topological
        # planner (`sciviz.routing`).  The planner decides which region
        # boundaries *must* be crossed (the symmetric difference of the
        # two endpoints' region ancestors) and forbids the path from
        # entering any other region.  This replaces the ad-hoc vertical
        # / horizontal / mixed branches that used to live here.
        if self.style == "orthogonal":
            from .. import routing as _rt

            tap = theme.unit * 2
            sb_x, sb_y, sb_w, sb_h = sb
            db_x, db_y, db_w, db_h = db

            # Raw anchor and region boxes.  Private ``__*`` keys
            # (e.g. drawn-segment lists) are skipped.
            all_anchors = []
            all_regions = []
            for name, b in registry.items():
                if name.startswith("__region_"):
                    bx, by, bw, bh = b
                    all_regions.append(_rt.Box(x=bx, y=by, w=bw, h=bh,
                                               name=name, kind="region"))
                elif name.startswith("__label_") and self.route_around_labels:
                    bx, by, bw, bh = b
                    all_anchors.append(_rt.Box(x=bx, y=by, w=bw, h=bh,
                                               name=name, kind="anchor"))
                elif name.startswith("__"):
                    continue
                else:
                    bx, by, bw, bh = b
                    all_anchors.append(_rt.Box(x=bx, y=by, w=bw, h=bh,
                                               name=name, kind="anchor"))
            src_box = _rt.Box(x=sb_x, y=sb_y, w=sb_w, h=sb_h,
                              name=self.src, kind="anchor")
            dst_box = _rt.Box(x=db_x, y=db_y, w=db_w, h=db_h,
                              name=self.dst, kind="anchor")
            # Free-standing text ink (zone headers, captions, chips that
            # are not anchors) blocks wires exactly like anchor boxes.
            # Ink clinging to either endpoint is exempt so the wire can
            # still reach its own boundary.
            from ..auto.ink import free_text_rects, rects_excluding_endpoints
            free_ink = rects_excluding_endpoints(
                free_text_rects(canvas, registry),
                [sb, db],
            )
            for (ix0, iy0, ix1, iy1) in free_ink:
                all_anchors.append(_rt.Box(x=ix0, y=iy0,
                                           w=ix1 - ix0, h=iy1 - iy0,
                                           name="__ink__", kind="anchor"))
            src_frac = getattr(self, "_share_src_frac", 0.5)
            dst_frac = getattr(self, "_share_dst_frac", 0.5)
            drawn_so_far = registry.get("__drawn_segments__", ())
            from dataclasses import replace as _dc_replace
            # The planner must know how much of each stub the
            # arrowhead will eat, or a marker crowded against a
            # neighbouring box ends up with no visible shaft behind it.
            policy = _dc_replace(_rt.DEFAULT_POLICY,
                                 min_clearance=self._clearance_px(theme),
                                 head_len=theme.arrow_head_px)
            # A labeled wire is only valid when some arm can carry its
            # caption; hand the measured caption box to the planner so
            # short-armed candidates are rejected while alternatives
            # exist.
            label_extent = None
            label_rotatable = False
            caption = self.label
            neighbour_extent = self._neighbour_extent(src_box, dst_box)
            if self.label:
                from ..auto.labels import caption_fit as _fit
                _probe_fit = _fit(
                    self.label, theme,
                    getattr(theme, "connector_label_size", "small"),
                    src_side=self.src_side, dst_side=self.dst_side,
                    neighbour_extent=neighbour_extent)
                _probe = _probe_fit.label
                caption = _probe.text
                label_extent = (_probe.width, _probe.height)
                # Single lines may be rotated by the placer; blocks are
                # never set as columns of tilted text. The planner has to
                # judge homes by the same rule the placer will apply, or
                # the two disagree and the route runs away looking for an
                # arm the caption does not need.
                label_rotatable = not _probe_fit.upright
            plan = _rt.plan_path(
                _rt.Endpoint(src_box, src_side, tap=tap,
                             tap_fraction=src_frac),
                _rt.Endpoint(dst_box, dst_side, tap=tap,
                             tap_fraction=dst_frac),
                anchors=all_anchors,
                regions=all_regions,
                existing_segments=list(drawn_so_far),
                policy=policy,
                label_extent=label_extent,
                label_gap=theme.unit,
                label_rotatable=label_rotatable,
            )

            # Retain `anchor_obstacles` for label-placement collision
            # avoidance below.  Critically we include the src and dst
            # bboxes too: otherwise label placement is allowed to land
            # the text *inside* the very card it is meant to annotate,
            # overlapping that card's body content. The router still
            # has access to its own src/dst geometry separately.
            anchor_obstacles = [b for name, b in registry.items()
                                if not name.startswith("__region_")
                                and not name.startswith("__")]
            # Pick up already-drawn segments from earlier flows in the
            # same Flowed scope so crossings become semicircular jump
            # arcs instead of plain intersections.
            drawn = registry.setdefault("__drawn_segments__", [])
            drawn_before = list(drawn)
            path = plan.waypoints
            _rt.render_orthogonal(
                canvas, plan,
                stroke=col, width=sw,
                dasharray=dash,
                marker_end=marker if marker_end else None,
                marker_start=marker if marker_start else None,
                # Ordinary directed edges terminate cleanly at node borders.
                # Dots are reserved for explicit bus/junction semantics; a
                # dot on every routed source adds unsupported visual meaning
                # and makes dense paper figures look like editor debug output.
                src_dot=False,
                existing_segments=drawn_before,
                hop_radius=max(2.5, sw * 2.5),
            )
            # Record the segments we just drew so subsequent flows can
            # detect crossings against them.
            own_segments = []
            for i in range(len(path) - 1):
                p1 = path[i]; p2 = path[i + 1]
                if abs(p1[0] - p2[0]) < 0.5 and abs(p1[1] - p2[1]) < 0.5:
                    continue
                seg = (p1[0], p1[1], p2[0], p2[1])
                drawn.append(seg)
                own_segments.append(seg)

            if not (self.label and len(path) >= 2):
                return None

            def _label_pass():
                from ..auto.ink import free_text_rects as _free_ink
                from ..auto.labels import (
                    fitted_caption, place_polyline_label,
                    register_label_obstacle, registry_label_obstacles,
                    segment_rects,
                )
                sz_tok = getattr(theme, "connector_label_size", "small")
                lbl = fitted_caption(
                    self.label, theme, sz_tok,
                    src_side=self.src_side, dst_side=self.dst_side,
                    neighbour_extent=neighbour_extent)
                all_anchor_obstacles = [
                    (ox, oy, ox + ow, oy + oh)
                    for ox, oy, ow, oh in anchor_obstacles
                ]
                all_anchor_obstacles.extend(registry_label_obstacles(registry))
                # Free-standing text ink is a label obstacle too, so a
                # connector caption never sits on a header or note.
                all_anchor_obstacles.extend(_free_ink(canvas, registry))
                # Every other wire drawn in this scope is an obstacle: a
                # label must not sit across another connector's line.
                # (Under deferred placement this set is complete; the
                # label's own legs are handled by the placer itself.)
                own = set(own_segments)
                wire_pad = max(0.5, sw)
                for seg in registry.get("__drawn_segments__", ()):  # noqa: B023
                    if seg in own:
                        continue
                    ex1, ey1, ex2, ey2 = seg
                    all_anchor_obstacles.extend(
                        segment_rects([(ex1, ey1), (ex2, ey2)], wire_pad))
                # The placer walks every leg of this wire longest-first
                # and offsets the label perpendicular to the chosen leg,
                # dodging cards, other labels, other wires, and the
                # wire's own perpendicular legs; in walled corridors it
                # falls back to an on-wire placement with a halo.
                placed = place_polyline_label(
                    path, lbl,
                    obstacles=all_anchor_obstacles,
                    prefer="above",
                    gap=theme.unit * 1.0,
                    wire_width=sw,
                )
                _draw_placed_label(canvas, placed, lbl.text,
                                   lbl.size_px, label_col,
                                   halo_fill=theme.color_of("bg"))
                register_label_obstacle(registry, placed.rect, self.src)

            if defer_label:
                return _label_pass
            _label_pass()
            return None

        # Explicit straight line: render as M/L so the tangent is the line
        # direction (well-defined) and orient="auto" points the arrowhead
        # correctly.  A degenerate Bezier with curvature=0 has zero tangent
        # at endpoints, which makes marker orientation unreliable.
        # ``style="straight"`` is equivalent -- the author has asked for a
        # direct segment, curvature parameter notwithstanding.
        if self.style == "straight" or self.curvature == 0:
            d = f"M {sx:.2f},{sy:.2f} L {dx:.2f},{dy:.2f}"
            canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                       marker_end=marker if marker_end else None,
                       marker_start=marker if marker_start else None,
                       dasharray=dash)
            if not self.label:
                return None

            def _straight_label_pass():
                from ..auto.ink import free_text_rects as _free_ink
                from ..auto.labels import (
                    measure_label, place_segment_label,
                    register_label_obstacle, registry_label_obstacles,
                )
                obstacles = []
                for name, b in registry.items():
                    if name.startswith("__"):
                        continue
                    if isinstance(b, tuple) and len(b) == 4:
                        ox, oy, ow, oh = b
                        obstacles.append((ox, oy, ox + ow, oy + oh))
                obstacles += registry_label_obstacles(registry)
                obstacles += _free_ink(canvas, registry)
                lbl = measure_label(
                    self.label, theme,
                    getattr(theme, "connector_label_size", "small"))
                placed = place_segment_label(
                    ((sx, sy), (dx, dy)), lbl, obstacles,
                    prefer="above", gap=theme.unit * 1.0,
                )
                _draw_placed_label(canvas, placed, self.label,
                                   lbl.size_px, label_col)
                register_label_obstacle(registry, placed.rect, self.src)

            if defer_label:
                return _straight_label_pass
            _straight_label_pass()
            return None

        dist = ((dx - sx) ** 2 + (dy - sy) ** 2) ** 0.5
        # Control-point distance scales with actual distance.  No minimum
        # floor -- short arrows should be nearly straight, not squiggly.
        c = dist * self.curvature

        # How much to deflect the control point away from the perfectly-
        # perpendicular "out" direction, toward the other endpoint.  A
        # stronger tilt makes the tangent at each endpoint line up with
        # the curve's overall diagonal sweep (not just the side normal),
        # so arrowheads (orient="auto") point along the visual flow.
        # TILT = 0.5 means the control point's off-axis coordinate sits at
        # the midpoint between src and dst on the perpendicular axis,
        # which produces tangents essentially parallel to the line
        # source-to-dest.
        TILT = 0.5

        def out(side, px, py, tx, ty):
            dx_to = tx - px
            dy_to = ty - py
            if side == "right":
                return (px + c,                     py + dy_to * TILT)
            if side == "left":
                return (px - c,                     py + dy_to * TILT)
            if side in ("top", "topleft", "topright"):
                return (px + dx_to * TILT,          py - c)
            if side in ("bottom", "bottomleft", "bottomright"):
                return (px + dx_to * TILT,          py + c)
            return (px, py)

        c1 = out(src_side, sx, sy, dx, dy)
        c2 = out(dst_side, dx, dy, sx, sy)

        # Only override control points for the special "both-below" and
        # "both-above" arcs, which need the curve to bow outward past
        # both endpoints.  For all other cases, the tilt-aware `out()`
        # already produces tangents that follow the overall flow.
        if src_side.startswith("bottom") and dst_side.startswith("bottom"):
            # Both-below arc: bow under the diagram.
            arch_y = max(sy, dy) + self.detour
            c1 = (sx, arch_y)
            c2 = (dx, arch_y)
        elif src_side.startswith("top") and dst_side.startswith("top"):
            # Both-above arc: bow over the diagram.
            arch_y = min(sy, dy) - self.detour
            c1 = (sx, arch_y)
            c2 = (dx, arch_y)
        elif src_side.startswith("right") and dst_side.startswith("right"):
            # Compact loop to the right. Scale the bow with endpoint
            # separation but cap it at detour, so a short consume/feedback
            # edge hugs its node instead of invading the next lane.
            bow = min(self.detour, max(theme.unit * 1.5,
                                       abs(dy - sy) * 0.28))
            arch_x = max(sx, dx) + bow
            c1 = (arch_x, sy)
            c2 = (arch_x, dy)
        elif src_side.startswith("left") and dst_side.startswith("left"):
            bow = min(self.detour, max(theme.unit * 1.5,
                                       abs(dy - sy) * 0.28))
            arch_x = min(sx, dx) - bow
            c1 = (arch_x, sy)
            c2 = (arch_x, dy)

        d = (f"M {sx:.2f},{sy:.2f} "
             f"C {c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} "
             f"{dx:.2f},{dy:.2f}")
        canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                   marker_end=marker if marker_end else None,
                   marker_start=marker if marker_start else None,
                   dasharray=dash)

        if not self.label:
            return None

        def _curve_label_pass():
            from ..auto.ink import free_text_rects as _free_ink
            from ..auto.labels import (
                measure_label, place_curve_label,
                register_label_obstacle, registry_label_obstacles,
            )
            obstacles = []
            for name, b in registry.items():
                if name.startswith("__"):
                    continue
                if isinstance(b, tuple) and len(b) == 4:
                    ox, oy, ow, oh = b
                    obstacles.append((ox, oy, ox + ow, oy + oh))
            obstacles += registry_label_obstacles(registry)
            obstacles += _free_ink(canvas, registry)
            lbl = measure_label(
                self.label, theme,
                getattr(theme, "connector_label_size", "small"))
            placed = place_curve_label(
                [(sx, sy), c1, c2, (dx, dy)], lbl, obstacles,
                prefer="above", gap=theme.unit * 1.0,
            )
            _draw_placed_label(canvas, placed, self.label,
                               lbl.size_px, label_col)
            register_label_obstacle(registry, placed.rect, self.src)

        if defer_label:
            return _curve_label_pass
        _curve_label_pass()
        return None


def label_corridor_reservation(spec, theme: Theme, side: str,
                               other_side: str, base: float,
                               neighbour_extent: float = 0.0) -> float:
    """Margin a labeled flow reserves on one pinned exit side.

    Labels are part of the route contract: a wire whose arms cannot
    carry its caption is not a valid wire, so the layout must reserve
    corridor length for the caption *before* geometry freezes -- a
    fixed multiplier cannot know how long the caption is.

    Two facing pinned sides (``right`` toward ``left``, ``bottom``
    toward ``top``) form a direct corridor whose only arm runs along
    that axis; each end then reserves half the caption's along-axis
    extent plus a caption gap, so the corridor as a whole is guaranteed
    to fit the caption. Any other side pairing implies a dog-leg whose
    long arm lives in shared space; the pinned stubs then reserve only
    the caption's smaller extent, which every orientation form needs.

    Multi-line captions (``"\\n"``) measure as blocks, so authors keep
    corridors compact by breaking long captions instead of the layout
    growing to fit one long line.

    On a facing pair the caption is costed as
    :func:`~sciviz.auto.labels.fitted_caption` will actually set it --
    wrapped to its narrowest block, so the corridor pays for the
    caption's longest WORD rather than its whole length. That is what
    makes an upright caption affordable between two neighbours, and it
    is the floor below which no wrapping can go. Reserving the full
    one-line length was what made side-by-side hand-offs ruinously
    expensive in wide figures -- expensive enough that authors start
    deleting words to fit, which is a layout failure wearing an
    editorial disguise.
    """
    label = getattr(spec, "label", None)
    if not label:
        return base
    from ..auto.labels import caption_fit
    fit = caption_fit(
        label, theme, getattr(theme, "connector_label_size", "small"),
        src_side=spec.src_side, dst_side=spec.dst_side,
        neighbour_extent=neighbour_extent)
    lbl = fit.label
    gap = theme.unit
    horizontal_pair = {side, other_side} == {"left", "right"}
    vertical_pair = {side, other_side} == {"top", "bottom"}
    if horizontal_pair and side in ("left", "right"):
        # Upright text reads along the wire and needs its own width of
        # corridor; a caption turned across the wire needs only a line.
        along = lbl.width if fit.upright else lbl.height
    elif vertical_pair and side in ("top", "bottom"):
        along = lbl.height if fit.upright else lbl.width
    else:
        # Dog-leg: the route's long arm rides *inside* this reserved
        # side lane with the caption offset beside the wire, so the
        # lane must hold the wire's own clearance (about half the base
        # budget), a caption gap, the caption's cross extent (its
        # smaller side -- rotated along a vertical arm or stacked
        # beside a horizontal one), and a clearance floor to whatever
        # third-party card neighbours the lane. Reserving only half
        # the cross extent left captions with no in-span home in
        # cramped inter-zone corridors: the placer was forced to hang
        # them past the arm's elbow as a last resort.
        cross = min(lbl.width, lbl.height)
        return max(base, base / 2.0 + cross + 2.0 * gap)
    return max(base, along / 2.0 + gap)


def _assign_edge_shares(specs, registry: dict) -> None:
    """Choose clean attachment ports for a set of routed flows.

    Parallel node faces first try to share one projected coordinate.  When
    the faces overlap, this turns an aligned parent/child or memory link into
    one straight segment even if the larger node's midpoint differs.
    Multiple flows retain those projected coordinates and are separated only
    when their ports would collide.

    Both :class:`Flowed` and the implicit ``Connect`` resolver call this
    function; it is deliberately the sole port-assignment implementation.
    """
    flow_endpoints = []
    for spec in specs:
        flow = spec if isinstance(spec, Flow) else getattr(spec, "_flow", None)
        if flow is None:
            continue
        sb = registry.get(flow.src)
        db = registry.get(flow.dst)
        if sb is None or db is None:
            continue
        src_side = (
            registry.get(f"__preferred_side_{flow.src}",
                         flow._auto_side(sb, db))
            if flow.src_side == "auto" else flow.src_side
        )
        dst_side = (
            registry.get(f"__preferred_side_{flow.dst}",
                         flow._auto_side(db, sb))
            if flow.dst_side == "auto" else flow.dst_side
        )
        flow_endpoints.append((flow, sb, db, src_side, dst_side))

    def edge_span(bbox, side):
        x, y, w, h = bbox
        inset = min(4.0, w * 0.2, h * 0.2)
        if side in ("top", "bottom"):
            return x + inset, x + w - inset
        if side in ("left", "right"):
            return y + inset, y + h - inset
        return None

    def fraction_for(span, coordinate):
        if span is None:
            return 0.5
        lo, hi = span
        if hi <= lo:
            return 0.5
        return max(0.0, min(1.0, (coordinate - lo) / (hi - lo)))

    preferred: dict[tuple[int, str], float] = {}
    for flow, sb, db, src_side, dst_side in flow_endpoints:
        src_span = edge_span(sb, src_side)
        dst_span = edge_span(db, dst_side)
        parallel = (
            src_side in ("top", "bottom")
            and dst_side in ("top", "bottom")
        ) or (
            src_side in ("left", "right")
            and dst_side in ("left", "right")
        )
        src_fraction = dst_fraction = 0.5
        if parallel and src_span is not None and dst_span is not None:
            overlap_lo = max(src_span[0], dst_span[0])
            overlap_hi = min(src_span[1], dst_span[1])
            if overlap_lo <= overlap_hi:
                src_len = src_span[1] - src_span[0]
                dst_len = dst_span[1] - dst_span[0]
                narrower = src_span if src_len <= dst_len else dst_span
                coordinate = (narrower[0] + narrower[1]) / 2.0
                coordinate = max(overlap_lo, min(overlap_hi, coordinate))
                src_fraction = fraction_for(src_span, coordinate)
                dst_fraction = fraction_for(dst_span, coordinate)
        preferred[(id(flow), "src")] = src_fraction
        preferred[(id(flow), "dst")] = dst_fraction

    buckets: dict = {}
    for entry in flow_endpoints:
        flow, _sb, _db, src_side, dst_side = entry
        buckets.setdefault((flow.src, src_side), []).append(("src", entry))
        buckets.setdefault((flow.dst, dst_side), []).append(("dst", entry))

    for (anchor_name, side), members in buckets.items():
        span = edge_span(registry[anchor_name], side)

        def member_fraction(member):
            role, entry = member
            return preferred[(id(entry[0]), role)]

        members.sort(key=member_fraction)
        fractions = [member_fraction(member) for member in members]
        if len(fractions) > 1 and span is not None:
            usable = max(1.0, span[1] - span[0])
            separation = min(6.0 / usable, 1.0 / (len(fractions) + 1))
            for index in range(1, len(fractions)):
                fractions[index] = max(
                    fractions[index], fractions[index - 1] + separation
                )
            if fractions[-1] > 1.0:
                fractions[-1] = 1.0
                for index in range(len(fractions) - 2, -1, -1):
                    fractions[index] = min(
                        fractions[index], fractions[index + 1] - separation
                    )
            if fractions[0] < 0.0:
                fractions[0] = 0.0
                for index in range(1, len(fractions)):
                    fractions[index] = max(
                        fractions[index], fractions[index - 1] + separation
                    )

        for fraction, (role, entry) in zip(fractions, members):
            flow = entry[0]
            if role == "src":
                flow._share_src_frac = fraction
            else:
                flow._share_dst_frac = fraction


class Labeled(Element):
    """A ``source`` element followed by a short drawn arrow into a ``label``.

    The clean replacement for the ``Row(Box(...), Text("->"), Math(...))``
    pattern: the author just writes ``Labeled(box, math_label)`` and the
    library draws a proportional horizontal arrow between them, routing
    from the source's right edge to the label's left edge.  Useful for
    the "block -> symbol" annotation pattern (e.g. ``Cross-Entropy Loss``
    flanked by ``L_{MTP}^k``).

    Parameters
    ----------
    source, label : Element
        The block producing the output, and the label explaining it.
    gap : str or float
        Minimum horizontal space between source and label (arrow shaft).
    color : ColorRef or str
        Arrow and (default) label stroke colour.
    align : str
        Cross-axis alignment, passed through to the inner Row.
    """

    def __init__(self, source: Element, label: Element, *,
                 gap: Union[str, float] = "md",
                 color = "text",
                 align: str = "center"):
        self.source = source
        self.label = label
        self.gap = gap
        self.color = color
        self.align = align
        self._compiled: Optional[Element] = None

    def _build(self, theme: Theme) -> Element:
        from ..layout import Row
        from ._flowed import Flowed
        src_anchor = Anchor("__labeled_src", self.source)
        lbl_anchor = Anchor("__labeled_lbl", self.label)
        inner = Row(src_anchor, lbl_anchor, gap=self.gap, align=self.align)
        return Flowed(inner, flows=[
            Flow("__labeled_src", "__labeled_lbl",
                 src_side="right", dst_side="left",
                 curvature=0.0, color=self.color),
        ])

    def _get(self, theme: Theme) -> Element:
        # Compile fresh every time: Flow carries internal state (like the
        # Flowed._margins_applied flag) that we don't want to leak across
        # measure/render cycles of the same Labeled instance.
        return self._build(theme)

    def measure(self, theme: Theme) -> BBox:
        return self._get(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._get(theme).render(canvas, x, y, theme)

    def primary_anchor_bbox(self, theme: Theme):
        """Expose the *source* box as the primary anchor so Grid centers
        on the box, not on the whole ``box + arrow + label`` composite.
        """
        src_b = self.source.measure(theme)
        return (0.0, 0.0, src_b.w, src_b.h)

    def content_bbox(self, theme: Theme):
        return self.primary_anchor_bbox(theme)
