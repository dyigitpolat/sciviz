from sciviz import (
    Anchor, Box, Canvas, Column, Matrix, MatrixCell, MatrixSelection, Text,
    Theme,
)
from sciviz.composition._anchor import _anchor_stack


def _registry_after(element):
    registry = {}
    token = _anchor_stack.set([registry])
    try:
        element.render(Canvas(), 0.0, 0.0, Theme())
    finally:
        _anchor_stack.reset(token)
    return registry


def test_element_label_box_is_region_not_opaque_obstacle():
    box = Box(Column(Anchor("inside", Text("target"))))
    registry = _registry_after(box)

    assert "inside" in registry
    assert any(name.startswith("__region_") for name in registry)
    assert not any(name.startswith("_auto_obstacle_") for name in registry)


def test_matrix_with_named_selection_is_owning_region():
    matrix = Matrix(
        [[MatrixCell(), MatrixCell()]],
        row_labels=None,
        col_labels=None,
        selections=[MatrixSelection(0, 0, name="selected")],
    )
    registry = _registry_after(matrix)

    assert "selected" in registry
    assert any(name.startswith("__region_") for name in registry)
    assert not any(name.startswith("_auto_obstacle_") for name in registry)
