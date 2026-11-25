"""Trunk connector geometry: several sources join into one trunk that forks onto several targets."""
import pytest

from sciviz.connect.trunk import TrunkRoute, round_corners, trunk_route


def _on_axis(poly):
    """Every side of a polyline is horizontal or vertical."""
    return all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9 for a, b in zip(poly, poly[1:]))


def test_two_sources_two_targets_share_one_trunk():
    r = trunk_route([(10, 100), (30, 98)], [(10, 20), (30, 20)], join=90, fork=30)
    assert isinstance(r, TrunkRoute)
    assert r.trunk == ((20.0, 90.0), (20.0, 30.0))                 # one line, midway between the ends
    assert len(r.source_legs) == 2 and len(r.target_legs) == 2
    for leg, src in zip(r.source_legs, [(10, 100), (30, 98)]):
        assert leg[0] == (float(src[0]), float(src[1])) and leg[-1] == r.trunk[0]
    for leg, dst in zip(r.target_legs, [(10, 20), (30, 20)]):
        assert leg[0] == r.trunk[1] and leg[-1] == (float(dst[0]), float(dst[1]))
    assert all(_on_axis(p) for p in r.polylines)


def test_an_end_on_the_trunk_gets_a_straight_leg():
    r = trunk_route([(20, 100)], [(20, 20)], join=90, fork=30)
    assert r.source_legs[0] == ((20.0, 100.0), (20.0, 90.0))
    assert r.target_legs[0] == ((20.0, 30.0), (20.0, 20.0))
    # one source and one target on the trunk: every stroke lies on one straight line
    xs = {round(pt[0], 6) for stroke in r.commands(2.0) for cmd in stroke for pt in cmd[1:]}
    assert xs == {20.0}
    assert all(cmd[0] != "Q" for stroke in r.commands(2.0) for cmd in stroke)


def test_trunk_position_is_settable_and_defaults_to_the_mean():
    ends = dict(sources=[(0, 50), (10, 50)], targets=[(40, 0)], join=40, fork=10)
    assert trunk_route(**ends).trunk[0][0] == pytest.approx(50 / 3)
    assert trunk_route(**ends, trunk=12.5).trunk == ((12.5, 40.0), (12.5, 10.0))


def test_horizontal_trunk_mirrors_the_vertical_one():
    v = trunk_route([(10, 100), (30, 100)], [(10, 20), (30, 20)], join=90, fork=30)
    h = trunk_route([(100, 10), (100, 30)], [(20, 10), (20, 30)], join=90, fork=30, axis="horizontal")
    swap = [tuple((y, x) for x, y in poly) for poly in v.polylines]
    assert swap == [tuple(p) for p in h.polylines]


def test_rounded_corners_stay_inside_their_sides_and_mirror():
    r = trunk_route([(10, 100), (30, 100)], [(10, 20), (30, 20)], join=96, fork=24)
    strokes = r.commands(radius=3.0)
    assert strokes[0] == [("M", (20.0, 96.0)), ("L", (20.0, 24.0))]        # the trunk: one unbroken line
    left, right = strokes[1], strokes[2]
    # a 4-unit drop holds a corner of at most 2: the curve starts halfway down the drop
    assert left[1] == ("L", (10.0, 98.0)) and left[2][0] == "Q" and left[2][1] == (10.0, 96.0)
    # the two source legs are mirror images about the trunk
    mirror = [(c[0], *[(40.0 - x, y) for x, y in c[1:]]) for c in left]
    assert mirror == right
    # every leg ends on the trunk, two corner lengths along it
    assert left[-1][-1] == (20.0, 90.0) and strokes[3][0] == ("M", (20.0, 30.0))
    assert sum(1 for s in strokes for c in s if c[0] == "Q") == 8          # two corners per side leg


def test_sharp_corners_and_svg_path():
    r = trunk_route([(0, 10), (20, 10)], [(10, 0)], join=6, fork=4)
    assert all(c[0] in "ML" for s in r.commands(0.0) for c in s)
    d = r.svg_path(radius=1.0)
    assert d.startswith("M10.00 6.00 L10.00 4.00") and d.count("M") == 4 and "Q" in d


def test_round_corners_of_a_plain_polyline():
    cmds = round_corners([(0, 0), (0, 10), (10, 10)], 2.0)
    assert cmds == [("M", (0.0, 0.0)), ("L", (0.0, 8.0)), ("Q", (0.0, 10.0), (2.0, 10.0)), ("L", (10.0, 10.0))]
    assert round_corners([(0, 0), (0, 0), (5, 0)], 2.0) == [("M", (0.0, 0.0)), ("L", (5.0, 0.0))]


def test_refusals():
    with pytest.raises(ValueError):
        trunk_route([], [(0, 0)], join=1, fork=0)
    with pytest.raises(ValueError):
        trunk_route([(0, 10)], [(0, 0)], join=8, fork=2, axis="diagonal")
    with pytest.raises(ValueError):                                # a source past the join level
        trunk_route([(0, 5)], [(0, 0)], join=8, fork=2)
    with pytest.raises(ValueError):                                # a target past the fork level
        trunk_route([(0, 10)], [(0, 3)], join=8, fork=2)
