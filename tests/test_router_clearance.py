"""Obstacle clearance and wire separation in the topological router.

Routed wires keep ``policy.min_clearance`` of breathing room from every
obstacle that is not one of their own endpoints.  When a corridor is too
narrow for the full margin the planner degrades it gradually (half,
quarter, zero) instead of collapsing straight to an edge-grazing route,
and wires never ride co-linearly on top of an already-drawn wire while
a lane shift can avoid it.
"""
from __future__ import annotations

from sciviz.auto.router import (
    Box, CrossPolicy, Endpoint, plan_path, _parallel_overlap_len,
)


def _seg_box_dist(x1, y1, x2, y2, box: Box) -> float:
    sx0, sx1 = min(x1, x2), max(x1, x2)
    sy0, sy1 = min(y1, y2), max(y1, y2)
    dx = max(box.left - sx1, sx0 - box.right, 0.0)
    dy = max(box.top - sy1, sy0 - box.bottom, 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _min_dist_to(plan, box: Box) -> float:
    wps = plan.waypoints
    return min(
        _seg_box_dist(wps[i][0], wps[i][1], wps[i + 1][0], wps[i + 1][1], box)
        for i in range(len(wps) - 1)
    )


def test_route_keeps_min_clearance_from_bystander():
    """A staircase route through open space stays >= min_clearance away
    from an unrelated obstacle near the natural midline."""
    src = Box(0, 0, 40, 20, name="src")
    dst = Box(160, 100, 40, 20, name="dst")
    bystander = Box(90, 30, 30, 60, name="obs")
    policy = CrossPolicy(min_clearance=10.0)
    plan = plan_path(
        Endpoint(src, "right"), Endpoint(dst, "left"),
        anchors=[src, dst, bystander], policy=policy,
    )
    assert _min_dist_to(plan, bystander) >= policy.min_clearance - 0.5


def test_narrow_corridor_degrades_clearance_gradually():
    """When the only corridor is too narrow for the full margin, the
    route still keeps the largest feasible fraction (not zero)."""
    src = Box(0, 0, 40, 20, name="src")
    dst = Box(0, 200, 40, 20, name="dst")
    # Two walls leave a 14px corridor; full clearance 10 would need
    # 20px+wire, half clearance (5) fits.
    wall_a = Box(60, -40, 40, 300, name="wall_a")
    wall_b = Box(-94, -40, 40, 300, name="wall_b")
    policy = CrossPolicy(min_clearance=10.0)
    plan = plan_path(
        Endpoint(src, "left"), Endpoint(dst, "left"),
        anchors=[src, dst, wall_a, wall_b], policy=policy,
    )
    dist = min(_min_dist_to(plan, wall_a), _min_dist_to(plan, wall_b))
    assert dist >= 4.0, (dist, plan.waypoints)


def test_second_wire_shifts_lane_instead_of_riding_first():
    """A second wire whose natural lane coincides with an existing
    vertical run shifts sideways rather than overlapping co-linearly."""
    src_a = Box(0, 0, 40, 20, name="a")
    src_b = Box(0, 80, 40, 20, name="b")
    dst = Box(200, 40, 40, 20, name="dst")
    anchors = [src_a, src_b, dst]
    policy = CrossPolicy(min_clearance=6.0)
    first = plan_path(Endpoint(src_a, "right"), Endpoint(dst, "left"),
                      anchors=anchors, policy=policy)
    segs = [(*first.waypoints[i], *first.waypoints[i + 1])
            for i in range(len(first.waypoints) - 1)]
    second = plan_path(Endpoint(src_b, "right"), Endpoint(dst, "left"),
                       anchors=anchors, existing_segments=segs,
                       policy=policy)
    overlap = _parallel_overlap_len(second.waypoints, segs, 3.0, 0.5)
    assert overlap <= 2.0, (overlap, first.waypoints, second.waypoints)


def test_parallel_overlap_len_counts_colinear_not_crossings():
    path = [(0.0, 0.0), (0.0, 100.0)]
    riding = [(1.0, 10.0, 1.0, 60.0)]    # parallel, 1px away, 50 shared
    crossing = [(-20.0, 50.0, 20.0, 50.0)]  # perpendicular crossing
    assert _parallel_overlap_len(path, riding, 3.0, 0.5) == 50.0
    assert _parallel_overlap_len(path, crossing, 3.0, 0.5) == 0.0


def test_flow_clearance_defaults_to_theme_proportional():
    from sciviz import DEFAULT_THEME
    from sciviz.composition import Flow

    flow = Flow("a", "b")
    assert abs(flow._clearance_px(DEFAULT_THEME)
               - DEFAULT_THEME.unit * 4.0 / 3.0) < 1e-9
    compressed = DEFAULT_THEME.with_overrides(unit=3.0)
    assert abs(flow._clearance_px(compressed) - 4.0) < 1e-9
    pinned = Flow("a", "b", clearance=11.0)
    assert pinned._clearance_px(DEFAULT_THEME) == 11.0
