"""Roofline performance model for an NVIDIA A100 (FP16 Tensor cores)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Scatter, Math, Section, Text,
                    Palette)

PEAK_FLOPS_GF, PEAK_BW = 312_000.0, 2_000.0   # GFLOP/s, GB/s
RIDGE = PEAK_FLOPS_GF / PEAK_BW

ai_grid = [0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3000]
roof = [(a, min(PEAK_FLOPS_GF, a * PEAK_BW)) for a in ai_grid]

# Real kernels: (AI, achieved GFLOP/s, name, color, marker_size)
# Use stable palette assignment so each kernel keeps its colour even if reordered.
kernels = [
    (0.25,     425.0,  "SpMV",       Palette.next("SpMV"),    5),
    (0.8,    1_500.0,  "GEMV",       Palette.next("GEMV"),    5),
    (5.0,    9_800.0,  "Conv 3x3",   Palette.next("Conv"),    5),
    (40.0,  82_000.0,  "GEMM 4k",    Palette.next("GEMM"),    5),
    (150.0, 270_000.0, "FFT",        Palette.next("FFT"),     5),
    (250.0, 305_000.0, "LLM attn",   Palette.next("attn"),    5),
]

plot = Scatter(
    kernels,
    lines=[(roof, "text", None, 1.3)],
    x_range=(0.1, 3000), y_range=(100, 1_000_000),
    width=460, height=260,
    x_label="operational intensity  (FLOP / byte)",
    y_label="performance  (GFLOP / s)",
    log_x=True, log_y=True, grid=True,
)

notes = Column(
    Section("Memory-bound", Math(r"$P = I \cdot B$"),
            caption="left of ridge"),
    Section("Compute-bound", Math(r"$P = P_\mathrm{peak}$"),
            caption="right of ridge"),
    Section("Ridge",
            Math(fr"$I^* = P_\mathrm{{peak}} / B = {RIDGE:.0f}\ \mathrm{{FLOP/B}}$"),
            caption="break-even AI"),
    gap="md", align="start",
)

d = Diagram(
    title="Roofline model: NVIDIA A100, FP16 Tensor cores",
    subtitle="peak 312 TFLOP/s, 2.0 TB/s HBM",
    body=Row(plot, notes, gap="xl", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "roofline")
print("Rendered:", d.measure())
