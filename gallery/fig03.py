"""Fig 03 - Region side labels and per-zone annotations.

Three stacked phases of a training loop, each wrapped in a ``Region``.
One uses a left-side label, one a bottom label, one a corner badge.
Annotations document the dominant cost of each phase next to its border.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Box,
    Column,
    Diagram,
    Region,
    Row,
    Text,
)


def phase(label_pos: str, title: str, *cells, corner: Text | None = None,
          annotations=None):
    body = Row(*[Box(c, width=110) for c in cells], gap="md")
    return Region(
        body,
        label=title,
        label_position=label_pos,
        annotations=annotations or [],
        corner_badge=corner,
        pad_y=10, margin_y=14,
    )


phases = Column(
    phase("top", "Forward",
          "embed", "blocks", "head",
          annotations=[("right", "dominated by GEMM")]),
    phase("left", "Backward",
          "head\u02b8", "blocks\u02b8", "embed\u02b8",
          annotations=[("right", "~2.3x forward FLOPs")]),
    phase("top", "Optimizer",
          "adam step",
          corner=Text("fp32", color="accent", size="tiny", weight="bold"),
          annotations=[("right", "bandwidth-bound")]),
    gap="lg", align="start",
)

d = Diagram(
    title="Training step phases",
    subtitle="label_position + annotations + corner_badge",
    body=phases,
)

d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig03")
print("Rendered:", d.measure())
