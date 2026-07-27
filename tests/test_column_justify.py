"""Deliberate negative space: ``Column(justify=..., grow=...)``.

When a parent grants a column more main-axis room than its content
needs (``Row(align="stretch")`` equalising zone heights, or an explicit
``inflate_to``), the surplus must be *laid out*, not pooled wherever
content happens to stop:

1. ``justify="between"`` (default) preserves the historical behaviour:
   surplus grows the existing gaps, first child pinned to the top and
   last to the bottom.
2. ``justify="start" | "center" | "end"`` pack the block instead.
3. ``grow=True`` marks the child column that absorbs the parent's
   surplus before any gap distribution -- the zone grammar
   ``Column(header, Column(*content, grow=True, justify=...))`` keeps
   the header in the shared top band while the content column owns the
   zone's remaining height.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Column, Theme
from sciviz.core import Canvas


_RECT_RX = re.compile(r"<rect ([^/]+?)/>")


def _rect_y(svg: str, fill: str) -> float:
    for m in _RECT_RX.finditer(svg):
        attrs = m.group(1)
        fill_m = re.search(r'fill="([^"]+)"', attrs)
        if fill_m and fill_m.group(1).lower() == fill:
            y_m = re.search(r'y="([^"]+)"', attrs)
            assert y_m is not None
            return float(y_m.group(1))
    raise AssertionError(f"no rect with fill {fill!r} in svg")


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


RED, BLUE, GREEN = "#aa1100", "#0011aa", "#11aa00"


def _box(fill: str, h: float = 20.0) -> Box:
    return Box("", width=40.0, height=h, fill=fill, stroke="none")


def test_justify_between_default_distributes_gaps():
    col = Column(_box(RED), _box(BLUE), gap=10.0)
    col.inflate_to(0.0, 110.0)
    svg = _render(col)
    assert _rect_y(svg, RED) == pytest.approx(0.0, abs=0.5)
    assert _rect_y(svg, BLUE) == pytest.approx(90.0, abs=0.5)


def test_justify_center_centres_the_block():
    col = Column(_box(RED), _box(BLUE), gap=10.0, justify="center")
    col.inflate_to(0.0, 110.0)
    svg = _render(col)
    # natural block 50 tall, residual 60 -> lead 30; gap stays natural.
    assert _rect_y(svg, RED) == pytest.approx(30.0, abs=0.5)
    assert _rect_y(svg, BLUE) == pytest.approx(60.0, abs=0.5)


def test_justify_start_and_end_pin_the_block():
    start = Column(_box(RED), _box(BLUE), gap=10.0, justify="start")
    start.inflate_to(0.0, 110.0)
    svg = _render(start)
    assert _rect_y(svg, RED) == pytest.approx(0.0, abs=0.5)
    assert _rect_y(svg, BLUE) == pytest.approx(30.0, abs=0.5)

    end = Column(_box(RED), _box(BLUE), gap=10.0, justify="end")
    end.inflate_to(0.0, 110.0)
    svg = _render(end)
    assert _rect_y(svg, RED) == pytest.approx(60.0, abs=0.5)
    assert _rect_y(svg, BLUE) == pytest.approx(90.0, abs=0.5)


def test_grow_child_absorbs_surplus_header_stays_in_band():
    # Zone grammar: header + growing content column. The header keeps
    # its natural gap to the content frame; the content column receives
    # the zone's remaining height and centres its lone card in it.
    zone = Column(
        _box(GREEN, h=12.0),
        Column(_box(RED, h=30.0), grow=True),
        gap=10.0,
    )
    zone.inflate_to(0.0, 112.0)
    svg = _render(zone)
    assert _rect_y(svg, GREEN) == pytest.approx(0.0, abs=0.5)
    # inner frame spans y=[22, 112]; the 30-tall card centres at y=52.
    assert _rect_y(svg, RED) == pytest.approx(52.0, abs=0.75)


def test_invalid_justify_is_rejected():
    with pytest.raises(ValueError):
        Column(_box(RED), justify="stretch")
