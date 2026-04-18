"""TokenRow(*indices) renders as a single rounded pill with math-typeset
t-with-subscript tokens inside.
"""
from __future__ import annotations

import re

from sciviz import Canvas, Theme, TokenRow


_RECT_RX = re.compile(r'<rect ([^/]+?)/>')


def _render(elem) -> tuple[str, float, float]:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


def test_tokenrow_draws_single_pill_rect():
    tr = TokenRow(3, 4, 5, 6)
    svg, w, h = _render(tr)
    rects = _RECT_RX.findall(svg)
    # Only ONE pill rect (plus the root background that to_svg emits separately
    # outside the body).
    content_rects = [r for r in rects
                     if not re.search(r'fill="#ffffff"', r)]
    assert len(content_rects) == 1, (
        f"expected 1 pill rect, got {len(content_rects)}: {content_rects}")


def test_tokenrow_uses_math_for_subscripts():
    """Subscripted tokens require mathtext; the output contains the math
    group wrapper.
    """
    tr = TokenRow(3, 4, 5, 6)
    svg, _, _ = _render(tr)
    assert 'class="sciviz-math"' in svg, (
        "TokenRow should typeset tokens via Math for proper subscripts")
