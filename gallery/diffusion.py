"""Diffusion models: forward noising + learned reverse process.

Uses the generic ``Heatmap`` primitive (no custom NoisyTile class).
"""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Heatmap, Math,
                    Section, Text, Inline, LabeledChain)

PATTERN = [[(i + j) / 10 for j in range(6)] for i in range(6)]
CELL = 12                  # Heatmap cell size; 6x6 grid -> tile is 72 px wide


def noisy(snr, seed):
    rng = random.Random(seed)
    return [[max(0, min(1, snr * PATTERN[i][j] +
                                (1 - snr) * (0.5 + 0.5 * rng.uniform(-1, 1))))
             for j in range(6)] for i in range(6)]


def tile(snr, seed):
    return Heatmap(noisy(snr, seed), cell=CELL, palette="grays",
                   show_grid=True, vmin=0, vmax=1)


def step_label(sym, *, rev=False):
    return Math(sym, size="small", color="muted")


STEPS = [r"$x_0$", r"$x_1$", r"$x_2$", r"$x_{t-1}$", r"$x_t$"]


def labeled_chain(snrs, seed_base, *, labels_at: str, rev_labels: bool = False):
    """Build one (row, labels) chain via the library's built-in alignment."""
    tiles = [tile(snr, seed_base + i) for i, snr in enumerate(snrs)]
    syms = list(reversed(STEPS)) if rev_labels else list(STEPS)
    lbls = [step_label(s) for s in syms]
    kw = {"top_labels": lbls} if labels_at == "top" else {"bottom_labels": lbls}
    return LabeledChain(items=tiles, arrow="->", gap="sm", label_gap="xs", **kw)


forward_chain = labeled_chain([1.0, 0.75, 0.5, 0.25, 0.0],
                              seed_base=10, labels_at="bottom")
reverse_chain = labeled_chain([0.0, 0.25, 0.5, 0.75, 1.0],
                              seed_base=20, labels_at="top", rev_labels=True)

forward_panel = Column(
    Inline(
        Text("FORWARD  (fixed)", size="small", color="alert", weight="700"),
        Math(r"$q(x_t \mid x_{t-1}) = "
             r"\mathcal{N}(\sqrt{1 - \beta_t}\, x_{t-1},\ \beta_t I)$"),
        gap="sm",
    ),
    forward_chain,
    gap="xs", align="start",
)

reverse_panel = Column(
    reverse_chain,
    Inline(
        Text("REVERSE  (learned)", size="small", color="info", weight="700"),
        Math(r"$p_\theta(x_{t-1} \mid x_t) = "
             r"\mathcal{N}(\mu_\theta(x_t, t),\ \Sigma_\theta(x_t, t))$"),
        gap="sm",
    ),
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
