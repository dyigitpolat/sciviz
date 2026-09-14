"""``Column(align="stretch")`` should give stacked siblings a common outer
width, mirroring ``Row(align="stretch")``'s height stretch.

Motivating case (thesis co-optimization loop): six role-coloured ``Card``\\ s
stacked in one Column. Before this behaviour existed, ``align="stretch"``
fell through to the centring branch silently -- the author shipped a figure
believing the cards shared one width while each merely centred at its own
intrinsic width. Both containers now also *reject* unrecognised align
values instead of silently degrading to centring.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Column, Palette, Row, Text, Theme
from sciviz.core import Canvas


_RECT_RX = re.compile(r"<rect ([^/]+?)/>")


def _rects(svg: str) -> list[dict]:
    out = []
    for m in _RECT_RX.finditer(svg):
        attrs = m.group(1)
        d = {}
        for k in ("x", "y", "width", "height"):
            mk = re.search(rf'{k}="([^"]+)"', attrs)
            if mk:
                d[k] = float(mk.group(1))
        fill_m = re.search(r'fill="([^"]+)"', attrs)
        d["fill"] = (fill_m.group(1) if fill_m else "").lower()
        out.append(d)
    return out


def _render(elem) -> tuple[str, Theme]:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), theme


def _boxes():
    return (Box("short", fill=Palette.blue.soft(), stroke=Palette.blue),
            Box("a much, much longer sibling label",
                fill=Palette.amber.soft(), stroke=Palette.amber))


def _box_rects(svg: str) -> list[dict]:
    """Positioned, non-background filled rects (the two Box bodies)."""
    rects = [r for r in _rects(svg)
             if r["fill"] not in ("none", "#ffffff")
             and "x" in r and "y" in r and "width" in r]
    rects.sort(key=lambda r: r["y"])
    return rects


def test_center_leaves_box_widths_unequal():
    """Baseline: without stretch the two boxes have different widths (this
    is the behaviour ``align="stretch"`` is meant to fix)."""
    svg, _ = _render(Column(*_boxes(), gap="md", align="center"))
    rects = _box_rects(svg)
    assert len(rects) == 2, f"expected 2 box rects, got {rects}"
    assert rects[0]["width"] < rects[1]["width"] - 1.0, (
        f"expected unequal widths under align=center: "
        f"{rects[0]['width']} vs {rects[1]['width']}")


def test_stretch_equalises_box_widths():
    """``align="stretch"`` grows the narrow box to the wide box's outer
    width; both rects share a left edge and a width."""
    svg, _ = _render(Column(*_boxes(), gap="md", align="stretch"))
    rects = _box_rects(svg)
    assert len(rects) == 2, f"expected 2 box rects, got {rects}"
    narrow, wide = rects
    assert abs(narrow["width"] - wide["width"]) < 0.5, (
        f"widths not equalised: {narrow['width']} vs {wide['width']}")
    assert abs(narrow["x"] - wide["x"]) < 0.5, (
        f"boxes not left-aligned: x={narrow['x']} vs x={wide['x']}")


def test_stretch_leaves_non_inflatable_leaf_at_natural_width():
    """A leaf ``Text`` cannot grow; stretch must not distort it and the
    column still renders (mirrors Row's leaf behaviour)."""
    box, wide_box = _boxes()
    col = Column(box, wide_box, Text("caption"), gap="md", align="stretch")
    svg, theme = _render(col)
    rects = _box_rects(svg)
    assert abs(rects[0]["width"] - rects[1]["width"]) < 0.5
    # The column is at least as wide as the widest (stretched) child.
    assert col.measure(theme).w >= rects[1]["width"] - 0.5


def test_stretch_honours_parent_min_width():
    """A parent ``inflate_to`` above the widest child re-broadcasts the
    larger floor to every stretchable child."""
    box, wide_box = _boxes()
    col = Column(box, wide_box, gap="md", align="stretch")
    theme = Theme()
    natural = col.measure(theme).w
    col.inflate_to(natural + 40.0, 0.0)
    svg, _ = _render(col)
    rects = _box_rects(svg)
    assert all(abs(r["width"] - (natural + 40.0)) < 1.0 for r in rects), (
        f"children did not absorb the raised width floor: {rects}")


@pytest.mark.parametrize("container", [Row, Column])
def test_unrecognized_align_raises(container):
    """Unknown align values must fail fast instead of silently centring."""
    with pytest.raises(ValueError, match="align"):
        container(Text("x"), align="strech")  # typo'd "stretch"


@pytest.mark.parametrize("container", [Row, Column])
@pytest.mark.parametrize("align", ["start", "center", "end", "stretch"])
def test_valid_align_values_accepted(container, align):
    assert container(Text("x"), align=align).align == align


def test_stretch_colocates_faces_over_flow_corridor():
    """A flow-lane margin on ONE anchored child is a column-level
    corridor: every stretched sibling's painted face starts past it,
    so wires routed in the corridor clear all cards and the stacked
    faces (and their connector ports) stay collinear."""
    from sciviz.composition import Anchor

    margined = Anchor(
        "corridor",
        Box("first card", fill=Palette.blue.soft(), stroke=Palette.blue),
        margin_left=30.0,
    )
    plain = Box("second card", fill=Palette.amber.soft(),
                stroke=Palette.amber)
    col = Column(margined, plain, gap="md", align="stretch")
    svg, theme = _render(col)
    rects = _box_rects(svg)
    assert len(rects) == 2, rects
    top, bottom = rects
    assert abs(top["x"] - bottom["x"]) < 0.51, (
        f"faces not co-located: {rects}")
    assert abs(top["width"] - bottom["width"]) < 0.51, rects
    assert top["x"] >= 29.5, f"corridor not honoured: {rects}"
    assert col.measure(theme).w >= top["x"] + top["width"] - 0.5
