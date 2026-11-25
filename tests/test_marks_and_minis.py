"""Pale marks, rasters of kinds, areas in an objective plane, filled lines.

* ``Theme.edge_for_fill`` gives a filled mark whose fill would vanish on
  its ground a hairline edge in a darker shade of its own colour; solid
  ``Marker``s, ``MiniPoint``s and ``MiniRaster`` cells use it.
* ``MiniRaster`` cells may each carry a colour (which kind each unit is),
  and ``spans`` bracket runs of columns with a caption.
* ``MiniScatter`` draws ``MiniArea`` polygons under its points and clips
  everything to its window.
* ``SparkLine(fill=...)`` paints the area down to ``fill_to``.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (DEFAULT_THEME, Canvas, Marker, MiniArea, MiniPoint,
                    MiniRaster, MiniScatter, SparkLine, Sparkline)


def _render(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas


def _inside(elem, theme=DEFAULT_THEME, slack=0.6):
    b = elem.measure(theme)
    x0, y0, x1, y1 = _render(elem, theme).ink_bbox
    return (x0 >= -slack and y0 >= -slack and x1 <= b.w + slack
            and y1 <= b.h + slack)


# -- contrast edge ------------------------------------------------------

def test_pale_fills_get_a_darker_edge_of_their_own_hue():
    t = DEFAULT_THEME
    for pale in ("#ededed", "#d6d6d6"):
        edge = t.edge_for_fill(pale, ground="#ffffff")
        assert edge is not None
        assert t.contrast_ratio(edge, "#ffffff") > t.contrast_ratio(
            pale, "#ffffff")
    for legible in ("#b9b9b9", "#9dbad6", "#1f3f63", "#8a8a8a"):
        assert t.edge_for_fill(legible, ground="#ffffff") is None


def test_a_dark_fill_on_a_dark_ground_lightens_and_odd_paints_get_none():
    t = DEFAULT_THEME
    edge = t.edge_for_fill("#202020", ground="#1a1a1a")
    assert edge is not None
    assert t._relative_luminance(edge) > t._relative_luminance("#202020")
    assert t.edge_for_fill("none") is None
    assert t.edge_for_fill("#ededed", min_contrast=1.1) is None


def test_solid_marker_takes_the_edge_instead_of_a_white_halo():
    pale = _render(Marker("circle", color="#ededed", size=2.0)).to_svg(10, 10)
    dark = _render(Marker("circle", color="#1f3f63", size=2.0)).to_svg(10, 10)
    assert 'stroke="white"' not in pale and 'stroke="#' in pale
    assert 'stroke="white"' in dark


# -- MiniRaster ------------------------------------------------------------

def test_raster_cells_carry_their_own_colours_and_pale_ones_an_edge():
    cells = ["#b9b9b9"] * 3 + ["#1f3f63"] * 6 + ["#ededed"]
    svg = _render(MiniRaster([cells], cell=4.6)).to_svg(60, 10)
    fills = re.findall(r'<rect[^>]*fill="(#[0-9a-fA-F]{6})"[^>]*/>', svg)
    assert fills.count("#1f3f63") == 6 and fills.count("#b9b9b9") == 3
    pale = [r for r in re.findall(r"<rect[^>]*/>", svg) if "#ededed" in r]
    assert pale and 'stroke="#' in pale[0]


def test_raster_span_brackets_columns_and_stays_in_its_box():
    plain = MiniRaster([[1] * 10], cell=4.6)
    spanned = MiniRaster([[1] * 10], cell=4.6,
                         spans=[(0, 3, "reserved floor")])
    t = DEFAULT_THEME
    assert spanned.measure(t).h > plain.measure(t).h
    # The caption may run past its short bracket; the box holds it.
    assert spanned.measure(t).w >= t.text_width("reserved floor", "tiny")
    assert _inside(spanned)
    assert "reserved floor" in _render(spanned).to_svg(80, 20)


def test_raster_keeps_its_boolean_form():
    r = MiniRaster([[1, 0, 1], [0, 1, 0]], cell=3.6)
    assert r.measure(DEFAULT_THEME).w == pytest.approx(3 * 3.6)
    assert r.measure(DEFAULT_THEME).h == pytest.approx(2 * 3.6)


# -- MiniScatter areas and clipping ----------------------------------------

def test_areas_draw_under_points_and_everything_clips_to_the_window():
    area = MiniArea([(0.2, 0.2), (3.0, 0.2), (3.0, 3.0), (0.2, 3.0)],
                    color="#9dbad6", opacity=0.6)
    far = MiniPoint(5.0, 5.0, color="#1f3f63")          # outside the window
    near = MiniPoint(0.5, 0.5, color="#1f3f63")
    s = MiniScatter([near, far], domain=(0, 1), range=(0, 1), width=40,
                    height=30, areas=[area],
                    path=[(0.0, 2.0), (0.5, 0.5), (2.0, 0.0)])
    assert _inside(s)
    svg = _render(s).to_svg(50, 40)
    first_area = svg.find("#9dbad6")
    first_point = svg.find("<circle")
    assert 0 <= first_area < first_point                 # area under points
    assert len(re.findall(r"<circle", svg)) == 1         # the far one clipped


def test_unclipped_scatter_is_the_old_behaviour():
    s = MiniScatter([MiniPoint(0.5, 0.5)], domain=(0, 1), range=(0, 1),
                    width=30, height=20, clip=False)
    assert "<circle" in _render(s).to_svg(40, 30)


def test_pale_points_get_the_contrast_edge_unless_suppressed():
    pale = MiniScatter([MiniPoint(0.5, 0.5, color="#ededed", size=1.5)],
                       domain=(0, 1), range=(0, 1), width=20, height=20)
    bare = MiniScatter([MiniPoint(0.5, 0.5, color="#ededed", size=1.5,
                                  edge="none")],
                       domain=(0, 1), range=(0, 1), width=20, height=20)
    assert re.search(r'<circle[^>]*stroke="#', _render(pale).to_svg(30, 30))
    assert not re.search(r'<circle[^>]*stroke="#',
                         _render(bare).to_svg(30, 30))


# -- SparkLine fill ----------------------------------------------------------

def test_filled_sparklines_stack_into_a_ridgeline():
    xs = [i / 20 for i in range(21)]
    lines = [SparkLine([(x, base + 1.5 * x * (1 - x)) for x in xs],
                       color=c, fill=f, fill_to=base)
             for base, c, f in ((1.0, "#1f3f63", "#8fa0b3"),
                                (0.0, "#8a8a8a", "#d0d0d0"))]
    spark = Sparkline(lines, width=50, height=24, domain=(0, 1),
                      range=(0, 2.5))
    svg = _render(spark).to_svg(60, 30)
    assert 'fill="#8fa0b3"' in svg and 'fill="#d0d0d0"' in svg
    # Up to half the line's stroke at its two ends, as for any sparkline.
    assert _inside(spark, slack=0.8)
