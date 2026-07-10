"""Tests for Wave 6 upgrades.

Brace.spanning(), Region(label_position=..., annotations=..., corner_badge=...)
and the new semantic positive/negative/warning colour roles.
"""

from __future__ import annotations

import re

import pytest

from sciviz import (
    Box,
    Badge,
    Brace,
    Canvas,
    Captioned,
    DEFAULT_THEME,
    Region,
    Row,
    Text,
    Theme,
)
from sciviz import Math


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


def test_vertical_brace_spanning_uses_element_height_and_multiline_label():
    box = Box("stack", width=80, height=120)
    brace = Brace.spanning(
        box, label="reuse\nindices", direction="right", color="positive"
    )
    measured = brace.measure(DEFAULT_THEME)
    assert measured.h == pytest.approx(box.measure(DEFAULT_THEME).h, abs=1.0)
    canvas = Canvas()
    brace.render(canvas, 0, 0, DEFAULT_THEME)
    svg = canvas.to_svg(200, 160)
    assert "reuse" in svg and "indices" in svg


def test_brace_rejects_unknown_direction():
    with pytest.raises(ValueError):
        Brace(40, direction="diagonal")


def test_badge_accepts_math_element_and_semantic_size():
    badge = Badge(Math(r"O_{t+1}"), size="lg", bordered=True)
    measured = badge.measure(DEFAULT_THEME)
    assert measured.w == measured.h
    assert measured.w >= DEFAULT_THEME.unit * 5.2
    canvas = Canvas()
    badge.render(canvas, 0, 0, DEFAULT_THEME)
    svg = canvas.to_svg(100, 100)
    assert "sciviz-math" in svg and "<circle" in svg


def test_box_semantic_aspect_controls_silhouette_without_pixels():
    portrait = Box("IDM", aspect="portrait").measure(DEFAULT_THEME)
    landscape = Box("decoder", aspect="landscape").measure(DEFAULT_THEME)
    square = Box("x", aspect="square").measure(DEFAULT_THEME)
    assert portrait.h > portrait.w
    assert portrait.h / portrait.w >= 1.5
    assert landscape.w > landscape.h
    assert landscape.w / landscape.h >= 2.4
    assert square.w == square.h


def test_box_semantic_size_scales_both_dimensions():
    small = Box("node", size="sm").measure(DEFAULT_THEME)
    large = Box("node", size="2xl").measure(DEFAULT_THEME)
    assert large.w > small.w and large.h > small.h


def test_large_landscape_size_spends_growth_on_line_length():
    box = Box("formula stage", size="xl", aspect="landscape")
    measured = box.measure(DEFAULT_THEME)
    assert measured.w / measured.h >= 3.2


def test_box_rejects_unknown_aspect():
    with pytest.raises(ValueError):
        Box("x", aspect="banana")


def test_box_rejects_unknown_semantic_size():
    with pytest.raises(ValueError):
        Box("x", size="huge")


def test_box_pill_radius_tracks_box_height():
    box = Box("bus", aspect="landscape", radius="pill")
    canvas = Canvas()
    size = box.measure(DEFAULT_THEME)
    box.render(canvas, 0, 0, DEFAULT_THEME)
    svg = canvas.to_svg(200, 100)
    assert f'rx="{size.h / 2:g}"' in svg


def test_box_rejects_unknown_semantic_radius():
    with pytest.raises(ValueError):
        Box("x", radius="roundish")


def test_captioned_right_accessory_reports_child_alignment_axis():
    child = Box("carrier", aspect="landscape")
    accessory = Badge(Math(r"O_{t+1}"), size="lg", bordered=True)
    decorated = Captioned(
        child,
        decoration=accessory,
        placement="right",
        gap=0,
        align_on="child",
    )
    assert decorated.measure(DEFAULT_THEME).w > child.measure(DEFAULT_THEME).w
    decorated_content = decorated.content_bbox(DEFAULT_THEME)
    child_content = child.content_bbox(DEFAULT_THEME)
    assert decorated_content[0] == child_content[0]
    assert decorated_content[2] == child_content[2]


def test_captioned_rejects_conflicting_decorations():
    with pytest.raises(ValueError):
        Captioned(Box("x"), decoration=Badge("1"), number="2")


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


def test_region_corner_badge_is_reserved_above_child_content():
    badge = Box("1", width=14, height=14, fill="negative")
    region = Region(Box("PE"), corner_badge=badge)
    size = region.measure(DEFAULT_THEME)
    canvas = Canvas()
    region.render(canvas, 0, 0, DEFAULT_THEME)
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    tolerance = DEFAULT_THEME.hairline
    assert x0 >= -tolerance and y0 >= -tolerance
    assert x1 <= size.w + tolerance and y1 <= size.h + tolerance

    rects = [
        tuple(float(value) for value in match)
        for match in re.findall(
            r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"',
            canvas.to_svg(size.w, size.h),
        )
    ]
    _border, badge_rect, child = rects[:3]
    assert badge_rect[1] + badge_rect[3] <= child[1]


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
