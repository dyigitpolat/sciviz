"""Fig 02 - Existing primitives with structured text runs.

Demonstrates ``Span`` -- inline styled text within ``Text`` and
``TextBlock`` -- by building a ``Box`` whose label highlights just the
quantity of interest, and a surrounding ``Caption`` with emphasised
phrases.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Box,
    Caption,
    Column,
    Diagram,
    Row,
    Span,
    Text,
    TextBlock,
)


def labelled(tag: str, highlight: str, unit: str, color: str):
    content = [
        tag, " = ",
        Span(highlight, color=color, weight="700"),
        " ", Span(unit, color="muted", size="small"),
    ]
    return Box(Text(content, size="label"), width=160, fill=color,
               stroke=color)


cost = Row(
    labelled("compute", "312", "TFLOP/s", "#1e3a8a"),
    labelled("bandwidth", "2.0", "TB/s", "#134e4a"),
    labelled("latency", "1.1", "ms", "#b45309"),
    gap="lg", align="center",
)

note = TextBlock(
    [
        ["Each box pairs its ", Span("headline number", weight="700"),
         " with a muted unit."],
        ["Inline ", Span("coloured", color="#134e4a", weight="700"),
         " runs reuse theme tokens without breaking hierarchy."],
    ],
    size="small", line_spacing=1.35,
)

d = Diagram(
    title="Inline text runs",
    subtitle="structured spans inside Text and TextBlock",
    body=Column(cost, note, gap="lg", align="start"),
)

d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig02")
print("Rendered:", d.measure())
