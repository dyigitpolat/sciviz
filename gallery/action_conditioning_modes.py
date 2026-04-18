"""Four ways to inject actions into a video-diffusion backbone.

A two-tier figure: top row of architecture variants, bottom comparison
table.  Author code touches *content* only -- no manual coordinates,
text colours, alignment widths, or brace spans.

Demonstrates the design-cleanup primitives:
  * Anchor/Flow/Flowed   -- curved arrows by name, no pixel maths
  * MatchSize            -- equalise heights / widths automatically
  * Group                -- row of children with auto-braced label
  * Box(text_color="auto") -- contrast-correct labels by default
  * BlockGroup(fill=...)   -- tinted grouping panels
  * Box(vertical_text=True) -- rotated labels in narrow tall blocks
  * Badge                  -- numbered markers AND inline operators
  * Palette.alert/info/warn/success -- panels match table rows
"""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Box, Heatmap, Text, Caption,
                    Badge, Brace, Group, Anchor, Flow, Flowed, MatchSize,
                    BlockGroup, MeshArray, Palette, Spacer, Table, TextBlock)


# Mode -> colour: same hue used for the panel header AND its table row.
COLORS = {
    "external":   Palette.alert,
    "contextual": Palette.info,
    "residual":   Palette.warn,
    "internal":   Palette.success,
}

# ---------------------------------------------------------------------------
# Reusable building blocks
# ---------------------------------------------------------------------------

def encoder(label, role):
    """Encoder block.  Width sized to label; height left unset so MatchSize
    can equalise it across siblings."""
    return Box(label, fill=role.soft(), stroke=role.dark(),
               text_size="small", text_weight="700", radius=6,
               width=58, height=58)        # height bumped by MatchSize later

def attn_block(label, accent=False):
    fill = Palette.info.soft().dark() if accent else Palette.info.soft()
    stroke = Palette.info.dark() if accent else Palette.info
    return Box(label, vertical_text=True, fill=fill, stroke=stroke,
               text_size="small", text_weight="700", radius=4,
               width=30, height=92)

def diffusion_transformer(*, accent: int, plus_anchor=None):
    """Diffusion Transformer block group (Self-Attn | Cross-Attn | FFN),
    with optional + badge after FFN tagged with ``plus_anchor`` so a Flow
    can route into it."""
    sub = [
        attn_block("Self-Attention",  accent == 0),
        attn_block("Cross-Attention", accent == 1),
        attn_block("FFN",             accent == 2),
    ]
    if plus_anchor:
        plus = Anchor(plus_anchor,
                      Badge("+", color=Palette.gray.soft(), size=20, bordered=True))
        inner = Row(*sub, Spacer(2, 0), plus, gap="sm", align="center")
    else:
        inner = Row(*sub, gap="sm", align="center")
    return BlockGroup(inner, label="Diffusion Transformer",
                      color=Palette.muted, fill=Palette.success.soft(),
                      dashed=False, padding="md", label_align="center")

def loop_marker():
    return Row(
        Badge("\u21bb", color=Palette.info, size=20, text_size="small"),
        Spacer(2, 0),
        Text("\u00d7 N", size="small", color="muted", weight="700"),
        gap="none", align="center",
    )

# ---------------------------------------------------------------------------
# Panel 1 -- external: action conditions the VAE input
# ---------------------------------------------------------------------------

panel_external = Flowed(
    child=Column(
        Row(Anchor("vae_plus", encoder("VAE\nEncoder", Palette.alert)),
            Spacer(2, 0),
            Anchor("vae_op",
                   Badge("+", color=Palette.gray.soft(), size=20, bordered=True)),
            gap="none", align="center"),
        Spacer(0, 28),
        Anchor("ae1", encoder("Action\nEncoder", Palette.success)),
        gap="none", align="end",
    ),
    flows=[Flow("ae1", "vae_op",
                src_side="top", dst_side="bottom",
                color=Palette.warn.dark(), curvature=0.4)],
)

# ---------------------------------------------------------------------------
# Panel 2 -- contextual: visual + action tokens concatenated
# ---------------------------------------------------------------------------

rng = random.Random(7)

def cell_renderer(i, j):
    if j == 4:
        return None
    if rng.random() < 0.30:
        return None
    role = Palette.violet if j < 4 else Palette.success
    return Box(width=8, height=8, fill=role.soft(), stroke=role, radius=1)

token_grid = MeshArray(shape=(6, 10), cell=11,
                       cell_renderer=cell_renderer, show_lines=False)

def chip(role):
    # Auto text contrast handles the label colour
    return Box(width=26, height=20, fill=role.soft(), stroke=role,
               text_size="tiny", text_weight="700", radius=2)

# Group(label, *children) auto-braces underneath -- no manual span calc
visual_group = Group("Visual Tokens", chip(Palette.warn), chip(Palette.warn))
action_group = Group("Action Tokens", chip(Palette.success), chip(Palette.success))
concat_op    = Badge("c", color=Palette.gray.soft(), size=20, bordered=True)

panel_contextual = Column(
    token_grid,
    Spacer(0, 6),
    Row(visual_group, Spacer(8, 0), concat_op, Spacer(8, 0), action_group,
        gap="none", align="start"),
    gap="none", align="center",
)

