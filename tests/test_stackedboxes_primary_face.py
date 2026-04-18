"""StackedBoxes should expose its FRONT (labeled) box as the primary anchor.

A StackedBoxes measures as a silhouette of ``(width + total, height + total)``
where ``total = (n-1) * offset``.  The front box -- the one that carries the
label and acts as the visible "face" of the stack -- sits at ``(0, total)``
in the element's local frame.

When used inside a Grid column alongside plain Box cells, the column axis
must align with the FACE, not with the centre of the outer silhouette.
Otherwise every plain box in the column is drawn ~total/2 px to the right
of the stack's visible face, making the column look wobbly.
"""
from __future__ import annotations

from sciviz import StackedBoxes, Theme


def test_stackedboxes_primary_anchor_is_front_face():
    theme = Theme()
    s = StackedBoxes(4, "Layer", fill="accent_proc",
                     width=120.0, height=30.0, offset=4.0)
    total = (4 - 1) * 4.0
    pa = s.primary_anchor_bbox(theme)
    assert pa is not None, "StackedBoxes must expose a primary anchor"
    x, y, w, h = pa
    assert (x, y, w, h) == (0.0, total, 120.0, 30.0), (
        f"primary_anchor_bbox {pa} should be the front face "
        f"(0, {total}, 120, 30)")


def test_stackedboxes_content_bbox_is_front_face():
    """content_bbox is used for Row/Column content-axis alignment.  The
    face of the stack (not the silhouette) should drive that alignment.
    """
    theme = Theme()
    s = StackedBoxes(4, "Layer", fill="accent_proc",
                     width=120.0, height=30.0, offset=4.0)
    total = (4 - 1) * 4.0
    cb = s.content_bbox(theme)
    x, y, w, h = cb
    assert (x, y, w, h) == (0.0, total, 120.0, 30.0), (
        f"content_bbox {cb} should be the front face")


def test_stackedboxes_face_is_horizontally_centered_on_axis_in_grid():
    """When a StackedBoxes shares a column with a plain Box, the Box's x
    centre must equal the StackedBoxes FRONT-FACE x centre (not the
    silhouette centre).
    """
    import re
    from sciviz import Box, Canvas, Grid

    theme = Theme()
    stack = StackedBoxes(4, "Layer", fill="accent_proc",
                         width=120.0, height=30.0, offset=4.0)
    box = Box("Top", width=80.0, height=22.0)
    g = Grid(
        rows=["top", "bot"],
        columns=[{"top": box, "bot": stack}],
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    rects = re.findall(
        r'<rect x="([-\d.]+)" y="([-\d.]+)" '
        r'width="([-\d.]+)" height="([-\d.]+)"[^/]*/>',
        svg)
    assert rects, svg
    total = (4 - 1) * 4.0
    # Stack draws n boxes.  The FRONT box is rendered at the *largest* y
    # (it sits below the back boxes) with width=120 height=30.
    stack_fronts = [(float(x), float(y), float(w), float(h))
                    for x, y, w, h in rects
                    if abs(float(w) - 120.0) < 0.5
                       and abs(float(h) - 30.0) < 0.5]
    assert stack_fronts, f"expected a 120x30 front rect, got rects={rects}"
    front = max(stack_fronts, key=lambda r: r[1])  # largest y
    fx_center = front[0] + front[2] / 2

    top_rects = [(float(x), float(y), float(w), float(h))
                 for x, y, w, h in rects
                 if abs(float(w) - 80.0) < 0.5
                    and abs(float(h) - 22.0) < 0.5]
    assert top_rects, f"expected top box 80x22 rect, got rects={rects}"
    top_cx = top_rects[0][0] + top_rects[0][2] / 2
    assert abs(fx_center - top_cx) < 0.6, (
        f"Stack face centre {fx_center} should align with top-box centre "
        f"{top_cx} (delta {fx_center - top_cx})")
