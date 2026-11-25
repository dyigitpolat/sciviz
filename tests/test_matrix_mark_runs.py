"""Several marks in one cell are set side by side; the column carries them."""
import pytest

from sciviz import DEFAULT_THEME, Diagram, Marker, Matrix, MatrixCell


def _run():
    return [Marker("circle", size="md"), Marker("square", size="md"),
            Marker("diamond", size="md")]


def test_mark_run_widens_only_its_column():
    m = Matrix([[MatrixCell(mark=_run()), MatrixCell(mark="x")]],
               cell_size="tiny", row_labels=None, col_labels=None)
    w = m._col_widths(DEFAULT_THEME)
    assert w[0] >= m._mark_run_width(m.data[0][0].mark, DEFAULT_THEME)
    assert w[1] == m._cell_px(DEFAULT_THEME)


def test_mark_run_renders_every_mark():
    svg = Diagram.for_paper(Matrix([[MatrixCell(mark=_run())]],
                                   row_labels=None, col_labels=None)).render()
    assert svg.count("<circle") >= 1 and svg.count("<rect") >= 2


def test_mark_run_members_are_checked():
    with pytest.raises(TypeError):
        MatrixCell(mark=[1, 2])
