"""Rows align tall systems while centring compact bridge accessories."""

from sciviz import Banner, Box, Row, Text, Theme


def test_center_row_top_aligns_tall_structures_around_compact_bridge():
    theme = Theme()
    left = Banner(
        Box("left", width=80, height=100, shape_key=""),
        above=Text("Left system"),
    )
    bridge = Box("NIC", width=30, height=30, shape_key="")
    right = Banner(
        Box("right", width=80, height=90, shape_key=""),
        above=Text("Right system"),
    )
    row = Row(left, bridge, right, align="center")

    offsets = row._child_offsets(theme)
    content = [child.content_bbox(theme) for child in row.children]
    content_tops = [offset[1] + cb[1] for offset, cb in zip(offsets, content)]

    assert content_tops[0] == content_tops[2]
    assert content_tops[1] > content_tops[0]


def test_two_peer_row_keeps_ordinary_center_alignment():
    theme = Theme()
    first = Box("a", width=30, height=100, shape_key="")
    second = Box("b", width=30, height=40, shape_key="")
    row = Row(first, second, align="center")
    offsets = row._child_offsets(theme)

    assert offsets[1][1] > offsets[0][1]
