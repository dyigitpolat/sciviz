"""Two rules that decide whether a connector reads as a connector.

1. Every arrowed endpoint keeps a stub longer than the arrowhead drawn
   on it. A head sitting flush on a border is a triangle glued to a box,
   not an arrow arriving somewhere -- and the failure is invisible to
   any test that only checks that a path exists.

2. Two endpoints leaving their boxes the same way can always meet on a
   shared lane. Offering deeper lanes lets the planner buy its way
   around a wire that already owns the shallow one with a longer
   outgoing arm, instead of crossing it for no reason.
"""
from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, DEFAULT_THEME, Diagram, Row
from sciviz.auto import router as rt


def _stub_length(path, index_from_end: bool = False):
    """Perpendicular run at one end of a planned path."""
    (ax, ay), (bx, by) = (path[-1], path[-2]) if index_from_end \
        else (path[0], path[1])
    return abs(bx - ax) + abs(by - ay)


# --------------------------------------------------------------------
# arrow stubs
# --------------------------------------------------------------------

def test_theme_derives_the_stub_from_the_arrow_size():
    t = DEFAULT_THEME
    assert t.arrow_head_px == pytest.approx(t.arrow_size * t.connector)
    assert t.arrow_stub_px > t.arrow_head_px, "no shaft behind the head"
    bigger = t.with_overrides(arrow_size=t.arrow_size * 2)
    assert bigger.arrow_stub_px > t.arrow_stub_px, (
        "stub must grow with the arrowhead it has to carry")


def test_stub_survives_a_neighbour_pressed_against_the_endpoint():
    """The obstacle limit used to win, collapsing the stub to nothing."""
    src = rt.Box(x=0.0, y=0.0, w=60.0, h=20.0, name="src", kind="anchor")
    dst = rt.Box(x=0.0, y=60.0, w=60.0, h=20.0, name="dst", kind="anchor")
    # A blocker 2 pt under the destination's bottom edge.
    wall = rt.Box(x=0.0, y=82.0, w=60.0, h=6.0, name="wall", kind="anchor")
    policy = rt.CrossPolicy(head_len=4.2)
    plan = rt.plan_path(
        rt.Endpoint(src, "bottom"), rt.Endpoint(dst, "bottom"),
        anchors=[src, dst, wall], policy=policy)
    assert _stub_length(plan.waypoints, index_from_end=True) > 4.2, (
        "arrowhead would consume the whole stub")


def test_zero_head_keeps_the_historical_stub():
    src = rt.Box(x=0.0, y=0.0, w=40.0, h=20.0, name="src", kind="anchor")
    dst = rt.Box(x=80.0, y=0.0, w=40.0, h=20.0, name="dst", kind="anchor")
    plain = rt.plan_path(rt.Endpoint(src, "right"), rt.Endpoint(dst, "left"),
                         anchors=[src, dst])
    headed = rt.plan_path(rt.Endpoint(src, "right"), rt.Endpoint(dst, "left"),
                          anchors=[src, dst],
                          policy=rt.CrossPolicy(head_len=6.0))
    assert _stub_length(headed.waypoints) >= _stub_length(plain.waypoints)


def test_bus_fan_in_keeps_a_visible_entry_segment():
    """The spine must not sit a point away from the edge it arrows into."""
    body = Column(
        Anchor("sink", Box("sink", width=140, height=30)),
        Column(*[Anchor(f"s{i}", Box(f"source {i}", width=100, height=16))
                 for i in range(4)], gap="xs"),
        Connect([f"s{i}" for i in range(4)], "sink"),
        gap="sm",
    )
    d = Diagram.for_paper(body)
    theme = d._layout_theme()
    from sciviz.core import Canvas
    from sciviz.connect._resolver import _FlowResolver
    res = _FlowResolver(body)
    res.measure(theme)
    canvas = Canvas()
    res.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(600, 400)
    # The entry segment is the one carrying the marker; find its length.
    import re
    marked = re.findall(
        r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"'
        r'[^>]*marker-end', svg)
    assert marked, "bus drew no arrowed segment"
    for x1, y1, x2, y2 in marked:
        length = abs(float(x2) - float(x1)) + abs(float(y2) - float(y1))
        assert length >= theme.arrow_stub_px - 0.5, (
            f"bus entry segment is {length:.1f}pt, shorter than the "
            f"{theme.arrow_stub_px:.1f}pt an arrowhead needs")


