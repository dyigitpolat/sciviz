"""Body ports and inner-anchor landings.

* ``Element.port_bbox``: a wire lands on an element's drawing (a funnel's
  taper), not on the edge of the box widened by its own captions. The
  layout box stays the obstacle; only the tap moves, and a side whose own
  captions sit between body and layout edge keeps the layout box.
* ``Connect(..., dst_at=inner)``: the wire lands on the endpoint's frame,
  level with an inner anchor, and never crosses into the card.
"""
from __future__ import annotations

import pytest

from sciviz import (Anchor, Box, Column, Connect, Diagram, Funnel,
                    FunnelStage, Region, Row, Text)
from sciviz.composition._anchor import PORT_PREFIX
from sciviz.core._routing_context import routing_registry_stack
import sciviz.auto.router as R


@pytest.fixture
def routes(monkeypatch):
    out = []
    orig = R.render_orthogonal

    def spy(canvas, plan, **kw):
        out.append(list(plan.waypoints))
        return orig(canvas, plan, **kw)

    import sciviz.routing as RT
    monkeypatch.setattr(R, "render_orthogonal", spy)
    monkeypatch.setattr(RT, "render_orthogonal", spy)
    return out


def _render(body):
    reg: dict = {}
    token = routing_registry_stack.set([reg])
    try:
        Diagram.for_paper(body).render()
    finally:
        routing_registry_stack.reset(token)
    return reg


def _funnel(**kw):
    return Funnel([FunnelStage("drawn", 60), FunnelStage("kept", 10)],
                  orientation="horizontal", width=40, height=30,
                  label_position="none",
                  bypass="a much wider bypass caption", **kw)


def _last(routes, n):
    """The final render's ``n`` routes (the fitter renders trial passes)."""
    return routes[-n:]


def test_horizontal_funnel_wires_land_on_the_taper(routes):
    body = Column(Row(Anchor("pool", Box("pool")), Anchor("funnel", _funnel()),
                      Anchor("eval", Box("eval")), gap="md"),
                  Connect("pool", "funnel"), Connect("funnel", "eval"))
    reg = _render(body)
    fx, fy, fw, fh = reg["funnel"]
    ports = reg[PORT_PREFIX + "funnel"]
    lx = ports["left"][0]
    rx = ports["right"][0] + ports["right"][2]
    assert lx > fx + 5 and rx < fx + fw - 5   # caption widened the box
    into, out = _last(routes, 2)
    assert abs(into[-1][0] - lx) < 0.5
    assert abs(out[0][0] - rx) < 0.5
    # siblings centred on the taper: shares project onto the taper's
    # faces, so both links stay one straight segment
    assert len(into) == 2 and len(out) == 2
    # the first bend (if any) clears the funnel's layout box
    for (x, _y) in into[1:-1]:
        assert x <= fx + 0.5
    for (x, _y) in out[1:-1]:
        assert x >= fx + fw - 0.5


def test_side_with_own_caption_keeps_the_layout_box(routes):
    # The top of a horizontal funnel carries its bypass caption: a wire
    # arriving from above lands on the layout box, never cuts the text.
    body = Column(Anchor("src", Box("source")), Anchor("funnel", _funnel()),
                  Connect("src", "funnel", src_side="bottom", dst_side="top"),
                  gap="md")
    reg = _render(body)
    (path,) = _last(routes, 1)
    assert abs(path[-1][1] - reg["funnel"][1]) < 0.5


def test_plain_anchor_registers_no_port():
    reg = _render(Column(Anchor("a", Box("a")), Anchor("b", Box("b")),
                         Connect("a", "b"), gap="md"))
    assert not any(k.startswith(PORT_PREFIX) for k in reg)


@pytest.mark.parametrize("kw", [{}, {"label": "Stage"},
                                {"label": "Stage", "label_style": "tab"}])
def test_arrow_into_region_meets_its_frame(routes, kw):
    # The measured box also holds the region's margin and outside label;
    # the arrow tip must reach the drawn frame, not hang above it.
    region = Region(Box("a body wider than the region label"), **kw)
    body = Column(Anchor("src", Box("source")), Anchor("r", region),
                  Connect("src", "r", src_side="bottom", dst_side="top"),
                  gap="md")
    reg = _render(body)
    (path,) = _last(routes, 1)
    frame_top = reg[PORT_PREFIX + "r"]["top"][1]
    assert frame_top > reg["r"][1]
    assert abs(path[-1][1] - frame_top) < 0.5


