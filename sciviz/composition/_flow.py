"""Flow: declarative curved/orthogonal arrow between named anchors.

Holds :class:`Labeled`, which composes ``Flow`` for its internal
label-to-source arrow.
"""

from __future__ import annotations

import re as _re

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text, TextBlock
from ..layout import Row, Column, Spacer
from ._anchor import Anchor, _side_point, _side_point_frac, port_face


def _draw_capsules(canvas: Canvas, placed, text: str, size_px: float,
                   fill: str, theme: Theme, size) -> None:
    """Set a capsule caption: every line its own pill (light fill, thin
    darker edge, fully rounded ends), stacked and centred in the placed
    rectangle, the text centred in its pill."""
    from ..auto.labels import capsule_geometry
    pad_x, pill_h, gap = capsule_geometry(theme, size)
    lines = text.split("\n")
    x0, y0, x1, y1 = placed.rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    total = len(lines) * pill_h + (len(lines) - 1) * gap
    rotation = getattr(placed, "rotation", 0.0)
    if fill is None:
        fill = theme.color_of(getattr(theme, "label_capsule_text", "text"))
    pill_fill = theme.color_of(getattr(theme, "label_capsule_fill", "#f6d5e0"))
    pill_edge = theme.color_of(getattr(theme, "label_capsule_stroke", "#d98ca8"))
    edge_w = float(getattr(theme, "hairline", 0.5))
    for i, line in enumerate(lines):
        w = max(theme.text_width(line, size) + 2.0 * pad_x, pill_h)
        # this pill's centre along the stacking axis
        off = -total / 2.0 + i * (pill_h + gap) + pill_h / 2.0
        if rotation:
            px, py = cx + off, cy
            canvas.rect(px - pill_h / 2.0, py - w / 2.0, pill_h, w,
                        fill=pill_fill, stroke=pill_edge,
                        stroke_width=edge_w, rx=pill_h / 2.0)
            canvas.text(px, py, line, size=size_px, fill=fill,
                        anchor="middle", baseline="middle", rotate=rotation)
        else:
            px, py = cx, cy + off
            canvas.rect(px - w / 2.0, py - pill_h / 2.0, w, pill_h,
                        fill=pill_fill, stroke=pill_edge,
                        stroke_width=edge_w, rx=pill_h / 2.0)
            canvas.text(px, py + size_px * 0.32, line, size=size_px,
                        fill=fill, anchor="middle")


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

    The placer may have re-set the caption to the arm it chose (the
    rotated-label wrap budget), in which case its own text wins over the
    caller's: the rectangle was measured for those lines, and drawing any
    others paints ink the layout never reserved.
    """
    text = getattr(placed, "text", None) or text
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
    # A hyphen between two word characters is punctuation, not a minus
    # sign: "held-back", "drop-in" and "sign-flip" are prose, and setting
    # them in italic beside upright siblings reads as an error. Intra-word
    # hyphens are therefore removed before the operator test; a hyphen with
    # space around it, or one that opens a token, still reads as an
    # operator and still italicises.
    probe = _re.sub(r"(?<=\w)-(?=\w)", "", stripped)
    # A caption of two or more real words is a phrase even when it quotes
    # an operator ("dose per kilogram, x0.25 to x4", "mean -> median"):
    # the operator is part of the prose, and one italic phrase among
    # upright captions reads as a different kind of label.
    phrase = len(_re.findall(r"[^\W\d_]{3,}", probe)) >= 2
    symbolic = not phrase and (
        (" " not in stripped and len(stripped) <= 3)
        or any(ch in probe for ch in "_{}^=+-×÷∑∏∈→←λμσ")
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

    def _frame(self, theme: Theme) -> str:
        """The caption frame: this flow's own, else the theme's."""
        f = getattr(self, "label_frame", None)
        if f is None:
            f = getattr(theme, "connector_label_frame", "none")
        return f

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
                 style = _STYLE_UNSET,
                 ports: str = "centred",
                 label_style: str = "beside",
                 src_at: Optional[str] = None,
                 dst_at: Optional[str] = None,
                 label_side: str = "auto",
                 label_frame: Optional[str] = None,
                 src_room: Optional[float] = None,
                 dst_room: Optional[float] = None,
                 min_shaft: Optional[float] = None):
        """
        ``min_shaft`` -- the least straight shaft (px) that stays visible
            between the wire's last bend and the base of its arrowhead.
            ``None`` (default) keeps the planner's own stub floor. A
            number raises the floor of every end that carries a head to
            the head plus that shaft: the planner keeps the last bend of
            a bridged route that far from the head while the corridor
            allows, and on a pinned side whose room the author did not
            set the layout reserves that much beside the anchor. An arm
            the layout fixes shorter (the elbow of an L route) is
            reported by the shaft check (``Diagram.short_shafts``).

        ``src_room`` / ``dst_room`` -- the room (px) the layout reserves
            beside the source / destination anchor on a pinned side for
            this wire's shaft. ``None`` (default) keeps the automatic
            reservation (the flow space, or a caption-sized corridor for
            a labelled wire). A number sets it, for an end whose shaft
            already has visible room in a boundary's padding or beyond
            it (an arrow entering a card inside a region from outside
            the region): ``0`` reserves nothing there.

        ``label_frame`` -- ``"none"`` (plain caption) or ``"capsule"``:
            every line of the caption is set as its own rounded pill
            (``Theme.label_capsule_fill`` / ``label_capsule_stroke``),
            stacked when there are several, never re-wrapped or turned.
            ``None`` (default) takes ``Theme.connector_label_frame``.

        ``src_at`` / ``dst_at`` -- the name of an anchor *inside* that
            endpoint. The wire still lands on the endpoint's own frame
            (it never crosses into a card to reach an inner title or
            badge), at the point of the chosen side level with the inner
            anchor's centre. Overrides the ``ports`` share for that end.

        ``label_style`` -- ``"beside"`` (default) sets the caption next to
            its wire; ``"on-wire"`` centres it on the wire over a
            page-coloured halo, so the caption occupies the wire's own
            lane (stacked lanes of labelled wires then need one caption
            height apart, not two). Falls back to ``"beside"`` when no leg
            can carry the caption.

        ``label_side`` -- ``"auto"`` (default) lets the placer pick the
            caption's leg and side; ``"left"``/``"right"`` set it beside a
            vertical leg on that side, ``"above"``/``"below"`` beside a
            horizontal leg (the vocabulary of :class:`Arrow`). Give sibling
            wires crossing one gutter the same side and their captions
            read as one set.

        ``ports`` -- where on its side each end attaches when the two
            faces do not overlap: ``"centred"`` (default) at the middle of
            the side; ``"facing"`` in the half of the side that faces the
            other end, so a wire that leaves the top of a card and turns
            toward a neighbour leaves from that neighbour's side of the
            card (shorter, and clear of whatever sits over the far half,
            such as a title).

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
        if ports not in ("centred", "facing"):
            raise ValueError(
                f"ports must be 'centred' or 'facing'; got {ports!r}")
        if label_style not in ("beside", "on-wire"):
            raise ValueError(
                f"label_style must be 'beside' or 'on-wire'; got {label_style!r}")
        if label_side not in ("auto", "left", "right", "above", "below"):
            raise ValueError(
                "label_side must be 'auto', 'left', 'right', 'above' or "
                f"'below'; got {label_side!r}")
        self.label_side = label_side
        if label_frame not in (None, "none", "capsule"):
            raise ValueError(
                f"label_frame must be 'none' or 'capsule'; got {label_frame!r}")
        self.label_frame = label_frame
        self.ports = ports
        self.label_style = label_style
        self.src_at = src_at
        self.dst_at = dst_at
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
        for _name, _room in (("src_room", src_room), ("dst_room", dst_room)):
            if _room is not None and float(_room) < 0.0:
                raise ValueError(f"{_name} must be >= 0; got {_room!r}")
        self.src_room = None if src_room is None else float(src_room)
        self.dst_room = None if dst_room is None else float(dst_room)
        if min_shaft is not None and float(min_shaft) < 0.0:
            raise ValueError(f"min_shaft must be >= 0; got {min_shaft!r}")
        self.min_shaft = None if min_shaft is None else float(min_shaft)

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
        # Hard floor: a wire closer than min_space to a card edge reads
        # as part of the border.
        return max(theme.unit * (4.0 / 3.0), theme.min_space)

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

    @staticmethod
    def _containment_bounds(registry: dict, sb, db):
        """Innermost registered ``__region_*`` rect fully containing both
        endpoint boxes. A wire that lives inside a framed container (e.g.
        a Panel) must keep its caption inside that container's frame.
        Returns ``(x0, y0, x1, y1)`` or ``None``."""
        def _inside(box, region):
            bx, by, bw, bh = box
            rx, ry, rw, rh = region
            eps = 0.5
            return (bx >= rx - eps and by >= ry - eps
                    and bx + bw <= rx + rw + eps
                    and by + bh <= ry + rh + eps)
        best = None
        best_area = None
        for name, region in registry.items():
            if not name.startswith("__region_"):
                continue
            if not (isinstance(region, tuple) and len(region) == 4):
                continue
            if _inside(sb, region) and _inside(db, region):
                area = region[2] * region[3]
                if best_area is None or area < best_area:
                    best = (region[0], region[1],
                            region[0] + region[2], region[1] + region[3])
                    best_area = area
        return best

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
        sp = _body_port(registry, self.src, src_side)
        dp = _body_port(registry, self.dst, dst_side)
        # Shares (``_assign_edge_shares``) already pin ``src_at`` /
        # ``dst_at`` ends and separate their neighbours; without a share
        # pass the inner anchor still decides the tap.
        src_frac = getattr(self, "_share_src_frac", None)
        if src_frac is None:
            src_frac = _at_fraction(sp or sb, src_side,
                                    registry.get(self.src_at or ""), 0.5)
        dst_frac = getattr(self, "_share_dst_frac", None)
        if dst_frac is None:
            dst_frac = _at_fraction(dp or db, dst_side,
                                    registry.get(self.dst_at or ""), 0.5)
        sp = _clear_port(registry, self.src, sb, sp, src_side, src_frac)
        dp = _clear_port(registry, self.dst, db, dp, dst_side, dst_frac)
        sx, sy = _side_point_frac(sp or sb, src_side, src_frac)
        dx, dy = _side_point_frac(dp or db, dst_side, dst_frac)

        col = theme.color_of(self.color)
        label_col = theme.color_of(
            self.label_color if self.label_color is not None else self.color
        )
        # a capsule's text is the theme's capsule ink unless the author
        # coloured the caption (it sits on the pill, not beside the wire)
        capsule_ink = (theme.color_of(self.label_color)
                       if self.label_color is not None
                       and getattr(self, "capsule_ink_authored", True)
                       else None)
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
            drawn_so_far = registry.get("__drawn_segments__", ())
            from dataclasses import replace as _dc_replace
            # The planner must know how much of each stub the
            # arrowhead will eat, or a marker crowded against a
            # neighbouring box ends up with no visible shaft behind it.
            policy = _dc_replace(_rt.DEFAULT_POLICY,
                                 min_clearance=self._clearance_px(theme),
                                 head_len=theme.arrow_head_px)
            # An author-set shaft (``min_shaft``) raises the stub floor of
            # each end that carries a head to the head plus that shaft, so
            # the last bend of a bridged route keeps that far from it.
            src_tap_len = dst_tap_len = tap
            _min_shaft = getattr(self, "min_shaft", None)
            if _min_shaft is not None and (marker_start or marker_end):
                policy = _dc_replace(
                    policy,
                    src_shaft=_min_shaft if marker_start else None,
                    dst_shaft=_min_shaft if marker_end else None)
                _need = theme.arrow_head_px + _min_shaft
                if marker_end:
                    dst_tap_len = max(tap, _need)
                if marker_start:
                    src_tap_len = max(tap, _need)
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
                    neighbour_extent=neighbour_extent,
                    frame=self._frame(theme))
                _probe = _probe_fit.label
                caption = _probe.text
                label_extent = (_probe.width, _probe.height)
                # Single lines may be rotated by the placer; blocks are
                # never set as columns of tilted text. The planner has to
                # judge homes by the same rule the placer will apply, or
                # the two disagree and the route runs away looking for an
                # arm the caption does not need.
                label_rotatable = not _probe_fit.upright
            bounds = _scope_bounds(
                all_anchors + all_regions + [src_box, dst_box],
                drawn_so_far,
                lane=(max(tap, policy.min_tap + policy.head_len)
                      + policy.min_clearance
                      + (max(label_extent) + theme.unit
                         if label_extent else 0.0)))
            plan = _rt.plan_path(
                _rt.Endpoint(src_box, src_side, tap=src_tap_len,
                             tap_fraction=src_frac,
                             port=_rt_box(sp, self.src)),
                _rt.Endpoint(dst_box, dst_side, tap=dst_tap_len,
                             tap_fraction=dst_frac,
                             port=_rt_box(dp, self.dst)),
                anchors=all_anchors,
                regions=all_regions,
                existing_segments=list(drawn_so_far),
                policy=policy,
                label_extent=label_extent,
                label_gap=theme.unit,
                label_rotatable=label_rotatable,
                label_inline=self.label_style == "on-wire",
                bounds=bounds,
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
                hop_radius=_rt.hop_radius(sw),
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
                    neighbour_extent=neighbour_extent,
                    frame=self._frame(theme))
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
                foreign = []
                for seg in registry.get("__drawn_segments__", ()):  # noqa: B023
                    if seg in own:
                        continue
                    foreign.append(seg)
                    ex1, ey1, ex2, ey2 = seg
                    all_anchor_obstacles.extend(
                        segment_rects([(ex1, ey1), (ex2, ey2)], wire_pad))
                # The placer walks every leg of this wire longest-first
                # and offsets the label perpendicular to the chosen leg,
                # dodging cards, other labels, other wires, and the
                # wire's own perpendicular legs; in walled corridors it
                # falls back to an on-wire placement with a halo.
                bounds = self._containment_bounds(registry, sb, db)
                placed = None
                if self.label_style == "on-wire":
                    from ..auto.labels import place_on_wire_label
                    placed = place_on_wire_label(
                        path, lbl, all_anchor_obstacles,
                        gap=theme.unit * 1.0, wire_width=sw, bounds=bounds)
                if placed is None:
                    placed = place_polyline_label(
                        path, lbl,
                        obstacles=all_anchor_obstacles,
                        prefer="above",
                        gap=theme.unit * 1.0,
                        wire_width=sw,
                        bounds=bounds,
                        foreign_segments=foreign,
                        side=(None if self.label_side == "auto"
                              else self.label_side),
                    )
                if lbl.frame == "capsule":
                    _draw_capsules(canvas, placed,
                                   getattr(placed, "text", None) or lbl.text,
                                   lbl.size_px, capsule_ink, theme, sz_tok)
                else:
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
                    getattr(theme, "connector_label_size", "small"),
                    frame=self._frame(theme))
                placed = place_segment_label(
                    ((sx, sy), (dx, dy)), lbl, obstacles,
                    prefer="above", gap=theme.unit * 1.0,
                    bounds=self._containment_bounds(registry, sb, db),
                )
                if lbl.frame == "capsule":
                    _draw_capsules(
                        canvas, placed, self.label, lbl.size_px, capsule_ink,
                        theme, getattr(theme, "connector_label_size", "small"))
                else:
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

        # A framed container (Panel) is a hard boundary for the wire's
        # ink: clamp the arc's control points so the bow stays inside
        # the innermost region that contains both endpoints.
        _cb = self._containment_bounds(registry, sb, db)
        if _cb is not None:
            m = theme.unit * 0.6
            c1 = (min(max(c1[0], _cb[0] + m), _cb[2] - m),
                  min(max(c1[1], _cb[1] + m), _cb[3] - m))
            c2 = (min(max(c2[0], _cb[0] + m), _cb[2] - m),
                  min(max(c2[1], _cb[1] + m), _cb[3] - m))

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
                getattr(theme, "connector_label_size", "small"),
                frame=self._frame(theme))
            placed = place_curve_label(
                [(sx, sy), c1, c2, (dx, dy)], lbl, obstacles,
                prefer="above", gap=theme.unit * 1.0,
                bounds=self._containment_bounds(registry, sb, db),
            )
            if lbl.frame == "capsule":
                _draw_capsules(
                    canvas, placed, self.label, lbl.size_px, capsule_ink,
                    theme, getattr(theme, "connector_label_size", "small"))
            else:
                _draw_placed_label(canvas, placed, self.label,
                                   lbl.size_px, label_col)
            register_label_obstacle(registry, placed.rect, self.src)

        if defer_label:
            return _curve_label_pass
        _curve_label_pass()
        return None


