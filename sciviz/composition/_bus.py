"""Bus: multi-endpoint connector routed through a single spine."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

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
        lines (T-bars, taps, other boxes).  When ``mask_bg`` is True, a
        white rectangle is drawn behind the label so a dashed line
        reads as passing cleanly behind the text.
        """
        if not self.label:
            return
        from ..auto.labels import (
            measure_label, place_segment_label,
            register_label_obstacle, registry_label_obstacles,
        )
        lbl = measure_label(self.label, theme, size_token)
        all_obstacles = list(obstacles)
        if registry is not None:
            all_obstacles += registry_label_obstacles(registry)
        placed = place_segment_label(
            segment, lbl, obstacles=all_obstacles, prefer=prefer,
            gap=theme.unit * 0.35,
        )
        rect, anchor = placed.rect, placed.anchor
        x0, y0, x1, y1 = rect
        if mask_bg:
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

    def _render(self, canvas: Canvas, theme: Theme, registry: dict) -> None:
        src_boxes = [registry[n] for n in self.sources if n in registry]
        dst_boxes = [registry[n] for n in self.sinks   if n in registry]
        if not src_boxes or not dst_boxes:
            return

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
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x_from, mid_y), (x_to, mid_y)),
                        obstacles=box_obstacles,
                        color=col,
                        size_token="tiny",
                        prefer="above",
                        registry=registry,
                        mask_bg=True,
                    )
            return

        # Otherwise fan-out/fan-in: one-side (sources or sinks) is clustered,
        # other side is spread out.  Build a spine OFFSET from the clustered
        # side toward the spread side, and route taps to each endpoint.
        # Orientation precedence: explicit author hint > dominant geometry.
        # ``orientation`` describes the FLOW (source -> sink) direction:
        #   "horizontal" flow (src left of sinks)  => spine is VERTICAL
        #   "vertical"   flow (src above of sinks) => spine is HORIZONTAL
        # See the symmetric margin inflation in ``Flowed._apply_flow_margins``.
        all_x = [b[0] + b[2] / 2 for b in all_boxes]
        x_spread = max(all_x) - min(all_x)
        if self.orientation == "horizontal":
            horizontal = False   # spine perpendicular to horizontal flow
        elif self.orientation == "vertical":
            horizontal = True    # spine perpendicular to vertical flow
        else:
            horizontal = x_spread >= y_spread

        if horizontal:
            # Spine is horizontal, spread is along x.  Decide which cluster
            # is "below" (source) vs "above" (sink) by mean y.
            src_mean_y = sum(b[1] + b[3] / 2 for b in src_boxes) / len(src_boxes)
            dst_mean_y = sum(b[1] + b[3] / 2 for b in dst_boxes) / len(dst_boxes)
            source_below = src_mean_y > dst_mean_y
            if source_below:
                src_edge = lambda b: (b[0] + b[2] / 2, b[1])              # top
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])       # bottom
                # Spine sits in the middle of the gap between the source
                # tops and the sink bottom, so the side label has clear
                # room above it without touching the sink.
                src_top = max(b[1] for b in src_boxes)
                dst_bot = min(b[1] + b[3] for b in dst_boxes)
                spine_y = (src_top + dst_bot) / 2
            else:
                src_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1])
                src_bot = min(b[1] + b[3] for b in src_boxes)
                dst_top = max(b[1] for b in dst_boxes)
                spine_y = (src_bot + dst_top) / 2

            # Single-sink fan-in (``concatenation`` junction): taps from
            # each source rise to a short horizontal bar, then ONE arrow
            # from the centre of that bar goes all the way to the sink.
            is_fan_in = len(dst_boxes) == 1 and len(src_boxes) > 1
            src_taps_x = [src_edge(b)[0] for b in src_boxes]

            line_obstacles = []  # drawn line rects we'll want to avoid
            for b in src_boxes:
                px, py = src_edge(b)
                canvas.line(px, py, px, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                _record_segment(px, py, px, spine_y)
                # tap obstacle: thin vertical stripe, sw wide
                y_lo, y_hi = min(py, spine_y), max(py, spine_y)
                line_obstacles.append((px - sw, y_lo, px + sw, y_hi))
            if is_fan_in:
                x0 = min(src_taps_x); x1 = max(src_taps_x)
                canvas.line(x0, spine_y, x1, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                _record_segment(x0, spine_y, x1, spine_y)
                # T-bar obstacle -- pad it by half a text-line's height so
                # the placer never places a label flush against it.
                bar_pad = theme.unit * 0.5
                line_obstacles.append((x0, spine_y - bar_pad,
                                       x1, spine_y + bar_pad))
                bar_mid_x = (x0 + x1) / 2
                dpx, dpy = dst_edge(dst_boxes[0])
                attrs = {"stroke": col, "stroke_width": sw}
                if dasharray:
                    attrs["dasharray"] = dasharray
                if self.arrow:
                    attrs["marker_end"] = marker
                canvas.line(bar_mid_x, spine_y, dpx, dpy, **attrs)
                _record_segment(bar_mid_x, spine_y, dpx, dpy)
                # sink arrow obstacle
                y_lo, y_hi = min(spine_y, dpy), max(spine_y, dpy)
                line_obstacles.append((bar_mid_x - sw, y_lo,
                                       bar_mid_x + sw, y_hi))
                if self.label:
                    # For a fan-in, prefer the empty space BETWEEN the
                    # source boxes and the T-bar (i.e. on the source side
                    # of the bar).  That's "below" the bar when sources
                    # are below, or "above" when sources are above.
                    prefer = "below" if source_below else "above"
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x0, spine_y), (x1, spine_y)),
                        obstacles=box_obstacles + line_obstacles,
                        color=col,
                        size_token="micro",
                        prefer=prefer,
                        registry=registry,
                        mask_bg=False,
                    )
            else:
                # Fan-out (or symmetric): taps from spine to each sink,
                # with an arrowhead on each.  Spine spans all tap xs.
                taps_x = list(src_taps_x)
                for b in dst_boxes:
                    px, py = dst_edge(b)
                    attrs = {"stroke": col, "stroke_width": sw}
                    if dasharray:
                        attrs["dasharray"] = dasharray
                    if self.arrow:
                        attrs["marker_end"] = marker
                    canvas.line(px, spine_y, px, py, **attrs)
                    _record_segment(px, spine_y, px, py)
                    taps_x.append(px)
                    y_lo, y_hi = min(spine_y, py), max(spine_y, py)
                    line_obstacles.append((px - sw, y_lo, px + sw, y_hi))
                x0 = min(taps_x); x1 = max(taps_x)
                canvas.line(x0, spine_y, x1, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                _record_segment(x0, spine_y, x1, spine_y)
                if self.label:
                    prefer = "above" if source_below else "below"
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x0, spine_y), (x1, spine_y)),
                        obstacles=box_obstacles + line_obstacles,
                        color=col,
                        size_token="tiny",
                        prefer=prefer,
                        registry=registry,
                        mask_bg=False,
                    )
        else:
            # Vertical spine (left-right cluster spread vertically).
            src_mean_x = sum(b[0] + b[2] / 2 for b in src_boxes) / len(src_boxes)
            dst_mean_x = sum(b[0] + b[2] / 2 for b in dst_boxes) / len(dst_boxes)
            source_left = src_mean_x < dst_mean_x
            if source_left:
                spine_x = (max(b[0] + b[2] for b in src_boxes)
                           + min(b[0] for b in dst_boxes)) / 2
                src_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0], b[1] + b[3] / 2)
            else:
                spine_x = (min(b[0] for b in src_boxes)
                           + max(b[0] + b[2] for b in dst_boxes)) / 2
                src_edge = lambda b: (b[0], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
            taps_y = []
            line_obstacles = []
            for b in src_boxes:
                px, py = src_edge(b)
                canvas.line(px, py, spine_x, py,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                _record_segment(px, py, spine_x, py)
                taps_y.append(py)
                x_lo, x_hi = min(px, spine_x), max(px, spine_x)
                line_obstacles.append((x_lo, py - sw, x_hi, py + sw))
            for b in dst_boxes:
                px, py = dst_edge(b)
                attrs = {"stroke": col, "stroke_width": sw}
                if dasharray:
                    attrs["dasharray"] = dasharray
                if self.arrow:
                    attrs["marker_end"] = marker
                canvas.line(spine_x, py, px, py, **attrs)
                _record_segment(spine_x, py, px, py)
                taps_y.append(py)
                x_lo, x_hi = min(spine_x, px), max(spine_x, px)
                line_obstacles.append((x_lo, py - sw, x_hi, py + sw))
            y0 = min(taps_y); y1 = max(taps_y)
            canvas.line(spine_x, y0, spine_x, y1,
                        stroke=col, stroke_width=sw, dasharray=dasharray)
            _record_segment(spine_x, y0, spine_x, y1)
            if self.label:
                # Prefer the SOURCE side of the spine for the label -- the
                # sink side is typically a cluster of targets (often with
                # their own labels/regions), so placing the bus label on
                # the sink side tends to collide with other content.
                prefer = "left" if source_left else "right"
                self._draw_placed_label(
                    canvas, theme,
                    segment=((spine_x, y0), (spine_x, y1)),
                    obstacles=box_obstacles + line_obstacles,
                    color=col,
                    size_token="tiny",
                    prefer=prefer,
                    registry=registry,
                    mask_bg=False,
                )

