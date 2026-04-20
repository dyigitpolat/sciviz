"""Fig 03 - Test-Time Reinforcement Learning (TTRL) overview.

Reproduces [`gallery/reference/fig03.png`](reference/fig03.png): a
grouped-bar benchmark comparison (AIME / AMC / MATH-500) paired with a
three-tier Data/Role explainer.

Every decoration comes from the library: :class:`GroupedBarChart`
handles the benchmark cards, :class:`Brace` draws the pre-training
header, :class:`Region` provides the two tinted panels and their
side labels, and inline :class:`Connect` arrows stay axis-aligned
between siblings.  The feedback loop alone uses a routed ``Connect``
between named anchors because it has to curve over the pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Anchor, Banner, BarSeries, Box, Brace, Column, Connect, Diagram,
    GroupedBarChart, Icon, Region, Row, Text,
)


RED       = "#c0392b"
INK       = "#0f1a2b"
LLM_FILL  = "#f3d8b6"
LLM_EDGE  = "#8a6a3c"
SET_EDGE  = "#c9c9c9"


def chip(text: str, *, fill: str, color: str, width: float) -> Box:
    return Box(Text(text, color=color, weight="700", size="label"),
               width=width, height=30, fill=fill, stroke=fill, radius=2.5)


def llm(aid: str, icon: str, icon_color: str) -> Anchor:
    return Anchor(aid, Box(
        Row(Text("LLM", weight="700", color=LLM_EDGE, size="label"),
            Icon(icon, color=icon_color, size=12),
            gap="xs", align="center"),
        width=74, height=40, fill=LLM_FILL, stroke=LLM_EDGE, radius=6))


def wire(length: float = 20.0, *, dashed: bool = False) -> Connect:
    """Axis-aligned inline arrow between pipeline siblings."""
    return Connect(direction="right", length=length, dashed=dashed,
                   color=INK)


# ---- Left column: benchmark comparison --------------------------------------

chart = GroupedBarChart(
    [("AIME 2024", [16.7, 43.3], "+159.3%"),
     ("AMC",       [38.6, 67.5],  "+74.9%"),
     ("MATH-500",  [50.6, 84.2],  "+66.4%")],
    series=[BarSeries(name="Baseline", color="#c7d3ea"),
            BarSeries(name="TTRL",     color="#1d3557")],
    y_max=100, y_label="Accuracy (Pass@1)",
    plot_width=360, plot_height=270,
    annotation_color=RED,
    wash="#eceef2", card_stroke="#c0c5cd",
)


# ---- Right column: Data / message / Role ------------------------------------

pretrain_pair = Row(
    chip("Pre-Training Data", fill="#9aa0a6", color="#1a1d21", width=172),
    chip("Labeled Data",      fill="#c7e7b6", color="#14361e", width=92),
    gap=0, align="center",
)

data = Region(
    Row(
        Column(Brace.spanning(pretrain_pair, "Pre-Training +SFT/RL",
                              direction="up", color=INK),
               pretrain_pair, gap="xs", align="center"),
        Column(Text("TTRL", color=RED, weight="700", size="panel",
                    italic=True),
               chip("Unlabeled Data (e.g., Test Data)",
                    fill="#f4cfcf", color="#4a1414", width=260),
               gap="xs", align="center"),
        gap="xl", align="end",
    ),
    label="Data", label_position="right",
    color="#4c63a0", fill="#e7eef7", dashed=False,
    pad_x=16, pad_y=14, margin_y=0, label_size="panel",
)

message = Text(
    "TTRL estimates rewards via majority voting\n"
    "on unlabeled data for RL training.",
    color=RED, weight="700", size="label", italic=True,
)

# Anchors inside the pipeline so the RL-Training feedback arrow can reach
# them; inline wires keep the chain horizontal.
scaling = Region(
    Row(
        Text("Query", color=INK, weight="600"), wire(),
        llm("sample", "cube",  "#3b82f6"), wire(),
        Anchor("samples", Box(
            Text("{\u0177\u2081, \u0177\u2082, \u00b7\u00b7\u00b7}",
                 color=INK, weight="500"),
            width=108, height=40, fill="#ffffff", stroke=SET_EDGE,
            radius=6, dashed=True)), wire(),
        Box(Text("\u0177", color=INK, weight="600"), width=34, height=40,
            fill="#f2f3f5", stroke=SET_EDGE, radius=6),
        gap="sm", align="center",
    ),
    label="Test-Time Scaling (e.g., Majority Voting)",
    label_position="bottom", color="#334155", dashed=True,
    pad_x=12, pad_y=8, margin_y=0, label_size="small",
)

role = Region(
    Column(
        Row(
            scaling, wire(),
            Banner(llm("train", "flame", "#e11d48"),
                   below=Text("TTRL", color=RED, weight="700",
                              size="small", italic=True), gap="xs"),
            wire(dashed=True, length=24),
            gap="sm", align="center",
        ),
        Connect("samples", "train",
                src_side="top", dst_side="top",
                label="RL Training", label_color=RED,
                color=RED, dashed=True, head="dst",
                style="curve", curvature=0.35, detour=24.0),
        gap="xs", align="center",
    ),
    label="Role", label_position="right",
    color="#3a6b2a", fill="#e9f1df", dashed=True,
    pad_x=14, pad_y=14, margin_y=0, label_size="panel",
)


# ---- Figure -----------------------------------------------------------------

Diagram(body=Row(
    chart,
    Column(data, message, role, gap="md", align="center"),
    gap="xl", align="center",
)).save_all(Path(__file__).resolve().parents[1] / "_out" / "fig03")
