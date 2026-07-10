"""Panel headers accept semantic element tags without manual geometry."""

from sciviz import BBox, Badge, Box, Canvas, Element, Panel, Palette, Theme


def test_panel_accepts_badge_as_measured_tag():
    theme = Theme()
    badge = Badge("3", color=Palette.info, size="sm")
    panel = Panel(badge, "Transfer pipeline", Box("body"))
    size = panel.measure(theme)
    canvas = Canvas()
    panel.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(size.w, size.h)

    assert "Transfer pipeline" in svg
    assert "<circle" in svg
    assert size.w >= badge.measure(theme).w


def test_panel_rejects_non_element_header_values():
    try:
        Panel(3, "title", Box("body"))
    except TypeError as exc:
        assert "Panel.tag" in str(exc)
    else:  # pragma: no cover - failure branch
        raise AssertionError("Panel should reject non-string/non-Element tags")


class _Probe(Element):
    def __init__(self, width, height):
        self.box = BBox(width, height)
        self.render_y = None

    def measure(self, theme):
        return self.box

    def render(self, canvas, x, y, theme):
        self.render_y = y


def test_panel_footer_anchors_to_bottom_of_inflated_panel():
    theme = Theme()
    body = _Probe(80, 30)
    footer = _Probe(60, 12)
    panel = Panel("2", "Pipeline", body, footer=footer)
    panel.inflate_to(0, 180)
    panel.render(Canvas(), 0, 0, theme)

    assert footer.render_y == 180 - theme.panel_padding - footer.box.h
    assert body.render_y < footer.render_y
