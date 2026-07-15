"""WrapRow: flow layout that wraps children onto new lines within a budget.

Motivating case (thesis deployment-taxonomy figure): a taxonomy leaf is a
method-family box followed by a run of small citation chips. Inline the run
can exceed the printable width; a WrapRow lets the chips flow onto a second
line instead of widening the whole tree, so the diagram fits its physical
target at authored font sizes.
"""
from __future__ import annotations

import pytest

from sciviz import Theme, WrapRow
from sciviz.core import BBox, Canvas, Element


class _Probe(Element):
    """Fixed-size child that records where it was rendered."""

    def __init__(self, w: float, h: float):
        self.w = w
        self.h = h
        self.rendered_at: tuple[float, float] | None = None

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.w, self.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self.rendered_at = (x, y)


def _layout(elem) -> Theme:
    theme = Theme()
    elem.render(Canvas(), 0.0, 0.0, theme)
    return theme


def test_single_line_when_children_fit():
    kids = [_Probe(30, 10), _Probe(40, 12), _Probe(20, 8)]
    wr = WrapRow(*kids, gap=5.0, max_width=200.0)
    theme = Theme()
    size = wr.measure(theme)
    assert size.w == pytest.approx(30 + 5 + 40 + 5 + 20)
    assert size.h == pytest.approx(12)  # tallest child, one line
    _layout(wr)
    ys = [k.rendered_at[1] for k in kids]
    # align="center" (default): children share the line's vertical band.
    assert max(ys) - min(ys) < 12
    xs = [k.rendered_at[0] for k in kids]
    assert xs == sorted(xs)  # reading order preserved


def test_wraps_at_budget_and_reports_stacked_height():
    kids = [_Probe(60, 10), _Probe(60, 10), _Probe(60, 10)]
    wr = WrapRow(*kids, gap=10.0, line_gap=4.0, max_width=140.0)
    theme = Theme()
    size = wr.measure(theme)
    # Two fit per line (60+10+60=130 <= 140); the third wraps.
    assert size.w == pytest.approx(130)
    assert size.h == pytest.approx(10 + 4 + 10)
    _layout(wr)
    assert kids[0].rendered_at[1] == kids[1].rendered_at[1]
    assert kids[2].rendered_at[1] > kids[0].rendered_at[1]
    assert kids[2].rendered_at[0] == pytest.approx(kids[0].rendered_at[0])


def test_oversized_child_gets_own_line_not_clipped():
    kids = [_Probe(50, 10), _Probe(300, 10)]
    wr = WrapRow(*kids, gap=6.0, max_width=100.0)
    theme = Theme()
    size = wr.measure(theme)
    # The budget is a wrap threshold, not a clip: the wide child still
    # reports its full width (longest-child floor).
    assert size.w == pytest.approx(300)
    assert size.h > 10  # two lines
    _layout(wr)
    assert kids[1].rendered_at[1] > kids[0].rendered_at[1]


def test_default_budget_is_theme_wrap_budget():
    theme = Theme()
    budget = theme.wrap_budget_px()
    w = budget * 0.6
    kids = [_Probe(w, 10), _Probe(w, 10)]
    wr = WrapRow(*kids, gap=2.0)  # no max_width -> theme wrap budget
    size = wr.measure(theme)
    # Two children of 0.6*budget each cannot share a line.
    assert size.w == pytest.approx(w)
    assert size.h > 10


def test_line_align_center_centres_short_last_line():
    kids = [_Probe(60, 10), _Probe(60, 10), _Probe(20, 10)]
    wr = WrapRow(*kids, gap=10.0, max_width=130.0, line_align="center")
    _layout(wr)
    outer_w = wr.measure(Theme()).w
    # Last line (just the 20-wide child) is centred within the container.
    assert kids[2].rendered_at[0] == pytest.approx((outer_w - 20) / 2.0)


def test_render_stays_inside_reported_bbox():
    kids = [_Probe(45, 9), _Probe(80, 14), _Probe(33, 7), _Probe(70, 11)]
    wr = WrapRow(*kids, gap=4.0, line_gap=3.0, max_width=120.0)
    theme = Theme()
    size = wr.measure(theme)
    wr.render(Canvas(), 0.0, 0.0, theme)
    for k in kids:
        x, y = k.rendered_at
        assert x >= -1e-6 and y >= -1e-6
        assert x + k.w <= size.w + 1e-6
        assert y + k.h <= size.h + 1e-6


def test_invisible_children_consume_no_flow_space():
    class _Ghost(_Probe):
        is_layout_invisible = True

    ghost = _Ghost(500, 500)
    kids = [_Probe(30, 10), ghost, _Probe(30, 10)]
    wr = WrapRow(*kids, gap=5.0, max_width=100.0)
    size = wr.measure(Theme())
    assert size.w == pytest.approx(30 + 5 + 30)
    assert size.h == pytest.approx(10)
    _layout(wr)
    assert ghost.rendered_at is not None  # still rendered for walkers


def test_hanging_indent_marks_continuation_lines():
    kids = [_Probe(60, 10), _Probe(60, 10), _Probe(60, 10)]
    wr = WrapRow(*kids, gap=10.0, max_width=140.0, hang=12.0)
    theme = Theme()
    _layout(wr)
    # First line at the frame edge; the continuation line is indented.
    assert kids[0].rendered_at[0] == pytest.approx(0.0)
    assert kids[2].rendered_at[0] == pytest.approx(12.0)
    # The indent participates in both the flow budget and the bbox.
    size = wr.measure(theme)
    assert size.w == pytest.approx(130)  # first line: 60+10+60
    # Continuation budget shrinks by the indent: 12+60+10+60=142 > 140,
    # so a fourth child would wrap again rather than overflow.
    kids4 = [_Probe(60, 10)] * 4
    wr4 = WrapRow(*kids4, gap=10.0, max_width=140.0, hang=12.0)
    assert len(wr4._lines(theme)) == 3


def test_rejects_unknown_align_values():
    with pytest.raises(ValueError):
        WrapRow(_Probe(10, 10), align="stretch")
    with pytest.raises(ValueError):
        WrapRow(_Probe(10, 10), line_align="justify")


def test_inflate_to_widens_frame_without_reflow():
    kids = [_Probe(30, 10), _Probe(30, 10)]
    wr = WrapRow(*kids, gap=5.0, max_width=100.0, line_align="end")
    wr.inflate_to(min_w=200.0)
    theme = Theme()
    assert wr.measure(theme).w == pytest.approx(200)
    _layout(wr)
    # line_align="end" pushes the single line to the widened right edge.
    assert kids[1].rendered_at[0] + 30 == pytest.approx(200)
