"""When a staircase flow's bridge row is blocked by an anchor inside
the x-span, the router must choose a different y so the horizontal
segment does not pass through the obstacle.
"""
import re

from sciviz import (Anchor, Box, Diagram, Row, Column, Spacer)
from sciviz.composition import Flow, Flowed


def _line_rects(svg: str):
    return re.findall(
        r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"',
        svg,
    )


def test_bridge_detours_around_obstacle() -> None:
    # Layout: SRC on the left at row-0; DST on the right at row-2;
    # OBSTACLE sits in the middle column at row-1 (between them).
    # When we flow src.right -> dst.left, the natural staircase
    # midpoint row-1 is blocked by the obstacle, so the router must
    # route above or below it instead.
    body = Flowed(
        Column(
            Row(
                Anchor("src", Box("src", width=60, height=20)),
                Spacer(120, 0),
                Anchor("dst", Box("dst", width=60, height=20)),
                gap="none",
            ),
            Row(
                Spacer(80, 0),
                Anchor("obs", Box("obs", width=80, height=40)),
                gap="none",
            ),
            gap="none",
        ),
        [Flow("src", "dst", src_side="right", dst_side="left")],
    )
    d = Diagram(body=body)
    svg = d.render()

    segs = _line_rects(svg)
    horiz_bridges = [
        (float(x1), float(x2), float(y1))
        for (x1, y1, x2, y2) in segs
        if abs(float(y1) - float(y2)) < 0.5
        and abs(float(x2) - float(x1)) > 50
    ]
    assert horiz_bridges, "expected at least one horizontal bridge segment"

    # The obstacle's middle row is around y = src_row_h + obs_h/2.
    # We assert no horizontal segment sits in that band AND crosses the
    # obstacle's x-range.
    # Obstacle occupies x in [80, 160] and y around 20+20 = 40 (with
    # diagram padding added).  Find the obstacle's rect from SVG.
    rects = re.findall(
        r'<rect[^>]*x="([0-9.]+)"[^>]*y="([0-9.]+)"[^>]*width="([0-9.]+)"[^>]*height="([0-9.]+)"',
        svg,
    )
    obs_rect = None
    for (rx, ry, rw, rh) in rects:
        rw_f = float(rw)
        rh_f = float(rh)
        if 70 < rw_f < 90 and 30 < rh_f < 50:
            obs_rect = (float(rx), float(ry), rw_f, rh_f)
            break
    assert obs_rect is not None, "expected to find obstacle rect in SVG"
    ox, oy, ow, oh = obs_rect
    obs_y_band = (oy + 2, oy + oh - 2)
    obs_x_band = (ox, ox + ow)
    for x1, x2, y in horiz_bridges:
        seg_lo = min(x1, x2)
        seg_hi = max(x1, x2)
        overlaps_x = seg_hi > obs_x_band[0] and seg_lo < obs_x_band[1]
        inside_y = obs_y_band[0] < y < obs_y_band[1]
        if overlaps_x and inside_y:
            raise AssertionError(
                f"bridge at y={y} [{seg_lo}..{seg_hi}] crosses obstacle"
                f" x=[{obs_x_band}] y=[{obs_y_band}]"
            )
