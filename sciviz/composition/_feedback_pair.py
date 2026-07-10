"""FeedbackPair: two coupled components with observation/action channels."""

from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme
from ..elements import Arrow
from ..layout import Column, Row
from ._anchor import Anchor
from ._loopicon import LoopIcon
from ._region import Region


class _ChannelBand(Element):
    """Keep coupled components on one semantic centre-to-centre pitch.

    The visible shaft stays compact.  If either component is shorter, the
    band absorbs the difference as air around the shaft instead of moving
    that component's centre and turning peer-to-peer links diagonal.
    """

    def __init__(self, child: Element, top: Element, bottom: Element, *,
                 center_pitch_units: float):
        self.child = child
        self.top = top
        self.bottom = bottom
        self.center_pitch_units = float(center_pitch_units)
        self._min_w = 0.0
        self._min_h = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))
        if min_w:
            self.child.inflate_to(min_w, 0.0)

    def measure(self, theme: Theme) -> BBox:
        child = self.child.measure(theme)
        top = self.top.measure(theme)
        bottom = self.bottom.measure(theme)
        pitch = theme.unit * self.center_pitch_units
        gap = max(child.h, pitch - top.h / 2.0 - bottom.h / 2.0)
        return BBox(max(child.w, self._min_w), max(gap, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        size = self.measure(theme)
        child = self.child.measure(theme)
        self.child.render(
            canvas,
            x + (size.w - child.w) / 2.0,
            y + (size.h - child.h) / 2.0,
            theme,
        )


class FeedbackPair(Element):
    """A named two-component feedback loop with exposed semantic anchors.

    The pair owns its loop boundary, rollout marker, and opposing channel
    arrows. Authors provide component content and channel labels; side
    branches connect to :attr:`top_anchor` / :attr:`bottom_anchor` without
    knowing any coordinates. Its content alignment landmark is the bottom
    component, so an auxiliary model in a sibling Row naturally aligns with
    the policy/VLA block rather than the pair's geometric midpoint.
    """

    shape_peer_boundary = True
    _CENTER_PITCH_UNITS = 13.0

    def __init__(self, key: str, top: Element, bottom: Element, *,
                 forward_label: Optional[str] = "O",
                 return_label: Optional[str] = "A",
                 loop_label: Optional[str] = "𝒯", color="border",
                 boundary: bool = True):
        if not key:
            raise ValueError("FeedbackPair.key must be non-empty")
        if not isinstance(top, Element) or not isinstance(bottom, Element):
            raise TypeError("FeedbackPair top and bottom must be Elements")
        self.top_anchor = f"{key}_top"
        self.bottom_anchor = f"{key}_bottom"
        self.top = Anchor(self.top_anchor, top)
        self.bottom = Anchor(self.bottom_anchor, bottom)
        channel_elements = []
        if forward_label is not None:
            forward_symbolic = (
                " " not in forward_label and len(forward_label) <= 3
            )
            channel_elements.append(Arrow(
                    direction="down", length="md", label=forward_label,
                    color=color, label_color=color, head="end",
                    italic=forward_symbolic,
                    label_weight=("normal" if forward_symbolic else "600"),
                    # Paired channel labels sit outside the two shafts;
                    # a single one-way coupling reads naturally on the
                    # right, leaving its source-side corridor clear.
                    label_side=("left" if return_label is not None
                                else "right")))
        if return_label is not None:
            return_symbolic = (
                " " not in return_label and len(return_label) <= 3
            )
            channel_elements.append(Arrow(
                    direction="up", length="md", label=return_label,
                    color=color, label_color=color, head="end",
                    italic=return_symbolic,
                    label_weight=("normal" if return_symbolic else "600"),
                    label_side="right"))
        if not channel_elements:
            raise ValueError("FeedbackPair requires at least one channel")
        channel_row = Row(
            *channel_elements,
            gap="sm",
            align="center",
        )
        self.channels = _ChannelBand(
            channel_row,
            self.top,
            self.bottom,
            center_pitch_units=self._CENTER_PITCH_UNITS,
        )
        self.core = Column(
            self.top,
            self.channels,
            self.bottom,
            gap="none",
            align="center",
        )
        self.boundary = bool(boundary)
        self.child = (
            Region(
                self.core,
                label=loop_label,
                color=color,
                fill="white",
                dashed=False,
                corner_badge=(LoopIcon(size=18.0, color=color)
                              if loop_label is not None else None),
                label_size="label",
            )
            if self.boundary else self.core
        )

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.child.inflate_to(min_w, min_h)

    def measure(self, theme: Theme) -> BBox:
        return self.child.measure(theme)

    def _bottom_content_in_core(self, theme: Theme):
        sizes = [child.measure(theme) for child in self.core.children]
        content = [child.content_bbox(theme) for child in self.core.children]
        left_extent, _right_extent = self.core._cross_extents(sizes, content)
        bottom_cb = content[-1]
        bx = left_extent - bottom_cb[2] / 2
        by = sizes[0].h + sizes[1].h + bottom_cb[1]
        return (bx, by, bottom_cb[2], bottom_cb[3])

    def content_bbox(self, theme: Theme):
        # Region.content_bbox gives the core's rendered origin inside the
        # outer loop boundary. Translate the bottom component landmark into
        # the FeedbackPair frame for sibling Row alignment.
        if self.boundary:
            core_x, core_y, _core_w, _core_h = self.child.content_bbox(theme)
        else:
            core_x, core_y = 0.0, 0.0
        bx, by, bw, bh = self._bottom_content_in_core(theme)
        return (core_x + bx, core_y + by, bw, bh)

    def primary_anchor_bbox(self, theme: Theme):
        return self.content_bbox(theme)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        self.child.render(canvas, x, y, theme)
