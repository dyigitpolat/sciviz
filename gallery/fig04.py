"""Fig 04 - AlignedStack cross-parent column alignment.

Two independent ``Table`` children have different content widths per
column.  Wrapping them in an ``AlignedStack`` makes their columns share
the maximum width per slot, producing a perfectly aligned schedule.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    AlignedStack,
    Box,
    Column,
    Diagram,
    Row,
    Span,
    Table,
    Text,
)


def cell(tag: str, color: str):
    return Box(Text(tag, color="white", weight="bold"), fill=color,
               stroke=color, width=90)


stage_a = Table(
    [[cell("load", "#1e3a8a"), cell("forward", "#134e4a"),
      cell("wait", "#44403c")]],
    col_align=("center", "center", "center"),
    gap_x="sm",
)
stage_b = Table(
    [[cell("load large batch", "#1e3a8a"),
      cell("fwd", "#134e4a"),
      cell("bwd and step", "#44403c")]],
    col_align=("center", "center", "center"),
    gap_x="sm",
)

aligned = AlignedStack(
    Column(Text("pipeline stage 1", size="small", color="muted"), stage_a,
           gap="sm", align="start"),
    Column(Text("pipeline stage 2", size="small", color="muted"), stage_b,
           gap="sm", align="start"),
    gap="md",
)

note = Text(
    ["The two rows share column widths ",
     Span("even though their cells differ", color="highlight"),
     " -- AlignedStack propagates max width per slot."],
    size="small", color="muted",
)

d = Diagram(
    title="Aligned schedules",
    subtitle="cross-parent column alignment with AlignedStack",
    body=Column(aligned, note, gap="lg", align="start"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig04")
print("Rendered:", d.measure())
