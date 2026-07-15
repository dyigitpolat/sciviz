"""Scatter multi-line point labels and in-plot annotations.

Multi-line labels: a point label may contain newlines; the first line
renders in the text colour, continuation lines render muted, and the
whole block participates in collision-aware placement.

Annotations: Scatter accepts the same :class:`Annotate` items as
LineChart (one chart family), including ``dot`` and ``anchor``.
"""
from __future__ import annotations

import re

from sciviz import Annotate, Canvas, LineChart, Scatter, Series, Theme


def _render(element) -> str:
    theme = Theme()
    size = element.measure(theme)
    canvas = Canvas()
    element.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def _texts(svg: str):
    """Return list of (attrs, content) for every <text> element."""
    out = []
    for m in re.finditer(r"<text ([^>]*)>(.*?)</text>", svg):
        out.append((m.group(1), m.group(2)))
    return out


def _text_attr(attrs: str, name: str):
    m = re.search(rf'{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def _find(svg: str, content: str):
    hits = [(a, c) for a, c in _texts(svg) if content in c]
    assert hits, f"no <text> containing {content!r} in SVG"
    return hits[0]


# ---- multi-line point labels ------------------------------------------------

def test_multiline_label_renders_every_line():
    svg = _render(Scatter([(0.5, 0.5, "Alpha\nBeta detail")]))
    _find(svg, "Alpha")
    _find(svg, "Beta detail")


def test_multiline_continuation_line_is_muted():
    theme = Theme()
    svg = _render(Scatter([(0.5, 0.5, "Alpha\nBeta detail")]))
    first_attrs, _ = _find(svg, "Alpha")
    detail_attrs, _ = _find(svg, "Beta detail")
    assert _text_attr(first_attrs, "fill") == theme.color_of("text")
    assert _text_attr(detail_attrs, "fill") == theme.color_of("muted")


def test_multiline_label_lines_stack_downward_share_anchor():
    svg = _render(Scatter([(0.5, 0.5, "Alpha\nBeta detail")]))
    first_attrs, _ = _find(svg, "Alpha")
    detail_attrs, _ = _find(svg, "Beta detail")
    assert float(_text_attr(detail_attrs, "y")) > float(_text_attr(first_attrs, "y"))
    assert _text_attr(first_attrs, "x") == _text_attr(detail_attrs, "x")
    assert (_text_attr(first_attrs, "text-anchor")
            == _text_attr(detail_attrs, "text-anchor"))


def test_north_hinted_multiline_block_sits_fully_above_marker():
    # With hint "n" the whole block (both lines) must clear the marker top;
    # single-line placement math would leave the first line overlapping it.
    r = 4.0
    sc = Scatter([(0.5, 0.5, "Alpha\nBeta detail", "primary_fill", r, "n")])
    svg = _render(sc)
    circle = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4', svg)
    assert circle, "marker circle not found"
    marker_top = float(circle.group(2)) - r
    for content in ("Alpha", "Beta detail"):
        attrs, _ = _find(svg, content)
        assert float(_text_attr(attrs, "y")) < marker_top


def test_singleline_label_still_renders_in_text_colour():
    theme = Theme()
    svg = _render(Scatter([(0.5, 0.5, "Solo")]))
    attrs, _ = _find(svg, "Solo")
    assert _text_attr(attrs, "fill") == theme.color_of("text")


# ---- annotations (Annotate family, shared with LineChart) -------------------

def test_scatter_annotation_renders_multiline_text_with_anchor():
    ann = Annotate(0.5, 0.5, "note one\nnote two", dx=0, dy=0,
                   anchor="middle", dot=False)
    svg = _render(Scatter([(0.2, 0.2)], annotations=[ann]))
    for content in ("note one", "note two"):
        attrs, _ = _find(svg, content)
        assert _text_attr(attrs, "text-anchor") == "middle"


def test_scatter_annotation_dot_flag_controls_anchor_dot():
    plain = _render(Scatter([(0.2, 0.2)]))
    without = _render(Scatter(
        [(0.2, 0.2)],
        annotations=[Annotate(0.5, 0.5, "n", dot=False)]))
    with_dot = _render(Scatter(
        [(0.2, 0.2)],
        annotations=[Annotate(0.5, 0.5, "n", dot=True)]))
    n_plain = plain.count("<circle")
    assert without.count("<circle") == n_plain
    assert with_dot.count("<circle") == n_plain + 1


def test_linechart_annotation_multiline_and_anchor_parity():
    ann = Annotate(0.5, 0.5, "line one\nline two", anchor="end", dot=False)
    chart = LineChart([Series([(0.0, 0.0), (1.0, 1.0)], label="s")],
                      annotations=[ann])
    svg = _render(chart)
    for content in ("line one", "line two"):
        attrs, _ = _find(svg, content)
        assert _text_attr(attrs, "text-anchor") == "end"
