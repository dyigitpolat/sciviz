"""A funnel's wires leave through its outlet and arrive through its mouth.

The faces a connector lands on at the funnel's two ends are the openings
of the flow (the neck at the narrow end, the first stage at the wide
end), not the whole taper box, so a wire leaves from the outlet's centre
instead of from a corner of the taper.
"""

from __future__ import annotations

import pytest

from sciviz import (Anchor, Box, Column, Connect, DEFAULT_THEME, Diagram,
                    Funnel, FunnelStage, Row)
from sciviz.auto.debug import DebugRecorder, record_into


def _funnel(orientation="horizontal", bypass=None):
    return Funnel([FunnelStage("in", 60, marks=["#1f3b5c"] * 20),
                   FunnelStage("out", 10, marks=["#1f3b5c"] * 6)],
                  orientation=orientation, width=48, height=34,
                  show_values=False, label_position="none",
                  neck_ratio=0.3, bypass=bypass)


@pytest.mark.parametrize("orientation,outlet,inlet",
                         [("horizontal", "right", "left"),
                          ("vertical", "bottom", "top")])
def test_outlet_and_mouth_faces_are_the_flow_openings(orientation, outlet,
                                                      inlet):
    f = _funnel(orientation)
    t = DEFAULT_THEME
    cx, cy, cw, ch = f.content_bbox(t)
    extents = f._geometry(t)[1]
    for side, span in ((outlet, extents[-1]), (inlet, extents[0])):
        x, y, w, h = f.port_bbox(t, side)
        if orientation == "horizontal":
            assert h == pytest.approx(span)
            assert y + h / 2 == pytest.approx(cy + ch / 2)
            assert (x, w) == pytest.approx((cx, cw))
        else:
            assert w == pytest.approx(span)
            assert x + w / 2 == pytest.approx(cx + cw / 2)
            assert (y, h) == pytest.approx((cy, ch))
    # The long sides still land on the whole taper.
    other = "top" if orientation == "horizontal" else "left"
    assert f.port_bbox(t, other) == pytest.approx((cx, cy, cw, ch))


def test_wire_leaves_from_the_outlet_centre():
    """A neighbour level with the outlet gets one straight wire at the
    outlet's centre line (the old taper-box face put it at the corner)."""
    f = _funnel(bypass="bypass")
    body = Column(Row(Anchor("f", f), Anchor("n", Box("next")), gap="lg",
                      align="center"),
                  Connect("f", "n", src_side="right", dst_side="left"))
    rec = DebugRecorder()
    with record_into(rec):
        Diagram.for_paper(body).render()
    (route,) = rec.router_paths
    boxes = dict(route.anchors)
    fx0, fy0, fx1, fy1 = boxes["f"]
    t = DEFAULT_THEME
    lx, ly, lw, lh = f.port_bbox(t, "right")
    outlet_centre = fy0 + ly + lh / 2
    ys = {round(p[1], 1) for p in route.waypoints}
    assert len(ys) == 1, route.waypoints
    assert ys.pop() == pytest.approx(outlet_centre, abs=0.6)


