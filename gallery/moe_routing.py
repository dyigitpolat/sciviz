"""Sparse Mixture-of-Experts: top-2 routing with auxiliary load balancing.

Refactored: the bespoke RouterDiagram is replaced by the generic
``BipartiteGraph``.  Load chart uses ``BarChart(auto_color=True)``.  All
formulas are typeset with ``Math``; all colours come from ``Palette``.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, BipartiteGraph, BarChart,
                    Math, Section, TextBlock)

# Top-2 routing: 4 tokens to 2 of 8 experts each
edges = [
    (0, 0, 0.80), (0, 3, 0.60),    # "the"  -> E1, E4
    (1, 1, 0.70), (1, 5, 0.50),    # "cat"  -> E2, E6
    (2, 2, 0.90), (2, 0, 0.40),    # "sat"  -> E3, E1
    (3, 4, 0.75), (3, 2, 0.55),    # "down" -> E5, E3
]
router = BipartiteGraph(
    left=["the", "cat", "sat", "down"],
    right=[f"E{i+1}" for i in range(8)],
    edges=edges,
    height=210, column_gap=180, node_w=56,
    color_by="right",
)

# Per-expert load
expert_counts = [0] * 8
for _, j, _ in edges:
    expert_counts[j] += 1
total = sum(expert_counts)
load = BarChart(
    [(f"E{i+1}", c / total, f"{c} tok") for i, c in enumerate(expert_counts)],
    bar_width=140, bar_height=9, vmax=1.0, auto_color=True,
)

formulas = Column(
    Section(
        "Router gate",
        Math(r"$g(x) = \mathrm{softmax}(W_g x),\ "
             r"y = \sum_{j \in \mathrm{top}_k g} g_j\, E_j(x)$"),
        caption="Only k experts compute per token (FLOPs scale with k, not N)",
    ),
    Section(
        "Auxiliary load-balancing loss",
        Math(r"$\mathcal{L}_\mathrm{aux} = "
             r"N \sum_{j=1}^{N} f_j \cdot \bar g_j$"),
        caption=("f_j = fraction of tokens routed to expert j;  "
                 "g-bar_j = mean gate value.  Penalises imbalance."),
    ),
    gap="lg", align="start",
)

d = Diagram(
    title="Sparse Mixture-of-Experts: top-k routing",
    subtitle="only k of N experts activate per token; FLOPs scale with k, parameters with N",
    body=Row(
        Panel("a", "Routing  (top-2, 8 experts)", router),
        Panel("b", "Load per expert", load),
        Panel("c", "Formulas",        formulas),
        gap="md", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "moe_routing")
print("Rendered:", d.measure())
