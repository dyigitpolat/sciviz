"""MLP with In-Place Test-Time Training (TTT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Box, Text, TextBlock, Badge, Arrow,
                    Connector, BlockGroup, Anchor, Flow, Flowed, Region,
                    VectorTiles, Palette)

# -- paper-faithful identity colours -----------------------------------------

EMB  = Palette.literal("#f1ead0")
ACT  = Palette.literal("#e9b88f")
OUT  = Palette.literal("#cee0f0")
PROJ = Palette.literal("#3f6469")
ATTN = Palette.literal("#a83b3b")
GLL  = Palette.literal("#5a6b78")
W    = Palette.literal("#c0c8d0")

W_WIDTH = 62   # identical width for every W_down block

def add():   return Badge("+", bordered=True)
def chunk(): return VectorTiles(3, color=ACT)
def wdown(label):
    return Box(label, fill=W, width=W_WIDTH)

# -- sidebar + input ---------------------------------------------------------

generating = Column(
    Text("Generating Direction", rotate=-90, color=Palette.alert, weight="700"),
    Arrow(direction="down", length=140, color=Palette.alert),
)
input_section = Column(
    TextBlock("Input\nEmbedding", weight="700", align="center"),
    Anchor("inp", VectorTiles(9, color=EMB)),
)

# -- Attention residual block ------------------------------------------------

attention_block = Flowed(
    BlockGroup(Row(
        Anchor("attn_in", VectorTiles(9, color=EMB)),
        Box("Attention", vertical_text=True, fill=ATTN),
        Anchor("attn_plus", add()),
    )),
    flows=[Flow("attn_in", "attn_plus", src_side="top", dst_side="top")],
)

# -- chunks and W_downs: three rows, all W's identical width ----------------

chunks_rows = Column(
    Row(Anchor("chunk_im1", chunk()),
        Anchor("wdown_im1", wdown("W\u2193\u207d\u2071\u207b\u00b9\u207e"))),
    Row(Anchor("chunk_i", chunk()),
        Region(Row(Anchor("wdown_i",   wdown("W\u2193\u207d\u2071\u207e")),
                   Anchor("apply_out", VectorTiles(2, color=OUT))),
               label="Apply")),
    Row(Anchor("chunk_ip1", chunk()),
        Anchor("wdown_ip1", wdown("W\u2193\u207d\u2071\u207a\u00b9\u207e"))),
    align="start",
)

# -- Update region -----------------------------------------------------------

update_stack = Region(
    Row(
        Anchor("yvec", VectorTiles(7, color=EMB)),
        Column(
            Anchor("loss", Box("\u2112(O,V)",             fill=W)),
            Anchor("dW",   Box("\u0394W\u207d\u2071\u207e", fill=W)),
            Anchor("teal", VectorTiles(3, color=PROJ)),
            Anchor("conv", Box("Conv1D & Projection",
                                fill=Palette.alert.soft())),
        ),
    ),
    label="Update",
)

# -- MLP block ---------------------------------------------------------------

mlp_block = Flowed(
    BlockGroup(Row(
        Anchor("mlp_entry", Box("Gated Linear Layer", vertical_text=True, fill=GLL)),
        Anchor("mlp_in", VectorTiles(15, color=ACT)),
        TextBlock("Split into\nchunks", color="muted", align="center"),
        chunks_rows,
        update_stack,
        Anchor("mlp_plus", add()),
    ), label="MLP with In-Place TTT", label_size="title", label_align="end"),
    flows=[
        # residual skips from BEFORE GLL, over the top, to the final +
        Flow("mlp_entry", "mlp_plus", src_side="top", dst_side="top"),
        # Split: mlp_in (activation vector) fans out to the three chunks
        Flow("mlp_in", "chunk_im1", src_side="right", dst_side="left"),
        Flow("mlp_in", "chunk_i",   src_side="right", dst_side="left"),
        Flow("mlp_in", "chunk_ip1", src_side="right", dst_side="left"),
        # Each chunk -> its W_down
        Flow("chunk_im1", "wdown_im1", src_side="right", dst_side="left"),
        Flow("chunk_i",   "wdown_i",   src_side="right", dst_side="left"),
        Flow("chunk_ip1", "wdown_ip1", src_side="right", dst_side="left"),
        # Apply output -> Update input
        Flow("apply_out", "yvec", src_side="right", dst_side="left"),
        # loop-back: delta W -> W_down(i)
        Flow("dW", "wdown_i", src_side="left", dst_side="right"),
        # Update internals
        Flow("yvec", "loss", src_side="right", dst_side="left"),
        Flow("loss", "dW",   src_side="bottom", dst_side="top",   curvature=0),
        Flow("conv", "teal", src_side="top",    dst_side="bottom", curvature=0),
        Flow("teal", "dW",   src_side="top",    dst_side="bottom", curvature=0),
        # Vertical dashed control flow through W_down column
        Flow("wdown_im1", "wdown_i",  src_side="bottom", dst_side="top",
             dashed=True, arrow=False, curvature=0),
        Flow("wdown_i",   "wdown_ip1", src_side="bottom", dst_side="top",
             dashed=True, arrow=False, curvature=0),
    ],
)

# -- outer Flowed for the long cross-diagram residual ------------------------

d = Diagram(
    title="MLP with In-Place Test-Time Training (TTT)",
    subtitle=("each chunk of post-GLL activations goes through its own "
              "W_down; the Update branch computes a delta from the per-chunk loss"),
    body=Flowed(
        Row(generating, input_section,
            Connector(direction="right"),
            attention_block,
            mlp_block,
            Connector(direction="right")),
        flows=[
            Flow("inp", "mlp_plus",
                 src_side="bottom", dst_side="bottom",
                 color=Palette.muted, detour=34),
        ],
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "ttt_mlp")
print("Rendered:", d.measure())
