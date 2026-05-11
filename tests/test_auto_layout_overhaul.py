from __future__ import annotations

import pytest

from sciviz import (
    Box,
    Card,
    Column,
    ConditionGlyph,
    ConditionSpec,
    Diagram,
    EqualGrid,
    Icon,
    MiniMatrix,
    Palette,
    SoftLegend,
    SparkLine,
    Sparkline,
    StepCell,
    Text,
    TextBlock,
)
from sciviz.auto.labels import (
    measure_label,
    place_segment_label,
    register_label_obstacle,
    registry_label_obstacles,
)
from sciviz.core import BBox, Canvas, Element, Theme
from sciviz.core import FontRegistry
from sciviz.composition._compound import _align_x_in_slot


def test_svg_embeds_font_face():
    theme = Theme(font_family="'DejaVu Sans', sans-serif")
    svg = Diagram.for_paper(Text("glyph safe"), theme=theme).render()
    assert "@font-face" in svg
    assert 'font-family: "DejaVu Sans"' in svg
    assert "base64," in svg


def test_svg_preserves_theme_font_stack():
    family = "'Helvetica Neue', Helvetica, Arial, 'DejaVu Sans', sans-serif"
    svg = Diagram.for_paper(Text("old gallery face"),
                            theme=Theme(font_family=family)).render()
    assert "font-family=\"'Helvetica Neue', Helvetica, Arial, 'DejaVu Sans', sans-serif\"" in svg
    assert "sciviz-" not in svg


def test_textblock_content_bbox_tracks_visual_line_band():
    theme = Theme()
    block = TextBlock("Short\nMuch Longer", size="tiny", align="center",
                      line_spacing=1.12)
    measure = block.measure(theme)
    cb = block.content_bbox(theme)
    assert cb[1] > 0
    assert cb[3] < measure.h
    assert cb[0] == pytest.approx(0.0)
    assert cb[2] == pytest.approx(measure.w)


def test_equalgrid_broadcasts_child_size():
    a = Card("A", StepCell("Short", MiniMatrix(role=Palette.blue), role=Palette.blue),
             role=Palette.blue)
    b = Card("B", StepCell("Activation Quantization",
                           MiniMatrix(role=Palette.red), role=Palette.red),
             role=Palette.red)
    grid = EqualGrid(a, b, columns=2, equal="both")
    theme = Theme()
    grid.measure(theme)
    assert a.measure(theme).w == pytest.approx(b.measure(theme).w)
    assert a.measure(theme).h == pytest.approx(b.measure(theme).h)


def test_stepcell_full_name_wraps_without_author_width():
    cell = StepCell("Core Quantization Verification",
                    Sparkline([SparkLine([(0, 0), (1, 1)], color=Palette.blue)]),
                    role=Palette.blue,
                    condition=ConditionSpec("verification", "automatic check"))
    size = cell.measure(Theme())
    assert size.w > 0
    assert size.h > 0


def test_condition_legend_renders_glyphs():
    legend = SoftLegend.from_conditions([
        ConditionSpec("branch", "either-or path"),
        ConditionSpec("toggle", "enabled by configuration"),
    ])
    svg = Diagram.for_paper(legend).render()
    assert "either-or path" in svg
    assert "enabled by configuration" in svg


def test_label_registry_roundtrip():
    theme = Theme()
    label = measure_label("handoff", theme, "tiny")
    placed = place_segment_label(((0, 10), (60, 10)), label, [], gap=theme.unit)
    registry = {}
    register_label_obstacle(registry, placed.rect, "test")
    assert registry_label_obstacles(registry)
    assert any(k.startswith("__label_") for k in registry)


def test_canvas_ink_bbox_tracks_text():
    canvas = Canvas()
    canvas.text(-20, -10, "outside")
    assert canvas.ink_bbox is not None
    x0, y0, _, _ = canvas.ink_bbox
    assert x0 < 0
    assert y0 < 0


class Overpaint(Element):
    def measure(self, theme: Theme):
        from sciviz.core import BBox
        return BBox(10, 10)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        canvas.text(x - 25, y - 10, "outside", size=10)


def test_diagram_for_paper_auto_fits_overflow():
    d = Diagram.for_paper(Overpaint())
    nominal = d.measure()
    d.render()
    assert d._last_render_size.w > nominal.w
    assert d._last_render_size.h > nominal.h


