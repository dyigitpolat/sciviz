"""Tests for :class:`sciviz.Tree`."""

from __future__ import annotations

import pytest

from sciviz import Box, Canvas, DEFAULT_THEME, Text, Tree, TreeNode


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


def test_tree_per_edge_dashed_style():
    t = Tree(Tree.node(Text("r"), children=[
        (Tree.node(Box("a")), {"style": "dashed"}),
    ]))
    c = Canvas()
    t.render(c, 0, 0, DEFAULT_THEME)
    assert 'stroke-dasharray="4,3"' in c.to_svg(400, 400)


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
