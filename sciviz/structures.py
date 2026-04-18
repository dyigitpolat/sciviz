"""High-level structural primitives.

These are general-purpose containers that absorb common manual work the
author would otherwise do with ``Spacer`` and ad-hoc ``Row``/``Column``
arithmetic:

* :class:`Sequence`    -- like Row/Column but with auto-equal-width cells
                          and uniform spacing (no manual Spacers).
* :class:`Section`     -- titled block with auto rule + spacing.
* :class:`BlockGroup`  -- rounded grouping box with optional caption.
* :class:`MessageSequence` -- timeline with cross-lane message arrows.
* :class:`LayeredGraph`    -- generic layered diagram (DAG / tree / lattice)
                              with auto edge routing.
"""

from __future__ import annotations

from typing import List, Optional, Sequence as _Seq, Tuple, Union

from .core import Element, BBox, Canvas, Theme
from .layout import Row, Column, Spacer
from .elements import Text, Box


# ---------------------------------------------------------------------------
# Sequence -- the "no manual Spacers" container
# ---------------------------------------------------------------------------

class Strip(Element):
    """A linear arrangement of children with automatic alignment.

    The "no manual Spacers" container.  Like Row/Column but with built-in
    sizing modes that are common enough to deserve dedicated support.

    Modes
    -----
    ``"natural"`` (default)
        Like Row/Column: each child uses its own measured size.
    ``"equal"``
        All children are stretched to the same major-axis size = the max
        across children.  Use for token strips, time steps, table rows --
        anywhere you want a regular drum-beat alignment.
    ``"justify"``
        Total span fixed; gaps between children are computed to fill it.

    Direction
    ---------
    ``"horizontal"`` (default) or ``"vertical"``.

    Alignment
    ---------
    ``align`` controls cross-axis alignment ("start" / "center" / "end" /
    "baseline").

    Examples
    --------
    Vertically aligned token strip with equal-width cells:

        Strip(*tokens, mode="equal", align="center")

    Three columns of body text, justified to a fixed width:

        Strip(c1, c2, c3, mode="justify", span=600)
    """

    def __init__(self, *children: Element,
                 direction: str = "horizontal",
                 mode: str = "natural",
                 gap: Union[str, float] = "md",
                 align: str = "center",
                 span: Optional[float] = None):
        self.children: List[Element] = [c for c in children if c is not None]
        self.direction = direction
        self.mode = mode
        self.gap = gap
        self.align = align
        self.span = span

    def _major_minor(self, bbox: BBox):
        return (bbox.w, bbox.h) if self.direction == "horizontal" else (bbox.h, bbox.w)

    def _from_major_minor(self, major: float, minor: float) -> BBox:
        return BBox(major, minor) if self.direction == "horizontal" else BBox(minor, major)

    def _cell_size(self, theme: Theme):
        sizes = [c.measure(theme) for c in self.children]
        majors = [self._major_minor(s)[0] for s in sizes]
        minors = [self._major_minor(s)[1] for s in sizes]
        if self.mode == "equal":
            cell_major = max(majors) if majors else 0
            cells = [(cell_major, m) for m in minors]
        elif self.mode == "justify":
            cells = list(zip(majors, minors))
        else:
            cells = list(zip(majors, minors))
        return sizes, cells

    def measure(self, theme: Theme) -> BBox:
        if not self.children:
            return BBox(0, 0)
        sizes, cells = self._cell_size(theme)
        gap = theme.gap_px(self.gap)
        if self.mode == "justify" and self.span is not None:
            major = self.span
        else:
            major = sum(c[0] for c in cells) + gap * (len(cells) - 1)
        minor = max(c[1] for c in cells) if cells else 0
        return self._from_major_minor(major, minor)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.children:
            return
        sizes, cells = self._cell_size(theme)
        outer = self.measure(theme)
        outer_major, outer_minor = self._major_minor(outer)

        # determine effective gap
        if self.mode == "justify" and self.span is not None and len(cells) > 1:
            cells_total = sum(c[0] for c in cells)
            gap = max(0.0, (outer_major - cells_total) / (len(cells) - 1))
        else:
            gap = theme.gap_px(self.gap)

        # cursor along the major axis
        cursor = 0.0
        for child, size, (cell_major, cell_minor) in zip(self.children, sizes, cells):
            child_major, child_minor = self._major_minor(size)
            # major-axis: place child centered within the cell major span
            major_off = cursor + (cell_major - child_major) / 2 if self.mode == "equal" else cursor
            # minor-axis (cross): respect align
            if self.align == "start":
                minor_off = 0.0
            elif self.align == "end":
                minor_off = outer_minor - child_minor
            else:  # center / baseline
                minor_off = (outer_minor - child_minor) / 2

            if self.direction == "horizontal":
                child.render(canvas, x + major_off, y + minor_off, theme)
            else:
                child.render(canvas, x + minor_off, y + major_off, theme)
            cursor += cell_major + gap


