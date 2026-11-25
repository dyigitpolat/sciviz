"""Width fitting when width does not fall steadily with spacing density.

Discrete layout decisions (a wire caption set beside its wire instead of
on it, a label re-wrap, a routed lane moving outward) can make a tighter
candidate WIDER. The density fixed-point then stalls above the target
although a looser-than-floor density fits; the fitter must find it.
The exported page (connector ink included) is reported by
``Diagram.page_size``.
"""
from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Column, Connect, Diagram, Row
from sciviz.core._bbox import BBox


TARGET = 396.0


def _stepped(d: Diagram, widths, min_text: float = 6.5):
    """Replace the trial with a synthetic width-vs-density profile. Its
    text sits at the figure's legibility floor unless ``min_text`` says
    otherwise (see ``_floor``)."""
    base = d.theme.unit
    calls = []

    def trial(theme, assignment=()):
        dens = theme.unit / base
        calls.append(round(dens, 4))
        return BBox(widths(dens), 180.0), 0.0, min_text

    d._trial = trial
    return calls


def test_fit_finds_a_density_past_a_width_jump():
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    # Wider than the target down to 0.62, then comfortably narrower:
    # the fixed-point creeps down in ever-smaller steps and stalls.
    _stepped(d, lambda dens: 430.0 if dens > 0.62 else 380.0)
    theme, size, density, _, _ = d._fit_density(TARGET)
    assert size.w <= TARGET
    # The looser neighbour is bisected towards: little spacing is lost.
    assert 0.6 <= density <= 0.62 + 1e-9


def test_fit_skips_a_wider_island_between_fitting_densities():
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    # Fits at 0.8, is wider at 0.7 (a caption set beside its wire),
    # fits again below: the least compressed fitting density wins.
    def widths(dens):
        if dens > 0.85:
            return 402.0 + 60.0 * (dens - 0.85)
        if 0.75 < dens <= 0.85:
            return 390.0
        if 0.55 < dens <= 0.75:
            return 432.0
        return 382.0
    _stepped(d, widths)
    _, size, density, _, _ = d._fit_density(TARGET)
    assert size.w <= TARGET
    assert density > 0.75


def test_nothing_fits_returns_the_narrowest_candidate():
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    _stepped(d, lambda dens: 500.0 - 10.0 * abs(dens - 0.7))
    _, size, _, _, _ = d._fit_density(TARGET)
    assert size.w == min(500.0 - 10.0 * abs(x / 100 - 0.7)
                         for x in range(50, 101))


def test_steady_content_lands_without_the_grid_scan():
    """Monotone content whose fixed-point converges slowly (most of its
    width does not scale with spacing) lands by a secant step on the
    fixed-point's own trials; the density grid is never scanned."""
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    calls = _stepped(d, lambda dens: 300.0 + 120.0 * dens)
    _, size, _, _, _ = d._fit_density(TARGET)
    assert TARGET - 1.0 <= size.w <= TARGET + 0.5
    assert len(calls) <= 1 + Diagram._FIT_PASSES + Diagram._FIT_SECANT_STEPS
    grid = {round(1.0 - k * Diagram._FIT_SCAN_STEP, 4) for k in range(1, 11)}
    assert not grid & set(calls)


def test_converging_content_keeps_the_fixed_point_result():
    """Content the fixed-point lands on its own is not re-fitted."""
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    calls = _stepped(d, lambda dens: 44.0 + 400.0 * dens)
    _, size, _, _, _ = d._fit_density(TARGET)
    assert size.w <= TARGET + 0.5
    grid = {round(1.0 - k * Diagram._FIT_SCAN_STEP, 4) for k in range(1, 11)}
    assert not grid & set(calls)
    assert len(set(calls)) <= 1 + Diagram._FIT_PASSES


def test_page_size_includes_connector_ink_outside_the_layout():
    """A labelled top-to-top wire runs in a lane above both cards: the
    page holds it, the laid-out box does not."""
    body = Column(
        Row(Anchor("a", Box("source card")), Box("middle card"),
            Anchor("b", Box("target card")), gap="lg"),
        Connect("a", "b", src_side="top", dst_side="top",
                label="a labelled lane above"),
    )
    d = Diagram.for_paper(body)
    page = d.page_size()
    assert page.h >= d.measure().h - 0.5
    svg_h = float(d.render().split('height="', 1)[1].split('"', 1)[0]
                  .rstrip("ptx"))
    assert abs(svg_h - page.h) < 0.01


def test_width_allowance_never_carries_text_below_the_floor():
    """The 5 % overshoot tolerance is a scale-down at export; text
    authored at the legibility floor may not be scaled down at all."""
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.5)
    assert d._width_allowance(TARGET, 6.5) == TARGET
    # Text authored above the floor may take part of the tolerance.
    assert TARGET < d._width_allowance(TARGET, 6.7) <= TARGET * 6.7 / 6.5
    assert d._width_allowance(TARGET, 9.0) == TARGET * Diagram._FIT_TOLERANCE
    assert d._width_allowance(TARGET, None) == TARGET * Diagram._FIT_TOLERANCE


def test_text_widths_are_memoised_per_face():
    from sciviz.core import _fonts
    fam = "'STIXGeneral', serif"
    _fonts._measure_text_width_at_ref.cache_clear()
    a = _fonts.measure_text_width("memoised width probe", 6.5, fam)
    b = _fonts.measure_text_width("memoised width probe", 13.0, fam)
    info = _fonts._measure_text_width_at_ref.cache_info()
    if a is None:          # no font backend in this environment
        return
    assert b == pytest.approx(2 * a)
    assert info.hits >= 1 and info.misses == 1
    bold = _fonts.measure_text_width("memoised width probe", 6.5, fam,
                                     bold=True)
    assert bold != a
    assert _fonts.measure_text_width("", 6.5, fam) == 0.0


def test_text_above_the_floor_keeps_its_spacing_within_the_tolerance():
    """Overshoot the export may absorb by a legible scale-down (text above
    the floor, within _FIT_TOLERANCE) is not worth compressing spacing
    for: no scan runs and the fixed-point result stands."""
    d = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                          min_effective_font_pt=6.0)
    calls = _stepped(d, lambda dens: 410.0 if dens > 0.62 else 380.0,
                     min_text=9.0)
    _, size, _, _, _ = d._fit_density(TARGET)
    grid = {round(1.0 - k * Diagram._FIT_SCAN_STEP, 4) for k in range(1, 11)}
    assert not grid & set(calls)
    assert size.w == 410.0
    # Past the tolerance, the scan finds the fitting density after all.
    d2 = Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                           min_effective_font_pt=6.0)
    _stepped(d2, lambda dens: 430.0 if dens > 0.62 else 380.0, min_text=9.0)
    assert d2._fit_density(TARGET)[1].w == 380.0
