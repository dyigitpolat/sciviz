"""Timeline owns paper-scale dimensions and phase guides."""

from sciviz import Canvas, Palette, Theme, Timeline


LANES = [
    ("Compute", [(0, 1, "L1", Palette.blue)]),
    ("Transfer", [(1, 1, "", Palette.cyan)]),
]


def test_timeline_semantic_dimensions_and_auto_label_width():
    theme = Theme()
    timeline = Timeline(
        LANES,
        t_min=0,
        t_max=4,
        width="md",
        lane_h="sm",
        lane_label_width="auto",
        show_axis=False,
    )
    size = timeline.measure(theme)

    assert size.w > theme.text_width("Transfer", "label")
    assert size.h == 2 * theme.unit * 3.0 + theme.unit


def test_timeline_renders_semantic_milestone_guide():
    theme = Theme()
    timeline = Timeline(
        LANES,
        t_min=0,
        t_max=4,
        width="sm",
        lane_h="sm",
        lane_label_width="auto",
        show_axis=False,
        milestones=[(2, None, Palette.red)],
    )
    size = timeline.measure(theme)
    canvas = Canvas()
    timeline.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert 'stroke-dasharray="3,2"' in svg
    assert theme.color_of(Palette.red) in svg
