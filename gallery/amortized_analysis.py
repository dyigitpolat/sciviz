"""Amortized analysis: push() on a doubling dynamic array."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, Panel, Histogram, Math, Section,
                    Text, Spacer)

# Per-push cost: power-of-2 indices cost i (resize), others cost 1.
N = 32
costs = [(str(i), i if (i & (i - 1)) == 0 else 1,
          "alert" if (i & (i - 1)) == 0 else "info")
         for i in range(1, N + 1)]

cost_chart = Histogram(bins=costs, width=520, height=180,
                       x_label="push index  i",
                       bar_gap=2)

aggregate = Section(
    "Aggregate method",
    Math(r"$T(n) = n + \sum_{k=0}^{\lfloor\log_2 n\rfloor} 2^k \leq 3n - 1$"),
    caption="Total work bounded by 3n; amortised cost = T(n)/n < 3",
)
accounting = Section(
    "Accounting method",
    Math(r"$c_\mathrm{amort} = 3:\ 1\ \mathrm{slot},\ 2\ \mathrm{credit}$"),
    caption="Each push pays 3; the 2 credits cover its own move + one older one",
)
potential = Section(
    "Potential method",
    Math(r"$\Phi = 2n - C \geq 0,\quad \hat c_i = c_i + \Delta\Phi$"),
    caption="Resize spikes are absorbed by the drop in potential",
)

d = Diagram(
    title="Amortized analysis: push() on a doubling dynamic array",
    subtitle="every individual push is O(n) worst-case, but the mean is O(1)",
    body=Column(
        Panel("a", "Per-push cost  (alert = resize)", cost_chart),
        Panel("b", "Three equivalent arguments",
              Row(aggregate, accounting, potential, gap="lg", align="start")),
        gap="lg", align="center",
    ),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "amortized_analysis")
print("Rendered:", d.measure())
