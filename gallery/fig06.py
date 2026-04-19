"""Fig 06 - LineChart with inline annotations.

Training vs validation loss for two runs.  Annotations pin commentary to
specific steps; legend is placed to the right.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Annotate,
    Caption,
    Column,
    Diagram,
    LineChart,
    Series,
)


def decay(a: float, b: float, steps: int, noise: float = 0.0):
    return [(i, a * math.exp(-i / b) + noise * math.sin(i / 3.0))
            for i in range(steps)]


train = decay(3.2, 12, 40)
val = [(x, y + 0.25) for x, y in decay(3.2, 10, 40)]
baseline = [(0, 2.3), (10, 2.15), (20, 2.0), (30, 1.92), (39, 1.88)]

chart = LineChart(
    [
        Series(train, label="train", color="blue"),
        Series(val, label="val", color="amber", dash="4,3"),
        Series(baseline, label="baseline", color="gray", width=0.7),
    ],
    x_range=(0, 39),
    y_range=(0.1, 3.5),
    width=420, height=230,
    x_label="step",
    y_label="loss",
    grid=True,
    annotations=[
        Annotate(10, 2.05, "LR warmup", dx=10, dy=-12, color="accent"),
        Annotate(28, 0.75, "val plateau", dx=-6, dy=-16, color="highlight"),
    ],
    legend="right",
)

d = Diagram(
    title="Loss curves",
    subtitle="LineChart with annotations and a right-mounted legend",
    body=Column(chart, Caption("solid -- train; dashed -- val"),
                 gap="sm", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "fig06")
print("Rendered:", d.measure())
