"""Shared-face connector ports project aligned counterparts before routing."""

import pytest

from sciviz.composition import Flow
from sciviz.composition._anchor import _side_point_frac
from sciviz.composition._flow import _assign_edge_shares


def _point(bbox, side, flow, role):
    fraction = getattr(flow, f"_share_{role}_frac")
    return _side_point_frac(bbox, side, fraction)


def test_vertical_fan_in_projects_each_narrow_source_onto_wide_target():
    registry = {
        "link_1": (0.0, 0.0, 20.0, 40.0),
        "link_2": (60.0, 0.0, 20.0, 40.0),
        "router": (0.0, 100.0, 80.0, 60.0),
    }
    flows = [
        Flow("link_1", "router", src_side="bottom", dst_side="top"),
        Flow("link_2", "router", src_side="bottom", dst_side="top"),
    ]

    _assign_edge_shares(flows, registry)

    for flow in flows:
        source = _point(registry[flow.src], "bottom", flow, "src")
        target = _point(registry[flow.dst], "top", flow, "dst")
        assert source[0] == pytest.approx(target[0])


def test_single_memory_link_uses_small_face_centre_on_wide_hbm():
    registry = {
        "memory": (10.0, 0.0, 20.0, 30.0),
        "hbm": (0.0, 80.0, 100.0, 40.0),
    }
    flow = Flow("memory", "hbm", src_side="bottom", dst_side="top")

    _assign_edge_shares([flow], registry)

    source = _point(registry["memory"], "bottom", flow, "src")
    target = _point(registry["hbm"], "top", flow, "dst")
    assert source[0] == pytest.approx(20.0)
    assert target[0] == pytest.approx(20.0)


def test_horizontal_vector_taps_align_to_each_accelerator_centre():
    registry = {
        "vector": (0.0, 0.0, 40.0, 100.0),
        "matrix": (100.0, 10.0, 60.0, 30.0),
        "transpose": (100.0, 60.0, 60.0, 30.0),
    }
    flows = [
        Flow("vector", "matrix", src_side="right", dst_side="left"),
        Flow("vector", "transpose", src_side="right", dst_side="left"),
    ]

    _assign_edge_shares(flows, registry)

    for flow in flows:
        source = _point(registry["vector"], "right", flow, "src")
        target = _point(registry[flow.dst], "left", flow, "dst")
        assert source[1] == pytest.approx(target[1])


def test_coincident_projected_ports_receive_minimum_separation():
    registry = {
        "source_1": (0.0, 0.0, 20.0, 30.0),
        "source_2": (0.0, 0.0, 20.0, 30.0),
        "target": (0.0, 80.0, 60.0, 40.0),
    }
    flows = [
        Flow("source_1", "target", src_side="bottom", dst_side="top"),
        Flow("source_2", "target", src_side="bottom", dst_side="top"),
    ]

    _assign_edge_shares(flows, registry)

    first = _point(registry["target"], "top", flows[0], "dst")
    second = _point(registry["target"], "top", flows[1], "dst")
    assert abs(first[0] - second[0]) >= 6.0 - 1e-6
