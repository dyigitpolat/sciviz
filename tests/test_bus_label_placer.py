"""Bus labels should never overlap structural lines (T-bar, arrow,
sink/source boxes).

Representative case: the concatenation fan-in Bus.  The author writes::

    Bus(sources=[rn_l, rn_r], sinks=proj, label="concatenation")

and the library places "concatenation" in the empty space between the
horizontal T-bar and the nearest sibling (below the bar, above the sources),
never colliding with the bar itself or with the Linear Projection sink.
"""
from __future__ import annotations

import re

from sciviz import (
    Anchor, Box, Bus, Canvas, Flowed, Grid, Palette, Theme,
)


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def _text_rect(svg: str, needle: str, theme: Theme):
    m = re.search(rf'<text ([^>]*)>{needle}</text>', svg)
    if not m:
        return None
    attrs = m.group(1)
    x = float(re.search(r'x="([^"]+)"', attrs).group(1))
    y = float(re.search(r'y="([^"]+)"', attrs).group(1))
    fs = float(re.search(r'font-size="([^"]+)"', attrs).group(1))
    anchor_m = re.search(r'text-anchor="([^"]+)"', attrs)
    anchor = anchor_m.group(1) if anchor_m else "start"
    w = theme.text_width(needle, fs)
    if anchor == "middle":
        x0 = x - w / 2
    elif anchor == "end":
        x0 = x - w
    else:
        x0 = x
    return (x0, y - fs * 0.88, x0 + w, y + fs * 0.35)


def _lines(svg: str):
    out = []
    for m in re.finditer(
        r'<line x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)"',
        svg,
    ):
        out.append(tuple(float(v) for v in m.groups()))
    return out


def test_concat_label_does_not_cross_tbar():
    """The 'concatenation' label rect must be vertically disjoint from the
    horizontal T-bar of the fan-in bus.
    """
    theme = Theme()
    PROC = Palette.literal("#fbe5a8")
    from sciviz.layout import Row
    rms_row = Row(
        Anchor("rn_l", Box("RMSNorm", fill=PROC, text_size="small")),
        Anchor("rn_r", Box("RMSNorm", fill=PROC, text_size="small")),
        gap="md",
    )
    proj = Anchor("proj", Box("Linear Projection", fill=PROC, text_size="small"))
    g = Grid(
        rows=["proj", "rms"],
        columns=[{"rms": rms_row, "proj": proj}],
    )
    flowed = Flowed(g, flows=[
        Bus(sources=["rn_l", "rn_r"], sinks="proj",
            label="concatenation", color="text"),
    ])
    svg = _render(flowed)
    lbl = _text_rect(svg, "concatenation", theme)
    assert lbl, svg
    lbl_x0, lbl_y0, lbl_x1, lbl_y1 = lbl
    # The only short horizontal line between the two taps is the T-bar.
    # The label must NOT intersect its y-band.
    for x1, y1, x2, y2 in _lines(svg):
        if abs(y1 - y2) > 0.5:  # not horizontal
            continue
        # short horizontal lines only (the T-bar is about half a cell wide)
        seg_w = abs(x2 - x1)
        if seg_w < 5.0 or seg_w > 200.0:
            continue
        # A true T-bar sits between the RMSNorm tops and the proj bottom.
        # Overlap check: label rect cannot contain this y coordinate.
        if lbl_y0 - 0.5 <= y1 <= lbl_y1 + 0.5:
            x_overlap = not (lbl_x1 < min(x1, x2) - 0.5
                             or max(x1, x2) < lbl_x0 - 0.5)
            if x_overlap:
                raise AssertionError(
                    f"concatenation label {lbl} crosses T-bar at "
                    f"y={y1} x=[{x1},{x2}]")
