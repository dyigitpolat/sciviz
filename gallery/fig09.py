"""Fig 09 - Icon-heavy composition.

A taxonomy of operations, laid out as a 3x3 grid where each cell is an
icon with a caption.  Colour roles distinguish categories (compute vs
memory vs policy) without any legend needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Column,
    Diagram,
    Icon,
    Row,
    Text,
)


def chip(icon_name: str, name: str, family: str):
    color = {
        "compute": "primary",
        "memory":  "accent",
        "policy":  "amber",
    }[family]
    return Column(
        Icon(icon_name, size=28, color=color),
        Text(name, size="small"),
        gap="sm", align="center",
    )


grid = Column(
    Row(chip("cpu", "matmul", "compute"),
        chip("refresh-cw", "reduce", "compute"),
        chip("function-square", "activate", "compute"),
        gap="xl"),
    Row(chip("memory-stick", "load", "memory"),
        chip("database", "cache", "memory"),
        chip("hard-drive", "page", "memory"),
        gap="xl"),
    Row(chip("shield", "clip", "policy"),
        chip("filter", "sample", "policy"),
        chip("git-branch", "route", "policy"),
        gap="xl"),
    gap="xl", align="start",
)

d = Diagram(
    title="Op taxonomy",
    subtitle="icon + label grid across three operation families",
    body=grid,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig09")
print("Rendered:", d.measure())
