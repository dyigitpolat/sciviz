"""TextBlock should accept ``align="center"`` (the word most authors reach
for) as a synonym for the internal ``"middle"`` keyword.
"""
from __future__ import annotations

import re

from sciviz import TextBlock, Theme, Canvas


def test_textblock_align_center_equivalent_to_middle():
    theme = Theme()
    # Reference rendering: align="middle"
    tb_mid = TextBlock("Input\nEmbedding", align="middle", weight="700")
    tb_ctr = TextBlock("Input\nEmbedding", align="center", weight="700")

    c1 = Canvas()
    tb_mid.render(c1, 0.0, 0.0, theme)
    svg_mid = c1.to_svg(100, 30)

    c2 = Canvas()
    tb_ctr.render(c2, 0.0, 0.0, theme)
    svg_ctr = c2.to_svg(100, 30)

    # Grab the <text x="..." ... > coordinates from each rendering and
    # check they are identical (same x positions for the text runs).
    xs_mid = [float(m.group(1)) for m in re.finditer(r'<text x="([0-9.-]+)"', svg_mid)]
    xs_ctr = [float(m.group(1)) for m in re.finditer(r'<text x="([0-9.-]+)"', svg_ctr)]
    assert xs_mid == xs_ctr, (xs_mid, xs_ctr)