def _scope_bounds(boxes, segments, lane: float):
    """The region a wire in this scope may route through: the hull of
    everything the scope has laid out or drawn so far (anchors, regions,
    free ink, earlier wires), grown by one lane on every side.

    Earlier wires count, so a second return lane stacked outside a first
    one is still inside; the lane is what one more such detour needs
    (stub, arrowhead, clearance and, for a captioned wire, its caption).
    """
    from .. import routing as _rt
    xs, ys = [], []
    for b in boxes:
        xs += [b.left, b.right]
        ys += [b.top, b.bottom]
    for (x1, y1, x2, y2) in segments:
        xs += [x1, x2]
        ys += [y1, y2]
    if not xs:
        return None
    x0, y0 = min(xs) - lane, min(ys) - lane
    return _rt.Box(x=x0, y=y0, w=max(xs) + lane - x0, h=max(ys) + lane - y0,
                   name="__scope__", kind="region")


def _rt_box(box, name):
    if box is None:
        return None
    from .. import routing as _rt
    x, y, w, h = box
    return _rt.Box(x=x, y=y, w=w, h=h, name=name, kind="anchor")


def _body_port(registry: dict, name: str, side: str):
    """The body box a wire to ``name`` lands on at ``side``, or None
    (see :meth:`Element.port_bbox` and :func:`port_face`)."""
    from ._anchor import PORT_PREFIX
    ports = registry.get(PORT_PREFIX + name)
    return ports.get(side) if ports else None


