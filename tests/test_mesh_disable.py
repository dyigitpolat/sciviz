"""`MeshArray(disable_rows=..., disable_cols=...)`: declarative "gate off
this row/column" highlighting for crossbar-style figures.

Adds a subtle fade on the cell pixels at disabled row/col indices, without
affecting peripherals (authors still control peripheral rendering).
"""
from __future__ import annotations

import re

from sciviz import MeshArray, Canvas, Theme


def _svg(elem):
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), theme


def _count_faded_cells(svg: str) -> int:
    """Count cell rects rendered with reduced opacity (the fade marker)."""
    return len(re.findall(r'<rect[^/]+\bopacity="[\d.]+"', svg))


def test_disabled_cells_rendered_with_reduced_opacity():
    data = [[1.0, 1.0], [1.0, 1.0]]
    m = MeshArray(shape=(2, 2), cell_data=data, palette="blues",
                  disable_rows=[0])
    svg, _ = _svg(m)
    assert _count_faded_cells(svg) == 2, (
        f"expected 2 faded cells in row 0, got {_count_faded_cells(svg)}")


def test_disable_cols_fades_column_cells():
    data = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
    m = MeshArray(shape=(3, 3), cell_data=data, palette="blues",
                  disable_cols=[1])
    svg, _ = _svg(m)
    assert _count_faded_cells(svg) == 3, (
        f"expected 3 faded cells in col 1, got {_count_faded_cells(svg)}")


def test_both_rows_and_cols_fade_union():
    """Disabling row 0 and col 0 fades all 3 cells at those coordinates
    (intersection cell counted once)."""
    data = [[1.0, 1.0], [1.0, 1.0]]
    m = MeshArray(shape=(2, 2), cell_data=data, palette="blues",
                  disable_rows=[0], disable_cols=[0])
    svg, _ = _svg(m)
    assert _count_faded_cells(svg) == 3, (
        f"expected 3 faded cells from row0 U col0, got {_count_faded_cells(svg)}")


def test_no_fade_by_default():
    m = MeshArray(shape=(2, 2), cell_data=[[1.0, 1.0], [1.0, 1.0]],
                  palette="blues")
    svg, _ = _svg(m)
    assert _count_faded_cells(svg) == 0, "MeshArray should not fade by default"
