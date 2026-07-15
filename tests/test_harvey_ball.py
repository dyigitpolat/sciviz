"""HarveyBall renders fraction-filled coverage discs within its bbox."""

import pytest

from sciviz import Canvas, HarveyBall, Palette, Theme


def _render(ball):
    theme = Theme()
    size = ball.measure(theme)
    canvas = Canvas()
    ball.render(canvas, 0, 0, theme)
    return size, canvas.to_svg(size.w, size.h)


def test_measure_is_square_for_token_and_pixel_sizes():
    theme = Theme()
    token = HarveyBall(0.5).measure(theme)
    assert token.w == token.h > 0
    fixed = HarveyBall(0.5, size=13.0).measure(theme)
    assert fixed.w == fixed.h == 13.0


def test_hollow_state_renders_ring_only():
    _, svg = _render(HarveyBall(0.0, size=14.0))
    assert svg.count("<circle") == 1
    assert "<path" not in svg
    assert 'fill="none"' in svg


def test_half_renders_small_arc_wedge_plus_ring():
    _, svg = _render(HarveyBall(0.5, size=14.0))
    assert svg.count("<path") == 1
    assert svg.count("<circle") == 1  # the ring
    # fraction <= 0.5 must use the small-arc sweep
    assert " 0 0 1 " in svg


def test_three_quarters_uses_large_arc_flag():
    _, svg = _render(HarveyBall(0.75, size=14.0))
    assert svg.count("<path") == 1
    assert " 0 1 1 " in svg


def test_full_renders_solid_disc_without_degenerate_arc():
    _, svg = _render(HarveyBall(1.0, size=14.0))
    assert "<path" not in svg
    assert svg.count("<circle") == 2  # filled disc + ring


def test_ring_color_can_differ_from_fill():
    theme = Theme()
    ball = HarveyBall(1.0, size=14.0, color=Palette.success, ring=Palette.gray)
    canvas = Canvas()
    ball.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(14, 14)
    fill = theme.color_of(Palette.success)
    ring = theme.color_of(Palette.gray)
    assert fill in svg and ring in svg


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), "high"])
def test_fraction_outside_unit_interval_rejected(bad):
    with pytest.raises(ValueError):
        HarveyBall(bad)


def test_ink_stays_inside_declared_bbox():
    theme = Theme()
    ball = HarveyBall(0.75, size=16.0, stroke_width=1.4)
    canvas = Canvas()
    ball.render(canvas, 0, 0, theme)
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= -1e-6 and y0 >= -1e-6
    assert x1 <= 16.0 + 1e-6 and y1 <= 16.0 + 1e-6
