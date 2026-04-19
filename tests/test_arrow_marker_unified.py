"""Every connector in a diagram should share a single arrowhead size.

Previously, ``Grid.column_flow`` used ``theme.line`` for its stroke while
``Flow`` / ``Bus`` / ``Arrow`` / ``Labeled`` used ``theme.connector``.
``define_arrow_marker`` scaled the head linearly with stroke width, so
the same diagram produced visibly different triangle sizes for the
column-flow arrows vs. Flow arrows.

After the fix: a single ``Theme.arrow_size`` drives every marker and is
independent of stroke width, so all arrowheads render at the same size
across a whole diagram.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Canvas, Grid, Theme)
from sciviz.composition import Flowed, Flow


_MARKER_RX = re.compile(
    r'<marker id="([^"]+)"[^>]+markerWidth="([-\d.]+)"[^>]+markerHeight="([-\d.]+)"'
)


def _marker_sizes(svg: str):
    return [(m.group(1), float(m.group(2)), float(m.group(3)))
            for m in _MARKER_RX.finditer(svg)]


def test_theme_has_arrow_size_field():
    theme = Theme()
    assert hasattr(theme, "arrow_size"), (
        "Theme should expose an arrow_size field driving marker size")
    assert theme.arrow_size > 0


def test_arrow_marker_independent_of_stroke_width():
    """Two markers created with different stroke widths but the same
    theme should have the same dimensions (Theme.arrow_size drives size).
    """
    theme = Theme()
    c = Canvas()
    m1 = c.define_arrow_marker(
        color="#000", stroke_width=theme.line,
        arrow_size=theme.arrow_size)
    m2 = c.define_arrow_marker(
        color="#000", stroke_width=theme.connector,
        arrow_size=theme.arrow_size)
    svg = c.to_svg(10, 10)
    sizes = dict((mid, (w, h)) for mid, w, h in _marker_sizes(svg))
    assert sizes[m1] == sizes[m2], (
        f"markers should be identical when arrow_size is fixed; got {sizes}")


def test_diagram_markers_uniform_across_connector_types():
    """A Grid with column_flow AND an overlaid Flow should emit markers
    of identical markerWidth -- not "some small, some big".
    """
    theme = Theme()
    inner = Grid(
        rows=["top", "bot"],
        columns=[{
            "top": Anchor("a", Box("A", width=60.0, height=22.0)),
            "bot": Anchor("b", Box("B", width=60.0, height=22.0)),
        }],
        column_flow="up",
    )
    outer = Flowed(
        inner,
        flows=[Flow("a", "b", src_side="bottom", dst_side="top",
                     style="orthogonal")],
    )
    size = outer.measure(theme)
    canvas = Canvas()
    outer.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    sizes = _marker_sizes(svg)
    assert len(sizes) >= 2, f"expected multiple markers, got {sizes}"
    widths = {round(w, 2) for _id, w, _h in sizes}
    assert len(widths) == 1, (
        f"expected one unique markerWidth, got {widths} across {sizes}")