def _clear_port(registry: dict, name: str, layout, port, side: str,
                frac: float):
    """The face a wire tapping ``port`` at ``frac`` lands on.

    Where the run from the body out to the layout edge would cross the
    element's own text at that point (an outside label, a frame tab, a
    caption; see :func:`~sciviz.composition._anchor._blocked_spans`), the
    face is pushed out to the ``layout`` edge on ``side`` -- the wire
    stops there, at the same coordinate, instead of cutting the text.
    """
    if port is None:
        return None
    from ._anchor import PORT_PREFIX, blocked_key
    blocked = (registry.get(PORT_PREFIX + name) or {}).get(
        blocked_key(side), ())
    x, y = _side_point_frac(port, side, frac)
    along = x if side in ("top", "bottom") else y
    if any(lo - 0.5 <= along <= hi + 0.5 for lo, hi in blocked):
        px, py, pw, ph = port
        lx, ly, lw, lh = layout
        return {"top": (px, ly, pw, py + ph - ly),
                "bottom": (px, py, pw, ly + lh - py),
                "left": (lx, py, px + pw - lx, ph),
                "right": (px, py, lx + lw - px, ph)}.get(side)
    return port


def _at_fraction(box, side: str, inner, default: float) -> float:
    """Share fraction on ``box``'s ``side`` level with ``inner``'s centre."""
    if inner is None or box is None:
        return default
    x, y, w, h = box
    ix, iy, iw, ih = inner
    inset = min(4.0, w * 0.2, h * 0.2)
    if side in ("top", "bottom"):
        lo, hi, c = x + inset, x + w - inset, ix + iw / 2
    elif side in ("left", "right"):
        lo, hi, c = y + inset, y + h - inset, iy + ih / 2
    else:
        return default
    if hi <= lo:
        return default
    return max(0.0, min(1.0, (c - lo) / (hi - lo)))


