"""Caption homes: an on-wire caption covers at most half its leg, and a
beside caption never sits nearer another wire than its own."""
from __future__ import annotations

from sciviz.auto.labels import (LabelBox, _ambiguous, on_wire_fits,
                                on_wire_stub, place_polyline_label)


def test_on_wire_caption_covers_at_most_half_its_leg():
    for leg in (40.0, 100.0, 300.0):
        for along in (5.0, 20.0, 49.0, 50.0, 51.0, 59.0, 150.0):
            if on_wire_fits(leg, along, 1.0):
                assert along <= 0.5 * leg + 1e-9
    assert on_wire_stub(100.0, 1.0) == 25.0
    assert not on_wire_fits(100.0, 59.0, 1.0)   # a two-stub corridor


def _two_sided_scene():
    """A short vertical leg at x=50 with foreign wires on both sides; the
    left one sits just past a beside caption's width."""
    lbl = LabelBox(text="candidates", width=30.0, height=7.0, size_px=7.0)
    own = [(50.0, 0.0), (50.0, 20.0)]
    fl = 50 - 6 - 30 - 2.0
    foreign = [(fl, -40.0, fl, 60.0), (88.0, -40.0, 88.0, 60.0)]
    obst = [(x - 0.5, y1, x + 0.5, y2) for (x, y1, _x, y2) in foreign]
    return lbl, own, foreign, obst


def test_beside_caption_is_never_nearer_a_foreign_wire():
    lbl, own, foreign, obst = _two_sided_scene()
    # Without the foreign-wire geometry the placer takes the ambiguous home.
    legacy = place_polyline_label(own, lbl, obst, gap=6.0)
    assert _ambiguous(legacy.rect, (own[0], own[1]), foreign, 6.0)
    placed = place_polyline_label(own, lbl, obst, gap=6.0,
                                  foreign_segments=foreign)
    assert not _ambiguous(placed.rect, (own[0], own[1]), foreign, 6.0)
    x0, y0, x1, y1 = placed.rect
    d_own = max(0.0, x0 - 50.0, 50.0 - x1)
    for (fx, _a, _b, _c) in foreign:
        d_f = max(0.0, x0 - fx, fx - x1)
        assert d_f >= d_own


def test_crossing_wire_under_the_caption_is_not_ambiguous():
    # A perpendicular wire crossing the own leg inside the caption's
    # extent does not make every home near the crossing ambiguous.
    seg = ((0.0, 50.0), (100.0, 50.0))
    rect = (30.0, 38.0, 70.0, 45.0)           # caption above the leg
    crossing = [(50.0, 0.0, 50.0, 100.0)]
    assert not _ambiguous(rect, seg, crossing, 6.0)
    parallel = [(0.0, 36.0, 100.0, 36.0)]     # a wire just above it
    assert _ambiguous(rect, seg, parallel, 6.0)
