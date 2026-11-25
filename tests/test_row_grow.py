"""A ``Row(grow=True)`` takes a stretched column's surplus height.

A heading above a band of boxes, in a column that a parent makes taller:
without an absorber the column's ``justify`` places the surplus around
the band; with ``grow=True`` the band takes it, and an
``align="stretch"`` band passes it on to every box, through an
``Anchor`` too.
"""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, DEFAULT_THEME, Row


def _band(**kw):
    return Row(Box(width=40, height=20), Box(width=40, height=12),
               gap=4.0, align="stretch", **kw)


def _column(band):
    return Column(Box(width=30, height=6), band, gap=0.0, align="start")


def test_grow_row_absorbs_column_surplus():
    t = DEFAULT_THEME
    band = _band(grow=True)
    col = _column(band)
    natural_band = band.measure(t).h
    natural = col.measure(t).h
    col.inflate_to(0.0, natural + 9.0)
    assert col.measure(t).h == pytest.approx(natural + 9.0)
    assert band.measure(t).h == pytest.approx(natural_band + 9.0)
    for box in band.children:
        assert box.measure(t).h == pytest.approx(natural_band + 9.0)


def test_grow_row_absorbs_through_anchor():
    t = DEFAULT_THEME
    band = _band(grow=True)
    col = _column(Anchor("band", band))
    natural_band = band.measure(t).h
    natural = col.measure(t).h
    col.inflate_to(0.0, natural + 5.0)
    assert col.measure(t).h == pytest.approx(natural + 5.0)
    assert band.measure(t).h == pytest.approx(natural_band + 5.0)


def test_row_does_not_grow_by_default():
    t = DEFAULT_THEME
    band = _band()
    assert not getattr(band, "absorbs_main_axis_stretch", False)
    col = _column(band)
    natural_band = band.measure(t).h
    natural = col.measure(t).h
    col.inflate_to(0.0, natural + 9.0)
    assert col.measure(t).h == pytest.approx(natural + 9.0)
    assert band.measure(t).h == pytest.approx(natural_band)
