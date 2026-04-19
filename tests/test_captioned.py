"""`Captioned` wraps a child with a small numbered badge or title above it,
replacing the hand-rolled ``Column(Badge(num), Spacer(0, 6), body, ...)`` pattern.
"""
from __future__ import annotations

import re

from sciviz import Captioned, Box, Palette, Canvas, Theme


def _render(elem):
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), theme, size


def test_captioned_with_number_renders_badge_above_child():
    body = Box("body", width=40, height=20)
    cap = Captioned(body, number="1", number_role=Palette.alert)
    svg, theme, size = _render(cap)
    assert "<circle" in svg, "numbered Captioned should render a Badge circle"
    assert re.search(r'<rect[^>]+width="40', svg), (
        "child Box must still render at its intrinsic width")
    assert size.h > 20, "Captioned must be taller than the bare body"


def test_captioned_with_title_renders_text_above_child():
    body = Box("body", width=40, height=20)
    cap = Captioned(body, title="FORWARD")
    svg, _, size = _render(cap)
    assert "FORWARD" in svg
    assert size.h > 20


def test_captioned_without_decoration_is_bare_child():
    body = Box("body", width=40, height=20)
    cap = Captioned(body)
    size = cap.measure(Theme())
    bare = body.measure(Theme())
    assert abs(size.w - bare.w) < 0.5
    assert abs(size.h - bare.h) < 0.5


def test_captioned_centers_child_when_decoration_wider():
    body = Box("body", width=10, height=10)
    cap = Captioned(body, title="a very long title here")
    size = cap.measure(Theme())
    assert size.w > 10, "width expands to the decoration's width"
