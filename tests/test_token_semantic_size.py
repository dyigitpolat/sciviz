"""Token geometry should scale through semantic theme tiers."""

from __future__ import annotations

import pytest

from sciviz import Canvas, Palette, Theme, Token, Tokens


def test_blank_semantic_token_is_square():
    measured = Token("", size="lg").measure(Theme())
    assert measured.w == measured.h


def test_semantic_token_sizes_scale():
    theme = Theme()
    small = Token("x", size="sm").measure(theme)
    large = Token("x", size="lg").measure(theme)
    assert large.w >= small.w and large.h > small.h


def test_tokens_forwards_semantic_size_to_blank_items():
    measured = Tokens([("", "blue"), ("", "red")], size="md").measure(Theme())
    assert measured.h == Theme().unit * 4.0


def test_token_rejects_unknown_size():
    with pytest.raises(ValueError):
        Token("x", size="huge")


def test_noisy_token_uses_dashed_semantic_boundary():
    theme = Theme()
    token = Token("z₁", role=Palette.orange, size="sm", noisy=True)
    canvas = Canvas()
    size = token.measure(theme)
    token.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert 'stroke-dasharray="3,2"' in svg