# --------------------------------------------------------------------
# common lanes
# --------------------------------------------------------------------

def test_common_lane_ladder_offers_deeper_lanes():
    lanes = rt._common_lane_candidates(
        10.0, 14.0, +1, 0.0, 200.0, existing_segments=(),
        policy=rt.DEFAULT_POLICY)
    assert len(lanes) >= 3
    assert lanes == sorted(lanes), "lanes must be offered shallow-first"
    assert lanes[0] >= 14.0 - 1e-6, "shallowest lane must clear both stubs"


def test_common_lane_clears_an_existing_wire():
    lanes = rt._common_lane_candidates(
        10.0, 14.0, +1, 0.0, 200.0,
        existing_segments=[(0.0, 40.0, 100.0, 40.0)],
        policy=rt.DEFAULT_POLICY)
    assert any(lane > 40.0 for lane in lanes), (
        "no lane offered beyond the wire already drawn")


def test_lane_ladder_ignores_wires_outside_the_span():
    """A wire elsewhere in the figure is not in the way."""
    lanes = rt._common_lane_candidates(
        10.0, 14.0, +1, 0.0, 100.0,
        existing_segments=[(400.0, 40.0, 500.0, 40.0)],
        policy=rt.DEFAULT_POLICY)
    assert all(lane <= 14.0 + rt._MAX_LANE_STEPS * 12.0 for lane in lanes)


def test_lane_ladder_is_bounded():
    """The crossing penalty may buy a longer arm, never an excursion."""
    lanes = rt._common_lane_candidates(
        10.0, 14.0, +1, 0.0, 400.0,
        existing_segments=[(0.0, 900.0, 400.0, 900.0)],
        policy=rt.DEFAULT_POLICY)
    assert max(lanes) < 200.0, (
        f"unbounded lane ladder: {max(lanes)} -- a detour must stay a "
        f"detour")


def test_same_side_run_routes_around_an_existing_wire():
    """The regression: a long same-side run used to step through a
    shorter one sitting in the shallow lane."""
    src = rt.Box(x=0.0, y=0.0, w=40.0, h=30.0, name="src", kind="anchor")
    dst = rt.Box(x=300.0, y=0.0, w=40.0, h=30.0, name="dst", kind="anchor")
    # A wire already parked just below the two boxes, spanning the middle.
    existing = [(100.0, 40.0, 240.0, 40.0),
                (100.0, 30.0, 100.0, 40.0),
                (240.0, 30.0, 240.0, 40.0)]
    plan = rt.plan_path(
        rt.Endpoint(src, "bottom"), rt.Endpoint(dst, "bottom"),
        anchors=[src, dst], existing_segments=existing)
    crossings = 0
    pts = plan.waypoints
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        if abs(ay - by) > 0.5:      # vertical leg
            lo, hi = sorted((ay, by))
            if lo < 40.0 < hi and 100.0 < ax < 240.0:
                crossings += 1
    assert crossings == 0, (
        "planner crossed a wire it could have routed under")


def test_bus_members_are_not_charged_the_spine_budget_each():
    """A stack of tags feeding a bus must not be spread by clearance
    nothing uses.

    The spine sits in the gap BETWEEN the two clusters, which is a
    layout gap. Charging every member the full spine budget on both
    faces inflated a run of pills by its own height again.
    """
    from sciviz import Chip, Palette
    from sciviz.connect._resolver import _FlowResolver, _collect_anchors

    tags = [Anchor(f"t{i}", Chip(f"domain {i}", color=Palette.teal))
            for i in range(5)]
    body = Column(
        Anchor("hub", Box("hub", width=140, height=30)),
        Column(*tags, gap="xs"),
        Connect([t.name for t in tags], "hub", orientation="vertical"),
        gap="sm",
    )
    theme = Diagram.for_paper(body)._layout_theme()
    _FlowResolver(body).measure(theme)
    anchors = {}
    _collect_anchors(body, anchors)
    hub = anchors["hub"]
    # The sink keeps room for a visible arrowhead.
    assert max(hub.margin_top, hub.margin_bottom) >= theme.arrow_stub_px - 0.1

    for i in range(5):
        a = anchors[f"t{i}"]
        pill_h = a.child.measure(theme).h
        added = a.margin_top + a.margin_bottom
        assert added < pill_h * 0.5, (
            f"tag {i} carries {added:.1f}pt of bus margin on a "
            f"{pill_h:.1f}pt pill")
