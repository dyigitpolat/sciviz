"""DeepSeek-V3 architecture.

Purely declarative: rows, cells, connections.  No widths, heights, gaps,
curvatures, spacers, or per-step arrow declarations.  The library figures
out layout, vertical flow arrows, orthogonal inter-module branches, and
shared-parameter buses.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Box, Text, Anchor, Flow, Flowed, Bus,
                    Grid, Labeled, StackedBoxes, TokenRow)
from sciviz.math import Math


def proc(label, sub=None):
    return Box(label, fill="accent_proc", text_size="small",
               sub_label=sub, sub_color="muted_label")

def shared(label, sub=None):
    return Box(label, fill="accent_shared", text_size="small",
               sub_label=sub, sub_color="muted_label")

def loss_math(name, sup=None):
    """LaTeX loss symbol: L_Main or L_MTP^k (no author-side arrow glyph)."""
    if sup is None:
        latex = rf"\mathcal{{L}}_{{\text{{{name}}}}}"
    else:
        latex = rf"\mathcal{{L}}_{{\text{{{name}}}}}^{{{sup}}}"
    return Math(latex)


ROW_ORDER = ["target", "ce", "out", "tf", "proj", "rms", "emb", "input"]

def main_column():
    return {
        "_panel": "Main Model\n(Next Token Prediction)",
        "target": TokenRow(2, 3, 4, 5),
        "ce":     Labeled(Anchor("main_ce", proc("Cross-Entropy Loss", sub="FP32")),
                          loss_math("Main")),
        "out":    Anchor("main_out", shared("Output Head", sub="BF16")),
        ("tf", "proj", "rms"):
                  Anchor("main_tf",  StackedBoxes(4, "Transformer Block \u00d7 L",
                                                   fill="accent_proc")),
        "emb":    Anchor("main_emb", shared("Embedding Layer", sub="BF16")),
        "input":  TokenRow(1, 2, 3, 4),
    }

def mtp_column(k, input_indices, target_indices):
    panel_label = f"MTP Module {k}\n(Next\u207f Token Prediction)".replace(
        "\u207f", {1: "\u00b2", 2: "\u00b3", 3: "\u2074"}[k])
    return {
        "_panel": panel_label,
        "target": TokenRow(*target_indices),
        "ce":     Labeled(Anchor(f"mtp{k}_ce", proc("Cross-Entropy Loss", sub="FP32")),
                          loss_math("MTP", sup=str(k))),
        "out":    Anchor(f"mtp{k}_out",  shared("Output Head", sub="BF16")),
        "tf":     Anchor(f"mtp{k}_tf",   proc("Transformer Block",
                                               sub="FP8 Mixed Precision")),
        "proj":   Anchor(f"mtp{k}_proj", proc("Linear Projection", sub="BF16")),
        # The "concatenation" label is drawn by the Bus itself (beside the
        # sink-arrow).  The row stays empty so the concat line floats in
        # the gap between the RMSNorms and the Linear Projection.
        "rms":    Row(Anchor(f"mtp{k}_rn_l", proc("RMSNorm", sub="FP32")),
                      Anchor(f"mtp{k}_rn_r", proc("RMSNorm", sub="FP32"))),
        "emb":    Anchor(f"mtp{k}_emb",  shared("Embedding Layer", sub="BF16")),
        "input":  TokenRow(*input_indices),
    }

top_strip = Flowed(
    Grid(
        rows=ROW_ORDER,
        row_labels={"target": "Target Tokens", "input": "Input Tokens"},
        columns=[
            main_column(),
            mtp_column(1, (2, 3, 4, 5), (3, 4, 5, 6)),
            mtp_column(2, (3, 4, 5, 6), (4, 5, 6, 7)),
            mtp_column(3, (4, 5, 6, 7), (5, 6, 7, 8)),
        ],
        trailer=Text("\u2026", size="2xl", color="muted", weight="700"),
        column_flow="up",
        # Skip the auto-arrow INTO "proj" -- we replace it with an explicit
        # Y-merge (two RMSNorms -> one Linear Projection) below.
        column_flow_skip_before=["proj"],
    ),
    flows=[
        # Shared-parameter buses: single source, multiple sinks on same row.
        Bus(sources="main_out",
            sinks=["mtp1_out", "mtp2_out", "mtp3_out"],
            label="Shared", dashed=True, arrow=False),
        Bus(sources="main_emb",
            sinks=["mtp1_emb", "mtp2_emb", "mtp3_emb"],
            label="Shared", dashed=True, arrow=False),
        # Concatenation merge: both RMSNorms fan into Linear Projection.
        *[Bus(sources=[f"mtp{k}_rn_l", f"mtp{k}_rn_r"],
              sinks=f"mtp{k}_proj", label="concatenation", color="text")
          for k in (1, 2, 3)],
        # Cascading inter-module flows: the previous module's transformer
        # output feeds the next module's LEFT RMSNorm from below, merging
        # with the embedding-layer signal already travelling up into it.
        Flow("main_tf",  "mtp1_rn_l", src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
        Flow("mtp1_tf",  "mtp2_rn_l", src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
        Flow("mtp2_tf",  "mtp3_rn_l", src_side="top", dst_side="bottom",
             style="orthogonal", color="text"),
        # Embedding-layer signal feeds the RIGHT RMSNorm in each MTP
        # module (the LEFT one is already driven by the cascading
        # inter-module flow above).  Column-flow can't pick between
        # two siblings automatically, so we name the destination here.
        *[Flow(f"mtp{k}_emb", f"mtp{k}_rn_r",
               src_side="top", dst_side="bottom",
               style="orthogonal", color="text")
          for k in (1, 2, 3)],
    ],
)


d = Diagram(
    title="DeepSeek-V3 architecture  (top strip)",
    subtitle="Main Model + MTP modules with shared Embedding and Output Head",
    body=top_strip,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "deepseek_v3")
print("Rendered:", d.measure())
