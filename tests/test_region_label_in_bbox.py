"""`Region` must publish its FULL footprint -- border rectangle *plus*
the label strip above it -- so connector routers don't send paths
through the region's label.
"""
from sciviz import (
    Anchor,
    Box,
    Diagram,
    Region,
    Row,
    Spacer,
)
from sciviz.composition import _anchor_stack


def test_region_bbox_includes_label_strip():
    # A labelled region should publish a bbox whose top edge is ABOVE
    # the border (in the label strip) rather than flush with the
    # border line.  Otherwise, orthogonal routers will happily drop
    # path segments across the label text.
    capture: dict = {}
    token = _anchor_stack.set([capture])
    try:
        body = Region(
            Row(
                Anchor("a", Box("A", width=40, height=24)),
                Spacer(16, 0),
                Anchor("b", Box("B", width=40, height=24)),
            ),
            label="My Region",
        )
        d = Diagram(body=body)
        d.render()
    finally:
        _anchor_stack.reset(token)

    region_keys = [k for k in capture if k.startswith("__region_")]
    assert region_keys, "expected __region_* entry from Region"
    rx, ry, rw, rh = capture[region_keys[0]]

    # The first anchor's top edge should sit comfortably BELOW the
    # region's registered top edge -- i.e. there must be enough
    # headroom above the anchor row to have contained the label.
    a_top = capture["a"][1]
    assert a_top - ry >= 6.0, (
        "region top edge must be above the first child by at least a "
        "few pixels of label-strip clearance; got "
        f"ry={ry}, a_top={a_top}"
    )


def test_unlabeled_region_bbox_is_tight_to_border():
    # Unlabelled regions should NOT reserve a phantom label strip at
    # the top; the registered rect should hug the border.
    capture: dict = {}
    token = _anchor_stack.set([capture])
    try:
        body = Region(
            Row(
                Anchor("a", Box("A", width=40, height=24)),
                Spacer(16, 0),
                Anchor("b", Box("B", width=40, height=24)),
            ),
            label=None,
        )
        d = Diagram(body=body)
        d.render()
    finally:
        _anchor_stack.reset(token)

    region_keys = [k for k in capture if k.startswith("__region_")]
    rx, ry, rw, rh = capture[region_keys[0]]
    a_top = capture["a"][1]
    assert a_top - ry < 18.0, (
        "unlabelled region should not leave extra vertical padding "
        f"for a label; ry={ry}, a_top={a_top}"
    )