def test_pdf_backend_probe_falls_back_to_cairosvg(monkeypatch):
    from sciviz.diagram import Diagram as DiagramClass

    monkeypatch.setattr("shutil.which", lambda name: None)
    assert DiagramClass._probe_pdf_backend() == "cairosvg"


def test_condition_glyph_rejects_unknown_kind():
    with pytest.raises(ValueError):
        ConditionGlyph("code-flag")


def test_stepcell_index_badge_grows_for_two_digits():
    one = StepCell("One", MiniMatrix(role=Palette.blue), role=Palette.blue, index=9)
    two = StepCell("Two", MiniMatrix(role=Palette.blue), role=Palette.blue, index=21)
    theme = Theme()
    assert two._index_badge_size(theme).w > one._index_badge_size(theme).w
    assert two.measure(theme).w > 0


def test_icon_content_bbox_uses_glyph_not_full_viewbox():
    icon = Icon("arrow-up", size=24)
    bbox = icon.content_bbox(Theme())
    assert bbox[2] < icon.measure(Theme()).w
    assert bbox[3] < icon.measure(Theme()).h


def test_arc_icon_content_bbox_uses_path_commands_not_raw_numbers():
    theme = Theme()
    for name in ("settings", "brain", "zap"):
        icon = Icon(name, size="small")
        bbox = icon.content_bbox(theme)
        size = icon.measure(theme)
        cy = bbox[1] + bbox[3] / 2
        assert cy == pytest.approx(size.h / 2, abs=0.2)


def test_png_auto_text_mode_keeps_live_text(monkeypatch, tmp_path):
    calls = {}

    class FakeResvg:
        @staticmethod
        def svg_to_bytes(*, svg_string, width, height):
            calls["svg"] = svg_string
            return b"png"

    import sys

    monkeypatch.setitem(sys.modules, "resvg_py", FakeResvg)
    Diagram.for_paper(Text("same text")).save(tmp_path / "out.png")
    assert "<text" in calls["svg"]
    assert "same text" in calls["svg"]


def test_png_outline_text_mode_outlines_text(monkeypatch, tmp_path):
    calls = {}

    class FakeResvg:
        @staticmethod
        def svg_to_bytes(*, svg_string, width, height):
            calls["svg"] = svg_string
            return b"png"

    import sys

    monkeypatch.setitem(sys.modules, "resvg_py", FakeResvg)
    Diagram.for_paper(Text("same text")).save(tmp_path / "out.png",
                                              text_mode="outline")
    assert "<path" in calls["svg"]
    assert "same text" not in calls["svg"]


def test_pdf_auto_text_mode_keeps_live_text(monkeypatch, tmp_path):
    calls = {}

    class FakeCairoSvg:
        @staticmethod
        def svg2pdf(*, bytestring, write_to):
            calls["svg"] = bytestring.decode("utf-8")

    import sys

    monkeypatch.setitem(sys.modules, "cairosvg", FakeCairoSvg)
    monkeypatch.setattr("shutil.which", lambda name: None)
    Diagram.for_paper(Text("same text")).save(tmp_path / "out.pdf")
    assert "<text" in calls["svg"]
    assert "same text" in calls["svg"]


def test_font_registry_respects_requested_family():
    registry = FontRegistry.default("'DejaVu Sans', sans-serif")
    assert "DejaVuSans" in registry.primary.ttf_path.name


class OffsetContentVisual(Element):
    def __init__(self):
        self.render_y = None

    def measure(self, theme: Theme):
        from sciviz.core import BBox
        return BBox(20, 40)

    def content_bbox(self, theme: Theme):
        return (0.0, 18.0, 20.0, 10.0)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self.render_y = y
        canvas.rect(x, y + 18, 20, 10, fill=theme.bg_subtle, stroke=theme.border)


def test_stepcell_aligns_visual_by_content_bbox():
    visual = OffsetContentVisual()
    cell = StepCell("Aligned Label", visual, role=Palette.blue, index=12)
    theme = Theme()
    canvas = Canvas()
    cell.render(canvas, 0, 0, theme)
    cell_center = cell.measure(theme).h / 2
    visual_content_center = visual.render_y + 18 + 10 / 2
    assert visual_content_center == pytest.approx(cell_center)


class WideVisual(Element):
    def __init__(self, w: float):
        self.w = w

    def measure(self, theme: Theme):
        return BBox(self.w, 12)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        canvas.rect(x, y, self.w, 12, fill=theme.bg_subtle, stroke=theme.border)


