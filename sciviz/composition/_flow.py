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
                       fill: str) -> None:
    """Render a connector label at the placer's chosen rectangle.

    Honours :attr:`PlacedLabel.rotation` so labels found by the placer
    to fit better vertically are drawn rotated 90 degrees clockwise --
    useful in narrow horizontal corridors. Anchored at "middle" by
    default so the placer's centred ``rect`` lines up correctly.
    """
    x0, y0, x1, y1 = placed.rect
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    if getattr(placed, "rotation", 0.0):
        # Rotated text: anchor at the centre of the rotated bbox.
        canvas.text(cx, cy, text,
                    size=size_px, fill=fill, italic=True,
                    anchor="middle", baseline="middle",
                    rotate=placed.rotation)
    else:
        # Horizontal text: anchor with baseline approximated from the
        # placer's vertical centre (fonts have ~33% descender).
        baseline_y = cy + size_px * 0.33
        canvas.text(cx, baseline_y, text,
                    size=size_px, fill=fill, italic=True,
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
        self.dashed = dashed
        self.curvature = curvature
        self.detour = detour
        self.arrow = arrow
        self.style = style
        self.route_around_labels = route_around_labels
        self.clearance = clearance

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

    def _render(self, canvas: Canvas, theme: Theme, registry: dict):
        sb = registry.get(self.src)
        db = registry.get(self.dst)
        if sb is None or db is None:
            return
        src_side = self._auto_side(sb, db) if self.src_side == "auto" else self.src_side
        dst_side = self._auto_side(db, sb) if self.dst_side == "auto" else self.dst_side
        src_frac = getattr(self, "_share_src_frac", 0.5)
        dst_frac = getattr(self, "_share_dst_frac", 0.5)
        sx, sy = _side_point_frac(sb, src_side, src_frac)
        dx, dy = _side_point_frac(db, dst_side, dst_frac)

        col = theme.color_of(self.color)
        sw = theme.connector
        dash = "5,3" if self.dashed else None
        marker = (canvas.define_arrow_marker(
                      color=col, stroke_width=sw,
                      arrow_size=getattr(theme, "arrow_size", None),
                      name_hint="flow")
                  if self.arrow else None)

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
            src_frac = getattr(self, "_share_src_frac", 0.5)
            dst_frac = getattr(self, "_share_dst_frac", 0.5)
            drawn_so_far = registry.get("__drawn_segments__", ())
            from dataclasses import replace as _dc_replace
            policy = _dc_replace(_rt.DEFAULT_POLICY,
                                 min_clearance=self._clearance_px(theme))
            plan = _rt.plan_path(
                _rt.Endpoint(src_box, src_side, tap=tap,
                             tap_fraction=src_frac),
                _rt.Endpoint(dst_box, dst_side, tap=tap,
                             tap_fraction=dst_frac),
                anchors=all_anchors,
                regions=all_regions,
                existing_segments=list(drawn_so_far),
                policy=policy,
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
                marker_end=marker if self.arrow else None,
                src_dot=True,
                existing_segments=drawn_before,
                hop_radius=max(2.5, sw * 2.5),
            )
            # Record the segments we just drew so subsequent flows can
            # detect crossings against them.
            for i in range(len(path) - 1):
                p1 = path[i]; p2 = path[i + 1]
                if abs(p1[0] - p2[0]) < 0.5 and abs(p1[1] - p2[1]) < 0.5:
                    continue
                drawn.append((p1[0], p1[1], p2[0], p2[1]))
            if self.label and len(path) >= 2:
                from ..auto.labels import (
                    measure_label, place_polyline_label,
                    register_label_obstacle, registry_label_obstacles,
                    segment_rects,
                )
                sz_tok = "small"
                lbl = measure_label(self.label, theme, sz_tok)
                all_anchor_obstacles = [
                    (ox, oy, ox + ow, oy + oh)
                    for ox, oy, ow, oh in anchor_obstacles
                ]
                all_anchor_obstacles.extend(registry_label_obstacles(registry))
                # Earlier flows' wires are obstacles too: a label must
                # not sit across another connector's line.
                wire_pad = max(0.5, sw)
                for (ex1, ey1, ex2, ey2) in drawn_before:
                    all_anchor_obstacles.extend(
                        segment_rects([(ex1, ey1), (ex2, ey2)], wire_pad))
                # The placer walks every leg of this wire longest-first
                # and offsets the label perpendicular to the chosen leg,
                # dodging cards, other labels, other wires, and the
                # wire's own perpendicular legs.
                placed = place_polyline_label(
                    path, lbl,
                    obstacles=all_anchor_obstacles,
                    prefer="above",
                    gap=theme.unit * 1.0,
                    wire_width=sw,
                )
                _draw_placed_label(canvas, placed, self.label,
                                   lbl.size_px, col)
                register_label_obstacle(registry, placed.rect, self.src)
            return

        # Explicit straight line: render as M/L so the tangent is the line
        # direction (well-defined) and orient="auto" points the arrowhead
        # correctly.  A degenerate Bezier with curvature=0 has zero tangent
        # at endpoints, which makes marker orientation unreliable.
        # ``style="straight"`` is equivalent -- the author has asked for a
        # direct segment, curvature parameter notwithstanding.
        if self.style == "straight" or self.curvature == 0:
            d = f"M {sx:.2f},{sy:.2f} L {dx:.2f},{dy:.2f}"
            canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                       marker_end=marker, dasharray=dash)
            if self.label:
                from ..auto.labels import (
                    measure_label, place_segment_label,
                    register_label_obstacle, registry_label_obstacles,
                )
                obstacles = []
                for name, b in registry.items():
                    if name.startswith("__") or name in (self.src, self.dst):
                        continue
                    if isinstance(b, tuple) and len(b) == 4:
                        ox, oy, ow, oh = b
                        obstacles.append((ox, oy, ox + ow, oy + oh))
                obstacles += registry_label_obstacles(registry)
                lbl = measure_label(self.label, theme, "small")
                placed = place_segment_label(
                    ((sx, sy), (dx, dy)), lbl, obstacles,
                    prefer="above", gap=theme.unit * 1.0,
                )
                _draw_placed_label(canvas, placed, self.label,
                                   lbl.size_px, col)
                register_label_obstacle(registry, placed.rect, self.src)
            return

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
            sign = 1.0 if dx > sx else -1.0
            pull = abs(dx - sx) * 0.25
            c1 = (sx + sign * pull, arch_y)
            c2 = (dx - sign * pull, arch_y)
        elif src_side.startswith("top") and dst_side.startswith("top"):
            # Both-above arc: bow over the diagram.
            arch_y = min(sy, dy) - self.detour
            sign = 1.0 if dx > sx else -1.0
            pull = abs(dx - sx) * 0.25
            c1 = (sx + sign * pull, arch_y)
            c2 = (dx - sign * pull, arch_y)

        d = (f"M {sx:.2f},{sy:.2f} "
             f"C {c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} "
             f"{dx:.2f},{dy:.2f}")
        canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                   marker_end=marker, dasharray=dash)

        if self.label:
            from ..auto.labels import (
                measure_label, place_curve_label,
                register_label_obstacle, registry_label_obstacles,
            )
            obstacles = []
            for name, b in registry.items():
                if name.startswith("__") or name in (self.src, self.dst):
                    continue
                if isinstance(b, tuple) and len(b) == 4:
                    ox, oy, ow, oh = b
                    obstacles.append((ox, oy, ox + ow, oy + oh))
            obstacles += registry_label_obstacles(registry)
            lbl = measure_label(self.label, theme, "small")
            placed = place_curve_label(
                [(sx, sy), c1, c2, (dx, dy)], lbl, obstacles,
                prefer="above", gap=theme.unit * 1.0,
            )
            _draw_placed_label(canvas, placed, self.label, lbl.size_px, col)
            register_label_obstacle(registry, placed.rect, self.src)


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


