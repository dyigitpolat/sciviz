"""A fan-in ``Bus`` (many sources, one sink) should render as a **junction**:

  * vertical tap from each source up to a shared horizontal bar,
  * a SINGLE arrow from the centre of the bar to the sink (with arrowhead),
  * an optional label that sits *beside* the bar/arrow, not on top.

The original DeepSeek concatenation figure is the target: two RMSNorm
blocks merge into a Linear Projection via a small "T" with the word
``concatenation`` tucked to the side.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Row, Column, Theme, Canvas, Spacer)
from sciviz.composition import Bus, Flowed


def _render(body, flows, theme: Theme | None = None) -> tuple[str, float, float]:
    theme = theme or Theme()
    d = Flowed(body, flows=flows)
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


_LINE_RX = re.compile(
    r'<line ([^/>]*?)/>'
)

_ATTR_RX = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _parse_lines(svg: str) -> list[dict]:
    lines = []
    for m in _LINE_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        out = {
            "x1": float(attrs["x1"]),
            "y1": float(attrs["y1"]),
            "x2": float(attrs["x2"]),
            "y2": float(attrs["y2"]),
            "marker_end": attrs.get("marker-end"),
            "dasharray": attrs.get("stroke-dasharray"),
        }
        lines.append(out)
    return lines


def test_fan_in_bus_has_exactly_one_arrow_into_sink():
    """Two sources, one sink: only ONE arrow-terminated line segment
    enters the sink (the final stem from the bar to the sink)."""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    arrow_lines = [l for l in lines if l["marker_end"]]
    assert len(arrow_lines) == 1, (
        f"expected 1 arrow line (bar -> sink), got {len(arrow_lines)}")


def test_fan_in_bus_label_does_not_cross_bar():
    """The label must sit clear of every bus line -- taps, bar, and sink
    arrow -- as a 2-D rectangle check. (Historically this test asserted
    1-D x-separation from the sink arrow, which also outlawed the ideal
    placement: the clean pocket centred directly *below* the bar. The
    two-ring placer now finds that pocket, so the assertion checks the
    real property: no label/wire intersection.)"""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    assert len([l for l in lines if l["marker_end"]]) == 1
    # find the "concatenation" label
    m = re.search(
        r'<text ([^>]*?)>concatenation</text>', svg)
    assert m, svg
    attrs = dict(_ATTR_RX.findall(m.group(1)))
    lx = float(attrs["x"])
    ly = float(attrs["y"])
    fs = float(attrs["font-size"])
    lw = theme.text_width("concatenation", fs)
    anchor = attrs.get("text-anchor", "start")
    if anchor == "middle":
        lx0, lx1 = lx - lw / 2, lx + lw / 2
    elif anchor == "end":
        lx0, lx1 = lx - lw, lx
    else:
        lx0, lx1 = lx, lx + lw
    ly0, ly1 = ly - fs, ly + fs * 0.35
    for line in lines:
        sx0, sx1 = sorted((line["x1"], line["x2"]))
        sy0, sy1 = sorted((line["y1"], line["y2"]))
        assert (lx1 <= sx0 or lx0 >= sx1 or ly1 <= sy0 or ly0 >= sy1), (
            f"label rect ({lx0}, {ly0}, {lx1}, {ly1}) crosses "
            f"bus line {line}")


def test_fan_in_bus_has_horizontal_bar_between_sources():
    """A horizontal bar spans above the two sources and is the common
    meeting point; the sink-arrow starts on that bar."""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    horizontals = [l for l in lines
                   if abs(l["y1"] - l["y2"]) < 0.01 and abs(l["x2"] - l["x1"]) > 5]
    assert horizontals, "no horizontal bar found"
