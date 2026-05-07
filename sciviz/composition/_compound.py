"""Compound layout primitives for semantic cards and step cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from ..core import BBox, Canvas, Element, Theme
from ..elements import ConditionGlyph, Text, TextBlock
from ..elements._obstacles import _register_implicit_obstacle
from ..layout import Column, Row


def _pad_px(theme: Theme, padding) -> float:
    if isinstance(padding, (int, float)):
        return float(padding)
    return theme.gap_px(padding)


def _soft(theme: Theme, role) -> str:
    return theme.color_of(role.soft()) if hasattr(role, "soft") else theme.role(str(role), "soft")


@dataclass(frozen=True)
class ConditionSpec:
    """Legend-aware conditional marker."""

    kind: str
    label: str


class Card(Element):
    """A titled card with a role-coloured header and soft body."""

    def __init__(self, header: Element | str, body: Element, *, role,
                 footer: Optional[Element] = None, padding="sm",
                 radius: Optional[float] = None, dashed: bool = False):
        self.header = header if isinstance(header, Element) else Text(str(header), weight="700")
        self.body = body
        self.footer = footer
        self.role = role
        self.padding = padding
        self.radius = radius
        self.dashed = dashed
        self._min_w = 0.0
        self._min_h = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))
        pad = 12.0
        inner_w = max(0.0, self._min_w - 2 * pad)
        inner_h = max(0.0, self._min_h - 3 * pad)
        self.body.inflate_to(inner_w, inner_h)

    def measure(self, theme: Theme) -> BBox:
        pad = _pad_px(theme, self.padding)
        header = self.header.measure(theme)
        body = self.body.measure(theme)
        footer = self.footer.measure(theme) if self.footer else BBox(0, 0)
        header_h = header.h + pad * 1.2
        footer_h = (footer.h + pad) if self.footer else 0.0
        w = max(header.w, body.w, footer.w) + 2 * pad
        h = header_h + body.h + footer_h + 2 * pad
        return BBox(max(w, self._min_w), max(h, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = _pad_px(theme, self.padding)
        radius = self.radius if self.radius is not None else theme.panel_radius * 2
        stroke = theme.color_of(self.role)
        canvas.rect(x, y, size.w, size.h, fill=_soft(theme, self.role),
                    stroke=stroke, stroke_width=theme.hairline, rx=radius,
                    dasharray="3,2" if self.dashed else None)
        _register_implicit_obstacle(x, y, size.w, size.h)

        header_size = self.header.measure(theme)
        header_h = header_size.h + pad * 1.2
        canvas.rect(x, y, size.w, header_h, fill=stroke, stroke=stroke,
                    stroke_width=theme.hairline, rx=radius)
        self.header.render(canvas, x + pad, y + (header_h - header_size.h) / 2, theme)

        body_size = self.body.measure(theme)
        body_x = x + (size.w - body_size.w) / 2
        body_y = y + header_h + pad
        self.body.render(canvas, body_x, body_y, theme)
        if self.footer:
            footer = self.footer.measure(theme)
            self.footer.render(canvas, x + (size.w - footer.w) / 2,
                               y + size.h - pad - footer.h, theme)


class EqualGrid(Element):
    """Grid that broadcasts the widest/tallest child cell to all children."""

    def __init__(self, *children: Element, columns: Optional[int] = None,
                 gap="md", equal: str = "both", align: str = "center"):
        self.children = [c for c in children if c is not None]
        self.columns = columns
        self.gap = gap
        self.equal = equal
        self.align = align
        self._cell: Optional[BBox] = None

    def _columns(self) -> int:
        if self.columns is not None:
            return max(1, int(self.columns))
        return max(1, int(len(self.children) ** 0.5 + 0.999))

    def _normalise(self, theme: Theme) -> list[BBox]:
        if not self.children:
            return []
        sizes = [c.measure(theme) for c in self.children]
        target_w = max(s.w for s in sizes) if self.equal in ("both", "width") else 0.0
        target_h = max(s.h for s in sizes) if self.equal in ("both", "height") else 0.0
        for child in self.children:
            child.inflate_to(target_w, target_h)
        return [c.measure(theme) for c in self.children]

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        if not self.children:
            return
        cols = self._columns()
        rows = (len(self.children) + cols - 1) // cols
        child_w = min_w / cols if cols else 0.0
        child_h = min_h / rows if rows else 0.0
        for child in self.children:
            child.inflate_to(child_w, child_h)
        self._cell = None

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        sizes = self._normalise(theme)
        cols = self._columns()
        rows = (len(self.children) + cols - 1) // cols
        gap = theme.gap_px(self.gap)
        if self.equal in ("both", "width"):
            widths = [max(s.w for s in sizes)] * cols
        else:
            widths = [
                max((sizes[r * cols + c].w for r in range(rows)
                     if r * cols + c < len(sizes)), default=0.0)
                for c in range(cols)
            ]
        if self.equal in ("both", "height"):
            heights = [max(s.h for s in sizes)] * rows
        else:
            heights = [
                max((sizes[i].h for i in range(r * cols, min((r + 1) * cols, len(sizes)))),
                    default=0.0)
                for r in range(rows)
            ]
        return BBox(sum(widths) + (cols - 1) * gap,
                    sum(heights) + (rows - 1) * gap)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes = self._normalise(theme)
        cols = self._columns()
        rows = (len(self.children) + cols - 1) // cols
        gap = theme.gap_px(self.gap)
        if self.equal in ("both", "width"):
            widths = [max(s.w for s in sizes)] * cols
        else:
            widths = [
                max((sizes[r * cols + c].w for r in range(rows)
                     if r * cols + c < len(sizes)), default=0.0)
                for c in range(cols)
            ]
        if self.equal in ("both", "height"):
            heights = [max(s.h for s in sizes)] * rows
        else:
            heights = [
                max((sizes[i].h for i in range(r * cols, min((r + 1) * cols, len(sizes)))),
                    default=0.0)
                for r in range(rows)
            ]
        y_offsets = [0.0]
        for h in heights[:-1]:
            y_offsets.append(y_offsets[-1] + h + gap)
        x_offsets = [0.0]
        for w in widths[:-1]:
            x_offsets.append(x_offsets[-1] + w + gap)
        for idx, child in enumerate(self.children):
            row = idx // cols
            col = idx % cols
            child_size = child.measure(theme)
            cx = x + x_offsets[col] + (widths[col] - child_size.w) / 2
            if self.align == "start":
                cy = y + y_offsets[row]
            elif self.align == "end":
                cy = y + y_offsets[row] + heights[row] - child_size.h
            else:
                cy = y + y_offsets[row] + (heights[row] - child_size.h) / 2
            child.render(canvas, cx, cy, theme)


class Stripe(Element):
    """Subtle role-coloured grouping rail around a list of items."""

    def __init__(self, *items: Element | Sequence[Element], role,
                 orientation: str = "vertical", gap="sm", padding="xs",
                 rail: bool = True):
        if len(items) == 1 and isinstance(items[0], (list, tuple)):
            self.items = [i for i in items[0] if i is not None]
        else:
            self.items = [i for i in items if i is not None]
        self.role = role
        self.orientation = orientation
        self.gap = gap
        self.padding = padding
        self.rail = rail
        self._min_w = 0.0
        self._min_h = 0.0

    def _inner(self) -> Element:
        if self.orientation == "horizontal":
            return Row(*self.items, gap=self.gap, align="center")
        return Column(*self.items, gap=self.gap, align="center", equal_widths=True)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, min_w)
        self._min_h = max(self._min_h, min_h)
        pad = 10.0
        for item in self.items:
            item.inflate_to(max(0.0, min_w - 2 * pad), 0.0)

    def measure(self, theme: Theme) -> BBox:
        pad = _pad_px(theme, self.padding)
        inner = self._inner().measure(theme)
        rail_w = theme.unit * 0.55 if self.rail else 0.0
        return BBox(max(inner.w + 2 * pad + rail_w, self._min_w),
                    max(inner.h + 2 * pad, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = _pad_px(theme, self.padding)
        rail_w = theme.unit * 0.55 if self.rail else 0.0
        canvas.rect(x, y, size.w, size.h, fill=_soft(theme, self.role),
                    stroke=theme.color_of(self.role), stroke_width=theme.hairline,
                    rx=theme.panel_radius, opacity=0.55)
        if self.rail:
            canvas.rect(x, y, rail_w, size.h, fill=theme.color_of(self.role),
                        stroke="none", rx=theme.panel_radius)
        inner = self._inner()
        inner_size = inner.measure(theme)
        inner.render(canvas, x + rail_w + pad + (size.w - rail_w - 2 * pad - inner_size.w) / 2,
                     y + pad + (size.h - 2 * pad - inner_size.h) / 2, theme)


class StepCell(Element):
    """A full-name pipeline step card with a thumbnail and condition glyph."""

    def __init__(self, name: str, visual: Element, *, role, index: Optional[int] = None,
                 optional: bool = False, condition: Optional[ConditionSpec] = None):
        self.name = name
        self.visual = visual
        self.role = role
        self.index = index
        self.optional = optional or condition is not None
        self.condition = condition
        self._min_w = 0.0
        self._min_h = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def _label_width(self, theme: Theme) -> float:
        bold = True
        longest = max((theme.text_width(w, "tiny", bold=bold)
                       for w in self.name.split()), default=0.0)
        total = theme.text_width(self.name, "tiny", bold=bold)
        return max(longest, min(total, theme.unit * 8.5))

    def _label(self, theme: Theme) -> TextBlock:
        return TextBlock(self.name, size="tiny", color="text", weight="700",
                         align="center", line_spacing=1.12,
                         max_width=self._label_width(theme))

    def _index_badge_size(self, theme: Theme) -> BBox:
        if self.index is None:
            return BBox(0, 0)
        text = str(self.index)
        h = max(theme.unit * 1.55, theme.text_height("micro") + theme.unit * 0.45)
        w = max(h, theme.text_width(text, "micro", bold=True) + theme.unit * 0.9)
        return BBox(w, h)

    def measure(self, theme: Theme) -> BBox:
        pad = theme.unit * 0.55
        visual = self.visual.measure(theme)
        label = self._label(theme).measure(theme)
        left_guard = pad * (3.6 if self.index is not None else 1.0)
        right_guard = pad * (2.0 if self.condition is not None else 1.0)
        w = visual.w + label.w + left_guard + right_guard + pad
        h = max(visual.h, label.h, theme.unit * 4.6) + 2 * pad
        return BBox(max(w, self._min_w), max(h, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = theme.unit * 0.55
        stroke = theme.color_of(self.role)
        fill = "white" if self.optional else _soft(theme, self.role)
        canvas.rect(x, y, size.w, size.h, fill=fill, stroke=stroke,
                    stroke_width=theme.hairline, rx=theme.panel_radius * 2,
                    dasharray="3,2" if self.optional else None)
        _register_implicit_obstacle(x, y, size.w, size.h)
        if self.index is not None:
            text = str(self.index)
            badge = self._index_badge_size(theme)
            bx = x + pad
            by = y + pad
            canvas.rect(bx, by, badge.w, badge.h,
                        fill=stroke, stroke=stroke,
                        stroke_width=theme.hairline, rx=badge.h / 2)
            canvas.text(bx + badge.w / 2,
                        by + badge.h / 2,
                        text, size=theme.font_micro, fill="white",
                        weight="700", anchor="middle", baseline="middle")
        if self.condition is not None:
            glyph = ConditionGlyph(self.condition.kind, color=self.role)
            gs = glyph.measure(theme)
            glyph.render(canvas, x + size.w - pad - gs.w, y + pad, theme)
        visual = self.visual.measure(theme)
        label = self._label(theme)
        label_size = label.measure(theme)
        content_w = visual.w + pad + label_size.w
        left_guard = pad * (3.6 if self.index is not None else 1.0)
        right_guard = pad * (2.0 if self.condition is not None else 1.0)
        usable_w = max(0.0, size.w - left_guard - right_guard)
        start_x = x + left_guard + max(0.0, (usable_w - content_w) / 2)
        center_y = y + size.h / 2
        vcb = self.visual.content_bbox(theme)
        lcb = label.content_bbox(theme)
        self.visual.render(
            canvas,
            start_x,
            center_y - (vcb[1] + vcb[3] / 2),
            theme,
        )
        label.render(
            canvas,
            start_x + visual.w + pad,
            center_y - (lcb[1] + lcb[3] / 2),
            theme,
        )


class SoftLegend(Element):
    """Compact legend for condition glyphs."""

    def __init__(self, items: Iterable[tuple[ConditionGlyph | str, str]],
                 *, gap="md", padding="xs"):
        self.items = list(items)
        self.gap = gap
        self.padding = padding

    @classmethod
    def from_conditions(cls, conditions: Iterable[ConditionSpec]) -> "SoftLegend":
        seen: dict[str, str] = {}
        for cond in conditions:
            seen.setdefault(cond.kind, cond.label)
        return cls([(ConditionGlyph(kind), label) for kind, label in seen.items()])

    def _row(self) -> Row:
        entries = []
        for glyph, label in self.items:
            g = glyph if isinstance(glyph, Element) else ConditionGlyph(str(glyph))
            entries.append(Row(g, Text(label, size="tiny", color="muted"),
                               gap="xs", align="center"))
        return Row(*entries, gap=self.gap, align="center")

    def measure(self, theme: Theme) -> BBox:
        pad = _pad_px(theme, self.padding)
        inner = self._row().measure(theme)
        return BBox(inner.w + 2 * pad, inner.h + 2 * pad)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = _pad_px(theme, self.padding)
        canvas.rect(x, y, size.w, size.h, fill=theme.bg_subtle,
                    stroke=theme.border, stroke_width=theme.hairline,
                    rx=theme.panel_radius)
        row = self._row()
        row.render(canvas, x + pad, y + pad, theme)
