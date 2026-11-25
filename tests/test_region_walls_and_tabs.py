"""Region walls: double borders, tab labels on a wall, open sides.

A double wall marks a boundary (a membrane, a trust boundary) rather than a
grouping; a tab sets the region's name on its wall; an open side makes a
tray that holds titled stages without pushing their titles below their
neighbours'. Every variant keeps its ink inside the measured box.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (DEFAULT_THEME, Anchor, Box, Canvas, Column, Connect,
                    Diagram, Region, Row, Text)


def _ink(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas


def _inside(elem, theme=DEFAULT_THEME, slack=0.8):
    """Walls and plates within the box, up to half a stroke; text within
    it up to the canvas's conservative glyph-ascent estimate."""
    b = elem.measure(theme)
    canvas = _ink(elem, theme)
    for kind, pad in (("shape", slack), ("text", slack + 1.0)):
        for x0, y0, x1, y1 in canvas.ink_items(kind):
            if not (x0 >= -pad and y0 >= -pad
                    and x1 <= b.w + pad and y1 <= b.h + pad):
                return False
    return True


def test_double_wall_draws_two_nested_rectangles():
    region = Region(Text("membrane"), border="double", dashed=False,
                    margin_x=0.0, margin_y=0.0)
    svg = _ink(region).to_svg(200, 100)
    rects = re.findall(r"<rect[^>]*?/>", svg)
    framed = [r for r in rects if 'stroke="' in r and 'stroke="none"' not in r]
    assert len(framed) == 2
    assert _inside(region)
    # The content keeps its clearance from the INNER wall.
    single = Region(Text("membrane"), dashed=False, margin_x=0.0, margin_y=0.0)
    assert region.measure(DEFAULT_THEME).w > single.measure(DEFAULT_THEME).w


def test_tab_label_sits_on_the_wall_inside_the_box():
    for position in ("top", "bottom"):
        region = Region(Text("content line"), label="Cell Membrane",
                        label_style="tab", label_position=position,
                        dashed=False, margin_x=0.0, margin_y=0.0)
        assert _inside(region)
        # A tab adds half its height outside the wall, not a label strip.
        outside = Region(Text("content line"), label="Cell Membrane",
                         label_position=position, dashed=False,
                         margin_x=0.0, margin_y=0.0)
        assert (region.measure(DEFAULT_THEME).h
                < outside.measure(DEFAULT_THEME).h + DEFAULT_THEME.text_height(
                    "label"))


def test_tabs_on_both_walls_and_element_labels():
    name = Text("Cell interior", weight="700")
    gloss = Text("ions and gradients", color="muted")
    region = Region(Text("x"), tabs={"top": name, "bottom": gloss},
                    tab_align={"top": "start", "bottom": "center"},
                    dashed=False, margin_x=0.0, margin_y=0.0)
    assert _inside(region)
    # The box is at least as wide as its widest tab.
    assert region.measure(DEFAULT_THEME).w >= gloss.measure(DEFAULT_THEME).w
    texts = re.findall(r">([^<>]+)</text>", _ink(region).to_svg(300, 100))
    assert "Cell interior" in texts and "ions and gradients" in texts


def test_tab_without_outline_is_a_plain_knockout():
    plate = Region(Text("x"), label="name", label_style="tab",
                   dashed=False, margin_x=0.0, margin_y=0.0)
    plain = Region(Text("x"), label="name", label_style="tab",
                   dashed=False, margin_x=0.0, margin_y=0.0, tab_outline=False)
    def framed(region):
        rects = re.findall(r"<rect[^>]*?/>", _ink(region).to_svg(100, 50))
        return sum(1 for r in rects if 'stroke="none"' not in r
                   and 'stroke="' in r)
    assert framed(plate) == framed(plain) + 1


def test_invalid_wall_options_are_rejected():
    with pytest.raises(ValueError):
        Region(Text("x"), border="triple")
    with pytest.raises(ValueError):
        Region(Text("x"), label="a", label_style="tab", label_position="left")
    with pytest.raises(ValueError):
        Region(Text("x"), tabs={"left": "a"})
    with pytest.raises(ValueError):
        Region(Text("x"), label="a", label_style="tab", tabs={"top": "b"})
    with pytest.raises(ValueError):
        Region(Text("x"), open_side="middle")
    with pytest.raises(ValueError):
        Region(Text("x"), open_side="top", border="double")
    with pytest.raises(ValueError):
        Region(Text("x"), open_side="bottom", label="a", label_style="tab",
               label_position="bottom")


def test_open_side_draws_three_walls_and_no_clearance_there():
    closed = Region(Text("stage"), dashed=False, margin_x=0.0, margin_y=0.0)
    tray = Region(Text("stage"), dashed=False, margin_x=0.0, margin_y=0.0,
                  open_side="top")
    theme = DEFAULT_THEME
    # No clearance on the open side: the tray is one pad shorter and its
    # content starts at its top edge.
    assert tray.measure(theme).h == pytest.approx(
        closed.measure(theme).h - tray._py(theme))
    assert tray.content_bbox(theme)[1] == pytest.approx(0.0)
    svg = _ink(tray).to_svg(100, 50)
    # The walls are one open path, not a closed rectangle.
    assert re.search(r"<path[^>]*d=\"M [^\"]*Q[^\"]*Q[^\"]*\"", svg)
    assert not [r for r in re.findall(r"<rect[^>]*?/>", svg)
                if 'stroke="none"' not in r and 'stroke="' in r]
    assert _inside(tray)


def test_open_top_tray_keeps_wired_titles_level_with_siblings():
    """Stations inside an open-top tray line their titles up with a
    station outside it, even when a wire lane sits above a tray title."""
    def station(title, name=None):
        head = Text(title, weight="700")
        if name:
            head = Anchor(name, head)
        return Column(head, Box("picture", width=40, height=30), gap="sm",
                      align="start", share_columns=False)
    tray = Region(Row(station("Two"), station("Three", "three"), gap="md",
                      align="start"),
                  dashed=False, margin_x=0.0, margin_y=0.0, pad_x=2.0,
                  pad_y=2.0, open_side="top")
    body = Column(Row(Anchor("one", station("One")), tray, gap="md",
                      align="start"),
                  Connect("three", "one", src_side="top", dst_side="top",
                          label="measured"))
    d = Diagram.for_paper(body)
    reg: dict = {}
    from sciviz.core._routing_context import routing_registry_stack
    token = routing_registry_stack.set([reg])
    try:
        d.render()
    finally:
        routing_registry_stack.reset(token)
    one_top = reg["one"][1]
    three_top = reg["three"][1]
    # "one" is the whole station column (its title is its top line).
    assert three_top == pytest.approx(one_top, abs=0.6)
