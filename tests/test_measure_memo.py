"""Scoped measure memo (``sciviz.core._measure_memo``).

Containers re-measure children from ``measure``, ``content_bbox`` and
their offset helpers, so an unmemoised deep tree costs a multiple of its
size per measure (a dense diagram's fitter trial took 15 s). The memo reuses
results inside ``measure_memo()`` scopes (one fitter trial, one render)
and must never change a single output byte.
"""
from __future__ import annotations

import numpy as np
import pytest

from sciviz import (Anchor, Box, Card, Column, Connect, Diagram, Palette,
                    Row, Stripe, Text, Theme, card_header)
from sciviz.core._bbox import BBox
from sciviz.core._measure_memo import measure_memo, memo_enabled

needs_memo = pytest.mark.skipif(not memo_enabled(),
                                reason="SCIVIZ_MEASURE_MEMO=0")


def _body():
    role = Palette.blue
    cards = [Card(card_header(f"Stage {i}"),
                  Stripe([Box(f"step {i}.{j}", fill=role.soft(), stroke=role)
                          for j in range(3)], role=role),
                  role=role) for i in range(3)]
    return Column(
        Row(Anchor("a", cards[0]), cards[1], Anchor("b", cards[2]), gap="lg"),
        Connect("a", "b", src_side="bottom", dst_side="bottom",
                label="feedback to the first stage"),
        gap="md")


def test_memo_on_and_off_render_identical_svg(monkeypatch):
    monkeypatch.setenv("SCIVIZ_MEASURE_MEMO", "0")
    off = Diagram.for_paper(_body()).render(embed_fonts=False)
    off_fit = Diagram.for_paper(_body(), target_width_pt=200.0)
    off_fit_svg = off_fit.render(embed_fonts=False)
    monkeypatch.setenv("SCIVIZ_MEASURE_MEMO", "1")
    on = Diagram.for_paper(_body()).render(embed_fonts=False)
    on_fit = Diagram.for_paper(_body(), target_width_pt=200.0)
    on_fit_svg = on_fit.render(embed_fonts=False)
    assert on == off
    assert on_fit_svg == off_fit_svg
    assert on_fit.page_size() == off_fit.page_size()


def test_writes_inside_the_scope_invalidate():
    theme = Theme()
    with measure_memo():
        box = Box("x")
        w1 = box.measure(theme).w
        box.label = "a much longer label than before"
        w2 = box.measure(theme).w
        assert w2 > w1
        box.inflate_to(w2 + 40.0, 0.0)
        assert box.measure(theme).w >= w2 + 40.0 - 1e-9


@needs_memo
def test_repeat_measures_hit_the_memo():
    theme = Theme()
    calls = []
    original = Text.measure

    def counting(self, th):
        calls.append(id(self))
        return original(self, th)

    Text.measure = counting
    try:
        tree = Row(*[Column(Text(f"t{i}"), Text(f"u{i}")) for i in range(4)])
        with measure_memo():
            first = tree.measure(theme)
            n = len(calls)
            again = tree.measure(theme)
        assert again == first
        assert len(calls) == n  # the second measure is free
        assert n <= 8 * 4  # each Text measured a bounded number of times
    finally:
        Text.measure = original


def test_subclass_calling_super_keeps_its_own_result():
    theme = Theme()

    class Padded(Box):
        def measure(self, th):
            inner = super().measure(th)
            return BBox(inner.w + 10.0, inner.h)

    plain = Box("label").measure(theme).w
    with measure_memo():
        p = Padded("label")
        assert p.measure(theme).w == plain + 10.0
        assert p.measure(theme).w == plain + 10.0
        assert Box("label").measure(theme).w == plain


@needs_memo
def test_nothing_is_cached_outside_the_scope():
    theme = Theme()
    box = Box("x")
    original = Box.measure
    with measure_memo():
        assert Box.measure is not original
        box.measure(theme)
    assert Box.measure is original
    w1 = box.measure(theme).w
    theme.unit = 12.0  # a plain dataclass: authors may mutate it
    assert box.measure(theme).w != w1


def test_kill_switch_leaves_methods_untouched(monkeypatch):
    monkeypatch.setenv("SCIVIZ_MEASURE_MEMO", "0")
    original = Box.measure
    with measure_memo():
        assert Box.measure is original


def test_array_valued_attributes_do_not_break_change_detection():
    theme = Theme()
    with measure_memo():
        box = Box("x")
        box.measure(theme)
        box.payload = np.arange(4)
        box.payload = np.arange(4)  # equal array, compared by identity
        box.measure(theme)
