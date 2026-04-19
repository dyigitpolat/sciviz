"""MLP with In-Place Test-Time Training (TTT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Box, Text, TextBlock, Badge, Arrow,
                    Connector, BlockGroup, Anchor, Flow, Flowed, Region,
                    VectorTiles, Palette, Math, Bus)

# -- paper-faithful identity colours -----------------------------------------
#
# Registered once as named Palette entries so every subsequent reference
# (``Palette.emb``, ``Palette.w``, ...) resolves through the usual theme
# pipeline -- including ``.soft()`` / ``.dark()`` modifiers where needed.

EMB  = Palette.register("emb",  "#f1ead0")
ACT  = Palette.register("act",  "#e9b88f")
OUT  = Palette.register("out",  "#9fbedd")   # saturated paper blue (Apply output tile)
PROJ = Palette.register("proj", "#2f4a66")   # dark slate (Conv output array)
ATTN = Palette.register("attn", "#a83b3b")
GLL  = Palette.register("gll",  "#5a6b78")
W    = Palette.register("wblk", "#c0c8d0")

W_WIDTH = 62   # identical width for every W_down block

def add():   return Badge("+", bordered=True)
def chunk(): return VectorTiles(3, color=ACT)
def wdown(latex):
    return Box(Math(latex), fill=W, width=W_WIDTH)

# -- sidebar + input ---------------------------------------------------------

generating = Column(
    Text("Generating Direction", rotate=-90, weight="700"),
    Arrow(direction="down", length=140, color=Palette.alert),
)

# -- Attention residual block (owns the single input embedding) --------------
#
# The input embedding is *the* attention input -- we don't duplicate it as
# a separate tile stack outside the block.  The "Input Embedding" label is
# placed as a small header above the stack via ``TextBlock`` so it reads as
# part of the attention column without pulling the tiles outside the dashed
# region.

attention_block = Flowed(
    BlockGroup(Row(
        Column(
            TextBlock("Input\nEmbedding", weight="700", align="center"),
            Anchor("inp", VectorTiles(9, color=EMB)),
        ),
        Box("Attention", vertical_text=True, fill=ATTN),
        Anchor("attn_plus", add()),
    )),
    flows=[Flow("inp", "attn_plus", src_side="top", dst_side="top")],
)

# -- chunks and W_downs: three rows, all W's identical width ----------------

chunks_rows = Column(
    Row(Anchor("chunk_im1", chunk()),
        Anchor("wdown_im1", wdown(r"W_{\text{down}}^{(i-1)}"))),
    Row(Anchor("chunk_i", chunk()),
        Region(Row(Anchor("wdown_i",   wdown(r"W_{\text{down}}^{(i)}")),
                   Anchor("apply_out", VectorTiles(2, color=OUT))),
               label="Apply")),
    Row(Anchor("chunk_ip1", chunk()),
        Anchor("wdown_ip1", wdown(r"W_{\text{down}}^{(i+1)}"))),
    align="start",
)

# -- Update region -----------------------------------------------------------

update_stack = Region(
    Row(
        Anchor("yvec", VectorTiles(7, color=EMB)),
        Column(
            Anchor("loss", Box(Math(r"\mathcal{L}(O_{[i]}, V_{[i]})"), fill=W)),
            Anchor("dW",   Box(Math(r"\Delta W^{(i)}"),                 fill=W)),
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
        Anchor("mlp_entry", Box("Gated Linear\nLayer", vertical_text=True, fill=GLL)),
        Anchor("mlp_in", VectorTiles(15, color=ACT)),
        chunks_rows,
        update_stack,
        Anchor("mlp_plus", add()),
    ), label="MLP with In-Place TTT", label_size="title", label_align="end"),
    flows=[
        # residual skip over the top: GLL output -> final +
        Flow("mlp_entry", "mlp_plus", src_side="top", dst_side="top"),
        # mlp_in (activation vector) fans out to every chunk on a single
        # labelled bus -- the shared spine reads as "split into chunks"
        # once instead of repeating the label on each tap.
        Bus(sources="mlp_in",
            sinks=["chunk_im1", "chunk_i", "chunk_ip1"],
            label="Split into chunks",
            color="ink",
            orientation="horizontal"),
        # Each chunk -> its W_down
        Flow("chunk_im1", "wdown_im1"),
        Flow("chunk_i",   "wdown_i"),
        Flow("chunk_ip1", "wdown_ip1"),
        # Apply output -> Update input
        Flow("apply_out", "yvec"),
        # Update internals: yvec -> loss, loss -> dW, teal -> loss
        Flow("yvec", "loss"),
        Flow("loss", "dW",   src_side="bottom", dst_side="top"),
        Flow("conv", "teal", src_side="top",    dst_side="bottom"),
        Flow("teal", "loss", src_side="top",    dst_side="bottom"),
        # Feedback: dW -> wdown_i (routes around the Region boundary)
        Flow("dW", "wdown_i", src_side="left", dst_side="right"),
        # Vertical dashed control flow through the W_down column
        Flow("wdown_im1", "wdown_i",
             src_side="bottom", dst_side="top", dashed=True, arrow=False),
        Flow("wdown_i",   "wdown_ip1",
             src_side="bottom", dst_side="top", dashed=True, arrow=False),
    ],
)

# -- outer Flowed for the long cross-diagram residual ------------------------

d = Diagram(
    title="MLP with In-Place Test-Time Training (TTT)",
    subtitle=("each chunk of post-GLL activations goes through its own "
              "W_down; the Update branch computes a delta from the per-chunk loss"),
    body=Flowed(
        Row(generating,
            attention_block,
            mlp_block,
            Connector(direction="right")),
        flows=[
            Flow("inp", "mlp_plus",
                 src_side="bottom", dst_side="bottom",
                 color=Palette.muted),
        ],
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "ttt_mlp")
print("Rendered:", d.measure())