def _blocked(registry: dict, name: str, side: str) -> list:
    """Stretches of ``name``'s ``side`` a wire should not tap (its own
    label or tab lies between body and layout edge there)."""
    from ._anchor import PORT_PREFIX, blocked_key
    return list((registry.get(PORT_PREFIX + name) or {}).get(
        blocked_key(side), ()))


def _shared_coordinate(src_span, dst_span, src_inner, dst_inner,
                       side: str, blocked=()):
    """One coordinate both ends of a parallel wire can take, or None.

    An end pinned to an inner anchor may attach anywhere along that
    anchor's extent (clipped to its face ``*_span``); a free end anywhere
    along its face. When those ranges overlap the wire needs no jog: it
    runs straight at the pinned centre (the mean of both when both are
    pinned), clamped into the overlap. ``None`` means the ranges are
    disjoint and the router must add one jog.
    """
    if src_span is None or dst_span is None:
        return None
    along = 0 if side in ("top", "bottom") else 1

    def extent(span, inner):
        if inner is None:
            return span[0], span[1], None
        lo = max(span[0], inner[along])
        hi = min(span[1], inner[along] + inner[2 + along])
        return lo, hi, inner[along] + inner[2 + along] / 2.0

    s_lo, s_hi, s_c = extent(src_span, src_inner)
    d_lo, d_hi, d_c = extent(dst_span, dst_inner)
    lo, hi = max(s_lo, d_lo), min(s_hi, d_hi)
    if lo > hi:
        return None
    centres = [c for c in (s_c, d_c) if c is not None]
    if not centres:
        return None
    target = sum(centres) / len(centres)
    # Skip stretches guarded by either end's own label or tab, so the
    # wire meets the frame beside them rather than their outer edge.
    clear, cursor = [], lo
    for b0, b1 in sorted(blocked):
        if b0 > cursor:
            clear.append((cursor, min(b0, hi)))
        cursor = max(cursor, b1)
    if cursor < hi:
        clear.append((cursor, hi))
    clear = [(a, b) for a, b in clear if b - a > 1.0] or [(lo, hi)]
    return min((max(a, min(b, target)) for a, b in clear),
               key=lambda c: abs(c - target))


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
    frame = getattr(spec, "label_frame", None)
    if frame is None:
        frame = getattr(theme, "connector_label_frame", "none")
    fit = caption_fit(
        label, theme, getattr(theme, "connector_label_size", "small"),
        src_side=spec.src_side, dst_side=spec.dst_side,
        neighbour_extent=neighbour_extent, frame=frame)
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
        if getattr(spec, "label_style", "beside") == "on-wire":
            # The caption rides on the wire itself: the lane holds the
            # wire's clearance and half the caption on either side of it.
            return max(base, base / 2.0 + cross / 2.0 + gap)
        return max(base, base / 2.0 + cross + 2.0 * gap)
    return max(base, along / 2.0 + gap)


