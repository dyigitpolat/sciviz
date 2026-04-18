"""Scaled-dot-product attention and its place in a Transformer block.

Two panels: (a) the QK-V pipeline inside one head; (b) how the head sits
inside a standard Transformer block.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, Connector, NNLayer,
                    Tensor, Math, Section, Text)
from sciviz.examples.ml import AttentionHead

# Panel (a): anatomy of a single attention head
head = AttentionHead(seq_len=6, d_k=4, mask="causal", weights_seed=3)

# Panel (b): full Transformer block with tensor-shape annotations
B, L, D, H = 32, 128, 512, 8
block = Column(
    Tensor((B, L, D), labels=("B", "L", "D"), title="x (input)"),
    Connector("LayerNorm", direction="down", length=20),
    NNLayer("Multi-Head Attention", kind="attn",
            shape=f"{H} heads, d_k = {D//H}", width=220, height=52),
    Connector("residual +", direction="down", length=20),
    NNLayer("LayerNorm", kind="norm", width=220, height=34),
    Connector(direction="down", length=16),
    NNLayer("MLP (GELU)", kind="dense",
            shape=f"{D} -> {4*D} -> {D}", width=220, height=52),
    Connector("residual +", direction="down", length=20),
    Tensor((B, L, D), labels=("B", "L", "D"), title="x (output)"),
    gap="xs", align="center",
)

formula = Section(
    "Per-head computation",
    Math(r"$\mathrm{Attention}(Q, K, V) = "
         r"\mathrm{softmax}\!\left(\frac{QK^\top}{\sqrt{d_k}}\right) V$"),
    caption="d_k = D / H = 64; causal mask drops upper triangle of QK^T",
)

d = Diagram(
    title="Scaled-dot-product attention in a Transformer block",
    subtitle="per-head matmul pipeline (left) composed into a full block (right)",
    body=Row(
        Panel("a", "Inside one attention head", head),
        Column(
            Panel("b", "Transformer block", block),
            formula,
            gap="lg", align="center",
        ),
        gap="md", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "transformer_attention")
print("Rendered:", d.measure())
