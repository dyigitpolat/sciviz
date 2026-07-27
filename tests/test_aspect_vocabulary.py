"""Aspect annotations: declaring the shape a figure -- or one component
of it -- should print at.

``Aspect("landscape", child)`` states an intent; the layout engine
reaches it by choosing among the layout alternatives that already exist
inside the subtree (``columns="auto"`` containers, ``Cycle`` ring
shapes). Nothing is scaled or letterboxed, and the annotation is
transparent: it measures and renders exactly like its child.
"""
from __future__ import annotations

import warnings

import pytest

from sciviz import (
    Anchor, Aspect, AspectSpec, Box, Card, Column, Cycle, DEFAULT_THEME,
    Diagram, EqualGrid, Palette, Row, card_header,
)
from sciviz.core import Canvas
from sciviz.core._aspect import NAMED_ASPECTS


TARGET = 252.0


def _card(title: str, lines: int = 2) -> Card:
    role = Palette.blue
    chips = [Box(f"descriptive chip label {i}", wrap=True, text_size="tiny",
                 fill=role.soft(), stroke=role) for i in range(lines)]
    return Card(card_header(title), *chips, role=role)


def _measure(d: Diagram):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d.render()
    return d._last_render_size


# --------------------------------------------------------------------
# the vocabulary
# --------------------------------------------------------------------

def test_named_shapes_read_as_width_over_height():
    """A landscape figure is wider than tall; a portrait one taller."""
    assert AspectSpec("landscape").min_ratio > 1.0
    assert AspectSpec("portrait").max_ratio < 1.0
    square = AspectSpec("square")
    assert square.min_ratio < 1.0 < square.max_ratio
    assert AspectSpec("landscape").contains(200.0, 100.0)
    assert not AspectSpec("landscape").contains(100.0, 200.0)


def test_named_bands_tile_the_ratio_line():
    """Adjacent names share an edge, so no proportion is unnameable."""
    ordered = sorted(NAMED_ASPECTS.values())
    for (_, hi), (lo, _) in zip(ordered, ordered[1:]):
        assert lo <= hi, "gap between adjacent named aspect bands"


def test_ratio_tightens_a_named_band():
    spec = AspectSpec("landscape", ratio=(1.85, 2.2))
    assert spec.min_ratio == pytest.approx(1.85)
    assert spec.max_ratio == pytest.approx(2.2)
    assert not spec.contains(150.0, 100.0)   # 1.5 is landscape but too square
    assert spec.contains(190.0, 100.0)


def test_ratio_contradicting_its_name_is_an_error():
    with pytest.raises(ValueError):
        AspectSpec("portrait", ratio=2.0)
    with pytest.raises(ValueError):
        AspectSpec("banner")


def test_penalty_is_relative_so_goals_are_comparable():
    """A small card missing its goal by 10% scores the same as a whole
    page missing it by 10% -- goals from different scopes add up."""
    spec = AspectSpec("square", ratio=(1.0, 1.0))
    small = spec.penalty(11.0, 10.0)
    large = spec.penalty(1100.0, 1000.0)
    assert small == pytest.approx(large)
    assert spec.penalty(10.0, 10.0) == 0.0


def test_numeric_target_aspect_keeps_its_height_over_width_meaning():
    """Figures written before the vocabulary existed keep their shape."""
    assert Diagram._normalise_aspect(None) is None
    assert Diagram._normalise_aspect(1.5) == pytest.approx((0.0, 1.5))
    assert Diagram._normalise_aspect((1.0, 1.3)) == pytest.approx((1.0, 1.3))


def test_named_target_aspect_lands_on_the_same_internal_band():
    lo, hi = Diagram._normalise_aspect("landscape")
    band = NAMED_ASPECTS["landscape"]
    assert lo == pytest.approx(1.0 / band[1])
    assert hi == pytest.approx(1.0 / band[0])


# --------------------------------------------------------------------
# the annotation
# --------------------------------------------------------------------

