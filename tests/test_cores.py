"""``StepRaster``, ``CoreChip``, ``LayerNet``, ``ThinArrow``: schematic step blocks.

A schedule drawn as hardware: lit blocks over discrete steps, chips of cores
with window strips, a small layered network, one thin arrow style. Also the
outliner's blank-run guard, which an empty alignment title relies on.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (DEFAULT_THEME, Canvas, Column, Core, CoreChip, CoreLink, Diagram,
                    LayerNet, NetLayer, RasterLink, RasterRow, StepRaster, Text, ThinArrow)

HUE = "#3b5fa0"


def _render(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    box = elem.measure(theme)
    return canvas.to_svg(box.w, box.h), box


def _rects(svg):
    return re.findall(r"<rect [^>]*/>", svg)


def test_raster_lights_the_window_blocks_and_puts_dots_at_marks():
    r = StepRaster([RasterRow("L1", HUE, (0, 2), [0, 2])], range(5), cell=10, axis=False)
    svg, box = _render(r)
    lit = [t for t in _rects(svg) if f'stroke="{HUE}"' in t]
    assert len(lit) == 3                                  # steps 0, 1, 2
    dots = re.findall(r"<circle [^>]*/>", svg)
    assert len(dots) == 2
    x0 = r.cell_center(DEFAULT_THEME, 0, 0)[0]
    x2 = r.cell_center(DEFAULT_THEME, 0, 2)[0]
    assert x2 - x0 == pytest.approx(20.0)                 # one pitch per step


def test_raster_cuts_add_a_gap_and_rows_share_lines_by_phase():
    rows = [RasterRow("L1", HUE, (0, 2), [0], span=(0, 4)),
            RasterRow("", kind="store", marks=[5], span=(5, 9), line=0)]
    r = StepRaster(rows, list(range(5)) * 2, cell=10, cuts=[5], cut_gap=1.5, axis=False)
    assert r._n_lines() == 1
    a = r.cell_center(DEFAULT_THEME, 0, 4)[0]
    b = r.cell_center(DEFAULT_THEME, 1, 5)[0]
    assert b - a == pytest.approx(10.0 * 2.5)             # one pitch plus the cut gap
    svg, _ = _render(r)
    assert "1.6,1.6" in svg                               # the dashed cut rule
    plain = StepRaster(rows, list(range(5)) * 2, cell=10, cuts=[(5, False)], axis=False)
    assert "1.6,1.6" not in _render(plain)[0]


def test_raster_link_must_name_a_cell_and_tags_widen_the_raster():
    with pytest.raises(ValueError):
        StepRaster([RasterRow("a")], range(3), links=[RasterLink((0, 0), (1, 1))])
    base = StepRaster([RasterRow("a", HUE, (0, 1))], range(3), axis=False)
    tagged = StepRaster([RasterRow("a", HUE, (0, 1), tag=Text("same output"))], range(3),
                        axis=False)
    assert tagged.measure(DEFAULT_THEME).w > base.measure(DEFAULT_THEME).w + 20


def test_chip_draws_cores_strips_idle_cores_and_skip_arcs_inside_its_outline():
    chip = CoreChip([Core("L1", HUE, (0, 2)), Core("L2", HUE, (1, 3)), Core()], steps=5,
                    core=16, links=[CoreLink(0, 1), CoreLink(0, 2, bend=0.2, dashed=True)])
    svg, box = _render(chip)
    lit = [t for t in _rects(svg) if f'stroke="{HUE}"' in t]
    assert len(lit) == 2 + 6                              # two blocks, 3 + 3 window cells
    assert "1.6,1.2" in svg                               # the idle core's dashed outline
    assert "Q " in svg                                    # the skip is an arc
    x, y, w, h = chip.core_box(0)
    assert y >= chip._arc_h()                             # the arc's room is inside the chip
    flat = CoreChip([Core("L1", HUE, (0, 2)), Core("L2", HUE, (1, 3))], steps=5, core=16)
    assert box.h > flat.measure(DEFAULT_THEME).h


def test_layer_net_fans_consecutive_layers_and_arcs_the_skip():
    net = LayerNet([NetLayer("L1", 3), NetLayer("L2", 3), NetLayer("L3", 2)], skips=[(0, 2)])
    svg, box = _render(net)
    assert len(re.findall(r"<line ", svg)) == 3 * 3 + 3 * 2
    assert len(re.findall(r"<circle ", svg)) == 8
    assert "Q " in svg
    no_skip = LayerNet([NetLayer("L1", 3), NetLayer("L2", 3), NetLayer("L3", 2)])
    assert box.h > no_skip.measure(DEFAULT_THEME).h


def test_thin_arrow_has_the_link_head():
    svg, box = _render(ThinArrow(12))
    assert box.w == pytest.approx(16.0)
    assert "<polygon" in svg


def test_outline_skips_a_blank_text_run(tmp_path):
    d = Diagram.for_paper(Column(Text(" "), Text("x")))
    d.save(str(tmp_path / "blank.pdf"), text_mode="outline")
    assert (tmp_path / "blank.pdf").stat().st_size > 0


def test_point_arrows_join_a_raster_dot_to_a_chip_strip_cell():
    from sciviz import PointArrow, PointArrows, Row
    raster = StepRaster([RasterRow("", kind="store", marks=[0, 2])], range(5), cell=9,
                        axis_side="top", name="st")
    chip = CoreChip([Core("L2", HUE, (1, 3), [1, 3])], steps=5, core=20, strip_h=5, name="p2")
    body = PointArrows(Row(raster, chip, gap=20),
                       [PointArrow("st:0,2", "p2:0,3", enter="below")])
    svg, _ = _render(body)
    assert " C " in svg                                   # the entering curve is a cubic
    heads = re.findall(r"<polygon [^>]*/>", svg)
    assert heads                                          # one solid head
    # the head points up: its tip is the polygon's highest vertex, under the cell's dot
    pts = [tuple(map(float, p.split(","))) for p in
           re.search(r'points="([^"]+)"', heads[-1]).group(1).split()]
    tip = min(pts, key=lambda p: p[1])
    assert abs(tip[0] - min(p[0] for p in pts) - (max(p[0] for p in pts) - tip[0])) < 0.05
    with pytest.raises(KeyError):
        _render(PointArrows(Row(raster, chip), [PointArrow("st:0,2", "nowhere:0")]))
    with pytest.raises(ValueError):
        PointArrow("a:0", "b:0", enter="sideways")


def test_strip_marks_and_top_axis():
    chip = CoreChip([Core("L1", HUE, (0, 2), [0, 2])], steps=5, core=20)
    svg, _ = _render(chip)
    assert len(re.findall(r"<circle ", svg)) == 2         # one dot per marked step
    top = StepRaster([RasterRow("", kind="store", marks=[0])], range(5), cell=9,
                     axis_side="top")
    bottom = StepRaster([RasterRow("", kind="store", marks=[0])], range(5), cell=9)
    assert top.measure(DEFAULT_THEME).h == pytest.approx(bottom.measure(DEFAULT_THEME).h)
    assert top.cell_center(DEFAULT_THEME, 0, 0)[1] > bottom.cell_center(DEFAULT_THEME, 0, 0)[1]
    with pytest.raises(ValueError):
        StepRaster([RasterRow("")], range(3), axis_side="left")