def test_size_group_member_forwards_the_port():
    from sciviz import SizeGroup
    group = SizeGroup(axis="both", fit="slot")
    small = Region(Box("s"))
    wide = Region(Box("a much wider body"))
    body = Column(Anchor("src", Box("source")),
                  Row(Anchor("r", group.add(small)), group.add(wide),
                      gap="md"),
                  Connect("src", "r", src_side="bottom", dst_side="top"),
                  gap="md")
    reg = _render(body)
    port = reg[PORT_PREFIX + "r"]["top"]
    # The port is the small region's frame, placed where the slot put it.
    assert port[1] > reg["r"][1]
    assert port[2] < reg["r"][2]


def test_nested_anchor_forwards_the_port():
    reg = _render(Row(Anchor("outer", Anchor("inner", _funnel(),
                                             margin_left=6.0)),
                      Anchor("x", Box("x")), gap="md"))
    assert reg[PORT_PREFIX + "outer"]["left"] == reg[PORT_PREFIX + "inner"]["left"]


def _card(name, title, inner_name):
    return Anchor(name, Region(Column(Text(title, weight="700"),
                                      Anchor(inner_name, Box("badge")),
                                      gap="sm"), fill="white"))


def test_dst_at_lands_on_frame_level_with_inner_anchor(routes):
    body = Column(Row(Anchor("a", Box("source")), Box("spacer"), gap="lg"),
                  Row(Box("left"), _card("C", "Target card", "C_badge"),
                      gap="lg"),
                  Connect("a", "C", src_side="bottom", dst_side="top",
                          dst_at="C_badge"),
                  gap="lg")
    reg = _render(body)
    (path,) = _last(routes, 1)
    cx, cy, cw, ch = reg.get(PORT_PREFIX + "C", {}).get("top", reg["C"])
    bx, by, bw, bh = reg["C_badge"]
    hx, hy = path[-1]
    assert abs(hy - cy) < 0.5                       # on C's top frame
    assert abs(hx - (bx + bw / 2)) < 0.5            # level with the badge
    for (x1, y1), (x2, y2) in zip(path, path[1:]):  # never inside C
        assert max(y1, y2) <= cy + 0.5


def test_src_at_on_a_side(routes):
    body = Column(Row(_card("A", "Source card with a title", "A_row"),
                      Anchor("b", Box("dest")), gap="xl"),
                  Connect("A", "b", src_side="right", dst_side="left",
                          src_at="A_row"))
    reg = _render(body)
    (path,) = _last(routes, 1)
    ax, ay, aw, ah = reg.get(PORT_PREFIX + "A", {}).get("right", reg["A"])
    rx, ry, rw, rh = reg["A_row"]
    assert abs(path[0][0] - (ax + aw)) < 0.5
    assert ry <= path[0][1] <= ry + rh              # level with the row
    assert len(path) == 2                           # and straight


def test_vertical_funnel_side_with_bypass_caption_is_not_crossed(routes):
    # A vertical funnel's bypass caption sits on its left: a wire arriving
    # from the left must not cut through it to reach the taper.
    funnel = Funnel([FunnelStage("drawn", 60), FunnelStage("kept", 10)],
                    bypass="a much wider bypass caption than the taper")
    body = Column(Row(Anchor("pool", Box("pool")), Anchor("funnel", funnel),
                      gap="md"), Connect("pool", "funnel"))
    reg = _render(body)
    ports = reg.get(PORT_PREFIX + "funnel", {})
    assert ports.get("left_blocked")           # the caption guards the side
    assert "top" in ports and not ports.get("top_blocked")  # mouth is clear
    (path,) = _last(routes, 1)
    assert abs(path[-1][0] - reg["funnel"][0]) < 0.5


