"""``StepLanes``: lanes over discrete time steps, with windows, marks, links.

A schedule on a step grid: every step is one column, a lane's window covers
exactly its steps' columns, marks are dots at column centres on faint
gridlines, and a link is an arrow between the edges of two marks, so "emitted
at step t, received at step t + 1" is read off the drawing. A ``bar`` lane
puts a measured share on the grid's own width.
"""
from __future__ import annotations

import math
import re

import pytest

from sciviz import (DEFAULT_THEME, Canvas, StepGroup, StepLane, StepLanes,
                    StepLink, Text)

INK = "#1f3f63"


def _render(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    box = elem.measure(theme)
    return canvas, canvas.to_svg(box.w, box.h), box


def _num(attr, tag):
    return float(re.search(rf'{attr}="([-0-9.]+)"', tag).group(1))


def _dots(svg, color=INK):
    return [(_num("cx", c), _num("cy", c), _num("r", c))
            for c in re.findall(r"<circle [^>]*/>", svg) if f'fill="{color}"' in c]


def _two_layers(step_w=20.0, **kw):
    return StepLanes([
        StepGroup("one pass", [
            StepLane("layer 1", window=(0, 2), marks=[0, 2], color=INK, key="l1"),
            StepLane("layer 2", window=(1, 3), marks=[1, 3], color=INK, key="l2"),
        ], note="reference"),
    ], steps=range(5), links=[StepLink(("l1", 0), ("l2", 1)),
                              StepLink(("l1", 2), ("l2", 3))], step_w=step_w, **kw)


def test_ink_stays_inside_the_measured_box():
    for notes in ("label", "right"):
        canvas, _svg, box = _render(_two_layers(axis_title="time step", notes=notes))
        x0, y0, x1, y1 = canvas.ink_bbox
        assert x0 >= -0.5 and y0 >= -0.5
        assert x1 <= box.w + 0.5 and y1 <= box.h + 0.5


def test_marks_are_dots_at_column_centres():
    _c, svg, _b = _render(_two_layers())
    xs = sorted(cx for cx, _cy, _r in _dots(svg))
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    # layer 1 at steps 0, 2 and layer 2 at 1, 3: one column (20 px) apart
    assert sorted(set(round(g, 3) for g in gaps)) == [20.0]


def test_windows_cover_exactly_their_columns_with_square_corners():
    _c, svg, _b = _render(_two_layers())
    windows = [r for r in re.findall(r"<rect [^>]*/>", svg) if "stroke=" in r]
    assert len(windows) == 2
    assert all("rx=" not in r for r in windows)
    assert [_num("width", r) for r in windows] == pytest.approx([60.0, 60.0])
    heights = {round(_num("height", r), 4) for r in windows}
    assert len(heights) == 1                                   # one bar height for all lanes
    xs = sorted(_num("x", r) for r in windows)
    assert xs[1] - xs[0] == pytest.approx(20.0)                # layer 2 starts one step later


def test_gridlines_pass_through_the_dots():
    _c, svg, _b = _render(_two_layers())
    verticals = {round(_num("x1", ln), 3) for ln in re.findall(r"<line [^>]*/>", svg)
                 if _num("x1", ln) == _num("x2", ln)}
    for cx, _cy, _r in _dots(svg):
        assert round(cx, 3) in verticals


def test_link_runs_from_mark_edge_to_mark_edge_one_step_later():
    _c, svg, _b = _render(_two_layers())
    dots = _dots(svg)
    heads = re.findall(r'<polygon points="([^"]+)"', svg)
    assert len(heads) == 2
    for pts in heads:
        tx, ty = (float(v) for v in pts.split()[0].split(","))
        # the tip sits just outside one dot, on the side facing the source
        near = min(dots, key=lambda d: math.hypot(tx - d[0], ty - d[1]))
        dist = math.hypot(tx - near[0], ty - near[1])
        assert near[2] < dist < near[2] + 1.0
        assert ty < near[1] and tx < near[0]                   # arrives from upper left


def test_same_lane_link_is_horizontal_and_ghosts_are_hollow():
    elem = StepLanes([StepLane("late", window=(2, 4), marks=[2, 4], ghosts=[1, 3],
                               color="#b91c1c", key="late")],
                     steps=range(5), step_w=20.0,
                     links=[StepLink(("late", 1), ("late", 2), color="#b91c1c")])
    _c, svg, _b = _render(elem)
    shaft = re.search(r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"'
                      r' stroke="#b91c1c"', svg)
    assert shaft and shaft.group(2) == shaft.group(4)
    assert float(shaft.group(1)) < float(shaft.group(3))
    hollow = [c for c in re.findall(r"<circle [^>]*/>", svg) if 'fill="#ffffff"' in c]
    assert len(hollow) == 2


def test_store_lane_is_a_dashed_strip_over_every_step():
    elem = StepLanes([StepLane("stored spikes", kind="store", marks=[1, 3])],
                     steps=range(5), step_w=20.0)
    _c, svg, _b = _render(elem)
    strip = [r for r in re.findall(r"<rect [^>]*/>", svg) if "stroke-dasharray" in r]
    assert len(strip) == 1
    assert _num("width", strip[0]) == pytest.approx(5 * 20.0)


def test_bar_lane_spans_its_share_of_the_grid_and_sets_its_value_after_it():
    elem = StepLanes([
        StepLane("a", window=(0, 1), marks=[0]),
        StepGroup("counts", [StepLane("half", kind="bar", share=0.5, color="#b91c1c",
                                      value="1 of 2"),
                             StepLane("none", kind="bar", share=0.0, value="0 of 2")]),
    ], steps=range(4), step_w=25.0)
    canvas, svg, box = _render(elem)
    window = [r for r in re.findall(r"<rect [^>]*/>", svg) if "stroke=" in r][0]
    bar = [r for r in re.findall(r"<rect [^>]*/>", svg) if 'fill="#b91c1c"' in r]
    assert len(bar) == 1
    assert _num("x", bar[0]) == pytest.approx(_num("x", window))    # same left edge
    assert _num("width", bar[0]) == pytest.approx(0.5 * 4 * 25.0)
    assert "1 of 2" in svg and "0 of 2" in svg
    assert canvas.ink_bbox[2] <= box.w + 0.5


def test_a_full_bar_keeps_its_value_inside_the_box():
    elem = StepLanes([StepLane("all", kind="bar", share=1.0, value="2 of 2")],
                     steps=range(3), step_w=20.0)
    canvas, _svg, box = _render(elem)
    assert canvas.ink_bbox[2] <= box.w + 0.5


def test_notes_as_label_line_leave_the_grid_the_width():
    th = DEFAULT_THEME
    right = _two_layers(step_w=None, width=300.0, notes="right")
    label = _two_layers(step_w=None, width=300.0, notes="label")
    assert label._step_w(th) > right._step_w(th)
    assert label.measure(th).w == pytest.approx(300.0)
    assert right.measure(th).w == pytest.approx(300.0)


def test_corner_and_left_axis_title_both_fit_the_label_room():
    th = DEFAULT_THEME
    corner = Text("(b)  A long panel title", size="small")
    elem = _two_layers(axis_title="time step", corner=corner)
    gw, lw, _nw, cg = elem._columns(th)
    assert gw + cg + lw + 1e-6 >= (corner.measure(th).w + cg
                                   + th.text_width("time step", "small"))
    canvas, _svg, box = _render(elem)
    assert canvas.ink_bbox[2] <= box.w + 0.5


def test_a_group_label_with_more_lines_than_lanes_grows_the_group():
    one = StepLanes([StepGroup("a", [StepLane("x", marks=[0])])], steps=range(2))
    three = StepLanes([StepGroup("a\nb\nc", [StepLane("x", marks=[0])])], steps=range(2))
    noted = StepLanes([StepGroup("a", [StepLane("x", marks=[0])], note="n")], steps=range(2))
    th = DEFAULT_THEME
    assert three.measure(th).h > one.measure(th).h
    assert noted.measure(th).h > one.measure(th).h          # the note is a second line


def test_tick_marks_remain_available():
    _c, svg, _b = _render(_two_layers(mark="tick"))
    ticks = [r for r in re.findall(r"<rect [^>]*/>", svg) if f'fill="{INK}"' in r]
    assert len(ticks) == 4 and not _dots(svg)


def test_bad_arguments_raise():
    with pytest.raises(ValueError):
        StepLanes([StepLane("a")], steps=range(3), links=[StepLink(("b", 0), ("a", 1))])
    with pytest.raises(ValueError):
        StepLanes([StepLane("a")], steps=range(3), links=[StepLink(("a", 0), ("a", 7))])
    with pytest.raises(ValueError):
        StepLane("a", window=(3, 1))
    with pytest.raises(ValueError):
        StepLane("a", kind="buffer")
    with pytest.raises(ValueError):
        StepLane("a", kind="bar", share=1.5)
    with pytest.raises(ValueError):
        StepLanes([StepLane("a", key="k"), StepLane("b", key="k")], steps=range(2))
    with pytest.raises(ValueError):
        StepLanes([StepLane("a")], steps=range(2), notes="below")
    with pytest.raises(ValueError):
        StepLanes([StepLane("a")], steps=range(2), mark="star")


# -- stacked timelines: diamonds, curved skip links, pass tags and cuts ------
from sciviz import ShareBar, StepMark  # noqa: E402


def _residual(**link_kw):
    return StepLanes([StepGroup("segment", [
        StepLane("L1", window=(0, 2), marks=[0], key="a", tag="pass 1"),
        StepLane("L2", window=(1, 3), marks=[1], key="b", tag="pass 2"),
        StepLane("L3", window=(2, 4), marks=[StepMark(2, "diamond", color="#123456")],
                 key="c", tag="pass 2"),
    ], cuts=(0,))], steps=range(5), step_w=24.0,
        links=[StepLink(("a", 0), ("b", 1)), StepLink(("b", 1), ("c", 2)),
               StepLink(("a", 0), ("c", 2), **link_kw)])


def test_diamond_mark_is_a_polygon_centred_on_its_step_in_its_own_colour():
    _c, svg, _b = _render(_residual())
    diamonds = [p for p in re.findall(r"<polygon [^>]*/>", svg) if 'fill="#123456"' in p]
    assert len(diamonds) == 1
    pts = [tuple(float(v) for v in xy.split(","))
           for xy in re.search(r'points="([^"]+)"', diamonds[0]).group(1).split()]
    cx = sum(p[0] for p in pts) / 4
    dots = _dots(svg, color=DEFAULT_THEME.color_of("text"))
    x0 = min(d[0] for d in dots)                         # L1's dot at step 0
    assert cx - x0 == pytest.approx(2 * 24.0, abs=0.02)


def test_curved_dashed_link_bows_below_left_of_the_straight_line():
    _c, svg, _b = _render(_residual(bend=0.1, dashed=True))
    arcs = re.findall(r'<path d="M ([-0-9.]+) ([-0-9.]+) Q ([-0-9.]+) ([-0-9.]+) '
                      r'([-0-9.]+) ([-0-9.]+)"[^>]*/>', svg)
    assert len(arcs) == 1
    sx, sy, qx, qy, ex, ey = (float(v) for v in arcs[0])
    # the control point lies below the chord for a link running down and right
    chord_y_at_qx = sy + (ey - sy) * (qx - sx) / (ex - sx)
    assert qy > chord_y_at_qx
    assert "stroke-dasharray" in re.search(r'<path d="M [^>]*/>', svg).group(0)


def test_straight_links_have_no_dashes_by_default():
    _c, svg, _b = _render(_residual())
    shafts = [ln for ln in re.findall(r"<line [^>]*/>", svg)
              if _num("x1", ln) != _num("x2", ln) and _num("y1", ln) != _num("y2", ln)]
    assert len(shafts) == 3 and all("dasharray" not in ln for ln in shafts)


def test_tags_sit_right_of_the_grid_inside_the_box():
    canvas, svg, box = _render(_residual())
    assert svg.count(">pass 2<") == 2 and ">pass 1<" in svg
    tag_x = [float(x) for x in re.findall(r'<text x="([0-9.]+)"[^>]*>pass', svg)]
    windows = [r for r in re.findall(r"<rect [^>]*/>", svg) if "stroke=" in r]
    grid_end = max(_num("x", r) + _num("width", r) for r in windows)
    assert min(tag_x) > grid_end
    assert canvas.ink_bbox[2] <= box.w + 0.5


def test_cut_is_a_dashed_line_between_the_first_two_lanes():
    _c, svg, _b = _render(_residual())
    cuts = [ln for ln in re.findall(r"<line [^>]*/>", svg)
            if "dasharray" in ln and _num("y1", ln) == _num("y2", ln)]
    assert len(cuts) == 1
    dots = sorted(_dots(svg, color=DEFAULT_THEME.color_of("text")), key=lambda d: d[1])
    assert dots[0][1] < _num("y1", cuts[0]) < dots[1][1]   # between L1 and L2


def test_bad_mark_shape_raises():
    with pytest.raises(ValueError):
        StepMark(1, "star")


def test_share_bar_fills_its_share_of_the_track():
    canvas = Canvas(default_font_family=DEFAULT_THEME.font_family)
    ShareBar(0.25, width=80.0, color="#b91c1c").render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(90, 10)
    rects = re.findall(r"<rect x=[^>]*/>", svg)
    fill = [r for r in rects if 'fill="#b91c1c"' in r]
    assert len(rects) == 2 and len(fill) == 1
    assert _num("width", fill[0]) == pytest.approx(20.0)
    assert max(_num("width", r) for r in rects) == pytest.approx(80.0)


def test_share_bar_at_zero_keeps_track_and_origin_and_validates():
    canvas = Canvas(default_font_family=DEFAULT_THEME.font_family)
    bar = ShareBar(0.0, width=50.0)
    bar.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(60, 10)
    assert len(re.findall(r"<rect x=[^>]*/>", svg)) == 1
    assert len(re.findall(r"<line [^>]*/>", svg)) == 1
    x0, y0, x1, y1 = canvas.ink_bbox
    box = bar.measure(DEFAULT_THEME)
    assert x1 <= box.w + 0.5 and y1 <= box.h + 0.5
    with pytest.raises(ValueError):
        ShareBar(1.2)
