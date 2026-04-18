"""Domain-specific ML diagram presets.

These are higher-level *examples* built on top of the generic sciviz
primitives.  They live in ``sciviz.examples`` rather than the core because
they encode strong assumptions about a specific topic (attention, LoRA,
quantization).  Use them as-is for typical figures, or copy and adapt.

To use:

    from sciviz.examples.ml import AttentionHead, LoRA, QuantBins
"""
from __future__ import annotations
import math
from typing import List, Optional, Sequence, Tuple, Union
from ..core import Element, BBox, Canvas, Theme
from ..elements import _normalise_matrix, Text, TextBlock, Box, MiniGrid
from ..layout import Row, Column, Stack, Spacer
from ..ml import NNLayer, Pipeline, Tensor

# ---------------------------------------------------------------------------
# AttentionHead -- Q @ K^T -> softmax -> A @ V
# ---------------------------------------------------------------------------

class AttentionHead(Element):
    """Pipeline visualising scaled-dot-product attention.

    Renders as:  Q   K   V
                 \\ /    |
                 Q@Kᵀ   |
                   |    |
                 softmax
                   |    |
                   A----+
                   |
                  out

    Parameters
    ----------
    seq_len : int
        Number of tokens.
    d_k : int
        Head dimension (controls width of Q/K/V).
    mask : str, optional
        Either ``"causal"`` or ``None``.
    """

    def __init__(self, *, seq_len: int = 6, d_k: int = 4,
                 mask: Optional[str] = None,
                 weights_seed: int = 0):
        self.seq_len = seq_len
        self.d_k = d_k
        self.mask = mask
        self.weights_seed = weights_seed

    def _compose(self, theme: Theme) -> Element:
        from ..elements import Matrix, Arrow, Text
        import random
        rng = random.Random(self.weights_seed)
        L, D = self.seq_len, self.d_k

        def rnd(r, c):
            return [[rng.uniform(-1, 1) for _ in range(c)] for _ in range(r)]

        Q = rnd(L, D); K = rnd(L, D); V = rnd(L, D)
        # attention weights: softmax-ish random
        attn = [[max(0.0, rng.uniform(0, 1)) for _ in range(L)] for _ in range(L)]
        if self.mask == "causal":
            for i in range(L):
                for j in range(L):
                    if j > i:
                        attn[i][j] = 0.0
        # normalize rows
        for i in range(L):
            s = sum(attn[i]) or 1.0
            attn[i] = [v / s for v in attn[i]]
        out = rnd(L, D)

        Mat = lambda data, title, palette="blues": Column(
            Text(title, size="small", color="muted", weight="600", align="middle"),
            Matrix(data, cell_size="xs", row_labels=None, col_labels=None,
                   palette=palette),
            gap="xs", align="center",
        )

        row1 = Row(
            Mat(Q, "Q"),
            Mat(K, "K"),
            Mat(V, "V"),
            gap="lg", align="center",
        )

        qk = Row(
            Mat([[sum(Q[i][k] * K[j][k] for k in range(D)) for j in range(L)]
                 for i in range(L)],
                "QK\u1d40 / \u221ad"),
            gap="md", align="center",
        )

        softmax = Mat(attn, "softmax(QK\u1d40)", palette="emeralds")

        final = Row(
            Mat(out, "Output = A\u00b7V", palette="blues"),
            gap="md", align="center",
        )

        return Column(
            row1,
            Arrow(label="matmul", direction="down", length=16),
            qk,
            Arrow(label="softmax / \u221a dim", direction="down", length=16),
            softmax,
            Arrow(label="\u00b7 V", direction="down", length=16),
            final,
            gap="xs", align="center",
        )

    def measure(self, theme: Theme) -> BBox:
        return self._compose(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._compose(theme).render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# LoRA -- W + B @ A decomposition
# ---------------------------------------------------------------------------

class LoRA(Element):
    """Visualise LoRA low-rank adaptation: W = W0 + scaling * B @ A.

    Shows:

    +--------+        +---+   +-----------+
    |   W0   |  +     | B | * |     A     |
    +--------+        +---+   +-----------+
     d x d             d x r      r x d

    The dimensions are conveyed visually by the aspect ratios.
    """

    def __init__(self, *, d: int = 8, r: int = 2, freeze_base: bool = True,
                 seed: int = 0):
        self.d = d
        self.r = r
        self.freeze_base = freeze_base
        self.seed = seed

    def _compose(self, theme: Theme) -> Element:
        from ..elements import Matrix, Text, Caption
        import random
        rng = random.Random(self.seed)

        d, r = self.d, self.r

        def rnd(a, b):
            return [[rng.uniform(-1, 1) for _ in range(b)] for _ in range(a)]

        W0 = rnd(d, d)
        B = rnd(d, r)
        A = rnd(r, d)

        base = Column(
            Text("W\u2080  (frozen)" if self.freeze_base else "W\u2080",
                 size="small", color="muted", weight="600", align="middle"),
            Matrix(W0, cell_size="xs", row_labels=None, col_labels=None,
                   palette="grays"),
            Caption(f"{d} \u00d7 {d}"),
            gap="xs", align="center",
        )

        plus = Column(
            Spacer(0, theme.unit),
            Text("+", size="title", color="muted", weight="700"),
            gap="none", align="center",
        )

        b_block = Column(
            Text("B", size="small", color="accent", weight="600", align="middle"),
            Matrix(B, cell_size="xs", row_labels=None, col_labels=None,
                   palette="emeralds"),
            Caption(f"{d} \u00d7 {r}"),
            gap="xs", align="center",
        )

        at_block = Column(
            Text("A", size="small", color="accent", weight="600", align="middle"),
            Matrix(A, cell_size="xs", row_labels=None, col_labels=None,
                   palette="emeralds"),
            Caption(f"{r} \u00d7 {d}"),
            gap="xs", align="center",
        )

        times = Column(
            Spacer(0, theme.unit),
            Text("\u00d7", size="title", color="muted", weight="700"),
            gap="none", align="center",
        )

        update = Row(b_block, times, at_block, gap="sm", align="center")

        return Row(base, plus, update, gap="md", align="center")

    def measure(self, theme: Theme) -> BBox:
        return self._compose(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._compose(theme).render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# QuantBins -- FP -> INTn quantisation visualisation
# ---------------------------------------------------------------------------

class QuantBins(Element):
    """Visualise quantisation: FP distribution bucketed into a few INT levels.

    The element shows a histogram-ish distribution of FP values and vertical
    gridlines marking the integer bin boundaries, emphasising the rounding
    step.
    """

    def __init__(self, *, n_bins: int = 8, n_samples: int = 80,
                 width: float = 260.0, height: float = 90.0, seed: int = 0):
        self.n_bins = n_bins
        self.n_samples = n_samples
        self.width = width
        self.height = height
        self.seed = seed

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width, self.height + theme.text_height("tiny") + theme.unit)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        import random, math as _m
        rng = random.Random(self.seed)

        W, H = self.width, self.height
        # Generate bell-ish FP samples in [-1, 1]
        samples = []
        for _ in range(self.n_samples):
            v = (rng.gauss(0, 0.35))
            v = max(-0.99, min(0.99, v))
            samples.append(v)

        # Draw axis
        axis_y = y + H
        canvas.line(x, axis_y, x + W, axis_y, stroke=theme.text_muted,
                   stroke_width=1.0)
        # Bin boundaries (lighter lines)
        for i in range(self.n_bins + 1):
            bx = x + i * W / self.n_bins
            canvas.line(bx, y + 6, bx, axis_y,
                       stroke=theme.border_strong, stroke_width=0.8,
                       dasharray="2,2")
        # Bin centers (dotted guide)
        for i in range(self.n_bins):
            cx = x + (i + 0.5) * W / self.n_bins
            canvas.circle(cx, axis_y, 2.0, fill=theme.text_muted)
        # Bucket samples
        bin_counts = [0] * self.n_bins
        for v in samples:
            b = int(min(self.n_bins - 1, (v + 1) / 2 * self.n_bins))
            bin_counts[b] += 1
        max_c = max(bin_counts) or 1
        # --- rounding arrows: pick ~1 representative per bin, arrow to centre
        # one representative sample per bin (first encountered)
        rep_per_bin = {}
        for v in samples:
            b = int(min(self.n_bins - 1, (v + 1) / 2 * self.n_bins))
            if b not in rep_per_bin:
                rep_per_bin[b] = v
        # draw all samples as small circles first (so arrows sit on top)
        for i, v in enumerate(samples):
            sx = x + (v + 1) / 2 * W
            # vertical placement: spread based on seeded jitter
            jitter = rng.uniform(0.15, 0.85)
            sy = y + 8 + jitter * (H - 28)
            canvas.circle(sx, sy, 1.7, fill=theme.primary_fill, opacity=0.75)
        # rounding arrows (prominent, one per bin)
        arrow_color = theme.highlight_fill
        marker = canvas.define_marker(color=arrow_color, size=5.5,
                                      name_hint="qArr")
        for b, v in rep_per_bin.items():
            sx = x + (v + 1) / 2 * W
            # pick a spot in the upper half for the sample tip
            sy = y + 16 + (b * 13) % int(max(14, H * 0.45))
            bin_cx = x + (b + 0.5) * W / self.n_bins
            canvas.line(sx, sy, bin_cx, axis_y - 2,
                       stroke=arrow_color, stroke_width=0.9,
                       dasharray="2.5,2", marker_end=marker, opacity=0.85)
            # highlight the representative sample
            canvas.circle(sx, sy, 2.3, fill=arrow_color, opacity=0.95)
        # Bin labels below axis
        for i in range(self.n_bins):
            bx = x + (i + 0.5) * W / self.n_bins
            canvas.text(
                bx, axis_y + theme.size_px("tiny") * 1.5,
                str(i - self.n_bins // 2),
                size=theme.size_px("tiny"),
                fill=theme.text_muted, anchor="middle",
            )
