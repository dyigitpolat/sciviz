"""Tests for structured text runs on :class:`sciviz.Text` / :class:`TextBlock`.

The run-list API must coexist with the historic ``Text("...")`` form;
these tests cover both: measurement additivity, SVG run emission, the
:func:`Span` sugar, plain-string parity, and TextBlock line-level mixing.
"""

from __future__ import annotations

import pytest

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


def test_monospace_measurement_uses_export_safe_advance():
    """Code boxes reserve enough width for the concrete export fallback."""
    size = DEFAULT_THEME.size_px("small")
    plain = Text("mmmm", size="small", font="mono")
    runs = Text(["mm", Span("mm", weight="700")],
                size="small", font="mono")
    expected = 4 * size * 0.62
    assert abs(plain.measure(DEFAULT_THEME).w - expected) < 1e-6
    assert abs(runs.measure(DEFAULT_THEME).w - expected) < 1e-6


def test_structured_runs_publish_ink_bounds_for_auto_trim():
    text = Text([Span("Figure ", weight="700"), "caption"])
    canvas = Canvas()
    text.render(canvas, 12, 80, DEFAULT_THEME)
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    measured = text.measure(DEFAULT_THEME)
    assert x0 <= 12 and y0 <= 80
    assert x1 >= 12 + measured.w and y1 >= 80 + measured.h


def test_named_span_publishes_only_its_run_bbox_for_connectors():
    from sciviz.composition._anchor import _anchor_stack

    text = Text(
        ["prefix ", Span("target", weight="700", anchor="operation",
                          anchor_side="top"),
         " suffix"],
        size="small",
        font="mono",
    )
    registry = {}
    token = _anchor_stack.set([registry])
    try:
        text.render(Canvas(), 20.0, 30.0, DEFAULT_THEME)
    finally:
        _anchor_stack.reset(token)

    x, y, w, h = registry["operation"]
    unit = DEFAULT_THEME.size_px("small") * 0.62
    assert x == 20.0 + len("prefix ") * unit
    assert y == 30.0
    assert w == pytest.approx(len("target") * unit)
    assert h == text.measure(DEFAULT_THEME).h
    assert registry["__preferred_side_operation"] == "top"
