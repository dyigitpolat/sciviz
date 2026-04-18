"""Column align='start' must align children on their *content* rectangles,
not on the outer bbox, so flow-margin bumps on one row don't shift siblings
on other rows.

Reproduces the TTT MLP regression where the middle row of W_down boxes
drifted right because an asymmetric Anchor margin on that row's first
Anchor inflated the outer bbox only.
"""
from sciviz import Column, Row, Box, Anchor, Canvas, Theme
from sciviz.composition import _anchor_stack


def _render_registry(elem):
    theme = Theme()
    reg = {}
    tok = _anchor_stack.set([reg])
    try:
        elem.render(Canvas(), 0, 0, theme)
    finally:
        _anchor_stack.reset(tok)
    return reg


def test_column_start_aligns_anchor_children_across_rows():
    chunk_a = Anchor("chunk_a", Box(width=30, height=20))
    w_a = Anchor("w_a", Box(width=60, height=20))

    chunk_b = Anchor("chunk_b", Box(width=30, height=20), margin_left=10)
    w_b = Anchor("w_b", Box(width=60, height=20))

    col = Column(
        Row(chunk_a, w_a, gap=0),
        Row(chunk_b, w_b, gap=0),
        gap=0,
        align="start",
    )
    reg = _render_registry(col)
    ax = reg["chunk_a"][0]
    bx = reg["chunk_b"][0]
    assert ax == bx, f"chunk children must share x; got {ax} vs {bx}"

    wax = reg["w_a"][0]
    wbx = reg["w_b"][0]
    assert wax == wbx, f"wdown children must share x; got {wax} vs {wbx}"


def test_row_center_aligns_shorter_child_by_content_centre():
    """Row(align='center', default) must centre each child's content centre
    on the row centre -- not align its content top to the row content band
    top.  Reproduces the TTT regression where the small Attention '+' Badge
    sat at the row top instead of the vertical middle.
    """
    tall = Anchor("tall", Box(width=20, height=60))
    short = Anchor("short", Box(width=20, height=20))

    row = Row(tall, short, gap=0)
    reg = _render_registry(row)

    _, tall_y, _, tall_h = reg["tall"]
    _, short_y, _, short_h = reg["short"]

    tall_cy = tall_y + tall_h / 2
    short_cy = short_y + short_h / 2
    assert abs(tall_cy - short_cy) < 0.5, (
        f"Row align='center' must centre content centres, got "
        f"tall_cy={tall_cy} vs short_cy={short_cy}"
    )


def test_column_center_aligns_narrower_child_by_content_centre():
    """Column(align='center', default) must centre each child's content
    centre on the column centre -- not align the left edge of their content
    bboxes.  Reproduces the TTT Update column where L, dW, teal, conv
    should share a vertical centre axis.
    """
    wide = Anchor("wide", Box(width=80, height=20))
    narrow = Anchor("narrow", Box(width=20, height=20))

    col = Column(wide, narrow, gap=0)
    reg = _render_registry(col)

    wx, _, ww, _ = reg["wide"]
    nx, _, nw, _ = reg["narrow"]

    wide_cx = wx + ww / 2
    narrow_cx = nx + nw / 2
    assert abs(wide_cx - narrow_cx) < 0.5, (
        f"Column align='center' must centre content centres, got "
        f"wide_cx={wide_cx} vs narrow_cx={narrow_cx}"
    )
