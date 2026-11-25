"""A ``Region(grow=True)`` takes a stretched column's surplus height.

Two regions stacked flush (``gap=0``) in a column that a row stretches:
without an absorber the column's ``justify="between"`` opens the
surplus as a seam between them; with ``grow=True`` on the lower one its
walls extend to the column's foot, through an ``Anchor`` too.
"""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, DEFAULT_THEME, Region


def _region(h, **kw):
    return Region(Box(width=40, height=h), pad_x=1.0, pad_y=1.0,
                  margin_x=0.0, margin_y=0.0, **kw)


def test_grow_region_absorbs_column_surplus_through_anchor():
    t = DEFAULT_THEME
    top = _region(10)
    low = Anchor("low", _region(20, grow=True))
    col = Column(top, low, gap=0.0, align="stretch")
    natural_top = top.measure(t).h
    natural = col.measure(t).h
    col.inflate_to(0.0, natural + 7.0)
    assert col.measure(t).h == pytest.approx(natural + 7.0)
    assert top.measure(t).h == pytest.approx(natural_top)
    assert top.measure(t).h + low.measure(t).h == pytest.approx(natural + 7.0)


def test_region_does_not_grow_by_default():
    assert not getattr(_region(5), "absorbs_main_axis_stretch", False)
    assert not Anchor("a", _region(5)).absorbs_main_axis_stretch
