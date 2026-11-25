"""A stretched Region's border fills the slot its bbox reports.

A Region around leaf text (which cannot grow) used to report the inflated
width as its bbox while painting a border that hugged the text, so wires
anchored to it ended in empty space beside the visible frame.
"""
import re

from sciviz import Anchor, Box, Column, Diagram, Region, Text


def _rect_widths(svg):
    return [float(w) for w in re.findall(r'<rect[^>]*?\swidth="([\d.]+)"', svg)]


def test_stretched_region_border_fills_its_slot():
    band = Region(Text("membrane"), dashed=False, fill="#eeeeee",
                  margin_x=0.0, margin_y=0.0)
    wide = Box("a much wider sibling that sets the column width", width=300)
    d = Diagram.for_paper(Column(wide, Anchor("band", band), align="stretch"))
    theme = d.theme
    svg = d.render()
    assert band.measure(theme).w >= 299.0
    # The painted border spans the stretched slot, not the text: both the
    # sibling box and the region's border are drawn at the slot width.
    frames = [w for w in _rect_widths(svg) if 299.0 <= w <= 301.0]
    assert len(frames) == 2


def test_unstretched_region_is_unchanged():
    band = Region(Text("membrane"), dashed=False, margin_x=0.0, margin_y=0.0)
    theme = Diagram.for_paper(band).theme
    b = band.measure(theme)
    cx, cy, cw, ch = band.content_bbox(theme)
    assert abs(cy - band.pad_y) < 1e-6
    assert abs(cx - (b.w - cw) / 2.0) < 1e-6
