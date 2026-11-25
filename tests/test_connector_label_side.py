"""``Connect(label_side=...)``: one side for a set of sibling captions.

Sibling wires crossing one gutter read as a set when their captions sit
on the same side of their wires; left to itself the placer picks each
caption's side on its own, so a stack of short verticals gets mixed
sides. The vocabulary is :class:`Arrow`'s ``label_side``.
"""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Row
from sciviz.auto.labels import LabelBox, place_polyline_label


def _siblings(side):
    top = Row(*[Anchor(f"t{i}", Box(f"upper {i}")) for i in range(3)],
              gap="xl")
    bottom = Row(*[Anchor(f"b{i}", Box(f"lower {i}")) for i in range(3)],
                 gap="xl")
    wires = [Connect(f"t{i}", f"b{i}", src_side="bottom", dst_side="top",
                     label=word, label_side=side)
             for i, word in enumerate(("sends", "returns", "advises"))]
    return Column(top, bottom, *wires, gap="lg")


def _caption_rects(svg, words, theme):
    import re
    out = {}
    for w in words:
        m = re.search(rf'<text ([^>]*)>{w}</text>', svg)
        assert m, w
        attrs = m.group(1)
        x = float(re.search(r'(?:^|\s)x="([^"]+)"', attrs).group(1))
        y = float(re.search(r'(?:^|\s)y="([^"]+)"', attrs).group(1))
        anchor = re.search(r'text-anchor="([^"]+)"', attrs)
        out[w] = (x, y, anchor.group(1) if anchor else "start")
    return out


@pytest.mark.parametrize("side", ["left", "right"])
def test_sibling_captions_share_the_given_side(side):
    from sciviz import DEFAULT_THEME
    from sciviz.auto.debug import DebugRecorder, record_into
    d = Diagram.for_paper(_siblings(side))
    rec = DebugRecorder()
    with record_into(rec):
        svg = d.render()
    words = ("sends", "returns", "advises")
    rects = _caption_rects(svg, words, DEFAULT_THEME)
    verticals = sorted({round(r.waypoints[0][0], 2)
                        for r in rec.router_paths[-3:]})
    assert len(verticals) == 3
    for w in words:
        x, y, anchor = rects[w]
        nearest = min(verticals, key=lambda v: abs(v - x))
        if side == "right":
            assert x > nearest, (w, x, nearest)
        else:
            assert x < nearest, (w, x, nearest)
    # One gutter, one baseline.
    ys = [rects[w][1] for w in words]
    assert max(ys) - min(ys) < 0.5


def test_side_names_the_leg_orientation():
    """A bent wire with ``side="right"`` carries its caption beside the
    vertical leg even when its horizontal leg is the longer one."""
    pts = [(0.0, 0.0), (0.0, 30.0), (120.0, 30.0), (120.0, 40.0)]
    label = LabelBox(text="caption", width=30.0, height=8.0, lines=["caption"],
                     size_px=8.0)
    placed = place_polyline_label(pts, label, obstacles=[], gap=4.0,
                                  side="right")
    x0, y0, x1, y1 = placed.rect
    assert x0 >= 0.0 and y1 <= 30.0, placed.rect


def test_invalid_side_is_rejected():
    with pytest.raises(ValueError):
        Connect("a", "b", label="x", label_side="middle")
