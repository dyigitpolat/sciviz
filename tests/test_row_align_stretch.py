"""``Row(align="stretch")`` should give side-by-side siblings a common outer
height and centre each inflated child in its enlarged content area.

Motivating case (AgentEvolve rebuttal, Figure 1): two ``Panel``\\ s sit in a
Row -- panel (a) holds a short reflective loop, panel (b) a tall 6-level
mapping. With ``align="center"`` the shorter panel's *border* stays short and
its content hugs the header, so the two framed boxes don't line up and a
feedback arc can overflow the cramped box. ``align="stretch"`` inflates the
short panel to the tall one's height (generic, no per-figure padding) and the
``Panel`` then centres its child in the taller box.
"""
from __future__ import annotations

import re

from sciviz import Box, Column, Palette, Panel, Row, Text, Theme
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


def _short_panel():
    return Panel("a", "Short", Box("one line", fill=Palette.blue.soft(),
                                   stroke=Palette.blue))


def _tall_panel():
    rows = Column(*[Box(f"level {i}", fill=Palette.amber.soft(),
                        stroke=Palette.amber) for i in range(6)],
                  gap="sm", align="start")
    return Panel("b", "Tall", rows)


def _panel_borders(svg: str) -> list[dict]:
    """Panel frames render as ``fill="none"`` rects; sort left-to-right."""
    borders = [r for r in _rects(svg) if r["fill"] == "none" and "x" in r]
    borders.sort(key=lambda r: r["x"])
    return borders


def test_center_leaves_panel_borders_unequal():
    """Baseline: without stretch the two panel frames have different heights
    (this is the behaviour ``align="stretch"`` is meant to fix)."""
    svg, _ = _render(Row(_short_panel(), _tall_panel(), gap="lg",
                         align="center"))
    borders = _panel_borders(svg)
    assert len(borders) == 2, f"expected 2 panel frames, got {borders}"
    short_h, tall_h = borders[0]["height"], borders[1]["height"]
    assert short_h < tall_h - 1.0, (
        f"expected unequal frames under align=center: {short_h} vs {tall_h}")


def test_stretch_equalises_panel_heights():
    """``align="stretch"`` grows the short panel to the tall panel's outer
    height; both frames share a top edge and a height."""
    svg, _ = _render(Row(_short_panel(), _tall_panel(), gap="lg",
                         align="stretch"))
    borders = _panel_borders(svg)
    assert len(borders) == 2, f"expected 2 panel frames, got {borders}"
    short, tall = borders
    assert abs(short["height"] - tall["height"]) < 0.5, (
        f"frame heights not equalised: {short['height']} vs {tall['height']}")
    assert abs(short["y"] - tall["y"]) < 0.5, (
        f"frames not top-aligned: y={short['y']} vs y={tall['y']}")


def test_stretch_centres_short_panel_child():
    """After inflation the short panel centres its child vertically in the
    content area below the header rule (equal top/bottom margins)."""
    short = _short_panel()
    svg, theme = _render(Row(short, _tall_panel(), gap="lg", align="stretch"))
    borders = _panel_borders(svg)
    frame = min(borders, key=lambda r: r["x"])  # left = short panel
    # The short panel's child is the soft-filled box inside the left frame
    # (located by geometry so the test is independent of the exact hex the
    # theme resolves ``Palette.blue.soft()`` to).
    fx0, fx1 = frame["x"], frame["x"] + frame["width"]
    child = [r for r in _rects(svg)
             if r["fill"] not in ("none", "#ffffff") and "y" in r
             and fx0 < (r["x"] + r["width"] / 2) < fx1]
    assert child, "short panel child rect not found"
    c = child[0]
    pad = theme.panel_padding
    header_h = theme.text_height(theme.font_panel_title) + theme.unit * 1.4
    content_top = frame["y"] + pad + header_h
    content_bot = frame["y"] + frame["height"] - pad
    top_margin = c["y"] - content_top
    bot_margin = content_bot - (c["y"] + c["height"])
    assert top_margin > 1.0, (
        f"child not pushed below header into a taller box (top={top_margin})")
    assert abs(top_margin - bot_margin) < 1.0, (
        f"child not vertically centred: top={top_margin}, bot={bot_margin}")
