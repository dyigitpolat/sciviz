from __future__ import annotations

import pytest

from sciviz import Column, Diagram, Text, Theme
from sciviz.connect._resolver import _FlowResolver
from sciviz.graphs._flow_graph import (
    FlowEdge, FlowGraph, FlowGroup, FlowNode, FlowPort, FlowRef, _FlowShape,
)


def test_longest_path_ranks_and_independent_edges():
    graph = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B"), FlowNode("c", "C")],
        [FlowEdge("a", "c"), FlowEdge("b", "c")],
    )
    assert graph.rank_for("a") == graph.rank_for("b") == 0
    assert graph.rank_for("c") == 1
    assert [connector.mode for connector in graph._connectors] == ["routed", "routed"]
    assert "<svg" in Diagram.for_paper(graph).render()


def test_sequence_endpoint_explicitly_creates_bus():
    graph = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B"), FlowNode("c", "C")],
        [FlowEdge(["a", "b"], "c", label="merge")],
    )
    assert graph._connectors[0].mode == "bus"


def test_downward_graph_owns_perpendicular_faces_and_bus_orientation():
    graph = FlowGraph(
        [
            FlowNode("source", "Source", rank="source"),
            FlowNode("left", "Left", rank="workers"),
            FlowNode("right", "Right", rank="workers"),
        ],
        [FlowEdge("source", ["left", "right"])],
        direction="down",
        rank_order=("source", "workers"),
    )
    bus = graph._connectors[0]._impl._bus
    assert bus.orientation == "vertical"

    serial = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B")],
        [FlowEdge("a", "b")],
        direction="down",
    )
    flow = serial._connectors[0]._impl._flow
    assert (flow.src_side, flow.dst_side) == ("bottom", "top")


@pytest.mark.parametrize("direction", ["down", "right"])
def test_ranked_forward_edges_do_not_double_charge_endpoint_margins(direction):
    graph = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B"), FlowNode("c", "C")],
        [FlowEdge("a", "b"), FlowEdge("b", "c")],
        direction=direction,
    )
    before = graph.measure(Theme())
    after = _FlowResolver(graph).measure(Theme())

    if direction == "down":
        assert after.h == before.h
    else:
        assert after.w == before.w


def test_unlabelled_rank_corridor_is_larger_than_arrowhead():
    graph = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B")],
        [FlowEdge("a", "b")],
        direction="down",
    )
    ranked = graph.child.children[0].child
    assert Theme().gap_px(ranked.gap) > Theme().arrow_size


def test_rank_local_flow_shapes_equalise_worker_heights_only():
    graph = FlowGraph(
        [
            FlowNode("short", "A", rank="workers"),
            FlowNode(
                "tall",
                Column(Text("Line one"), Text("Line two"), gap="xs"),
                shape="process",
                rank="workers",
            ),
            FlowNode("later", "A much wider later process", rank="later"),
        ],
        [],
        direction="down",
        rank_order=("workers", "later"),
    )
    graph.measure(Theme())
    worker_band, later_band = graph.child.children[0].child.children
    worker_shapes = [anchor.child.child for anchor in worker_band.children]
    assert worker_shapes[0].measure(Theme()).h == worker_shapes[1].measure(Theme()).h
    assert worker_shapes[0].measure(Theme()).w == worker_shapes[1].measure(Theme()).w
    later_shape = later_band.children[0].child.child
    assert later_shape.measure(Theme()).w > worker_shapes[0].measure(Theme()).w


def test_long_decision_labels_keep_a_legible_diamond_aspect():
    shape = _FlowShape(
        Text("Assign this graph to an automatically selected worker rank"),
        "decision",
        "warning",
        peer_key="decision",
    )
    size = shape.measure(Theme())
    assert size.w / size.h <= 2.0


def test_feedback_is_excluded_from_cycle_detection():
    graph = FlowGraph(
        [FlowNode("a", "A"), FlowNode("b", "B")],
        [FlowEdge("a", "b"), FlowEdge("b", "a", kind="feedback")],
    )
    assert graph.rank_for("a") == 0
    assert graph.rank_for("b") == 1
    assert "<svg" in Diagram.for_paper(graph).render()


def test_port_validation_and_markers():
    graph = FlowGraph(
        [FlowNode("source", "Source", ports=(FlowPort("data", "right", "triangle"),)),
         FlowNode("sink", "Sink", ports=(FlowPort("in", "left", "circle"),))],
        [FlowEdge(FlowRef("source", "data"), FlowRef("sink", "in"))],
    )
    svg = Diagram.for_paper(graph).render()
    assert "<polygon" in svg
    assert "<circle" in svg
    with pytest.raises(ValueError, match="unknown port"):
        FlowGraph(graph.nodes, [FlowEdge(FlowRef("source", "missing"), "sink")])


@pytest.mark.parametrize("shape, needle", [
    ("decision", "<polygon"),
    ("store", " C "),
    ("document", "<path"),
    ("terminator", "<rect"),
])
def test_flowchart_shapes_render(shape, needle):
    svg = Diagram.for_paper(FlowGraph([FlowNode("n", "node", shape=shape)], [])).render()
    assert needle in svg


def test_group_validation_and_bounds():
    graph = FlowGraph(
        [FlowNode("a", "A", group="g"), FlowNode("b", "B", group="g")],
        [FlowEdge("a", "b")],
        groups=[FlowGroup("g", label="group")],
    )
    svg = Diagram.for_paper(graph).render()
    assert "group" in svg
    assert "stroke-dasharray" in svg
    with pytest.raises(ValueError, match="unknown group"):
        FlowGraph([FlowNode("x", "X", group="missing")], [])


def test_unknown_nodes_and_forward_cycles_fail_eagerly():
    with pytest.raises(ValueError, match="unknown node"):
        FlowGraph([FlowNode("a", "A")], [FlowEdge("a", "missing")])
    with pytest.raises(ValueError, match="acyclic"):
        FlowGraph(
            [FlowNode("a", "A"), FlowNode("b", "B")],
            [FlowEdge("a", "b"), FlowEdge("b", "a")],
        )