# ---------------------------------------------------------------------------
# Panel 3 -- residual: action delta added at FFN output
# ---------------------------------------------------------------------------

panel_residual = Flowed(
    child=BlockGroup(
        MatchSize(           # auto-equalises heights of these three
            Anchor("ae3", encoder("Action\nEncoder", Palette.success)),
            diffusion_transformer(accent=2, plus_anchor="dt3_plus"),
            loop_marker(),
            arrange="row", gap="md", align="center",
        ),
        color=Palette.warn.dark(), fill=Palette.warn.soft(),
        dashed=False, padding="md",
    ),
    flows=[Flow("ae3", "dt3_plus",
                src_side="bottom", dst_side="bottom",
                color=Palette.warn.dark(), curvature=0.4, detour=14)],
)

# ---------------------------------------------------------------------------
# Panel 4 -- internal: action enters the cross-attention block
# ---------------------------------------------------------------------------

# Add an anchor on the Cross-Attn block by inlining attn_block with Anchor
def attn_block_anchored(label, name, accent=False):
    return Anchor(name, attn_block(label, accent=accent))

def diffusion_transformer_with_anchor(*, accent, anchor_at):
    sub = [attn_block("Self-Attention",  accent == 0),
           attn_block("Cross-Attention", accent == 1),
           attn_block("FFN",             accent == 2)]
    sub[anchor_at] = Anchor("dt4_target", sub[anchor_at])
    inner = Row(*sub, gap="sm", align="center")
    return BlockGroup(inner, label="Diffusion Transformer",
                      color=Palette.muted, fill=Palette.success.soft(),
                      dashed=False, padding="md", label_align="center")

panel_internal = Flowed(
    child=BlockGroup(
        MatchSize(
            Anchor("ae4", encoder("Action\nEncoder", Palette.success)),
            diffusion_transformer_with_anchor(accent=1, anchor_at=1),
            loop_marker(),
            arrange="row", gap="md", align="center",
        ),
        color=Palette.warn.dark(), fill=Palette.warn.soft(),
        dashed=False, padding="md",
    ),
    flows=[Flow("ae4", "dt4_target",
                src_side="bottom", dst_side="bottom",
                color=Palette.warn.dark(), curvature=0.4, detour=14)],
)

# ---------------------------------------------------------------------------
# Top row: panels with numbered headers
# ---------------------------------------------------------------------------

def headed_panel(num, role, body):
    return Column(
        Badge(num, color=role, size=24, text_size="small"),
        Spacer(0, 6),
        body,
        gap="none", align="center",
    )

top_row = Row(
    headed_panel("1", COLORS["external"],   panel_external),
    headed_panel("2", COLORS["contextual"], panel_contextual),
    headed_panel("3", COLORS["residual"],   panel_residual),
    headed_panel("4", COLORS["internal"],   panel_internal),
    gap="lg", align="start",
)

# ---------------------------------------------------------------------------
# Bottom: comparison table
# ---------------------------------------------------------------------------

def mode_cell(num, role, name):
    return Row(
        Badge(num, color=role, size=18, text_size="tiny"),
        Spacer(8, 0),
        Text(name, size="small", weight="700", font="mono"),
        gap="none", align="center",
    )

table = Table(
    [
        [Text("Mode",            size="small", weight="700"),
         Text("Injection point", size="small", weight="700"),
         Text("Notes",           size="small", weight="700")],
        [mode_cell("1", COLORS["external"],   "external"),
         Text("Conditioned VAE input", size="small", color="muted"),
         TextBlock("Actions injected as an external conditioning stream that "
                   "modulates the backbone without sharing the main token sequence.",
                   size="small", color="muted", max_width=380)],
        [mode_cell("2", COLORS["contextual"], "contextual"),
         Text("Concat frames, actions", size="small", color="muted"),
         TextBlock("Video and action tokens share one sequence with a "
                   "lag-aware temporal attention mask, enabling mid-level fusion.",
                   size="small", color="muted", max_width=380)],
        [mode_cell("3", COLORS["residual"],   "residual"),
         Text("Hidden state with action delta", size="small", color="muted"),
         TextBlock("Actions added through residual-style modulation branches; "
                   "a strong but more indirect baseline.",
                   size="small", color="muted", max_width=380)],
        [mode_cell("4", COLORS["internal"],   "internal"),
         Text("After cross-attn, before FFN", size="small", color="muted"),
         TextBlock("Actions enter through dedicated cross-attention inside the "
                   "transformer blocks, fusing near the backbone core.",
                   size="small", color="muted", max_width=380)],
    ],
    col_align=("start", "start", "start"),
    gap_y="md", gap_x="xl",
    header_rule=True,
)

d = Diagram(
    title="Action conditioning in video diffusion: four injection modes",
    subtitle=("where to fuse the action stream into the diffusion backbone "
              "-- input, sequence, residual, or attention"),
    body=Column(top_row, Spacer(0, 18), table, gap="lg", align="start"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "action_conditioning_modes")
print("Rendered:", d.measure())