# ---------------------------------------------------------------------------
# Section -- titled block with rule and auto-spacing
# ---------------------------------------------------------------------------

class Section(Element):
    """A titled block of content.

    Renders as:
        Title (optional kicker)
        ---------- (rule)
        body
        (caption)

    Spacing between title, rule, body, and caption is consistent and tuned
    by the theme.  Authors don't insert Spacers manually.

    Parameters
    ----------
    title : str
        Section title.
    body : Element
        The content.
    kicker : str, optional
        Small uppercase label above the title (like a tag).
    caption : str, optional
        Italic caption below the body.
    rule : bool
        Draw a hairline rule between title and body.  Default ``True``.
    align : str
        ``"start"`` (default), ``"center"``, ``"end"`` -- horizontal alignment
        of the title/caption relative to the body's measured width.
    """

    def __init__(self, title: str, body: Element, *,
                 kicker: Optional[str] = None,
                 caption: Optional[str] = None,
                 rule: bool = True,
                 align: str = "start"):
        self.title = title
        self.body = body
        self.kicker = kicker
        self.caption = caption
        self.rule = rule
        self.align = align

    # -------- internal layout helpers --------

    def _kicker_h(self, theme):
        return theme.text_height("tiny") + theme.unit * 0.4 if self.kicker else 0.0

    def _title_h(self, theme):
        return theme.text_height("section") + theme.unit * 0.6

    def _rule_h(self, theme):
        return theme.unit * 0.6 if self.rule else 0.0

    def _caption_h(self, theme):
        return theme.text_height("small") + theme.unit * 0.5 if self.caption else 0.0

    def measure(self, theme: Theme) -> BBox:
        b = self.body.measure(theme)
        title_w = theme.text_width(self.title, "section", bold=True)
        kicker_w = theme.text_width(self.kicker, "tiny", bold=True) if self.kicker else 0
        cap_w = theme.text_width(self.caption, "small") if self.caption else 0
        w = max(b.w, title_w, kicker_w, cap_w)
        h = (self._kicker_h(theme) + self._title_h(theme) + self._rule_h(theme)
             + b.h + self._caption_h(theme))
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        cur_y = y

        # kicker
        if self.kicker:
            canvas.text(x, cur_y + theme.size_px("tiny") * 0.85,
                       self.kicker.upper(),
                       size=theme.size_px("tiny"),
                       fill=theme.color_of("muted"),
                       weight="700", anchor="start")
            cur_y += self._kicker_h(theme)

        # title
        canvas.text(x, cur_y + theme.size_px("section") * 0.85,
                   self.title,
                   size=theme.size_px("section"),
                   fill=theme.color_of("text"),
                   weight="700", anchor="start")
        cur_y += theme.text_height("section")

        # rule
        if self.rule:
            cur_y += theme.unit * 0.3
            canvas.line(x, cur_y, x + size.w, cur_y,
                       stroke=theme.color_of("border"),
                       stroke_width=theme.hairline)
            cur_y += theme.unit * 0.3

        # body (centred horizontally if requested)
        b = self.body.measure(theme)
        if self.align == "center":
            bx = x + (size.w - b.w) / 2
        elif self.align == "end":
            bx = x + (size.w - b.w)
        else:
            bx = x
        self.body.render(canvas, bx, cur_y, theme)
        cur_y += b.h

        # caption
        if self.caption:
            cur_y += theme.unit * 0.5
            cap_baseline = cur_y + theme.size_px("small") * 0.85
            cap_x = x
            if self.align == "center":
                cap_x = x + size.w / 2
                anchor = "middle"
            elif self.align == "end":
                cap_x = x + size.w
                anchor = "end"
            else:
                anchor = "start"
            canvas.text(cap_x, cap_baseline, self.caption,
                       size=theme.size_px("small"),
                       fill=theme.color_of("text_muted"),
                       italic=True, anchor=anchor)


