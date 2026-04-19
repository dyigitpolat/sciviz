"""Fig 07 - Tree with per-edge colour and labels.

A speculative-decoding verification tree: the proposal tokens branch
into accepted (green) and rejected (red) futures; rejection is drawn
dashed to reinforce the semantic difference.
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
    Text,
    Tree,
)


def tok(s: str, color: str = "muted"):
    return Box(Text(s, size="small"), width=48, fill="bg_subtle",
               stroke=color)


accept = {"color": "positive", "label": "accept"}
reject = {"color": "negative", "label": "reject", "style": "dashed"}

tree = Tree(Tree.node(
    tok("the", "primary"),
    children=[
        (Tree.node(tok("cat", "positive"), children=[
            (Tree.node(tok("sat", "positive")), accept),
            (Tree.node(tok("ran", "negative")), reject),
        ]), accept),
        (Tree.node(tok("dog", "negative")), reject),
    ],
))

d = Diagram(
    title="Speculative decoding tree",
    subtitle="per-edge colour and style from semantic role tokens",
    body=Column(tree, Caption("green = accepted, red dashed = rejected"),
                gap="sm", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig07")
print("Rendered:", d.measure())
