"""``Box(title=...)`` heads a block with a line of its own.

Motivating case (thesis evidence ladder / assurance stack): five blocks
labelled ``"Rung 4: Cycle-accurate simulation"``. Folded into one wrapped
string, the rung's NAME is whatever fits on line one and the rest of the
sentence trails after it, so the reader has to find where the name ends.
A title is the missing distinction: it is drawn above the body, in its own
weight, and it participates in the same wrapping and auto-sizing as the
label, so the block still sizes itself.

The invariants checked here are the ones a figure actually depends on:
the title sits ABOVE the body, it is a separate run at its own weight, it
grows the box rather than overflowing it, and it stays inside the border.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Text, Theme
from sciviz.core import Canvas


_TEXT_RX = re.compile(r"<text ([^>]*)>([^<]*)</text>")


def _attr(raw: str, name: str, default=None):
    m = re.search(rf'{name}="([^"]+)"', raw)
    return m.group(1) if m else default


def _render(elem, theme=None):
    theme = theme or Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size, theme


def _texts(svg: str) -> list[dict]:
    out = []
    for m in _TEXT_RX.finditer(svg):
        raw, content = m.group(1), m.group(2)
        out.append({
            "x": float(_attr(raw, "x", "0")),
            "y": float(_attr(raw, "y", "0")),
            "fs": float(_attr(raw, "font-size", "0")),
            "weight": _attr(raw, "font-weight", "normal"),
            "fill": (_attr(raw, "fill", "") or "").lower(),
            "text": content,
        })
    return out


def _one(svg: str, text: str) -> dict:
    hits = [t for t in _texts(svg) if t["text"] == text]
    assert len(hits) == 1, f"expected exactly one {text!r} run in\n{svg}"
    return hits[0]


def test_title_is_drawn_above_the_label():
    svg, _, _ = _render(Box(title="Rung 4", label="Cycle-accurate simulation"))
    title = _one(svg, "Rung 4")
    body = _one(svg, "Cycle-accurate simulation")
    assert title["y"] < body["y"], (
        f"title baseline {title['y']} should sit above body {body['y']}")


def test_title_carries_its_own_weight():
    """The title is what makes the block a titled block: it is bold by
    default while the body keeps the box's own text weight."""
    svg, _, _ = _render(Box(title="Layer 2", label="Lowering invariants",
                            text_weight="400"))
    assert _one(svg, "Layer 2")["weight"] == "700"
    assert _one(svg, "Lowering invariants")["weight"] == "400"


def test_title_weight_size_and_colour_are_overridable():
    theme = Theme()
    svg, _, _ = _render(Box(title="Layer 2", label="Lowering invariants",
                            text_size="small", title_size="tiny",
                            title_weight="500", title_color="highlight"),
                        theme)
    title = _one(svg, "Layer 2")
    body = _one(svg, "Lowering invariants")
    assert title["weight"] == "500"
    assert title["fs"] < body["fs"]
    assert title["fill"] == theme.color_of("highlight").lower()


def test_titled_box_is_taller_and_no_narrower_than_the_untitled_one():
    theme = Theme()
    plain = Box("Cycle-accurate simulation").measure(theme)
    titled = Box(title="Rung 4", label="Cycle-accurate simulation").measure(theme)
    assert titled.h > plain.h, "the title strip must be reserved, not overlaid"
    assert titled.w >= plain.w - 0.01


def test_a_long_title_widens_the_box_instead_of_overflowing_it():
    theme = Theme()
    box = Box(title="Configuration validity gate", label="ok")
    svg, size, _ = _render(box, theme)
    title = _one(svg, "Configuration validity gate")
    half = theme.text_width(title["text"], title["fs"], bold=True) / 2
    assert title["x"] - half >= -0.01
    assert title["x"] + half <= size.w + 0.01


def test_title_wraps_on_the_boxs_own_budget():
    theme = Theme()
    box = Box(title="Layer 3: cross-implementation conformance",
              label="Independent implementations agree",
              wrap=True, max_width=90.0, text_size="small")
    svg, size, _ = _render(box, theme)
    runs = [t for t in _texts(svg)]
    assert len(runs) > 2, "a long title and body should both wrap"
    for t in runs:
        half = theme.text_width(t["text"], t["fs"],
                                bold=t["weight"] in ("700", "bold")) / 2
        assert t["x"] - half >= -0.01 and t["x"] + half <= size.w + 0.01, (
            f"{t['text']!r} escapes the box of width {size.w}")


def test_every_line_stays_inside_the_border():
    theme = Theme()
    box = Box(title="Rung 5", label="Measured silicon", wrap=True,
              max_width=70.0)
    svg, size, _ = _render(box, theme)
    for t in _texts(svg):
        assert t["y"] <= size.h, f"{t['text']!r} baseline below the box"
        assert t["y"] - t["fs"] >= -0.01, f"{t['text']!r} above the box"


def test_title_only_box_still_renders_and_sizes():
    theme = Theme()
    box = Box(title="Rung 1")
    svg, size, _ = _render(box, theme)
    assert _one(svg, "Rung 1")
    assert size.w > 0 and size.h > 0


def test_title_heads_an_element_label_too():
    svg, _, _ = _render(Box(Text("body element"), title="Rung 2"))
    assert _one(svg, "Rung 2")["y"] < _one(svg, "body element")["y"]


def test_title_with_vertical_text_is_rejected():
    with pytest.raises(ValueError):
        Box("side", title="Rung 1", vertical_text=True)
