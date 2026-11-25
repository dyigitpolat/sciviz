"""Facing flow lanes share one gutter under a Rhythm.

A wire leaving the bottom of one card and entering the top of the next
crosses ONE gutter; its two end reservations are two halves of one
wire's room, so the gutter needs the larger of them (or both caption
halves), not tail lane + gap + head lane."""
import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Rhythm, Row


def _stack(gap, label=None, n=1):
    rows = [Row(*[Anchor(f"{r}{i}", Box(f"{r} {i}")) for i in range(n)],
                gap="md") for r in "abc"]
    wires = [Connect(f"{s}{i}", f"{t}{i}", src_side="bottom",
                     dst_side="top", label=label)
             for s, t in (("a", "b"), ("b", "c")) for i in range(n)]
    return Column(*rows, *wires, gap=gap)


def _height(body):
    return Diagram.for_paper(body).measure().h


def test_token_gap_sums_the_facing_lanes():
    plain = _height(Column(Row(Box("a 0")), Row(Box("b 0")),
                           Row(Box("c 0")), gap="sm"))
    wired = _height(_stack("sm"))
    assert wired - plain > 2 * 15.0        # tail + head on top of the gap


@pytest.mark.parametrize("n", [1, 3])
def test_rhythm_gutter_is_the_larger_end_not_the_sum(n):
    from sciviz import DEFAULT_THEME as T
    plain = _height(Column(Row(Box("a 0")), Row(Box("b 0")),
                           Row(Box("c 0")), gap="sm"))
    wired = _height(_stack(Rhythm("sm"), n=n))
    per_gutter = (wired - plain) / 2 + T.gap_px("sm")
    assert per_gutter == pytest.approx(max(T.gap_px("sm"), T.unit * 5 / 3))


def test_captioned_facing_wire_keeps_its_whole_corridor():
    rhythm = Rhythm("sm")
    shared = _height(_stack(rhythm, label="refine"))
    summed = _height(_stack("none", label="refine"))
    # both caption halves are kept: never tighter than the summed lanes
    assert shared >= summed - 1e-6


def test_distinct_wires_in_one_gutter_still_add_up():
    """a's bottom carries a wire to the side, b's top one from the side:
    two lanes in one gutter, never merged into one."""
    beat = Rhythm("none")
    col = Column(Anchor("a", Box("a")), Anchor("b", Box("b")), gap=beat)
    body = Row(col, Column(Anchor("x", Box("x")), Anchor("y", Box("y"))),
               Connect("a", "x", src_side="bottom", dst_side="left"),
               Connect("y", "b", src_side="left", dst_side="top"))
    d = Diagram.for_paper(body)
    d.render(embed_fonts=False)
    theme = d._layout_theme()
    a, b = col.children
    assert beat.gutter(theme) == pytest.approx(
        a.margin_bottom + b.margin_top)


def test_wires_stay_on_the_page():
    body = _stack(Rhythm("sm"), n=2)
    d = Diagram.for_paper(body)
    svg = d.render(embed_fonts=False)
    size = d.page_size()
    assert size.h < _height(_stack("sm", n=2))
    assert "NaN" not in svg
