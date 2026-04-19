"""Tests for structured text runs on :class:`sciviz.Text` / :class:`TextBlock`.

The run-list API must coexist with the historic ``Text("...")`` form;
these tests cover both: measurement additivity, SVG run emission, the
:func:`Span` sugar, plain-string parity, and TextBlock line-level mixing.
"""

from __future__ import annotations

from sciviz import Canvas, DEFAULT_THEME, Span, Text, TextBlock


def test_span_returns_text_style_tuple():
    assert Span("hi", weight="700") == ("hi", {"weight": "700"})
    assert Span("x") == ("x", {})


def test_plain_text_unchanged_measure():
    t = Text("Principle 1: instruction adherence")
    bbox_runs_single = t.measure(DEFAULT_THEME)
    t2 = Text([("Principle 1: instruction adherence", {})])
    bbox_runs = t2.measure(DEFAULT_THEME)
    assert abs(bbox_runs_single.w - bbox_runs.w) < 1e-6
    assert bbox_runs_single.h == bbox_runs.h


def test_runs_width_is_sum_of_per_run_widths():
    theme = DEFAULT_THEME
    plain_total = theme.text_width("Principle 1: ", "label") \
        + theme.text_width("instruction", "label", bold=True) \
        + theme.text_width(" adherence", "label")
    t = Text([
        "Principle 1: ",
        Span("instruction", weight="700"),
        " adherence",
    ])
    assert abs(t.measure(theme).w - plain_total) < 1.0


def test_runs_emit_tspans_with_style_overrides():
    t = Text([
        "Principle 1: ",
        Span("instruction", weight="700"),
        " adherence ",
        Span("(weight 4)", color="red"),
    ])
    c = Canvas()
    t.render(c, 0.0, 0.0, DEFAULT_THEME)
    svg = c.to_svg(400, 40)
    assert '<text ' in svg
    # A plain segment renders with no tspan tags (direct text).
    assert 'Principle 1: ' in svg
    # The bold run has a font-weight override.
    assert 'font-weight="700"' in svg
    # The red run has a fill override.
    red = DEFAULT_THEME.color_of("red")
    assert f'fill="{red}"' in svg


def test_runs_plain_string_content_is_concatenation():
    t = Text(["a ", Span("b", weight="700"), " c"])
    assert t.content == "a b c"


def test_textblock_mixed_lines():
    tb = TextBlock([
        "Line one",
        [Span("Line two ", weight="700"), "continued"],
        "Line three",
    ])
    bbox = tb.measure(DEFAULT_THEME)
    assert bbox.h > 0 and bbox.w > 0
    c = Canvas()
    tb.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(400, 400)
    assert "Line one" in svg
    assert "Line two " in svg
    assert "continued" in svg
    assert "Line three" in svg
    assert 'font-weight="700"' in svg


def test_textblock_plain_string_parity():
    tb = TextBlock("a\nb\nc")
    assert tb.measure(DEFAULT_THEME).h > 0
    c = Canvas()
    tb.render(c, 0, 0, DEFAULT_THEME)
    svg = c.to_svg(200, 200)
    for line in ("a", "b", "c"):
        assert line in svg


def test_run_with_size_override():
    base = Text("hello", size="small").measure(DEFAULT_THEME)
    mixed = Text([Span("hello", size="title")]).measure(DEFAULT_THEME)
    assert mixed.w > base.w


def test_runs_accept_bad_type_raises():
    import pytest
    with pytest.raises(TypeError):
        Text([42])