def test_annotation_is_transparent():
    """An Aspect wrapper must not change what it wraps."""
    inner = Row(_card("A"), _card("B"), gap="md")
    wrapped = Aspect("landscape", inner)
    assert wrapped.measure(DEFAULT_THEME).w == inner.measure(DEFAULT_THEME).w
    assert wrapped.measure(DEFAULT_THEME).h == inner.measure(DEFAULT_THEME).h
    bare, annotated = Canvas(), Canvas()
    inner.render(bare, 0.0, 0.0, DEFAULT_THEME)
    wrapped.render(annotated, 0.0, 0.0, DEFAULT_THEME)
    assert annotated.to_svg(400, 400) == bare.to_svg(400, 400)


def test_annotation_rejects_swapped_arguments():
    with pytest.raises(TypeError):
        Aspect(_card("A"), "landscape")


def test_component_goal_alone_drives_the_reflow_search():
    """No figure-level target_aspect: the component annotation is the
    only goal, and it must still be explored."""
    grid = EqualGrid(*[_card(f"C{i}") for i in range(6)], columns="auto")
    plain = Diagram.for_paper(grid, target_width_pt=TARGET)
    assert plain._reflow_assignments() == [()]

    grid2 = EqualGrid(*[_card(f"C{i}") for i in range(6)], columns="auto")
    annotated = Diagram.for_paper(Aspect("landscape", grid2),
                                  target_width_pt=TARGET)
    assert len(annotated._reflow_assignments()) > 1


def test_component_goal_reshapes_only_its_own_subtree():
    """Two sibling grids, one annotated: the annotation must move the
    annotated one and leave its sibling on the intrinsic default."""
    left = EqualGrid(*[Box(f"l{i}", width=30, height=18) for i in range(6)],
                     columns="auto")
    right = EqualGrid(*[Box(f"r{i}", width=30, height=18) for i in range(6)],
                      columns="auto")
    body = Row(Aspect("panorama", left, ratio=(3.5, 6.0)), right, gap="lg")
    d = Diagram.for_paper(body, target_width_pt=520.0)
    _measure(d)
    assert left._columns() == 5, "annotated grid did not reach its goal"
    assert right._columns() == 3, "unannotated sibling was disturbed"


def test_component_goal_is_reported_on_the_realised_layout():
    grid = EqualGrid(*[Box(f"b{i}", width=30, height=18) for i in range(6)],
                     columns=1)
    goal = Aspect("landscape", grid)
    assert goal.aspect_penalty(DEFAULT_THEME) > 0.0
    grid_wide = EqualGrid(*[Box(f"b{i}", width=30, height=18)
                            for i in range(6)], columns=3)
    assert Aspect("landscape", grid_wide).aspect_penalty(DEFAULT_THEME) == 0.0
    # Overshooting the band is a miss too: six in a row is a hairline,
    # not a landscape block.
    flat = EqualGrid(*[Box(f"b{i}", width=30, height=18) for i in range(6)],
                     columns=6)
    assert Aspect("landscape", flat).aspect_penalty(DEFAULT_THEME) > 0.0


def test_figure_level_goal_outranks_component_goals():
    """A component goal must never be satisfied at the cost of the
    printed page shape the figure declared."""
    grid = EqualGrid(*[_card(f"C{i}") for i in range(6)], columns="auto")
    d = Diagram.for_paper(Aspect("panorama", grid, ratio=(5.0, 9.0)),
                          target_width_pt=TARGET, target_aspect="portrait")
    size = _measure(d)
    assert size.h / max(size.w, TARGET) > 1.0, (
        "component goal overrode the figure-level portrait target")


# --------------------------------------------------------------------
# the annotation over a Cycle
# --------------------------------------------------------------------

def test_landscape_annotation_picks_the_wide_ring():
    stages = [Anchor(f"s{i}", Box(f"stage {i}", width=70, height=44))
              for i in range(6)]
    ring = Cycle(*stages, shape="auto")
    d = Diagram.for_paper(Aspect("landscape", ring), target_width_pt=420.0)
    _measure(d)
    assert ring.shape == (2, 3)


