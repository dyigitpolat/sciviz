"""Theme-relative micro-geometry avoids per-figure pixel constants."""

from __future__ import annotations

import pytest

from sciviz import Connect, Theme, VectorTiles


def test_vector_tiles_semantic_size_scales_cells():
    small = VectorTiles(4, orientation="horizontal", size="xs").measure(Theme())
    large = VectorTiles(4, orientation="horizontal", size="lg").measure(Theme())
    assert large.w > small.w and large.h > small.h


def test_vector_tiles_reject_unknown_size():
    with pytest.raises(ValueError):
        VectorTiles(3, size="huge")


def test_inline_connector_accepts_semantic_length():
    theme = Theme()
    short = Connect(direction="right", length="xs").measure(theme)
    long = Connect(direction="right", length="lg").measure(theme)
    assert long.w > short.w


def test_inline_connector_rejects_unknown_length():
    with pytest.raises(ValueError):
        Connect(direction="right", length="enormous")
