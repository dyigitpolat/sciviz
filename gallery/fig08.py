"""Fig 08 - Icon-driven data pipeline with a spanning brace.

A four-stage ETL-style pipeline uses bundled Lucide icons to label each
phase.  A ``Brace.spanning`` under the row annotates the middle three
stages as ``"compute"`` while the rest are framed as IO.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Brace,
    Column,
    Diagram,
    Icon,
    Row,
    Text,
)


def stage(icon_name: str, label: str, color: str):
    return Column(
        Icon(icon_name, size=36, color=color),
        Text(label, size="small"),
        gap="sm", align="center",
    )


stages = Row(
    stage("download", "ingest", "primary"),
    stage("filter", "clean", "accent"),
    stage("cpu", "transform", "amber"),
    stage("database", "persist", "purple"),
    gap="xl", align="end",
)

d = Diagram(
    title="Stream pipeline",
    subtitle="icons + Brace.spanning -- self-sizing to the stage row",
    body=Column(
        stages,
        Brace.spanning(stages, label="four-stage data path"),
        gap="sm", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig08")
print("Rendered:", d.measure())
