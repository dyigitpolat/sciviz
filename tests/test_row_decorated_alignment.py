from sciviz import Box, Canvas, Region, Row, Theme


def test_start_aligned_decorated_children_stay_inside_row_measurement():
    theme = Theme()
    row = Row(
        Region(Box("A"), label="tall label"),
        Region(Box("B"), label="x"),
        align="start",
    )
    size = row.measure(theme)
    canvas = Canvas()
    row.render(canvas, 0.0, 0.0, theme)

    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= -theme.hairline / 2.0 - 1e-6
    assert y0 >= -1e-6
    assert x1 <= size.w + 1e-6
    assert y1 <= size.h + 1e-6
