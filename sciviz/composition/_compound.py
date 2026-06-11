"""Compound layout primitives for semantic cards and step cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Union

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


def _align_x_in_slot(child: Element, slot_x: float, slot_w: float,
                     theme: Theme, align: str) -> float:
    cbx, _, cbw, _ = child.content_bbox(theme)
    if align in ("middle", "center"):
        return slot_x + slot_w / 2 - (cbx + cbw / 2)
    if align == "end":
        return slot_x + slot_w - (cbx + cbw)
    return slot_x - cbx


def _center_y_on_content(child: Element, center_y: float, theme: Theme) -> float:
    _, cby, _, cbh = child.content_bbox(theme)
    return center_y - (cby + cbh / 2)


@dataclass(frozen=True)
class ConditionSpec:
    """Legend-aware conditional marker."""

    kind: str
    label: str


class Card(Element):
    """A titled card with a role-coloured header and soft body.

    Accepts a header followed by one or more body children. When more than
    one body child is provided, they are auto-wrapped in a Column with
    ``align="stretch"`` and a small gap, so the most common usage --
    "header plus a stack of rows" -- is non-erroneous.
    """

    def __init__(self, header: Element | str, *body: Element, role,
                 footer: Optional[Element] = None, padding="sm",
                 radius: Optional[float] = None, dashed: bool = False,
                 body_gap: str = "xs", body_align: str = "stretch"):
        # ``body`` may be one Element (kept as-is) or many (auto-stacked
        # in a Column for the caller's convenience).
        elems = [b for b in body if b is not None]
        if not elems:
            raise ValueError("Card requires at least one body element")
        if len(elems) == 1:
            body_elem: Element = elems[0]
        else:
            body_elem = Column(*elems, gap=body_gap, align=body_align)
        self.header = header if isinstance(header, Element) else Text(str(header), weight="700")
        self.body = body_elem
        self.footer = footer
        self.role = role
        self.padding = padding
        self.radius = radius
        self.dashed = dashed
        self._min_w = 0.0
        self._min_h = 0.0
        self._header_h: Optional[float] = None

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        # Record the outer floor; the body inflation defers to
        # ``_apply_body_inflation`` so the pad math runs with the
        # theme-aware padding that ``measure``/``render`` will use.
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def _apply_body_inflation(self, theme: Theme) -> None:
        """Forward the recorded outer floor to the body using
        theme-aware padding so card boundary and content arithmetic
        agree at render time.
        """
        if self._min_w <= 0.0 and self._min_h <= 0.0:
            return
        pad = _pad_px(theme, self.padding)
        header_h = self._header_height(theme)
        footer_h = (self.footer.measure(theme).h + pad) if self.footer else 0.0
        inner_w = max(0.0, self._min_w - 2 * pad)
        # Subtract the actual top+bottom pads, the header band, and any
        # footer band so the body fills the requested floor exactly.
        inner_h = max(0.0, self._min_h - 2 * pad - header_h - footer_h)
        self.body.inflate_to(inner_w, inner_h)

    def _intrinsic_header_height(self, theme: Theme) -> float:
        pad = _pad_px(theme, self.padding)
        header = self.header.measure(theme)
        design_min = theme.text_height("small") + pad * 1.2
        return max(header.h + pad * 1.2, design_min)

    def _header_height(self, theme: Theme) -> float:
        intrinsic = self._intrinsic_header_height(theme)
        return max(intrinsic, self._header_h or 0.0)

    def _shared_header_height(self, theme: Theme) -> float:
        return self._intrinsic_header_height(theme)

    def _apply_shared_header_height(self, height: float) -> None:
        self._header_h = max(self._header_h or 0.0, float(height))

    def measure(self, theme: Theme) -> BBox:
        self._apply_body_inflation(theme)
        pad = _pad_px(theme, self.padding)
        header = self.header.measure(theme)
        body = self.body.measure(theme)
        footer = self.footer.measure(theme) if self.footer else BBox(0, 0)
        header_h = self._header_height(theme)
        footer_h = (footer.h + pad) if self.footer else 0.0
        w = max(header.w, body.w, footer.w) + 2 * pad
        h = header_h + body.h + footer_h + 2 * pad
        return BBox(max(w, self._min_w), max(h, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._apply_body_inflation(theme)
        size = self.measure(theme)
        pad = _pad_px(theme, self.padding)
        radius = self.radius if self.radius is not None else theme.panel_radius * 2
        stroke = theme.color_of(self.role)
        body_bg = _soft(theme, self.role)
        canvas.rect(x, y, size.w, size.h, fill=body_bg,
                    stroke=stroke, stroke_width=theme.hairline, rx=radius,
                    dasharray="3,2" if self.dashed else None)
        _register_implicit_obstacle(x, y, size.w, size.h)

        header_h = self._header_height(theme)
        canvas.rect(x, y, size.w, header_h, fill=stroke, stroke=stroke,
                    stroke_width=theme.hairline, rx=radius)
        hcbx, hcby, _, hcbh = self.header.content_bbox(theme)
        # Push the saturated header bg so white text in the header
        # remains white; pop after.
        theme.push_bg(stroke)
        try:
            self.header.render(
                canvas,
                x + pad - hcbx,
                y + header_h / 2 - (hcby + hcbh / 2),
                theme,
            )
        finally:
            theme.pop_bg()

        body_size = self.body.measure(theme)
        body_x = x + (size.w - body_size.w) / 2
        body_y = y + header_h + pad
        # Push the soft body bg so any Text(color="white") inside the
        # body auto-corrects to a dark, readable colour.
        theme.push_bg(body_bg)
        try:
            self.body.render(canvas, body_x, body_y, theme)
            if self.footer:
                footer = self.footer.measure(theme)
                self.footer.render(canvas, x + (size.w - footer.w) / 2,
                                   y + size.h - pad - footer.h, theme)
        finally:
            theme.pop_bg()


class EqualGrid(Element):
    """Grid that broadcasts the widest/tallest child cell to all children.

    ``columns`` accepts an int (fixed), ``None`` (square-ish default,
    ``ceil(sqrt(n))``), or ``"auto"``: same square-ish default on its
    own, but when the enclosing :class:`~sciviz.Diagram` declares both
    ``target_width_pt`` and ``target_aspect`` the diagram fitter may
    reflow the grid -- redistributing the same children over a
    different column count -- to land the figure inside the requested
    physical aspect range. Authors declare *what* flows together; the
    fitter owns *how many columns* it takes.
    """

    def __init__(self, *children: Element,
                 columns: Union[int, str, None] = None,
                 gap="md", equal: str = "both", align: str = "center"):
        self.children = [c for c in children if c is not None]
        if isinstance(columns, str) and columns != "auto":
            raise ValueError("columns must be an int, None, or 'auto'")
        self.columns = columns
        self.gap = gap
        self.equal = equal
        self.align = align
        self._cell: Optional[BBox] = None
        self._fitted_columns: Optional[int] = None

    # -- reflow protocol (consumed by Diagram's target fitter) ------------

    def _reflow_options(self) -> list[int]:
        """Column counts the diagram fitter may choose between."""
        if self.columns == "auto" and len(self.children) > 1:
            return list(range(1, len(self.children) + 1))
        return []

    def _apply_reflow(self, columns: int) -> None:
        self._fitted_columns = max(1, int(columns))
        self._cell = None

    def _columns(self) -> int:
        if isinstance(self.columns, int):
            return max(1, self.columns)
        if self._fitted_columns is not None:
            return self._fitted_columns
        return max(1, int(len(self.children) ** 0.5 + 0.999))

    def _normalise(self, theme: Theme) -> list[BBox]:
        if not self.children:
            return []
        self._normalise_header_bands(theme)
        sizes = [c.measure(theme) for c in self.children]
        target_w = max(s.w for s in sizes) if self.equal in ("both", "width") else 0.0
        target_h = max(s.h for s in sizes) if self.equal in ("both", "height") else 0.0
        for child in self.children:
            child.inflate_to(target_w, target_h)
        return [c.measure(theme) for c in self.children]

    def _normalise_header_bands(self, theme: Theme) -> None:
        heights: list[float] = []
        for child in self.children:
            fn = getattr(child, "_shared_header_height", None)
            if fn is not None:
                heights.append(float(fn(theme)))
        if len(heights) < 2:
            return
        target = max(heights)
        for child in self.children:
            apply = getattr(child, "_apply_shared_header_height", None)
            if apply is not None:
                apply(target)

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
            # Use content_bbox-aware centering so children whose outer
            # ink is asymmetric (Region with an outside label, Card
            # with a header strip, etc.) align on their content axis
            # rather than the silhouette midpoint.
            cbx, cby, cbw, cbh = child.content_bbox(theme)
            slot_cx = x + x_offsets[col] + widths[col] / 2
            cx = slot_cx - (cbx + cbw / 2)
            if self.align == "start":
                cy = y + y_offsets[row] - cby
            elif self.align == "end":
                cy = y + y_offsets[row] + heights[row] - (cby + cbh)
            else:
                slot_cy = y + y_offsets[row] + heights[row] / 2
                cy = slot_cy - (cby + cbh / 2)
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
                 optional: bool = False, condition: Optional[ConditionSpec] = None,
                 label_align: str = "center"):
        self.name = name
        self.visual = visual
        self.role = role
        self.index = index
        self.optional = optional or condition is not None
        self.condition = condition
        self.label_align = label_align
        self._min_w = 0.0
        self._min_h = 0.0
        self._forced_slot_w: Optional[list[float]] = None

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
                         align=self.label_align, line_spacing=1.12,
                         max_width=self._label_width(theme))

    def _index_badge_size(self, theme: Theme) -> BBox:
        if self.index is None:
            return BBox(0, 0)
        text = str(self.index)
        h = max(theme.unit * 1.55, theme.text_height("micro") + theme.unit * 0.45)
        w = max(h, theme.text_width(text, "micro", bold=True) + theme.unit * 0.9)
        return BBox(w, h)

    def _left_guard(self, theme: Theme) -> float:
        pad = theme.unit * 0.55
        if self.index is None:
            return pad
        badge = self._index_badge_size(theme)
        return max(pad * 3.2, badge.w + pad * 1.9)

    def _right_guard(self, theme: Theme) -> float:
        pad = theme.unit * 0.55
        if self.condition is None:
            return pad
        glyph = ConditionGlyph(self.condition.kind, color=self.role).measure(theme)
        return max(pad * 2.0, glyph.w + pad * 1.7)

    def _intrinsic_slot_widths(self, theme: Theme) -> list[float]:
        return [
            self._left_guard(theme),
            self.visual.measure(theme).w,
            self._label(theme).measure(theme).w,
            self._right_guard(theme),
        ]

    def _slot_widths(self, theme: Theme) -> list[float]:
        slots = self._intrinsic_slot_widths(theme)
        if self._forced_slot_w is not None:
            slots = [
                max(slots[i], self._forced_slot_w[i] if i < len(self._forced_slot_w) else 0.0)
                for i in range(len(slots))
            ]
        return slots

    def _shared_column_widths(self, theme: Theme) -> list[float]:
        return self._intrinsic_slot_widths(theme)

    def _apply_shared_columns(self, widths: list[float]) -> None:
        self._forced_slot_w = list(widths)

    def measure(self, theme: Theme) -> BBox:
        pad = theme.unit * 0.55
        visual = self.visual.measure(theme)
        label = self._label(theme).measure(theme)
        left_guard, visual_slot, label_slot, right_guard = self._slot_widths(theme)
        w = left_guard + visual_slot + pad + label_slot + right_guard
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
        label = self._label(theme)
        left_guard, visual_slot, label_slot, _ = self._slot_widths(theme)
        visual_slot_x = x + left_guard
        label_slot_x = visual_slot_x + visual_slot + pad
        center_y = y + size.h / 2
        self.visual.render(
            canvas,
            _align_x_in_slot(self.visual, visual_slot_x, visual_slot, theme, "center"),
            _center_y_on_content(self.visual, center_y, theme),
            theme,
        )
        label.render(
            canvas,
            _align_x_in_slot(label, label_slot_x, label_slot, theme, self.label_align),
            _center_y_on_content(label, center_y, theme),
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


# ---------------------------------------------------------------------
# Convenience: rows/columns of Cards, equalised by default.
# ---------------------------------------------------------------------

class BalancedColumns(Element):
    """Order-preserving column packer for unequal-height children.

    The complement of :class:`EqualGrid`: instead of broadcasting one
    uniform cell, children keep their natural sizes and flow
    top-to-bottom into ``columns`` side-by-side stacks. The container
    owns the one layout decision authors otherwise hand-tune -- *where
    the column breaks fall* -- by choosing the contiguous split that
    minimises the tallest column (classic linear partition). Authors
    therefore declare only reading order and adjacency; the library
    balances the area.

    ``columns`` accepts an int (fixed count), ``None``/``"auto"``
    (square-ish default, ``ceil(sqrt(n))``).  ``"auto"`` additionally
    opts the container into the :class:`~sciviz.Diagram` target
    fitter's reflow search: when the diagram declares
    ``target_width_pt`` and ``target_aspect``, the fitter may pick a
    different column count to land the figure in the requested
    physical aspect range.

    ``gap`` is the vertical rhythm inside a column; ``column_gap``
    (default: one step looser than ``gap``) separates the columns and
    doubles as the routing corridor for connectors between them.
    """

    _COLUMN_GAP_DEFAULT = {"none": "xs", "xs": "sm", "sm": "md",
                           "md": "lg", "lg": "xl", "xl": "2xl",
                           "2xl": "3xl", "3xl": "3xl"}

    def __init__(self, *children: Element,
                 columns: Union[int, str, None] = "auto",
                 gap="md", column_gap=None, align: str = "center"):
        self.children = [c for c in children if c is not None]
        if isinstance(columns, str) and columns != "auto":
            raise ValueError("columns must be an int, None, or 'auto'")
        self.columns = columns
        self.gap = gap
        if column_gap is None and isinstance(gap, str):
            column_gap = self._COLUMN_GAP_DEFAULT.get(gap, gap)
        self.column_gap = gap if column_gap is None else column_gap
        self.align = align
        self._fitted_columns: Optional[int] = None
        self._min_w = 0.0
        self._min_h = 0.0

    # -- reflow protocol (consumed by Diagram's target fitter) ------------

    def _reflow_options(self) -> list[int]:
        if self.columns == "auto" and len(self.children) > 1:
            return list(range(1, len(self.children) + 1))
        return []

    def _apply_reflow(self, columns: int) -> None:
        self._fitted_columns = max(1, int(columns))

    def _columns_count(self) -> int:
        if isinstance(self.columns, int):
            n = max(1, self.columns)
        elif self._fitted_columns is not None:
            n = self._fitted_columns
        else:
            n = max(1, int(len(self.children) ** 0.5 + 0.999))
        return min(n, max(1, len(self.children)))

    # -- balanced contiguous split ----------------------------------------

    def _split(self, theme: Theme) -> list[list[Element]]:
        """Split children into ``k`` contiguous runs minimising the
        tallest stacked column (heights include the intra-column gap)."""
        kids = self.children
        if not kids:
            return []
        k = self._columns_count()
        gap = theme.gap_px(self.gap)
        heights = [c.measure(theme).h for c in kids]
        n = len(kids)

        def run_h(i: int, j: int) -> float:
            return sum(heights[i:j]) + gap * max(0, j - i - 1)

        INF = float("inf")
        # dp[c][j] = minimal max-column-height splitting kids[:j] into c runs
        dp = [[INF] * (n + 1) for _ in range(k + 1)]
        cut = [[0] * (n + 1) for _ in range(k + 1)]
        dp[0][0] = 0.0
        for c in range(1, k + 1):
            for j in range(c, n + 1):
                for i in range(c - 1, j):
                    cand = max(dp[c - 1][i], run_h(i, j))
                    if cand < dp[c][j]:
                        dp[c][j] = cand
                        cut[c][j] = i
        runs: list[list[Element]] = []
        j = n
        for c in range(k, 0, -1):
            i = cut[c][j]
            runs.append(kids[i:j])
            j = i
        runs.reverse()
        return [r for r in runs if r]

    # -- Element protocol ---------------------------------------------------

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def _geometry(self, theme: Theme):
        runs = self._split(theme)
        gap = theme.gap_px(self.gap)
        col_gap = theme.gap_px(self.column_gap)
        sizes = [[c.measure(theme) for c in run] for run in runs]
        widths = [max((s.w for s in col), default=0.0) for col in sizes]
        heights = [sum(s.h for s in col) + gap * max(0, len(col) - 1)
                   for col in sizes]
        total_w = sum(widths) + col_gap * max(0, len(runs) - 1)
        total_h = max(heights, default=0.0)
        return runs, sizes, widths, heights, total_w, total_h

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        *_, total_w, total_h = self._geometry(theme)
        return BBox(max(total_w, self._min_w), max(total_h, self._min_h))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        runs, sizes, widths, heights, total_w, total_h = self._geometry(theme)
        gap = theme.gap_px(self.gap)
        col_gap = theme.gap_px(self.column_gap)
        outer = self.measure(theme)
        cx = x + (outer.w - total_w) / 2
        for col_idx, run in enumerate(runs):
            cy = y + (outer.h - total_h) / 2
            for child_idx, child in enumerate(run):
                s = sizes[col_idx][child_idx]
                if self.align == "start":
                    child_x = cx
                elif self.align == "end":
                    child_x = cx + widths[col_idx] - s.w
                else:
                    child_x = cx + (widths[col_idx] - s.w) / 2
                child.render(canvas, child_x, cy, theme)
                cy += s.h + gap
            cx += widths[col_idx] + col_gap


class CardRow(Element):
    """A row of Cards (or other Elements) with equal widths by default.

    The single most common figure pattern in this codebase is "a row of
    same-shape Cards"; CardRow encodes that pattern so the caller cannot
    accidentally end up with cards of wildly different widths. Pass
    ``equal_widths=False`` to opt out.
    """

    def __init__(self, *children: Element, gap: str = "md",
                 align: str = "start", equal_widths: bool = True):
        self.children = [c for c in children if c is not None]
        self.gap = gap
        self.align = align
        self.equal_widths = equal_widths
        self._row = Row(*self.children, gap=gap, align=align,
                        equal_widths=equal_widths)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._row.inflate_to(min_w, min_h)

    def measure(self, theme: Theme) -> BBox:
        return self._row.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._row.render(canvas, x, y, theme)


class CardColumn(Element):
    """Vertical stack of Cards equalised in width by default."""

    def __init__(self, *children: Element, gap: str = "sm",
                 align: str = "stretch", equal_widths: bool = True):
        self.children = [c for c in children if c is not None]
        self._col = Column(
            *self.children, gap=gap, align=align,
            equal_widths=equal_widths,
        )

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._col.inflate_to(min_w, min_h)

    def measure(self, theme: Theme) -> BBox:
        return self._col.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._col.render(canvas, x, y, theme)


def card_header(title: str, icon: Optional[str] = None,
                *, color: str = "white", size: str = "small",
                weight: str = "700") -> Element:
    """Standard role-coloured card header: optional icon + title text.

    Returned element is intended to be passed as the first argument of
    :class:`Card`. Encapsulating this here means callers do not
    re-implement the same Row(Icon, Text) pattern in every figure.
    """
    text = Text(title, color=color, size=size, weight=weight)
    if icon is None:
        return text
    # Local import avoids a top-level circular import with elements.
    from ..elements import Icon  # noqa: WPS433
    return Row(
        Icon(icon, color=color, size=size, stroke_width=2.0),
        text,
        gap="xs",
        align="center",
    )