# ---------------------------------------------------------------------------
# BlockGroup -- rounded "phase" container
# ---------------------------------------------------------------------------

class BlockGroup(Element):
    """A rounded box that visually groups its child with an optional label.

    Useful for "phase 1 / phase 2" groupings, "frozen / trainable" partitions,
    and other implicit-region indicators.

    Parameters
    ----------
    child : Element
        Content rendered inside.
    label : str, optional
        Header label drawn on the top edge.
    color : ColorRef or str
        Stroke colour for the border (and label, if shown).
    fill : ColorRef or str, optional
        Background fill behind the child.  Default ``None`` = transparent.
    dashed : bool
        Stroke style: dashed (default) or solid.
    padding : str or float
        Inset between border and child.
    label_align : str
        ``"start"`` (default), ``"center"``, ``"end"``.
    """

    def __init__(self, child: Element, *,
                 label: Optional[str] = None,
                 color = "muted",
                 fill = None,
                 dashed: bool = True,
                 padding: Union[str, float] = "md",
                 label_align: str = "start",
                 label_size: str = "small"):
        self.child = child
        self.label = label
        self.color = color
        self.fill = fill
        self.dashed = dashed
        self.padding = padding
        self.label_align = label_align
        self.label_size = label_size

    def _pad(self, theme):
        return theme.gap_px(self.padding) if isinstance(self.padding, str) else float(self.padding)

    def _label_h(self, theme):
        return theme.text_height(self.label_size) + theme.unit * 0.4 if self.label else 0.0

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        p = self._pad(theme)
        lbl_w = (theme.text_width(self.label, self.label_size, bold=True)
                 + theme.unit * 1.2) if self.label else 0
        w = max(b.w + 2 * p, lbl_w + 2 * p)
        h = b.h + 2 * p + self._label_h(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        p = self._pad(theme)
        lbl_h = self._label_h(theme)
        col = theme.color_of(self.color)
        fill_col = theme.color_of(self.fill) if self.fill is not None else "none"
        border_x = x
        border_y = y + lbl_h
        border_w = size.w
        border_h = size.h - lbl_h
        canvas.rect(
            border_x, border_y, border_w, border_h,
            fill=fill_col, stroke=col,
            stroke_width=theme.hairline,
            rx=theme.panel_radius * 1.5,
            dasharray="4,3" if self.dashed else None,
        )

        # Publish the border rectangle to every active anchor registry
        # under a `__region_<id>` key so connector routers can detect
        # required / forbidden boundary crossings.
        from .composition import _anchor_stack
        stack = _anchor_stack.get()
        if stack is not None:
            key = f"__region_{id(self):x}"
            for reg in stack:
                reg[key] = (border_x, border_y, border_w, border_h)

        if self.label:
            lbl_w = theme.text_width(self.label, self.label_size, bold=True)
            if self.label_align == "center":
                lx = x + (size.w - lbl_w) / 2
                anchor = "start"
            elif self.label_align == "end":
                lx = x + size.w - theme.unit - lbl_w
                anchor = "start"
            else:
                lx = x + theme.unit
                anchor = "start"
            # Label sits transparently on top of whatever is underneath.
            canvas.text(lx, y + theme.size_px(self.label_size) * 0.85, self.label,
                       size=theme.size_px(self.label_size),
                       fill=col, weight="700", anchor=anchor)
        b = self.child.measure(theme)
        cx = x + (size.w - b.w) / 2
        self.child.render(canvas, cx, y + lbl_h + p, theme)


# ---------------------------------------------------------------------------

class LayeredGraph(Element):
    """A general layered (DAG / tree / lattice) diagram.

    The author specifies a list of layers; each layer is a list of nodes
    (an Element each, typically a :class:`Box`).  Edges are given as
    ``(src_layer, src_idx, dst_layer, dst_idx, color?)``.  Layout is
    automatic: every layer is centered, edges are straight lines from the
    bottom of the source node to the top of the destination node.

    This single primitive subsumes most tree, network, and pipeline
    visualisations -- B+ trees, MoE routing, message-passing graphs, etc.
    The author writes only the structure.

    Parameters
    ----------
    layers : list[list[Element]]
        Layer-major node list.
    edges : list[tuple]
        ``(src_layer, src_idx, dst_layer, dst_idx, color?)``.  Color may be
        a ``ColorRef`` or a hex string.
    direction : str
        ``"down"`` (default) for top-to-bottom, or ``"right"`` for
        left-to-right.
    layer_gap, node_gap : str or float
        Spacing between layers and between siblings within a layer.
    edge_routing : str
        ``"line"`` (default) or ``"orthogonal"`` (right-angle routing).
    sibling_links : list[tuple], optional
        ``(layer, from_idx, to_idx, color?)`` -- horizontal arrows linking
        siblings (for leaf-pointer chains, etc.).
    """

    def __init__(self, layers: _Seq[_Seq[Element]], *,
                 edges: _Seq[tuple] = (),
                 sibling_links: _Seq[tuple] = (),
                 direction: str = "down",
                 layer_gap: Union[str, float] = "lg",
                 node_gap: Union[str, float] = "md",
                 edge_routing: str = "line",
                 edge_color = "muted"):
        self.layers = [list(layer) for layer in layers]
        self.edges = list(edges)
        self.sibling_links = list(sibling_links)
        self.direction = direction
        self.layer_gap = layer_gap
        self.node_gap = node_gap
        self.edge_routing = edge_routing
        self.edge_color = edge_color

    def _node_sizes(self, theme: Theme):
        return [[node.measure(theme) for node in layer] for layer in self.layers]

    def _layer_extents(self, theme: Theme):
        """For each layer, return (total_major, max_minor)."""
        sizes = self._node_sizes(theme)
        node_gap = theme.gap_px(self.node_gap)
        out = []
        for layer in sizes:
            if not layer:
                out.append((0.0, 0.0))
                continue
            if self.direction == "down":
                tw = sum(s.w for s in layer) + node_gap * (len(layer) - 1)
                mh = max(s.h for s in layer)
            else:
                tw = sum(s.h for s in layer) + node_gap * (len(layer) - 1)
                mh = max(s.w for s in layer)
            out.append((tw, mh))
        return out, sizes

    def measure(self, theme: Theme) -> BBox:
        extents, _ = self._layer_extents(theme)
        layer_gap = theme.gap_px(self.layer_gap)
        if self.direction == "down":
            w = max((tw for tw, _ in extents), default=0)
            h = sum(mh for _, mh in extents) + layer_gap * (len(extents) - 1)
        else:
            w = sum(mh for _, mh in extents) + layer_gap * (len(extents) - 1)
            h = max((tw for tw, _ in extents), default=0)
        return BBox(w, h)

    def _node_positions(self, theme: Theme, x: float, y: float):
        """Return positions[layer][node] = (cx, cy, w, h) for each node."""
        extents, sizes = self._layer_extents(theme)
        outer = self.measure(theme)
        layer_gap = theme.gap_px(self.layer_gap)
        node_gap = theme.gap_px(self.node_gap)
        out = []
        if self.direction == "down":
            cur_y = y
            for li, layer in enumerate(self.layers):
                tw, mh = extents[li]
                cur_x = x + (outer.w - tw) / 2
                row = []
                for ni, sz in enumerate(sizes[li]):
                    nx = cur_x
                    ny = cur_y + (mh - sz.h) / 2
                    row.append((nx + sz.w / 2, ny + sz.h / 2, sz.w, sz.h))
                    cur_x += sz.w + node_gap
                out.append(row)
                cur_y += mh + layer_gap
        else:
            cur_x = x
            for li, layer in enumerate(self.layers):
                tw, mw = extents[li]
                cur_y = y + (outer.h - tw) / 2
                row = []
                for ni, sz in enumerate(sizes[li]):
                    nx = cur_x + (mw - sz.w) / 2
                    ny = cur_y
                    row.append((nx + sz.w / 2, ny + sz.h / 2, sz.w, sz.h))
                    cur_y += sz.h + node_gap
                out.append(row)
                cur_x += mw + layer_gap
        return out, sizes

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        positions, sizes = self._node_positions(theme, x, y)

        # Edges first (so they sit behind nodes)
        for e in self.edges:
            if len(e) == 4:
                sl, si, dl, di = e; col = self.edge_color
            elif len(e) == 5:
                sl, si, dl, di, col = e
            else:
                raise ValueError(f"edge spec: (src_layer, src_idx, dst_layer, dst_idx[, color])")
            try:
                scx, scy, sw, sh = positions[sl][si]
                dcx, dcy, dw, dh = positions[dl][di]
            except IndexError:
                continue
            color = theme.color_of(col)
            # Source bottom (or right) anchor
            if self.direction == "down":
                sx, sy = scx, scy + sh / 2
                ex, ey = dcx, dcy - dh / 2
            else:
                sx, sy = scx + sw / 2, scy
                ex, ey = dcx - dw / 2, dcy
            if self.edge_routing == "orthogonal":
                if self.direction == "down":
                    midy = (sy + ey) / 2
                    d = f"M {sx:.2f},{sy:.2f} L {sx:.2f},{midy:.2f} L {ex:.2f},{midy:.2f} L {ex:.2f},{ey:.2f}"
                else:
                    midx = (sx + ex) / 2
                    d = f"M {sx:.2f},{sy:.2f} L {midx:.2f},{sy:.2f} L {midx:.2f},{ey:.2f} L {ex:.2f},{ey:.2f}"
                canvas.path(d, stroke=color, stroke_width=theme.hairline, fill="none")
            else:
                canvas.line(sx, sy, ex, ey,
                           stroke=color, stroke_width=theme.hairline)

        # Sibling links
        for s in self.sibling_links:
            if len(s) == 3:
                lay, fi, ti = s; col = "accent"
            elif len(s) == 4:
                lay, fi, ti, col = s
            else:
                raise ValueError(f"sibling link: (layer, from_idx, to_idx[, color])")
            color = theme.color_of(col)
            cf = positions[lay][fi]
            ct = positions[lay][ti]
            sx = cf[0] + cf[2] / 2
            sy = cf[1]
            ex = ct[0] - ct[2] / 2
            ey = ct[1]
            marker = canvas.define_marker(color=color, size=4, name_hint="sib")
            canvas.line(sx, sy, ex, ey,
                       stroke=color, stroke_width=theme.line,
                       marker_end=marker)

        # Nodes
        for li, layer in enumerate(self.layers):
            for ni, node in enumerate(layer):
                cx, cy, w, h = positions[li][ni]
                node.render(canvas, cx - w / 2, cy - h / 2, theme)
