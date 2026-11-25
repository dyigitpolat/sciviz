"""Routed paths never run past a corner and double back.

A same-side U route whose lane is capped by a close obstacle used to keep
its full stubs, run past the lane and fold back up to it, leaving a stub
of ink beyond each corner. The planner now folds such spurs away, and
prefers a lane that keeps each end's stub floor when one exists.
"""
from dataclasses import replace

from sciviz.auto.router import DEFAULT_POLICY, Box, Endpoint, _simplify, plan_path

POLICY = replace(DEFAULT_POLICY, min_clearance=2.0, head_len=4.4)
FLOOR = POLICY.min_tap + POLICY.head_len


def _reversals(points):
    """Collinear triples whose middle point runs past the next one."""
    found = []
    for (ax, ay), (bx, by), (cx, cy) in zip(points, points[1:], points[2:]):
        if abs(ax - bx) < 1e-6 and abs(bx - cx) < 1e-6 \
                and (by - ay) * (cy - by) < 0:
            found.append((bx, by))
        if abs(ay - by) < 1e-6 and abs(by - cy) < 1e-6 \
                and (bx - ax) * (cx - bx) < 0:
            found.append((bx, by))
    return found


def _u_route(obstacle_top):
    left = Box(0, 0, 40, 20, name="left")
    right = Box(160, 0, 40, 20, name="right")
    below = Box(-20, obstacle_top, 240, 10, name="below")
    plan = plan_path(Endpoint(right, "bottom", tap=FLOOR),
                     Endpoint(left, "bottom", tap=FLOOR),
                     anchors=[left, right, below], policy=POLICY)
    return plan.waypoints


def test_u_route_into_a_bottom_side_under_a_close_lane_has_no_spur():
    # The gutter under the boxes is exactly one stub floor deep, so the
    # lane (kept clear of the box below) sits nearer the boxes than the
    # stubs reach.
    points = _u_route(20 + FLOOR)
    assert _reversals(points) == []
    assert len(points) == 4
    (sx, sy), (ax, ay), (bx, by), (dx, dy) = points
    lane = ay
    # down out of the source, one straight run along the lane, up into
    # the target: every leg monotone, nothing below the lane
    assert sx == ax and bx == dx and ay == by
    assert sy < lane and dy < lane
    assert max(y for _x, y in points) == lane
    assert 20 < lane < 20 + FLOOR


def test_u_route_keeps_the_stub_floor_when_the_gutter_allows_it():
    points = _u_route(20 + 3 * FLOOR)
    assert _reversals(points) == []
    lane = points[1][1]
    assert lane - 20 >= FLOOR - 1e-6


def test_simplify_folds_a_spur_past_a_corner():
    # the stub runs to 20 and doubles back to the lane at 10
    assert _simplify([(0, 0), (0, 20), (0, 10), (30, 10)], 0.5) == [
        (0, 0), (0, 10), (30, 10)]
    # the same at the far end: past the lane, then back up into the target
    assert _simplify([(30, 0), (30, 10), (0, 10), (0, 20), (0, 0)], 0.5) == [
        (30, 0), (30, 10), (0, 10), (0, 0)]
    # a horizontal spur
    assert _simplify([(0, 0), (20, 0), (10, 0), (10, 30)], 0.5) == [
        (0, 0), (10, 0), (10, 30)]


def test_simplify_keeps_a_reversal_behind_the_start():
    # Dropping the turn would start the path into its own box.
    points = [(0, 0), (0, 20), (0, -10), (30, -10)]
    assert _simplify(points, 0.5) == points


def test_simplify_sets_a_leg_square_after_merging_near_duplicates():
    # Two stubs ending a hair apart (under the tolerance) meet on a lane;
    # merging the near-duplicate corner must not leave a slanted lane.
    points = [(100, 0), (100, 10.0), (100, 10.3), (0, 10.3), (0, 10.4),
              (0, 20)]
    out = _simplify(points, 0.5)
    for (ax, ay), (bx, by) in zip(out, out[1:]):
        assert ax == bx or ay == by, out
    assert out[0] == (100, 0) and out[-1] == (0, 20)
    assert len(out) == 4
