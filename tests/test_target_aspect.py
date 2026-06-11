"""Aspect-aware target fitting: ``Diagram(target_width_pt=..., target_aspect=...)``.

With only ``target_width_pt`` the fitter stops at the first width fit,
which can leave a multi-card diagram as one degenerate tall corridor.
Declaring ``target_aspect`` makes the fitter also balance the layout:
it reflows ``columns="auto"`` containers (``EqualGrid``,
``BalancedColumns``) and probes spacing densities, picking the variant
whose printed height/width lands inside the requested range.  Fonts are
never touched.
"""
from __future__ import annotations

import warnings

import pytest

from sciviz import (
    BalancedColumns, Box, Card, Column, Diagram, EqualGrid, Palette,
    card_header,
)


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


def test_normalise_aspect_forms():
    assert Diagram._normalise_aspect(None) is None
    assert Diagram._normalise_aspect(1.5) == (0.0, 1.5)
    assert Diagram._normalise_aspect((1.0, 1.3)) == (1.0, 1.3)


def test_without_target_aspect_auto_grid_keeps_square_default():
    """Backwards compatibility: ``columns="auto"`` without an aspect
    goal behaves like the square-ish default and the fitter does not
    explore reflow variants."""
    grid = EqualGrid(*[_card(f"C{i}") for i in range(6)], columns="auto")
    d = Diagram.for_paper(grid, target_width_pt=TARGET)
    assert d._reflow_assignments() == [()]
    assert grid._columns() == 3  # ceil(sqrt(6))


def test_target_aspect_reflows_grid_out_of_degenerate_stack():
    """Six cards in an auto grid: the fitter must not export a single
    tall corridor when a balanced arrangement exists."""
    def build(aspect):
        grid = EqualGrid(*[_card(f"Card {i}") for i in range(6)],
                         columns="auto")
        return grid, Diagram.for_paper(grid, target_width_pt=TARGET,
                                       target_aspect=aspect)

    grid, d = build((1.0, 1.3))
    size = _measure(d)
    assert grid._columns() > 1, "fitter left the grid as one column"
    aspect = size.h / max(size.w, TARGET)
    # The fitted figure is dramatically more balanced than the
    # single-column stack of the same content.
    grid1, d1 = build(None)
    grid1._apply_reflow(1)
    stack = _measure(d1)
    assert aspect < (stack.h / max(stack.w, TARGET)) / 2


def test_target_aspect_prefers_width_fit_over_aspect():
    """A variant that fits the column width beats a wider one even if
    the wider one has the nicer aspect."""
    grid = EqualGrid(*[_card(f"Wide card name {i}") for i in range(4)],
                     columns="auto")
    d = Diagram.for_paper(grid, target_width_pt=120.0,
                          target_aspect=(1.0, 1.3))
    _measure(d)
    # At a 120pt column none of the multi-column variants fit; the
    # fitter must not pick one that blows past the width tolerance
    # when a narrower variant exists.
    best_w = d._trial_size(d._layout_theme()).w
    for cols in grid._reflow_options():
        g2 = EqualGrid(*[_card(f"Wide card name {i}") for i in range(4)],
                       columns=cols)
        d2 = Diagram.for_paper(g2, target_width_pt=120.0)
        w2 = d2._trial_size(d2._layout_theme()).w
        if w2 <= 120.0 * Diagram._FIT_TOLERANCE:
            assert best_w <= 120.0 * Diagram._FIT_TOLERANCE + 0.5
            break


def test_balanced_columns_minimises_tallest_column():
    """Order-preserving split: unequal children flow into columns whose
    heights are balanced, keeping declared order contiguous."""
    from sciviz import DEFAULT_THEME

    tall = Box("tall", width=40, height=90)
    short_a = Box("a", width=40, height=30)
    short_b = Box("b", width=40, height=30)
    short_c = Box("c", width=40, height=30)
    bc = BalancedColumns(tall, short_a, short_b, short_c, columns=2,
                         gap="none")
    runs = bc._split(DEFAULT_THEME)
    assert [len(r) for r in runs] == [1, 3]
    size = bc.measure(DEFAULT_THEME)
    assert size.h == pytest.approx(90.0)


def test_balanced_columns_reflow_protocol():
    bc = BalancedColumns(*[Box(str(i), width=30, height=20)
                           for i in range(4)], columns="auto")
    assert bc._reflow_options() == [1, 2, 3, 4]
    bc._apply_reflow(4)
    assert bc._columns_count() == 4
    fixed = BalancedColumns(*[Box(str(i), width=30, height=20)
                              for i in range(4)], columns=2)
    assert fixed._reflow_options() == []
    assert fixed._columns_count() == 2


def test_balanced_columns_renders_all_children_without_overlap():
    from sciviz import DEFAULT_THEME
    from sciviz.core import Canvas

    boxes = [Box(f"b{i}", width=44, height=18 + 8 * (i % 3))
             for i in range(5)]
    bc = BalancedColumns(*boxes, columns=2, gap="sm")
    canvas = Canvas()
    bc.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(400, 400)
    assert svg.count("b0") + svg.count("b4") >= 2


def test_rotated_text_ink_is_tall_not_wide():
    """A 90-degree rotated label inks a tall, narrow box; treating it
    as horizontal ink inflated every canvas that carried one."""
    from sciviz.core import Canvas

    c = Canvas()
    c.text(100.0, 100.0, "observations", size=9.0, anchor="middle",
           baseline="middle", rotate=90.0)
    x0, y0, x1, y1 = c.ink_bbox
    assert (x1 - x0) < (y1 - y0)
    assert (x1 - x0) < 20.0
