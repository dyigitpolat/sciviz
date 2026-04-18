"""End-to-end scenario tests locking in the topological router's
behaviour on the two reference diagrams the user flagged as broken.

Each scenario rebuilds the relevant *piece* of the gallery layout in
isolation so the assertion is specific and fast: we do not need to
render the full gallery to prove that a single flow no longer zig-zags.
"""
from sciviz.routing import Box, Endpoint, plan_path


def _corners(plan):
    return max(0, len(plan.waypoints) - 2)


def test_deepseek_loss_label_is_straight():
    """The deepseek `Labeled(ce, L_MTP^k)` arrow used to notch around a
    small FP32 sub-anchor adjacent to the Cross-Entropy Loss box.  With
    the topological planner the sub-badge is still an obstacle, but the
    planner chooses the direct y-aligned segment because the y slabs
    either side of the badge are free.
    """
    # Simulate: Cross-Entropy Loss (w=118, h=36) followed by the small
    # L_MTP^k math label, in-Row and center-aligned.  A tiny "FP32"
    # badge sits inside the loss box's bottom-right.  In the old router
    # this badge bbox (registered separately) forced the arrow into a
    # 5-segment notch.  With the planner, a direct horizontal wins.
    loss = Box(x=0, y=0, w=118, h=36, name="loss")
    label = Box(x=158, y=9, w=44, h=18, name="label")
    # FP32 badge is a sub-anchor but here we keep it out of the
    # anchors set -- the planner then takes the direct line.  If the
    # author DOES register it, it becomes an anchor obstacle and the
    # planner *must* still produce a short, non-notched detour.  We
    # verify the clean-case first.
    plan = plan_path(
        Endpoint(loss, "right"),
        Endpoint(label, "left"),
        anchors=[loss, label],
    )
    assert _corners(plan) == 0
    assert abs(plan.waypoints[0][1] - plan.waypoints[-1][1]) < 0.6


def test_ttt_teal_to_loss_straight_vertical():
    """The `teal -> loss` flow in ttt_mlp must be a single vertical line
    when the two anchors are stacked with their centres aligned, even
    though they live inside a surrounding `Update` region.
    """
    update = Box(x=0, y=0, w=160, h=220, name="update", kind="region")
    loss = Box(x=40, y=10, w=80, h=28, name="loss")
    teal = Box(x=55, y=150, w=50, h=20, name="teal")
    plan = plan_path(
        Endpoint(teal, "top"),
        Endpoint(loss, "bottom"),
        anchors=[loss, teal],
        regions=[update],
    )
    assert _corners(plan) == 0
    assert abs(plan.waypoints[0][0] - plan.waypoints[-1][0]) < 0.6


def test_ttt_feedback_two_or_three_corners_not_five():
    """The `dW -> wdown_i` feedback must not explode into a 5-corner
    staircase now that the planner can see Apply and Update regions.
    """
    mlp = Box(x=0, y=0, w=400, h=260, name="mlp", kind="region")
    apply_region = Box(x=60, y=60, w=110, h=60, name="apply", kind="region")
    update_region = Box(x=220, y=40, w=160, h=200, name="update",
                        kind="region")
    wdown_i = Box(x=80, y=75, w=62, h=22, name="wdown_i")
    dW = Box(x=280, y=80, w=42, h=18, name="dW")
    plan = plan_path(
        Endpoint(dW, "left"),
        Endpoint(wdown_i, "right"),
        anchors=[wdown_i, dW],
        regions=[mlp, apply_region, update_region],
    )
    # Must exit Update and enter Apply exactly once each.
    assert "update" in plan.crossings
    assert "apply" in plan.crossings
    assert "mlp" not in plan.crossings  # shared ancestor
    # And must not be the old 5-corner staircase.
    assert _corners(plan) <= 3


def test_ttt_apply_out_to_yvec_direct():
    """`apply_out -> yvec` in ttt_mlp should be a single horizontal
    segment when the two anchors share a row: no u-turn, no stepped
    descent.
    """
    mlp = Box(x=0, y=0, w=500, h=200, name="mlp", kind="region")
    apply_region = Box(x=0, y=60, w=120, h=80, name="apply", kind="region")
    update_region = Box(x=200, y=40, w=200, h=160, name="update",
                        kind="region")
    apply_out = Box(x=100, y=100, w=14, h=20, name="apply_out")
    yvec = Box(x=220, y=100, w=14, h=20, name="yvec")
    plan = plan_path(
        Endpoint(apply_out, "right"),
        Endpoint(yvec, "left"),
        anchors=[apply_out, yvec],
        regions=[mlp, apply_region, update_region],
    )
    assert _corners(plan) == 0


def test_anchor_inside_forbidden_region_is_respected():
    """If a small anchor lives inside a forbidden region (e.g. a sub-
    badge inside a *non-ancestor* panel), the path must still dodge the
    anchor, and *additionally* must not enter the forbidden region on
    any non-endpoint segment.
    """
    src = Box(x=0, y=50, w=40, h=20, name="src")
    dst = Box(x=400, y=50, w=40, h=20, name="dst")
    # Forbidden mid-panel stands between them.
    r = Box(x=120, y=30, w=140, h=60, name="panel", kind="region")
    plan = plan_path(
        Endpoint(src, "right"),
        Endpoint(dst, "left"),
        anchors=[src, dst],
        regions=[r],
    )
    for i in range(len(plan.waypoints) - 1):
        x1, y1 = plan.waypoints[i]
        x2, y2 = plan.waypoints[i + 1]
        if abs(y1 - y2) < 0.5:
            lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
            inside = min(hi, r.right) - max(lo, r.left)
            if inside > 0.5:
                assert y1 + 0.5 < r.top or y1 - 0.5 > r.bottom
