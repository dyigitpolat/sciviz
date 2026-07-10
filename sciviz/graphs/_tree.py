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
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

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
                 level_gap: Union[str, float] = "auto",
                 page_gap: Union[str, float] = "auto",
                 edge_padding: Union[str, float] = "auto",
                 label_size: str = "small",
                 level_labels: Optional[Mapping[int, str]] = None):
        self.root = root
        self.level_gap = level_gap
        self.page_gap = page_gap
        self.edge_padding = edge_padding
        self.label_size = label_size
        self.level_labels = dict(level_labels or {})
        if any(isinstance(depth, bool) or not isinstance(depth, int)
               or depth < 0 for depth in self.level_labels):
            raise ValueError("Tree.level_labels keys must be non-negative depths")
        if any(not isinstance(label, str) or not label
               for label in self.level_labels.values()):
            raise ValueError("Tree.level_labels values must be non-empty strings")

    @staticmethod
    def _spacing(theme: Theme, value: Union[str, float], *, kind: str) -> float:
        if isinstance(value, str):
            if value == "auto":
                if kind == "edge":
                    # Tree branches are headless structural strokes; unlike
                    # arrowheads they should meet the node boundary cleanly.
                    return 0.0
                token = {"level": "xl", "page": "md"}[kind]
            else:
                token = value
            return theme.gap_px(token)
        resolved = float(value)
        if resolved < 0:
            raise ValueError("Tree spacing must be non-negative")
        return resolved

    def _level_gap(self, theme: Theme) -> float:
        return self._spacing(theme, self.level_gap, kind="level")

    def _page_gap(self, theme: Theme) -> float:
        return self._spacing(theme, self.page_gap, kind="page")

    def _edge_padding(self, theme: Theme) -> float:
        return self._spacing(theme, self.edge_padding, kind="edge")

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
        kids_w += self._page_gap(theme) * (len(node.children) - 1)
        return max(own, kids_w)

    @staticmethod
    def _node_face(node: TreeNode, theme: Theme):
        face = node.content.primary_anchor_bbox(theme)
        return face if face is not None else node.content.content_bbox(theme)

    def _row_metrics(self, node: TreeNode, theme: Theme,
                     metrics: List[List[float]], depth: int = 0) -> None:
        size = node.content.measure(theme)
        _fx, fy, _fw, fh = self._node_face(node, theme)
        top = fy
        bottom = size.h - fy - fh
        if depth >= len(metrics):
            metrics.append([top, fh, bottom])
        else:
            metrics[depth][0] = max(metrics[depth][0], top)
            metrics[depth][1] = max(metrics[depth][1], fh)
            metrics[depth][2] = max(metrics[depth][2], bottom)
        for c, _ in node.children:
            self._row_metrics(c, theme, metrics, depth + 1)

    def measure(self, theme: Theme) -> BBox:
        tree_w = self._subtree_w(self.root, theme)
        band_w = max(
            (theme.text_width(label, "small", bold=True) + 2 * theme.unit
             for label in self.level_labels.values()),
            default=0.0,
        )
        w = max(tree_w, band_w)
        metrics: List[List[float]] = []
        self._row_metrics(self.root, theme, metrics)
        heights = [top + face + bottom for top, face, bottom in metrics]
        h = sum(heights) + self._level_gap(theme) * (len(heights) - 1)
        return BBox(w, h)

    # ---- rendering ------------------------------------------------------

    def _row_starts(self, theme: Theme):
        metrics: List[List[float]] = []
        self._row_metrics(self.root, theme, metrics)
        starts = [0.0]
        gap = self._level_gap(theme)
        for top, face, bottom in metrics:
            h = top + face + bottom
            starts.append(starts[-1] + h + gap)
        return starts, metrics

    def _render_level_bands(self, canvas: Canvas, x: float, y: float,
                            theme: Theme, row_starts: List[float],
                            row_heights: List[float]) -> None:
        if not self.level_labels:
            return
        total = self.measure(theme)
        inset = theme.unit * 0.55
        color = theme.paint_of("border_strong")
        for depth, label in self.level_labels.items():
            if depth >= len(row_heights):
                raise ValueError(
                    f"Tree level label depth {depth} exceeds tree depth "
                    f"{len(row_heights) - 1}"
                )
            top = max(0.0, row_starts[depth] - inset)
            bottom = min(total.h, row_starts[depth] + row_heights[depth] + inset)
            canvas.rect(
                x, y + top, total.w, bottom - top,
                fill="none", stroke=color,
                stroke_width=theme.hairline,
                rx=max(theme.panel_radius, theme.unit * 0.55),
                dasharray="4,3",
            )
            size = theme.size_px("small")
            canvas.text(
                x + theme.unit,
                y + (top + bottom) / 2.0 + size * 0.33,
                label,
                size=size, fill=color, weight="700", anchor="start",
            )

    def _render_rec(self, canvas: Canvas, node: TreeNode,
                    x: float, y: float, theme: Theme,
                    row_starts: List[float], row_metrics: List[List[float]],
                    depth: int = 0) -> None:
        subtree_w = self._subtree_w(node, theme)
        own = node.content.measure(theme)
        fx, fy, fw, fh = self._node_face(node, theme)
        # Centre the semantic face within its subtree band; decorations may
        # extend above/below without moving sibling faces off the depth row.
        nx = x + subtree_w / 2.0 - (fx + fw / 2.0)
        max_top, max_face_h, _max_bottom = row_metrics[depth]
        ny = (y + row_starts[depth] + max_top + max_face_h / 2.0
              - (fy + fh / 2.0))
        node.content.render(canvas, nx, ny, theme)

        if not node.children:
            return

        # Parent anchor: bottom-centre of THIS node.
        parent_anchor = (nx + fx + fw / 2, ny + fy + fh)

        kid_widths = [self._subtree_w(c, theme) for c, _ in node.children]
        page_gap = self._page_gap(theme)
        total_kids = sum(kid_widths) + page_gap * (len(kid_widths) - 1)
        start_x = x + (subtree_w - total_kids) / 2
        cursor = start_x

        for (child, edge), kw in zip(node.children, kid_widths):
            child_own = child.content.measure(theme)
            cfx, cfy, cfw, cfh = self._node_face(child, theme)
            child_nx = cursor + kw / 2.0 - (cfx + cfw / 2.0)
            ctop, cface_h, _cbottom = row_metrics[depth + 1]
            child_ny = (y + row_starts[depth + 1] + ctop + cface_h / 2.0
                        - (cfy + cfh / 2.0))
            child_anchor = (
                child_nx + cfx + cfw / 2.0,
                child_ny + cfy,
            )

            color = theme.color_of(edge.get("color", "text"))
            style = edge.get("style", "solid")
            dash = None
            if style == "dashed":
                dash = "4,3"
            elif style == "dotted":
                dash = "1,2"
            if "width" in edge:
                width = edge["width"]
                if isinstance(width, str):
                    try:
                        sw = float(getattr(theme, width))
                    except (AttributeError, TypeError, ValueError) as exc:
                        raise ValueError(
                            "Tree edge width token must name a numeric Theme field"
                        ) from exc
                else:
                    sw = float(width)
            else:
                # A semantically coloured route is normally the selected or
                # exceptional path. Give it one automatic visual-weight step
                # so authors declare meaning, not a copied stroke pixel.
                sw = theme.thick if edge.get("color", "text") != "text" \
                    else theme.line

            # Edge endpoints with padding off the node faces.
            edge_padding = self._edge_padding(theme)
            p1 = (parent_anchor[0], parent_anchor[1] + edge_padding)
            p2 = (child_anchor[0], child_anchor[1] - edge_padding)
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
                             row_starts, row_metrics, depth + 1)
            cursor += kw + page_gap

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        row_starts, row_metrics = self._row_starts(theme)
        row_heights = [sum(metric) for metric in row_metrics]
        size = self.measure(theme)
        tree_w = self._subtree_w(self.root, theme)
        tree_x = x + (size.w - tree_w) / 2.0
        self._render_level_bands(canvas, x, y, theme, row_starts, row_heights)
        self._render_rec(canvas, self.root, tree_x, y, theme,
                         row_starts, row_metrics)
