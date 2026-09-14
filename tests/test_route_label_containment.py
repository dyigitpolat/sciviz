"""Caption-driven routing stays proportionate, and labels stay inside
their containing region.

Two invariants born from composing framed panels:

* A labeled wire may take a modest detour to host its caption, never a
  runaway sweep (``CrossPolicy.label_detour_ratio`` bounds it against
  the label-free route; the label placer's halo is the fallback).
* A wire whose endpoints live inside a registered ``__region_*`` (e.g.
  a Panel frame) keeps its caption inside that region.
"""
from __future__ import annotations


def _path_len(points):
    total = 0.0
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def test_labeled_route_between_tight_stacked_cards_does_not_run_away():
    from sciviz.auto.router import Box, Endpoint, plan_path

    # Two stacked cards with an 18-px gap: far too short to host a
    # 70-px caption on any arm, so an unbounded caption search would
    # abandon the direct drop and sweep around the cards.
    src = Box(x=0.0, y=0.0, w=120.0, h=30.0, name="src", kind="anchor")
    dst = Box(x=0.0, y=48.0, w=120.0, h=30.0, name="dst", kind="anchor")
    label_gap = 6.0

    free = plan_path(
        Endpoint(src, "bottom", tap=4.0), Endpoint(dst, "top", tap=4.0),
        anchors=[src, dst], label_extent=None, label_gap=label_gap)
    labeled = plan_path(
        Endpoint(src, "bottom", tap=4.0), Endpoint(dst, "top", tap=4.0),
        anchors=[src, dst], label_extent=(70.0, 12.0),
        label_gap=label_gap, label_rotatable=False)

    free_len = _path_len(free.waypoints)
    labeled_len = _path_len(labeled.waypoints)
    # The detour bound: ratio * label-free length + 4 * label_gap slack.
    assert labeled_len <= 2.0 * free_len + 4.0 * label_gap + 1e-6, (
        f"caption search ran away: {labeled_len:.1f}px vs "
        f"label-free {free_len:.1f}px")


def test_place_polyline_label_respects_bounds():
    from sciviz.auto.labels import LabelBox, place_polyline_label

    # A vertical wire hugging the left edge of its containing region,
    # walled off on the right: the only offset home is OUTSIDE the
    # region. With bounds, the placer must refuse it and fall back to
    # an in-bounds placement (the on-wire halo).
    label = LabelBox(text="next candidate", width=80.0, height=12.0,
                     size_px=8.0)
    points = [(10.0, 10.0), (10.0, 110.0)]
    wall = [(16.0, 0.0, 300.0, 120.0)]
    bounds = (4.0, 0.0, 300.0, 120.0)

    escaped = place_polyline_label(points, label, wall, gap=6.0)
    assert escaped.rect[0] < bounds[0] - 0.5, (
        "control setup no longer escapes; adjust the scenario")

    contained = place_polyline_label(points, label, wall, gap=6.0,
                                     bounds=bounds)
    x0, y0, x1, y1 = contained.rect
    assert x0 >= bounds[0] - 0.5 and y0 >= bounds[1] - 0.5, contained.rect
    assert x1 <= bounds[2] + 0.5 and y1 <= bounds[3] + 0.5, contained.rect


def test_containment_bounds_picks_innermost_region():
    from sciviz.composition._flow import Flow

    registry = {
        "__region_outer": (0.0, 0.0, 400.0, 400.0),
        "__region_inner": (50.0, 50.0, 200.0, 200.0),
        "src": (60.0, 60.0, 10.0, 10.0),
        "dst": (100.0, 200.0, 20.0, 20.0),
    }
    bounds = Flow._containment_bounds(
        registry, registry["src"], registry["dst"])
    assert bounds == (50.0, 50.0, 250.0, 250.0)

    # An endpoint outside the inner region falls back to the outer one.
    bounds = Flow._containment_bounds(
        registry, registry["src"], (300.0, 300.0, 20.0, 20.0))
    assert bounds == (0.0, 0.0, 400.0, 400.0)

    # No containing region at all -> unbounded.
    assert Flow._containment_bounds(
        registry, registry["src"], (500.0, 10.0, 20.0, 20.0)) is None
