"""Print floors are opt-in: ``Theme.min_space`` defaults to 0.

With the default theme the fitter compresses spacing proportionally
(authored layouts keep their fitted size); a figure that wants floors
sets ``min_space`` and gets every floor at once."""
import pytest

from sciviz import (DEFAULT_THEME, Anchor, Box, Column, Connect, Diagram,
                    Palette, Row, Theme)
from sciviz.connect._resolver import _FlowResolver


def test_default_theme_has_no_print_floor():
    assert Theme().min_space == 0.0
    assert not Theme().print_floors
    assert Theme().with_overrides(min_space=2.0).print_floors


def _body():
    cards = [Anchor(n, Box(f"stage {n}", stroke=Palette.blue))
             for n in "abc"]
    return Column(Row(*cards, gap="sm"),
                  Connect("a", "b", src_side="right", dst_side="left"),
                  Connect("b", "c", src_side="right", dst_side="left"))


def test_without_floors_compression_is_proportional():
    theme = DEFAULT_THEME.with_overrides(unit=3.0)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    floor = d._compressed_theme(Diagram._FIT_MIN_DENSITY)
    assert floor.gap_px("sm") == pytest.approx(floor.unit * 1.0)
    assert floor.panel_padding == pytest.approx(
        theme.panel_padding * Diagram._FIT_MIN_DENSITY)


def test_with_floors_spacing_and_wire_ends_hold():
    theme = DEFAULT_THEME.with_overrides(unit=3.0, min_space=2.0)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    floor = d._compressed_theme(Diagram._FIT_MIN_DENSITY)
    assert floor.gap_px("sm") >= min(3.0, theme.min_space) - 1e-9
    a, b = Anchor("a", Box("a")), Anchor("b", Box("b"))
    body = Column(Row(a, b), Connect("a", "b", src_side="right",
                                     dst_side="left", head=True))
    _FlowResolver(body)._apply_flow_margins(floor)
    assert b.margin_left >= floor.arrow_gutter_px() - 1e-9
    assert a.margin_right >= floor.min_space - 1e-9


def test_floors_never_bind_at_the_authored_unit():
    plain = Diagram.for_paper(_body()).measure()
    floored = Diagram.for_paper(
        _body(), theme=DEFAULT_THEME.with_overrides(min_space=2.0)).measure()
    assert (plain.w, plain.h) == pytest.approx((floored.w, floored.h))


def test_fitted_size_without_floors_is_below_the_floored_one():
    kw = dict(target_width_pt=120.0)
    free = Diagram.for_paper(_body(), **kw)
    held = Diagram.for_paper(
        _body(), theme=DEFAULT_THEME.with_overrides(min_space=2.0), **kw)
    assert free.page_size().h <= held.page_size().h + 1e-6
