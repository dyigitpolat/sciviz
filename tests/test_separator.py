"""Tests for :class:`sciviz.Separator` and its stretch plumbing in Row/Column."""

from __future__ import annotations

import pytest

from sciviz import Canvas, Column, DEFAULT_THEME, Row, Separator, Box


def test_horizontal_separator_fixed_length():
    s = Separator(length=100.0)
    b = s.measure(DEFAULT_THEME)
    assert b.w == 100.0
    assert b.h > 0


def test_vertical_separator_fixed_length():
    s = Separator(length=80.0, orientation="vertical")
    b = s.measure(DEFAULT_THEME)
    assert b.h == 80.0
    assert b.w > 0


def test_separator_dashed_emits_dasharray():
    s = Separator(length=50.0, style="dashed")
    c = Canvas()
    s.render(c, 0, 0, DEFAULT_THEME)
    assert 'stroke-dasharray="4,3"' in c.to_svg(100, 100)


def test_separator_dotted_emits_dasharray():
    s = Separator(length=50.0, style="dotted")
    c = Canvas()
    s.render(c, 0, 0, DEFAULT_THEME)
    assert 'stroke-dasharray="1,2"' in c.to_svg(100, 100)


def test_separator_rejects_bad_style():
    with pytest.raises(ValueError):
        Separator(style="zigzag")


def test_separator_rejects_bad_orientation():
    with pytest.raises(ValueError):
        Separator(orientation="diagonal")


def test_horizontal_separator_stretches_in_column():
    col = Column(
        Box("Wide header", width=240),
        Separator(),
        Box("A", width=60),
    )
    bbox = col.measure(DEFAULT_THEME)
    canvas = Canvas()
    col.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(bbox.w + 20, bbox.h + 20)
    # The separator should have extended to the column's full width (240),
    # which is the widest child. Find the <line> emitted by the separator.
    # The box borders emit <rect>, the separator emits <line>.
    lines = [l for l in canvas._body if l.startswith("<line")]
    assert lines, "separator should have rendered a <line>"
    line = lines[0]
    assert 'x1="0"' in line
    assert 'x2="240"' in line


def test_vertical_separator_stretches_in_row():
    row = Row(
        Box("A", width=40, height=50),
        Separator(orientation="vertical"),
        Box("B", width=40, height=80),
    )
    bbox = row.measure(DEFAULT_THEME)
    canvas = Canvas()
    row.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    lines = [l for l in canvas._body if l.startswith("<line")]
    # The vertical separator should span the row's full content height
    # (~80, the tallest child). It may not be the only <line> if Row adds
    # any of its own (it doesn't), so find one with matching y-span.
    tall = [l for l in lines
            if abs(float(_attr(l, "y1")) - 0.0) < 1e-3
            and abs(float(_attr(l, "y2")) - bbox.h) < 1e-3]
    assert tall, f"no vertical separator line spanning row height; lines={lines}"


def _attr(svg: str, name: str) -> str:
    import re
    m = re.search(rf'{name}="([^"]+)"', svg)
    assert m, f"{name!r} not found in {svg!r}"
    return m.group(1)
