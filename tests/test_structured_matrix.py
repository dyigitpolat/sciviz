"""Focused tests for structured Matrix cells and selections."""

from __future__ import annotations

import re

import pytest

from sciviz import Anchor, Box, Canvas, Column, Connect, Diagram, Theme
from sciviz.elements._matrix import (
    ColorScale,
    Matrix,
    MatrixCell,
    MatrixGroup,
    MatrixSelection,
)


def _render(element):
    theme = Theme()
    size = element.measure(theme)
    canvas = Canvas()
    element.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), theme, size, canvas


def test_color_scale_centered_normalization_and_reverse():
    scale = ColorScale(domain=(-1, 3), center=0)
    assert scale.normalized(-100) == 0.0
    assert scale.normalized(-1) == 0.0
    assert scale.normalized(0) == 0.5
    assert scale.normalized(3) == 1.0
    assert scale.normalized(100) == 1.0

    reverse = ColorScale(domain=(-1, 3), center=0, reverse=True)
    assert reverse.normalized(-1) == 1.0
    assert reverse.normalized(0) == 0.5
    assert reverse.normalized(3) == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"domain": (1, 1)},
        {"domain": (2, 1)},
        {"domain": (0, float("inf"))},
        {"domain": (0, 1), "center": 0},
        {"domain": (0, 1), "center": 1},
        {"domain": (0, 1), "palette": "not-a-palette"},
    ],
)
def test_color_scale_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        ColorScale(**kwargs)


def test_structured_cell_renders_primary_detail_mark_and_emphasis():
    matrix = Matrix(
        [[MatrixCell(value=0.18, label="23.01", detail="+0.18",
                     emphasis=True, mark="check")]],
        scale=ColorScale((-1, 1), center=0),
        row_labels=None,
        col_labels=None,
        cell_size="lg",
    )
    svg, _, _, _ = _render(matrix)
    assert ">23.01<" in svg
    assert ">+0.18<" in svg
    assert ">✓<" in svg
    assert re.search(r"font-weight=\"700\"[^>]*>23\.01<", svg)


def test_matrix_cell_role_overrides_numeric_scale_fill():
    matrix = Matrix(
        [[MatrixCell(value=-1.0, label="active", role="positive")]],
        scale=ColorScale((-1, 1), center=0),
        row_labels=None,
        col_labels=None,
    )
    svg, theme, _, _ = _render(matrix)
    assert f'fill="{theme.color_of("positive")}"' in svg
    assert f'fill="{matrix.scale.color(theme, -1.0)}"' not in svg


def test_shared_scale_maps_equal_values_to_equal_fills():
    scale = ColorScale((-2, 2), center=0)
    left = Matrix([[MatrixCell(0.5, label="left")]], scale=scale,
                  row_labels=None, col_labels=None)
    right = Matrix([[MatrixCell(0.5, label="right")]], scale=scale,
                   row_labels=None, col_labels=None)
    left_svg, theme, _, _ = _render(left)
    right_svg, _, _, _ = _render(right)
    expected = scale.color(theme, 0.5)
    assert f'fill="{expected}"' in left_svg
    assert f'fill="{expected}"' in right_svg


def test_bottom_column_labels_and_semantic_xl_cells_are_measured():
    matrix = Matrix(
        [[MatrixCell(0.0, label="value")]],
        scale=ColorScale((-1, 1), center=0),
        row_labels=None,
        col_labels=("below",),
        col_label_position="bottom",
        cell_size="xl",
    )
    svg, _, size, _ = _render(matrix)
    assert matrix._cell_px(Theme()) == 54.0
    assert ">below<" in svg
    assert size.h > 54.0
    label_y = float(re.search(r'<text[^>]+y="([\d.]+)"[^>]*>below<', svg).group(1))
    assert label_y > 54.0


def test_discrete_and_dense_matrices_use_square_shared_grid_boundaries():
    categorical = Matrix(
        [[MatrixCell(1, role="positive", mark="check"),
          MatrixCell(0, role="white")]],
        row_labels=None,
        col_labels=None,
        cell_size=20,
    )
    dense = Matrix(
        [[0, 1], [1, 0]],
        scale=ColorScale((0, 1), palette="blues"),
        row_labels=None,
        col_labels=None,
        cell_size=12,
    )
    annotated = Matrix(
        [[MatrixCell(0.5, label="0.50", detail="+0.1")]],
        scale=ColorScale((0, 1), palette="blues"),
        row_labels=None,
        col_labels=None,
        cell_size="lg",
    )
    categorical_svg, _, _, _ = _render(categorical)
    dense_svg, _, _, _ = _render(dense)
    annotated_svg, _, _, _ = _render(annotated)
    assert "rx=" not in categorical_svg
    assert "rx=" not in dense_svg
    assert "rx=" in annotated_svg


