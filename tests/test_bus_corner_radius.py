"""The corners of a bus: ``Connect(..., corner_radius=)`` in bus mode (``Bus`` carries it).

A bus draws every stroke as its own butt-ended segment, so where an
outermost tap turns into the end of the spine the outer corner is left
open (a notch of half a stroke on each side). ``corner_radius`` draws each
corner of exactly two strokes as one stroke: rounded by the radius, or
sharp and closed for ``0``. ``None``, the default, leaves every bus as it
was.
"""

from __future__ import annotations

import re

import pytest

from sciviz import Anchor, Box, Column, Connect, DEFAULT_THEME, Diagram, Row
from sciviz.composition._bus import Bus

SW = DEFAULT_THEME.connector
HEAD = DEFAULT_THEME.arrow_head_px


def _fan_in(orientation="horizontal", gap=40.0, spread=20.0, **kw):
    a = Anchor("a", Box(width=30, height=12))
    b = Anchor("b", Box(width=30, height=12))
    s = Anchor("s", Box(width=14, height=14))
    wire = Connect(["a", "b"], "s", orientation=orientation, src_room=0.0, dst_room=0.0, **kw)
    if orientation == "horizontal":
        return Diagram(Row(Column(a, b, gap=spread), s, wire, gap=gap, align="center"))
    return Diagram(Column(Row(a, b, gap=spread), s, wire, gap=gap, align="center"))


def _lines(svg):
    """The bus's strokes drawn as lines: (x1, y1, x2, y2, has marker)."""
    out = []
    for m in re.finditer(r"<line ([^>]*)/>", svg):
        a = dict(re.findall(r'([a-z0-9\-]+)="([^"]*)"', m.group(1)))
        out.append((float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]), "marker-end" in a))
    return out


def _corner_paths(svg):
    """The corner strokes: every stroked path without a fill, as its list of numbers and its commands."""
    out = []
    for m in re.finditer(r'<path d="(M [^"]*)" fill="none" stroke="[^"]*" stroke-width="[0-9.]+"/>', svg):
        d = m.group(1)
        out.append((re.findall(r"[MLQ]", d), [float(v) for v in re.findall(r"-?[0-9.]+", d)]))
    return out


def _len(l):
    return abs(l[2] - l[0]) + abs(l[3] - l[1])


def test_default_is_off_and_the_drawing_is_unchanged():
    assert Bus(["a", "b"], "s").corner_radius is None
    assert Connect(["a", "b"], "s")._impl._bus.corner_radius is None
    plain = _fan_in().render(embed_fonts=False)
    assert plain == _fan_in(corner_radius=None).render(embed_fonts=False)
    assert _corner_paths(plain) == [], "without the keyword a bus draws no corner stroke"


def test_a_negative_radius_is_refused_and_connect_passes_it_on():
    with pytest.raises(ValueError):
        Bus(["a", "b"], "s", corner_radius=-1.0)
    assert Connect(["a", "b"], "s", corner_radius=2.5)._impl._bus.corner_radius == 2.5


def test_the_two_ends_of_the_spine_turn_with_the_radius():
    r = 3.0
    plain = _lines(_fan_in().render(embed_fonts=False))
    svg = _fan_in(corner_radius=r).render(embed_fonts=False)
    lines, corners = _lines(svg), _corner_paths(svg)
    assert len(lines) == len(plain) == 4, "two source taps, the arrowed tap and the spine"
    assert len(corners) == 2, "one corner stroke at each end of the spine"
    for cmds, nums in corners:
        assert cmds == ["M", "L", "Q", "L"]
        (ax, ay), (cx, cy), (bx, by) = (nums[2], nums[3]), (nums[4], nums[5]), (nums[6], nums[7])
        assert abs(ax - cx) + abs(ay - cy) == pytest.approx(r, abs=0.01)
        assert abs(bx - cx) + abs(by - cy) == pytest.approx(r, abs=0.01)
        assert (abs(ax - cx) < 0.01) != (abs(bx - cx) < 0.01), "the two sides stand at a right angle"
    # the arrowed tap is the bus's T: untouched, with its whole shaft
    arrow_plain = next(l for l in plain if l[4])
    arrow = next(l for l in lines if l[4])
    assert arrow == arrow_plain
    # the spine gives up the radius at each end, each outer tap at its spine end
    spine_plain = next(l for l in plain if abs(l[0] - l[2]) < 0.01)
    spine = next(l for l in lines if abs(l[0] - l[2]) < 0.01)
    assert _len(spine) == pytest.approx(_len(spine_plain) - 2 * r, abs=0.01)
    taps_plain = sorted(_len(l) for l in plain if not l[4] and abs(l[1] - l[3]) < 0.01)
    taps = sorted(_len(l) for l in lines if not l[4] and abs(l[1] - l[3]) < 0.01)
    assert taps == pytest.approx([t - r for t in taps_plain], abs=0.01)
    # the shaft check reads the same arm
    assert _fan_in(corner_radius=r).arrow_ends()[0].run == pytest.approx(_fan_in().arrow_ends()[0].run)


