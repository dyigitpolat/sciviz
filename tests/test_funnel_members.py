"""Funnel members, lanes, bypass arc and horizontal orientation.

A funnel can show a selection as its members (one dot per member, in the
member's colour), give every colour its own lane (a selection *within*
each group), draw a dashed bypass arc for a selection that can be
skipped, and run left to right. Its ink stays inside its measured box,
and siblings align on the taper body, not on its captions.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (DEFAULT_THEME, Canvas, Diagram, Funnel, FunnelStage,
                    Icon, Row)

NAVY, GREY, DARK = "#1f3f63", "#b9b9b9", "#8a8a8a"


def _funnel(**kw):
    pool = [NAVY] * 5 + [GREY] * 24 + [DARK] * 32
    kept = [NAVY] * 3 + [GREY] * 3 + [DARK] * 4
    args = dict(orientation="horizontal", width=44, height=54, lanes=True,
                show_values=False, label_position="none", neck_ratio=0.3,
                mark_radius=1.15)
    args.update(kw)
    return Funnel([FunnelStage("drawn", 61, marks=pool),
                   FunnelStage("kept", 10, marks=kept, mark_size=1.5)],
                  **args)


def _render(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas


def _circles(svg):
    return re.findall(r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="([\d.]+)"'
                      r'[^>]*fill="(#[0-9a-fA-F]{6})"', svg)


def test_every_member_is_drawn_once_in_its_colour():
    f = _funnel()
    circles = _circles(_render(f).to_svg(100, 100))
    by_colour = {}
    for _x, _y, _r, fill in circles:
        by_colour[fill.lower()] = by_colour.get(fill.lower(), 0) + 1
    assert by_colour == {NAVY: 8, GREY: 27, DARK: 36}


def test_members_and_body_stay_inside_the_measured_box():
    for kw in ({}, dict(bypass="bypassed until\nthe sensor is\nwarmed up"),
               dict(label_position="below", show_values=True)):
        f = _funnel(**kw)
        b = f.measure(DEFAULT_THEME)
        x0, y0, x1, y1 = _render(f).ink_bbox
        assert x0 >= -0.6 and y0 >= -1.3
        assert x1 <= b.w + 0.6 and y1 <= b.h + 1.3


def test_lanes_keep_each_colour_in_its_own_band():
    """Lanes follow the taper, so they tilt; across any vertical cut the
    colours stay in lane order (navy over light grey over dark grey)."""
    f = _funnel()
    circles = [(float(x), float(y), fill.lower()) for x, y, _r, fill
               in _circles(_render(f).to_svg(100, 100))]
    order = {NAVY: 0, GREY: 1, DARK: 2}
    for xa, ya, ca in circles:
        for xb, yb, cb in circles:
            if order[ca] < order[cb] and abs(xa - xb) < 1.0:
                assert ya < yb


def test_bypass_caption_widens_the_box_and_sits_over_the_body():
    plain = _funnel()
    arc = _funnel(bypass="bypassed until\nthe sensor is\nwarmed up")
    t = DEFAULT_THEME
    assert arc.measure(t).h > plain.measure(t).h
    texts = re.findall(r">([^<>]+)</text>", _render(arc).to_svg(100, 100))
    assert texts == ["bypassed until", "the sensor is", "warmed up"]
    assert 'stroke-dasharray' in _render(arc).to_svg(100, 100)


def test_content_box_is_the_taper_body():
    f = _funnel(bypass="bypassed until\nthe sensor is\nwarmed up")
    t = DEFAULT_THEME
    cx, cy, cw, ch = f.content_bbox(t)
    b = f.measure(t)
    assert (cw, ch) == (f.width, f.height)
    assert cy + ch == pytest.approx(b.h)          # captions sit above
    # A centred neighbour lines up with the body (the neck), not with the
    # caption-inflated box.
    row = Row(f, Icon("cpu", size=14), align="center")
    (_fx, fy, _fs), (_ix, iy, isz) = row._child_offsets(t)
    assert iy + isz.h / 2 == pytest.approx(fy + cy + ch / 2, abs=1e-6)


def test_vertical_funnel_without_members_is_unchanged_in_kind():
    f = Funnel([("all", 100), ("half", 50), ("few", 10)], width=60,
               height=40)
    t = DEFAULT_THEME
    b = f.measure(t)
    assert b.w > 60 and b.h >= 40                 # label column on the right
    assert f.content_bbox(t) == (0.0, 0.0, 60.0, 40.0)
    Diagram.for_paper(f).render()


def test_orientation_and_label_position_are_validated():
    with pytest.raises(ValueError):
        Funnel([("a", 2), ("b", 1)], orientation="diagonal")
    with pytest.raises(ValueError):
        Funnel([("a", 2), ("b", 1)], orientation="vertical",
               label_position="below")
