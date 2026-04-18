"""GPipe pipeline-parallel schedule on 4 GPUs x 4 micro-batches."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, Timeline, Math, Text, Section,
                    Spacer, Palette)

N_STAGES, N_MB, F_DUR, B_DUR = 4, 4, 1.0, 2.0

# Stable colour per micro-batch.  Same name -> same colour.
def mb_color(m):
    return Palette.next(f"mb_{m}")

lanes = []
for w in range(N_STAGES):
    tasks = []
    # forwards
    for m in range(N_MB):
        tasks.append((w + m, F_DUR, f"F{m+1}", mb_color(m)))
    # backwards (after all forwards done)
    backward_base = (N_STAGES + N_MB - 1) * F_DUR
    for m in range(N_MB):
        tasks.append((backward_base + (N_STAGES - 1 - w) * B_DUR + m * B_DUR,
                      B_DUR, f"B{m+1}", mb_color(m)))
    lanes.append((f"GPU {w}", tasks))

timeline = Timeline(
    lanes, t_min=0, t_max=24, width=620, lane_h=30,
    lane_label_width=60, tick_every=2,
)

bubble = Row(
    Section("Forward / backward",
            Text("F_n = forward on micro-batch n;  "
                 "B_n = backward on micro-batch n.",
                 size="small", color="muted")),
    Section("Bubble fraction",
            Math(r"$\mathrm{bubble} \approx \dfrac{N_{\mathrm{stage}} - 1}"
                 r"{N_{\mathrm{mb}} + N_{\mathrm{stage}} - 1}$"),
            caption=f"with N_stage={N_STAGES}, N_mb={N_MB}: "
                    f"{(N_STAGES-1)/(N_MB+N_STAGES-1):.0%}"),
    gap="lg", align="start",
)

d = Diagram(
    title="Pipeline parallelism: the GPipe schedule",
    subtitle=(f"{N_STAGES} workers, mini-batch split into {N_MB} micro-batches; "
              "forwards flow right-and-down, backwards left-and-up"),
    body=Column(timeline, bubble, gap="lg", align="center"),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "pipeline_parallelism")
print("Rendered:", d.measure())
