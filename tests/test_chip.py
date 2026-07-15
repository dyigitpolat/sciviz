"""Chip: a compact tag pill that hugs its text.

Motivating case (thesis deployment-taxonomy figure): citation tags next
to taxonomy leaves. Box's paper-node floors (``unit*4`` height,
``unit*6`` width, wide side bearing) inflate a tiny-text tag to the same
height as the node it annotates; Chip has no minimum silhouette, so a
run of tags stays visually subordinate and packs tightly.
"""
from __future__ import annotations

import re

from sciviz import Box, Chip, Palette, Theme
from sciviz.core import Canvas


def _svg(elem) -> tuple[str, "object"]:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size


def test_chip_is_more_compact_than_equivalent_box():
    theme = Theme()
    chip = Chip("QCFS", color=Palette.blue)
    box = Box("QCFS", stroke=Palette.blue, text_size="tiny", radius="pill")
    cs, bs = chip.measure(theme), box.measure(theme)
    assert cs.h < bs.h
    assert cs.w <= bs.w
    # No paper-node height floor: the chip hugs its tiny text.
    assert cs.h < theme.unit * 4.0


def test_chip_renders_a_pill_outline():
    svg, size = _svg(Chip("Rueckauer 2017", color=Palette.red))
    m = re.search(r'<rect [^>]*rx="([0-9.]+)"', svg)
    assert m, svg
    assert float(m.group(1)) == round(size.h / 2, 2) or abs(
        float(m.group(1)) - size.h / 2) < 0.05


def test_chip_text_is_centred_inside_bbox():
    svg, size = _svg(Chip("SANA-FE"))
    m = re.search(r'<text x="([0-9.]+)" y="([0-9.]+)"', svg)
    assert m, svg
    assert float(m.group(1)) == round(size.w / 2, 2) or abs(
        float(m.group(1)) - size.w / 2) < 0.05
    assert 0.0 < float(m.group(2)) < size.h


def test_chip_never_narrower_than_tall():
    theme = Theme()
    s = Chip("a").measure(theme)
    assert s.w >= s.h


def test_chip_opts_out_of_sibling_shape_equalisation():
    # Row/Column peer-normalisation groups by truthy shape_key; chips
    # must keep intrinsic width, so their key is the empty opt-out.
    assert Chip("x").shape_key == ""


def test_dashed_chip_has_dasharray():
    svg, _size = _svg(Chip("provisional", dashed=True))
    assert "stroke-dasharray" in svg
