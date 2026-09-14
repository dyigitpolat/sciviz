"""``Panel(content_align=...)`` decides where a child sits in the surplus
content height a peer-matched panel inherits.

The ``"auto"`` default keeps the structural heuristic (a Column/Card stack
pins to the content top so comparative panels share a first-row baseline;
compact leaf visuals centre). Panels holding *independent* diagrams declare
``"center"`` -- sciviz cannot infer whether row i of one panel corresponds
to row i of its neighbour.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Column, Palette, Panel, Row, Theme
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


def _stack(n: int, tag: str) -> Column:
    return Column(
        *[Box(f"{tag}{i}", fill=Palette.blue.soft(), stroke=Palette.blue)
          for i in range(n)],
        gap="md",
    )


def _short_panel_margins(content_align: str) -> tuple[float, float, Theme]:
    """(top, bottom) blank band inside the SHORT panel of a peer row."""
    short = Panel("a", "short", _stack(2, "s"), content_align=content_align)
    tall = Panel("b", "tall", _stack(6, "t"))
    svg, theme = _render(Row(short, tall, gap="lg"))

    frames = [r for r in _rects(svg) if r["fill"] == "none" and "x" in r]
    frames.sort(key=lambda r: r["x"])
    frame = frames[0]
    fx0, fx1 = frame["x"], frame["x"] + frame["width"]
    cards = [r for r in _rects(svg)
             if r["fill"] not in ("none", "#ffffff") and "y" in r
             and fx0 < (r["x"] + r["width"] / 2) < fx1]
    assert cards, "short panel cards not found"
    cards.sort(key=lambda r: r["y"])

    pad = theme.panel_padding
    header_h = theme.text_height(theme.font_panel_title) + theme.unit * 1.4
    content_top = frame["y"] + pad + header_h
    content_bot = frame["y"] + frame["height"] - pad
    top = cards[0]["y"] - content_top
    bot = content_bot - (cards[-1]["y"] + cards[-1]["height"])
    return top, bot, theme


def test_auto_pins_structural_body_to_content_top():
    """The default keeps comparative panels sharing a first-row baseline."""
    top, bot, theme = _short_panel_margins("auto")
    assert top < theme.unit, f"structural body not pinned to top: {top}"
    assert bot > theme.unit * 2.0, f"expected surplus at the bottom: {bot}"


def test_center_splits_surplus_evenly():
    """An independent diagram centres: equal blank bands top and bottom."""
    top, bot, _theme = _short_panel_margins("center")
    assert abs(top - bot) < 1.0, (
        f"content not vertically centred: top={top}, bottom={bot}")
    assert top > 1.0, "centring produced no top band at all"


def test_end_pins_structural_body_to_content_bottom():
    top, bot, theme = _short_panel_margins("end")
    assert bot < theme.unit, f"structural body not pinned to bottom: {bot}"
    assert top > theme.unit * 2.0, f"expected surplus at the top: {top}"


def test_unrecognized_content_align_raises():
    with pytest.raises(ValueError, match="content_align"):
        Panel("a", "t", Box("x"), content_align="centre")  # en-GB spelling
