"""Diffusion models: forward noising + learned reverse process.

Uses the generic ``Heatmap`` primitive (no custom NoisyTile class).
"""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, Heatmap, Connector, Math,
                    Section, Text, Spacer, FixedSize)

# Generate a 6x6 deterministic "image" plus snapshots at decreasing SNR
PATTERN = [[(i + j) / 10 for j in range(6)] for i in range(6)]

CELL = 12                  # Heatmap cell size; 6x6 grid -> tile is 72 px wide
TILE_W = 6 * CELL
ARROW_LEN = 22

def noisy(snr, seed):
    rng = random.Random(seed)
    return [[max(0, min(1, snr * PATTERN[i][j] +
                                (1 - snr) * (0.5 + 0.5 * rng.uniform(-1, 1))))
             for j in range(6)] for i in range(6)]

def tile(snr, seed):
    return Heatmap(noisy(snr, seed), cell=CELL, palette="grays",
                   show_grid=True, vmin=0, vmax=1)

def chain(snrs, seed_base):
    items = []
    for i, snr in enumerate(snrs):
        items.append(tile(snr, seed_base + i))
        if i < len(snrs) - 1:
            items.append(Connector(direction="right", length=ARROW_LEN))
    return Row(*items, gap="sm", align="center")

forward_chain = chain([1.0, 0.75, 0.5, 0.25, 0.0], seed_base=10)
reverse_chain = chain([0.0, 0.25, 0.5, 0.75, 1.0], seed_base=20)

# Step labels (x_0 ... x_t), typeset as math and wrapped in fixed-width cells
# so each label centers exactly under its tile in the chain above/below.
def labels(rev=False):
    base = [r"$x_0$", r"$x_1$", r"$x_2$", r"$x_{t-1}$", r"$x_t$"]
    if rev:
        base = list(reversed(base))
    cells = []
    for i, lbl in enumerate(base):
        cells.append(FixedSize(Math(lbl, size="small", color="muted"),
                               width=TILE_W, align="center"))
        if i < len(base) - 1:
            cells.append(Spacer(ARROW_LEN, 0))
    return Row(*cells, gap="sm", align="center")

forward_panel = Column(
    Row(Text("FORWARD  (fixed)", size="small", color="alert", weight="700"),
        Spacer(8, 0),
        Math(r"$q(x_t \mid x_{t-1}) = "
             r"\mathcal{N}(\sqrt{1 - \beta_t}\, x_{t-1},\ \beta_t I)$"),
        gap="none", align="center"),
    forward_chain,
    labels(),
    gap="xs", align="start",
)

reverse_panel = Column(
    labels(rev=True),
    reverse_chain,
    Row(Text("REVERSE  (learned)", size="small", color="info", weight="700"),
        Spacer(8, 0),
        Math(r"$p_\theta(x_{t-1} \mid x_t) = "
             r"\mathcal{N}(\mu_\theta(x_t, t),\ \Sigma_\theta(x_t, t))$"),
        gap="none", align="center"),
    gap="xs", align="start",
)

objective = Section(
    "Training objective (noise prediction)",
    Column(
        Math(r"$\mathcal{L}_\mathrm{simple} = "
             r"\mathbb{E}_{t, x_0, \varepsilon}\!\left["
             r"\|\varepsilon - \varepsilon_\theta(x_t, t)\|^2\right]$"),
        Math(r"$x_t = \sqrt{\bar\alpha_t}\, x_0 + "
             r"\sqrt{1 - \bar\alpha_t}\, \varepsilon$",
             size="small", color="muted"),
        gap="xs", align="start",
    ),
    caption="train one network to predict the noise.",
)

d = Diagram(
    title="Diffusion models: learn to invert a fixed noise schedule",
    subtitle=("forward Markov chain corrupts a clean sample to pure noise; "
              "the reverse chain denoises step by step"),
    body=Column(forward_panel, reverse_panel, objective,
                gap="lg", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "diffusion")
print("Rendered:", d.measure())
