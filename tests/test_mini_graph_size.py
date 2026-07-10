"""MiniGraph semantic sizes keep thumbnail geometry theme-relative."""

from __future__ import annotations

import pytest

from sciviz import MiniGraph, Theme


def test_mini_graph_semantic_size_scales_both_axes():
    nodes = [(0.1, 0.1), (0.9, 0.9)]
    edges = [(0, 1)]
    small = MiniGraph(nodes, edges, size="sm").measure(Theme())
    large = MiniGraph(nodes, edges, size="xl").measure(Theme())
    assert large.w > small.w and large.h > small.h


def test_mini_graph_explicit_dimensions_override_semantic_defaults():
    graph = MiniGraph([(0.5, 0.5)], [], size="xl", width=77, height=55)
    measured = graph.measure(Theme())
    assert measured.w == 77 and measured.h == 55


def test_mini_graph_rejects_unknown_size():
    with pytest.raises(ValueError):
        MiniGraph([(0.5, 0.5)], [], size="enormous")


def test_mini_graph_filled_mode_uses_role_ink_for_nodes():
    from sciviz import Canvas

    theme = Theme()
    graph = MiniGraph([(0.5, 0.5)], [], role="positive", filled=True)
    canvas = Canvas()
    graph.render(canvas, 0, 0, theme)
    assert f'fill="{theme.color_of("positive")}"' in canvas.to_svg(100, 100)
