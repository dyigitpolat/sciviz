"""`Labeled(source, label)` draws a horizontal arrow from source's right
edge into label's left edge, with no author-side coordinate work.
"""
from __future__ import annotations

import re

from sciviz import Box, Labeled, Theme, Canvas
from sciviz.math import Math


def _render(elem):
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


def test_labeled_emits_arrow_path():
    pair = Labeled(
        Box("Cross-Entropy Loss", sub_label="FP32", text_size="small"),
        Math(r"\mathcal{L}_{\text{MTP}}^{2}", size="label"),
    )
    svg, _, _ = _render(pair)
    # a drawn arrow exists (a path with marker-end)
    assert re.search(r'<path[^>]+marker-end="url\(#[^)]+\)"', svg), svg


def test_labeled_has_horizontal_shape():
    """The pair's bounding box should be wider than tall, reflecting the
    natural horizontal Row layout produced by Labeled.
    """
    pair = Labeled(
        Box("CE Loss", sub_label="FP32", text_size="small"),
        Math(r"\mathcal{L}^{2}", size="label"),
    )
    theme = Theme()
    size = pair.measure(theme)
    assert size.w > size.h, f"{size.w} should be > {size.h}"
