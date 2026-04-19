"""Fig 01 - Perception Encoder (PE) multi-headed architecture.

Reproduces [`gallery/reference/fig01.png`](reference/fig01.png) -- the
PE figure: two raw modalities (image/video) feed a contrastive "PE Core"
backbone, which emits four pretraining outputs; an alignment-tuning
bridge (\u00a73) branches the shared backbone into a language encoder
(\u00a74) and a spatial encoder (\u00a75), each with four downstream tasks.

Demonstrates:

* icon-decorated tiles via :class:`Box` + :class:`Icon`,
* three-way semantic palette (teal core / blue language / purple spatial),
* :class:`Anchor` + :class:`Connect` for the image/video bus into the
  PE Core and the diverging alignment-tuning branches,
* a compact helper vocabulary keeps the figure description under 200
  lines of mostly-declarative code.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Anchor,
    Box,
    Column,
    Connect,
    Diagram,
    Icon,
    Row,
    Spacer,
    Text,
)


# ---------------------------------------------------------------------------
# Palette -- three semantic families used by the figure.
# ---------------------------------------------------------------------------

CORE_STROKE     = "#234d46"     # teal, "PE Core"
CORE_FILL       = "#e9f0ee"
LANG_STROKE     = "#3b5fa0"     # blue, "PE Language"
LANG_FILL       = "#dbe3f1"
SPAT_STROKE     = "#6d28d9"     # purple, "PE Spatial"
SPAT_FILL       = "#e4dcf5"
TILE_STROKE     = "#6d5fa0"     # muted purple for the output tiles
TILE_INK        = "#3b2f70"
INPUT_STROKE    = "#94a3b8"
INPUT_FILL      = "#f1f5f9"


# ---------------------------------------------------------------------------
# Small helpers built entirely from public primitives.
# ---------------------------------------------------------------------------

def input_tile(icon_name: str, label: str) -> Box:
    """Dashed grey rounded tile: icon + caption below."""
    return Box(
        Column(
            Icon(icon_name, size=22, color=LANG_STROKE),
            Text(label, size="small", color="muted"),
            gap="xs", align="center",
        ),
        width=82, height=66,
        fill=INPUT_FILL, stroke=INPUT_STROKE, dashed=True,
    )


def output_tile(header: str, glyph, caption: str) -> Column:
    """Purple-outlined output tile with a header label above it.

    ``glyph`` may be an :class:`Icon` or any :class:`Element` (e.g. a bold
    ``Text("#")``) so we can render the paper's hand-drawn glyphs.
    """
    body = Box(
        Column(glyph, Text(caption, size="small", color=TILE_INK),
               gap="xs", align="center"),
        width=86, height=66,
        fill="#f6f4fb", stroke=TILE_STROKE,
    )
    return Column(
        Text(header, size="small", color=TILE_INK, weight="600"),
        body,
        gap="xs", align="center",
    )


PE_PANEL_WIDTH = 130
PE_PANEL_HEIGHT = 110


def pe_panel(subtitle: str, *, stroke: str, fill: str,
             section: str = "") -> Box:
    """The big "PE <subtitle>" rounded panel with an optional `\u00a7N`
    chip tucked into the top-right corner."""
    stack = Column(
        Text("PE", size="title", color=stroke, weight="700"),
        Text(subtitle, size="label", color=stroke, italic=True),
        gap="xs", align="center",
    )
    if section:
        chip = Row(
            Spacer(PE_PANEL_WIDTH - 44, 0),
            Text(section, size="tiny", color=stroke, weight="700"),
            gap="none", align="center",
        )
        stack = Column(chip, stack, gap="xs", align="center")
    return Box(stack, width=PE_PANEL_WIDTH, height=PE_PANEL_HEIGHT,
               fill=fill, stroke=stroke)


def group_header(bold: str, italic: str) -> Column:
    """Bold kicker over an italic subtitle."""
    return Column(
        Text(bold, size="label", weight="700"),
        Text(italic, size="label", italic=True, color="muted"),
        gap="xs", align="start",
    )


# ---------------------------------------------------------------------------
# Glyphs used inside the output tiles ("#", "T", boxes, mask, ...).
# ---------------------------------------------------------------------------

def hash_glyph() -> Text:
    return Text("#", size=22, color=TILE_STROKE, weight="700")


def text_glyph() -> Text:
    return Text("T", size=22, color=TILE_STROKE, weight="700")


def icon_glyph(name: str) -> Icon:
    return Icon(name, size=22, color=TILE_STROKE)


# ---------------------------------------------------------------------------
# Content trees for the three groups.
# ---------------------------------------------------------------------------

inputs_column = Column(
    Anchor("in_image", input_tile("image", "Image")),
    Anchor("in_video", input_tile("video", "Video")),
    gap="md", align="center",
)

pretraining_outputs = Column(
    Row(output_tile("Classify Images",  hash_glyph(),        "Class Idx"),
        output_tile("Retrieve Images",  icon_glyph("image"), "Image"),
        gap="md", align="start"),
    Row(output_tile("Classify Videos",  hash_glyph(),        "Class Idx"),
        output_tile("Retrieve Videos",  icon_glyph("video"), "Video"),
        gap="md", align="start"),
    gap="md", align="start",
)

pretraining_block = Column(
    group_header("Large-Scale", "Contrastive Pretraining"),
    Row(
        Anchor("pe_core",
               pe_panel("Core", stroke=CORE_STROKE, fill=CORE_FILL,
                        section="\u00a72")),
        pretraining_outputs,
        gap="lg", align="center",
    ),
    gap="sm", align="start",
)

# --- alignment-tuning bridge (lock icon + italic label) --------------------

bridge = Column(
    Text("\u00a73", size="tiny", color="muted", weight="700"),
    Anchor("lock", Icon("unlock", size=32, color=CORE_STROKE)),
    Text("Alignment", size="small", color="muted", italic=True),
    Text("Tuning",    size="small", color="muted", italic=True),
    gap="xs", align="center",
)


def language_tile(header: str, caption: str, *, use_box: bool = False):
    glyph = icon_glyph("box") if use_box else text_glyph()
    return output_tile(header, glyph, caption)


def spatial_tile(header: str, icon_name: str, caption: str):
    return output_tile(header, icon_glyph(icon_name), caption)


language_block = Column(
    group_header("State-of-the-Art", "Language Encoder"),
    Row(
        Anchor("pe_lang",
               pe_panel("Language", stroke=LANG_STROKE, fill=LANG_FILL,
                        section="\u00a74")),
        Row(language_tile("OCR Q&A",    "Text"),
            language_tile("Captioning", "Text"),
            language_tile("Video Q&A",  "Text"),
            language_tile("Grounding",  "Box", use_box=True),
            gap="md", align="start"),
        gap="lg", align="center",
    ),
    gap="sm", align="start",
)

spatial_block = Column(
    group_header("State-of-the-Art", "Spatial Encoder"),
    Row(
        Anchor("pe_spat",
               pe_panel("Spatial", stroke=SPAT_STROKE, fill=SPAT_FILL,
                        section="\u00a75")),
        Row(spatial_tile("Detect",          "boxes",    "Box"),
            spatial_tile("Segment",         "scan",     "Mask"),
            spatial_tile("Track",           "link",     "Masklet"),
            spatial_tile("Estimate Depth",  "mountain", "Depth Map"),
            gap="md", align="start"),
        gap="lg", align="center",
    ),
    gap="sm", align="start",
)

encoders = Column(language_block, spatial_block, gap="xl", align="start")


# ---------------------------------------------------------------------------
# Assemble the whole figure: Anchors live in the body, Connect overlays
# pull into the PE Core bus and split out of the lock.
# ---------------------------------------------------------------------------

layout = Row(
    inputs_column,
    pretraining_block,
    bridge,
    encoders,
    gap="lg", align="center",
)

body = Column(
    layout,
    # Image + Video curl into the left edge of PE Core (two smooth
    # curved arcs instead of a bus T-bar).
    Connect("in_image", "pe_core",
            src_side="right", dst_side="left",
            style="curve", curvature=0.6,
            color=CORE_STROKE, head=False),
    Connect("in_video", "pe_core",
            src_side="right", dst_side="left",
            style="curve", curvature=0.6,
            color=CORE_STROKE, head=False),
    # Alignment tuning (\u00a73) fans up to PE Language and down to
    # PE Spatial from the lock glyph.
    Connect("lock", "pe_lang",
            src_side="right", dst_side="left",
            style="curve", curvature=0.4,
            color=CORE_STROKE, head=True),
    Connect("lock", "pe_spat",
            src_side="right", dst_side="left",
            style="curve", curvature=0.4,
            color=CORE_STROKE, head=True),
)

d = Diagram(title="Perception Encoder (PE) overview", body=body)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig01")
print("Rendered:", d.measure())
