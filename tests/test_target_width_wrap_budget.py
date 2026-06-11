"""Wrap-budget continuation of target-width fitting.

Spacing density never compresses below ``_FIT_MIN_DENSITY`` (padding
would read as cramped), but text wrap budgets can keep shrinking past
that point without hurting legibility: labels re-wrap onto more lines
while fonts and paddings keep their authored sizes, and the
longest-word floor inside ``Box`` bounds the narrowing.  These tests
pin (a) the ``Theme.wrap_budget`` token that ``Box(wrap=True)``
consumes and (b) the fitter phase that compresses it once the density
floor alone cannot reach ``target_width_pt``.
"""
from __future__ import annotations

import re
import warnings

import pytest

from sciviz import Box, Diagram, Palette, Row, Theme


TARGET = 252.0  # IEEE \columnwidth in points


def test_box_honors_theme_wrap_budget_token():
    """A tighter ``wrap_budget`` re-wraps a multi-word label onto more,
    narrower lines: the box gets narrower and taller, never wider."""
    theme = Theme()
    tight = theme.with_overrides(wrap_budget=theme.wrap_budget / 2)
    label = "first second third fourth fifth sixth seventh"
    wide = Box(label, wrap=True, text_size="tiny").measure(theme)
    narrow = Box(label, wrap=True, text_size="tiny").measure(tight)
    assert narrow.w < wide.w
    assert narrow.h > wide.h


def _floor_bound_body() -> Row:
    """Wider than one column even at the spacing-density floor: each
    chip's two-word lines sit just under the floor's wrap budget, so
    only wrap-budget compression can narrow the row further."""
    role = Palette.blue
    return Row(
        *[Box("alpha beta gamma delta", wrap=True, text_size="tiny",
              fill=role.soft(), stroke=role, shape_key="")
          for _ in range(6)],
        gap="sm",
    )


def test_wrap_budget_compresses_past_density_floor():
    """When the density floor leaves the canvas over the target, the
    fitter keeps compressing the wrap budget alone until the width
    lands on the target -- with every font at its authored size."""
    base = Theme()
    d = Diagram.for_paper(_floor_bound_body(), target_width_pt=TARGET)
    floor = d._compressed_theme(d._FIT_MIN_DENSITY)
    floor_w = d._trial_size(floor).w
    assert floor_w > TARGET, (
        "fixture must overflow the target at the spacing-density floor")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        svg = d.render()
    assert d._last_render_size.w == pytest.approx(TARGET, rel=0.05)
    fitted = d._layout_theme()
    assert fitted.wrap_budget < base.wrap_budget, (
        "the wrap-budget phase must have engaged")
    assert fitted.wrap_budget >= base.wrap_budget * d._FIT_MIN_WRAP - 1e-9
    sizes = {float(s) for s in re.findall(r'font-size="([0-9.]+)"', svg)}
    authored = {base.font_tiny, base.font_small, base.font_micro,
                base.font_label, base.font_section}
    assert sizes and all(
        any(abs(s - a) < 0.05 for a in authored) for s in sizes)


def test_wrap_budget_untouched_when_density_suffices():
    """A diagram the density walk alone can fit keeps the authored wrap
    budget: the continuation phase only runs on a floor-bound layout."""
    role = Palette.blue
    body = Row(
        *[Box("some moderately long wrapped label", wrap=True,
              text_size="tiny", fill=role.soft(), stroke=role)
          for _ in range(3)],
        gap="md",
    )
    d = Diagram.for_paper(body, target_width_pt=TARGET)
    d.render()
    assert d._layout_theme().wrap_budget == pytest.approx(
        Theme().wrap_budget)
