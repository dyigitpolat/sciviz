"""Declarative part-to-whole donut chart with automatic labels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text
from ..palette import Palette


@dataclass(frozen=True)
class Part:
    """One part of a whole.

    ``key`` controls stable automatic colour. ``group`` is optional semantic
    metadata used by :class:`GroupSummary`; no aggregate is hand-maintained.
    """

    key: str
    value: float
    label: Optional[str] = None
    role: object = "auto"
    variant: str = "fill"
    group: Optional[str] = None


@dataclass(frozen=True)
class GroupSummary:
    """Derived center summary for one or more :attr:`Part.group` values."""

    groups: tuple[str, ...]
    label: Optional[str] = None
    format: str = ".0f"


class DonutChart(Element):
    """A true part-to-whole ring with collision-managed labels.

    Values are normalized to their sum unless ``total`` is provided, in which
    case exact closure is validated. Outside labels and leaders are included in
    the measured bbox.
    """

    def __init__(
        self,
        parts: Sequence[Part],
        *,
        total: Optional[float] = None,
        inner_ratio: float = 0.58,
        start_angle: float = -90.0,
        direction: str = "clockwise",
        labels: Optional[str] = "outside",
        label_format: Union[str, Callable[[Part, float], str]] = "{label} {percent:g}%",
        leaders: bool = True,
        center: Optional[Union[Element, str, GroupSummary]] = None,
        size: str = "md",
    ):
        self.parts = list(parts)
        if not self.parts:
            raise ValueError("DonutChart requires at least one part")
        if any(float(part.value) < 0 for part in self.parts):
            raise ValueError("DonutChart values must be nonnegative")
        summed = sum(float(part.value) for part in self.parts)
        if summed <= 0:
            raise ValueError("DonutChart total must be positive")
        if total is not None:
            total = float(total)
            if total <= 0 or not math.isclose(summed, total, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(
                    f"DonutChart parts sum to {summed:g}, not explicit total {total:g}")
        if not (0.15 <= float(inner_ratio) < 0.9):
            raise ValueError("inner_ratio must be in [0.15, 0.9)")
        if direction not in ("clockwise", "counterclockwise"):
            raise ValueError("direction must be 'clockwise' or 'counterclockwise'")
        if labels not in ("outside", "inside", "legend", None):
            raise ValueError("labels must be outside, inside, legend, or None")
        if size not in ("sm", "md", "lg"):
            raise ValueError("size must be sm, md, or lg")
        for part in self.parts:
            if part.variant not in ("fill", "soft"):
                raise ValueError("Part.variant must be 'fill' or 'soft'")
        self.total = summed
        self.inner_ratio = float(inner_ratio)
        self.start_angle = float(start_angle)
        self.direction = direction
        self.labels = labels
        self.label_format = label_format
        self.leaders = bool(leaders)
        self.center = center
        self.size = size

    def _radius(self, theme: Theme) -> float:
        return theme.unit * {"sm": 6.5, "md": 8.5, "lg": 11.0}[self.size]

    def _percent(self, part: Part) -> float:
        return float(part.value) / self.total * 100.0

    def _label(self, part: Part) -> str:
        percent = self._percent(part)
        label = part.label or part.key
        if callable(self.label_format):
            return str(self.label_format(part, percent))
        return self.label_format.format(
            key=part.key, label=label, value=float(part.value), percent=percent)

    def _role(self, part: Part):
        role = Palette.next(part.key) if part.role == "auto" else part.role
        if part.variant == "soft" and hasattr(role, "soft"):
            return role.soft()
        return role

    def _center_element(self) -> Optional[Element]:
        if self.center is None:
            return None
        if isinstance(self.center, Element):
            return self.center
        if isinstance(self.center, str):
            return Text(self.center, size="small", weight="700", align="center")
        if isinstance(self.center, GroupSummary):
            by_group = {
                group: sum(float(part.value) for part in self.parts
                           if part.group == group)
                for group in self.center.groups
            }
            values = [by_group[group] / self.total * 100.0
                      for group in self.center.groups]
            value_text = " / ".join(format(value, self.center.format)
                                    for value in values)
            text = (f"{self.center.label}\n{value_text}"
                    if self.center.label else value_text)
            return Text(text, size="small", weight="700", align="center")
        raise TypeError("center must be an Element, string, GroupSummary, or None")

    def _angles(self) -> list[tuple[float, float]]:
        sign = 1.0 if self.direction == "clockwise" else -1.0
        cursor = self.start_angle
        out = []
        for part in self.parts:
            span = sign * 360.0 * float(part.value) / self.total
            out.append((cursor, cursor + span))
            cursor += span
        return out

    @staticmethod
    def _point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
        radians = math.radians(angle)
        return cx + radius * math.cos(radians), cy + radius * math.sin(radians)

    def _sector_path(self, cx: float, cy: float, outer: float, inner: float,
                     start: float, end: float) -> str:
        span = abs(end - start)
        sweep = 1 if end >= start else 0
        reverse = 0 if sweep else 1
        o0 = self._point(cx, cy, outer, start)
        o1 = self._point(cx, cy, outer, end)
        i1 = self._point(cx, cy, inner, end)
        i0 = self._point(cx, cy, inner, start)
        large = 1 if span > 180 else 0
        return (
            f"M {o0[0]:.3f} {o0[1]:.3f} "
            f"A {outer:.3f} {outer:.3f} 0 {large} {sweep} {o1[0]:.3f} {o1[1]:.3f} "
            f"L {i1[0]:.3f} {i1[1]:.3f} "
            f"A {inner:.3f} {inner:.3f} 0 {large} {reverse} {i0[0]:.3f} {i0[1]:.3f} Z"
        )

    def _outside_layout(self, theme: Theme, radius: float):
        angles = self._angles()
        line_h = theme.text_height("small") * 1.15
        sides = {"left": [], "right": []}
        for index, (part, (start, end)) in enumerate(zip(self.parts, angles)):
            middle = start + (end - start) / 2.0
            side = "right" if math.cos(math.radians(middle)) >= 0 else "left"
            desired = math.sin(math.radians(middle)) * radius
            sides[side].append([desired, index, middle, self._label(part)])
        for items in sides.values():
            items.sort(key=lambda item: item[0])
            minimum = -radius
            for item in items:
                item[0] = max(item[0], minimum)
                minimum = item[0] + line_h
            if items and items[-1][0] > radius:
                shift = items[-1][0] - radius
                for item in reversed(items):
                    item[0] -= shift
                    shift = max(0.0, (item[0] + line_h) - radius)
        return sides

    def _extents(self, theme: Theme):
        radius = self._radius(theme)
        pad = theme.unit
        if self.labels == "outside":
            sides = self._outside_layout(theme, radius)
            left_w = max((theme.text_width(item[3], "small")
                          for item in sides["left"]), default=0.0)
            right_w = max((theme.text_width(item[3], "small")
                           for item in sides["right"]), default=0.0)
            leader = theme.unit * 2.2 if self.leaders else theme.unit * 0.8
        elif self.labels == "legend":
            left_w = 0.0
            right_w = max(theme.text_width(self._label(part), "small")
                          for part in self.parts) + theme.unit * 2.0
            leader = theme.unit
        else:
            left_w = right_w = leader = 0.0
        width = left_w + right_w + 2 * radius + 2 * leader + 2 * pad
        rows_h = len(self.parts) * theme.text_height("small") * 1.15
        height = max(2 * radius + 2 * pad,
                     rows_h + 2 * pad if self.labels == "legend" else 0.0)
        return radius, left_w, right_w, leader, pad, width, height

    def measure(self, theme: Theme) -> BBox:
        *_, width, height = self._extents(theme)
        return BBox(width, height)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        radius, left_w, _right_w, leader, pad, width, height = self._extents(theme)
        cx = x + pad + left_w + leader + radius
        cy = y + height / 2.0
        inner = radius * self.inner_ratio
        angles = self._angles()

        for part, (start, end) in zip(self.parts, angles):
            color = theme.color_of(self._role(part))
            spans = ((start, (start + end) / 2.0), ((start + end) / 2.0, end)) \
                if abs(end - start) >= 359.999 else ((start, end),)
            for sub_start, sub_end in spans:
                canvas.path(
                    self._sector_path(cx, cy, radius, inner, sub_start, sub_end),
                    fill=color, stroke=theme.color_of("bg"),
                    stroke_width=theme.hairline,
                    ink_bbox=(
                        cx - radius,
                        cy - radius,
                        cx + radius,
                        cy + radius,
                    ),
                )

        if self.labels == "outside":
            sides = self._outside_layout(theme, radius)
            for side, items in sides.items():
                sign = 1 if side == "right" else -1
                for relative_y, _index, middle, label in items:
                    sx, sy = self._point(cx, cy, radius, middle)
                    elbow_x = cx + sign * (radius + theme.unit * 0.9)
                    label_x = cx + sign * (radius + leader)
                    label_y = cy + relative_y
                    if self.leaders:
                        canvas.line(sx, sy, elbow_x, label_y,
                                    stroke=theme.color_of("muted"),
                                    stroke_width=theme.hairline)
                        canvas.line(elbow_x, label_y, label_x, label_y,
                                    stroke=theme.color_of("muted"),
                                    stroke_width=theme.hairline)
                    canvas.text(label_x + sign * theme.unit * 0.25,
                                label_y + theme.size_px("small") * 0.33,
                                label, size=theme.size_px("small"),
                                fill=theme.color_of("text"),
                                anchor="start" if side == "right" else "end")
        elif self.labels == "inside":
            for part, (start, end) in zip(self.parts, angles):
                middle = start + (end - start) / 2.0
                px, py = self._point(cx, cy, (radius + inner) / 2.0, middle)
                color = theme.color_of(self._role(part))
                canvas.text(px, py, f"{self._percent(part):g}%",
                            size=theme.size_px("tiny"),
                            fill=theme.text_on(color), weight="700",
                            anchor="middle", baseline="middle")
        elif self.labels == "legend":
            lx = cx + radius + leader
            line_h = theme.text_height("small") * 1.15
            ly = cy - line_h * (len(self.parts) - 1) / 2.0
            for part in self.parts:
                color = theme.color_of(self._role(part))
                canvas.circle(lx, ly, theme.unit * 0.35, fill=color, stroke="none")
                canvas.text(lx + theme.unit, ly, self._label(part),
                            size=theme.size_px("small"),
                            fill=theme.color_of("text"), baseline="middle")
                ly += line_h

        center = self._center_element()
        if center is not None:
            measured = center.measure(theme)
            center.render(canvas, cx - measured.w / 2.0,
                          cy - measured.h / 2.0, theme)


__all__ = ["Part", "GroupSummary", "DonutChart"]
