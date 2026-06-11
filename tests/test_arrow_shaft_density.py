"""The default inline-arrow shaft must track the theme's spacing density.

The ``target_width_pt`` fitter compresses a layout by deriving themes
with a scaled-down ``unit`` (fonts keep their authored sizes).  A fixed
pixel floor on the default Arrow shaft would refuse to compress with
the rest of the layout, leaving a card-sized corridor around every
inline ``Connect`` exactly when the figure is tightest.  The default
shaft is therefore expressed in theme units (8 units == the historical
48px at the default ``unit=6.0``); an explicit ``length=`` always wins.
"""
from __future__ import annotations

from sciviz import Theme
from sciviz.elements import Arrow


def test_default_shaft_matches_historical_default_density():
    theme = Theme()
    arrow = Arrow(direction="right")
    # 8 units at the default unit=6.0 -> the historical 48px shaft.
    assert arrow.measure(theme).w == 48.0


def test_default_shaft_compresses_with_theme_unit():
    base = Theme()
    dense = base.with_overrides(unit=base.unit * 0.5)
    arrow = Arrow(direction="right")
    assert arrow.measure(dense).w == arrow.measure(base).w * 0.5


def test_explicit_length_wins_over_density():
    base = Theme()
    dense = base.with_overrides(unit=base.unit * 0.5)
    arrow = Arrow(direction="right", length=30.0)
    assert arrow.measure(base).w == 30.0
    assert arrow.measure(dense).w == 30.0


def test_vertical_shaft_tracks_density_too():
    base = Theme()
    dense = base.with_overrides(unit=base.unit * 0.75)
    arrow = Arrow(direction="down")
    assert arrow.measure(dense).h == arrow.measure(base).h * 0.75
