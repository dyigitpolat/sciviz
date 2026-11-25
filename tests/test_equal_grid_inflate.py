"""An inflated EqualGrid lands on the floor it was given, gaps included.

A stretched column inflates each child to one outer width; a grid that
handed each cell ``floor / columns`` grew by its own gaps and painted
wider than its siblings (a tiled panel sticking out past the band under
it).
"""

from __future__ import annotations

import pytest

from sciviz import Box, Column, DEFAULT_THEME, EqualGrid, Region


@pytest.mark.parametrize("columns,gap", [(2, "sm"), (3, "md"), (3, 4.0)])
def test_inflated_grid_width_equals_the_floor(columns, gap):
    grid = EqualGrid(*[Box(width=20, height=6) for _ in range(columns)],
                     columns=columns, equal="width", gap=gap)
    grid.inflate_to(150.0, 0.0)
    assert grid.measure(DEFAULT_THEME).w == pytest.approx(150.0)


def test_stacked_regions_share_one_outer_width():
    """A padded region holding a tile grid, stacked with a wider sibling
    under ``equal_widths``, paints at the sibling's width exactly."""
    t = DEFAULT_THEME
    tiles = Region(EqualGrid(*[Box(width=20, height=6) for _ in range(3)],
                             columns=3, equal="width", gap="sm"),
                   pad_x=2.0, pad_y=1.0, margin_x=0.0, margin_y=0.0)
    band = Region(Box(width=140, height=6), pad_x=2.0, pad_y=1.0,
                  margin_x=0.0, margin_y=0.0)
    col = Column(tiles, band, gap=0.0, align="stretch", equal_widths=True)
    w = col.measure(t).w
    assert tiles.measure(t).w == pytest.approx(w)
    assert band.measure(t).w == pytest.approx(w)
