"""Tree: generic top-down tree of arbitrary :class:`Element` nodes.

Unlike :class:`NodeTree` (which renders compact multi-cell pages of
strings), :class:`Tree` takes *elements* as nodes. That means a tree can
mix text boxes, tokens, math labels, or bespoke composites at any depth.
Edges carry their own style and can be individually coloured, dashed,
and labelled:

    Tree.node(
        Text("root"),
        children=[
            (Tree.node(Box("A")), {"color": "green", "label": "accept"}),
            (Tree.node(Box("B")), {"color": "red", "label": "reject", "style": "dashed"}),
        ],
    )

The element is measure-stable under the usual :class:`Element` contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


@dataclass
class TreeNode:
    """A single tree node with a content element and child nodes.

    ``children`` is a list of ``(TreeNode, edge_style_dict)`` tuples; the
    plain ``TreeNode`` form with no edge style is also accepted via
    :meth:`Tree.node`.
    """

    content: Element
    children: List[Tuple["TreeNode", Dict[str, Any]]] = field(default_factory=list)


class Tree(Element):
    """Generic top-down tree rendered from :class:`TreeNode`-structured data.

    Each edge can be individually styled via its edge dict:

    * ``color`` -- semantic colour role or hex; default "text".
    * ``style`` -- ``"solid"`` (default), ``"dashed"``, or ``"dotted"``.
    * ``label`` -- short string drawn near the midpoint of the edge.
    * ``width`` -- stroke width in px; default ``theme.line``.

    Parameters
    ----------
    root : TreeNode
    level_gap : float
        Vertical spacing between tree depths.
    page_gap : float
        Horizontal spacing between sibling subtrees.
    edge_padding : float
        Distance in px the edge keeps away from each node's bbox, so the
        line doesn't visually kiss the border.
    label_size : str
        Theme size token for edge labels.
    """

    def __init__(self, root: TreeNode, *,
                 level_gap: float = 36.0,
                 page_gap: float = 18.0,
                 edge_padding: float = 2.0,
                 label_size: str = "small"):
        self.root = root
        self.level_gap = float(level_gap)
        self.page_gap = float(page_gap)
        self.edge_padding = float(edge_padding)
        self.label_size = label_size

    # ---- constructors ---------------------------------------------------

    @staticmethod
    def node(content: Element,
             *,
             children: Optional[List[Union["TreeNode",
                                           Tuple["TreeNode", Dict[str, Any]]]]] = None,
             ) -> TreeNode:
        """Convenience constructor: coerces ``children`` entries to
        ``(TreeNode, edge_dict)`` pairs.

        A bare :class:`TreeNode` child is treated as an unstyled edge.
        """
        kids: List[Tuple[TreeNode, Dict[str, Any]]] = []
        for c in children or []:
            if isinstance(c, TreeNode):
                kids.append((c, {}))
            elif isinstance(c, tuple) and len(c) == 2 and isinstance(c[0], TreeNode):
                kids.append((c[0], dict(c[1] or {})))
            else:
                raise TypeError(
                    f"Tree child must be TreeNode or (TreeNode, dict); got {c!r}")
        return TreeNode(content=content, children=kids)

    # ---- measurement ----------------------------------------------------

    def _subtree_w(self, node: TreeNode, theme: Theme) -> float:
        own = node.content.measure(theme).w
        if not node.children:
            return own
        kids_w = sum(self._subtree_w(c, theme) for c, _ in node.children)
        kids_w += self.page_gap * (len(node.children) - 1)
        return max(own, kids_w)

    def _row_heights(self, node: TreeNode, theme: Theme,
                     heights: List[float], depth: int = 0) -> None:
        h = node.content.measure(theme).h
        if depth >= len(heights):
            heights.append(h)
        else:
            heights[depth] = max(heights[depth], h)
        for c, _ in node.children:
            self._row_heights(c, theme, heights, depth + 1)

    def measure(self, theme: Theme) -> BBox:
        w = self._subtree_w(self.root, theme)
        heights: List[float] = []
        self._row_heights(self.root, theme, heights)
        h = sum(heights) + self.level_gap * (len(heights) - 1)
        return BBox(w, h)

    # ---- rendering ------------------------------------------------------

    def _row_starts(self, theme: Theme) -> List[float]:
        heights: List[float] = []
        self._row_heights(self.root, theme, heights)
        starts = [0.0]
        for h in heights:
            starts.append(starts[-1] + h + self.level_gap)
        return starts, heights

    def _render_rec(self, canvas: Canvas, node: TreeNode,
                    x: float, y: float, theme: Theme,
                    row_starts: List[float], row_heights: List[float],
                    depth: int = 0) -> None:
        subtree_w = self._subtree_w(node, theme)
        own = node.content.measure(theme)
        # Centre this node within its subtree band.
        nx = x + (subtree_w - own.w) / 2
        row_h = row_heights[depth]
        ny = y + row_starts[depth] + (row_h - own.h) / 2
        node.content.render(canvas, nx, ny, theme)

        if not node.children:
            return

        # Parent anchor: bottom-centre of THIS node.
        parent_anchor = (nx + own.w / 2, ny + own.h)

        kid_widths = [self._subtree_w(c, theme) for c, _ in node.children]
        total_kids = sum(kid_widths) + self.page_gap * (len(kid_widths) - 1)
        start_x = x + (subtree_w - total_kids) / 2
        cursor = start_x

        for (child, edge), kw in zip(node.children, kid_widths):
            child_own = child.content.measure(theme)
            child_row_h = row_heights[depth + 1]
            child_nx = cursor + (kw - child_own.w) / 2
            child_ny = (y + row_starts[depth + 1]
                        + (child_row_h - child_own.h) / 2)
            child_anchor = (child_nx + child_own.w / 2, child_ny)

            color = theme.color_of(edge.get("color", "text"))
            style = edge.get("style", "solid")
            dash = None
            if style == "dashed":
                dash = "4,3"
            elif style == "dotted":
                dash = "1,2"
            sw = edge.get("width", theme.line)

            # Edge endpoints with padding off the node faces.
            p1 = (parent_anchor[0], parent_anchor[1] + self.edge_padding)
            p2 = (child_anchor[0], child_anchor[1] - self.edge_padding)
            canvas.line(p1[0], p1[1], p2[0], p2[1],
                        stroke=color, stroke_width=sw, dasharray=dash)

            # Edge label: draw near the midpoint, offset to the side.
            label = edge.get("label")
            if label:
                mx = (p1[0] + p2[0]) / 2
                my = (p1[1] + p2[1]) / 2
                canvas.text(mx + 4, my,
                            label, size=theme.size_px(self.label_size),
                            fill=theme.color_of(edge.get("label_color", "muted")))

            self._render_rec(canvas, child, cursor, y, theme,
                             row_starts, row_heights, depth + 1)
            cursor += kw + self.page_gap

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        row_starts, row_heights = self._row_starts(theme)
        self._render_rec(canvas, self.root, x, y, theme, row_starts, row_heights)
