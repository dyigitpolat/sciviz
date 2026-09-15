"""Funnel: a staged narrowing of one population.

A funnel is the shape of *selection*: a set enters at the top, a rule
keeps part of it, and the survivors leave at the bottom. Drawing that as
a row of boxes with counts loses the one thing the reader wants, which is
how much was dropped; drawing it as a taper puts the ratio in the
silhouette itself.

Every stage is ``(label, value)``. The first value sets the full width,
so each later stage's edge width is its share of the population that
entered. A straight *neck* below the last stage keeps a two-stage funnel
reading as a funnel rather than as one trapezoid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass(frozen=True)
class FunnelStage:
    """One level of a :class:`Funnel`.

    Parameters
    ----------
    label : str
        The name of the population at this level. Empty means unlabelled.
    value : float
        Its size, in any unit shared by the stages. Non-negative.
    color : optional
        Per-stage override of the funnel's role colour.
    """

    label: str
    value: float
    color: object = None


StageLike = Union[FunnelStage, Tuple]


class Funnel(Element):
    """A tapering silhouette over a sequence of shrinking stages.

    Parameters
    ----------
    stages : sequence
        Two or more :class:`FunnelStage` values, or ``(label, value)`` /
        ``(label, value, color)`` tuples. Values need not decrease, but a
        funnel that widens is usually a sign the stages are in the wrong
        order.
    width, height : float
        The taper's own extent, before labels.
    role : ColorRef or str
        The colour family of the body (filled soft, stroked solid).
    label_position : {"right", "none"}
        Where stage labels are written. ``"right"`` puts each label beside
        its own edge and widens the measured box by the label column.
    show_values : bool
        Whether the value is written after the label.
    value_format : str
        ``format`` spec for the value, e.g. ``"{:g}"`` or ``"{:.0f}"``.
    neck_ratio : float
        Fraction of the height given to a straight neck under the last
        stage. ``0.0`` ends the figure on the taper.
    min_ratio : float
        Floor on an edge's width as a fraction of the widest edge, so a
        stage that keeps almost nothing is still visible as an edge.
    """

    def __init__(self, stages: Sequence[StageLike], *,
                 width: float = 64.0, height: float = 40.0,
                 role="primary",
                 label_position: str = "right",
                 show_values: bool = True,
                 value_format: str = "{:g}",
                 neck_ratio: float = 0.22,
                 min_ratio: float = 0.08,
                 text_size: str = "tiny"):
        self.stages = [self._normalise(s) for s in stages]
        if len(self.stages) < 2:
            raise ValueError("Funnel needs at least two stages")
        if any(s.value < 0 for s in self.stages):
            raise ValueError("Funnel stage values must be non-negative")
        if label_position not in ("right", "none"):
            raise ValueError('Funnel label_position must be "right" or "none"')
        self.width = float(width)
        self.height = float(height)
        self.role = role
        self.label_position = label_position
        self.show_values = bool(show_values)
        self.value_format = value_format
        self.neck_ratio = max(0.0, min(0.6, float(neck_ratio)))
        self.min_ratio = max(0.0, min(0.9, float(min_ratio)))
        self.text_size = text_size

    # -- data ----------------------------------------------------------

    @staticmethod
    def _normalise(s: StageLike) -> FunnelStage:
        if isinstance(s, FunnelStage):
            return s
        if len(s) == 2:
            return FunnelStage(str(s[0]), float(s[1]))
        if len(s) == 3:
            return FunnelStage(str(s[0]), float(s[1]), s[2])
        raise ValueError(f"Funnel stage: (label, value[, color]); got {s!r}")

    def _caption(self, stage: FunnelStage) -> str:
        if not self.show_values:
            return stage.label
        value = self.value_format.format(stage.value)
        return f"{stage.label} {value}".strip()

    def _ratios(self) -> list[float]:
        top = max((s.value for s in self.stages), default=0.0)
        if top <= 0:
            return [1.0] * len(self.stages)
        return [max(self.min_ratio, s.value / top) for s in self.stages]

    # -- layout --------------------------------------------------------

    def _label_width(self, theme: Theme) -> float:
        if self.label_position == "none":
            return 0.0
        widths = [theme.text_width(self._caption(s), self.text_size)
                  for s in self.stages]
        return max(widths, default=0.0) + theme.unit * 0.7

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.width + self._label_width(theme), self.height)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        ratios = self._ratios()
        n = len(self.stages)
        taper_h = self.height * (1.0 - self.neck_ratio)
        band_h = taper_h / (n - 1)
        cx = x + self.width / 2
        body = theme.color_of(self.role)
        soft = (theme.color_of(self.role.soft())
                if hasattr(self.role, "soft")
                else theme.role(str(self.role), "soft"))

        def edge(i: int) -> Tuple[float, float]:
            half = self.width * ratios[i] / 2
            return cx - half, cx + half

        for i in range(n - 1):
            top_y = y + i * band_h
            bot_y = top_y + band_h
            l0, r0 = edge(i)
            l1, r1 = edge(i + 1)
            fill = soft
            if self.stages[i].color is not None:
                ref = self.stages[i].color
                fill = (theme.color_of(ref.soft()) if hasattr(ref, "soft")
                        else theme.role(str(ref), "soft"))
            canvas.polygon([(l0, top_y), (r0, top_y), (r1, bot_y), (l1, bot_y)],
                           fill=fill, stroke=body,
                           stroke_width=theme.hairline)

        if self.neck_ratio > 0:
            l1, r1 = edge(n - 1)
            neck_y = y + taper_h
            canvas.rect(l1, neck_y, max(r1 - l1, 0.4),
                        self.height - taper_h,
                        fill=soft, stroke=body, stroke_width=theme.hairline)

        if self.label_position == "none":
            return
        size = theme.size_px(self.text_size)
        tx = x + self.width + theme.unit * 0.55
        for i, stage in enumerate(self.stages):
            ly = y + min(i * band_h, self.height)
            canvas.text(tx, ly + size * 0.36, self._caption(stage),
                        size=size, fill=theme.color_of("text_muted"),
                        anchor="start")
