"""Cell-content centering defaults (lock tests).

The engines/market/pilot mis-centering (user report, jul27 figure
sprint) was authored ``align="start"`` in the figure script, not a
primitive defect. These tests lock the library defaults that make
centred cell content the path of least resistance:

1. ``Grid`` centres each cell's content vertically within its row band.
2. ``Matrix`` centres marks within their cells.
"""
from __future__ import annotations

import re

from sciviz import Box, Grid, HarveyBall, Matrix, MatrixCell, Palette, Theme
from sciviz.core import Canvas


_RECT_RX = re.compile(r"<rect ([^/>]*?)/>")
_CIRCLE_RX = re.compile(r"<circle ([^/>]*?)/>")
_ATTR_RX = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def _rects(svg: str) -> list[dict]:
    out = []
    for m in _RECT_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        try:
            out.append({k: float(attrs[k]) for k in ("x", "y",
                                                     "width", "height")}
                       | {"fill": attrs.get("fill", "").lower()})
        except KeyError:
            continue
    return out


RED, BLUE = "#aa1100", "#0011aa"


def test_grid_centres_shorter_cell_in_its_row():
    tall = Box("", width=40.0, height=60.0, fill=RED, stroke="none")
    short = Box("", width=40.0, height=20.0, fill=BLUE, stroke="none")
    grid = Grid(rows=["r"],
                columns=[dict(r=tall), dict(r=short)],
                row_gap="sm", col_gap="sm")
    rects = _rects(_render(grid))
    tall_r = next(r for r in rects if r["fill"] == RED)
    short_r = next(r for r in rects if r["fill"] == BLUE)
    tall_cy = tall_r["y"] + tall_r["height"] / 2.0
    short_cy = short_r["y"] + short_r["height"] / 2.0
    assert abs(tall_cy - short_cy) < 0.75, (
        f"short cell centre {short_cy} vs row centre {tall_cy}")


def test_matrix_centres_marks_in_cells():
    cell = MatrixCell(mark=HarveyBall(1.0, size=6.5,
                                      color=Palette.blue,
                                      ring=Palette.blue))
    svg = _render(Matrix([[cell]], cell_size="micro"))
    circles = [dict(_ATTR_RX.findall(m.group(1)))
               for m in _CIRCLE_RX.finditer(svg)]
    assert circles, "expected the HarveyBall to draw a circle"
    cx = float(circles[0]["cx"])
    cy = float(circles[0]["cy"])
    squares = [r for r in _rects(_render(Matrix([[cell]],
                                                cell_size="micro")))
               if abs(r["width"] - r["height"]) < 0.5]
    assert squares, "expected a square matrix cell rect"
    cell_r = squares[0]
    assert abs(cx - (cell_r["x"] + cell_r["width"] / 2.0)) < 0.75
    assert abs(cy - (cell_r["y"] + cell_r["height"] / 2.0)) < 0.75
