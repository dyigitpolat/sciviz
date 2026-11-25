"""Rhythm: one gutter shared by every gap it spaces.

Sister cards read as one beat only when every gutter between them is the
same, whatever wires or captions cross some of them and not others."""
import pytest

from sciviz import (DEFAULT_THEME, Anchor, Box, Column, Connect, Diagram,
                    Rhythm, Row, WrapRow)


def _row_positions(gap):
    """Content boxes (x0, x1) of four anchored boxes in a row where a->b
    is wired, b|c is not, and c->d carries a caption."""
    names = "abcd"
    row = Row(*[Anchor(n, Box(f"stage {n}")) for n in names], gap=gap)
    body = Column(row,
                  Connect("a", "b", src_side="right", dst_side="left"),
                  Connect("c", "d", src_side="right", dst_side="left",
                          label="ok"))
    d = Diagram.for_paper(body)
    d.render(embed_fonts=False)
    theme = d._layout_theme()
    offs = row._child_offsets(theme)
    out = []
    for (ox, _oy, _s), child in zip(offs, row.children):
        cx, _cy, cw, _ch = child.content_bbox(theme)
        out.append((ox + cx, ox + cx + cw))
    # the row is returned too: a Rhythm holds its containers weakly
    return out, theme, row


def _gutters(boxes):
    return [b[0] - a[1] for a, b in zip(boxes, boxes[1:])]


def test_token_gap_gutters_grow_with_what_crosses_them():
    boxes, _theme, _row = _row_positions("md")
    g = _gutters(boxes)
    assert max(g) - min(g) > 1.0          # the failure a Rhythm fixes


def test_rhythm_sets_every_gutter_to_one_beat():
    rhythm = Rhythm("md")
    boxes, theme, _row = _row_positions(rhythm)
    g = _gutters(boxes)
    assert max(g) - min(g) < 1e-6
    assert g[0] == pytest.approx(rhythm.gutter(theme))
    assert g[0] >= theme.gap_px("md") - 1e-9


def test_sister_containers_sharing_a_rhythm_share_the_gutter():
    beat = Rhythm("sm")
    wired = Column(Anchor("a", Box("a")), Anchor("b", Box("b")), gap=beat)
    plain = Column(Box("c"), Box("d"), gap=beat)
    body = Column(Row(wired, plain, gap="xl"),
                  Connect("a", "b", src_side="bottom", dst_side="top",
                          label="hand-off"))
    d = Diagram.for_paper(body)
    d.render(embed_fonts=False)
    theme = d._layout_theme()
    G = beat.gutter(theme)
    assert G > theme.gap_px("sm")          # the caption's corridor wins

    def gutter(col):
        a, b = col.children
        ha = a.measure(theme).h
        la = a.content_bbox(theme)
        lb = b.content_bbox(theme)
        spacing = col._gap_list(theme, col._visible_children())[0]
        return (ha - la[1] - la[3]) + spacing + lb[1]

    assert gutter(wired) == pytest.approx(G)
    assert gutter(plain) == pytest.approx(G)


def test_rhythm_spaces_one_axis():
    beat = Rhythm("sm")
    Column(Box("a"), Box("b"), gap=beat)
    with pytest.raises(ValueError, match="one axis"):
        Row(Box("c"), Box("d"), gap=beat)


def test_rhythm_follows_a_compressed_theme():
    beat = Rhythm("md")
    Row(Box("a"), Box("b"), gap=beat)
    small = DEFAULT_THEME.with_overrides(unit=3.0)
    assert beat.gutter(small) == pytest.approx(small.gap_px("md"))
    assert beat.gutter(DEFAULT_THEME) == pytest.approx(
        DEFAULT_THEME.gap_px("md"))


def test_only_row_and_column_take_a_rhythm():
    with pytest.raises(TypeError):
        DEFAULT_THEME.gap_px(Rhythm("md"))
    el = WrapRow(Box("a"), Box("b"), gap=Rhythm("md"))
    with pytest.raises(TypeError):
        el.measure(DEFAULT_THEME)


def test_token_gaps_keep_their_layout():
    """A string gap takes the legacy path: sizes are those of a plain
    token gap."""
    row = Row(Box("a"), Box("b"), Box("c"), gap="md")
    w = sum(c.measure(DEFAULT_THEME).w for c in row.children)
    assert row.measure(DEFAULT_THEME).w == pytest.approx(
        w + 2 * DEFAULT_THEME.gap_px("md"))


@pytest.mark.parametrize("wrap", ["column", "row", "region"])
def test_rhythm_row_keeps_its_gutter_over_a_same_count_row(wrap):
    """A Rhythm row stacked over a row with as many children takes no
    shared slot columns: its children sit one gutter apart, in order and
    without overlap, whatever they are (a Box inflates to a slot; a
    Column, a Row or a Region does not)."""
    from sciviz import Icon, Region, Text

    def child(name):
        if wrap == "column":
            return Column(Text(name))
        if wrap == "row":
            return Row(Icon("cpu", size=8), Text(name))
        return Region(Text(name))

    beat = Rhythm("md")
    top = Row(child("a"), child("b"), child("c"), gap=beat)
    bottom = Row(Box("a much much wider peer card"), Box("b"),
                 Box("another very very wide peer card"))
    d = Diagram.for_paper(Column(top, bottom))
    d.render(embed_fonts=False)
    theme = d._layout_theme()
    # no wire crosses these gutters, so no flow lane narrows them: the
    # box-to-box spacing is the content-to-content gutter
    offs = top._child_offsets(theme)
    spans = [(ox, ox + size.w) for ox, _oy, size in offs]
    gutter = beat.gutter(theme)
    for g in _gutters(spans):
        assert g == pytest.approx(gutter, abs=0.05)
    assert top.measure(theme).w == pytest.approx(
        sum(c.measure(theme).w for c in top.children) + 2 * gutter, abs=0.05)


def test_repeated_measures_do_not_grow_the_beat():
    """Measuring a Rhythm row again does not grow what the beat spans,
    and a container built on every measure (a composite forwarding its
    gap) leaves the beat once it is dropped."""
    import gc
    beat = Rhythm("md")
    row = Row(Box("a"), Box("b"), gap=beat)
    theme = DEFAULT_THEME
    for _ in range(3):
        row.measure(theme)
        row._child_offsets(theme)
    assert len(beat._members) == 1
    for _ in range(5):
        Row(Box("c"), Box("d"), gap=beat).measure(theme)
    gc.collect()
    assert len(beat._members) == 1
