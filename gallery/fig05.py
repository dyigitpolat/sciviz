"""Fig 05 - Region corner badges + structured text runs.

Three feature cards, each a ``Region`` carrying a corner badge (``new``,
``beta``, ``stable``) and a structured-text body.  Uses the new semantic
positive/negative/warning role colours for the badges.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Box,
    Column,
    DEFAULT_THEME,
    Diagram,
    Region,
    Row,
    Span,
    Text,
    TextBlock,
)


def badge(text: str, role: str) -> Box:
    fill = DEFAULT_THEME.role(role, "fill")
    return Box(
        Text(text.upper(), color="white", size="tiny", weight="bold"),
        fill=fill, stroke=fill, width=58,
    )


def card(title: str, body, role_badge):
    tag_text, role_name = role_badge
    return Region(
        TextBlock(body, size="small", line_spacing=1.4, max_width=240),
        label=title,
        pad_x=12, pad_y=10, margin_y=14,
        corner_badge=badge(tag_text, role_name),
    )


cards = Row(
    card("AlignedStack",
         [["Share column widths ", Span("across parents", weight="700")],
          ["Two-pass measure; opt-in via ",
           Span("_apply_shared_columns", color="accent")]],
         ("stable", "positive")),
    card("Tree",
         [[Span("Generic ", weight="700"),
           "top-down tree with per-edge labels"],
          ["Replaces NodeTree for arbitrary Element nodes"]],
         ("new", "info")),
    card("Separator",
         [[Span("Auto-stretch ", weight="700"),
           "inside Row/Column"],
          ["Choose dash, dot, or solid"]],
         ("beta", "warning")),
    gap="lg", align="start",
)

d = Diagram(
    title="Feature cards",
    subtitle="corner_badge + structured text runs + semantic role colours",
    body=cards,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig05")
print("Rendered:", d.measure())