def test_bypass_lands_clear_of_the_outlet():
    """The bypass arc ends on the neck's edge at its middle, a clearance
    away from the outlet end where the outgoing wire starts."""
    import re
    from sciviz import Canvas
    f = _funnel(bypass="bypass")
    t = DEFAULT_THEME
    canvas = Canvas()
    f.render(canvas, 0.0, 0.0, t)
    size = f.measure(t)
    svg = canvas.to_svg(size.w, size.h)
    (d,) = [m.group(1) for m in re.finditer(r'<path ([^>]*)>', svg)
            if "1.6,1.2" in m.group(1)]
    end_x, end_y = map(float, re.findall(r"([-\d.]+),([-\d.]+)",
                                         re.search(r'(?:^|\s)d="([^"]+)"', d)
                                         .group(1))[-1])
    cx, cy, cw, ch = f.content_bbox(t)
    taper = f._geometry(t)[2]
    extents = f._geometry(t)[1]
    assert cx + taper <= end_x <= cx + cw - t.unit * 0.5
    assert end_y == pytest.approx(cy + ch / 2 - extents[-1] / 2, abs=0.01)


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_bypass_leaves_a_bracket_over_the_whole_mouth(orientation):
    """The bypass steps the whole inlet aside, so it starts from a bracket
    that spans every lane of the mouth, before the mouth and inside the
    funnel's box, not from the lane nearest the arc."""
    import re
    from sciviz import Canvas
    f = _funnel(orientation, bypass="bypass")
    t = DEFAULT_THEME
    canvas = Canvas()
    f.render(canvas, 0.0, 0.0, t)
    size = f.measure(t)
    svg = canvas.to_svg(size.w, size.h)
    paths = [re.search(r'(?:^|\s)d="([^"]+)"', m.group(1)).group(1)
             for m in re.finditer(r'<path ([^>]*)>', svg)]
    brackets = [d for d in paths if d.count("L") == 3 and "C" not in d]
    assert brackets
    pts = [tuple(map(float, p)) for p in
           re.findall(r"([-\d.]+),([-\d.]+)", brackets[-1])]
    cx, cy, cw, ch = f.content_bbox(t)
    mouth = f._geometry(t)[1][0]
    if orientation == "horizontal":
        across = [p[1] for p in pts]
        along = [p[0] for p in pts]
        mid, before = cy + ch / 2, max(along) <= cx
    else:
        across = [p[0] for p in pts]
        along = [p[1] for p in pts]
        mid, before = cx + cw / 2, max(along) <= cy
    assert max(across) - min(across) == pytest.approx(mouth, abs=0.01)
    assert (max(across) + min(across)) / 2 == pytest.approx(mid, abs=0.01)
    assert before and min(along) >= 0.0
    # the arc starts where the bracket's spine begins
    arc = [d for d in paths if "C" in d][-1]
    start = tuple(map(float, re.findall(r"([-\d.]+),([-\d.]+)", arc)[0]))
    assert start == pytest.approx(pts[1], abs=0.01)


def test_outlet_bypass_spans_the_whole_selection():
    """``bypass_to="outlet"``: the arc leaves the bracket at the mouth's
    centre line and lands on the outlet's own end (not over the kept
    members at the neck's middle), inside the funnel's box."""
    import re
    from sciviz import Canvas
    f = Funnel([FunnelStage("in", 60, marks=["#1f3b5c"] * 20),
                FunnelStage("out", 10, marks=["#1f3b5c"] * 6)],
               orientation="horizontal", width=48, height=34,
               show_values=False, label_position="none", neck_ratio=0.3,
               bypass="bypass", bypass_to="outlet")
    t = DEFAULT_THEME
    canvas = Canvas()
    f.render(canvas, 0.0, 0.0, t)
    size = f.measure(t)
    svg = canvas.to_svg(size.w, size.h)
    (d,) = [re.search(r'(?:^|\s)d="([^"]+)"', m.group(1)).group(1)
            for m in re.finditer(r'<path ([^>]*)>', svg)
            if "1.6,1.2" in m.group(1)]
    pts = [tuple(map(float, p)) for p in re.findall(r"([-\d.]+),([-\d.]+)", d)]
    cx, cy, cw, ch = f.content_bbox(t)
    extents = f._geometry(t)[1]
    start, end = pts[0], pts[-1]
    assert start[1] == pytest.approx(cy + ch / 2, abs=0.01)   # mouth centre
    assert start[0] < cx                                      # before the mouth
    assert end[0] == pytest.approx(cx + cw, abs=0.01)         # the outlet end
    assert end[1] == pytest.approx(cy + ch / 2 - extents[-1] / 2, abs=0.01)
    assert min(p[0] for p in pts) >= 0.0
    with pytest.raises(ValueError):
        Funnel([FunnelStage("a", 2), FunnelStage("b", 1)], bypass_to="side")
