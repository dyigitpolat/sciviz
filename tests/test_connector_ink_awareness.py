"""The connector subsystem must respect ALL rendered ink, not only anchors.

Locks in the arrow-routing overhaul:

1. The canvas keeps a per-item ink ledger with a ``kind`` tag, and
   ``free_text_rects`` filters out text already covered by an anchor.
2. Routed wires do not run through free-standing text (zone headers,
   captions) that was never wrapped in an ``Anchor``.
3. Labels are placed in a second phase, after every wire in the scope is
   drawn, so a label never straddles a wire that merely happened to be
   drawn later.
4. In a corridor walled on both sides, the label falls back to the
   schematic convention: centred ON its own wire with a background halo.
5. A vertically stacked source cluster feeding a sink above it gets a
   side rail; bus taps never strike through sibling endpoints.
"""
from __future__ import annotations

import re

from sciviz import Anchor, Box, Canvas, Column, Row, Spacer, Text, Theme
from sciviz.auto.ink import free_text_rects
from sciviz.auto.labels import LabelBox, place_polyline_label
from sciviz.composition import Bus, Flow, Flowed


def _render(elem) -> tuple[str, Canvas]:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), canvas


_LINE_RX = re.compile(r'<line ([^/>]*?)/>')
_ATTR_RX = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _lines(svg: str) -> list[tuple[float, float, float, float]]:
    out = []
    for m in _LINE_RX.finditer(svg):
        a = dict(_ATTR_RX.findall(m.group(1)))
        out.append((float(a["x1"]), float(a["y1"]),
                    float(a["x2"]), float(a["y2"])))
    return out


def _seg_hits_rect(seg, rect, shrink=0.5) -> bool:
    x0, y0, x1, y1 = rect
    x0 += shrink; y0 += shrink; x1 -= shrink; y1 -= shrink
    sx0, sx1 = sorted((seg[0], seg[2]))
    sy0, sy1 = sorted((seg[1], seg[3]))
    return not (sx1 <= x0 or sx0 >= x1 or sy1 <= y0 or sy0 >= y1)


# ---------------------------------------------------------------------------
# 1. ink ledger + free-text filtering
# ---------------------------------------------------------------------------

def test_canvas_ink_ledger_tags_text():
    canvas = Canvas()
    canvas.text(10, 20, "hello", size=10)
    canvas.rect(0, 0, 5, 5, fill="#000")
    text_items = canvas.ink_items("text")
    shape_items = canvas.ink_items("shape")
    assert len(text_items) == 1
    assert len(shape_items) == 1
    x0, y0, x1, y1 = text_items[0]
    assert x0 == 10 and x1 > x0 and y0 < 20 < y1


def test_free_text_rects_filters_anchor_interiors():
    canvas = Canvas()
    canvas.text(10, 20, "inside", size=10)     # inside the anchor below
    canvas.text(200, 20, "free", size=10)      # free-standing
    registry = {"card": (0.0, 0.0, 120.0, 40.0)}
    free = free_text_rects(canvas, registry)
    assert len(free) == 1
    assert free[0][0] >= 195.0


# ---------------------------------------------------------------------------
# 2. wires route around free-standing text
# ---------------------------------------------------------------------------

def test_routed_wire_avoids_free_text():
    header = Text("A FREE-STANDING HEADER", size="small", weight="700")
    body = Row(
        Anchor("a", Box("source", width=60, height=30)),
        Column(header, Spacer(1, 1), align="center"),
        Anchor("b", Box("sink", width=60, height=30)),
        gap="md", align="center",
    )
    flowed = Flowed(body, flows=[
        Flow("a", "b", src_side="right", dst_side="left"),
    ])
    svg, canvas = _render(flowed)
    # The header's ink rect (free text: not inside any anchor).
    header_rects = [r for r in canvas.ink_items("text")
                    if r[2] - r[0] > 60]      # the long header run
    assert header_rects, "expected the header's ink to be ledgered"
    for seg in _lines(svg):
        for rect in header_rects:
            assert not _seg_hits_rect(seg, rect), (
                f"wire segment {seg} runs through free text {rect}")


