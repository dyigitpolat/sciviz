from __future__ import annotations

from sciviz.auto.router import Box, Endpoint, plan_path


def test_outside_to_inside_mixed_side_route_does_not_exit_and_reenter_region():
    source = Box(0, 180, 60, 40, name="source")
    sink = Box(150, 80, 100, 50, name="sink")
    workflow = Box(100, 20, 300, 260, name="workflow", kind="region")

    plan = plan_path(
        Endpoint(source, "right", tap=12),
        Endpoint(sink, "bottom", tap=12),
        anchors=(source, sink),
        regions=(workflow,),
    )

    # The source crosses the left workflow boundary on its way to the sink;
    # the sink's bottom stub must not first escape through y=280 and U-turn.
    assert max(y for _x, y in plan.waypoints) <= source.cy + 12
    for a, b, c in zip(plan.waypoints, plan.waypoints[1:], plan.waypoints[2:]):
        if abs(a[0] - b[0]) < 0.5 and abs(b[0] - c[0]) < 0.5:
            assert (b[1] - a[1]) * (c[1] - b[1]) >= 0
