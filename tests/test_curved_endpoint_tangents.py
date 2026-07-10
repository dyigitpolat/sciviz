from __future__ import annotations

import re

from sciviz import Canvas, Theme
from sciviz.composition import Flow


def test_same_right_side_curve_has_perpendicular_endpoint_tangents_and_compact_bow():
    registry = {
        "lower": (0.0, 80.0, 30.0, 20.0),
        "upper": (0.0, 0.0, 30.0, 20.0),
    }
    canvas = Canvas()
    flow = Flow(
        "lower", "upper",
        src_side="right", dst_side="right",
        style="curved", detour=24.0,
    )
    flow._render(canvas, Theme(), registry)
    svg = canvas.to_svg(100, 120)
    match = re.search(
        r'<path d="M ([\d.-]+),([\d.-]+) C ([\d.-]+),([\d.-]+) '
        r'([\d.-]+),([\d.-]+) ([\d.-]+),([\d.-]+)"',
        svg,
    )
    assert match, svg
    sx, sy, c1x, c1y, c2x, c2y, dx, dy = map(float, match.groups())
    assert c1y == sy and c2y == dy
    assert 0.0 < c1x - sx <= 24.0
    assert 0.0 < c2x - dx <= 24.0
