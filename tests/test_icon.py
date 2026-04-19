"""Tests for :class:`sciviz.Icon`."""

from __future__ import annotations

import pytest

from sciviz import Canvas, DEFAULT_THEME, Icon


def test_icon_known_name_measures_square():
    icon = Icon("camera") if "camera" in _available() else Icon("image")
    bbox = icon.measure(DEFAULT_THEME)
    assert bbox.w > 0 and bbox.w == bbox.h


def test_icon_unknown_name_raises_with_suggestions():
    with pytest.raises(KeyError, match="Unknown icon"):
        Icon("not-a-real-icon")


def test_icon_renders_path_data_in_nested_svg():
    icon = Icon("check", size=20.0, color="dark")
    canvas = Canvas()
    icon.render(canvas, 5.0, 7.0, DEFAULT_THEME)
    svg = canvas.to_svg(40, 40)
    assert 'x="5" y="7"' in svg
    assert 'width="20" height="20"' in svg
    assert 'viewBox="0 0 24 24"' in svg
    assert '<path d="M20 6 9 17l-5-5"/>' in svg


def test_icon_color_resolves_via_theme():
    icon = Icon("check", color="highlight")
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    assert f'stroke="{DEFAULT_THEME.color_of("highlight")}"' in canvas.to_svg(24, 24)


def test_icon_semantic_size():
    small = Icon("check", size="small")
    label = Icon("check", size="label")
    title = Icon("check", size="title")
    assert small.measure(DEFAULT_THEME).w < label.measure(DEFAULT_THEME).w
    assert label.measure(DEFAULT_THEME).w < title.measure(DEFAULT_THEME).w


def test_icon_fill_remains_none():
    icon = Icon("star")
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    assert 'fill="none"' in canvas.to_svg(24, 24)


def _available() -> set[str]:
    from sciviz._assets import LUCIDE_ICONS
    return set(LUCIDE_ICONS)
