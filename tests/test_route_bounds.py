"""Routes stay inside the drawing when a route inside exists.

``plan_path(bounds=...)`` holds every candidate inside the scope's
region first; only when no validated route exists there does the
planner leave it (and records a debug note). Flow passes the hull of
everything the scope has laid out or drawn, grown by one lane.
"""

from __future__ import annotations

from sciviz import Anchor, Box as Card, Column, Connect, Diagram, Row
from sciviz.auto import router as R
from sciviz.auto.debug import DebugRecorder, record_into


def _walled_case():
    """Source above-left, sink below-right, a wall between them that
    spans the whole scope except a narrow interior gutter, and a drawn
    wire that every interior route must cross once, while an excursion
    far left of the drawing crosses nothing."""
    src = R.Box(x=40, y=0, w=30, h=20, name="src")
    dst = R.Box(x=140, y=120, w=30, h=20, name="dst")
    wall_l = R.Box(x=0, y=60, w=90, h=20, name="wl")
    wall_r = R.Box(x=110, y=60, w=100, h=20, name="wr")
    # a drawn wire across the gutter between the walls: going through
    # the gutter costs one hop, going round the left wall costs none
    drawn = [(85.0, 45.0, 115.0, 45.0)]
    anchors = [src, dst, wall_l, wall_r]
    return src, dst, anchors, drawn


def test_bounded_route_never_leaves_the_scope():
    src, dst, anchors, drawn = _walled_case()
    bounds = R.Box(x=-5, y=-5, w=220, h=150, name="__scope__",
                   kind="region")
    plan = R.plan_path(R.Endpoint(src, "bottom", tap=12),
                       R.Endpoint(dst, "top", tap=12),
                       anchors=anchors, existing_segments=drawn,
                       bounds=bounds)
    for (x, y) in plan.waypoints:
        assert bounds.contains_point(x, y, eps=0.5), plan.waypoints
    # Without the bound the crossing-free excursion wins.
    free = R.plan_path(R.Endpoint(src, "bottom", tap=12),
                       R.Endpoint(dst, "top", tap=12),
                       anchors=anchors, existing_segments=drawn)
    assert min(x for x, _ in free.waypoints) < bounds.left


def test_unbounded_route_keeps_todays_answer_when_it_is_inside():
    """A route found inside the bound is the unbounded ladder's route."""
    src = R.Box(x=0, y=0, w=40, h=20, name="a")
    dst = R.Box(x=100, y=80, w=40, h=20, name="b")
    free = R.plan_path(R.Endpoint(src, "bottom", tap=12),
                       R.Endpoint(dst, "top", tap=12), anchors=[src, dst])
    bounded = R.plan_path(R.Endpoint(src, "bottom", tap=12),
                          R.Endpoint(dst, "top", tap=12), anchors=[src, dst],
                          bounds=R.Box(x=-30, y=-30, w=200, h=160))
    assert bounded.waypoints == free.waypoints


def test_no_route_inside_falls_back_and_notes_it():
    """A sink walled in on every side: the planner still returns a
    route, and the debug log says it left the bound."""
    src = R.Box(x=0, y=0, w=20, h=20, name="src")
    dst = R.Box(x=100, y=100, w=20, h=20, name="dst")
    walls = [R.Box(x=80, y=80, w=60, h=5, name="n"),
             R.Box(x=80, y=135, w=60, h=5, name="s"),
             R.Box(x=80, y=80, w=5, h=60, name="w"),
             R.Box(x=135, y=80, w=5, h=60, name="e")]
    rec = DebugRecorder()
    with record_into(rec):
        plan = R.plan_path(R.Endpoint(src, "right", tap=12),
                           R.Endpoint(dst, "top", tap=12),
                           anchors=[src, dst, *walls],
                           bounds=R.Box(x=-10, y=-10, w=160, h=160))
    assert len(plan.waypoints) >= 2
    assert any("left scope bounds" in n for n in rec.notes)


def test_router_constants_are_policy_fields():
    """The pad-free parallel floor and the widest gutter still counted
    as a channel are CrossPolicy fields whose defaults are the old
    module constants."""
    assert R.DEFAULT_POLICY.parallel_floor == R._PARALLEL_FLOOR == 1.5
    assert R.DEFAULT_POLICY.max_channel == R._MAX_CHANNEL == 160.0


def test_stacked_return_lanes_are_unchanged_by_the_bound(monkeypatch):
    """Feedback wires around one row stack their lanes outside the cards:
    a later lane lies beyond an earlier one, and the scope bound (which
    grows with every drawn wire) keeps every detour exactly as the
    unbounded planner draws it."""
    def body():
        return Column(
            Row(Anchor("a", Card("first stage")),
                Anchor("b", Card("second stage")),
                Anchor("c", Card("third stage")), gap="lg"),
            Connect("c", "a", src_side="bottom", dst_side="bottom",
                    label="retune"),
            Connect("c", "b", src_side="bottom", dst_side="bottom"),
            Connect("b", "a", src_side="top", dst_side="top"),
            Connect("c", "a", src_side="top", dst_side="top"),
            gap="md")
    bounded = Diagram.for_paper(body()).render()
    import sciviz.composition._flow as flow_mod
    monkeypatch.setattr(flow_mod, "_scope_bounds", lambda *a, **k: None)
    unbounded = Diagram.for_paper(body()).render()
    assert bounded == unbounded


def test_tight_gutter_stubs_meet_without_a_spur():
    """Two faces across a gutter shorter than both taps: the stubs meet
    on one line (a clean Z, monotone along the flow), and the arrowhead
    stub keeps its visible floor while the gutter allows it."""
    from dataclasses import replace
    policy = replace(R.DEFAULT_POLICY, min_clearance=8.0, head_len=5.0)
    floor = policy.min_tap + policy.head_len
    for gutter in (2 * floor, 1.5 * floor, floor, 0.75 * floor):
        top = [R.Box(x=i * 110, y=0, w=100, h=40, name=f"t{i}")
               for i in range(3)]
        bottom = [R.Box(x=i * 110, y=40 + gutter, w=100, h=40,
                        name=f"b{i}") for i in range(3)]
        plan = R.plan_path(
            R.Endpoint(top[0], "bottom", tap=12.0),
            R.Endpoint(bottom[0], "top", tap=12.0, tap_fraction=0.3),
            anchors=top + bottom, policy=policy)
        ys = [p[1] for p in plan.waypoints]
        assert ys == sorted(ys), (gutter, plan.waypoints)
        assert plan.style_hint != "fallback"
        last = plan.waypoints[-1][1] - plan.waypoints[-2][1]
        if gutter >= floor + policy.min_tap:
            assert last >= floor - 1e-6, (gutter, plan.waypoints)
