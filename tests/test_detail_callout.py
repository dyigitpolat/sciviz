"""Focused tests for the semantic overview-to-detail composition."""

from __future__ import annotations

import pytest

from sciviz import Anchor, Box, Canvas, Column, Region, Row, Theme
from sciviz.composition._detail_callout import DetailCallout


def _assert_ink_inside(element, theme: Theme | None = None) -> str:
    theme = theme or Theme()
    size = element.measure(theme)
    canvas = Canvas()
    element.render(canvas, 0.0, 0.0, theme)
    assert canvas.ink_bbox is not None
    x0, y0, x1, y1 = canvas.ink_bbox
    assert x0 >= -1e-6
    assert y0 >= -1e-6
    assert x1 <= size.w + 1e-6
    assert y1 <= size.h + 1e-6
    return "".join(canvas._body)


def test_unknown_source_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="not an Anchor"):
        DetailCallout(Box("overview"), Box("detail"), source="sm0")


def test_duplicate_source_is_rejected_as_ambiguous() -> None:
    overview = Row(
        Anchor("selected", Box("one")),
        Anchor("selected", Box("two")),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        DetailCallout(overview, Box("detail"), source="selected")


def test_unknown_target_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="target .* is not an Anchor"):
        DetailCallout(
            Anchor("selected", Box("overview")),
            Box("detail"),
            source="selected",
            target="detail-root",
        )


def test_composite_detail_can_target_one_nested_panel() -> None:
    detail = Column(
        Anchor("detail-root", Region(Box("row"), label="Row detail")),
        Region(Box("pe"), label="PE detail"),
    )
    callout = DetailCallout(
        Anchor("selected", Box("overview")),
        detail,
        source="selected",
        target="detail-root",
        placement="right",
    )

    svg_body = _assert_ink_inside(callout)
    assert svg_body.count("stroke-dasharray") >= 2


@pytest.mark.parametrize("placement", ["left", "top", "diagonal"])
def test_invalid_placement_fails(placement: str) -> None:
    with pytest.raises(ValueError, match="placement"):
        DetailCallout(
            Anchor("selected", Box("overview")),
            Box("detail"),
            source="selected",
            placement=placement,  # type: ignore[arg-type]
        )


def test_nested_anchor_is_discovered_and_leader_is_headless() -> None:
    overview = Region(
        Column(
            Box("header"),
            Row(Anchor("sm0", Box("SM 0")), Box("SM")),
        ),
        label="GPU",
    )
    callout = DetailCallout(
        overview,
        Region(Box("Tensor cores"), label="Inside one SM"),
        source="sm0",
        placement="below",
        label="expanded SM",
    )

    svg_body = _assert_ink_inside(callout)
    assert "stroke-dasharray" in svg_body
    assert "expanded SM" in svg_body
    assert "marker-end" not in svg_body


def test_auto_placement_uses_measured_shape() -> None:
    theme = Theme()
    wide = DetailCallout(
        Row(
            Anchor("wide-source", Box("0")),
            Box("1"), Box("2"), Box("3"), Box("4"),
        ),
        Box("detail"),
        source="wide-source",
    )
    tall = DetailCallout(
        Column(
            Anchor("tall-source", Box("0")),
            Box("1"), Box("2"), Box("3"), Box("4"),
        ),
        Box("detail"),
        source="tall-source",
    )

    assert wide.resolved_placement(theme) == "below"
    assert tall.resolved_placement(theme) == "right"


@pytest.mark.parametrize("placement", ["right", "below"])
def test_unlabelled_callout_renders_two_zoom_boundary_rails(placement) -> None:
    callout = DetailCallout(
        Region(Anchor("selected", Box("selected")), label="Overview"),
        Region(Box("expanded"), label="Detail"),
        source="selected",
        placement=placement,
    )

    svg_body = _assert_ink_inside(callout)
    # two expansion rails plus the automatically highlighted source extent
    assert svg_body.count("stroke-dasharray") >= 3
    assert "marker-end" not in svg_body


def test_recursive_callouts_render_two_semantic_detail_levels() -> None:
    row_detail = DetailCallout(
        Region(Anchor("row0", Box("PE row 0")), label="Array"),
        Region(Anchor("pe0", Box("PE 0")), label="Inside row"),
        source="row0",
        placement="right",
        label="row detail",
    )
    pe_detail = DetailCallout(
        row_detail,
        Region(Box("FIFO + ALU"), label="Inside PE"),
        source="pe0",
        placement="below",
        label="PE detail",
    )

    svg_body = _assert_ink_inside(pe_detail)
    assert "row detail" in svg_body
    assert "PE detail" in svg_body
    assert svg_body.count("stroke-dasharray") >= 2