#: Where a ``ports="facing"`` end attaches along its side: this far from
#: the side's middle toward the other end (0.5 would be the corner).
_FACING_OFFSET = 0.3


def _facing_fraction(own, side: str, other) -> float:
    """Port fraction on ``own``'s ``side`` in the half facing ``other``.

    Only a partner lying wholly beyond the side's own extent pulls the
    port; one whose extent overlaps it leaves the port centred (the
    projected-coordinate rule then applies to parallel faces).
    """
    along = 0 if side in ("top", "bottom") else 1
    lo = own[along]
    hi = own[along] + own[2 + along]
    o_lo = other[along]
    o_hi = other[along] + other[2 + along]
    if o_lo >= hi:
        return 0.5 + _FACING_OFFSET
    if o_hi <= lo:
        return 0.5 - _FACING_OFFSET
    return 0.5


def _assign_edge_shares(specs, registry: dict,
                        theme: Optional[Theme] = None) -> None:
    """Choose clean attachment ports for a set of routed flows.

    Parallel node faces first try to share one projected coordinate.  When
    the faces overlap, this turns an aligned parent/child or memory link into
    one straight segment even if the larger node's midpoint differs.
    Multiple flows retain those projected coordinates and are separated only
    when their ports would collide.

    Ports on one side are ordered so wires never cross: a wire that can
    run straight keeps its projected coordinate, and wires turning away
    from it take the ports on the side they turn toward. Neighbouring
    ports sit at least one wire clearance apart (with ``theme``), so the
    router never has to jog a wire off a port to keep that clearance.

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
        # Shares are judged on the faces wires land on (body ports).
        sb = port_face(registry, flow.src, src_side) or sb
        db = port_face(registry, flow.dst, dst_side) or db
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
    straight_ends: set[int] = set()
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
        if getattr(flow, "ports", "centred") == "facing":
            src_fraction = _facing_fraction(sb, src_side, db)
            dst_fraction = _facing_fraction(db, dst_side, sb)
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
        straight = (parallel and src_span is not None
                    and dst_span is not None
                    and max(src_span[0], dst_span[0])
                    <= min(src_span[1], dst_span[1]))
        # An end pinned to an inner anchor (``src_at`` / ``dst_at``) sits
        # level with it; the bucket pass below nests its neighbours
        # around it like any other preferred port.
        src_in = registry.get(flow.src_at or "")
        dst_in = registry.get(flow.dst_at or "")
        shared = (_shared_coordinate(
                      src_span, dst_span, src_in, dst_in, src_side,
                      _blocked(registry, flow.src, src_side)
                      + _blocked(registry, flow.dst, dst_side))
                  if parallel and (src_in or dst_in) else None)
        if shared is not None:
            # Both pinned extents overlap: one straight wire, no jog.
            src_fraction = fraction_for(src_span, shared)
            dst_fraction = fraction_for(dst_span, shared)
        else:
            straight = straight and not (src_in or dst_in)
            src_fraction = _at_fraction(sb, src_side, src_in, src_fraction)
            dst_fraction = _at_fraction(db, dst_side, dst_in, dst_fraction)
        if straight:
            straight_ends.add(id(flow))
        preferred[(id(flow), "src")] = src_fraction
        preferred[(id(flow), "dst")] = dst_fraction

    buckets: dict = {}
    for entry in flow_endpoints:
        flow, _sb, _db, src_side, dst_side = entry
        buckets.setdefault((flow.src, src_side), []).append(("src", entry))
        buckets.setdefault((flow.dst, dst_side), []).append(("dst", entry))

    for (anchor_name, side), members in buckets.items():
        own = port_face(registry, anchor_name, side)
        span = edge_span(own, side)

        def member_fraction(member):
            role, entry = member
            return preferred[(id(entry[0]), role)]

        along = 0 if side in ("top", "bottom") else 1
        centre = own[along] + own[2 + along] / 2.0

        def nesting(member):
            """Order wires with no geometric port preference so they nest.

            Wires leaving one side turn toward their far ends. Those turning
            the same way nest without crossing when the one travelling
            farther takes the port farther from where they turn (it then
            runs outside the nearer one); those turning toward the smaller
            coordinate sit before those turning toward the larger.
            """
            role, entry = member
            other = entry[2] if role == "src" else entry[1]
            far = other[along] + other[2 + along] / 2.0
            # A straight wire does not turn: wires turning toward the
            # smaller coordinate sit before it, those turning toward the
            # larger after it, so none crosses it.
            if id(entry[0]) in straight_ends:
                return (1, 0.0)
            return (2 if far >= centre else 0, -far)

        members.sort(key=lambda m: (round(member_fraction(m), 6), nesting(m)))
        fractions = [member_fraction(member) for member in members]
        if len(fractions) > 1 and span is not None:
            usable = max(1.0, span[1] - span[0])
            apart = 6.0
            if theme is not None:
                apart = max([apart] + [m[1][0]._clearance_px(theme)
                                       for m in members])
            separation = min(apart / usable, 1.0 / (len(fractions) + 1))
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

    def port_bbox(self, theme: Theme, side: str):
        """Wires land on the *source* box; the label side (right) keeps
        the whole composite, since its own arrow and label sit there."""
        if side == "right":
            return None
        port = self.source.port_bbox(theme, side)
        if port is not None:
            return port
        return self.primary_anchor_bbox(theme)
