"""Justified rows, non-grid columns, flow lanes, slips and page margins.

* ``Row(justify=...)`` places the surplus of a stretched row (a name flush
  left, its note flush right) without spacers; justified rows share no
  grid columns.
* ``Column(share_columns=False)``: a title over a picture is not a grid,
  so a two-part title row is never stretched onto an unrelated row below.
* ``Column.flow_lanes`` / ``content_bbox`` and ``Row.flow_lanes``: a wire
  corridor reserved over a station's title is the station's outer lane,
  so sibling titles stay level -- also when the wired element is a small
  badge centred beside a taller title.
* ``Stripe(surface=..., outline=..., align=...)``: a slip.
* ``Document(padding=...)``: a sheet that carries a page of content.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (DEFAULT_THEME, Anchor, Badge, Box, Canvas, Column,
                    Connect, Diagram, Document, Palette, Row, Stripe, Text)
from sciviz.core._routing_context import routing_registry_stack


def _render(elem, theme=DEFAULT_THEME):
    canvas = Canvas(default_font_family=theme.font_family)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas


def _registry(body):
    reg: dict = {}
    token = routing_registry_stack.set([reg])
    try:
        Diagram.for_paper(body).render()
    finally:
        routing_registry_stack.reset(token)
    return reg


# -- Row justify -------------------------------------------------------------

def test_justify_between_puts_the_note_flush_right():
    t = DEFAULT_THEME
    row = Row(Anchor("name", Text("Sample batches")),
              Anchor("note", Text("every 2nd day")),
              justify="between", gap="xs")
    wide = Column(row, Box("a much wider sibling sets the width", width=260),
                  align="stretch", share_columns=False)
    reg = _registry(wide)
    name, note = reg["name"], reg["note"]
    assert name[0] < note[0]
    # The note ends where the stretched row ends (the sibling's width).
    assert note[0] + note[2] == pytest.approx(name[0] + 260.0, abs=0.6)


def test_justify_is_validated_and_start_is_the_default():
    with pytest.raises(ValueError):
        Row(Text("a"), justify="around")
    assert Row(Text("a")).justify == "start"
    # A justified row offers no grid columns to a stacked parent.
    assert Row(Text("a"), Text("b"),
               justify="between")._shared_column_widths(DEFAULT_THEME) == []


# -- Column share_columns ------------------------------------------------------

def test_title_row_is_not_stretched_onto_the_row_below():
    t = DEFAULT_THEME
    title = Row(Anchor("badge", Badge("1")), Anchor("title", Text("Title")),
                gap="xs")
    below = Row(Box("a wide first cell", width=120), Box("second", width=40),
                gap="xs")
    reg = _registry(Column(title, below, align="start", share_columns=False))
    badge, head = reg["badge"], reg["title"]
    # The title follows its badge at the row's own gap, not in a 120 px slot.
    assert head[0] - (badge[0] + badge[2]) < 10.0
    shared = _registry(Column(Row(Anchor("badge", Badge("1")),
                                  Anchor("title", Text("Title")), gap="xs"),
                              Row(Box("a wide first cell", width=120),
                                  Box("second", width=40), gap="xs"),
                              align="start"))
    assert shared["title"][0] > reg["title"][0]


# -- lanes ---------------------------------------------------------------------

def _station(title, name=None, on_badge=False):
    badge = Badge("n")
    text = Text(title, weight="700", size="label")
    if name and on_badge:
        badge = Anchor(name, badge)
    head = Row(badge, text, gap="xs", align="center")
    if name and not on_badge:
        head = Anchor(name, head)
    return Column(head, Box("picture", width=50, height=30), gap="sm",
                  align="start", share_columns=False)


@pytest.mark.parametrize("on_badge", [False, True])
def test_wired_station_titles_stay_level_with_their_neighbours(on_badge):
    body = Column(
        Row(Anchor("one", _station("One")),
            _station("Two", "two", on_badge),
            _station("Three", "three", on_badge), gap="md", align="start"),
        Connect("three", "two", src_side="top", dst_side="top",
                label="a caption"))
    reg = _registry(body)
    t = DEFAULT_THEME
    one_title_top = reg["one"][1]
    # The wired element's top: the title row, or the badge centred in it.
    two = reg["two"]
    three = reg["three"]
    assert two[1] == pytest.approx(three[1], abs=0.01)
    if not on_badge:
        assert two[1] == pytest.approx(one_title_top, abs=0.6)
    else:
        # The badge is centred on the title line: at most half the height
        # difference below the unwired title's top.
        diff = max(0.0, t.text_height("label") - Badge("n").measure(t).h) / 2
        assert two[1] == pytest.approx(one_title_top + diff, abs=0.8)


def test_column_content_box_excludes_its_end_lanes():
    head = Anchor("head", Text("Title"))
    col = Column(head, Box("x", width=20, height=20), gap="sm",
                 share_columns=False)
    t = DEFAULT_THEME
    assert col.flow_lanes(t) == (0.0, 0.0)
    assert col.content_bbox(t)[1] == 0.0
    head._bump_margin("top", 7.0)
    assert col.flow_lanes(t) == (7.0, 0.0)
    cx, cy, cw, ch = col.content_bbox(t)
    assert cy == pytest.approx(7.0)
    assert ch == pytest.approx(col.measure(t).h - 7.0)


def test_centred_row_reports_only_the_lane_overhang():
    t = DEFAULT_THEME
    badge = Anchor("b", Badge("5"))
    row = Row(badge, Text("Signal routing", size="title"), align="center")
    assert row.flow_lanes(t) == (0.0, 0.0)
    badge._bump_margin("top", 12.0)
    top, bottom = row.flow_lanes(t)
    # The badge is shorter than the title line; only the part of its lane
    # that reaches above the title counts.
    overhang = 12.0 - (t.text_height("title") - Badge("5").measure(t).h) / 2
    assert top == pytest.approx(max(0.0, overhang), abs=0.6)
    assert bottom == 0.0


# -- Stripe slips ----------------------------------------------------------------

def test_slip_paints_its_own_surface_without_a_frame():
    role = Palette.literal("#1f3f63")
    slip = Stripe(Text("temperature 21, period 0.7 s"), Text("measured"),
                  role=role, surface="white", outline=False, align="start")
    svg = _render(slip).to_svg(200, 40)
    rects = re.findall(r"<rect[^>]*/>", svg)
    assert any('fill="white"' in r or 'fill="#ffffff"' in r for r in rects)
    assert all('stroke="none"' in r or 'stroke=' not in r for r in rects)
    # Flush-left lines start at the same x.
    xs = re.findall(r'<text x="([\d.]+)"', svg)
    assert len(set(xs)) == 1


def test_default_stripe_keeps_its_tint_and_frame():
    role = Palette.literal("#1f3f63")
    svg = _render(Stripe(Text("a"), role=role)).to_svg(60, 20)
    assert re.search(r'<rect[^>]*stroke="#1f3f63"', svg)
    with pytest.raises(ValueError):
        Stripe(Text("a"), role=role, align="justify")


# -- Document page margin ----------------------------------------------------------

def test_document_padding_is_a_spacing_token():
    t = DEFAULT_THEME
    body = Column(Text("Parameters", weight="700"), Text("period 0.3-1.0 s"),
                  align="start")
    plain = Document(body, size="sm")
    page = Document(Column(Text("Parameters", weight="700"),
                           Text("period 0.3-1.0 s"), align="start"),
                    size="sm", padding="md")
    assert page.measure(t).w - plain.measure(t).w == pytest.approx(
        2 * (t.gap_px("md") - t.gap_px("sm")), abs=0.01)
    assert Document("x").padding == "sm"
