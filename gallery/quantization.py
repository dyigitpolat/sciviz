"""Post-training quantization: FP32 -> INT8.

Three panels: rounding visualization, scale formula, footprint comparison.
Bars are auto-coloured; the bin chart uses the QuantBins example primitive.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, BarChart, Math, Caption,
                    Section, Text, NNLayer, Spacer)
from sciviz.examples.ml import QuantBins

dist = Column(
    QuantBins(n_bins=8, n_samples=140, width=320, height=110, seed=7),
    Caption("vertical lines = bin boundaries; arrows = rounding"),
    gap="xs", align="center",
)

formula = Column(
    Math(r"$Q(w) = \mathrm{round}(w / s) \cdot s$"),
    Spacer(0, 8),
    Row(
        NNLayer("compute s", kind="norm",
                shape="s = max|w| / 127", width=170, height=42),
        Spacer(16, 0),
        NNLayer("w / s -> int8", kind="dense",
                shape="saturating cast", width=170, height=42),
        gap="none", align="start",
    ),
    Spacer(0, 6),
    Text("store s (FP16) + int8 codes", size="small",
         color="accent", weight="700", align="middle"),
    gap="xs", align="center",
)

footprint = BarChart([
    ("FP32 baseline", 28.0, "28.0 GB"),
    ("INT8 PTQ",       7.0,  "7.0 GB"),
    ("INT4 GPTQ",      3.5,  "3.5 GB"),
], bar_width=200, bar_height=12, highlight_first=True)
bandwidth = BarChart([
    ("FP32", 900.0, "900 GB/s"),
    ("INT8", 225.0, "225 GB/s"),
    ("INT4", 113.0, "113 GB/s"),
], bar_width=200, bar_height=12, highlight_first=True)

footprint_panel = Column(
    Section("Memory (7B model)", footprint),
    Section("Bandwidth", bandwidth),
    gap="md", align="start",
)

notes = Row(
    Section("Granularity matters",
            Text("Per-tensor scales are cheapest but bleed to outliers. "
                 "Per-channel (column) scales preserve accuracy.",
                 size="small", color="muted")),
    Section("Handle outliers",
            Text("A few activations are 100x larger than the rest. SmoothQuant "
                 "and GPTQ absorb them via equivalence transforms.",
                 size="small", color="muted")),
    gap="lg", align="start",
)

d = Diagram(
    title="Post-training quantization: FP32 -> INT8",
    subtitle="4x cut in memory and bandwidth, typically <1% accuracy loss",
    body=Column(
        Row(
            Panel("a", "Rounding", dist),
            Panel("b", "Per-channel scale", formula),
            Panel("c", "Footprint", footprint_panel),
            gap="md", align="start",
        ),
        notes,
        gap="lg", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "quantization")
print("Rendered:", d.measure())
