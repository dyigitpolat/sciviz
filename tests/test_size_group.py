"""``SizeGroup`` gives blocks in DIFFERENT parents one shared size.

Motivating case (thesis evidence ladder / assurance stack): one rung block
per row of a ``Table``. Each block auto-sizes to its own longest word, so
the column comes out ragged on both edges and five rungs of one ladder read
as five unrelated objects. ``MatchSize`` cannot help -- it only reaches
children it lays out itself, and these live one per table row.

The invariants checked here: every member renders at the widest member's
width, the widest member is not shrunk, both edges therefore align, the
group is idempotent under repeated measures, members that cannot grow are
left alone, and the equalization survives a ``Diagram``'s width fitting.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Column, Diagram, SizeGroup, Table, Text, Theme
from sciviz.core import Canvas


_RECT_RX = re.compile(r"<rect ([^/]+?)/>")


def _attr(raw: str, name: str, default=None):
    m = re.search(rf'{name}="([^"]+)"', raw)
    return m.group(1) if m else default


def _boxes(svg: str) -> list[dict]:
    """Every drawn rectangle except the canvas background."""
    out = []
    for m in _RECT_RX.finditer(svg):
        raw = m.group(1)
        if _attr(raw, "x") is None:
            continue                      # background rect has no x/y
        out.append({k: float(_attr(raw, k, "0"))
                    for k in ("x", "y", "width", "height")})
    return out


def _render(elem, theme=None):
    theme = theme or Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size, theme


def _ladder(group, *, gap="sm"):
    """A rung block per Table row: the shape the group has to reach into."""
    rows = [[group.add(Box(title=f"Rung {i}", label=name, wrap=True,
                           max_width=90.0, text_size="small")),
             Text(f"row {i}")]
            for i, name in enumerate(
                ["Algorithmic proxy", "Calibrated architecture simulator",
                 "Measured silicon"], start=1)]
    return Table(rows, col_align=("start", "start"), row_align="start",
                 gap_x=gap, gap_y=gap)


def test_axis_must_be_a_known_value():
    with pytest.raises(ValueError):
        SizeGroup(axis="diagonal")


def test_members_share_the_widest_width():
    theme = Theme()
    group = SizeGroup()
    widest = max(Box(title=f"Rung {i}", label=name, wrap=True, max_width=90.0,
                     text_size="small").measure(theme).w
                 for i, name in enumerate(
                     ["Algorithmic proxy", "Calibrated architecture simulator",
                      "Measured silicon"], start=1))
    svg, _, _ = _render(_ladder(group), theme)
    widths = {round(r["width"], 3) for r in _boxes(svg)}
    assert len(widths) == 1, f"ragged widths remain: {sorted(widths)}"
    assert abs(widths.pop() - widest) < 0.01, "the widest member was resized"


def test_both_edges_of_a_column_align():
    svg, _, _ = _render(_ladder(SizeGroup()))
    lefts = {round(r["x"], 3) for r in _boxes(svg)}
    rights = {round(r["x"] + r["width"], 3) for r in _boxes(svg)}
    assert len(lefts) == 1 and len(rights) == 1, (sorted(lefts), sorted(rights))


def test_without_the_group_the_same_column_is_ragged():
    """The regression this primitive exists for."""
    rows = [[Box(title=f"Rung {i}", label=name, wrap=True, max_width=90.0,
                 text_size="small"), Text(f"row {i}")]
            for i, name in enumerate(
                ["Algorithmic proxy", "Calibrated architecture simulator",
                 "Measured silicon"], start=1)]
    svg, _, _ = _render(Table(rows, col_align=("start", "start"),
                              row_align="start"))
    widths = {round(r["width"], 3) for r in _boxes(svg)}
    assert len(widths) > 1


def test_height_axis_equalises_heights_only():
    theme = Theme()
    group = SizeGroup(axis="height")
    svg, _, _ = _render(_ladder(group), theme)
    rects = _boxes(svg)
    assert len({round(r["height"], 3) for r in rects}) == 1
    assert len({round(r["width"], 3) for r in rects}) > 1


def test_both_axes_equalise_one_silhouette():
    svg, _, _ = _render(_ladder(SizeGroup(axis="both")))
    rects = _boxes(svg)
    assert len({round(r["width"], 3) for r in rects}) == 1
    assert len({round(r["height"], 3) for r in rects}) == 1


def test_group_is_idempotent_across_repeated_measures():
    theme = Theme()
    group = SizeGroup()
    ladder = _ladder(group)
    first = ladder.measure(theme)
    for _ in range(3):
        again = ladder.measure(theme)
    assert abs(again.w - first.w) < 1e-6 and abs(again.h - first.h) < 1e-6


def test_calling_the_group_is_the_same_as_add():
    group = SizeGroup()
    box = Box("a")
    member = group(box)
    assert member.child is box and group.members == [member]


def test_members_that_cannot_grow_are_left_at_their_natural_size():
    """Leaf text has no ``inflate_to``; the group must not break on it."""
    theme = Theme()
    group = SizeGroup()
    body = Column(group.add(Text("short")),
                  group.add(Box("a much wider block", text_size="small")),
                  gap="sm", align="start")
    svg, size, _ = _render(body, theme)
    assert size.w > 0
    assert len(_boxes(svg)) == 1


def test_equalisation_survives_a_diagram_width_fit():
    """The fitter measures throwaway copies; the printed tree must still
    come out equalised (and at the fitted geometry, not the trial one)."""
    group = SizeGroup()
    d = Diagram.for_paper(_ladder(group, gap="md"), target_width_pt=300.0,
                          chrome="none")
    svg = d.render()
    rects = [r for r in _boxes(svg) if r["width"] > 1.0]
    widths = {round(r["width"], 2) for r in rects}
    assert len(widths) == 1, f"ragged after fitting: {sorted(widths)}"


def test_two_groups_do_not_interfere():
    """Membership is per group: a figure may align several columns of
    blocks without collapsing them all onto one width."""
    theme = Theme()
    narrow, wide = SizeGroup(), SizeGroup()
    rows = [[narrow.add(Box("a", text_size="small")),
             wide.add(Box("a very much wider block indeed",
                          text_size="small"))],
            [narrow.add(Box("bb", text_size="small")),
             wide.add(Box("c", text_size="small"))]]
    svg, _, _ = _render(Table(rows, col_align=("start", "start"),
                              row_align="start"), theme)
    rects = sorted(_boxes(svg), key=lambda r: (r["y"], r["x"]))
    narrow_w = {round(rects[0]["width"], 3), round(rects[2]["width"], 3)}
    wide_w = {round(rects[1]["width"], 3), round(rects[3]["width"], 3)}
    assert len(narrow_w) == 1 and len(wide_w) == 1
    assert narrow_w.pop() < wide_w.pop()
