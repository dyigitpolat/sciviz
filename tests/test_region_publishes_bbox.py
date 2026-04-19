"""`Region` and `BlockGroup` must publish their border rectangle to the
anchor registry under a `__region_*` key so connector routers can see
them as logical boundaries.
"""
from sciviz import (Anchor, Box, BlockGroup, Diagram, Region, Row, Spacer)
from sciviz.composition import Flow, Flowed
from sciviz.composition import _anchor_stack


def test_region_registers_bbox_on_stack():
    # Build a tree with a Region containing one Anchor; install a
    # capturing registry on the stack, render once, and check that
    # the region's bbox appears under `__region_*`.
    capture: dict = {}
    token = _anchor_stack.set([capture])
    try:
        body = Region(
            Row(
                Anchor("a", Box("A", width=40, height=24)),
                Spacer(20, 0),
                Anchor("b", Box("B", width=40, height=24)),
            ),
            label="R",
        )
        d = Diagram(body=body)
        d.render()
    finally:
        _anchor_stack.reset(token)

    region_keys = [k for k in capture if k.startswith("__region_")]
    assert region_keys, "expected at least one __region_* entry from Region"
    rx, ry, rw, rh = capture[region_keys[0]]
    # Region must encompass both named anchors.
    a = capture["a"]
    b = capture["b"]
    assert rx <= min(a[0], b[0])
    assert rx + rw >= max(a[0] + a[2], b[0] + b[2])
    assert ry <= min(a[1], b[1])
    assert ry + rh >= max(a[1] + a[3], b[1] + b[3])


def test_blockgroup_registers_bbox_on_stack():
    capture: dict = {}
    token = _anchor_stack.set([capture])
    try:
        body = BlockGroup(
            Row(
                Anchor("p", Box("P", width=40, height=24)),
                Spacer(16, 0),
                Anchor("q", Box("Q", width=40, height=24)),
            ),
            label="BG",
        )
        d = Diagram(body=body)
        d.render()
    finally:
        _anchor_stack.reset(token)
    region_keys = [k for k in capture if k.startswith("__region_")]
    assert region_keys, "expected __region_* entry from BlockGroup"
    rx, ry, rw, rh = capture[region_keys[0]]
    p = capture["p"]
    q = capture["q"]
    assert rx <= min(p[0], q[0])
    assert rx + rw >= max(p[0] + p[2], q[0] + q[2])
