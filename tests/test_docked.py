from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Canvas, Docked, Text, Theme
from sciviz.composition import _anchor_stack


def test_corner_decorations_straddle_body_while_content_alignment_uses_body():
    theme = Theme()
    top = Anchor("top", Box("C", width=20, height=20))
    bottom = Anchor("bottom", Box("B", width=20, height=20))
    docked = Docked(
        Box("PE", width=50, height=40),
        top_right=top,
        bottom_right=bottom,
    )

    assert docked.measure(theme) == Box("", width=60, height=60).measure(theme)
    assert docked.content_bbox(theme) == (0.0, 10.0, 50.0, 40.0)

    registry = {}
    token = _anchor_stack.set([registry])
    try:
        docked.render(Canvas(), 0.0, 0.0, theme)
    finally:
        _anchor_stack.reset(token)
    assert registry["top"] == (40.0, 0.0, 20.0, 20.0)
    assert registry["bottom"] == (40.0, 40.0, 20.0, 20.0)


def test_center_decoration_overlays_without_changing_primary_content():
    theme = Theme()
    body = Box("", width=80, height=24, fill="none", stroke="none")
    docked = Docked(body, center=Text("×", size="title"))
    assert docked.content_bbox(theme) == (0.0, 0.0, 80.0, 24.0)


def test_center_band_can_fit_width_and_use_lower_third():
    theme = Theme()
    body = Box("modules", width=120, height=90, shape_key="")
    band = Anchor(
        "band",
        Box("Cross-attention", width=30, height=18, shape_key=""),
    )
    docked = Docked(
        body,
        center=band,
        center_fit="width",
        center_position="lower",
    )

    registry = {}
    token = _anchor_stack.set([registry])
    try:
        docked.render(Canvas(), 0.0, 0.0, theme)
    finally:
        _anchor_stack.reset(token)

    assert registry["band"][2] == pytest.approx(120.0)
    assert registry["band"][1] + registry["band"][3] / 2 == pytest.approx(60.0)
    assert docked.content_bbox(theme) == (0.0, 0.0, 120.0, 90.0)


def test_center_fit_options_require_a_center_decoration():
    with pytest.raises(ValueError, match="require a center decoration"):
        Docked(Box("body"), center_fit="width")


def test_center_overlay_rejects_unknown_fit_and_position():
    with pytest.raises(ValueError, match="center_fit"):
        Docked(Box("body"), center=Box("band"), center_fit="diagonal")
    with pytest.raises(ValueError, match="center_position"):
        Docked(Box("body"), center=Box("band"), center_position="baseline")
