"""A Canvas that records the primitives it paints, for layout tests."""
from __future__ import annotations

from sciviz.core import Canvas


class RecordingCanvas(Canvas):
    """Keeps ``(kind, args, kwargs)`` of every rect, circle, line and text."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls = []

    def rect(self, *a, **k):
        self.calls.append(("rect", a, k))
        return super().rect(*a, **k)

    def circle(self, *a, **k):
        self.calls.append(("circle", a, k))
        return super().circle(*a, **k)

    def line(self, *a, **k):
        self.calls.append(("line", a, k))
        return super().line(*a, **k)

    def text(self, *a, **k):
        self.calls.append(("text", a, k))
        return super().text(*a, **k)

    def of(self, kind):
        return [(a, k) for c, a, k in self.calls if c == kind]

    def texts(self):
        return {a[2]: (a, k) for a, k in self.of("text")}


def render(element, theme, x=10.0, y=10.0):
    """Render ``element`` at ``(x, y)`` with the theme's real font stack, so
    the canvas ledger measures glyphs (arrows, µ, ×, …) as the page does;
    return the canvas and the element's measured box."""
    canvas = RecordingCanvas(default_font_family=theme.font_family)
    box = element.measure(theme)
    element.render(canvas, x, y, theme)
    return canvas, (x, y, x + box.w, y + box.h)


def assert_inside(element, theme, canvas, box):
    """The bbox contract: no ink outside the measured ``box``.

    A text run's top is exempt: the ink model reserves the font's full
    ascent above every line, so a bare ``Text`` already reports it."""
    from sciviz.auto.ink import overflow_items
    over = [o for o in overflow_items(canvas, box)
            if not (o[0] == "text" and o[1] == "top")]
    assert over == [], over
