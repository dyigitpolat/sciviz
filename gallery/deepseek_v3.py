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
                    Grid, Framed, Labeled, Palette, StackedBoxes)
from sciviz.math import Math

# -- paper-faithful identity colours ----------------------------------------
PROC   = Palette.literal("#fbe5a8")
SHARED = Palette.literal("#c1e1c1")
TOKEN_BG = Palette.literal("#ececec")

# -- atoms -------------------------------------------------------------------
def toks(*ts):
    """Token row with light-gray rounded container."""
    return Framed(
        Row(*[Text(t, size="tiny", italic=True) for t in ts]),
        bg=TOKEN_BG, border=TOKEN_BG, padding="xs",
    )

def proc(label, sub=None):
    return Box(label, fill=PROC, text_size="small", sub_label=sub, sub_color="muted")

def shared(label, sub=None):
    return Box(label, fill=SHARED, text_size="small", sub_label=sub, sub_color="muted")

def loss_math(name, sup=None):
    """LaTeX loss symbol: L_Main or L_MTP^k (no author-side arrow glyph)."""
    if sup is None:
        latex = rf"\mathcal{{L}}_{{\text{{{name}}}}}"
    else:
        latex = rf"\mathcal{{L}}_{{\text{{{name}}}}}^{{{sup}}}"
    return Math(latex, size="label")

# ---------------------------------------------------------------------------
# TOP STRIP: Main Model + 3 MTP Modules as aligned parallel columns
# ---------------------------------------------------------------------------

ROW_ORDER = ["target", "ce", "out", "tf", "proj", "rms", "emb", "input"]

def main_column():
    return {
        "_panel": "Main Model\n(Next Token Prediction)",
        "target": toks("t\u2082", "t\u2083", "t\u2084", "t\u2085"),
        "ce":     Labeled(Anchor("main_ce", proc("Cross-Entropy Loss", sub="FP32")),
                          loss_math("Main")),
        "out":    Anchor("main_out", shared("Output Head", sub="BF16")),
        ("tf", "proj", "rms"):
                  Anchor("main_tf",  StackedBoxes(4, "Transformer Block \u00d7 L",
                                                   fill=PROC)),
        "emb":    Anchor("main_emb", shared("Embedding Layer", sub="BF16")),
        "input":  toks("t\u2081", "t\u2082", "t\u2083", "t\u2084"),
    }

def mtp_column(k, input_toks, target_toks):
    panel_label = f"MTP Module {k}\n(Next\u207f Token Prediction)".replace(
        "\u207f", {1: "\u00b2", 2: "\u00b3", 3: "\u2074"}[k])
    return {
        "_panel": panel_label,
        "target": toks(*target_toks),
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
        "input":  toks(*input_toks),
    }

top_strip = Flowed(
    Grid(
        rows=ROW_ORDER,
        row_labels={"target": "Target Tokens", "input": "Input Tokens"},
        columns=[
            main_column(),
            mtp_column(1, ("t\u2082","t\u2083","t\u2084","t\u2085"),
                          ("t\u2083","t\u2084","t\u2085","t\u2086")),
            mtp_column(2, ("t\u2083","t\u2084","t\u2085","t\u2086"),
                          ("t\u2084","t\u2085","t\u2086","t\u2087")),
            mtp_column(3, ("t\u2084","t\u2085","t\u2086","t\u2087"),
                          ("t\u2085","t\u2086","t\u2087","t\u2088")),
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
    ],
)

# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------

d = Diagram(
    title="DeepSeek-V3 architecture  (top strip)",
    subtitle="Main Model + MTP modules with shared Embedding and Output Head",
    body=top_strip,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "deepseek_v3")
print("Rendered:", d.measure())