def test_stepcell_sibling_label_slots_share_center_axis():
    theme = Theme()
    a = StepCell("Alpha", WideVisual(10), role=Palette.blue, index=1)
    b = StepCell("Longer Label", WideVisual(40), role=Palette.blue, index=2)
    Column(a, b, gap=0).measure(theme)
    pad = theme.unit * 0.55

    def label_center(cell: StepCell) -> float:
        left, visual, label, _ = cell._slot_widths(theme)
        return left + visual + pad + label / 2

    assert label_center(a) == pytest.approx(label_center(b))


def test_slot_alignment_respects_start_center_end_edges():
    theme = Theme()
    center = TextBlock("center", align="center")
    start = TextBlock("start", align="start")
    end = TextBlock("end", align="end")
    slot_x = 25.0
    slot_w = 100.0
    cx = _align_x_in_slot(center, slot_x, slot_w, theme, "center")
    sx = _align_x_in_slot(start, slot_x, slot_w, theme, "start")
    ex = _align_x_in_slot(end, slot_x, slot_w, theme, "end")
    ccb = center.content_bbox(theme)
    scb = start.content_bbox(theme)
    ecb = end.content_bbox(theme)
    assert cx + ccb[0] + ccb[2] / 2 == pytest.approx(slot_x + slot_w / 2)
    assert sx + scb[0] == pytest.approx(slot_x)
    assert ex + ecb[0] + ecb[2] == pytest.approx(slot_x + slot_w)


class HeaderProbe(Element):
    def __init__(self, h: float):
        self.h = h
        self.render_y = None

    def measure(self, theme: Theme):
        return BBox(30, self.h)

    def content_bbox(self, theme: Theme):
        return (0.0, self.h * 0.25, 30.0, self.h * 0.5)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self.render_y = y
        canvas.rect(x, y + self.h * 0.25, 30, self.h * 0.5,
                    fill="white", stroke="none")


def test_card_headers_share_band_height_and_center_content():
    theme = Theme()
    short_header = HeaderProbe(10)
    tall_header = HeaderProbe(24)
    a = Card(short_header, Box("A"), role=Palette.blue)
    b = Card(tall_header, Box("B"), role=Palette.green)
    EqualGrid(a, b, columns=2, equal="width").measure(theme)
    assert a._header_height(theme) == pytest.approx(b._header_height(theme))

    canvas = Canvas()
    a.render(canvas, 0, 0, theme)
    header_center = a._header_height(theme) / 2
    content_center = short_header.render_y + short_header.h * 0.25 + short_header.h * 0.25
    assert content_center == pytest.approx(header_center)


# ---------------------------------------------------------------------------
# Regression tests for the layout-engine fix plan.
# ---------------------------------------------------------------------------

def test_inline_arrow_label_does_not_force_long_shaft():
    """Long labels expand the bbox modestly but never blow the shaft up
    to label-width. Previously a 12-word label produced a 200+ px shaft
    that pushed neighbouring cards far apart."""
    from sciviz import Connect
    theme = Theme()
    label = "forward + inputs / observations bus"
    short = Connect(direction="right")
    labelled = Connect(label=label, direction="right")
    short_bbox = short.measure(theme)
    labelled_bbox = labelled.measure(theme)
    label_w = theme.text_width(label, "small")
    # The labelled arrow may be slightly wider (a small label cushion)
    # but never anywhere near the label's text width.
    assert labelled_bbox.w < label_w * 0.75, (
        f"labelled arrow w={labelled_bbox.w} should be much smaller than "
        f"label width {label_w}"
    )
    # Both arrows should keep at least the compact default shaft.
    assert short_bbox.w >= 48.0 - 0.5


def test_row_equal_widths_skips_inline_connectors():
    """An equal-width row of cards interspersed with inline arrows must
    equalise *only* the cards. Connectors keep their compact width so
    cards don't get pushed apart by their connector neighbours."""
    from sciviz import Connect, Row
    theme = Theme()
    short_card = Box("A", width=60, height=24)
    long_card = Box("Much Longer Label", height=24)
    arrow = Connect(label="next", direction="right")
    row = Row(short_card, arrow, long_card, gap=0, equal_widths=True)
    short_bbox = short_card.measure(theme)
    long_bbox = long_card.measure(theme)
    arrow_bbox = arrow.measure(theme)
    expected = long_bbox.w * 2 + arrow_bbox.w
    assert row.measure(theme).w == pytest.approx(expected, abs=0.5)


