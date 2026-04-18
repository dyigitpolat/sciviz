"""Layout primitives.

All layout containers follow the same rules:

* They measure each child, arrange them with automatic spacing, and report a
  bounding box that fully contains every child.
* Children are placed by position -- no child ever needs to know where it lives
  in its parent.

This means a deeply nested diagram always lays out correctly: measuring is
bottom-up, rendering is top-down.
"""

from __future__ import annotations

from typing import List, Optional, Union

from .core import Element, BBox, Canvas, Theme


# ---------------------------------------------------------------------------
# Spacer / Align
# ---------------------------------------------------------------------------

class Spacer(Element):
    """Invisible element that occupies fixed space."""

    def __init__(self, w: float = 0.0, h: float = 0.0):
        self.w = float(w)
        self.h = float(h)

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.w, self.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        pass


class FixedSize(Element):
    """Force a child into a specific bounding box (useful for alignment)."""

    def __init__(self, child: Element, *, width: Optional[float] = None,
                 height: Optional[float] = None, align: str = "center"):
        self.child = child
        self.width = width
        self.height = height
        self.align = align

    def measure(self, theme: Theme) -> BBox:
        inner = self.child.measure(theme)
        return BBox(self.width if self.width is not None else inner.w,
                    self.height if self.height is not None else inner.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        inner = self.child.measure(theme)
        outer = self.measure(theme)
        if self.align in ("center", "middle"):
            dx = (outer.w - inner.w) / 2
            dy = (outer.h - inner.h) / 2
        elif self.align == "start":
            dx, dy = 0, 0
        elif self.align == "end":
            dx = outer.w - inner.w
            dy = outer.h - inner.h
        else:
            dx = (outer.w - inner.w) / 2
            dy = (outer.h - inner.h) / 2
        self.child.render(canvas, x + dx, y + dy, theme)


# ---------------------------------------------------------------------------
# Row / Column
# ---------------------------------------------------------------------------

class Row(Element):
    """Horizontal container.

    Parameters
    ----------
    *children : Element
        The child elements, laid out left-to-right.  ``None`` children are
        silently dropped, which is handy for optional pieces.
    gap : str or float
        Spacing between children.  Semantic tokens (``"xs"``, ``"sm"``,
        ``"md"``, ``"lg"``, ``"xl"``, ``"2xl"``) are resolved against the
        theme's base unit.
    align : str
        Vertical alignment of shorter children: ``"start"``, ``"center"``,
        or ``"end"``.
    equal_widths : bool
        If True, every child gets the same horizontal slot (the max child
        width).  Critical for visually aligning columns of differing-width
        labels (e.g. tokens, bars, pictograms).  Each child is centered
        within its slot.
    """

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center", equal_widths: bool = False):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align
        self.equal_widths = equal_widths
        self._shape_normalized = False

    def _find_shape_peer(self, elem):
        """Unwrap one level of ``Anchor`` etc. to find a shape-key-bearing
        child (e.g. ``Box``) so sibling-normalisation reaches into
        ``Anchor(Box(...))`` without the author wrapping things differently.
        """
        seen = 0
        cur = elem
        while cur is not None and seen < 4:
            if getattr(cur, "shape_key", None):
                return cur
            cur = getattr(cur, "child", None)
            seen += 1
        return None

    def _normalize_shape_peers(self, theme: Theme) -> None:
        """Siblings in this row sharing the same ``shape_key`` get equalised
        min_width / min_height so they render at the same box size --
        regardless of label length or sub_label length.
        """
        if self._shape_normalized:
            return
        self._shape_normalized = True
        groups: dict = {}
        for c in self.children:
            peer = self._find_shape_peer(c)
            if peer is None:
                continue
            key = peer.shape_key
            if not key:
                continue
            groups.setdefault(key, []).append(peer)
        for key, peers in groups.items():
            if len(peers) < 2:
                continue
            # Measure each peer at its current intrinsic size (before
            # min_* bumping) and take the max -- this is the shared
            # target the whole group grows to.
            sizes = [p.measure(theme) for p in peers]
            target_w = max(s.w for s in sizes)
            target_h = max(s.h for s in sizes)
            for p in peers:
                if getattr(p, "min_width", None) is None or p.min_width < target_w:
                    p.min_width = target_w
                if getattr(p, "min_height", None) is None or p.min_height < target_h:
                    p.min_height = target_h

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        self._normalize_shape_peers(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        if self.equal_widths:
            slot = max(s.w for s in sizes)
            w = slot * len(sizes) + g * (len(sizes) - 1)
        else:
            w = sum(s.w for s in sizes) + g * (len(sizes) - 1)
        # Row height must accommodate the TALLEST content bbox plus the
        # asymmetric out-of-band margins of any individual child, so that
        # content-axis centering still fits every child inside the row.
        content = [c.content_bbox(theme) for c in self.children]
        content_h = max(cb[3] for cb in content)
        max_top = max(cb[1] for cb in content)
        max_bot = max(s.h - cb[1] - cb[3] for s, cb in zip(sizes, content))
        h = max(content_h + max_top + max_bot, max(s.h for s in sizes))
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        self._normalize_shape_peers(theme)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        # Content-bbox alignment: we want siblings' CONTENT rectangles
        # (excluding out-of-band margins like those added by Anchor for
        # Flow routing) to share a horizontal axis.  The row content y
        # band is the max content height centered within the row height.
        content = [c.content_bbox(theme) for c in self.children]
        content_h = max(cb[3] for cb in content)
        # Use the measured row H (derived the same way in ``measure``).
        H = self.measure(theme).h
        slot = max(s.w for s in sizes) if self.equal_widths else None
        cx = x
        for child, size, cb in zip(self.children, sizes, content):
            cb_y = cb[1]
            cb_h = cb[3]
            if self.align == "start":
                cy = y - cb_y
            elif self.align == "end":
                cy = y + H - (cb_y + cb_h)
            else:  # center content on the row content axis
                row_content_top = y + (H - content_h) / 2
                cy = row_content_top - cb_y
            if self.equal_widths:
                cb_x = cb[0]
                cb_w = cb[2]
                # Align content (not outer) centres inside the slot
                slot_cx = cx + slot / 2
                child.render(canvas, slot_cx - (cb_x + cb_w / 2), cy, theme)
                cx += slot + g
            else:
                child.render(canvas, cx, cy, theme)
                cx += size.w + g


class Column(Element):
    """Vertical container.  See :class:`Row` for the analogous documentation."""

    def __init__(self, *children: Element, gap: Union[str, float] = "md",
                 align: str = "center"):
        self.children: List[Element] = [c for c in children if c is not None]
        self.gap = gap
        self.align = align

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        w = max(s.w for s in sizes)
        h = sum(s.h for s in sizes) + g * (len(sizes) - 1)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes = [c.measure(theme) for c in self.children]
        g = theme.gap_px(self.gap)
        W = max(s.w for s in sizes)
        cy = y
        for child, size in zip(self.children, sizes):
            if self.align == "start":
                cx = x
            elif self.align == "end":
                cx = x + (W - size.w)
            else:  # center
                cx = x + (W - size.w) / 2
            child.render(canvas, cx, cy, theme)
            cy += size.h + g


# ---------------------------------------------------------------------------
# Stack & Grid
# ---------------------------------------------------------------------------

class Stack(Element):
    """Overlay all children at the same origin.  Useful for annotation layers."""

    def __init__(self, *children: Element, align: str = "center"):
        self.children = [c for c in children if c is not None]
        self.align = align

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        sizes = [c.measure(theme) for c in self.children]
        return BBox(max(s.w for s in sizes), max(s.h for s in sizes))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes = [c.measure(theme) for c in self.children]
        W = max(s.w for s in sizes)
        H = max(s.h for s in sizes)
        for child, size in zip(self.children, sizes):
            if self.align == "start":
                dx, dy = 0, 0
            elif self.align == "end":
                dx, dy = W - size.w, H - size.h
            else:
                dx = (W - size.w) / 2
                dy = (H - size.h) / 2
            child.render(canvas, x + dx, y + dy, theme)


class Grid(Element):
    """Regular N-column grid, children placed row-major.

    Column widths and row heights are automatically set to the max of the
    cells they contain, so every cell is the same size within its row/column.
    """

    def __init__(self, *children: Element, cols: int,
                 gap_x: Union[str, float] = "md",
                 gap_y: Union[str, float] = "md",
                 align: str = "center"):
        self.children = list(children)
        self.cols = cols
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.align = align

    def _col_row_extents(self, theme):
        sizes = [c.measure(theme) for c in self.children]
        rows = (len(sizes) + self.cols - 1) // self.cols
        col_w = [0.0] * self.cols
        row_h = [0.0] * rows
        for i, s in enumerate(sizes):
            r, c = i // self.cols, i % self.cols
            col_w[c] = max(col_w[c], s.w)
            row_h[r] = max(row_h[r], s.h)
        return sizes, col_w, row_h

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        _, col_w, row_h = self._col_row_extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        W = sum(col_w) + gx * (len(col_w) - 1)
        H = sum(row_h) + gy * (len(row_h) - 1)
        return BBox(W, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes, col_w, row_h = self._col_row_extents(theme)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        col_x = [0.0]
        for w in col_w[:-1]:
            col_x.append(col_x[-1] + w + gx)
        row_y = [0.0]
        for h in row_h[:-1]:
            row_y.append(row_y[-1] + h + gy)
        for i, (child, size) in enumerate(zip(self.children, sizes)):
            r, c = i // self.cols, i % self.cols
            cell_w, cell_h = col_w[c], row_h[r]
            if self.align == "start":
                dx, dy = 0, 0
            elif self.align == "end":
                dx = cell_w - size.w
                dy = cell_h - size.h
            else:
                dx = (cell_w - size.w) / 2
                dy = (cell_h - size.h) / 2
            child.render(canvas, x + col_x[c] + dx, y + row_y[r] + dy, theme)


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------

class Padded(Element):
    """Wrap a child with padding (semantic tokens accepted)."""

    def __init__(self, child: Element, *,
                 all: Union[str, float, None] = None,
                 x: Union[str, float, None] = None,
                 y: Union[str, float, None] = None,
                 top: Union[str, float, None] = None,
                 right: Union[str, float, None] = None,
                 bottom: Union[str, float, None] = None,
                 left: Union[str, float, None] = None):
        self.child = child
        self._all = all
        self._x = x
        self._y = y
        self._top = top
        self._right = right
        self._bottom = bottom
        self._left = left

    def _resolve(self, theme: Theme):
        def gx(v, default):
            if v is None:
                return default
            return theme.gap_px(v) if isinstance(v, str) else float(v)
        a = gx(self._all, 0.0)
        xp = gx(self._x, a)
        yp = gx(self._y, a)
        return (gx(self._top, yp), gx(self._right, xp),
                gx(self._bottom, yp), gx(self._left, xp))

    def measure(self, theme: Theme) -> BBox:
        top, right, bottom, left = self._resolve(theme)
        inner = self.child.measure(theme)
        return BBox(inner.w + left + right, inner.h + top + bottom)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        top, right, bottom, left = self._resolve(theme)
        self.child.render(canvas, x + left, y + top, theme)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class Panel(Element):
    """A framed sub-region with a small tag and title.

    Paper-style default: 0.5-px border, sharp corners, no filled background,
    compact header.  Tag and title share a single line at the top, left-aligned,
    with a thin baseline rule separating them from the content area.

    Example
    -------
    >>> Panel("a", "Weight Matrix", Matrix(...))
    """

    def __init__(self, tag: str, title: str, child: Element, *,
                 min_width: float = 0, min_height: float = 0,
                 rule: bool = True):
        self.tag = self._normalize_tag(tag)
        self.title = title
        self.child = child
        self.min_width = min_width
        self.min_height = min_height
        self.rule = rule

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        t = tag.strip()
        # paper convention: "(a)" with parens
        if t.startswith("(") and t.endswith(")"):
            return t
        return f"({t})"

    def _header_h(self, theme: Theme) -> float:
        # tag + title + a small gap to the rule + rule thickness + small gap
        return theme.text_height(theme.font_panel_title) + theme.unit * 1.4

    def measure(self, theme: Theme) -> BBox:
        pad = theme.panel_padding
        inner = self.child.measure(theme)
        tag_w = theme.text_width(self.tag, "panel", bold=True)
        title_w = theme.text_width(self.title, "panel", bold=False)
        header_w = tag_w + theme.unit * 0.6 + title_w
        content_w = max(inner.w, header_w)
        w = max(content_w + 2 * pad, self.min_width)
        h = max(self._header_h(theme) + inner.h + 2 * pad, self.min_height)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        pad = theme.panel_padding
        # frame (no fill -> transparent on paper)
        canvas.rect(
            x, y, size.w, size.h,
            fill="none",
            stroke=theme.color_of("border"),
            stroke_width=theme.hairline,
            rx=theme.panel_radius,
        )
        # header: "(a)" bold, then "Title" regular, same baseline
        header_baseline = y + pad + theme.font_panel_title * 0.85
        canvas.text(
            x + pad, header_baseline, self.tag,
            size=theme.font_panel_tag,
            fill=theme.color_of("text"),
            weight="700",
        )
        tag_w = theme.text_width(self.tag, "panel", bold=True)
        canvas.text(
            x + pad + tag_w + theme.unit * 0.9, header_baseline, self.title,
            size=theme.font_panel_title,
            fill=theme.color_of("text"),
            weight="500",
        )
        # hairline rule under header
        if self.rule:
            ry = y + pad + theme.font_panel_title + theme.unit * 0.6
            canvas.line(
                x + pad, ry, x + size.w - pad, ry,
                stroke=theme.color_of("border"),
                stroke_width=theme.hairline,
            )
        # child (below header area)
        inner = self.child.measure(theme)
        content_y = y + pad + self._header_h(theme)
        inner_w = size.w - 2 * pad
        child_x = x + pad + (inner_w - inner.w) / 2
        self.child.render(canvas, child_x, content_y, theme)


# ---------------------------------------------------------------------------
# Framed (unlabeled frame, for summary bands etc.)
# ---------------------------------------------------------------------------

class Framed(Element):
    """A simple rounded frame around a child, with configurable padding and bg."""

    def __init__(self, child: Element, *,
                 padding: Union[str, float] = "md",
                 bg: str = "bg_panel",
                 border: str = "border",
                 radius: Optional[float] = None):
        self.child = child
        self.padding = padding
        self.bg = bg
        self.border = border
        self.radius = radius

    def _pad(self, theme: Theme) -> float:
        return theme.gap_px(self.padding) if isinstance(self.padding, str) else float(self.padding)

    def measure(self, theme: Theme) -> BBox:
        inner = self.child.measure(theme)
        p = self._pad(theme)
        return BBox(inner.w + 2 * p, inner.h + 2 * p)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        p = self._pad(theme)
        r = self.radius if self.radius is not None else theme.panel_radius
        canvas.rect(
            x, y, size.w, size.h,
            fill=theme.color_of(self.bg),
            stroke=theme.color_of(self.border),
            stroke_width=1.0, rx=r,
        )
        self.child.render(canvas, x + p, y + p, theme)