def test_dense_matrix_has_semantic_micro_and_tiny_cell_sizes():
    micro = Matrix([[0, 1], [1, 0]], cell_size="micro",
                   row_labels=None, col_labels=None)
    tiny = Matrix([[0, 1], [1, 0]], cell_size="tiny",
                  row_labels=None, col_labels=None)
    assert micro.measure(Theme()).w == 20
    assert tiny.measure(Theme()).w == 28


def test_matrix_publishes_full_bounds_as_router_obstacle():
    from sciviz.composition import _anchor_stack

    matrix = Matrix([[0, 1], [1, 0]], cell_size="tiny",
                    row_labels=None, col_labels=None)
    registry = {}
    token = _anchor_stack.set([registry])
    try:
        matrix.render(Canvas(), 5.0, 7.0, Theme())
    finally:
        _anchor_stack.reset(token)

    obstacle = next(value for key, value in registry.items()
                    if key.startswith("_auto_obstacle_"))
    assert obstacle == (5.0, 7.0, 28.0, 28.0)


def test_matrix_rejects_unknown_column_label_position():
    with pytest.raises(ValueError, match="col_label_position"):
        Matrix([[1]], col_label_position="left")


def test_selection_bbox_is_cell_aligned_and_non_destructive():
    scale = ColorScale((0, 8), palette="blues")
    selection = MatrixSelection(
        rows=1,
        cols=slice(1, 3),
        name="window",
        role="highlight",
        style="dashed",
        label="active window",
        label_position="top",
    )
    matrix = Matrix(
        [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
        scale=scale,
        selections=[selection],
        row_labels=None,
        col_labels=None,
        cell_size=20,
    )
    assert matrix.selection_bboxes(Theme()) == {
        "window": (20.0, 20.0, 40.0, 20.0)
    }
    svg, theme, size, canvas = _render(matrix)
    # A selection is an outline, unlike legacy prune highlighting: selected
    # cells retain their scale fills and no disabled cell fill is introduced.
    assert 'fill="#f8fafc"' not in svg
    assert 'stroke-dasharray="5,3"' in svg
    assert f'stroke="{theme.color_of("highlight")}"' in svg
    assert "active window" in svg
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= 0 and y0 >= 0
    assert x1 <= size.w and y1 <= size.h


def test_long_structured_text_is_fitted_inside_measured_cell():
    matrix = Matrix(
        [[MatrixCell(value=0.1,
                     label="a very long structured value",
                     detail="a similarly long detail")]],
        scale=ColorScale((-1, 1), center=0),
        row_labels=None,
        col_labels=None,
        cell_size=28,
    )
    _, _, size, canvas = _render(matrix)
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= 0 and y0 >= 0
    assert x1 <= size.w and y1 <= size.h


def test_named_selection_is_available_to_routed_connect():
    matrix = Matrix(
        [[1, 2], [3, 4]],
        scale=ColorScale((1, 4), palette="blues"),
        selections=[MatrixSelection(0, 0, name="selected-cell")],
        row_labels=None,
        col_labels=None,
    )
    body = Column(
        matrix,
        Anchor("sink", Box("sink")),
        Connect("selected-cell", "sink", label="selection"),
        gap="lg",
    )
    svg = Diagram.for_paper(body).render()
    assert "selection" in svg
    assert "selected-cell" not in svg  # anchor identity is metadata only


def test_structured_matrix_validates_shape_cells_and_selections():
    with pytest.raises(ValueError, match="equal length"):
        Matrix(
            [[MatrixCell(1)], [MatrixCell(2), MatrixCell(3)]],
            row_labels=None,
            col_labels=None,
        )
    with pytest.raises(TypeError, match="numeric or MatrixCell"):
        Matrix([[MatrixCell(1), object()]], row_labels=None, col_labels=None)
    with pytest.raises(IndexError, match="out of range"):
        Matrix([[1]], selections=[MatrixSelection(2, 0)])
    with pytest.raises(ValueError, match="selects no cells"):
        Matrix([[1, 2]], selections=[MatrixSelection(0, slice(1, 1))])
    with pytest.raises(ValueError, match="unique"):
        Matrix(
            [[1, 2]],
            selections=[
                MatrixSelection(0, 0, name="same"),
                MatrixSelection(0, 1, name="same"),
            ],
        )
    with pytest.raises(ValueError, match="cannot be combined"):
        Matrix([[1]], scale=ColorScale((0, 1)), vmin=0)


def test_numeric_matrix_retains_legacy_mask_highlight_and_value_behavior():
    matrix = Matrix(
        [[0.25, 0.75], [0.5, 1.0]],
        row_labels=None,
        col_labels=None,
        show_values=True,
        mask=[[False, True], [False, False]],
        highlight_rows=[1],
        vmin=0,
        vmax=1,
    )
    assert matrix._structured is False
    svg, _, _, _ = _render(matrix)
    assert ">0.25<" in svg
    assert ">0.75<" not in svg
    assert 'fill="#f8fafc"' in svg
    assert svg.count('stroke-dasharray="2,1.5"') == 3
    assert 'stroke-dasharray="5,3"' in svg


def test_binary_color_scale_uses_soft_mid_tone_for_active_mask_cells():
    matrix = Matrix(
        [[0, 1], [0, 0]],
        scale=ColorScale((0, 1), palette="blues"),
        row_labels=None,
        col_labels=None,
        cell_size="tiny",
    )
    svg, theme, _, _ = _render(matrix)
    palette = theme.palette("blues")
    expected = palette[round(0.42 * (len(palette) - 1))]
    assert f'fill="{expected}"' in svg
    assert f'fill="{palette[-1]}"' not in svg


def test_grouped_matrix_renders_axis_bands_rotated_labels_and_partitions():
    matrix = Matrix(
        [[MatrixCell(role="primary_soft") for _ in range(4)] for _ in range(4)],
        row_labels=["q1", "q2", "d1", "d2"],
        col_labels=["k1", "k2", "m1", "m2"],
        col_label_angle=-45,
        row_groups=[
            MatrixGroup("Q_AR", 0, 2, "primary"),
            MatrixGroup("Q_DM", 2, 4, "warning"),
        ],
        col_groups=[
            MatrixGroup("K_AR", 0, 2, "primary"),
            MatrixGroup("K_DM", 2, 4, "warning"),
        ],
        row_partitions=[2],
        col_partitions=[2],
        cell_size="sm",
    )
    svg, theme, size, _canvas = _render(matrix)

    assert "Q_AR" in svg and "K_DM" in svg
    assert 'rotate(-45' in svg
    assert f'stroke-width="{theme.thick:.2f}"' in svg
    assert size.w > 4 * matrix._cell_px(theme)
    assert size.h > 4 * matrix._cell_px(theme)


def test_selection_can_be_center_label_without_extra_outline():
    matrix = Matrix(
        [[MatrixCell(role="primary_soft") for _ in range(3)] for _ in range(3)],
        selections=[
            MatrixSelection(
                slice(0, 3),
                slice(0, 3),
                style="none",
                label="Full\nattend",
                label_position="center",
                role="primary",
            )
        ],
        row_labels=None,
        col_labels=None,
        cell_size="sm",
    )
    svg, _theme, _size, _canvas = _render(matrix)

    assert ">Full<" in svg and ">attend<" in svg


def test_matrix_axis_annotations_validate_ranges():
    with pytest.raises(IndexError, match="exceeds"):
        Matrix([[1]], row_groups=[MatrixGroup("rows", 0, 2)])
    with pytest.raises(ValueError, match="partition"):
        Matrix([[1, 2]], col_partitions=[2])
    with pytest.raises(ValueError, match="label_position"):
        MatrixSelection(0, 0, label_position="diagonal")


def test_narrow_selection_auto_moves_label_to_side_extent_annotation():
    theme = Theme()
    auto = Matrix(
        [[MatrixCell() for _ in range(2)] for _ in range(5)],
        row_labels=None,
        col_labels=None,
        cell_size="xs",
        selections=[MatrixSelection(
            slice(1, 5), slice(0, 2),
            label="Active window", style="dashed",
        )],
    )
    internal = Matrix(
        [[MatrixCell() for _ in range(2)] for _ in range(5)],
        row_labels=None,
        col_labels=None,
        cell_size="xs",
        selections=[MatrixSelection(
            slice(1, 5), slice(0, 2),
            label="Active window", style="dashed",
            label_position="top",
        )],
    )

    assert auto.measure(theme).w > internal.measure(theme).w
    canvas = Canvas()
    size = auto.measure(theme)
    auto.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    assert ">Active<" in svg and ">window<" in svg
    assert "selection-extent" in svg


def test_wide_column_group_labels_wrap_to_their_span():
    theme = Theme()
    grid = [[MatrixCell(role="primary_soft") for _ in range(8)]
            for _ in range(2)]
    short = Matrix(
        grid,
        row_labels=None,
        col_labels=None,
        cell_size="sm",
        col_groups=[MatrixGroup("A", 0, 4), MatrixGroup("B", 4, 8)],
    )
    wrapped = Matrix(
        grid,
        row_labels=None,
        col_labels=None,
        cell_size="sm",
        col_groups=[
            MatrixGroup("Quantization and conversion", 0, 4),
            MatrixGroup("Mapping and architecture search", 4, 8),
        ],
    )
    # Long labels must claim extra rows above the grid, not spill sideways
    # into the neighbouring group.
    assert wrapped._group_space(theme, "col") > short._group_space(theme, "col")

    svg, _theme, _size, _canvas = _render(wrapped)
    assert ">Quantization<" in svg or ">Quantization and<" in svg
    assert ">search<" in svg or ">architecture search<" in svg
    # Every rendered line fits inside a four-cell span.
    span = 4 * wrapped._cell_px(theme) - theme.unit * 0.8
    lines, font, _line_h = wrapped._group_label_layout(theme, "col")
    for group_lines in lines:
        for line in group_lines:
            assert theme.text_width(line, "small") * (
                font / theme.size_px("small")
            ) <= span + 1e-6


def test_single_line_group_labels_keep_compact_band():
    theme = Theme()
    matrix = Matrix(
        [[MatrixCell(role="primary_soft") for _ in range(4)]
         for _ in range(4)],
        row_labels=None,
        col_labels=None,
        cell_size="sm",
        row_groups=[MatrixGroup("Q", 0, 2), MatrixGroup("K", 2, 4)],
        col_groups=[MatrixGroup("A", 0, 2), MatrixGroup("B", 2, 4)],
    )
    assert matrix._group_space(theme, "col") == pytest.approx(
        theme.text_height("small") + theme.unit * 1.15
    )
    assert matrix._group_space(theme, "row") == pytest.approx(
        theme.text_height("small") + theme.unit * 1.25
    )


def test_unbreakable_group_word_shrinks_shared_font_with_floor():
    theme = Theme()
    matrix = Matrix(
        [[MatrixCell(role="primary_soft") for _ in range(2)]
         for _ in range(2)],
        row_labels=None,
        col_labels=None,
        cell_size="sm",
        col_groups=[MatrixGroup("Hyperparameterization", 0, 2)],
    )
    _lines, font, _line_h = matrix._group_label_layout(theme, "col")
    assert font < theme.size_px("small")
    assert font >= theme.size_px("micro")


def test_multiline_row_labels_render_muted_tiny_sublabels():
    grid = [[MatrixCell() for _ in range(2)] for _ in range(2)]
    matrix = Matrix(
        grid,
        row_labels=["Fan-out per core\nLoihi: 4096 edges", "Weight precision"],
        col_labels=None,
        cell_size="sm",
    )
    svg, theme, _size, _canvas = _render(matrix)

    assert ">Fan-out per core<" in svg and ">Loihi: 4096 edges<" in svg
    # Sublabel renders at the tiny size in the faint text colour; the main
    # line keeps the usual small size and light colour.
    tiny, small = theme.size_px("tiny"), theme.size_px("small")
    assert f'font-size="{tiny:g}"' in svg
    assert theme.color_of("faint") in svg
    assert theme.color_of("light") in svg
    assert small != tiny


def test_multiline_row_label_space_counts_widest_line_at_its_own_size():
    theme = Theme()
    grid = [[MatrixCell() for _ in range(2)] for _ in range(2)]
    plain = Matrix(grid, row_labels=["A", "B"], col_labels=None,
                   cell_size="sm")
    sub = Matrix(
        grid,
        row_labels=["A\na very long grounding sublabel", "B"],
        col_labels=None,
        cell_size="sm",
    )
    assert sub._label_space(theme, "row") == pytest.approx(
        theme.text_width("a very long grounding sublabel", "tiny")
        + theme.unit
    )
    assert sub.measure(theme).w > plain.measure(theme).w
