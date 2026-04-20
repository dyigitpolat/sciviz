"""Fig 01 - Perception Encoder (PE) multi-headed architecture.

Reproduces [`gallery/reference/fig01.png`](reference/fig01.png): two raw
modalities feed a contrastive **PE Core** (§2); an alignment-tuning
bridge (§3) branches the backbone into a **PE Language** encoder (§4)
and a **PE Spatial** encoder (§5), each with four downstream tasks.

The author describes *what* flows into *what*. All layout, sizing,
padding, radii, and stroke widths come from the library backend.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (AlignedStack, Anchor, Banner, Box, Column, Connect,
                    Diagram, Icon, Row, Text)

CORE = ("#274b45", "#e8efed")
LANG = ("#3f5fa3", "#dbe2f0")
SPAT = ("#6b3fbf", "#e6dcf4")
TILE = ("#6a5aa2", "#eae6f3", "#2f2660")

def input_tile(name: str, label: str) -> Box:
    return Box(Column(Icon(name, color=TILE[0]), Text(label, color="muted"),
                      gap="xs"),
               fill="#f2f4f7", stroke="#a6b0bd", dashed=True)

def output_tile(header: str, glyph: Icon, caption: str) -> Banner:
    card = Box(Column(glyph, Text(caption, color=TILE[2], weight="600"), gap="xs"),
               fill=TILE[1], stroke=TILE[0])
    return Banner(card, above=Text(header, size="tiny",
                                    color=TILE[2], weight="600"),
                  gap="xs")

def pe_panel(subtitle: str, color, badge=None) -> Box:
    stroke, fill = color
    title_stack = Column(Text("PE", size="title", color=stroke, weight="700"),
                         Text(subtitle, size="label", color=stroke,
                              italic=True),
                         gap="sm")
    return Box(title_stack, fill=fill, stroke=stroke,
               badge=badge, badge_color=stroke,
               shape_key="pe_panel")

def header(bold: str, italic: str) -> Column:
    return Column(Text(bold, size="small", weight="700"),
                  Text(italic, size="small", italic=True, color="muted"),
                  gap="xs")

def glyph(name: str, *, filled: bool = False, color: str = TILE[0]) -> Icon:
    return Icon(name, color=color, fill="match" if filled else "none")

inputs = AlignedStack(Anchor("in_image", input_tile("image", "Image")),
                      Anchor("in_video", input_tile("video", "Video")),
                      gap="sm")

pretrain_outputs = AlignedStack(
    Row(output_tile("Classify Images", glyph("hash"),  "Class Idx"),
        output_tile("Retrieve Images", glyph("image"), "Image"),
        gap="sm"),
    Row(output_tile("Classify Videos", glyph("hash"),  "Class Idx"),
        output_tile("Retrieve Videos", glyph("video"), "Video"),
        gap="sm"),
    align="start", gap="sm")

pretrain_body = Row(
    Banner(Anchor("pe_core", pe_panel("Core", CORE, badge="§2")),
           above=header("Large-Scale", "Contrastive Pretraining")),
    pretrain_outputs)

language_body = Row(
    Banner(Anchor("pe_lang", pe_panel("Language", LANG, badge="§4")),
           above=header("State-of-the-Art", "Language Encoder")),
    output_tile("OCR Q&A",    glyph("serif-t"),        "Text"),
    output_tile("Captioning", glyph("serif-t"),        "Text"),
    output_tile("Video Q&A",  glyph("serif-t"),        "Text"),
    output_tile("Grounding",  glyph("frames-stacked"), "Box"),
    gap="sm")

spatial_body = Row(
    Banner(Anchor("pe_spat", pe_panel("Spatial", SPAT, badge="§5")),
           above=header("State-of-the-Art", "Spatial Encoder")),
    output_tile("Detect",         glyph("frames-stacked", color=SPAT[0]), "Box"),
    output_tile("Segment",        glyph("blob", filled=True, color=SPAT[0]), "Mask"),
    output_tile("Track",          glyph("ovals-stack", filled=True, color=SPAT[0]), "Masklet"),
    output_tile("Estimate Depth", glyph("peaks", color=SPAT[0]), "Depth Map"),
    gap="sm")

encoders = AlignedStack(language_body, spatial_body, gap="xs")

bridge = Column(Anchor("lock", Icon("unlock", color=CORE[0])),
                Text("§3", size="tiny", color="muted", weight="700"),
                Text("Alignment Tuning", size="small", color="muted",
                     italic=True),
                gap="xs")

body = Column(
    Row(inputs, pretrain_body, bridge, encoders),
    Connect("in_image", "pe_core", style="curve", head=False, color=CORE[0]),
    Connect("in_video", "pe_core", style="curve", head=False, color=CORE[0]),
    Connect("lock", "pe_lang",     style="curve", color=CORE[0]),
    Connect("lock", "pe_spat",     style="curve", color=CORE[0]))

Diagram(body=body).save_all(Path(__file__).resolve().parents[1] / "_out" / "fig01")
