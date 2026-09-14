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


def test_positional_legend_renders_its_heading_as_one_atomic_key():
    leg = Legend(
        LegendItem(Box(width=14, height=12), "state"),
        label="Tokens:",
    )
    svg, _, size = _render(leg)

    assert "Tokens:" in svg and "state" in svg
    assert size.w > 40


def test_legend_items_kwarg_still_works():
    """Backward-compat: the existing `items=[(color, label), ...]` form."""
    leg = Legend(items=[("info", "hot"), ("muted", "cold")])
    svg, _, _ = _render(leg)
    assert "hot" in svg and "cold" in svg


def test_legend_flows_onto_a_second_line_within_a_budget():
    """A key is subordinate to the figure it explains, so it must not be
    what sets the figure's width. With ``max_width`` the items wrap.
    """
    from sciviz import Box, Legend, LegendItem, Theme

    def swatch():
        return Box(width=15.0, height=10.0, fill="primary_soft",
                   stroke="primary")

    theme = Theme()
    items = [LegendItem(swatch(), text) for text in (
        "compares our work against our work",
        "instruments written independently of our implementation",
        "a third entry that would run the row off the page")]
    wide = Legend(*items, gap="md").measure(theme)
    flowed = Legend(*items, gap="md", max_width=260.0).measure(theme)
    assert wide.w > 260.0, "premise: the unbudgeted legend is over-wide"
    assert flowed.w <= wide.w
    assert flowed.h > wide.h, "wrapping trades width for a second line"


def test_legend_without_a_budget_keeps_one_row():
    from sciviz import Box, Legend, LegendItem, Theme

    theme = Theme()
    items = [LegendItem(Box(width=15.0, height=10.0, fill="primary_soft"), t)
             for t in ("alpha", "beta", "gamma")]
    one_row = Legend(*items).measure(theme)
    assert one_row.h < 2 * theme.text_height("small") + 10.0


def test_swatch_to_label_gap_is_a_text_relative_bearing():
    """A label must not touch the swatch it names, at any layout scale.

    The gap was the ``"xs"`` spacing token, a multiple of ``theme.unit``, so a
    figure compressed towards a print width drove it under a point while the
    type it separates barely moved: the key printed as one smeared run. Tie it
    to the label's own size and the word-space survives the compression.
    """
    from sciviz import Box, LegendItem, Theme

    def item(theme):
        it = LegendItem(Box(width=15.0, height=10.0, fill="primary_soft"),
                        "measured silicon")
        return it.measure(theme).w - it.swatch.measure(theme).w \
            - theme.text_width("measured silicon", "small")

    roomy = Theme()
    tight = Theme(unit=roomy.unit / 4.0)
    assert item(roomy) > 2.0
    assert item(tight) == item(roomy), (
        "the bearing must follow the type, not the layout unit")


def test_explicit_gap_still_wins_over_the_bearing():
    from sciviz import Box, LegendItem, Theme

    theme = Theme()
    def width(**kw):
        return LegendItem(Box(width=15.0, height=10.0), "alpha", **kw).measure(theme).w

    assert width(gap="lg") > width()
    assert width(gap=0.0) < width()
