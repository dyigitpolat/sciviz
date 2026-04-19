"""Tests for Wave 6 upgrades.

Brace.spanning(), Region(label_position=..., annotations=..., corner_badge=...)
and the new semantic positive/negative/warning colour roles.
"""

from __future__ import annotations

import pytest

from sciviz import (
    Box,
    Brace,
    Canvas,
    DEFAULT_THEME,
    Region,
    Row,
    Text,
    Theme,
)


# ---------------------------- Brace.spanning ------------------------------

def test_brace_spanning_uses_element_width():
    box = Box("hello world", width=120)
    b = Brace.spanning(box, label="group")
    bb = b.measure(DEFAULT_THEME)
    assert bb.w == pytest.approx(120.0, abs=1.0)


def test_brace_spanning_tracks_later_width_changes():
    box = Box("x")
    b = Brace.spanning(box)
    w1 = b.measure(DEFAULT_THEME).w
    box.width = 200.0
    w2 = b.measure(DEFAULT_THEME).w
    assert w2 > w1
    assert w2 == pytest.approx(200.0, abs=2.0)


def test_brace_spanning_rejects_non_element():
    with pytest.raises(TypeError):
        Brace.spanning("not an element")


def test_brace_spanning_renders_label():
    b = Brace.spanning(Box("foo", width=60), label="grouped")
    c = Canvas()
    b.render(c, 0, 0, DEFAULT_THEME)
    assert "grouped" in c.to_svg(200, 80)


# --------------------------- Region label_position ------------------------

def test_region_label_position_bottom_places_label_under_border():
    r = Region(Box("x"), label="Bot", label_position="bottom")
    c = Canvas()
    r.render(c, 20, 20, DEFAULT_THEME)
    svg = c.to_svg(200, 200)
    assert "Bot" in svg


def test_region_label_position_left_widens_bbox():
    child = Box("x", width=40)
    plain = Region(child)
    left_lbl = Region(Box("x", width=40), label="Side", label_position="left")
    assert left_lbl.measure(DEFAULT_THEME).w \
        > plain.measure(DEFAULT_THEME).w


def test_region_label_position_right_widens_bbox():
    child = Box("x", width=40)
    plain = Region(child)
    right_lbl = Region(Box("x", width=40), label="Side", label_position="right")
    assert right_lbl.measure(DEFAULT_THEME).w \
        > plain.measure(DEFAULT_THEME).w


def test_region_label_position_unknown_raises():
    with pytest.raises(ValueError):
        Region(Box("x"), label="L", label_position="diagonal")


# ---------------------------- Region annotations --------------------------

def test_region_annotations_top_extend_bbox_height():
    plain = Region(Box("x"))
    ann = Region(Box("x"), annotations=[("top", "O(n)")])
    assert ann.measure(DEFAULT_THEME).h > plain.measure(DEFAULT_THEME).h


def test_region_annotations_render_text():
    r = Region(Box("x"), annotations=[("bottom", "see note"),
                                       ("right", "hot path")])
    c = Canvas()
    r.render(c, 40, 40, DEFAULT_THEME)
    svg = c.to_svg(400, 300)
    assert "see note" in svg
    assert "hot path" in svg


def test_region_rejects_bad_annotation_type():
    with pytest.raises(TypeError):
        Region(Box("x"), annotations=["no tuple"])


def test_region_rejects_bad_annotation_side():
    with pytest.raises(ValueError):
        Region(Box("x"), annotations=[("diag", "no")])


# ----------------------------- Region corner_badge ------------------------

def test_region_corner_badge_rejects_non_element():
    with pytest.raises(TypeError):
        Region(Box("x"), corner_badge="NEW")


def test_region_corner_badge_renders():
    badge = Text("beta")
    r = Region(Box("x"), label="Feature", corner_badge=badge)
    c = Canvas()
    r.render(c, 40, 40, DEFAULT_THEME)
    svg = c.to_svg(300, 200)
    assert "beta" in svg
    assert "Feature" in svg


# --------------------------- Semantic color roles -------------------------

def test_positive_color_maps_to_emerald_family():
    t = DEFAULT_THEME
    assert t.color_of("positive") == t.accent


def test_negative_color_maps_to_highlight_family():
    t = DEFAULT_THEME
    assert t.color_of("negative") == t.highlight


def test_warning_alias_maps_to_amber_role():
    t = DEFAULT_THEME
    assert t.role("warning", "fill") == t._ROLE_PALETTE["warning"]


def test_semantic_role_variants_differ():
    t = DEFAULT_THEME
    soft = t.role("positive", "soft")
    fill = t.role("positive", "fill")
    stroke = t.role("positive", "stroke")
    assert soft != fill != stroke
