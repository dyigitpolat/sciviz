"""Tests for :meth:`sciviz.Canvas.svg_path` and :meth:`Canvas.image`.

These are the canvas-level primitives that back :class:`sciviz.Icon` and
:class:`sciviz.Image`. They are thin wrappers around SVG emission, so the
tests are correspondingly thin: we check that the emitted SVG is
well-formed and contains the attributes callers relied on.
"""

from __future__ import annotations

from sciviz import Canvas


def test_svg_path_default_viewbox_emits_nested_svg():
    c = Canvas()
    c.svg_path(10, 20, 16, 16, paths=["M 1 1 L 2 2"])
    svg = c.to_svg(40, 40)
    assert '<svg ' in svg.split("<defs")[1]  # there's a nested <svg>
    assert 'x="10" y="20"' in svg
    assert 'width="16" height="16"' in svg
    assert 'viewBox="0 0 24 24"' in svg
    assert '<path d="M 1 1 L 2 2"/>' in svg


def test_svg_path_custom_viewbox_and_stroke():
    c = Canvas()
    c.svg_path(0, 0, 32, 32,
               paths=["M 0 0 L 10 0", "M 5 5 L 6 6"],
               viewbox=(0, 0, 10, 10),
               stroke="#ff0000", stroke_width=2.5,
               linecap="butt", linejoin="miter")
    svg = c.to_svg(64, 64)
    assert 'viewBox="0 0 10 10"' in svg
    assert 'stroke="#ff0000"' in svg
    assert 'stroke-width="2.50"' in svg
    assert 'stroke-linecap="butt"' in svg
    assert 'stroke-linejoin="miter"' in svg
    assert svg.count('<path d=') == 2


def test_svg_path_is_stroke_only_by_default():
    """Lucide icons are stroke-only; ``fill="none"`` must be the default."""
    c = Canvas()
    c.svg_path(0, 0, 24, 24, paths=["M 0 0 L 1 1"])
    svg = c.to_svg(24, 24)
    assert 'fill="none"' in svg


def test_image_emits_image_tag_with_href():
    c = Canvas()
    c.image(5, 6, 100, 80, href="data:image/png;base64,AAAA")
    svg = c.to_svg(200, 200)
    assert '<image ' in svg
    assert 'x="5" y="6"' in svg
    assert 'width="100" height="80"' in svg
    assert 'href="data:image/png;base64,AAAA"' in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg


def test_image_preserve_aspect_ratio_override():
    c = Canvas()
    c.image(0, 0, 50, 50, href="x", preserve_aspect_ratio="none")
    svg = c.to_svg(50, 50)
    assert 'preserveAspectRatio="none"' in svg


def test_image_opacity():
    c = Canvas()
    c.image(0, 0, 10, 10, href="x", opacity=0.5)
    assert any('opacity="0.50"' in line for line in c._body)
