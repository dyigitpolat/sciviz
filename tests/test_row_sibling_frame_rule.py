"""Sibling-frame rule: a Row of framed siblings equalises heights by default."""

from sciviz import Box, Card, Palette, Panel, Row, StepCell, Text
from sciviz.core import DEFAULT_THEME as THEME


def _panel(lines: int, tag: str) -> Panel:
    body = Box("content\n" * lines if lines else "content")
    return Panel(tag, f"Panel {tag}", body)


def test_row_of_panels_equalises_heights_by_default():
    short = _panel(0, "a")
    tall = Panel("b", "Panel b", Box("x\ny\nz\nw"))
    row = Row(short, tall)  # no align="stretch", no flags
    row.measure(THEME)
    assert abs(short.measure(THEME).h - tall.measure(THEME).h) < 0.5


def test_row_of_step_cells_equalises_heights_by_default():
    a = StepCell("short label", Text("v"), role=Palette.blue)
    b = StepCell("a much longer label that wraps onto several lines", Text("v"), role=Palette.blue)
    row = Row(a, b, gap="sm")
    row.measure(THEME)
    assert abs(a.measure(THEME).h - b.measure(THEME).h) < 0.5


def test_row_of_cards_equalises_heights_by_default():
    a = Card(Text("h"), Box("one"), role=Palette.blue)
    b = Card(Text("h"), Box("one\ntwo\nthree"), role=Palette.blue)
    row = Row(a, b)
    row.measure(THEME)
    assert abs(a.measure(THEME).h - b.measure(THEME).h) < 0.5


def test_mixed_row_is_left_alone():
    panel = _panel(0, "a")
    text = Text("caption-like leaf")
    natural = _panel(0, "z").measure(THEME).h
    row = Row(panel, text)
    row.measure(THEME)
    assert abs(panel.measure(THEME).h - natural) < 0.5


def test_equal_heights_false_disables_the_rule():
    short = Panel("a", "Panel a", Text("one line"))
    tall = Panel("b", "Panel b", Box("x\ny\nz\nw"))
    natural = Panel("z", "Panel z", Text("one line")).measure(THEME).h
    row = Row(short, tall, equal_heights=False)
    row.measure(THEME)
    assert abs(short.measure(THEME).h - natural) < 0.5
    assert short.measure(THEME).h < tall.measure(THEME).h - 1.0


def test_equal_heights_true_forces_for_unframed_children():
    a = Box("one")
    b = Box("one\ntwo\nthree\nfour")
    row = Row(a, b, equal_heights=True)
    row.measure(THEME)
    assert abs(a.measure(THEME).h - b.measure(THEME).h) < 0.5


def test_rule_is_idempotent_across_repeated_measures():
    short = _panel(0, "a")
    tall = Panel("b", "Panel b", Box("x\ny\nz\nw"))
    row = Row(short, tall)
    first = row.measure(THEME)
    second = row.measure(THEME)
    assert abs(first.h - second.h) < 0.5
    assert abs(first.w - second.w) < 0.5
