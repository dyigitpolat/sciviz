"""Machine-learning specific elements built on top of the sciviz primitives.

These encapsulate common visualisation patterns that would be tedious to
assemble by hand:

* :class:`Crossbar`    -- analog in-memory compute crossbar with DAC/ADC peripherals.
* :class:`NNLayer`     -- a block representing one layer of a neural network.
* :class:`Pipeline`    -- a left-to-right sequence of layers joined by arrows.
* :class:`Tensor`      -- an axonometric projection of an N-D tensor shape.
* :class:`AttentionHead` -- attention-as-MatMul pipeline (Q, K, V, softmax).
* :class:`LoRA`        -- the W + B @ A low-rank adaptation visualisation.
* :class:`QuantBins`   -- FP -> INTn quantisation histogram.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple, Union

from .core import Element, BBox, Canvas, Theme
from .elements import _normalise_matrix, Text, TextBlock, Box, MiniGrid
from .layout import Row, Column, Stack, Spacer


# ---------------------------------------------------------------------------
# Crossbar
# ---------------------------------------------------------------------------


class NNLayer(Box):
    """A labeled block representing one layer of a neural network.

    Provides opinionated colour defaults based on the ``kind``:

    * ``"input"`` / ``"output"`` -- slate grey
    * ``"dense"``                -- blue
    * ``"conv"``                 -- emerald
    * ``"attn"``                 -- violet
    * ``"norm"``                 -- amber
    * ``"softmax"`` / ``"loss"`` -- red
    * ``"embed"``                -- teal
    """

    _KIND_STYLE = {
        "input":   dict(fill="#e2e8f0", stroke="#64748b", text_color="text"),
        "output":  dict(fill="#e2e8f0", stroke="#64748b", text_color="text"),
        "dense":   dict(fill="primary_fill", stroke="primary", text_color="inverse"),
        "linear":  dict(fill="primary_fill", stroke="primary", text_color="inverse"),
        "conv":    dict(fill="accent_fill", stroke="accent", text_color="inverse"),
        "attn":    dict(fill="#8b5cf6", stroke="#6d28d9", text_color="inverse"),
        "mha":     dict(fill="#8b5cf6", stroke="#6d28d9", text_color="inverse"),
        "norm":    dict(fill="warning_fill", stroke="warning", text_color="inverse"),
        "softmax": dict(fill="highlight_fill", stroke="highlight", text_color="inverse"),
        "loss":    dict(fill="highlight_fill", stroke="highlight", text_color="inverse"),
        "embed":   dict(fill="#14b8a6", stroke="#0f766e", text_color="inverse"),
        "residual": dict(fill="#ffffff", stroke="text_muted", text_color="text"),
    }

    def __init__(self, label: str, *, kind: str = "dense",
                 shape: Optional[str] = None, width: Optional[float] = None,
                 height: Optional[float] = None, dashed: bool = False):
        style = self._KIND_STYLE.get(kind, self._KIND_STYLE["dense"])
        super().__init__(
            label=label, width=width, height=height,
            fill=style["fill"], stroke=style["stroke"],
            text_color=style["text_color"],
            sub_label=shape, sub_color="muted",
            dashed=dashed, radius=6,
        )
        self.kind = kind


# ---------------------------------------------------------------------------
# Pipeline (horizontal sequence of layers + arrows)
# ---------------------------------------------------------------------------

class Pipeline(Element):
    """A sequence of blocks connected by arrows.

    Parameters
    ----------
    stages : list of Element or str
        If a string is given, it is wrapped in an :class:`NNLayer` with kind
        "dense".  Tuples ``(label, kind)`` or ``(label, kind, shape)`` also work.
    direction : str
        ``"right"`` (default), ``"down"``.
    gap : str or float
    arrow_labels : list of str, optional
        Labels to place between stages (must be len(stages) - 1).
    """

    def __init__(self, stages: Sequence, *,
                 direction: str = "right",
                 gap: Union[str, float] = "lg",
                 arrow_labels: Optional[Sequence[Optional[str]]] = None):
        self.stages = [self._coerce(s) for s in stages]
        self.direction = direction
        self.gap = gap
        self.arrow_labels = list(arrow_labels) if arrow_labels else None

    @staticmethod
    def _coerce(s):
        if isinstance(s, Element):
            return s
        if isinstance(s, str):
            return NNLayer(s, kind="dense")
        if isinstance(s, tuple):
            if len(s) == 2:
                return NNLayer(s[0], kind=s[1])
            if len(s) == 3:
                return NNLayer(s[0], kind=s[1], shape=s[2])
        raise TypeError(f"Cannot coerce {s!r} into an Element")

    def _arrow(self, idx: int, theme: Theme) -> Element:
        from .elements import Arrow
        lbl = None
        if self.arrow_labels and idx < len(self.arrow_labels):
            lbl = self.arrow_labels[idx]
        return Arrow(label=lbl, direction=self.direction,
                     length=theme.gap_px(self.gap))

    def _as_row_or_column(self, theme: Theme) -> Element:
        Container = Row if self.direction == "right" else Column
        parts = []
        for i, stage in enumerate(self.stages):
            parts.append(stage)
            if i < len(self.stages) - 1:
                parts.append(self._arrow(i, theme))
        return Container(*parts, gap="sm", align="center")

    def measure(self, theme: Theme) -> BBox:
        return self._as_row_or_column(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._as_row_or_column(theme).render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# Tensor -- axonometric projection of a shape
# ---------------------------------------------------------------------------

class Tensor(Element):
    """Axonometric view of a tensor's shape.

    For 1D -> 3D tensors it draws a cuboid with the axis sizes labeled on
    each visible face.  Higher-dimensional tensors fall back to a stacked
    visualisation of the trailing three dims.

    Parameters
    ----------
    shape : tuple[int, ...]
    labels : tuple[str, ...], optional
        Per-axis labels.  Defaults to ``("D\u2080", "D\u2081", ...)``.
    title : str, optional
    unit : float
        Scale factor for converting dim size into pixels.  Use ``None`` to
        let sciviz auto-scale so the cuboid fits a ~120 px envelope.
    """

    def __init__(self, shape: Sequence[int], *,
                 labels: Optional[Sequence[str]] = None,
                 title: Optional[str] = None,
                 palette: str = "blues",
                 unit: Optional[float] = None,
                 highlight_axis: Optional[int] = None):
        self.shape = tuple(shape)
        self.labels = tuple(labels) if labels else None
        self.title = title
        self.palette = palette
        self.unit = unit
        self.highlight_axis = highlight_axis

    def _axis_labels(self) -> List[str]:
        if self.labels is not None:
            return list(self.labels)
        subs = "\u2080\u2081\u2082\u2083\u2084\u2085"
        return [f"D{subs[i]}" if i < len(subs) else f"D{i}"
                for i in range(len(self.shape))]

    def _scaled(self) -> List[float]:
        """Convert shape entries into drawing units (so large dims don't dominate)."""
        if self.unit is not None:
            return [float(s) * self.unit for s in self.shape]
        # Log-ish scaling so dims like 768 and 64 both fit reasonably
        import math as _m
        scaled = []
        for s in self.shape:
            scaled.append(20.0 + 40.0 * _m.log2(max(s, 2)) / 10.0)
        return scaled

    def _axonometric_params(self):
        """Return (dx, dy) offset for depth axis (axonometric projection)."""
        return (14.0, -8.0)

    def _layout(self, theme: Theme):
        """Compute the key layout measurements for the cuboid.

        Returns a dict with the intrinsic width/height/depth of the front
        face, the projected depth offset in px (dx_off, dy_off), and the
        total ``(total_w, total_h, top_offset)`` where ``top_offset`` is
        how far the front face must sit below ``y + title_h`` so that the
        back face (drawn upward-and-right) doesn't poke above the bbox.
        """
        sizes = self._scaled()
        ndim = len(sizes)
        if ndim >= 3:
            w_sz, h_sz, d_sz = sizes[-3], sizes[-2], sizes[-1]
        elif ndim == 2:
            w_sz, h_sz, d_sz = sizes[-2], sizes[-1], 0.0
        else:
            w_sz, h_sz, d_sz = sizes[0], 20.0, 0.0
        dx, dy = self._axonometric_params()
        depth_scale = (d_sz / 20.0) if d_sz else 0.0
        dx_off = dx * depth_scale
        dy_off = dy * depth_scale              # negative (back goes up)
        top_offset = abs(dy_off)                # space reserved above front face
        total_w = w_sz + dx_off
        total_h = h_sz + top_offset             # front face + room for back face
        return dict(w_sz=w_sz, h_sz=h_sz, d_sz=d_sz,
                    dx_off=dx_off, dy_off=dy_off,
                    top_offset=top_offset,
                    total_w=total_w, total_h=total_h)

    def measure(self, theme: Theme) -> BBox:
        L = self._layout(theme)
        title_h = theme.text_height("small") + theme.unit * 0.5 if self.title else 0.0
        bottom_lbl_h = theme.text_height("tiny") + theme.unit * 0.4
        # reserve a little extra for the D-label that sits to the right of
        # the back face (it's drawn to the right, doesn't grow h, but we pad
        # the right side so it doesn't get clipped by a sibling)
        right_pad = 36.0 if L["d_sz"] else 0.0
        return BBox(max(L["total_w"] + right_pad, 72.0),
                    max(L["total_h"], 40.0) + title_h + bottom_lbl_h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        L = self._layout(theme)
        axes = self._axis_labels()
        ndim = len(self.shape)
        box_size = self.measure(theme)
        title_h = theme.text_height("small") + theme.unit * 0.5 if self.title else 0.0

        if self.title:
            canvas.text(
                x + box_size.w / 2, y + theme.size_px("small") * 0.88,
                self.title, size=theme.size_px("small"),
                fill=theme.text, weight="600", anchor="middle",
            )

        if ndim >= 3:
            w_lbl, h_lbl, d_lbl = axes[-3], axes[-2], axes[-1]
            w_val, h_val, d_val = self.shape[-3], self.shape[-2], self.shape[-1]
        elif ndim == 2:
            w_lbl, h_lbl, d_lbl = axes[-2], axes[-1], ""
            w_val, h_val, d_val = self.shape[-2], self.shape[-1], 0
        else:
            w_lbl, h_lbl, d_lbl = axes[0], "", ""
            w_val, h_val, d_val = self.shape[0], 0, 0

        w_sz, h_sz, d_sz = L["w_sz"], L["h_sz"], L["d_sz"]
        dx_off, dy_off = L["dx_off"], L["dy_off"]
        top_offset = L["top_offset"]

        # Front face top-left: centred horizontally in the drawing area,
        # placed below title + top_offset so the back face doesn't overflow.
        right_pad = 36.0 if d_sz else 0.0
        inner_w = max(L["total_w"] + right_pad, 72.0)
        # horizontally center on the front+depth footprint (not the right_pad)
        ox = x + (inner_w - L["total_w"]) / 2
        oy = y + title_h + top_offset

        # Front face
        front_fill = theme.color_scale(0.5, self.palette, 0, 1)
        front_stroke = theme.color_scale(0.9, self.palette, 0, 1)
        canvas.rect(ox, oy, w_sz, h_sz, fill=front_fill,
                   stroke=front_stroke, stroke_width=1.0, opacity=0.85)
        if d_sz:
            # Top face (parallelogram)
            pts = [(ox, oy), (ox + dx_off, oy + dy_off),
                   (ox + w_sz + dx_off, oy + dy_off), (ox + w_sz, oy)]
            top_fill = theme.color_scale(0.75, self.palette, 0, 1)
            canvas.polygon(pts, fill=top_fill, stroke=front_stroke,
                          stroke_width=1.0, opacity=0.85)
            # Right face
            pts = [(ox + w_sz, oy), (ox + w_sz + dx_off, oy + dy_off),
                   (ox + w_sz + dx_off, oy + h_sz + dy_off), (ox + w_sz, oy + h_sz)]
            right_fill = theme.color_scale(0.3, self.palette, 0, 1)
            canvas.polygon(pts, fill=right_fill, stroke=front_stroke,
                          stroke_width=1.0, opacity=0.85)

        # Axis labels
        lbl_sz = theme.size_px("tiny")
        # Width axis: centered under front bottom
        canvas.text(
            ox + w_sz / 2, oy + h_sz + lbl_sz * 1.2,
            f"{w_lbl}={w_val}", size=lbl_sz, fill=theme.text_muted,
            anchor="middle",
        )
        # Height axis: to the left of front face, rotated 90 degrees
        canvas.raw(
            f'<text x="{ox - theme.unit * 0.3}" y="{oy + h_sz / 2}" '
            f'font-size="{lbl_sz}" fill="{theme.text_muted}" '
            f'text-anchor="middle" '
            f'transform="rotate(-90 {ox - theme.unit * 0.3} {oy + h_sz / 2})">'
            f'{h_lbl}={h_val}</text>'
        )
        if d_sz:
            # Depth axis: to the right of the back face
            canvas.text(
                ox + w_sz + dx_off + theme.unit * 0.4,
                oy + dy_off + lbl_sz * 0.5,
                f"{d_lbl}={d_val}", size=lbl_sz,
                fill=theme.text_muted,
            )


