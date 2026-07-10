"""Endpoint taps escape nested routing regions before turning."""

from sciviz.auto.router import Box, Endpoint, _simplify, plan_path


def test_same_side_route_escapes_distinct_outer_regions():
    source = Box(40, 40, 20, 20, name="source")
    target = Box(240, 40, 20, 20, name="target")
    source_panel = Box(10, 10, 90, 90, name="source-panel", kind="region")
    target_panel = Box(210, 10, 90, 110, name="target-panel", kind="region")

    plan = plan_path(
        Endpoint(source, "bottom", tap=8),
        Endpoint(target, "bottom", tap=8),
        anchors=[source, target],
        regions=[source_panel, target_panel],
    )

    assert plan.waypoints[1][1] > source_panel.bottom
    assert plan.waypoints[-2][1] > target_panel.bottom


def test_shared_outer_region_is_not_needlessly_escaped():
    source = Box(40, 40, 20, 20, name="source")
    target = Box(40, 140, 20, 20, name="target")
    outer = Box(0, 0, 120, 220, name="outer", kind="region")
    source_panel = Box(10, 10, 90, 70, name="source-panel", kind="region")
    target_panel = Box(10, 120, 90, 70, name="target-panel", kind="region")

    plan = plan_path(
        Endpoint(source, "bottom", tap=8),
        Endpoint(target, "top", tap=8),
        anchors=[source, target],
        regions=[outer, source_panel, target_panel],
    )

    assert max(y for _x, y in plan.waypoints) < outer.bottom


def test_simplification_preserves_endpoint_escape_uturn():
    points = [(0, 0), (0, 20), (0, 10), (30, 10)]
    assert _simplify(points, 0.5) == points
