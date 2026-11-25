"""Elastic spacing: target-width compression stops at print floors.

Under ``target_width_pt`` the fitter compresses ``unit`` while strokes,
arrowheads and fonts keep their size. Proportional compression shrank
the gutters between bordered cards towards zero (cards touching, wires
running along card edges). Spacing tokens now stop at
``min(authored, Theme.min_space)``; structural floors
(``Theme.arrow_gutter_px``) say how much room a wire needs.
"""
from __future__ import annotations

import warnings

import pytest

from sciviz import Box, Diagram, Palette, Row, Theme


TOKENS = ("xs", "sm", "md", "lg", "xl", "2xl", "3xl")


@pytest.mark.parametrize("unit", [6.0, 3.0])
def test_tokens_are_authored_values_without_compression(unit):
    theme = Theme().with_overrides(unit=unit)
    for tok in TOKENS:
        assert theme.gap_px(tok) == Theme._GAP_MAP[tok] * unit
    # The fitter's density-1 theme is the authored theme.
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    same = d._compressed_theme(1.0)
    for tok in TOKENS:
        assert same.gap_px(tok) == theme.gap_px(tok)


def test_compressed_tokens_stop_at_the_print_floor():
    theme = Theme().with_overrides(unit=3.0, min_space=2.0)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    floor = d._compressed_theme(Diagram._FIT_MIN_DENSITY)
    assert floor.authored_unit == 3.0
    # "sm" is 3 pt authored: compressed to 1.5 it would be thinner than
    # a readable gutter, so it stops at min_space.
    assert floor.gap_px("sm") == pytest.approx(theme.min_space)
    # "xs" is authored at 1.5 pt, already under the floor: kept as
    # written, never raised.
    assert floor.gap_px("xs") == pytest.approx(1.5)
    # Slack above the floor still compresses.
    assert floor.gap_px("xl") == pytest.approx(4.5 * 1.5)
    # Numeric gaps are the author's own number.
    assert floor.gap_px(7.0) == 7.0


def test_elastic_gap_is_monotone_in_density():
    theme = Theme().with_overrides(unit=3.0, min_space=2.0)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    for tok in TOKENS:
        vals = [d._compressed_theme(k / 20.0).gap_px(tok)
                for k in range(10, 21)]
        assert vals == sorted(vals)
        assert vals[-1] == theme.gap_px(tok)


def test_min_space_zero_restores_proportional_compression():
    theme = Theme().with_overrides(unit=3.0, min_space=0.0)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    assert d._compressed_theme(0.5).gap_px("sm") == pytest.approx(1.5)


def test_paddings_and_margin_follow_the_same_floor():
    theme = Theme().with_overrides(unit=3.0, min_space=2.0, panel_padding=3.0,
                                   diagram_margin=2.4)
    d = Diagram.for_paper(Box("x"), theme=theme, target_width_pt=100.0)
    floor = d._compressed_theme(0.5)
    assert floor.panel_padding == pytest.approx(2.0)
    assert floor.diagram_margin == pytest.approx(2.0)
    # chrome="none" margin (half a unit) is authored under the floor.
    assert d._margin_for(floor) == pytest.approx(1.5)


def test_fitted_row_of_bordered_cards_keeps_visible_gutters():
    """A row of bordered cards fitted to a narrow target never ends
    with gutters thinner than min_space (at unit 3, "sm" used to reach
    1.5 pt)."""
    role = Palette.blue
    theme = Theme().with_overrides(unit=3.0, min_space=2.0)
    cards = [Box(f"card number {i}", fill=role.soft(), stroke=role)
             for i in range(4)]
    body = Row(*cards, gap="sm")
    d = Diagram.for_paper(body, theme=theme, target_width_pt=150.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = d._layout_theme()
    assert fitted.unit < theme.unit  # the fit did compress
    row_w = body.measure(fitted).w
    cards_w = sum(c.measure(fitted).w for c in cards)
    assert (row_w - cards_w) / 3 >= theme.min_space - 1e-9


def test_arrow_gutter_holds_the_head_and_clearance_on_both_sides():
    theme = Theme().with_overrides(arrow_size=3.6, connector=1.15,
                                   min_space=2.0)
    assert theme.arrow_gutter_px() == pytest.approx(
        theme.arrow_head_px + 2 * theme.min_space)
    # At the default unit the default flow margin (unit * 5/3) already
    # clears the structural floor, so adopting it changes nothing there.
    default = Theme().with_overrides(min_space=2.0)
    assert default.unit * 5.0 / 3.0 >= default.arrow_gutter_px()
