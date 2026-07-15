"""Tests for :class:`sciviz.Tree`."""

from __future__ import annotations

import pytest

from sciviz import Box, Canvas, Captioned, DEFAULT_THEME, Text, Tree, TreeNode


def _simple_tree():
    return Tree.node(
        Text("root"),
        children=[
            Tree.node(Box("A")),
            Tree.node(Box("B")),
        ],
    )


def test_tree_node_constructor_coerces_children():
    node = Tree.node(Box("r"), children=[Tree.node(Box("a"))])
    assert isinstance(node, TreeNode)
    assert len(node.children) == 1
    assert node.children[0][1] == {}


def test_tree_measures_positive():
    t = Tree(_simple_tree())
    b = t.measure(DEFAULT_THEME)
    assert b.w > 0 and b.h > 0


def test_tree_height_increases_with_depth():
    shallow = Tree(Tree.node(Box("r"), children=[Tree.node(Box("a"))]))
    deeper = Tree(
        Tree.node(Box("r"), children=[
            Tree.node(Box("a"), children=[Tree.node(Box("x"))]),
        ]))
    assert deeper.measure(DEFAULT_THEME).h > shallow.measure(DEFAULT_THEME).h


def test_tree_renders_nodes_and_edges():
    t = Tree(_simple_tree())
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    assert "root" in svg
    assert "A" in svg and "B" in svg
    # Two edges out of root.
    assert svg.count("<line ") >= 2


def test_tree_per_edge_color_styles_line():
    t = Tree(Tree.node(Text("r"), children=[
        (Tree.node(Box("a")), {"color": "green"}),
        (Tree.node(Box("b")), {"color": "red"}),
    ]))
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    assert f'stroke="{DEFAULT_THEME.color_of("green")}"' in svg
    assert f'stroke="{DEFAULT_THEME.color_of("red")}"' in svg
    assert f'stroke-width="{DEFAULT_THEME.thick:.2f}"' in svg


def test_tree_per_edge_dashed_style():
    t = Tree(Tree.node(Text("r"), children=[
        (Tree.node(Box("a")), {"style": "dashed"}),
    ]))
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    assert 'stroke-dasharray="4,3"' in c.to_svg(400, 400)


def test_tree_edge_width_accepts_theme_token():
    tree = Tree(Tree.node(Text("r"), children=[
        (Tree.node(Box("a")), {"width": "hairline"}),
    ]))
    canvas = Canvas()
    tree.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    assert f'stroke-width="{DEFAULT_THEME.hairline:.2f}"' in \
        canvas.to_svg(200, 200)


def test_tree_per_edge_label():
    t = Tree(Tree.node(Text("r"), children=[
        (Tree.node(Box("a")), {"label": "hit"}),
        (Tree.node(Box("b")), {"label": "miss"}),
    ]))
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    assert "hit" in svg and "miss" in svg


def test_tree_rejects_bad_child_type():
    with pytest.raises(TypeError):
        Tree.node(Box("r"), children=["not a node"])


def test_tree_leaf_only():
    t = Tree(Tree.node(Box("solo")))
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(80, 80)
    assert "solo" in svg
    # No edges out of a leaf root.
    assert svg.count("<line ") == 0


def test_tree_level_label_draws_measured_rank_band():
    tree = Tree(
        Tree.node(Box("root"), children=[
            Tree.node(Box("left")),
            Tree.node(Box("right")),
        ]),
        level_labels={1: "LUT"},
    )
    size = tree.measure(DEFAULT_THEME)
    canvas = Canvas()
    tree.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(size.w, size.h)

    assert ">LUT<" in svg
    assert 'stroke-dasharray="4,3"' in svg


def test_tree_rejects_bad_orientation():
    with pytest.raises(ValueError):
        Tree(_simple_tree(), orientation="up")


def test_tree_right_orientation_transposes_bbox():
    """With square nodes and explicit gaps, growing right is the exact
    transpose of growing down."""
    def square_tree():
        return Tree.node(Box("r", width=30, height=30), children=[
            Tree.node(Box("a", width=30, height=30)),
            Tree.node(Box("b", width=30, height=30)),
        ])

    down = Tree(square_tree(), level_gap=10.0, page_gap=6.0)
    right = Tree(square_tree(), orientation="right",
                 level_gap=10.0, page_gap=6.0)
    db = down.measure(DEFAULT_THEME)
    rb = right.measure(DEFAULT_THEME)
    assert (rb.w, rb.h) == (db.h, db.w)


def test_tree_right_orientation_width_increases_with_depth():
    shallow = Tree(Tree.node(Box("r"), children=[Tree.node(Box("a"))]),
                   orientation="right")
    deeper = Tree(
        Tree.node(Box("r"), children=[
            Tree.node(Box("a"), children=[Tree.node(Box("x"))]),
        ]),
        orientation="right")
    assert deeper.measure(DEFAULT_THEME).w > shallow.measure(DEFAULT_THEME).w


def test_tree_right_orientation_edges_run_horizontally():
    t = Tree(
        Tree.node(Box("r", width=40, height=20), children=[
            Tree.node(Box("a", width=40, height=20)),
        ]),
        orientation="right")
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)

    import re
    lines = re.findall(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"',
        svg)
    assert len(lines) == 1
    x1, y1, x2, y2 = (float(v) for v in lines[0])
    assert y1 == y2           # a single child sits level with its parent
    assert x2 > x1            # and the edge advances rightward


def test_tree_right_orientation_level_band():
    tree = Tree(
        Tree.node(Box("root"), children=[
            Tree.node(Box("left")),
            Tree.node(Box("right")),
        ]),
        orientation="right",
        level_labels={1: "children"},
    )
    size = tree.measure(DEFAULT_THEME)
    canvas = Canvas()
    tree.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(size.w, size.h)

    assert ">children<" in svg
    assert 'stroke-dasharray="4,3"' in svg


def test_tree_auto_spacing_resolves_from_theme_density():
    tree = Tree(_simple_tree())
    dense = DEFAULT_THEME.with_overrides(unit=DEFAULT_THEME.unit * 0.5)
    assert tree._level_gap(dense) == tree._level_gap(DEFAULT_THEME) * 0.5
    assert tree._page_gap(dense) == tree._page_gap(DEFAULT_THEME) * 0.5


def test_tree_aligns_decorated_nodes_on_primary_face():
    decorated = Captioned(
        Box("decorated", width=40, height=20),
        decoration=Box("note", width=30, height=18),
        placement="bottom",
        align_on="child",
    )
    tree = Tree(Tree.node(Box("root"), children=[
        Tree.node(Box("plain", width=40, height=20)),
        Tree.node(decorated),
    ]))
    canvas = Canvas()
    size = tree.measure(DEFAULT_THEME)
    tree.render(canvas, 0.0, 0.0, DEFAULT_THEME)

    import re
    rects = re.findall(
        r'<rect x="[-\d.]+" y="([-\d.]+)" width="40" height="20"',
        "".join(canvas._body),
    )
    assert len(rects) == 2
    assert float(rects[0]) == float(rects[1])
