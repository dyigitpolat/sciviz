"""``Badge(label_pad=...)``: the room a disc keeps around an Element label.

The default (``None``) keeps the 1.1-unit room, so existing figures do not
change; an explicit value lets a small status disc carry a large glyph.
"""
from __future__ import annotations

import pytest

from sciviz import Badge, Icon, Theme


def test_default_room_is_unchanged():
    theme = Theme()
    glyph = Icon("check", size=8.0)
    assert Badge(glyph, size=9.0).measure(theme).w == pytest.approx(8.0 + theme.unit * 1.1)


def test_label_pad_sets_the_room():
    theme = Theme()
    b = Badge(Icon("check", size=8.0), size=9.0, label_pad=3.0)
    box = b.measure(theme)
    assert box.w == pytest.approx(11.0)
    assert box.h == pytest.approx(11.0)


def test_size_stays_a_floor():
    theme = Theme()
    assert Badge(Icon("check", size=8.0), size=14.0, label_pad=0.0).measure(theme).w == pytest.approx(14.0)


def test_string_label_ignores_label_pad():
    theme = Theme()
    assert Badge("1", label_pad=0.0).measure(theme).w == Badge("1").measure(theme).w


def test_negative_label_pad_is_refused():
    with pytest.raises(ValueError):
        Badge(Icon("check"), label_pad=-1.0)
