"""Fig 02 - Multi-source video captioning pipeline.

Reproduces [`gallery/reference/fig02.png`](reference/fig02.png): a
multi-frame video stack feeds two parallel captioner branches plus a
metadata sideband; the resulting captions and metadata converge on a
single LLM that emits the aligned text caption.

Layout choreography:

* Each ``(captioner, output panel)`` pair lives in its own ``Row``.
  ``AlignedStack`` shares the captioner column's slot width across
  rows, so "Video Captioner" and "Image Captioner" line up on a
  single vertical axis even though the right-hand panels differ in
  height.
* The three caption banks (Video Caption, Frame Captions, Metadata)
  are wrapped in a ``Column(equal_widths=True)`` so they paint at
  identical width, regardless of how many chips each contains.
* The "Video Frames" tile uses ``StackedTiles`` to render three
  offset dashed copies for multi-frame depth.

The author describes which signals fan into which model. All layout,
spacing, radii, and curve routing come from the library backend.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    AlignedStack, Anchor, Box, Column, Connect, Diagram, Icon, Row,
    Spacer, StackedTiles, Text,
)

GREEN = ("#2f6b5b", "#dbe9e1")
BLUE  = ("#3f5fa3", "#d8dff0")
PURP  = ("#5b3fa3", "#e3d8ee")
INK   = "#1f2937"
WIRE  = "#2f6b5b"
DASH  = "#a3afbe"


def chip(label: str, color, *, anchor_id: str | None = None,
         italic: bool = False) -> Anchor | Box:
    """A white pill with a coloured ``+`` and a body label."""
    inner = Row(
        Text("+", weight="700", color=color[0], size="label"),
        Text(label, color=INK, italic=italic),
        gap="sm", align="center",
    )
    box = Box(inner, fill="white", stroke="white", radius=4)
    return Anchor(anchor_id, box) if anchor_id else box


def panel(header: str, color, items, *,
          anchor_id: str | None = None) -> Anchor | Box:
    """A tinted card titled ``header`` over a stack of chips."""
    inner = Column(
        Text(header, weight="700", color=color[0], size="label"),
        *items,
        gap="xs", align="start",
    )
    box = Box(inner, fill=color[1], stroke=color[1], radius=8)
    return Anchor(anchor_id, box) if anchor_id else box


def captioner(label: str, color, anchor_id: str) -> Anchor:
    return Anchor(anchor_id, Box(
        Text(label, weight="700", color=color[0], size="label"),
        fill="white", stroke=color[0], stroke_width=1.5, radius=8,
    ))


# ---- inputs (stacked dashed video-frames tile) ---------------------------
frame_tile = Box(
    Column(
        Icon("video", color=GREEN[0], size=28),
        Text("Video", color=GREEN[0], size="small"),
        Text("Frames", color=GREEN[0], size="small"),
        gap="xs", align="center",
    ),
    fill="white", stroke=DASH, dashed=True, radius=8,
)
# Ghost copies behind the front tile are the same outer rectangle with
# no icon / labels -- repetition reads as depth, not as duplicated text.
frame_ghost = Box(
    fill="white", stroke=DASH, dashed=True, radius=8,
    min_width=0, min_height=0,
)
frames = Anchor("frames", StackedTiles(
    frame_tile, ghost=frame_ghost, count=3, offset=(7.0, -7.0),
))

# ---- captioner cards -----------------------------------------------------
v_cap = captioner("Video Captioner", GREEN, "vcap")
i_cap = captioner("Image Captioner", BLUE,  "icap")

# ---- caption banks (equalised widths via Column(equal_widths=True)) -------
video_caption = Anchor("video_caption", Box(
    Text("Video Caption", weight="700", color=GREEN[0], size="label"),
    fill=GREEN[1], stroke=GREEN[1], radius=8,
))
frame_panel = panel(
    "Frame Captions", BLUE,
    [chip("Frame 1 caption", BLUE, anchor_id="fc1"),
     chip("Frame 2 caption", BLUE, anchor_id="fc2"),
     chip("...",             BLUE, anchor_id="fcdots", italic=True),
     chip("Frame n caption", BLUE, anchor_id="fcn")],
    anchor_id="frame_panel",
)
metadata_panel = panel(
    "Metadata", PURP,
    [chip("Title",       PURP, anchor_id="md_title"),
     chip("Description", PURP, anchor_id="md_desc")],
    anchor_id="md_panel",
)

# ---- pair each captioner with its bank, then align rows ------------------
# AlignedStack(stretch=True) broadcasts the widest captioner and the
# widest panel widths back to every row, AND inflates Box-like
# children to match -- so the two captioner cards paint at identical
# width on a shared vertical axis, and the three panels paint at
# identical width regardless of chip count. Empty Spacer in row 3
# reserves the captioner slot for the standalone Metadata panel.
pair_video    = Row(v_cap, video_caption, gap="lg", align="center")
pair_image    = Row(i_cap, frame_panel,   gap="lg", align="center")
pair_metadata = Row(Spacer(0, 0), metadata_panel, gap="lg", align="center")
banks = AlignedStack(pair_video, pair_image, pair_metadata,
                     gap="md", align="start", stretch=True)

# ---- LLM trunk + aligned-caption output ----------------------------------
llm = Anchor("llm", Box(
    Text("LLM", weight="700", size="title", color=PURP[0]),
    fill=PURP[1], stroke=PURP[1], radius=8,
    min_height=320, min_width=84,
))

aligned = Anchor("aligned", Box(
    Column(
        Text("Aligned", color=PURP[0], size="small", weight="600"),
        Text("Caption", color=PURP[0], size="small", weight="600"),
        Spacer(0, 4),
        Text("T", weight="700", size="title", color=PURP[0]),
        Text("Text", color=PURP[0], size="tiny"),
        gap="xs", align="center",
    ),
    fill="white", stroke=PURP[0], dashed=True, radius=8,
))

# ---- assembly + wires ----------------------------------------------------
# Every fan-out / fan-in is a single multi-endpoint Connect: one source
# to many sinks, or many sources to one sink. The bus resolver draws a
# shared spine and taps each endpoint off it.
body = Column(
    Row(frames, banks, llm, aligned, gap="xl", align="center"),
    # frames fan out to captioners + Metadata-sideband chips
    Connect("frames", ["vcap", "icap", "md_title", "md_desc"],
            orientation="horizontal", head=False, color=WIRE),
    # Image Captioner fans out to every Frame-caption chip
    Connect("icap", ["fc1", "fc2", "fcdots", "fcn"],
            orientation="horizontal", head=False, color=WIRE),
    # Video Captioner emits a single caption band
    Connect("vcap", "video_caption", style="curve",
            head=False, color=WIRE),
    # All three caption banks converge on the LLM
    Connect(["video_caption", "frame_panel", "md_panel"], "llm",
            orientation="horizontal", head=False, color=WIRE),
    # Final aligned-caption arrow
    Connect("llm", "aligned", color=WIRE),
)

Diagram(body=body).save_all(
    Path(__file__).resolve().parents[1] / "_out" / "fig02"
)