def test_sequence_widens_for_long_actor_labels():
    """Sequence must reserve enough column width to render its actor
    labels readably; previously a small default ``width=`` truncated
    them with a hard min-clamp."""
    from sciviz import Sequence
    theme = Theme()
    seq = Sequence(
        ["UserPlanner", "ToolHarness", "OrchestratorBackend"],
        [(0, 0, 1, "send plan"), (1, 1, 2, "dispatch")],
        width=120,
    )
    bbox = seq.measure(theme)
    longest = max(
        theme.text_width(name, "label", bold=True) + theme.unit * 2.4
        for name in seq.actors
    )
    # Each column must contain the longest actor label, so the total
    # width is at least 3 * longest.
    assert bbox.w >= longest * len(seq.actors) - 0.5


def test_sequence_widens_for_long_interaction_labels():
    """An interaction label longer than the column gap must widen the
    sequence so the label sits inside its arrow segment."""
    from sciviz import Sequence
    theme = Theme()
    long_label = "typed Plan / observations payload"
    short = Sequence(
        ["A", "B"], [(0, 0, 1, "hi")], width=100,
    )
    wide = Sequence(
        ["A", "B"], [(0, 0, 1, long_label)], width=100,
    )
    assert wide.measure(theme).w > short.measure(theme).w + 20


def test_region_border_stays_inside_measured_bbox():
    """The Region border ink must lie inside the reported measure
    bbox. Previously the border encroached ``pad_x`` to the left of
    the bbox, so a Region inside a tight Card painted its border on
    top of the Card's left edge."""
    from sciviz import Box, Region
    theme = Theme()
    region = Region(Box("inner", width=80, height=30), label="R", pad_x=12)
    bbox = region.measure(theme)
    canvas = Canvas()
    region.render(canvas, 0, 0, theme)
    ink = canvas.ink_bbox
    assert ink is not None
    x0, _y0, x1, _y1 = ink
    # The ink may legitimately extend slightly past the reported bbox
    # because of stroke widths and text antialiasing, but the LEFT edge
    # must not encroach more than the stroke width.
    assert x0 >= -theme.hairline - 0.5
    assert x1 <= bbox.w + theme.hairline + 0.5


def test_card_inflate_to_uses_theme_padding():
    """Card.inflate_to should defer body inflation so it matches the
    theme padding that measure/render use."""
    from sciviz import Card, Text
    from sciviz.palette import Palette as PaletteCls
    theme = Theme()
    pad = theme.gap_px("sm")  # default Card padding token
    body = Box("inner", width=40, height=20)
    card = Card("Title", body, role=PaletteCls.blue, padding="sm")
    base_bbox = card.measure(theme)
    target_w = base_bbox.w + 80
    card.inflate_to(target_w, 0)
    # measure should now report at least the requested target width.
    grown = card.measure(theme)
    assert grown.w >= target_w - 0.5
    # The body width should grow to (target - 2 * pad) so the card
    # boundary and body interior agree at render time.
    body_bbox = body.measure(theme)
    assert body_bbox.w >= target_w - 2 * pad - 0.5


def test_row_equal_widths_inflates_children_to_slot():
    """A Row with ``equal_widths=True`` must inflate every non-connector
    child so its rendered width equals the widest peer's slot. Without
    this, equal slots merely centred children with leftover whitespace
    on both sides, producing uneven visible gaps in the rendered SVG."""
    from sciviz import Row
    theme = Theme()
    short_card = Box("A", width=60, height=24)
    long_card = Box("Much Longer Label", height=24)
    long_w = long_card.measure(theme).w
    row = Row(short_card, long_card, gap=0, equal_widths=True)
    row.measure(theme)
    # Both children should now report the same outer width as the
    # widest peer, NOT their intrinsic 60 px width.
    assert short_card.measure(theme).w == pytest.approx(long_w, abs=0.5)
    assert long_card.measure(theme).w == pytest.approx(long_w, abs=0.5)


def test_row_inflate_to_lifts_min_width_and_propagates():
    """A Row floor (``inflate_to``) lifts its measured width and -- when
    ``equal_widths=True`` -- the surplus distributes evenly across the
    non-connector children so the Row actually fills the parent slot."""
    from sciviz import Row
    theme = Theme()
    a = Box("A", width=40, height=20)
    b = Box("B", width=40, height=20)
    row = Row(a, b, gap=0, equal_widths=True)
    row.inflate_to(200, 0)
    bbox = row.measure(theme)
    assert bbox.w >= 200 - 0.5
    # Each card receives 100 px of the 200 px row width.
    assert a.measure(theme).w == pytest.approx(100, abs=0.5)
    assert b.measure(theme).w == pytest.approx(100, abs=0.5)


