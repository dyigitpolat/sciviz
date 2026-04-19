"""Fig 10 - Separator + AlignedStack.

A release-notes table of three stanzas separated by horizontal rules.
Each stanza is a small ``Row`` with its own "column" of (tag, text);
``AlignedStack`` makes the tag column identical width across stanzas,
and ``Separator`` stretches to the full width between them.
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
    Separator,
    Span,
    Text,
)


def tag(word: str, color: str) -> Box:
    return Box(Text(word.upper(), color="white", size="tiny", weight="bold"),
               fill=color, stroke=color, width=72)


def stanza(tag_box: Box, headline: str, detail: str):
    return Row(
        tag_box,
        Column(
            Text([headline], size="label", weight="bold"),
            Text(detail, size="small", color="muted"),
            gap="xs", align="start",
        ),
        gap="md", align="center",
    )


stack = AlignedStack(
    stanza(tag("added", "#2d7a70"),
           "AlignedStack + Separator",
           "Cross-parent column alignment with full-width rules."),
    stanza(tag("changed", "#b45309"),
           "Region label_position",
           "Labels now sit on any side; annotations hang outside."),
    stanza(tag("deprecated", "#991b1b"),
           "NodeTree",
           "Prefer Tree for generic Element nodes."),
    gap="md",
)

body = Column(
    stack,
    Separator(length=420, orientation="horizontal", style="dashed"),
    Text(["See ",
          Span("plans/ten-of-ten.md", color="accent", weight="700"),
          " for the full changelog."],
         size="small", color="muted"),
    gap="md", align="start",
)

d = Diagram(
    title="Release notes",
    subtitle="AlignedStack anchors the tag column; Separator fills width",
    body=body,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig10")
print("Rendered:", d.measure())
