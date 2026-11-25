"""Wires run in the middle of their gutter.

A Z bridge between a band and a row of cards takes the gutter's centre
line (its stubs may shorten to their visible floor to reach it), a second
wire sharing the gutter takes an even track instead of the lane beside a
wall, and no two wires ride on one line even in a narrow gutter.
"""
from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Region, Row, Text
from sciviz.core._routing_context import routing_registry_stack
import sciviz.auto.router as R


@pytest.fixture
def routes(monkeypatch):
    out = []
    orig = R.render_orthogonal

    def spy(canvas, plan, **kw):
        out.append(list(plan.waypoints))
        return orig(canvas, plan, **kw)

    import sciviz.routing as RT
    monkeypatch.setattr(R, "render_orthogonal", spy)
    monkeypatch.setattr(RT, "render_orthogonal", spy)
    return out


def _scene(gap, wires):
    band = Anchor("band", Region(Row(*[Anchor(f"s{i}", Box(f"stripe {i}"))
                                       for i in (1, 2, 3)], gap="sm"),
                                 fill="white"))
    cards = Row(*[Anchor(f"c{i}", Region(Column(Text(f"Card {i}", weight="700"),
                                                Box("body")), fill="white"))
                  for i in range(4)], gap=gap)
    body = Column(band, cards,
                  *[Connect(a, b, src_side="bottom", dst_side="top")
                    for a, b in wires], gap=gap)
    reg: dict = {}
    token = routing_registry_stack.set([reg])
    try:
        Diagram.for_paper(body).render()
    finally:
        routing_registry_stack.reset(token)
    band_bottom = reg["band"][1] + reg["band"][3]
    cards_top = min(reg[f"c{i}"][1] for i in range(4))
    return band_bottom, cards_top


def _bridge_y(path):
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        if abs(y1 - y2) < 0.5 and abs(x1 - x2) > 20:
            return y1
    raise AssertionError(path)


def test_single_wire_takes_the_gutter_centre(routes):
    lo, hi = _scene("md", [("s1", "c3")])
    (path,) = routes[-1:]
    assert abs(_bridge_y(path) - (lo + hi) / 2) < 0.5


def test_second_wire_takes_an_even_track_not_a_wall(routes):
    lo, hi = _scene("md", [("s1", "c3"), ("s3", "c0")])
    a, b = routes[-2:]
    ya, yb = _bridge_y(a), _bridge_y(b)
    width = hi - lo
    assert abs(ya - (lo + hi) / 2) < 0.5
    assert abs(yb - ya) >= width / 6 - 0.5         # a separate track
    for y in (ya, yb):                             # clear of both walls
        assert lo + width / 4 - 0.5 <= y <= hi - width / 4 + 0.5


def test_narrow_gutter_never_merges_two_wires(routes):
    _scene("xs", [("s1", "c3"), ("s3", "c0")])
    a, b = routes[-2:]
    segs = [(p[0], p[1], q[0], q[1]) for p, q in zip(a, a[1:])]
    assert R._parallel_overlap_len(b, segs, 1.0, 0.5) <= 2.0


def test_open_side_is_not_a_channel():
    # A wall on one side only (open space on the other) is not centred on.
    wall = R.Box(x=0, y=0, w=100, h=10, name="w", kind="anchor")
    assert R._channel(40.0, (30.0, 50.0), 0.0, 100.0, [wall], "y", 0.5) is None
    far = R.Box(x=0, y=60, w=100, h=10, name="f", kind="anchor")
    assert R._channel(40.0, (30.0, 50.0), 0.0, 100.0, [wall, far], "y",
                      0.5) == (10, 60)
