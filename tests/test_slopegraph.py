"""Genericity tests for :class:`Slopegraph`.

The chart was motivated by a claimed-vs-deployed accuracy figure but
must serve any "one measurement, two conditions" comparison without
special-casing.  These tests pin that the chart accepts tuple / dict /
dataclass records, validates its knobs, resolves value ranges, dodges
colliding endpoint labels, deduplicates coincident labels, and renders
per-record styles plus reference levels on any theme.
"""
from __future__ import annotations

import re

import pytest

from sciviz import (
    Canvas, Diagram, SlopeRecord, SlopeReference, Slopegraph, Theme,
)


def _render(chart: Slopegraph, theme: Theme | None = None) -> str:
    theme = theme or Theme()
    d = Diagram(body=chart)
    size = d.measure()
    canvas = Canvas()
    chart.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def _text_ys(svg: str, text: str) -> list[float]:
    return [float(m.group(1)) for m in
            re.finditer(rf'<text[^>]*y="(-?[0-9.]+)"[^>]*>{re.escape(text)}<', svg)]


# ---- shape coercion ---------------------------------------------------------

def test_accepts_tuples_dicts_and_dataclasses():
    chart = Slopegraph([
        ("A", 1.0, 2.0),
        ("B", 3.0, 4.0, "(+1.0)"),
        {"label": "C", "left": 5.0, "right": 6.0},
        SlopeRecord("D", 7.0, 8.0, color="teal"),
    ])
    assert [r.label for r in chart.records] == ["A", "B", "C", "D"]
    assert chart.records[1].annotation == "(+1.0)"
    assert chart.records[3].color == "teal"


def test_rejects_bad_tuple_arity_and_empty():
    with pytest.raises(ValueError):
        Slopegraph([("A", 1.0)])
    with pytest.raises(ValueError):
        Slopegraph([])


def test_rejects_unknown_knobs():
    with pytest.raises(ValueError):
        Slopegraph([("A", 1, 2)], size="enormous")
    with pytest.raises(ValueError):
        Slopegraph([("A", 1, 2)], name_side="top")
    with pytest.raises(ValueError):
        Slopegraph([SlopeRecord("A", 1, 2, marker="star")])
    with pytest.raises(ValueError):
        Slopegraph([("A", 1, 2)],
                    references=[SlopeReference(1.5, label_side="above")])


# ---- scale -------------------------------------------------------------------

def test_auto_range_covers_data_and_references():
    chart = Slopegraph([("A", 10.0, 20.0)],
                       references=[SlopeReference(25.0)])
    lo, hi = chart._resolved_range()
    assert lo < 10.0 and hi > 25.0


def test_explicit_range_respected_and_validated():
    chart = Slopegraph([("A", 10.0, 20.0)], value_range=(0.0, 50.0))
    assert chart._resolved_range() == (0.0, 50.0)
    with pytest.raises(ValueError):
        Slopegraph([("A", 1, 2)], value_range=(5.0, 5.0))._resolved_range()


def test_value_format_spec_and_callable():
    spec = Slopegraph([("A", 1.234, 2.0)], value_format=".1f")
    assert spec._fmt(1.234) == "1.2"
    called = Slopegraph([("A", 1.0, 2.0)],
                        value_format=lambda v: f"{v:.2f}%")
    assert called._fmt(1.0) == "1.00%"


# ---- semantic sizes -----------------------------------------------------------

def test_semantic_plot_sizes_scale_both_axes():
    small = Slopegraph([("A", 1, 2)], size="sm")
    large = Slopegraph([("A", 1, 2)], size="xl")
    assert large.slope_width > small.slope_width
    assert large.height > small.height


# ---- rendering ---------------------------------------------------------------

def test_per_record_dash_and_solid_coexist():
    chart = Slopegraph([
        SlopeRecord("sim", 90.0, 80.0, dash="4,3"),
        SlopeRecord("silicon", 85.0, 84.0),
    ], name_side="left")
    svg = _render(chart)
    assert 'stroke-dasharray="4,3"' in svg
    # The solid record's slope line carries no dasharray: count dashed lines.
    dashed = svg.count('stroke-dasharray="4,3"')
    assert dashed == 1


def test_reference_level_renders_line_and_label():
    chart = Slopegraph(
        [("A", 7.0, 9.5)],
        references=[SlopeReference(8.4, label="equivalence bound")],
    )
    svg = _render(chart)
    assert "equivalence bound" in svg
    assert 'stroke-dasharray="2,3"' in svg


def test_center_reference_label_drops_below_when_a_slope_sits_above():
    """A centered caption sits above the level line unless a slope line
    occupies that band, in which case it moves just below the line."""
    # A flat record hovers right above the reference level mid-span.
    crossed = Slopegraph(
        [("A", 3.2, 3.2)],
        references=[SlopeReference(3.0, label="bound", label_side="center")],
        name_side="none", show_values=False,
        value_range=(0.0, 4.0),
    )
    svg = _render(crossed)
    ref_line = re.search(
        r'<line[^>]*y1="(-?[0-9.]+)"[^>]*stroke-dasharray="2,3"', svg)
    label_y = _text_ys(svg, "bound")
    assert ref_line and label_y
    assert label_y[0] > float(ref_line.group(1))   # below the line
    # With no records near the level, the label stays above the line.
    clear = Slopegraph(
        [("A", 1.0, 1.2)],
        references=[SlopeReference(3.0, label="bound", label_side="center")],
        name_side="none", show_values=False,
        value_range=(0.0, 4.0),
    )
    svg = _render(clear)
    ref_line = re.search(
        r'<line[^>]*y1="(-?[0-9.]+)"[^>]*stroke-dasharray="2,3"', svg)
    label_y = _text_ys(svg, "bound")
    assert label_y[0] < float(ref_line.group(1))   # above the line


