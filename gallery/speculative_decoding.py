"""Speculative decoding: K proposals for the price of 1 verification.

Refactored to use generic primitives: ``Tokens`` for the auto-aligned token
strips, ``Section`` for the formula card, ``BarChart`` with ``auto_color``
for the speedup chart.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Row, Column, Panel, Tokens, Math, Caption,
                    Section, BarChart, Text, AlignedColumns)


def _strip_label(name):
    return Text(name, size="small", color="muted", weight="700")


def _strip_tokens(tokens):
    return Tokens(tokens)


# (a) Token strips: AlignedColumns forces the three rows to share column
# widths so the "draft:" / "target:" / "kept:" labels stack into a rigid
# left column and the Tokens strips line up to the right of them.
strips = AlignedColumns(
    rows=[
        [_strip_label("draft:"),
         _strip_tokens([("The","accept"), ("cat","accept"),
                        ("sat","accept"), ("on","reject")])],
        [_strip_label("target:"),
         _strip_tokens([("The","accept"), ("cat","accept"),
                        ("sat","accept"), ("a","reject")])],
        [_strip_label("kept:"),
         _strip_tokens([("The","accept"), ("cat","accept"),
                        ("sat","accept"), ("a","accept")])],
    ],
    col_align=("end", "start"),
    gap_x="sm",
    gap_y="sm",
)
protocol_panel = Section(
    "Protocol on one step", strips,
    caption="3 draft tokens accepted; 4th replaced by target resample",
)

formulas = Column(
    Section(
        "Acceptance rule",
        Math(r"$\alpha_i = \min\!\left(1,\ \dfrac{p(x_i \mid x_{<i})}"
             r"{q(x_i \mid x_{<i})}\right)$"),
        caption="p = target distribution, q = draft distribution"),
    Section(
        "Expected speedup",
        Math(r"$\mathbb{E}[\#\,\mathrm{tokens/step}] = "
             r"\frac{1 - \alpha^{K+1}}{1 - \alpha}$"),
        caption="(Leviathan, Kalman, Matias 2023)"),
    gap="md", align="start",
)

speedup = BarChart([
    ("Greedy target",       1.00, "1.00x"),
    ("Spec. K=2, alpha=0.7", 1.97, "1.97x"),
    ("Spec. K=4, alpha=0.7", 2.59, "2.59x"),
    ("Spec. K=8, alpha=0.7", 2.95, "2.95x"),
    ("Spec. K=4, alpha=0.9", 3.44, "3.44x"),
], bar_width=140, bar_height=10, auto_color=True)

d = Diagram(
    title="Speculative decoding: K proposals for the price of 1 verification",
    subtitle="small draft model fills bubbles while the big target verifies in parallel",
    body=Row(
        Panel("a", "Per-step protocol",  protocol_panel),
        Panel("b", "Why it's unbiased",  formulas),
        Panel("c", "Speedup",            speedup),
        gap="md", align="start",
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "speculative_decoding")
print("Rendered:", d.measure())
