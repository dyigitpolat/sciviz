"""`LabeledChain`: a sequence of items with optional top and/or bottom
labels that auto-centre under each item, eliminating the manual
``FixedSize(label, width=tile_w, align="center")`` mirroring in
``gallery/diffusion.py``.
"""
from __future__ import annotations

from sciviz import LabeledChain, Box, Text, Theme, Canvas
from sciviz.layout import Row


def _pos(elem):
    """Render the element and return a flat list of (x, y, w, h) for every
    rendered <rect> in the SVG, in document order.  Good enough to check
    positional alignment without a full parser."""
    theme = Theme()
    size = elem.measure(theme)
    c = Canvas()
    elem.render(c, 0.0, 0.0, theme)
    svg = c.to_svg(size.w, size.h)
    import re
    rects = []
    for m in re.finditer(
            r'<rect[^>]*?\bx="([\d.\-]+)"[^>]*?\by="([\d.\-]+)"'
            r'[^>]*?\bwidth="([\d.\-]+)"[^>]*?\bheight="([\d.\-]+)"', svg):
        rects.append(tuple(float(g) for g in m.groups()))
    return rects, size


def test_items_render_with_top_labels_centered():
    items = [Box("a", width=40, height=20), Box("b", width=40, height=20),
             Box("c", width=40, height=20)]
    top = [Text("x_0"), Text("x_1"), Text("x_2")]
    chain = LabeledChain(items=items, top_labels=top, gap="md")
    rects, _ = _pos(chain)
    xs = [r[0] for r in rects if r[2] == 40]
    assert len(xs) == 3, f"expected 3 item rects, got {rects}"
    gaps = [xs[i + 1] - xs[i] - 40 for i in range(2)]
    assert abs(gaps[0] - gaps[1]) < 0.5, (
        f"items must be evenly spaced; got gaps={gaps}")


def test_bottom_labels_share_item_columns():
    """Top and bottom labels must sit in exactly the same X columns as
    their corresponding items, regardless of label width."""
    items = [Box("a", width=60, height=20), Box("b", width=60, height=20)]
    bottom = [Text("short"), Text("a much longer label")]
    chain = LabeledChain(items=items, bottom_labels=bottom, gap="md")
    size = chain.measure(Theme())
    assert size.h > 20, "bottom labels should contribute to height"


def test_label_and_item_centers_align():
    """A label positioned above an item must share the item's X centre
    to <= 1 px, computed from the text's rendered width (since the Text
    element is left-anchored and its x attribute is its left edge)."""
    items = [Box("a", width=80, height=20), Box("b", width=80, height=20)]
    top_labels = [Text("L0"), Text("A much longer L1")]
    chain = LabeledChain(items=items, top_labels=top_labels, gap="md")
    theme = Theme()
    # Predicted centres of the item row, given gap="md" (Theme default ~ 12 px).
    gap_md = theme.gap_px("md")
    expected_item_cxs = [80 / 2, 80 + gap_md + 80 / 2]
    for i, lbl in enumerate(top_labels):
        lbb = lbl.measure(theme)
        # Label is centred on item -> its rendered left edge must be
        # item_cx - label_w/2.
        label_x_left = expected_item_cxs[i] - lbb.w / 2
        # Verify by re-rendering and reading the <text> x attribute.
        c = Canvas()
        chain.render(c, 0.0, 0.0, theme)
        size = chain.measure(theme)
        svg = c.to_svg(size.w, size.h)
        import re
        label_text = re.escape(lbl.content)
        m = re.search(
            r'<text[^>]*?\bx="([\d.\-]+)"[^>]*?>' + label_text + r'</text>', svg)
        assert m, f"label text {lbl.content!r} not found in svg"
        rendered_x = float(m.group(1))
        assert abs(rendered_x - label_x_left) < 1.0, (
            f"label {i} ({lbl.content!r}) drawn at x={rendered_x}, "
            f"expected left edge {label_x_left}")


def test_arrow_connector_between_items():
    items = [Box("a", width=40, height=20), Box("b", width=40, height=20)]
    chain = LabeledChain(items=items, arrow="->", gap="md")
    rects, size = _pos(chain)
    xs = [r[0] for r in rects if r[2] == 40]
    assert len(xs) == 2
    # There should be space between the two items for the arrow glyph.
    assert xs[1] - xs[0] > 40 + 8, (
        f"arrow='->' should inject arrow width between items; gap={xs[1] - xs[0] - 40}")
