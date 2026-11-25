"""Sibling captions across a Rhythm gutter.

A ``Rhythm`` lets facing wire ends share one gutter, and
``Connect(label_side=...)`` puts a set of sibling captions on one side.
Together, the captioned wires in a shared gutter still keep their whole
caption corridor, read as one set (one side, one baseline), and stay
inside the drawing.
"""

from __future__ import annotations

import re

import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Rhythm, Row
from sciviz.auto.debug import DebugRecorder, record_into

WORDS = ("sends", "returns", "advises")


def _tiers(gap, side="right"):
    top = Row(*[Anchor(f"t{i}", Box(f"upper {i}")) for i in range(3)],
              gap=Rhythm("md"))
    bottom = Row(*[Anchor(f"b{i}", Box(f"lower {i}")) for i in range(3)],
                 gap=Rhythm("md"))
    wires = [Connect(f"t{i}", f"b{i}", src_side="bottom", dst_side="top",
                     label=word, label_side=side)
             for i, word in enumerate(WORDS)]
    return Column(top, bottom, *wires, gap=gap)


def _render(body):
    d = Diagram.for_paper(body)
    rec = DebugRecorder()
    with record_into(rec):
        svg = d.render()
    return d, svg, rec


def _caption_xy(svg, word):
    m = re.search(rf"<text ([^>]*)>{word}</text>", svg)
    assert m, word
    attrs = m.group(1)
    x = float(re.search(r'(?:^|\s)x="([^"]+)"', attrs).group(1))
    y = float(re.search(r'(?:^|\s)y="([^"]+)"', attrs).group(1))
    return x, y


@pytest.mark.parametrize("side", ["left", "right"])
def test_rhythm_gutter_captions_share_side_and_baseline(side):
    d, svg, rec = _render(_tiers(Rhythm("sm"), side))
    verticals = sorted(round(r.waypoints[0][0], 2)
                       for r in rec.router_paths[-3:])
    assert len(set(verticals)) == 3
    ys = []
    for word in WORDS:
        x, y = _caption_xy(svg, word)
        nearest = min(verticals, key=lambda v: abs(v - x))
        assert (x > nearest) if side == "right" else (x < nearest), word
        ys.append(y)
    assert max(ys) - min(ys) < 0.5


def test_rhythm_gutter_keeps_the_caption_corridor_and_the_drawing():
    shared, _, rec = _render(_tiers(Rhythm("sm")))
    summed, _, _ = _render(_tiers("none"))
    assert shared.measure().h >= summed.measure().h - 1e-6
    box = shared.measure()
    for route in rec.router_paths[-3:]:
        for x, y in route.waypoints:
            assert 0.0 <= x <= box.w and 0.0 <= y <= box.h, (x, y)
