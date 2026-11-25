"""``MiniRaster`` hollow cells: an open unit, outline only, in its colour.

A row of units can say that a member was not measured (not reached, not
checked within a limit) by drawing its square open, the convention
``MiniPoint(hollow=True)`` uses for a scatter. ``MiniCell(color,
hollow=True)`` is that entry: the outline sits inside the filled cell's
square, so an open unit has the same extent and pitch as a filled one.
"""
from __future__ import annotations

import re

import pytest

from sciviz import DEFAULT_THEME, Canvas, MiniCell, MiniRaster


def _svg(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas, canvas.to_svg(40, 10)


def test_hollow_cell_is_an_outline_in_its_colour():
    _c, svg = _svg(MiniRaster([[MiniCell("#1f3f63", hollow=True)]], cell=4.7))
    rects = re.findall(r"<rect x=[^>]*/>", svg)     # the page background has no x
    assert len(rects) == 1
    assert 'fill="none"' in rects[0]
    assert 'stroke="#1f3f63"' in rects[0]


def test_hollow_cell_keeps_the_filled_cell_extent():
    t = DEFAULT_THEME
    filled = MiniRaster([["#1f3f63", "#1f3f63"]], cell=4.7, gap=0.16)
    open_ = MiniRaster([["#1f3f63", MiniCell("#1f3f63", hollow=True)]],
                       cell=4.7, gap=0.16)
    assert open_.measure(t) == filled.measure(t)
    fx = _svg(filled)[0].ink_bbox
    ox = _svg(open_)[0].ink_bbox
    assert ox == pytest.approx(fx, abs=0.05)


def test_solid_mini_cell_is_a_bare_colour():
    a = _svg(MiniRaster([["#1f3f63", "#ededed"]], cell=4.7))[1]
    b = _svg(MiniRaster([[MiniCell("#1f3f63"), MiniCell("#ededed")]],
                        cell=4.7))[1]
    assert a == b
