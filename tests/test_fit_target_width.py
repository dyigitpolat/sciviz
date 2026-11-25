"""Width fit: bracketed search, bounded trials, and the fit report.

The fitter used to scan an 11-point density grid whenever the density
fixed-point stalled -- also when nothing could land -- and then crept on
the wrap budget for up to eight trials whose width did not move. It now
brackets the target with the spacing floor, bisects towards the looser
side only when the floor lands, stops the wrap continuation after two
steps without progress, and reports what holds the width up.
"""
from __future__ import annotations

import warnings

from sciviz import Anchor, Box, Column, Connect, Diagram, FitReport, Row
from sciviz.core._bbox import BBox


TARGET = 396.0


def _profile(d: Diagram, widths):
    """Replace the trial with ``widths(density, wrap_scale)``; text sits
    at the legibility floor, so landing means ``w <= target + 0.5``."""
    base_unit, base_wrap = d.theme.unit, d.theme.wrap_budget
    calls = []

    def trial(theme, assignment=()):
        dens = round(theme.unit / base_unit, 4)
        wrap = round(theme.wrap_budget / base_wrap, 4)
        calls.append((dens, wrap))
        return BBox(widths(dens, wrap), 180.0), 0.0, 6.5

    d._trial = trial
    return calls


def _diagram():
    return Diagram.for_paper(Box("x"), target_width_pt=TARGET,
                             min_effective_font_pt=6.5)


def test_floor_bound_content_stops_without_scanning_or_creeping():
    """Nothing lands at any density and re-wrapping moves nothing: the
    fit tries the floor once, stops the wrap continuation after two
    stalled steps, and keeps the narrowest trial."""
    d = _diagram()
    calls = _profile(d, lambda dens, wrap: 420.0 + 10.0 * dens)
    _, size, density, _, _ = d._fit_density(TARGET)
    assert size.w == 425.0 and density == Diagram._FIT_MIN_DENSITY
    grid = {round(1.0 - k * Diagram._FIT_SCAN_STEP, 4) for k in range(1, 10)}
    assert not grid & {c[0] for c in calls}
    wrap_trials = [c for c in calls if c[1] < 1.0]
    assert len(wrap_trials) <= 2
    assert len(calls) <= 1 + Diagram._FIT_PASSES + 1 + 2


def test_a_floor_that_lands_is_bisected_towards_looser_spacing():
    """The fixed-point stalls on a plateau above the target; the floor
    lands, so the bracket between them is bisected and the least
    compressed landing density found wins."""
    d = _diagram()
    calls = _profile(d, lambda dens, wrap: 400.0 if dens > 0.55 else 390.0)
    _, size, density, _, _ = d._fit_density(TARGET)
    assert size.w <= TARGET
    assert 0.5 < density <= 0.55
    assert len(calls) <= (1 + Diagram._FIT_PASSES + Diagram._FIT_SECANT_STEPS
                          + 1 + Diagram._FIT_SCAN_BISECT)


def test_the_fit_never_returns_a_width_that_does_not_land_when_one_did():
    """Width islands (discrete caption and routing decisions) anywhere in
    the range: whenever a landing trial was seen, the result lands."""
    profiles = [
        lambda d, w: 430.0 if 0.6 < d < 0.9 else 380.0,
        lambda d, w: 380.0 if 0.7 < d < 0.75 else 430.0,
        lambda d, w: 395.0 if d < 0.8 else 800.0,
        lambda d, w: 300.0 + 120.0 * d if d < 0.93 else 808.0,
    ]
    for widths in profiles:
        d = _diagram()
        calls = _profile(d, widths)
        _, size, _, _, _ = d._fit_density(TARGET)
        seen = [widths(dens, wrap) for dens, wrap in calls]
        if any(w <= TARGET + 0.5 for w in seen):
            assert size.w <= TARGET + 0.5
        else:
            assert size.w == min(seen)


def test_fit_report_names_the_width_drivers():
    """A figure that cannot land: the report says so and names the
    authored numeric gap and the widest leaves on the critical path."""
    body = Row(Box("a rather long label that does not wrap"),
               Column(Box("short"), Box("the widest label in the column")),
               gap=7.0)
    d = Diagram.for_paper(body, target_width_pt=120.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = d.fit_report()
    assert isinstance(report, FitReport)
    assert not report.landed
    assert report.trials >= 2 and report.seconds >= 0.0
    whats = [w for _, w, _ in report.drivers]
    assert any("numeric gap=7" in w for w in whats)
    assert any("the widest label in the column" in w for w in whats)
    # "short" is stretched to its sibling's width by layout, but it
    # does not set the column's width.
    assert not any('"short"' in w for w in whats)
    depths = [d for d, _, _ in report.drivers]
    assert depths == sorted(depths)  # top-level split first
    text = str(report)
    assert "OVER by" in text and "width drivers" in text


def test_fit_report_lists_ink_outside_the_layout():
    body = Column(
        Row(Anchor("a", Box("source card")), Box("middle card"),
            Anchor("b", Box("target card")), gap="lg"),
        Connect("a", "b", src_side="top", dst_side="top",
                label="a labelled lane above"),
    )
    d = Diagram.for_paper(body)
    report = d.fit_report()
    assert report.target is None and report.landed
    page = d.page_size()
    assert (report.width, report.height) == (page.w, page.h)
    sides = {side for _, side, _ in report.overflow}
    assert sides <= {"left", "top", "right", "bottom"}
    for _, _, extent in report.overflow:
        assert extent > 0.5


def test_overflow_items_reports_the_deepest_overshoot_per_kind_and_side():
    from sciviz import Canvas
    from sciviz.auto.ink import overflow_items
    canvas = Canvas()
    canvas.rect(10, 10, 50, 20)             # inside
    canvas.rect(-12, 30, 20, 5)             # 12 past the left edge
    canvas.rect(-4, 40, 10, 5)              # shallower, same side
    canvas.text(60, 108, "caption", size=8)  # below the box
    items = overflow_items(canvas, (0.0, 0.0, 100.0, 100.0))
    kinds = {(k, s): e for k, s, e in items}
    assert kinds[("shape", "left")] > 11.0
    assert ("text", "bottom") in kinds
    assert items == sorted(items, key=lambda t: -t[2])