# ---------------------------------------------------------------------------
# 3. two-phase labels: a label sees wires drawn after its own flow
# ---------------------------------------------------------------------------

def test_label_avoids_wire_drawn_later():
    # Horizontal labeled flow declared FIRST; a vertical unlabeled flow
    # declared SECOND crosses the corridor where the label would sit.
    body = Column(
        Row(
            Anchor("a", Box("left", width=60, height=26)),
            Spacer(120, 1),
            Anchor("b", Box("right", width=60, height=26)),
            gap="none", align="center",
        ),
        Spacer(1, 8),
        Row(
            Spacer(96, 1),
            Anchor("c", Box("below", width=60, height=26)),
            gap="none", align="center",
        ),
        gap="md", align="start",
    )
    flowed = Flowed(body, flows=[
        Flow("a", "b", src_side="right", dst_side="left",
             label="labeled edge"),
        Flow("c", "a", src_side="top", dst_side="bottom"),
    ])
    svg, canvas = _render(flowed)
    # The caption may reach the canvas as one run or, when it was
    # wrapped to a narrow corridor, as one run per line. Either way no
    # run may straddle a wire.
    theme = Theme()
    runs = [(m.group(2), dict(_ATTR_RX.findall(m.group(1))))
            for m in re.finditer(r'<text ([^>]*)>([^<]*)</text>', svg)
            if m.group(2) in ("labeled edge", "labeled", "edge")]
    assert runs, "label missing"
    for text, attrs in runs:
        lx, ly = float(attrs["x"]), float(attrs["y"])
        fs = float(attrs["font-size"])
        lw = theme.text_width(text, fs)
        anchor = attrs.get("text-anchor", "start")
        x0 = lx - lw / 2 if anchor == "middle" else lx
        rect = (x0, ly - fs, x0 + lw, ly + fs * 0.35)
        for seg in _lines(svg):
            assert not _seg_hits_rect(seg, rect, shrink=0.0), (
                f"label rect {rect} straddles wire {seg}")


# ---------------------------------------------------------------------------
# 4. walled corridor -> inline label with halo
# ---------------------------------------------------------------------------

def test_inline_fallback_in_walled_corridor():
    label = LabelBox(text="corridor", width=44.0, height=10.0, size_px=8.0)
    path = [(0.0, 50.0), (200.0, 50.0)]
    walls = [
        (-50.0, 0.0, 250.0, 43.0),     # wall above the wire
        (-50.0, 57.0, 250.0, 100.0),   # wall below the wire
    ]
    placed = place_polyline_label(path, label, obstacles=walls,
                                  gap=6.0, wire_width=1.4)
    assert placed.inline, "expected the on-wire fallback"
    x0, y0, x1, y1 = placed.rect
    assert abs((y0 + y1) / 2 - 50.0) < 0.6      # centred on the wire
    assert x0 >= 0.0 and x1 <= 200.0            # within the leg


# ---------------------------------------------------------------------------
# 5. stacked bus sources get a side rail (no strike-through)
# ---------------------------------------------------------------------------

def test_bus_stacked_sources_use_side_rail():
    theme = Theme()
    canvas = Canvas()
    # One wide sink card above; five chips stacked vertically below it.
    registry = {
        "sink": (0.0, 0.0, 140.0, 60.0),
    }
    chips = []
    for i in range(5):
        rect = (30.0, 90.0 + i * 24.0, 80.0, 16.0)
        registry[f"c{i}"] = rect
        chips.append(rect)
    bus = Bus(sources=[f"c{i}" for i in range(5)], sinks="sink")
    bus._render(canvas, theme, registry)
    svg = canvas.to_svg(220, 240)
    segs = _lines(svg)
    assert segs, "bus drew nothing"
    for seg in segs:
        for rect in chips:
            x, y, w, h = rect
            assert not _seg_hits_rect(seg, (x, y, x + w, y + h)), (
                f"bus segment {seg} strikes through source chip {rect}")
    # Exactly one arrowhead enters the sink.
    arrow_count = len(re.findall(r'marker-end', svg))
    assert arrow_count == 1