def test_margin_reference_label_lives_beside_the_rail():
    """label_side='right' captions render in the right label margin
    (past the right rail), participating in the endpoint-label dodge,
    and widen the measured bbox accordingly."""
    theme = Theme()
    chart = Slopegraph(
        [("A", 7.45, 9.48)],
        references=[SlopeReference(8.38, label="equivalence bound",
                                   label_side="right")],
        name_side="none", show_values=False,
        slope_width=150.0,
    )
    svg = _render(chart, theme)
    m = re.search(r'<text[^>]*x="(-?[0-9.]+)"[^>]*>equivalence bound<', svg)
    assert m and float(m.group(1)) >= 150.0        # beyond the right rail
    bare = Slopegraph([("A", 7.45, 9.48)], name_side="none",
                      show_values=False, slope_width=150.0)
    assert chart.measure(theme).w > bare.measure(theme).w


def test_rail_titles_rendered_only_when_given():
    titled = _render(Slopegraph([("A", 1, 2)],
                                left_title="before", right_title="after"))
    assert "before" in titled and "after" in titled
    untitled = _render(Slopegraph([("A", 1, 2)]))
    assert "before" not in untitled


def test_rail_titles_never_overprint_on_narrow_slopes():
    """Long titles over a narrow slope area separate instead of
    overlapping, and stay inside the measured bbox."""
    theme = Theme()
    chart = Slopegraph(
        [("A", 1.0, 2.0)],
        left_title="pre-deployment (software)",
        right_title="deployed on hardware",
        slope_width=60.0, name_side="none", show_values=False,
    )
    lay = chart._layout(theme)
    lt = theme.text_width("pre-deployment (software)", "label", bold=True)
    rt = theme.text_width("deployed on hardware", "label", bold=True)
    assert lay["title_lx"] + lt / 2 <= lay["title_rx"] - rt / 2
    assert lay["title_lx"] - lt / 2 >= -0.5
    assert lay["title_rx"] + rt / 2 <= lay["w"] + 0.5


def test_colliding_endpoint_labels_are_dodged():
    """Two records whose right values nearly coincide must not overprint."""
    theme = Theme()
    chart = Slopegraph([
        ("first record", 50.0, 70.05),
        ("second record", 30.0, 70.00),
    ], value_format=".2f", name_side="left")
    svg = _render(chart, theme)
    ys = sorted(_text_ys(svg, "70.05") + _text_ys(svg, "70.00"))
    assert len(ys) == 2
    assert ys[1] - ys[0] >= theme.text_height("small")


def test_coincident_identical_labels_deduplicate():
    """Records sharing one side's value and text draw that label once."""
    chart = Slopegraph([
        ("day-0", 7.45, 9.48),
        ("one week later", 7.45, 9.89),
    ], name_side="right", value_format=".2f")
    svg = _render(chart)
    assert svg.count(">7.45<") == 1
    assert svg.count(">9.48<") == 1 and svg.count(">9.89<") == 1


def test_annotation_appended_on_right_in_its_own_color():
    chart = Slopegraph(
        [SlopeRecord("A", 94.1, 85.1, annotation="(-9.0 pt)",
                     annotation_color="#b91c1c")],
    )
    svg = _render(chart)
    match = re.search(r'<text[^>]*fill="#b91c1c"[^>]*>\(-9.0 pt\)<', svg)
    assert match, svg


def test_name_side_none_hides_names():
    svg = _render(Slopegraph([("secret", 1.0, 2.0)], name_side="none"))
    assert "secret" not in svg


def test_labels_stay_inside_measured_bbox():
    """Bbox contract: endpoint labels and titles fit inside measure()."""
    theme = Theme()
    chart = Slopegraph(
        [("a very long record name indeed", 10.0, 90.0, "(+80.0)")],
        left_title="pre-deployment (software)",
        right_title="deployed",
    )
    bbox = chart.measure(theme)
    svg = _render(chart, theme)
    for m in re.finditer(r'<text[^>]*x="(-?[0-9.]+)"[^>]*y="(-?[0-9.]+)"', svg):
        x, y = float(m.group(1)), float(m.group(2))
        assert -0.5 <= x <= bbox.w + 0.5
        assert -0.5 <= y <= bbox.h + 0.5


# ---- theme integration ---------------------------------------------------------

def test_theme_tokens_resolve_on_default_and_slides_theme():
    chart = Slopegraph(
        [SlopeRecord("A", 1.0, 2.0, color="primary"),
         SlopeRecord("B", 2.0, 1.0, color="highlight", dash="4,3",
                     marker="diamond")],
        left_title="before", right_title="after",
        references=[SlopeReference(1.5, label="bound")],
    )
    for theme in (Theme(), Theme.slides()):
        canvas = Canvas()
        bbox = chart.measure(theme)
        chart.render(canvas, 0.0, 0.0, theme)
        assert bbox.w > 0 and bbox.h > 0
