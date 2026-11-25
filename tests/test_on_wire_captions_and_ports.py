"""Connector ports and on-wire captions.

* ``Connect(..., ports="facing")``: an end attaches in the half of its
  side that faces the other end.
* ``Connect(..., label_style="on-wire")``: the caption rides centred on
  its own wire (over a page-coloured halo), so a lane costs one caption
  height, not two. Stacked on-wire lanes keep a caption's height apart
  (the router's ``lane_room``), and a same-side U route whose stubs were
  sized for the caption runs its bridge in that reserved lane (``hug``)
  instead of a step further out.
* The router's bridge choice judges every clean candidate: within
  ``_MAX_DETOUR_RATIO`` of the shortest, fewest crossings, then the
  generators' preference order -- no excursion for a far edge lane.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Row
from sciviz.composition._flow import Flow, _facing_fraction
from sciviz.core._routing_context import routing_registry_stack
import sciviz.auto.router as R


def _render(body):
    reg: dict = {}
    token = routing_registry_stack.set([reg])
    try:
        svg = Diagram.for_paper(body).render()
    finally:
        routing_registry_stack.reset(token)
    return svg, reg


def _paths(svg):
    """Every routed wire as a polyline (its segments chained end to start)."""
    segs = [tuple(float(v) for v in m) for m in re.findall(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" '
        r'y2="([-\d.]+)"', svg)]
    out = []
    for x1, y1, x2, y2 in segs:
        if out and abs(out[-1][-1][0] - x1) < 0.01 \
                and abs(out[-1][-1][1] - y1) < 0.01:
            out[-1].append((x2, y2))
        else:
            out.append([(x1, y1), (x2, y2)])
    return out


def _captions(svg):
    return [(float(x), float(y), text) for x, y, text in re.findall(
        r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]+)</text>', svg)]


def _three_cards(**connect):
    return Column(
        Row(Anchor("a", Box("source card", width=60, height=30)),
            Box("a card in the way", width=120, height=30),
            Anchor("b", Box("target card", width=60, height=30)), gap="lg"),
        Connect("a", "b", src_side="top", dst_side="top", **connect))


def test_facing_ports_attach_on_the_partners_side():
    own = (0.0, 0.0, 100.0, 20.0)
    assert _facing_fraction(own, "top", (200.0, 0.0, 50.0, 20.0)) > 0.5
    assert _facing_fraction(own, "top", (-90.0, 0.0, 50.0, 20.0)) < 0.5
    # An overlapping partner leaves the port centred.
    assert _facing_fraction(own, "top", (50.0, 40.0, 100.0, 20.0)) == 0.5
    with pytest.raises(ValueError):
        Flow("a", "b", ports="sideways")
    with pytest.raises(ValueError):
        Flow("a", "b", label_style="floating")


def test_facing_port_leaves_from_the_partners_half_of_the_card():
    centred, reg_c = _render(_three_cards())
    facing, reg_f = _render(_three_cards(ports="facing"))
    a = reg_f["a"]
    start_c = _paths(centred)[0][0]
    start_f = _paths(facing)[0][0]
    assert start_c[0] == pytest.approx(a[0] + a[2] / 2, abs=0.6)
    assert start_f[0] > a[0] + a[2] / 2 + 1.0


def test_on_wire_caption_is_centred_on_its_own_run():
    svg, _reg = _render(_three_cards(label="a caption on the wire",
                                     label_style="on-wire"))
    (x, y, text), = [c for c in _captions(svg) if "caption" in c[2]]
    run_ys = [p0[1] for path in _paths(svg) for p0, p1 in zip(path, path[1:])
              if abs(p0[1] - p1[1]) < 0.01 and abs(p0[0] - p1[0]) > 20]
    assert run_ys
    # The baseline sits about a third of the type size below the wire.
    assert min(abs(y - ry) for ry in run_ys) < 4.0


def test_on_wire_lane_hugs_the_reserved_stub_lane():
    """The same wire labelled beside its run takes a lane a step further
    out; on the wire, it runs in the corridor its stubs reserved."""
    def rise(**kw):
        svg, reg = _render(_three_cards(label="a caption on the wire", **kw))
        path = _paths(svg)[0]
        return reg["a"][1] - min(p[1] for p in path)
    beside, inline = rise(), rise(label_style="on-wire")
    # Both run above the cards; the on-wire one no further out.
    assert 0.0 < inline < beside


def test_stacked_on_wire_lanes_keep_a_caption_height_apart():
    body = Column(
        Row(Anchor("a", Box("source", width=60, height=30)),
            Box("a card in the way", width=140, height=30),
            Anchor("b", Box("near target", width=60, height=30)),
            Anchor("c", Box("far target", width=60, height=30)), gap="lg"),
        Connect("a", "b", src_side="top", dst_side="top",
                label="the inner caption", label_style="on-wire"),
        Connect("a", "c", src_side="top", dst_side="top",
                label="the outer caption", label_style="on-wire"))
    svg, _reg = _render(body)
    caps = {t: y for x, y, t in _captions(svg)}
    runs = sorted(min(p[1] for p in path) for path in _paths(svg))
    assert len(runs) >= 2
    theme = Diagram.for_paper(body).theme
    line = theme.text_height(theme.connector_label_size)
    assert abs(runs[1] - runs[0]) >= line - 0.5
    # Both captions found a place on their own wires.
    assert abs(caps["the inner caption"] - caps["the outer caption"]) \
        >= line - 0.5


def test_best_bridge_prefers_the_proportionate_lane(monkeypatch):
    """A far edge lane that happens to be clean is never taken over a
    near lane of equal crossings: bridges past _MAX_DETOUR_RATIO of the
    shortest clean one are ineligible."""
    svg, reg = _render(_three_cards(label="caption"))
    path = _paths(svg)[0]
    a, b = reg["a"], reg["b"]
    height = max(p[1] for p in path) - min(p[1] for p in path)
    assert height < 3.0 * (a[3] + b[3])
    assert R._MAX_DETOUR_RATIO >= 1.0


def test_on_wire_caption_leaves_visible_wire_on_both_sides():
    """A caption nearly as long as its leg is not set on the wire (the halo
    would hide the whole leg); a short one is, with a stub each side."""
    from sciviz.auto.labels import (LabelBox, on_wire_fits, on_wire_stub,
                                    _place_inline)
    gap = 1.8
    leg = [(0.0, 0.0), (108.0, 0.0)]
    own = [(0.0, -0.5, 108.0, 0.5)]
    assert not on_wire_fits(108.0, 105.0, gap)
    wide = LabelBox(text="x" * 20, width=105.0, height=7.0, size_px=6.5)
    assert _place_inline(leg, own, wide, [], gap) is None
    short = LabelBox(text="x" * 8, width=40.0, height=7.0, size_px=6.5)
    placed = _place_inline(leg, own, short, [], gap)
    assert placed is not None and placed.inline
    stub = on_wire_stub(108.0, gap)
    x0, _, x1, _ = placed.rect
    assert x0 >= stub - 1e-6 and 108.0 - x1 >= stub - 1e-6


def test_document_valign_start_keeps_content_at_the_top_when_stretched():
    from sciviz import Document, Text
    from sciviz.core._theme import DEFAULT_THEME as T
    for valign, top in (("start", True), ("center", False)):
        doc = Document(Text("heading"), valign=valign, padding="sm")
        doc.inflate_to(min_h=200.0)
        seen = []
        doc.label.render = lambda c, x, y, t, _s=seen: _s.append(y)
        doc.render(_FakeCanvas(), 0.0, 0.0, T)
        assert (seen[0] < 20.0) == top


class _FakeCanvas:
    def __getattr__(self, name):
        return lambda *a, **k: None


def test_region_tab_clears_the_rounded_corner():
    """A tab set at the end of a wide double-walled band starts past the
    corner arc by at least half its plate height, so its rounded end never
    merges with the rounded corner."""
    from sciviz import DEFAULT_THEME, Region

    theme = DEFAULT_THEME
    reg = Region(Box("x" * 60), border="double", label="Membrane tab",
                 label_style="tab", label_position="top", label_align="end")
    bw, bh = 400.0, 60.0
    radius = reg._corner_radius(theme, bw, bh)
    _tw, th = reg._tab_size(theme, "top")
    inset = reg._tab_inset(theme, radius, th)
    assert inset >= radius + reg._wall(theme) + th / 2.0 - 1e-9
    # The border reserves room for both insets around the tab.
    b = reg.measure(theme)
    assert b.w >= reg._tab_size(theme, "top")[0] + 2 * inset - 1e-6
