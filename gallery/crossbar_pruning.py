"""Row- and column-pruning on an analog crossbar.

Refactored to use the generic ``MeshArray`` primitive (grid + peripheral
row/column) instead of a specialized Crossbar element.  Pruning is
expressed by passing ``None`` peripherals at the pruned indices.
"""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, MeshArray, Box, Connector,
                    Math, Caption, Section, Text, Matrix)

# Sparse weight matrix: rows {1,5} and cols {2,6} are zeroed.
rng = random.Random(1)
N = 8
W = [[abs(rng.gauss(0, 0.6)) for _ in range(N)] for _ in range(N)]
PR, PC = [1, 5], [2, 6]
for i in PR: W[i] = [0.0] * N
for r in W:
    for j in PC: r[j] = 0.0

# Helper: small DAC and ADC blocks
def dac(active=True):
    return Box(label="DAC", width=30, height=14,
               fill="#dbe3f1" if active else "#e5e7eb",
               stroke="#3b5fa0" if active else "#9ca3af",
               text_color="text" if active else "muted",
               text_size="tiny", text_weight="700", radius=2)
def adc(active=True):
    return Box(label="ADC", width=18, height=24,
               fill="#c7e5df" if active else "#e5e7eb",
               stroke="#2d7a70" if active else "#9ca3af",
               text_color="text" if active else "muted",
               text_size="tiny", text_weight="700", radius=2)

# Panel (a): the matrix with pruned rows / columns highlighted
mat_panel = Matrix(W, cell_size="md",
                   highlight_rows=PR, highlight_cols=PC,
                   caption=f"rows {PR}, cols {PC} pruned")

# Panel (b): full crossbar (all peripherals active)
xbar_full = MeshArray(
    shape=(N, N), cell=22, cell_data=W, palette="blues",
    cell_padding=4,
    left=[dac(True) for _ in range(N)],
    bottom=[adc(True) for _ in range(N)],
)

# Panel (c): pruned crossbar (DACs/ADCs at pruned indices are gated off)
xbar_pruned = MeshArray(
    shape=(N, N), cell=22, cell_data=W, palette="blues",
    cell_padding=4,
    left=[dac(i not in PR) for i in range(N)],
    bottom=[adc(j not in PC) for j in range(N)],
)

mvm_caption = Math(r"$y = W x \ \Rightarrow\ I_j = \sum_i G_{ij} \cdot V_i$")

d = Diagram(
    title="Row- and column-pruning maps to crossbar peripheral savings",
    subtitle="zero rows -> gate off DACs;  zero columns -> remove ADCs (largest energy win)",
    body=Row(
        Panel("a", "Weight matrix", mat_panel),
        Connector("map to", direction="right"),
        Panel("b", "Full crossbar",
              Column(xbar_full, mvm_caption, gap="md", align="center")),
        Connector("gate off pruned", direction="right"),
        Panel("c", "After pruning", xbar_pruned),
        gap="md", align="center",
    ),
    footer=Row(
        Section("Unstructured pruning",
                Text("Weights zeroed individually; needs a compression "
                     "engine to skip zeros at runtime.",
                     size="small", color="muted")),
        Section("Row pruning",
                Text("Whole rows zero -> input DACs and word-line drivers "
                     "gated off.", size="small", color="muted")),
        Section("Column pruning",
                Text("Whole columns zero -> ADCs and S&H removed; the "
                     "largest per-output energy win.",
                     size="small", color="muted")),
        gap="lg", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "crossbar_pruning")
print("Rendered:", d.measure())