def test_region_inflate_propagates_to_child():
    """When a parent inflates a Region (e.g. Column.equal_widths=True),
    the Region must forward the surplus width to its child so the
    decorated border and the inner content grow together instead of
    centring narrow ink inside a stretched box."""
    from sciviz import Region
    theme = Theme()
    inner = Box("inner", width=40, height=30)
    region = Region(inner, label="R", pad_x=10)
    base = region.measure(theme)
    target_w = base.w + 120
    region.inflate_to(target_w, 0)
    grown = region.measure(theme)
    assert grown.w >= target_w - 0.5
    # The child should grow by roughly the same amount the region grew
    # (modulo padding/margins that ``_reserve`` accounts for).
    new_inner_w = inner.measure(theme).w
    assert new_inner_w > 40 + 50, (
        f"inner width {new_inner_w} did not grow with region width "
        f"{grown.w}"
    )


def test_orthogonal_router_keeps_axis_aligned_for_near_aligned_endpoints():
    """Two anchors on opposite faces with a small parallel-axis
    misalignment must still produce a strictly orthogonal route -- the
    historical diagonal shortcut violated the axis-aligned contract,
    so the planner now emits a tight Z (one perpendicular arm of
    length ``abs(sy - dy)``) instead."""
    from sciviz.auto.router import Box as RBox, Endpoint, plan_path
    src = RBox(x=0, y=0, w=40, h=30, name="src")
    dst = RBox(x=200, y=3, w=40, h=30, name="dst")  # slight y misalignment
    plan = plan_path(
        Endpoint(src, side="right", tap=8.0),
        Endpoint(dst, side="left", tap=8.0),
        anchors=[src, dst],
    )
    # Every segment must be either purely horizontal or purely
    # vertical (no diagonal travel).
    for (x1, y1), (x2, y2) in zip(plan.waypoints[:-1], plan.waypoints[1:]):
        assert abs(x1 - x2) < 0.5 or abs(y1 - y2) < 0.5, (
            f"diagonal segment {(x1, y1)} -> {(x2, y2)} in plan {plan.waypoints}"
        )
    # The route should not have been emitted as "direct" any more.
    assert plan.style_hint != "direct"


def test_orthogonal_router_keeps_minimum_visible_tap():
    """``policy.min_tap`` should be respected so wrap-back routes have
    a visible stub instead of dropping straight into the obstacle."""
    from sciviz.auto.router import (
        Box as RBox, Endpoint, plan_path, DEFAULT_POLICY,
    )
    src = RBox(x=0, y=0, w=40, h=30, name="src")
    dst = RBox(x=0, y=80, w=40, h=30, name="dst")  # exactly below src
    plan = plan_path(
        Endpoint(src, side="right", tap=20.0),
        Endpoint(dst, side="right", tap=20.0),
        anchors=[src, dst],
    )
    # First leg should be a visible stub of at least min_tap pixels.
    p0 = plan.waypoints[0]
    p1 = plan.waypoints[1]
    stub_len = max(abs(p1[0] - p0[0]), abs(p1[1] - p0[1]))
    assert stub_len >= DEFAULT_POLICY.min_tap - 0.5


def test_for_paper_trims_blank_margins():
    """Diagram.for_paper(auto_trim=True) trims accidental whitespace so
    a narrow body does not leave a large blank stripe to either side
    of the ink."""
    class BlankPaddedBody(Element):
        """Reports 400x40 but only paints in the centre 60 px."""

        def measure(self, theme: Theme):
            return BBox(400.0, 40.0)

        def render(self, canvas: Canvas, x: float, y: float,
                   theme: Theme) -> None:
            mid_x = x + 200.0
            canvas.rect(mid_x - 30, y + 5, 60, 30,
                        fill="#1f6feb", stroke="none")

    body = BlankPaddedBody()
    d = Diagram.for_paper(body)
    svg = d.render()
    final = d._last_render_size
    # The ink only covers ~60 px wide; with chrome=none margin ~4 px and
    # cushion ~4 px, the final canvas should be much narrower than 400.
    assert final.w < 200.0, (
        f"auto_trim failed to remove blank margins; size={final.w}"
    )
    assert "<svg" in svg
