"""`Legend` upgrade: accept positional ``LegendItem`` children and allow
custom swatch elements (not just colour rectangles), replacing the
hand-built ``Row(Box, Text, Spacer, Box, Text, ...)`` legend in bplus_tree.
"""
from __future__ import annotations

import re

from sciviz import Legend, LegendItem, Box, Canvas, Theme


def _render(elem):
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    return c.to_svg(size.w, size.h), theme, size


def test_legend_item_accepts_custom_swatch_element():
    swatch = Box(width=18, height=14, fill="accent_soft", stroke="text", radius=1)
    item = LegendItem(swatch, "leaf page")
    svg, _, _ = _render(item)
    assert re.search(r'<rect[^>]+width="18', svg), (
        "LegendItem must render its custom swatch element verbatim")
    assert "leaf page" in svg


def test_legend_from_positional_items():
    leg = Legend(
        LegendItem(Box(width=18, height=14, fill="none", stroke="text", radius=1),
                   "internal page"),
        LegendItem(Box(width=18, height=14, fill="accent_soft", stroke="text",
                       radius=1),
                   "leaf page"),
    )
    svg, _, size = _render(leg)
    assert "internal page" in svg
    assert "leaf page" in svg
    assert size.w > 60  # two items plus gaps


def test_legend_items_kwarg_still_works():
    """Backward-compat: the existing `items=[(color, label), ...]` form."""
    leg = Legend(items=[("info", "hot"), ("muted", "cold")])
    svg, _, _ = _render(leg)
    assert "hot" in svg and "cold" in svg