def test_dst_at_is_pinned_and_neighbours_nest_around_it(routes):
    card = Anchor("C", Region(Row(Anchor("C_left", Box("left part")),
                                  Anchor("C_right", Box("right part")),
                                  gap="md"), fill="white"))
    body = Column(Row(Anchor("a", Box("a")), Anchor("b", Box("b")),
                      Anchor("c", Box("c")), gap="xl"),
                  card,
                  Connect("a", "C", src_side="bottom", dst_side="top"),
                  Connect("b", "C", src_side="bottom", dst_side="top",
                          dst_at="C_right"),
                  Connect("c", "C", src_side="bottom", dst_side="top"),
                  gap="xl")
    reg = _render(body)
    paths = _last(routes, 3)
    ends = sorted(p[-1][0] for p in paths)
    assert all(b - a >= 3.0 for a, b in zip(ends, ends[1:]))
    # The pinned end lands inside C_right's extent; where that extent
    # overlaps the source the wire drops straight.
    rx, _ry, rw, _rh = reg["C_right"]
    pinned = [p for p in paths if rx <= p[-1][0] <= rx + rw]
    assert pinned, (ends, rx, rx + rw)
    segs = [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1])
            for p in paths for i in range(len(p) - 1)]
    for p in paths:
        own = [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1])
               for i in range(len(p) - 1)]
        others = [s for s in segs if s not in own]
        assert R._crossing_count(p, others, 0.5) == 0


def test_overlapping_pinned_ends_run_straight(routes):
    # Pinned extents that overlap need no jog: one vertical segment.
    top = Anchor("T", Region(Row(Anchor("T_a", Box("a")),
                                 Anchor("T_b", Box("second cell")),
                                 gap="md")))
    bottom = Anchor("B", Region(Row(
        Anchor("B_a", Box("a first cell wide enough to reach the second")),
        Anchor("B_b", Box("b")), gap="md")))
    body = Column(top, bottom,
                  Connect("T", "B", src_side="bottom", dst_side="top",
                          src_at="T_b", dst_at="B_a"),
                  gap="lg", align="start")
    reg = _render(body)
    (path,) = _last(routes, 1)
    assert len(path) == 2 and abs(path[0][0] - path[1][0]) < 0.5
    for name in ("T_b", "B_a"):
        x, _y, w, _h = reg[name]
        assert x <= path[0][0] <= x + w


def test_landings_follow_their_sources_and_straight_wire_drops(routes):
    # A wire that can drop straight keeps the point below its source;
    # one arriving from the right lands to its right, so none cross.
    body = Column(Row(Anchor("above", Box("directly above")),
                      Anchor("far", Box("far to the right")), gap="xl"),
                  Anchor("dst", Box("target")),
                  Connect("far", "dst", src_side="bottom", dst_side="top"),
                  Connect("above", "dst", src_side="bottom", dst_side="top"),
                  gap="lg", align="start")
    reg = _render(body)
    far_path, above_path = _last(routes, 2)
    assert len(above_path) == 2                         # straight drop
    assert far_path[-1][0] > above_path[-1][0] + 3.0    # lands to its right
    segs = [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1])
            for p in (far_path,) for i in range(len(p) - 1)]
    assert R._crossing_count(above_path, segs, 0.5) == 0


def test_straight_wire_steps_off_a_frame_tab(routes):
    # A pinned straight wire would meet the target's frame tab; it takes
    # the clear stretch of the overlap and lands on the frame itself.
    top = Anchor("T", Region(Anchor("T_a", Box("a source cell spanning wide")),
                             fill="white"))
    tabbed = Region(Anchor("B_a", Box("a target cell spanning wider still")),
                    label="Tab", label_style="tab")
    body = Column(top, Anchor("B", tabbed),
                  Connect("T", "B", src_side="bottom", dst_side="top",
                          src_at="T_a", dst_at="B_a"),
                  gap="lg", align="start")
    reg = _render(body)
    (path,) = _last(routes, 1)
    ports = reg[PORT_PREFIX + "B"]
    assert len(path) == 2                                   # straight
    assert not any(lo - 0.5 <= path[-1][0] <= hi + 0.5
                   for lo, hi in ports.get("top_blocked", ()))
    assert abs(path[-1][1] - ports["top"][1]) < 0.5         # on the frame
