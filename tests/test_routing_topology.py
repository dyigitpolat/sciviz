"""Pure-function tests for the topological path planner.

The planner must:

* produce a direct segment when source and destination are collinear and
  no obstacle lies between them;
* produce a single-corner L when the direct route is blocked but one
  axis exit gives a clean path;
* avoid anchor obstacles even when they share a region with one of the
  endpoints;
* cross exactly the region boundaries implied by the two endpoints'
  region ancestry (symmetric difference) and never any other region
  boundary.
"""
from sciviz.routing import (
    Box,
    Endpoint,
    plan_path,
)


def _mkbox(x, y, w, h, name, kind="anchor"):
    return Box(x=x, y=y, w=w, h=h, name=name, kind=kind)


def _corner_count(plan):
    # Corners = interior vertices between 2-point endpoints.
    return max(0, len(plan.waypoints) - 2)


def test_direct_when_collinear_and_clear():
    src = _mkbox(0, 0, 20, 20, "src")
    dst = _mkbox(200, 0, 20, 20, "dst")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[],
    )
    assert _corner_count(plan) == 0
    assert plan.style_hint == "direct"
    assert plan.waypoints[0][1] == plan.waypoints[-1][1]


def test_l_when_axes_perpendicular_and_clear():
    src = _mkbox(0, 0, 20, 20, "src")
    dst = _mkbox(200, 200, 20, 20, "dst")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "top"),
        anchors=[src, dst],
        regions=[],
    )
    assert _corner_count(plan) == 1
    assert plan.style_hint == "L"


def test_anchor_obstacle_forces_detour():
    src = _mkbox(0, 0, 20, 20, "src")
    dst = _mkbox(400, 0, 20, 20, "dst")
    # An anchor sits exactly in the straight-line horizontal corridor.
    obs = _mkbox(180, -10, 40, 40, "obs")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst, obs],
        regions=[],
    )
    # Direct impossible -- we must take at least 2 corners to clear obs.
    assert _corner_count(plan) >= 2
    # Verify no segment overlaps the obstacle interior.
    for i in range(len(plan.waypoints) - 1):
        x1, y1 = plan.waypoints[i]
        x2, y2 = plan.waypoints[i + 1]
        if abs(y1 - y2) < 0.5:
            lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
            if obs.left < lo < obs.right or obs.left < hi < obs.right:
                assert y1 <= obs.top or y1 >= obs.bottom


def test_region_boundary_only_crossed_when_required():
    # src lives INSIDE region r1; dst lives OUTSIDE any region.  The
    # planner must cross exactly r1's boundary, not r2's.
    src = _mkbox(10, 10, 20, 20, "src")
    dst = _mkbox(500, 10, 20, 20, "dst")
    r1 = _mkbox(0, 0, 100, 60, "r1", kind="region")
    r2 = _mkbox(200, 0, 80, 60, "r2", kind="region")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[r1, r2],
    )
    # r1 must be in crossings; r2 must NOT be.
    assert "r1" in plan.crossings
    assert "r2" not in plan.crossings
    # The path cannot enter r2's interior.
    for i in range(len(plan.waypoints) - 1):
        x1, y1 = plan.waypoints[i]
        x2, y2 = plan.waypoints[i + 1]
        if abs(y1 - y2) < 0.5:
            lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
            inside = min(hi, r2.right) - max(lo, r2.left)
            if inside > 0.5:
                assert y1 + 0.5 < r2.top or y1 - 0.5 > r2.bottom


def test_shared_region_not_in_crossings():
    # Both endpoints inside the same region -> no crossings required.
    r = _mkbox(0, 0, 500, 60, "outer", kind="region")
    src = _mkbox(10, 10, 20, 20, "src")
    dst = _mkbox(400, 10, 20, 20, "dst")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[r],
    )
    assert "outer" not in plan.crossings
    assert _corner_count(plan) == 0


def test_nested_regions_exit_inner_only():
    # src is inside BOTH outer and inner; dst is inside outer only.
    # Required crossing: inner (exit).  NOT: outer.
    outer = _mkbox(0, 0, 500, 100, "outer", kind="region")
    inner = _mkbox(0, 20, 120, 60, "inner", kind="region")
    src = _mkbox(30, 40, 20, 20, "src")
    dst = _mkbox(400, 40, 20, 20, "dst")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[outer, inner],
    )
    assert "inner" in plan.crossings
    assert "outer" not in plan.crossings


def test_forbidden_region_forces_detour():
    # Neither endpoint is in region r; the planner must NOT cut through r.
    src = _mkbox(0, 0, 20, 20, "src")
    dst = _mkbox(400, 100, 20, 20, "dst")
    r = _mkbox(100, 40, 150, 40, "r", kind="region")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[r],
    )
    # Some segment passes AROUND r -- verify no horizontal segment
    # traverses r's interior band.
    for i in range(len(plan.waypoints) - 1):
        x1, y1 = plan.waypoints[i]
        x2, y2 = plan.waypoints[i + 1]
        if abs(y1 - y2) < 0.5:
            lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
            if r.top < y1 < r.bottom:
                span = min(hi, r.right) - max(lo, r.left)
                assert span <= 0.5
    assert "r" not in plan.crossings


def test_auto_side_resolves_sensibly():
    src = _mkbox(0, 0, 20, 20, "src")
    dst = _mkbox(200, 0, 20, 20, "dst")
    plan = plan_path(
        Endpoint(src, "auto"),
        Endpoint(dst, "auto"),
        anchors=[src, dst],
    )
    assert plan.resolved_src_side == "right"
    assert plan.resolved_dst_side == "left"
