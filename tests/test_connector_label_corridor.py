from __future__ import annotations

from sciviz import Canvas, Theme
from sciviz.composition import Flow


def _overlaps(a, b):
    ax0, ay0, ax1, ay1 = a
    bx, by, bw, bh = b
    return min(ax1, bx + bw) > max(ax0, bx) \
        and min(ay1, by + bh) > max(ay0, by)


def test_straight_flow_label_avoids_both_endpoint_nodes_and_uses_label_color():
    registry = {
        "source": (0.0, 70.0, 70.0, 35.0),
        "sink": (80.0, 0.0, 110.0, 40.0),
    }
    canvas = Canvas()
    flow = Flow(
        "source",
        "sink",
        src_side="top",
        dst_side="bottom",
        label="interpolate/predict",
        color="#111111",
        label_color="#123456",
        style="straight",
    )
    flow._render(canvas, Theme(), registry)

    label_rect = registry["__label_obstacles__"][0]
    assert not _overlaps(label_rect, registry["source"])
    assert not _overlaps(label_rect, registry["sink"])
    assert "#123456" in canvas.to_svg(220, 130)
