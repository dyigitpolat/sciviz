from __future__ import annotations

import re

import pytest

from sciviz import Box, Canvas, Grid, Theme


def test_adjacent_grid_columns_share_one_rounded_region():
    theme = Theme()
    grid = Grid(
        rows=("main",),
        columns=(
            {"main": Box("external")},
            {"_region": "workflow", "main": Box("stage A")},
            {"_region": "workflow", "main": Box("stage B")},
            {"main": Box("output")},
        ),
    )
    size = grid.measure(theme)
    canvas = Canvas()
    grid.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)

    dashed = re.findall(r'<rect [^>]*stroke-dasharray="4,3"[^>]*/>', svg)
    assert len(dashed) == 1
    assert 'rx="' in dashed[0]


def test_grid_region_members_must_be_contiguous():
    with pytest.raises(ValueError, match="adjacent columns"):
        Grid(
            rows=("main",),
            columns=(
                {"_region": "g", "main": Box("A")},
                {"main": Box("outside")},
                {"_region": "g", "main": Box("B")},
            ),
        )


def test_grid_equalises_matching_shape_peers_within_one_column():
    theme = Theme()
    short = Box("A", shape_key="same-stage")
    wide = Box("a much wider stage", shape_key="same-stage")
    grid = Grid(
        rows=("header", "main"),
        columns=({"header": short, "main": wide},),
    )
    grid.measure(theme)
    assert short.measure(theme) == wide.measure(theme)
