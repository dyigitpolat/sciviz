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