def test_portrait_annotation_picks_the_tall_ring():
    stages = [Anchor(f"s{i}", Box(f"stage {i}", width=70, height=44))
              for i in range(6)]
    ring = Cycle(*stages, shape="auto")
    d = Diagram.for_paper(Aspect("portrait", ring), target_width_pt=420.0)
    _measure(d)
    assert ring.shape == (3, 2)


# --------------------------------------------------------------------
# graceful degradation when the width target is unreachable
# --------------------------------------------------------------------

def test_unreachable_width_lets_the_declared_shape_decide():
    """Content too wide for the target at the authored font sizes: the
    shape goal must not be vetoed by a few points of overshoot."""
    stages = [Anchor(f"s{i}", Box(f"stage {i} of the loop", width=110,
                                  height=90)) for i in range(6)]
    ring = Cycle(*stages, shape="auto")
    # Neither ring reaches 225 pt, but both stay above the 5 pt floor
    # once scaled into it, so the declared shape is free to decide.
    d = Diagram.for_paper(ring, target_width_pt=225.0,
                          target_aspect="landscape",
                          min_effective_font_pt=5.0)
    _measure(d)
    assert ring.shape == (2, 3), (
        "the narrow ring won on width even though neither variant fits")


def test_reachable_width_still_wins_over_shape():
    """Historical contract: when a variant does reach the target, width
    comes first and shape only breaks ties."""
    grid = EqualGrid(*[_card(f"Wide card name {i}") for i in range(4)],
                     columns="auto")
    d = Diagram.for_paper(grid, target_width_pt=520.0,
                          target_aspect="portrait")
    size = _measure(d)
    assert size.w <= 520.0 * Diagram._FIT_TOLERANCE


def test_legibility_floor_is_the_width_ceiling_in_that_regime():
    d = Diagram.for_paper(Box("x", width=10, height=10),
                          target_width_pt=100.0, min_effective_font_pt=6.0)
    # 7pt type scaled to a 100pt-wide slot stays above 6pt until the
    # canvas reaches 100 * 7/6.
    assert d._legible_width_ceiling(100.0, 7.0) == pytest.approx(116.67, abs=0.1)
    # No text measured: fall back to the plain width tolerance.
    assert d._legible_width_ceiling(100.0, None) == pytest.approx(
        100.0 * Diagram._FIT_TOLERANCE)


def test_required_priority_buys_the_shape_with_print_scale():
    """The author says the shape is the point of the figure: the fitter
    may overshoot the width target, but only as far as the legibility
    floor allows."""
    def ring():
        stages = [Anchor(f"s{i}", Box(f"stage {i} of the loop", width=110,
                                      height=90)) for i in range(6)]
        return Cycle(*stages, shape="auto")

    # 250 pt is reachable by the tall ring but not by the wide one, so a
    # *preferred* landscape goal loses to the width fit.
    tall = ring()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Diagram.for_paper(tall, target_width_pt=250.0,
                          target_aspect="landscape").render()
    assert tall.shape == (3, 2)

    wide = ring()
    d = Diagram.for_paper(
        wide, target_width_pt=250.0, min_effective_font_pt=5.0,
        target_aspect=AspectSpec("landscape", priority="required"))
    _measure(d)
    assert wide.shape == (2, 3)


def test_required_priority_still_respects_the_legibility_floor():
    """"Required" is not "at any cost": a variant that would print
    below the floor is still rejected."""
    stages = [Anchor(f"s{i}", Box(f"stage {i} of the loop", width=110,
                                  height=90)) for i in range(6)]
    ring = Cycle(*stages, shape="auto")
    d = Diagram.for_paper(
        ring, target_width_pt=120.0, min_effective_font_pt=6.0,
        target_aspect=AspectSpec("landscape", priority="required"))
    _measure(d)
    assert ring.shape == (3, 2), "landscape was bought below the type floor"


def test_priority_is_validated_and_defaults_to_preferred():
    assert AspectSpec("landscape").priority == "preferred"
    assert not AspectSpec("landscape").is_required
    assert AspectSpec("landscape", priority="required").is_required
    assert Aspect("landscape", Box("x", width=9, height=9),
                  priority="required").spec.is_required
    with pytest.raises(ValueError):
        AspectSpec("landscape", priority="mandatory")
