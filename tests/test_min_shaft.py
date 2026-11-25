"""The entering shaft of an arrow: ``Connect(..., min_shaft=)`` and the shaft check.

An arrowhead that sits on the last bend of its wire reads as a triangle
glued to its target. Two things keep that out of a printed figure:

1. ``min_shaft`` (px) on ``Connect`` (routed and bus modes; ``Flow`` and
   ``Bus`` carry it): the least straight shaft that stays visible between
   the last bend and the base of the arrowhead. ``None``, the default,
   leaves every route and reservation as it was.
2. The shaft check (``sciviz._arrow_check``, ``Diagram.arrow_ends`` and
   ``Diagram.short_shafts``): every drawn arrowhead with the run that
   enters it, so an arm the layout fixes too short is a finding.
"""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, DEFAULT_THEME, Diagram, Row, Spacer
from sciviz._arrow_check import arrow_ends, short_shafts
from sciviz.composition._bus import Bus
from sciviz.composition._flow import Flow

HEAD = DEFAULT_THEME.arrow_head_px
BEHIND = 0.9 * HEAD            # the part of the head behind the stroke's end (the marker's refX)

MARKER = ('<defs><marker id="m-0" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" '
          'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker></defs>')


def _svg(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg">{MARKER}{body}</svg>'


# --------------------------------------------------------------------
# the check, on a drawing
# --------------------------------------------------------------------

def test_check_measures_run_head_and_shaft_of_a_line():
    ends = arrow_ends(_svg('<line x1="0" y1="10" x2="30" y2="10" stroke="#000" stroke-width="1.5" '
                           'marker-end="url(#m-0)"/>'
                           '<line x1="0" y1="60" x2="30" y2="60" stroke="#000" stroke-width="1"/>'))
    assert len(ends) == 1, "a stroke without a marker is no arrow"
    e = ends[0]
    assert e.tip == (30.0, 10.0) and e.bend == (0.0, 10.0)
    assert e.run == pytest.approx(30.0)
    assert e.head == pytest.approx(6.0)                 # marker width 4 in stroke widths of 1.5
    assert e.shaft == pytest.approx(30.0 - 0.9 * 6.0)   # the head's base stands 0.9 of the head behind the end
    assert e.straight


def test_check_takes_the_last_straight_run_of_a_path():
    ends = arrow_ends(_svg('<path d="M 0,40 L 20,40 L 20,44" fill="none" stroke="#000" stroke-width="1.5" '
                           'marker-end="url(#m-0)"/>'))
    e = ends[0]
    assert e.tip == (20.0, 44.0) and e.bend == (20.0, 40.0)
    assert e.run == pytest.approx(4.0)
    assert e.shaft == 0.0, "a head longer than its arm leaves no shaft"


def test_check_reads_a_head_at_the_start_of_a_stroke():
    ends = arrow_ends(_svg('<line x1="50" y1="0" x2="50" y2="20" stroke="#000" stroke-width="1" '
                           'marker-start="url(#m-0)"/>'))
    e = ends[0]
    assert e.tip == (50.0, 0.0) and e.bend == (50.0, 20.0)
    assert e.shaft == pytest.approx(20.0 - 0.9 * 4.0)


def test_check_measures_the_piece_after_an_arc_and_flags_a_curve():
    hop = arrow_ends(_svg('<path d="M 0,0 L 10,0 A 3,3 0 0 1 16,0 L 30,0" fill="none" stroke="#000" '
                          'stroke-width="1" marker-end="url(#m-0)"/>'))[0]
    assert hop.bend == (16.0, 0.0) and hop.run == pytest.approx(14.0) and hop.straight
    curve = arrow_ends(_svg('<path d="M 0,0 C 10,0 20,10 30,10" fill="none" stroke="#000" stroke-width="1" '
                            'marker-end="url(#m-0)"/>'))[0]
    assert not curve.straight


def test_short_shafts_lists_only_the_arrows_under_the_minimum_and_scales():
    svg = _svg('<line x1="0" y1="10" x2="30" y2="10" stroke="#000" stroke-width="1" marker-end="url(#m-0)"/>'
               '<line x1="0" y1="20" x2="6" y2="20" stroke="#000" stroke-width="1" marker-end="url(#m-0)"/>')
    short = short_shafts(svg, 8.0)
    assert [e.tip for e in short] == [(6.0, 20.0)]
    assert short_shafts(svg, 1.0) == []
    doubled = arrow_ends(svg, scale=2.0)[0]
    assert doubled.run == pytest.approx(60.0) and doubled.head == pytest.approx(8.0)
    assert doubled.tip == (60.0, 20.0)


# --------------------------------------------------------------------
# the parameter: defaults, refusals, pass-through
# --------------------------------------------------------------------

def test_default_is_off_and_a_negative_value_is_refused():
    assert Flow("a", "b").min_shaft is None
    bus = Bus(["a", "b"], "s")
    assert bus.min_shaft is None and bus.src_room is None and bus.dst_room is None
    assert bus._sink_stub(DEFAULT_THEME) == pytest.approx(DEFAULT_THEME.arrow_stub_px)
    with pytest.raises(ValueError):
        Flow("a", "b", min_shaft=-1.0)
    for name in ("min_shaft", "src_room", "dst_room"):
        with pytest.raises(ValueError):
            Bus(["a", "b"], "s", **{name: -1.0})


def test_connect_passes_the_shaft_to_its_flow_and_to_its_bus():
    c = Connect("a", "b", src_side="right", dst_side="left", min_shaft=9.0)
    assert c._impl._flow.min_shaft == 9.0
    assert Connect("a", "b")._impl._flow.min_shaft is None
    b = Connect(["a", "b"], "s", min_shaft=9.0, src_room=0.0, dst_room=2.0)
    assert (b._impl._bus.min_shaft, b._impl._bus.src_room, b._impl._bus.dst_room) == (9.0, 0.0, 2.0)
    assert b._impl._bus._sink_stub(DEFAULT_THEME) == pytest.approx(HEAD + 9.0)
    plain = Connect(["a", "b"], "s")._impl._bus
    assert plain.min_shaft is None and plain.src_room is None and plain.dst_room is None


# --------------------------------------------------------------------
# routed wires
# --------------------------------------------------------------------

def _z_route(gap=60.0, **kw):
    """A source up left, a destination down right: a bridged route across the gutter between them."""
    a = Anchor("a", Box(width=30, height=16))
    b = Anchor("b", Box(width=30, height=16))
    body = Row(Column(a, Spacer(0, 50), gap=0.0), Column(Spacer(0, 50), b, gap=0.0),
               Connect("a", "b", src_side="right", dst_side="left", src_room=0.0, dst_room=0.0, **kw),
               gap=gap, align="start")
    ends = Diagram(body).arrow_ends()
    assert len(ends) == 1
    return ends[0]


def test_routed_default_is_unchanged_by_the_parameter_at_none():
    assert _z_route() == _z_route(min_shaft=None)


def test_routed_bridge_keeps_the_shaft_from_the_head():
    plain = _z_route()
    assert plain.run < HEAD + 40.0, "the plain bridge already leaves the arm: the case shows nothing"
    held = _z_route(min_shaft=40.0)
    assert held.run >= HEAD + 40.0 - 0.6, "the last bend must stand the head and the shaft before the tip"
    assert held.shaft >= 40.0 - 0.6
    assert held.run <= 60.0 + 0.6, "the bend stays in the gutter"


def _facing(**kw):
    from sciviz.connect._resolver import _FlowResolver
    a = Anchor("a", Box(width=30, height=16))
    b = Anchor("b", Box(width=30, height=16))
    tree = Row(a, b, Connect("a", "b", src_side="right", dst_side="left", **kw), gap=0.0)
    _FlowResolver(tree)._apply_flow_margins(DEFAULT_THEME)
    return a, b


def test_pinned_head_end_reserves_the_head_and_the_shaft():
    _, b0 = _facing()
    _, b = _facing(min_shaft=30.0)
    assert b0.margin_left < HEAD + 30.0
    assert b.margin_left == pytest.approx(HEAD + 30.0)
    a, _ = _facing(min_shaft=30.0)
    a0, _ = _facing()
    assert a.margin_right == pytest.approx(a0.margin_right), "the tail end carries no head"


def test_a_room_the_author_set_wins_over_the_shaft_reservation():
    _, b = _facing(min_shaft=30.0, dst_room=0.0)
    assert b.margin_left == 0.0


# --------------------------------------------------------------------
# a bus: the spine is the last bend
# --------------------------------------------------------------------

def _fan_in(gap=40.0, rooms=True, **kw):
    a = Anchor("a", Box(width=30, height=12))
    b = Anchor("b", Box(width=30, height=12))
    s = Anchor("s", Box(width=14, height=14))
    if rooms:
        kw.update(src_room=0.0, dst_room=0.0)
    d = Diagram(Row(Column(a, b, gap=20.0), s, Connect(["a", "b"], "s", orientation="horizontal", **kw),
                    gap=gap, align="center"))
    return d


def test_bus_default_is_unchanged_by_the_parameter_at_none():
    assert _fan_in(rooms=False).render(embed_fonts=False) == _fan_in(rooms=False, min_shaft=None).render(
        embed_fonts=False)


def test_bus_spine_beside_a_sink_keeps_the_shaft():
    plain = _fan_in().arrow_ends()
    assert len(plain) == 1 and plain[0].run == pytest.approx(20.0, abs=0.6)     # the middle of the gap
    held = _fan_in(min_shaft=28.0).arrow_ends()[0]
    assert held.run == pytest.approx(HEAD + 28.0, abs=0.6)
    assert held.shaft >= 28.0 - 0.01
    assert _fan_in(min_shaft=28.0).short_shafts(28.0) == []


def test_bus_spine_stays_in_a_gap_too_narrow_and_the_check_reports_the_arm():
    d = _fan_in(min_shaft=50.0)
    e = d.arrow_ends()[0]
    assert e.run == pytest.approx(40.0, abs=0.6), "the spine is pressed against the sources, never past them"
    short = d.short_shafts(50.0)
    assert len(short) == 1 and "shaft" in short[0].describe()


def test_bus_spine_over_a_sink_keeps_the_shaft():
    a = Anchor("a", Box(width=30, height=12))
    b = Anchor("b", Box(width=30, height=12))
    s = Anchor("s", Box(width=14, height=14))
    d = Diagram(Column(Row(a, b, gap=20.0), s,
                       Connect(["a", "b"], "s", orientation="vertical", src_room=0.0, dst_room=0.0, min_shaft=22.0),
                       gap=40.0, align="center"))
    e = d.arrow_ends()[0]
    assert e.run == pytest.approx(HEAD + 22.0, abs=0.6)


def test_bus_rooms_replace_the_reservation():
    from sciviz.connect._resolver import _FlowResolver

    def margins(**kw):
        a = Anchor("a", Box(width=30, height=12))
        b = Anchor("b", Box(width=30, height=12))
        s = Anchor("s", Box(width=14, height=14))
        tree = Row(Column(a, b, gap=20.0), s, Connect(["a", "b"], "s", orientation="horizontal", **kw), gap=0.0)
        _FlowResolver(tree)._apply_flow_margins(DEFAULT_THEME)
        return a, s

    a0, s0 = margins()
    assert s0.margin_left > 0.0 and s0.margin_right > 0.0 and a0.margin_right > 0.0
    a, s = margins(src_room=0.0, dst_room=0.0)
    assert (a.margin_left, a.margin_right, s.margin_left, s.margin_right) == (0.0, 0.0, 0.0, 0.0)
    _, s = margins(min_shaft=30.0)
    assert s.margin_left == pytest.approx(HEAD + 30.0), "without a set room the sink reserves the head and the shaft"


# --------------------------------------------------------------------
# an arm the layout fixes: the check is the finding
# --------------------------------------------------------------------

def _elbow(drop):
    a = Anchor("a", Box(width=30, height=16))
    b = Anchor("b", Box(width=16, height=16))
    return Diagram(Row(Column(a, Spacer(0, drop), gap=0.0), Column(Spacer(0, drop), b, gap=0.0),
                       Connect("a", "b", src_side="right", dst_side="top", src_room=0.0, dst_room=0.0),
                       gap=30.0, align="start"))


def test_diagram_reports_an_elbow_that_ends_in_a_stub():
    short = _elbow(drop=12.0).short_shafts(8.0)        # the arm is the drop less half the source's height
    assert len(short) == 1 and short[0].run < 8.0 + BEHIND
    assert _elbow(drop=40.0).short_shafts(8.0) == []
