"""An authored cell label widens its column instead of shrinking its type."""
from sciviz import DEFAULT_THEME, Matrix, MatrixCell


def test_wide_cell_label_widens_its_column():
    m = Matrix([[MatrixCell(label="1.31"), MatrixCell(label="7")]],
               cell_size="tiny", row_labels=None, col_labels=None)
    w = m._col_widths(DEFAULT_THEME)
    need = len("1.31") * DEFAULT_THEME.size_px("tiny") * 0.62 + 4.0
    assert w[0] >= need
    assert w[1] == m._cell_px(DEFAULT_THEME)        # short label: square cell
