"""LoRA: low-rank adaptation of large language models.

Three panels: decomposition, parameter budget, runtime path.  All bars are
auto-coloured; manual hex codes are confined to a single helper that keeps
the runtime-path frozen/trainable distinction visually obvious.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, Connector, NNLayer, BarChart,
                    Math, Caption, Section, Text, Spacer, Box, Palette)
from sciviz.examples.ml import LoRA

# (a) decomposition
decomp = Column(
    Math(r"$\Delta W = \frac{\alpha}{r}\, B A$"),
    Spacer(0, 6),
    LoRA(d=10, r=2, seed=4),
    Caption("d=10, r=2 -> 40 trainable params instead of 100"),
    gap="sm", align="center",
)

# (b) parameter budget (auto-coloured by row)
budget = BarChart([
    ("Full fine-tune (d^2)", 1.000, "1,048,576"),
    ("LoRA r=16",            0.031,    "32,768"),
    ("LoRA r=8",             0.016,    "16,384"),
    ("LoRA r=4",             0.008,     "8,192"),
], bar_width=200, bar_height=10,
   highlight_first=True)

# (c) runtime: frozen base + trainable adapter
runtime = Column(
    NNLayer("input x", kind="input",  width=150, height=28),
    Connector(direction="down", length=14),
    Row(
        NNLayer("W_0 (frozen)", kind="residual",
                shape="no gradient", width=150, height=44, dashed=True),
        Spacer(28, 0),
        NNLayer("B . A", kind="conv",
                shape="trainable", width=110, height=44),
        gap="none", align="center",
    ),
    Connector("sum", direction="down", length=18),
    NNLayer("output y", kind="output", width=150, height=28),
    gap="xs", align="center",
)

d = Diagram(
    title="LoRA: low-rank adaptation",
    subtitle="freeze W_0, train two small matrices B and A, merge at deploy time",
    body=Row(
        Panel("a", "Decomposition",            decomp),
        Panel("b", "Parameters for d = 1024",  budget),
        Panel("c", "Runtime path",             runtime),
        gap="md", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "lora_adaptation")
print("Rendered:", d.measure())
