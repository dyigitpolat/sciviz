"""Router crossing behaviour.

Spec:

*   :func:`plan_path` prefers valid paths that do NOT cross already-
    drawn segments, when such a path exists.
*   :func:`render_orthogonal` draws a small semicircular arc in place
    of the straight line where a new segment crosses an existing
    perpendicular segment ("wire jump"), instead of a flat
    intersection.
"""
from sciviz.routing import (
    Box as RBox,
    Endpoint,
    plan_path,
    render_orthogonal,
    Plan,
)


class _FakeCanvas:
    """Minimal canvas that records method calls as tuples."""

    def __init__(self):
        self.calls = []

    def line(self, *args, **kwargs):
        self.calls.append(("line", args, kwargs))

    def path(self, *args, **kwargs):
        self.calls.append(("path", args, kwargs))

    def circle(self, *args, **kwargs):
        self.calls.append(("circle", args, kwargs))


def test_plan_path_prefers_non_crossing_route():
    # Two horizontal anchors on the left and right; a "pre-existing"
    # vertical segment in the middle column between them, sitting
    # ABOVE the straight horizontal route.
    # The planner must pick a route that goes BELOW the existing
    # segment (no crossing) over one that goes through it, when both
    # are valid.
    src = RBox(x=0, y=100, w=40, h=40, name="src")
    dst = RBox(x=300, y=100, w=40, h=40, name="dst")
    # Pre-drawn vertical segment from (180, 0) to (180, 80): entirely
    # above the direct horizontal corridor between src and dst.
    existing = [(180.0, 0.0, 180.0, 80.0)]
    anchors = [src, dst]
    plan = plan_path(
        Endpoint(src, side="right", tap=8),
        Endpoint(dst, side="left", tap=8),
        anchors=anchors,
        existing_segments=existing,
    )
    # Direct horizontal route at y=120 does not cross the segment
    # because the segment stops at y=80.  Either way the chosen route
    # must have zero crossings with the existing segment.
    pts = plan.waypoints
    crosses = _count_crossings(pts, existing)
    assert crosses == 0, (
        f"plan chose a path that crosses existing segment "
        f"{crosses} time(s); waypoints={pts}"
    )


def test_render_orthogonal_emits_arc_hop_for_crossing():
    # A horizontal new segment crossing a vertical existing segment
    # in the middle should yield an SVG <path> element (arc hop),
    # not a plain <line>.
    canvas = _FakeCanvas()
    plan = Plan(
        waypoints=[(0.0, 50.0), (200.0, 50.0)],
        crossings=[],
        style_hint="direct",
    )
    existing = [(100.0, 0.0, 100.0, 100.0)]
    render_orthogonal(
        canvas, plan,
        stroke="#000", width=1.0,
        src_dot=False,
        existing_segments=existing,
        hop_radius=3.0,
    )
    # Expect at least one <path> call with an 'A' arc command; no
    # plain 'line' call for this crossed segment.
    has_path_with_arc = any(
        call[0] == "path" and ("A " in call[1][0] if call[1] else False)
        for call in canvas.calls
    )
    has_plain_line = any(call[0] == "line" for call in canvas.calls)
    assert has_path_with_arc, (
        "expected an arc-bearing <path> element for the wire-jump, "
        f"got calls={canvas.calls}"
    )
    assert not has_plain_line, (
        "expected the hop-carrying segment to NOT also be drawn as a "
        f"plain line; got calls={canvas.calls}"
    )


def test_render_orthogonal_plain_line_when_no_crossings():
    # No existing segments: straight orthogonal legs must still be
    # emitted as plain <line> elements (cheaper + crisper).
    canvas = _FakeCanvas()
    plan = Plan(
        waypoints=[(0.0, 50.0), (200.0, 50.0)],
        crossings=[],
        style_hint="direct",
    )
    render_orthogonal(
        canvas, plan,
        stroke="#000", width=1.0,
        src_dot=False,
        existing_segments=[],
    )
    line_calls = [c for c in canvas.calls if c[0] == "line"]
    assert len(line_calls) == 1, (
        f"expected a single <line> call with no hops; got {canvas.calls}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_crossings(waypoints, segments, tol=0.5):
    n = 0
    for i in range(len(waypoints) - 1):
        ax, ay = waypoints[i]
        bx, by = waypoints[i + 1]
        horiz = abs(ay - by) < tol
        vert = abs(ax - bx) < tol
        for (ex1, ey1, ex2, ey2) in segments:
            eh = abs(ey1 - ey2) < tol
            ev = abs(ex1 - ex2) < tol
            if horiz and ev:
                x_lo, x_hi = sorted((ax, bx))
                y_lo, y_hi = sorted((ey1, ey2))
                if x_lo < ex1 < x_hi and y_lo < ay < y_hi:
                    n += 1
            elif vert and eh:
                y_lo, y_hi = sorted((ay, by))
                x_lo, x_hi = sorted((ex1, ex2))
                if y_lo < ey1 < y_hi and x_lo < ax < x_hi:
                    n += 1
    return n
