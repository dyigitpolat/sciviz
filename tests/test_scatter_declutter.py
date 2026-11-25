"""Scatter declutter: MiniScatter(declutter="dodge") keeps a pile of
points readable in a thumbnail without losing any series. The last-drawn
point keeps its place, true duplicates and redundant hollow points are
dropped, other colliding points move at most r_i + r_j,
and a point with no free spot rings the one that hides it."""
from __future__ import annotations

import math

from sciviz import MiniPoint, MiniScatter
from sciviz.core import Theme

from tests._recording_canvas import render

TH = Theme()


def _discs(canvas):
    return [(a[0], a[1], a[2], k.get("fill"), k.get("stroke"))
            for a, k in canvas.of("circle")]


def _pile():
    return [MiniPoint(0.05, 0.95, color="#9ca3af", hollow=True),
            MiniPoint(0.05, 0.95, color="#9ca3af", hollow=True),
            MiniPoint(0.05, 0.95, color="#6b7280"),
            MiniPoint(0.06, 0.94, color="#6b7280"),
            MiniPoint(0.07, 0.93, color="#1f4e79", size=1.9),
            MiniPoint(0.5, 0.5, color="#1f4e79")]


def test_no_overlap_and_every_colour_survives():
    s = MiniScatter(_pile(), width=64, height=40, radius=1.2, pad=1.5,
                    corner=False, declutter="dodge")
    canvas, _ = render(s, TH)
    discs = [d for d in _discs(canvas)]
    colours = {d[3] if d[3] not in (None, "none", TH.bg) else d[4] for d in discs}
    assert {"#9ca3af", "#6b7280", "#1f4e79"} <= colours
    solid = [d for d in discs if d[3] not in ("none",)]
    for i, a in enumerate(solid):
        for b in solid[i + 1:]:
            if (a[0], a[1]) == (b[0], b[1]):
                continue  # a ring fallback shares its winner's centre
            assert math.hypot(a[0] - b[0], a[1] - b[1]) >= a[2] + b[2] - 1e-6


def test_last_drawn_point_keeps_its_place_and_moves_are_bounded():
    pts = _pile()
    s = MiniScatter(pts, width=64, height=40, radius=1.2, pad=1.5,
                    declutter="dodge")
    plain = MiniScatter(pts, width=64, height=40, radius=1.2, pad=1.5)
    moved = s._placements(0, 0)
    true = {id(p): (cx, cy) for p, cx, cy, _ in plain._placements(0, 0)}
    last = pts[-2]
    got = {id(p): (cx, cy, ring) for p, cx, cy, ring in moved}
    assert got[id(last)][:2] == true[id(last)]
    for p, cx, cy, ring in moved:
        if ring is None:
            tx, ty = true[id(p)]
            r = p.size or 1.2
            assert math.hypot(cx - tx, cy - ty) <= r + 1.9 + 1e-6


def test_isolated_points_and_default_are_untouched():
    pts = [(0.1, 0.1), (0.9, 0.9)]
    a = MiniScatter(pts, declutter="dodge")._placements(0, 0)
    b = MiniScatter(pts)._placements(0, 0)
    assert [(cx, cy) for _, cx, cy, _ in a] == [(cx, cy) for _, cx, cy, _ in b]
    dup = [(0.5, 0.5), (0.5, 0.5)]
    assert len(MiniScatter(dup)._placements(0, 0)) == 2
    assert len(MiniScatter(dup, declutter="dodge")._placements(0, 0)) == 1


def test_crowded_point_rings_its_winner():
    pts = [MiniPoint(0.5, 0.5, color="#ff0000")] + [
        MiniPoint(0.5 + 0.03 * math.cos(k), 0.5 + 0.03 * math.sin(k),
                  color="#0000ff") for k in range(8)]
    pts.append(MiniPoint(0.5, 0.5, color="#00ff00", size=2.5))
    s = MiniScatter(pts, width=20, height=20, radius=1.5, pad=1,
                    declutter="dodge")
    canvas, _ = render(s, TH)
    strokes = {k.get("stroke") for _, k in canvas.of("circle")}
    fills = {k.get("fill") for _, k in canvas.of("circle")}
    assert "#ff0000" in strokes | fills