def test_radius_zero_closes_the_corner_and_keeps_every_stroke():
    plain = _lines(_fan_in().render(embed_fonts=False))
    svg = _fan_in(corner_radius=0.0).render(embed_fonts=False)
    assert _lines(svg) == plain
    corners = _corner_paths(svg)
    assert len(corners) == 2
    for cmds, nums in corners:
        assert cmds == ["M", "L", "L"], "two sides with a mitred join on the corner point"
        assert abs(nums[0] - nums[2]) + abs(nums[1] - nums[3]) == pytest.approx(SW, abs=0.01)


def test_a_corner_stops_at_the_next_junction_and_at_half_a_stroke():
    # the spine is 32 px long with the arrowed tap on its middle: a radius of 50 takes the 16 px to that T
    svg = _fan_in(spread=20.0, corner_radius=50.0).render(embed_fonts=False)
    lines = _lines(svg)
    plain = _lines(_fan_in(spread=20.0).render(embed_fonts=False))
    spine_plain = next(l for l in plain if abs(l[0] - l[2]) < 0.01)
    for cmds, nums in _corner_paths(svg):
        r = abs(nums[2] - nums[4]) + abs(nums[3] - nums[5])
        assert r == pytest.approx(_len(spine_plain) / 2.0, abs=0.01)
    assert all(_len(l) >= -1e-9 for l in lines)
    assert next(l for l in lines if l[4]) == next(l for l in plain if l[4]), "the T and its shaft stay"


def test_an_arrowed_stroke_keeps_its_head_and_shaft_behind_a_corner():
    # one source beside the sink's row: the bus is an elbow, and its arrowed tap ends on the corner
    a = Anchor("a", Box(width=30, height=12))
    s = Anchor("s", Box(width=14, height=14))

    def build(**kw):
        return Diagram(Row(Column(a, Box(width=30, height=40), gap=10.0), s,
                           Connect(["a"], ["s"], orientation="horizontal", src_room=0.0, dst_room=0.0,
                                   min_shaft=6.0, **kw),
                           gap=14.0, align="end"))

    plain = build().arrow_ends()[0]
    held = build(corner_radius=30.0).arrow_ends()[0]
    assert held.shaft >= min(plain.shaft, 6.0) - 0.01, "the corner never takes the shaft the head needs"


def test_a_horizontal_spine_turns_its_ends_too():
    svg = _fan_in(orientation="vertical", corner_radius=2.0).render(embed_fonts=False)
    corners = _corner_paths(svg)
    assert len(corners) == 2
    assert all(cmds == ["M", "L", "Q", "L"] for cmds, _ in corners)


# --------------------------------------------------------------------
# the flush head: ``Connect(..., flush_head=True)`` in bus mode
# --------------------------------------------------------------------
# The default head stands with nine tenths of its length behind the end of
# its stroke. A head only a few strokes wide is narrower than the stroke
# there, so the stroke's square end shows beside the tip. A flush head
# stands where it is exactly as wide as the stroke, and the stroke ends
# that much earlier, so the tip does not move.

def _marker_ref(svg):
    m = re.search(r'<marker id="bus-[0-9]+" viewBox="0 0 10 10" refX="([0-9.]+)"', svg)
    return float(m.group(1))


def test_flush_head_is_off_by_default_and_connect_passes_it_on():
    assert Bus(["a", "b"], "s").flush_head is False
    assert Connect(["a", "b"], "s")._impl._bus.flush_head is False
    assert Connect(["a", "b"], "s", flush_head=True)._impl._bus.flush_head is True
    plain = _fan_in().render(embed_fonts=False)
    assert plain == _fan_in(flush_head=False).render(embed_fonts=False)
    assert _marker_ref(plain) == 9.0


def test_flush_head_ends_the_stroke_where_the_head_is_as_wide_and_keeps_the_tip():
    size = DEFAULT_THEME.arrow_size
    plain_svg = _fan_in().render(embed_fonts=False)
    svg = _fan_in(flush_head=True).render(embed_fonts=False)
    ref = _marker_ref(svg)
    assert ref == pytest.approx(10.0 - 10.0 / size, abs=0.006)
    # at the stroke's end the head is as wide as the stroke
    assert (10.0 - ref) / 10.0 * HEAD == pytest.approx(SW, abs=0.01)
    plain = next(l for l in _lines(plain_svg) if l[4])
    flush = next(l for l in _lines(svg) if l[4])
    tip_plain = plain[2] + 0.1 * HEAD
    tip_flush = flush[2] + (10.0 - ref) / 10.0 * HEAD
    assert tip_flush == pytest.approx(tip_plain, abs=0.02), "the tip stands where the default head's tip stands"
    assert flush[2] < plain[2] and flush[:2] == plain[:2], "only the arrowed end of the stroke moves"
    # the shaft check reads the head from its marker: the same shaft behind the same head
    a, b = _fan_in().arrow_ends()[0], _fan_in(flush_head=True).arrow_ends()[0]
    assert b.head == pytest.approx(a.head) and b.shaft == pytest.approx(a.shaft, abs=0.02)


def test_flush_head_and_rounded_corners_together():
    svg = _fan_in(flush_head=True, corner_radius=3.0).render(embed_fonts=False)
    assert len(_corner_paths(svg)) == 2 and _marker_ref(svg) < 9.0
    a, b = _fan_in().arrow_ends()[0], _fan_in(flush_head=True, corner_radius=3.0).arrow_ends()[0]
    assert b.shaft == pytest.approx(a.shaft, abs=0.02)
