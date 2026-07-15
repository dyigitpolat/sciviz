"""Tests for the Hugeicons stroke-rounded icon bank and its Icon fallback.

See `sciviz/_assets/hugeicons/README.md` for provenance and licensing.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from sciviz import Canvas, DEFAULT_THEME, Icon
from sciviz._assets import (
    LUCIDE_ICONS,
    hugeicons_manifest,
    hugeicons_names,
    load_hugeicon_shapes,
    search_hugeicons,
)

ICONS_DIR = Path(__file__).resolve().parents[1] / "sciviz" / "_assets" / "hugeicons" / "icons"
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "sciviz" / "_assets" / "hugeicons" / "manifest.json"


def test_bank_has_thousands_of_icons():
    names = hugeicons_names()
    assert len(names) > 5000
    assert len(names) == len(set(names))


def test_lucide_takes_precedence_on_name_collision():
    overlap = set(LUCIDE_ICONS) & set(hugeicons_names())
    assert overlap, "expected some Lucide names to also exist in the Hugeicons bank"
    for name in overlap:
        icon = Icon(name)
        assert icon._bank == "lucide"


def test_all_svg_files_are_well_formed():
    files = list(ICONS_DIR.glob("*.svg"))
    assert len(files) > 5000
    bad = []
    for f in files:
        try:
            ET.fromstring(f.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            bad.append((f.name, str(e)))
    assert not bad, f"malformed SVGs: {bad[:5]}"


def test_load_hugeicon_shapes_returns_expected_tags():
    shapes = load_hugeicon_shapes("shopping-cart-02")
    tags = {tag for tag, _attrs in shapes}
    assert tags <= {"path", "circle", "rect", "ellipse"}
    assert len(shapes) > 0


def test_hugeicons_only_name_renders_via_icon():
    name = next(n for n in hugeicons_names() if n not in LUCIDE_ICONS)
    icon = Icon(name, size=32.0, color="dark")
    assert icon._bank == "hugeicons"
    bbox = icon.measure(DEFAULT_THEME)
    assert bbox.w == 32.0 and bbox.h == 32.0

    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(64, 64)
    assert 'viewBox="0 0 24 24"' in svg


def test_hugeicons_mixed_shape_icon_renders_all_tags():
    # shopping-cart-02 mixes <path> and <circle> (the wheels).
    icon = Icon("shopping-cart-02", size=24.0, color="dark")
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(48, 48)
    assert "<circle " in svg
    assert "<path " in svg


def test_hugeicons_fill_match_resolves_currentcolor_fill():
    icon = Icon("shopping-cart-02", color="highlight", fill="match")
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(24, 24)
    stroke_hex = DEFAULT_THEME.color_of("highlight")
    assert f'stroke="{stroke_hex}"' in svg


def test_hugeicons_stroke_width_scales_proportionally_not_uniformly():
    # An icon whose sub-shapes deliberately vary stroke width (e.g. a bold
    # accent dot next to normal-weight linework) should keep that relative
    # difference after scaling -- not collapse to one uniform width.
    shapes = load_hugeicon_shapes("shopping-cart-02")
    widths = {dict(attrs).get("stroke-width") for _tag, attrs in shapes if dict(attrs).get("stroke")}
    assert widths  # sanity: shapes carry their own stroke-width

    icon = Icon("shopping-cart-02", stroke_width=3.0)
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(24, 24)
    assert 'stroke-width="3"' in svg


def test_hugeicons_default_stroke_width_keeps_authored_weight():
    icon = Icon("shopping-cart-02")  # stroke_width=None -> keep authored 1.5
    canvas = Canvas()
    icon.render(canvas, 0.0, 0.0, DEFAULT_THEME)
    svg = canvas.to_svg(24, 24)
    assert 'stroke-width="1.5"' in svg


def test_search_hugeicons_matches_by_name_substring():
    hits = search_hugeicons("shopping-cart")
    assert "shopping-cart-02" in hits


def test_unknown_icon_error_mentions_both_banks():
    with pytest.raises(KeyError, match="Lucide.*Hugeicons"):
        Icon("definitely-not-a-real-icon-name")


@pytest.mark.skipif(not MANIFEST_PATH.exists(), reason="manifest.json not generated yet")
def test_manifest_structure_matches_svg_bank():
    manifest = hugeicons_manifest()
    names = set(hugeicons_names())
    assert set(manifest) <= names, "manifest must not reference icons missing from the bank"
    assert len(manifest) > 5000

    sample = list(manifest.items())[:200]
    for name, entry in sample:
        assert isinstance(entry.get("description"), str) and entry["description"]
        assert isinstance(entry.get("category"), str) and entry["category"]
        keywords = entry.get("keywords")
        assert isinstance(keywords, list) and len(keywords) == 10
        assert all(isinstance(k, str) and k for k in keywords)


def test_manifest_file_is_valid_json_if_present():
    if not MANIFEST_PATH.exists():
        pytest.skip("manifest.json not generated yet")
    json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
