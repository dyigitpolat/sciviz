"""Bus: multi-endpoint connector routed through a single spine."""

from __future__ import annotations

import warnings
from typing import Callable, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text
from ._anchor import Anchor, _anchor_stack, _side_point, _side_point_frac

class Bus:
    """Multi-endpoint connector routed through a single spine.

    Use when the same signal is shared by several sinks (e.g. a "Shared"
    weight layer) or many sources converge into one sink (e.g. expert
    outputs combining at an ``+``).  Authoring is endpoint-only::

        Bus(sources="main_out",
            sinks=["mtp1_out", "mtp2_out", "mtp3_out"],
            label="Shared",
            dashed=True)

    Geometry is derived from the *flow direction* (source-cluster
    centroid toward sink-cluster centroid): a mostly-vertical flow gets a
    horizontal spine in the clear gap between the clusters, a
    mostly-horizontal flow gets a vertical spine.  When a cluster is
    stacked *along* the flow axis (so straight taps would impale sibling
    endpoints), the taps exit sideways onto a rail that runs alongside
    the cluster and joins the spine -- endpoints are never struck
    through.  All bus ink is strictly axis-aligned.

    Parameters
    ----------
    sources, sinks : str or list of str
        Anchor names.
    label : str, optional
        Rendered once along the bus spine.
    dashed : bool
        Bus style.
    color : ColorRef or str
    arrow : bool
        Draw arrowheads at sink ends (default True).
    """

    def __init__(self, sources, sinks, *,
                 label: Optional[str] = None,
                 dashed: bool = False,
                 color = "muted_label",
                 arrow: bool = True,
                 auto_route: bool = True,
                 orientation: str = "auto"):
        self.sources = [sources] if isinstance(sources, str) else list(sources)
        self.sinks   = [sinks]   if isinstance(sinks,   str) else list(sinks)
        self.label = label
        self.dashed = dashed
        self.color = color
        self.arrow = arrow
        # Bus geometry (spine + taps) is always auto-routed; the flag is
        # accepted for API symmetry with ``Connect`` / ``Flow``.
        self.auto_route = bool(auto_route)
        # ``orientation`` is a hint used by Flowed._apply_flow_margins to
        # decide which anchor faces to inflate for the spine.  "horizontal"
        # inflates the source's right/left edges and the sinks' opposite
        # edges; "vertical" inflates top/bottom.  "auto" (default) inflates
        # every face with a smaller bump, since the actual orientation is
        # only determined at render time from measured positions.
        if orientation not in ("auto", "horizontal", "vertical"):
            raise ValueError(
                f"Bus orientation must be 'auto', 'horizontal', or "
                f"'vertical'; got {orientation!r}")
        self.orientation = orientation

    def _draw_placed_label(self, canvas: Canvas, theme: Theme,
                           segment, obstacles, *, color: str,
                           size_token: str = "tiny",
                           prefer: str = "above",
                           registry: Optional[dict] = None,
                           mask_bg: bool = False) -> None:
        """Place ``self.label`` on ``segment`` avoiding ``obstacles``.

        Uses the geometric label placer so the label dodges structural
        lines (T-bars, taps, other boxes), every wire drawn so far, and
        free-standing text ink.  When ``mask_bg`` is True, a background
        rectangle is drawn behind the label so a dashed line reads as
        passing cleanly behind the text.
        """
        if not self.label:
            return
        from ..auto.ink import free_text_rects
        from ..auto.labels import (
            measure_label, place_segment_label,
            register_label_obstacle, registry_label_obstacles,
            segment_rects,
        )
        lbl = measure_label(self.label, theme, size_token)
        all_obstacles = list(obstacles)
        if registry is not None:
            all_obstacles += registry_label_obstacles(registry)
            all_obstacles += free_text_rects(canvas, registry)
        placed = place_segment_label(
            segment, lbl, obstacles=all_obstacles, prefer=prefer,
            gap=theme.unit * 0.35,
        )
        rect, anchor = placed.rect, placed.anchor
        x0, y0, x1, y1 = rect
        # A caption the placer could not clear is knocked out rather
        # than struck through -- same rule as routed connectors.
        if mask_bg or getattr(placed, "overlapped", False):
            bg_pad = theme.unit * 0.25
            canvas.rect(x0 - bg_pad, y0 - bg_pad,
                        (x1 - x0) + 2 * bg_pad,
                        (y1 - y0) + 2 * bg_pad,
                        fill=theme.color_of("bg"), stroke="none")
        mx = (x0 + x1) / 2
        baseline_y = (y0 + y1) / 2 + lbl.size_px * 0.33
        canvas.text(mx, baseline_y, self.label, size=lbl.size_px, fill=color,
                    italic=True, anchor=anchor)
        if registry is not None:
            register_label_obstacle(registry, placed.rect, "bus")

    # ------------------------------------------------------------------
    # geometry helpers (pure, unit-testable through _render)
    # ------------------------------------------------------------------

    @staticmethod
    def _centroid(boxes: Sequence[Tuple[float, float, float, float]]
                  ) -> Tuple[float, float]:
        cx = sum(b[0] + b[2] / 2 for b in boxes) / len(boxes)
        cy = sum(b[1] + b[3] / 2 for b in boxes) / len(boxes)
        return cx, cy

    @staticmethod
    def _v_seg_hits(px: float, y_a: float, y_b: float,
                    boxes, skip) -> bool:
        """Does the vertical segment at x=px cross any box interior?"""
        y0, y1 = sorted((y_a, y_b))
        for b in boxes:
            if b is skip:
                continue
            bx, by, bw, bh = b
            if bx < px < bx + bw and y0 < by + bh and y1 > by:
                return True
        return False

    @staticmethod
    def _h_seg_hits(py: float, x_a: float, x_b: float,
                    boxes, skip) -> bool:
        """Does the horizontal segment at y=py cross any box interior?"""
        x0, x1 = sorted((x_a, x_b))
        for b in boxes:
            if b is skip:
                continue
            bx, by, bw, bh = b
            if by < py < by + bh and x0 < bx + bw and x1 > bx:
                return True
        return False

    def _render(self, canvas: Canvas, theme: Theme, registry: dict,
                defer_label: bool = False) -> Optional[Callable[[], None]]:
        src_boxes = [registry[n] for n in self.sources if n in registry]
        dst_boxes = [registry[n] for n in self.sinks   if n in registry]
        if not src_boxes or not dst_boxes:
            return None

        col = theme.color_of(self.color)
        dasharray = "4,3" if self.dashed else None
        sw = theme.connector
        marker = (canvas.define_arrow_marker(
                      color=col, stroke_width=sw,
                      arrow_size=getattr(theme, "arrow_size", None),
                      name_hint="bus")
                  if self.arrow else None)

        drawn = registry.setdefault("__drawn_segments__", [])

        def _record_segment(x1, y1, x2, y2):
            if abs(x1 - x2) > 0.5 or abs(y1 - y2) > 0.5:
                drawn.append((x1, y1, x2, y2))

        def _line(x1, y1, x2, y2, *, end_marker=None):
            attrs = {"stroke": col, "stroke_width": sw}
            if dasharray:
                attrs["dasharray"] = dasharray
            if end_marker:
                attrs["marker_end"] = end_marker
            canvas.line(x1, y1, x2, y2, **attrs)
            _record_segment(x1, y1, x2, y2)

        # Labels are deferred so they can dodge every wire in the scope.
        label_jobs: List[Callable[[], None]] = []

        def _emit_label(segment, obstacles, *, size_token, prefer,
                        mask_bg=False):
            if not self.label:
                return
            obs = list(obstacles)

            def run():
                self._draw_placed_label(
                    canvas, theme, segment=segment, obstacles=obs,
                    color=col, size_token=size_token, prefer=prefer,
                    registry=registry, mask_bg=mask_bg)
            label_jobs.append(run)

        def _finish() -> None:
            for job in label_jobs:
                job()

        def _done() -> Optional[Callable[[], None]]:
            if defer_label:
                return _finish if label_jobs else None
            _finish()
            return None

        # Collect every rectangle the planner knows about -- src/dst
        # boxes, sibling anchors, auto-registered Box obstacles, AND
        # region labels (``__region_*`` entries) -- so the label
        # placer keeps the bus label outside any neighbouring panel
        # or block that the spine happens to run alongside.  Regions
        # whose interior strictly CONTAINS every endpoint of the
        # spine are skipped: the spine is "inside" that container so
        # its label has to live inside too, and using the container
        # as an obstacle would make every candidate overlap.
        src_pts = [(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in src_boxes]
        dst_pts = [(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in dst_boxes]
        spine_pts = src_pts + dst_pts

        def _strictly_contains(rect, pts):
            x0, y0, x1, y1 = rect
            for px, py in pts:
                if not (x0 < px < x1 and y0 < py < y1):
                    return False
            return True

        box_obstacles = []
        for name, b in registry.items():
            if name.startswith("__drawn_segments__"):
                continue
            if not isinstance(b, tuple) or len(b) != 4:
                continue
            bx, by, bw, bh = b
            rect = (bx, by, bx + bw, by + bh)
            if _strictly_contains(rect, spine_pts):
                continue
            box_obstacles.append(rect)

        all_boxes = src_boxes + dst_boxes
        centres_y = [b[1] + b[3] / 2 for b in all_boxes]
        avg_h = sum(b[3] for b in all_boxes) / len(all_boxes)
        y_spread = max(centres_y) - min(centres_y)
        # The shared-row shortcut only applies when no orientation was
        # explicitly requested AND the endpoints really do lie on one
        # line -- an explicit ``vertical``/``horizontal`` always gets
        # the full spine layout below.
        orientation_explicit = self.orientation != "auto"
        if not orientation_explicit and y_spread < avg_h * 0.5:
            # Shared-row: line lives in the gaps between consecutive boxes
            # (the boxes themselves "mask" the middle by being rendered on top).
            sorted_boxes = sorted(all_boxes, key=lambda b: b[0])
            mid_y = sum(centres_y) / len(centres_y)
            for b_left, b_right in zip(sorted_boxes, sorted_boxes[1:]):
                x_from = b_left[0] + b_left[2]
                x_to   = b_right[0]
                canvas.line(x_from, mid_y, x_to, mid_y,
                            stroke=col, stroke_width=sw,
                            dasharray=dasharray)
                _record_segment(x_from, mid_y, x_to, mid_y)
            if self.label:
                for b_left, b_right in zip(sorted_boxes, sorted_boxes[1:]):
                    x_from = b_left[0] + b_left[2]
                    x_to   = b_right[0]
                    # Place on the centred line gap; mask the dashed line
                    # behind the label.  The placer chooses above/below
                    # automatically based on which side has more room.
                    _emit_label(((x_from, mid_y), (x_to, mid_y)),
                                box_obstacles, size_token="tiny",
                                prefer="above", mask_bg=True)
            return _done()

        # Fan-out/fan-in: orient from the FLOW direction (source-cluster
        # centroid toward sink-cluster centroid), never from incidental
        # cluster spread:
        #   mostly-vertical flow   => horizontal spine in the inter-cluster gap
        #   mostly-horizontal flow => vertical spine in the inter-cluster gap
        src_cx, src_cy = self._centroid(src_boxes)
        dst_cx, dst_cy = self._centroid(dst_boxes)
        flow_dx = dst_cx - src_cx
        flow_dy = dst_cy - src_cy
        if self.orientation == "horizontal":
            horizontal = False   # spine perpendicular to horizontal flow
        elif self.orientation == "vertical":
            horizontal = True    # spine perpendicular to vertical flow
        else:
            # The centroid vector alone is not enough. A row of sources feeding
            # one sink set below AND to the side has a centroid vector that
            # leans horizontal while the only gap the spine can occupy is the
            # vertical one, so the centroid rule lays the spine across the sink
            # and the arrowhead lands inside a box. Decide instead on which
            # axis the two clusters are actually separated: a spine needs a
            # gap to sit in, and only a separating axis has one. Fall back to
            # the centroid when both axes separate (a diagonal flow, where
            # either spine is sound) or neither does (interleaved clusters,
            # where no gap exists on either axis and the caller should be
            # declaring the orientation).
            v_gap = (min(b[1] for b in src_boxes)
                     >= max(b[1] + b[3] for b in dst_boxes)
                     or min(b[1] for b in dst_boxes)
                     >= max(b[1] + b[3] for b in src_boxes))
            h_gap = (min(b[0] for b in src_boxes)
                     >= max(b[0] + b[2] for b in dst_boxes)
                     or min(b[0] for b in dst_boxes)
                     >= max(b[0] + b[2] for b in src_boxes))
            if v_gap and not h_gap:
                horizontal = True    # only the vertical axis separates them
            elif h_gap and not v_gap:
                horizontal = False   # only the horizontal axis separates them
            else:
                horizontal = abs(flow_dy) >= abs(flow_dx)

        rail_off = theme.unit * 2.0
        edge_inset = theme.unit

        if horizontal:
            # Horizontal spine; flow is vertical.
            source_below = src_cy > dst_cy
            if source_below:
                gap_lo = max(b[1] + b[3] for b in dst_boxes)  # sinks bottom
                gap_hi = min(b[1] for b in src_boxes)         # sources top
                src_edge = lambda b: (b[0] + b[2] / 2, b[1])              # top
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])       # bottom
            else:
                gap_lo = max(b[1] + b[3] for b in src_boxes)
                gap_hi = min(b[1] for b in dst_boxes)
                src_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1])
            if gap_lo < gap_hi:
                # Spine sits in the clear inter-cluster gap, but never
                # closer to the arrowed edge than one arrow stub: the
                # entry segment has to be longer than the arrowhead it
                # carries, or the bus terminates in a triangle stuck to
                # the sink's border with no shaft behind it. The gap is
                # reserved for this in the pre-measure pass, so the
                # clamp normally has room; when it does not, a spine
                # pressed against the SOURCE cluster still reads better
                # than an invisible arrow.
                stub = theme.arrow_stub_px
                sink_edge = gap_lo if source_below else gap_hi
                spine_y = (gap_lo + gap_hi) / 2
                if source_below:
                    spine_y = max(spine_y, sink_edge + stub)
                    spine_y = min(spine_y, max(gap_hi, sink_edge + stub))
                else:
                    spine_y = min(spine_y, sink_edge - stub)
                    spine_y = max(spine_y, min(gap_lo, sink_edge - stub))
            else:
                # Overlapping clusters: fall back to nearest-edge midpoint.
                if source_below:
                    spine_y = (max(b[1] for b in src_boxes)
                               + min(b[1] + b[3] for b in dst_boxes)) / 2
                else:
                    spine_y = (min(b[1] + b[3] for b in src_boxes)
                               + max(b[1] for b in dst_boxes)) / 2

            def _cluster_taps(boxes, edge_of, *, arrows: bool):
                """Vertical taps from each box to the spine; or, when a
                straight tap would impale a sibling endpoint, a side
                rail alongside the cluster joining the spine once.
                Returns the tap x-coordinates on the spine."""
                blocked = any(
                    self._v_seg_hits(edge_of(b)[0], edge_of(b)[1], spine_y,
                                     all_boxes, b)
                    for b in boxes)
                if not blocked:
                    xs = []
                    for b in boxes:
                        px, py = edge_of(b)
                        _line(*(((px, spine_y, px, py)
                                 if arrows else (px, py, px, spine_y))),
                              end_marker=(marker if arrows else None))
                        line_obstacles.append((px - sw, min(py, spine_y),
                                               px + sw, max(py, spine_y)))
                        xs.append(px)
                    return xs
                # Side rail: exit each box horizontally toward open air,
                # run the rail alongside the cluster, join the spine.
                cl = min(b[0] for b in boxes)
                cr = max(b[0] + b[2] for b in boxes)
                other_c = dst_cx if boxes is src_boxes else src_cx
                to_right = other_c >= (cl + cr) / 2
                rail_x = cr + rail_off if to_right else cl - rail_off
                tap_ys = []
                for b in boxes:
                    ex = (b[0] + b[2]) if to_right else b[0]
                    ey = b[1] + b[3] / 2
                    if arrows:
                        _line(rail_x, ey, ex, ey, end_marker=marker)
                    else:
                        _line(ex, ey, rail_x, ey)
                    line_obstacles.append((min(ex, rail_x), ey - sw,
                                           max(ex, rail_x), ey + sw))
                    tap_ys.append(ey)
                far_y = (max(tap_ys) if source_below == (boxes is src_boxes)
                         else min(tap_ys))
                _line(rail_x, far_y, rail_x, spine_y)
                line_obstacles.append((rail_x - sw, min(far_y, spine_y),
                                       rail_x + sw, max(far_y, spine_y)))
                return [rail_x]

            line_obstacles = []  # drawn line rects we'll want to avoid
            src_taps_x = _cluster_taps(src_boxes, src_edge, arrows=False)

            # Single-sink fan-in (``concatenation`` junction): taps from
            # each source rise to a short horizontal bar, then ONE arrow
            # from the bar goes to the sink -- orthogonally.
            is_fan_in = len(dst_boxes) == 1
            if is_fan_in:
                x0 = min(src_taps_x); x1 = max(src_taps_x)
                if x1 - x0 > 0.5:
                    _line(x0, spine_y, x1, spine_y)
                    # T-bar obstacle -- pad it by half a text-line's height
                    # so the placer never sits a label flush against it.
                    bar_pad = theme.unit * 0.5
                    line_obstacles.append((x0, spine_y - bar_pad,
                                           x1, spine_y + bar_pad))
                bar_mid_x = (x0 + x1) / 2
                sink = dst_boxes[0]
                dpx, dpy = dst_edge(sink)
                # Enter the sink at the CENTER of its facing edge: a
                # centred entry reads as "the bus feeds this card",
                # while a bar-aligned entry at the face's extreme reads
                # as clipping a corner (rail-form buses put the bar far
                # to one side of the sink). Fall back to the bar-aligned
                # position, clamped into the face's usable span, when
                # the centred descent or its jog along the spine would
                # strike another endpoint or box.
                lo = sink[0] + min(edge_inset, sink[2] / 4)
                hi = sink[0] + sink[2] - min(edge_inset, sink[2] / 4)
                center_x = sink[0] + sink[2] / 2.0
                bar_aligned = min(max(bar_mid_x, lo), hi)
                centred_clear = (
                    not self._v_seg_hits(center_x, spine_y, dpy,
                                         all_boxes, sink)
                    and not self._h_seg_hits(spine_y,
                                             min(bar_mid_x, center_x),
                                             max(bar_mid_x, center_x),
                                             all_boxes, sink))
                if centred_clear:
                    entry_x = center_x
                else:
                    # The fallback is a visible layout concession (the
                    # bus meets the sink off-centre), so it is never
                    # silent: it always warns, and it leaves a note in
                    # the active debug recorder when one is installed.
                    entry_x = bar_aligned
                    msg = (
                        f"Bus fan-in into sink {self.sinks[0]!r}: the "
                        f"centred entry at x={center_x:.1f} is walled "
                        f"(the descent to the sink edge or the jog "
                        f"along the spine would strike another "
                        f"endpoint), so the entry falls back to the "
                        f"bar-aligned x={entry_x:.1f}. The bus will "
                        f"meet the sink off-centre; open the band "
                        f"below the sink or move the blocking "
                        f"endpoint to restore a centred entry.")
                    warnings.warn(msg)
                    from ..auto import debug as _layout_debug
                    rec = _layout_debug.active()
                    if rec is not None:
                        rec.note(msg)
                if abs(entry_x - bar_mid_x) > 0.5:
                    _line(bar_mid_x, spine_y, entry_x, spine_y)
                _line(entry_x, spine_y, entry_x, dpy, end_marker=marker)
                line_obstacles.append((entry_x - sw, min(spine_y, dpy),
                                       entry_x + sw, max(spine_y, dpy)))
                if x1 - x0 > 0.5:
                    # For a fan-in, prefer the empty space BETWEEN the
                    # source boxes and the T-bar (i.e. on the source side
                    # of the bar).
                    prefer = "below" if source_below else "above"
                    _emit_label(((x0, spine_y), (x1, spine_y)),
                                box_obstacles + line_obstacles,
                                size_token="micro", prefer=prefer)
                else:
                    seg_y0 = min(spine_y, dpy); seg_y1 = max(spine_y, dpy)
                    _emit_label(((entry_x, seg_y0), (entry_x, seg_y1)),
                                box_obstacles + line_obstacles,
                                size_token="micro",
                                prefer="left")
            else:
                # Fan-out (or symmetric): taps from spine to each sink,
                # with an arrowhead on each.  Spine spans all tap xs.
                taps_x = list(src_taps_x)
                taps_x += _cluster_taps(dst_boxes, dst_edge, arrows=True)
                x0 = min(taps_x); x1 = max(taps_x)
                _line(x0, spine_y, x1, spine_y)
                prefer = "above" if source_below else "below"
                _emit_label(((x0, spine_y), (x1, spine_y)),
                            box_obstacles + line_obstacles,
                            size_token="tiny", prefer=prefer)
        else:
            # Vertical spine; flow is horizontal.
            source_left = src_cx < dst_cx
            if source_left:
                gap_lo = max(b[0] + b[2] for b in src_boxes)  # sources right
                gap_hi = min(b[0] for b in dst_boxes)         # sinks left
                src_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0], b[1] + b[3] / 2)
            else:
                gap_lo = max(b[0] + b[2] for b in dst_boxes)
                gap_hi = min(b[0] for b in src_boxes)
                src_edge = lambda b: (b[0], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
            if gap_lo < gap_hi:
                spine_x = (gap_lo + gap_hi) / 2
            else:
                if source_left:
                    spine_x = (max(b[0] + b[2] for b in src_boxes)
                               + min(b[0] for b in dst_boxes)) / 2
                else:
                    spine_x = (min(b[0] for b in src_boxes)
                               + max(b[0] + b[2] for b in dst_boxes)) / 2

            def _cluster_taps_h(boxes, edge_of, *, arrows: bool):
                blocked = any(
                    self._h_seg_hits(edge_of(b)[1], edge_of(b)[0], spine_x,
                                     all_boxes, b)
                    for b in boxes)
                if not blocked:
                    ys = []
                    for b in boxes:
                        px, py = edge_of(b)
                        _line(*(((spine_x, py, px, py)
                                 if arrows else (px, py, spine_x, py))),
                              end_marker=(marker if arrows else None))
                        line_obstacles.append((min(px, spine_x), py - sw,
                                               max(px, spine_x), py + sw))
                        ys.append(py)
                    return ys
                ct = min(b[1] for b in boxes)
                cb = max(b[1] + b[3] for b in boxes)
                other_c = dst_cy if boxes is src_boxes else src_cy
                to_bottom = other_c >= (ct + cb) / 2
                rail_y = cb + rail_off if to_bottom else ct - rail_off
                tap_xs = []
                for b in boxes:
                    ex = b[0] + b[2] / 2
                    ey = (b[1] + b[3]) if to_bottom else b[1]
                    if arrows:
                        _line(ex, rail_y, ex, ey, end_marker=marker)
                    else:
                        _line(ex, ey, ex, rail_y)
                    line_obstacles.append((ex - sw, min(ey, rail_y),
                                           ex + sw, max(ey, rail_y)))
                    tap_xs.append(ex)
                far_x = (max(tap_xs) if source_left == (boxes is src_boxes)
                         else min(tap_xs))
                _line(far_x, rail_y, spine_x, rail_y)
                line_obstacles.append((min(far_x, spine_x), rail_y - sw,
                                       max(far_x, spine_x), rail_y + sw))
                return [rail_y]

            line_obstacles = []
            taps_y = list(_cluster_taps_h(src_boxes, src_edge, arrows=False))
            taps_y += _cluster_taps_h(dst_boxes, dst_edge, arrows=True)
            y0 = min(taps_y); y1 = max(taps_y)
            if y1 - y0 > 0.5:
                _line(spine_x, y0, spine_x, y1)
            if self.label:
                # Prefer the SOURCE side of the spine for the label -- the
                # sink side is typically a cluster of targets (often with
                # their own labels/regions), so placing the bus label on
                # the sink side tends to collide with other content.
                prefer = "left" if source_left else "right"
                _emit_label(((spine_x, y0), (spine_x, y1)),
                            box_obstacles + line_obstacles,
                            size_token="tiny", prefer=prefer)
        return _done()
