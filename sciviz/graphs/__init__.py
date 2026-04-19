"""Generic graph and flow primitives.

These replace the hand-rolled custom elements that kept appearing in the
showcase diagrams.  Each one is generic enough to cover a class of figures
across hardware, systems, ML, theory, and algorithms.

* :class:`Token`    -- a small labelled chip (replaces ``Box`` boilerplate
                       for tokens, code letters, picograms, ...).
* :class:`Tokens`   -- a row of equal-width chips (handles vertical
                       alignment of differing-length tokens automatically).
* :class:`Tree`     -- generic top-down tree with arbitrary :class:`Element`
                       nodes and per-edge colour / label / style.
* :class:`NodeTree` -- DEPRECATED alias for :class:`Tree`, retained for
                       back-compat. New callers should use :class:`Tree`.
* :class:`Sequence` -- UML-style sequence diagram with lifelines and
                       message arrows between participants.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence as Seq, Tuple, Union

from ..core import Element, BBox, Canvas, Theme

from ._tree import Tree, TreeNode


# ---------------------------------------------------------------------------
# Token / Tokens
# ---------------------------------------------------------------------------

class Token(Element):
    """A small labelled chip with a coloured border.

    Designed for use as a building-block of language-model token sequences,
    code letter cells, finite-automaton states, etc.  Width is intrinsic to
    the label by default, but can be fixed (which makes a row of tokens
    auto-align cleanly).

    Parameters
    ----------
    label : str
    role : str
        Color role: ``"blue"``, ``"green"``, ``"amber"``, ``"red"``,
        ``"neutral"``, ``"accept"`` (= green soft), ``"reject"`` (= red soft).
    variant : str
        ``"soft"`` (default, pale background + role-coloured border + dark
        text) or ``"fill"`` (saturated background + white text).
    width : float, optional
        Fix the chip width; default is intrinsic.
    height : float
        Chip height; default 22.
    """

    _ROLE_ALIASES = {
        "accept": ("green", "soft"),
        "reject": ("red",   "soft"),
        "ok":     ("green", "soft"),
        "warn":   ("amber", "soft"),
        "info":   ("blue",  "soft"),
    }

    def __init__(self, label: str, *,
                 role: str = "neutral",
                 variant: str = "soft",
                 width: Optional[float] = None,
                 height: float = 22.0):
        # collapse aliases
        if role in self._ROLE_ALIASES:
            role, variant = self._ROLE_ALIASES[role]
        self.label = str(label)
        self.role = role
        self.variant = variant
        self.width = width
        self.height = height

    def _intrinsic_w(self, theme: Theme) -> float:
        return theme.text_width(self.label, "small", bold=True) + theme.unit * 1.6

    def measure(self, theme: Theme) -> BBox:
        w = self.width if self.width is not None else self._intrinsic_w(theme)
        return BBox(max(w, theme.unit * 3), self.height)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        if self.role == "neutral":
            fill = theme.color_of("bg_panel")
            stroke = theme.color_of("text")
            text_col = theme.color_of("text")
        elif self.variant == "fill":
            fill = theme.role(self.role, "fill")
            stroke = theme.role(self.role, "stroke")
            text_col = theme.text_on(fill)
        else:
            fill = theme.role(self.role, "soft")
            stroke = theme.role(self.role, "stroke")
            text_col = theme.role(self.role, "ink")
        canvas.rect(x, y, size.w, size.h,
                   fill=fill, stroke=stroke,
                   stroke_width=theme.hairline, rx=2)
        canvas.text(x + size.w / 2,
                   y + size.h / 2 + theme.size_px("small") * 0.33,
                   self.label,
                   size=theme.size_px("small"),
                   fill=text_col, weight="700", anchor="middle")


class Tokens(Element):
    """A horizontal sequence of equal-width :class:`Token` chips.

    All chips are sized to fit the longest label, so a row like
    ``Tokens(["The", "cat", "spat"])`` aligns vertically with another row
    ``Tokens(["The", "cat", "ate"])``.

    Items may be:
      * a string -- becomes a neutral token
      * a tuple ``(label, role)``  e.g. ``("hi", "accept")``
      * an :class:`Element` -- placed as-is (also gets the equal-width slot)
    """

    def __init__(self, items: Seq, *,
                 height: float = 22.0,
                 gap: Union[str, float] = "xs"):
        self.items = list(items)
        self.height = height
        self.gap = gap

    def _coerce(self, it):
        if isinstance(it, Element):
            return it
        if isinstance(it, str):
            return Token(it, role="neutral", height=self.height)
        if isinstance(it, tuple) and len(it) == 2:
            return Token(it[0], role=it[1], height=self.height)
        raise TypeError(f"Tokens item: str, (label, role) tuple, or Element; got {it}")

    def _kids(self):
        return [self._coerce(it) for it in self.items]

    def measure(self, theme: Theme) -> BBox:
        kids = self._kids()
        if not kids:
            return BBox(0, 0)
        sizes = [k.measure(theme) for k in kids]
        slot = max(s.w for s in sizes)
        g = theme.gap_px(self.gap)
        return BBox(slot * len(kids) + g * (len(kids) - 1),
                    max(s.h for s in sizes))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        kids = self._kids()
        sizes = [k.measure(theme) for k in kids]
        slot = max(s.w for s in sizes)
        g = theme.gap_px(self.gap)
        H = max(s.h for s in sizes)
        cx = x
        for k, s in zip(kids, sizes):
            cy = y + (H - s.h) / 2
            k.render(canvas, cx + (slot - s.w) / 2, cy, theme)
            cx += slot + g


# ---------------------------------------------------------------------------
# NodeTree -- a tree of multi-cell pages (B+, B-tree, decision tree, parse tree)
# ---------------------------------------------------------------------------

class NodeTree(Element):
    """Top-down tree where each node is a sequence of cells (one or more).

    Generic enough to draw:
      * B+ trees (internal pages, leaf pages with sibling pointers)
      * B-trees, R-trees
      * decision trees (single-cell internal node, two children)
      * abstract syntax trees
      * any tree where each node is a small ordered group of items

    Each node is a tuple ``(cells, children)`` where ``cells`` is a list of
    strings (or a single string for one-cell nodes) and ``children`` is a
    list of subtree tuples.  Leaf pages have ``children=[]``.

    Parameters
    ----------
    root : tuple
    cell_w, cell_h : float
        Per-cell dimensions.
    level_gap, page_gap : float
        Vertical and horizontal gaps.
    leaf_role : str, optional
        Color role for leaves (default ``"green"``).  ``None`` -> no fill.
    sibling_links : bool
        Draw sibling-pointer arrows between leaves (B+ tree style).
    """

    def __init__(self, root, *,
                 cell_w: float = 28.0, cell_h: float = 22.0,
                 cell_sep: float = 2.0,
                 level_gap: float = 36.0, page_gap: float = 14.0,
                 leaf_role: Optional[str] = "green",
                 sibling_links: bool = True):
        self.root = self._normalise(root)
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.cell_sep = cell_sep
        self.level_gap = level_gap
        self.page_gap = page_gap
        self.leaf_role = leaf_role
        self.sibling_links = sibling_links

    @staticmethod
    def _normalise(node):
        if isinstance(node, str):
            return ([node], [])
        if isinstance(node, list):
            return (list(node), [])
        if isinstance(node, tuple):
            if len(node) == 2:
                cells, children = node
                if isinstance(cells, str):
                    cells = [cells]
                return (list(cells), [NodeTree._normalise(c) for c in (children or [])])
        raise ValueError(f"Bad NodeTree node: {node!r}")

    def _page_w(self, cells):
        return len(cells) * self.cell_w + (len(cells) - 1) * self.cell_sep + 4

    def _subtree_w(self, node) -> float:
        cells, children = node
        own = self._page_w(cells)
        if not children:
            return own
        children_w = sum(self._subtree_w(c) for c in children) + self.page_gap * (len(children) - 1)
        return max(own, children_w)

    def _depth(self, node) -> int:
        cells, children = node
        if not children:
            return 1
        return 1 + max(self._depth(c) for c in children)

    def measure(self, theme: Theme) -> BBox:
        W = self._subtree_w(self.root)
        D = self._depth(self.root)
        H = D * self.cell_h + (D - 1) * self.level_gap
        return BBox(W, H)

    def _draw_node(self, canvas, x, y, cells, is_leaf, theme):
        pw = self._page_w(cells)
        fill = (theme.role(self.leaf_role, "soft")
                if is_leaf and self.leaf_role else "#ffffff")
        canvas.rect(x, y, pw, self.cell_h,
                   fill=fill,
                   stroke=theme.color_of("text"),
                   stroke_width=theme.hairline, rx=1.5)
        cx = x + 2
        for c in cells:
            canvas.rect(cx, y + 2, self.cell_w, self.cell_h - 4,
                       fill="none",
                       stroke=theme.color_of("border"),
                       stroke_width=theme.hairline, rx=1)
            canvas.text(cx + self.cell_w / 2,
                       y + self.cell_h / 2 + theme.size_px("small") * 0.33,
                       str(c),
                       size=theme.size_px("small"),
                       fill=theme.color_of("text"),
                       weight="500" if is_leaf else "700",
                       anchor="middle")
            cx += self.cell_w + self.cell_sep
        return pw

    def _render_rec(self, canvas, node, x, y, theme, leaf_positions):
        cells, children = node
        subtree_w = self._subtree_w(node)
        own_w = self._page_w(cells)
        # center the node within the subtree column
        nx = x + (subtree_w - own_w) / 2
        is_leaf = not children
        self._draw_node(canvas, nx, y, cells, is_leaf, theme)
        if is_leaf:
            leaf_positions.append((nx, y, own_w))
        if children:
            child_widths = [self._subtree_w(c) for c in children]
            total = sum(child_widths) + self.page_gap * (len(children) - 1)
            start_x = x + (subtree_w - total) / 2
            child_y = y + self.cell_h + self.level_gap
            cursor = start_x
            for c, cw in zip(children, child_widths):
                # connect parent-bottom to child-top
                px_anchor = nx + own_w / 2
                cx_anchor = cursor + cw / 2
                canvas.line(px_anchor, y + self.cell_h,
                           cx_anchor, child_y,
                           stroke=theme.color_of("text"),
                           stroke_width=theme.hairline)
                self._render_rec(canvas, c, cursor, child_y, theme, leaf_positions)
                cursor += cw + self.page_gap

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        leaf_positions: List[Tuple[float, float, float]] = []
        self._render_rec(canvas, self.root, x, y, theme, leaf_positions)
        # sibling pointer arrows between leaves
        if self.sibling_links and self.leaf_role and len(leaf_positions) >= 2:
            arrow_color = theme.role(self.leaf_role, "stroke")
            marker = canvas.define_marker(color=arrow_color, size=4,
                                          name_hint="leafArr")
            for i in range(len(leaf_positions) - 1):
                lx, ly, lw = leaf_positions[i]
                rx, ry, rw = leaf_positions[i + 1]
                y_mid = ly + self.cell_h / 2
                canvas.line(lx + lw, y_mid, rx, y_mid,
                           stroke=arrow_color,
                           stroke_width=theme.line,
                           marker_end=marker)


# ---------------------------------------------------------------------------
# Sequence -- UML-style sequence diagram
# ---------------------------------------------------------------------------

class Sequence(Element):
    """UML-style sequence diagram with vertical lifelines and message arrows.

    Parameters
    ----------
    actors : list of str
        Names of the participants, left to right.
    messages : list of tuples
        Each message is ``(t, src, dst, label)`` or
        ``(t, src, dst, label, role)``.  ``t`` is a vertical position
        index (0..max_t), ``src`` and ``dst`` are actor names or indices.
        Self-arrows (src == dst) render as a small loop.
    width : float
        Total drawing width.
    actor_h : float
        Height of the actor box at the top.
    rows : int, optional
        Number of message rows (default = max(t)+1).
    row_h : float
        Vertical spacing between message rows.
    """

    def __init__(self, actors: Seq[str], messages: Seq,
                 *, width: float = 540.0,
                 actor_h: float = 28.0,
                 rows: Optional[int] = None,
                 row_h: float = 28.0):
        self.actors = list(actors)
        self.messages = list(messages)
        self.width = width
        self.actor_h = actor_h
        self.rows = rows
        self.row_h = row_h

    def _resolve_actor(self, a):
        if isinstance(a, int):
            return a
        return self.actors.index(a)

    def _max_t(self) -> int:
        if self.rows is not None:
            return self.rows - 1
        return max((m[0] for m in self.messages), default=0)

    def measure(self, theme: Theme) -> BBox:
        max_t = self._max_t()
        H = self.actor_h + (max_t + 2) * self.row_h
        return BBox(self.width, H)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        n = len(self.actors)
        if n == 0:
            return
        col_w = self.width / n
        col_centres = [x + (i + 0.5) * col_w for i in range(n)]
        max_t = self._max_t()
        # actor boxes at the top
        for i, name in enumerate(self.actors):
            cx = col_centres[i]
            box_w = min(col_w - 12,
                        theme.text_width(name, "label", bold=True) + theme.unit * 2.4)
            box_w = max(box_w, theme.unit * 8)
            canvas.rect(cx - box_w / 2, y, box_w, self.actor_h,
                       fill=theme.color_of("bg_subtle"),
                       stroke=theme.color_of("text"),
                       stroke_width=theme.hairline, rx=2)
            canvas.text(cx, y + self.actor_h / 2 + theme.size_px("label") * 0.33,
                       name, size=theme.size_px("label"),
                       fill=theme.color_of("text"),
                       weight="700", anchor="middle")
        # lifelines (dashed verticals)
        ll_top = y + self.actor_h + 2
        ll_bot = y + self.actor_h + (max_t + 2) * self.row_h - 4
        for cx in col_centres:
            canvas.line(cx, ll_top, cx, ll_bot,
                       stroke=theme.color_of("text_faint"),
                       stroke_width=theme.hairline,
                       dasharray="3,3")
        # messages
        for m in self.messages:
            if len(m) == 4:
                t, src, dst, label = m; role = None
            elif len(m) == 5:
                t, src, dst, label, role = m
            else:
                raise ValueError(
                    f"Sequence message: (t, src, dst, label[, role]); got {m}")
            si = self._resolve_actor(src)
            di = self._resolve_actor(dst)
            row_y = y + self.actor_h + (t + 1) * self.row_h
            color = (theme.role(role, "fill") if role
                     else theme.color_of("text"))
            marker = canvas.define_marker(color=color, size=5,
                                          name_hint=f"seq{role or 'k'}")
            if si == di:
                # self-loop arc to the right
                cx = col_centres[si]
                rx = 18
                d = (f"M {cx} {row_y - 6} "
                     f"C {cx + rx} {row_y - 6} "
                     f"{cx + rx} {row_y + 6} "
                     f"{cx + 2} {row_y + 6}")
                canvas.path(d, stroke=color, stroke_width=theme.line,
                           marker_end=marker)
                canvas.text(cx + rx + 4, row_y + theme.size_px("small") * 0.33,
                           label, size=theme.size_px("small"),
                           fill=theme.color_of("text"))
            else:
                x1 = col_centres[si]
                x2 = col_centres[di]
                # offset to avoid overlapping the lifeline circle
                offset = 1
                dx = -offset if x2 > x1 else offset
                canvas.line(x1, row_y, x2 + dx, row_y,
                           stroke=color, stroke_width=theme.line,
                           marker_end=marker)
                # label centered above the line
                mid_x = (x1 + x2) / 2
                canvas.text(mid_x, row_y - 3,
                           label, size=theme.size_px("small"),
                           fill=theme.color_of("text"),
                           weight="500", anchor="middle")


