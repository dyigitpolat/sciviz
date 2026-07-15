"""Semantic directed-flow graphs with automatic ranked layout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Union

from ..composition import Anchor, Region, _anchor_stack
from ..connect import Connect
from ..core import BBox, Canvas, Element, Theme
from ..elements import Box, Cylinder, Document, Text
from ..elements._obstacles import _register_implicit_obstacle
from ..layout import Column, Row


@dataclass(frozen=True)
class FlowPort:
    name: str
    side: str = "auto"
    marker: str = "none"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("FlowPort.name must be non-empty")
        if self.side not in ("auto", "left", "right", "top", "bottom"):
            raise ValueError("FlowPort.side must be auto/left/right/top/bottom")
        if self.marker not in ("none", "triangle", "circle"):
            raise ValueError("FlowPort.marker must be none/triangle/circle")


@dataclass(frozen=True)
class FlowRef:
    node: str
    port: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.node:
            raise ValueError("FlowRef.node must be non-empty")


Endpoint = Union[str, FlowRef]
Endpoints = Union[Endpoint, Sequence[Endpoint]]


@dataclass(frozen=True)
class FlowNode:
    id: str
    content: Union[str, Element]
    shape: str = "auto"
    rank: Optional[str] = None
    group: Optional[str] = None
    role: Any = "primary"
    ports: Sequence[FlowPort] = ()
    lane: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("FlowNode.id must be non-empty")
        if not isinstance(self.content, (str, Element)):
            raise TypeError("FlowNode.content must be a string or Element")
        if self.shape not in (
            "auto", "content", "process", "decision", "store",
            "document", "terminator",
        ):
            raise ValueError("unknown FlowNode.shape")
        ports = tuple(self.ports)
        if any(not isinstance(port, FlowPort) for port in ports):
            raise TypeError("FlowNode.ports must contain FlowPort values")
        names = [port.name for port in ports]
        if len(names) != len(set(names)):
            raise ValueError(f"FlowNode {self.id!r} has duplicate port names")
        object.__setattr__(self, "ports", ports)


@dataclass(frozen=True)
class FlowEdge:
    src: Endpoints
    dst: Endpoints
    label: Optional[str] = None
    role: Any = "text"
    dashed: bool = False
    head: bool = True
    kind: str = "flow"

    def __post_init__(self) -> None:
        if self.kind not in ("flow", "feedback"):
            raise ValueError("FlowEdge.kind must be 'flow' or 'feedback'")
        if not isinstance(self.head, bool):
            raise TypeError("FlowEdge.head must be bool")


@dataclass(frozen=True)
class FlowGroup:
    id: str
    label: Optional[str] = None
    parent: Optional[str] = None
    role: Any = "muted"
    dashed: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("FlowGroup.id must be non-empty")


def _soft(theme: Theme, role) -> str:
    if hasattr(role, "soft"):
        return theme.color_of(role.soft())
    try:
        return theme.role(str(role), "soft")
    except Exception:
        return theme.color_of("bg_subtle")


class _FlowShape(Element):
    """Content-sized flowchart node; geometry remains library-owned."""

    def __init__(self, content: Union[str, Element], shape: str, role, *,
                 peer_key: str) -> None:
        self.content = (Text(content, size="small", weight="700", align="center")
                        if isinstance(content, str) else content)
        self.shape = shape
        self.role = role
        # Shape normalisation is deliberately rank-local.  Four workers in
        # one band should paint as equal boxes, but a short launch node must
        # not become as wide as a prose-heavy process several ranks later.
        self.shape_key = f"flow:{peer_key}:{shape}"
        self.min_width = 0.0
        self.min_height = 0.0
        # Storage geometry has one SSOT: FlowGraph's ``shape='store'`` is a
        # semantic adapter around the public Cylinder primitive, not a
        # second hand-coded approximation of it.
        self._semantic_shape = (
            Cylinder(
                self.content,
                size="md",
                fill=(role.soft() if hasattr(role, "soft") else "bg_subtle"),
                stroke=role,
            )
            if shape == "store"
            else Document(
                self.content,
                size="md",
                fill=(role.soft() if hasattr(role, "soft") else "bg_subtle"),
                stroke=role,
            )
            if shape == "document"
            else None
        )

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.min_width = max(self.min_width, float(min_w))
        self.min_height = max(self.min_height, float(min_h))
        if self._semantic_shape is not None:
            self._semantic_shape.inflate_to(self.min_width, self.min_height)

    def measure(self, theme: Theme) -> BBox:
        if self._semantic_shape is not None:
            natural = self._semantic_shape.measure(theme)
            return BBox(max(natural.w, self.min_width),
                        max(natural.h, self.min_height))
        content = self.content.measure(theme)
        px, py = theme.unit * 1.25, theme.unit * 0.9
        w, h = content.w + 2 * px, content.h + 2 * py
        if self.shape == "decision":
            # A diamond's sloped sides need both lateral clearance and a
            # sensible aspect.  Multiplying width and height independently
            # made long labels collapse into almost-flat diamonds.  The
            # aspect floor grows height from measured content width, while
            # short labels retain a compact minimum.
            w *= 1.22
            h = max(h * 1.35, w / 2.0, theme.unit * 5.0)
        return BBox(max(w, theme.unit * 6, self.min_width),
                    max(h, theme.unit * 3.2, self.min_height))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        if self._semantic_shape is not None:
            self._semantic_shape.inflate_to(size.w, size.h)
            self._semantic_shape.render(canvas, x, y, theme)
            return
        fill = _soft(theme, self.role)
        stroke = theme.color_of(self.role)
        if self.shape == "decision":
            canvas.polygon(
                [(x + size.w / 2, y), (x + size.w, y + size.h / 2),
                 (x + size.w / 2, y + size.h), (x, y + size.h / 2)],
                fill=fill, stroke=stroke, stroke_width=theme.line,
            )
        else:
            radius = size.h / 2 if self.shape == "terminator" else theme.panel_radius
            canvas.rect(x, y, size.w, size.h, fill=fill, stroke=stroke,
                        stroke_width=theme.line, rx=radius)
        _register_implicit_obstacle(x, y, size.w, size.h)
        content = self.content.measure(theme)
        self.content.render(canvas, x + (size.w - content.w) / 2,
                            y + (size.h - content.h) / 2, theme)


class _PortMarkers(Element):
    def __init__(self, child: Element, ports: Sequence[FlowPort], role) -> None:
        self.child = child
        self.ports = tuple(ports)
        self.role = role

    def measure(self, theme: Theme) -> BBox:
        return self.child.measure(theme)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.child.inflate_to(min_w, min_h)

    def _positions(self, x: float, y: float, size: BBox):
        by_side: dict[str, list[FlowPort]] = {}
        for port in self.ports:
            if port.marker == "none":
                continue
            side = port.side if port.side != "auto" else "right"
            by_side.setdefault(side, []).append(port)
        out = []
        for side, ports in by_side.items():
            for index, port in enumerate(ports):
                frac = (index + 1) / (len(ports) + 1)
                if side in ("left", "right"):
                    px = x if side == "left" else x + size.w
                    py = y + frac * size.h
                else:
                    px = x + frac * size.w
                    py = y if side == "top" else y + size.h
                out.append((port, side, px, py))
        return out

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.child.measure(theme)
        self.child.render(canvas, x, y, theme)
        color = theme.color_of(self.role)
        radius = theme.unit * 0.42
        for port, side, px, py in self._positions(x, y, size):
            if port.marker == "circle":
                canvas.circle(px, py, radius, fill="white", stroke=color,
                              stroke_width=theme.hairline)
            else:
                if side == "left":
                    points = [(px, py), (px + 2 * radius, py - radius),
                              (px + 2 * radius, py + radius)]
                elif side == "right":
                    points = [(px, py), (px - 2 * radius, py - radius),
                              (px - 2 * radius, py + radius)]
                elif side == "top":
                    points = [(px, py), (px - radius, py + 2 * radius),
                              (px + radius, py + 2 * radius)]
                else:
                    points = [(px, py), (px - radius, py - 2 * radius),
                              (px + radius, py - 2 * radius)]
                canvas.polygon(points, fill="white", stroke=color,
                               stroke_width=theme.hairline)


class _RankAnchor(Anchor):
    """Anchor whose forward rank corridor is owned by FlowGraph."""

    def __init__(self, name: str, child: Element, *, direction: str) -> None:
        super().__init__(name, child)
        self.direction = direction

    def _bump_margin(self, side: str, amount: float) -> None:
        # One shared rank corridor is sufficient for a short forward shaft.
        # Retain cross-axis clearance because feedback loops genuinely route
        # outside the lane stack.
        if self.direction == "down" and side in ("top", "bottom"):
            return
        if self.direction == "right" and side in ("left", "right"):
            return
        super()._bump_margin(side, amount)


class _GroupOverlay(Element):
    def __init__(self, child: Element, groups: Sequence[FlowGroup],
                 members: dict[str, tuple[str, ...]],
                 label_sides: dict[str, str]) -> None:
        self.child = child
        self.groups = tuple(groups)
        self.members = members
        self.label_sides = label_sides

    def _pad(self, theme: Theme) -> float:
        return theme.gap_px("md") if self.groups else 0.0

    def _right_label_reserve(self, theme: Theme) -> float:
        labels = [
            group.label for group in self.groups
            if group.label and self.label_sides.get(group.id) == "right"
        ]
        if not labels:
            return 0.0
        return max(theme.text_width(label, "small") for label in labels) \
            + theme.unit * 0.8

    def measure(self, theme: Theme) -> BBox:
        child = self.child.measure(theme)
        pad = self._pad(theme)
        return BBox(child.w + 2 * pad + self._right_label_reserve(theme),
                    child.h + 2 * pad)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        pad = self._pad(theme)
        registry: dict = {}
        existing = _anchor_stack.get()
        stack = (list(existing) if existing else []) + [registry]
        token = _anchor_stack.set(stack)
        try:
            self.child.render(canvas, x + pad, y + pad, theme)
        finally:
            _anchor_stack.reset(token)

        boxes: dict[str, tuple[float, float, float, float]] = {}
        for group in reversed(self.groups):
            raw = [registry[name] for name in self.members[group.id]
                   if name in registry]
            raw += [boxes[child.id] for child in self.groups
                    if child.parent == group.id and child.id in boxes]
            if not raw:
                continue
            inset = theme.unit * 0.8
            label_side = self.label_sides.get(group.id, "top")
            label_h = theme.text_height("small") + theme.unit * 0.35 \
                if group.label and label_side == "top" else 0.0
            x0 = min(bx for bx, _, _, _ in raw) - inset
            y0 = min(by for _, by, _, _ in raw) - inset - label_h
            x1 = max(bx + bw for bx, _, bw, _ in raw) + inset
            y1 = max(by + bh for _, by, _, bh in raw) + inset
            boxes[group.id] = (x0, y0, x1 - x0, y1 - y0)
            color = theme.color_of(group.role)
            canvas.rect(x0, y0, x1 - x0, y1 - y0, fill="none", stroke=color,
                        stroke_width=theme.hairline, rx=theme.panel_radius,
                        dasharray="4,3" if group.dashed else None)
            if group.label:
                if label_side == "right":
                    canvas.text(
                        x1 + theme.unit * 0.55,
                        y0 + (y1 - y0) / 2 + theme.size_px("small") * 0.3,
                        group.label,
                        size=theme.size_px("small"),
                        fill=color,
                        italic=True,
                        anchor="start",
                    )
                else:
                    canvas.text(x0 + theme.unit * 0.7,
                                y0 + theme.size_px("small") * 0.9,
                                group.label, size=theme.size_px("small"),
                                fill=color, weight="700")

        if existing:
            for outer in existing:
                for group_id, bbox in boxes.items():
                    outer[f"__region_flow_group_{group_id}"] = bbox


class FlowGraph(Element):
    """Lay out a semantic directed graph without authored coordinates."""

    def __init__(self, nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                 groups: Sequence[FlowGroup] = (), direction: str = "right",
                 rank_order: Optional[Sequence[str]] = None,
                 lanes: Optional[Sequence[str]] = None,
                 lane_labels: Optional[dict] = None,
                 rank_labels: Optional[dict] = None) -> None:
        self.nodes = tuple(nodes)
        self.edges = tuple(edges)
        self.groups = tuple(groups)
        if direction not in ("right", "down"):
            raise ValueError("FlowGraph.direction must be 'right' or 'down'")
        self.direction = direction
        self.rank_order = tuple(rank_order) if rank_order is not None else None
        # Lanes are an OPTIONAL cross-flow banding: instead of centring each
        # rank, nodes are aligned into named horizontal bands (rows) that
        # stay straight across every rank. A node with ``lane=None`` under an
        # active lane set spans the whole band stack (a shared root/sink).
        self.lanes = tuple(lanes) if lanes is not None else None
        self.lane_labels = dict(lane_labels) if lane_labels else None
        # ``rank_labels`` writes a per-rank caption in the gutter that runs
        # along the flow (the left gutter for ``direction="down"``). Lane
        # labels then head each track band/column instead.
        self.rank_labels = dict(rank_labels) if rank_labels else None
        self._node_by_id = self._validate()
        self._ranks = self._assign_ranks()
        self._connectors: list[Connect] = []
        self.child = self._build()

    @staticmethod
    def _refs(value: Endpoints) -> tuple[FlowRef, ...]:
        raw = (value,) if isinstance(value, (str, FlowRef)) else tuple(value)
        if not raw:
            raise ValueError("FlowEdge endpoint lists cannot be empty")
        out = []
        for item in raw:
            if isinstance(item, str):
                out.append(FlowRef(item))
            elif isinstance(item, FlowRef):
                out.append(item)
            else:
                raise TypeError("FlowEdge endpoints must be strings or FlowRef")
        return tuple(out)

    def _validate(self) -> dict[str, FlowNode]:
        if not self.nodes:
            raise ValueError("FlowGraph requires at least one node")
        if any(not isinstance(node, FlowNode) for node in self.nodes):
            raise TypeError("FlowGraph.nodes must contain FlowNode values")
        if any(not isinstance(group, FlowGroup) for group in self.groups):
            raise TypeError("FlowGraph.groups must contain FlowGroup values")
        node_by_id = {node.id: node for node in self.nodes}
        if len(node_by_id) != len(self.nodes):
            raise ValueError("FlowGraph node ids must be unique")
        group_by_id = {group.id: group for group in self.groups}
        if len(group_by_id) != len(self.groups):
            raise ValueError("FlowGraph group ids must be unique")
        for group in self.groups:
            if group.parent is not None and group.parent not in group_by_id:
                raise ValueError(f"unknown parent group {group.parent!r}")
        for node in self.nodes:
            if node.group is not None and node.group not in group_by_id:
                raise ValueError(f"FlowNode {node.id!r} uses unknown group {node.group!r}")
        port_names = {node.id: {port.name for port in node.ports}
                      for node in self.nodes}
        for edge in self.edges:
            if not isinstance(edge, FlowEdge):
                raise TypeError("FlowGraph.edges must contain FlowEdge values")
            for ref in self._refs(edge.src) + self._refs(edge.dst):
                if ref.node not in node_by_id:
                    raise ValueError(f"FlowEdge references unknown node {ref.node!r}")
                if ref.port is not None and ref.port not in port_names[ref.node]:
                    raise ValueError(
                        f"FlowEdge references unknown port {ref.node}.{ref.port}")
        if self.rank_order is not None:
            if len(self.rank_order) != len(set(self.rank_order)):
                raise ValueError("rank_order values must be unique")
            known_ranks = {node.rank for node in self.nodes if node.rank is not None}
            missing = known_ranks - set(self.rank_order)
            if missing:
                raise ValueError(f"rank_order omits ranks: {sorted(missing)}")
        if self.lanes is not None:
            if len(self.lanes) != len(set(self.lanes)):
                raise ValueError("FlowGraph lanes must be unique")
            lane_set = set(self.lanes)
            for node in self.nodes:
                if node.lane is None and self.direction == "down":
                    # A ``lane=None`` node spans the whole band stack; that
                    # is only a well-defined cell when bands are rows
                    # (``direction="right"``).
                    raise ValueError(
                        "lane=None spanning nodes require direction='right'; "
                        f"give FlowNode {node.id!r} an explicit lane")
                if node.lane is not None and node.lane not in lane_set:
                    raise ValueError(
                        f"FlowNode {node.id!r} uses unknown lane {node.lane!r}")
            if self.lane_labels:
                for name in self.lane_labels:
                    if name not in lane_set:
                        raise ValueError(f"lane_labels names unknown lane {name!r}")
        return node_by_id

    def _assign_ranks(self) -> dict[str, int]:
        explicit_order = list(self.rank_order or [])
        if not explicit_order:
            for node in self.nodes:
                if node.rank is not None and node.rank not in explicit_order:
                    explicit_order.append(node.rank)
        explicit = {name: index for index, name in enumerate(explicit_order)}
        ranks = {node.id: explicit.get(node.rank, 0) for node in self.nodes}
        locked = {node.id for node in self.nodes if node.rank is not None}
        outgoing = {node.id: [] for node in self.nodes}
        indegree = {node.id: 0 for node in self.nodes}
        for edge in self.edges:
            if edge.kind == "feedback":
                continue
            for src in self._refs(edge.src):
                for dst in self._refs(edge.dst):
                    if src.node == dst.node:
                        continue
                    outgoing[src.node].append(dst.node)
                    indegree[dst.node] += 1
        queue = [node.id for node in self.nodes if indegree[node.id] == 0]
        visited = []
        while queue:
            node_id = queue.pop(0)
            visited.append(node_id)
            for target in outgoing[node_id]:
                candidate = ranks[node_id] + 1
                if target in locked and candidate > ranks[target]:
                    raise ValueError("explicit FlowNode ranks contradict a forward edge")
                if target not in locked:
                    ranks[target] = max(ranks[target], candidate)
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if len(visited) != len(self.nodes):
            raise ValueError("FlowGraph forward edges must be acyclic; use kind='feedback'")
        return ranks

    def rank_for(self, node_id: str) -> int:
        return self._ranks[node_id]

    def _node_element(self, node: FlowNode) -> Element:
        shape = node.shape
        if shape == "auto":
            shape = "process" if isinstance(node.content, str) else "content"
        if shape == "content":
            if not isinstance(node.content, Element):
                return Box(node.content, fill=_soft_placeholder(node.role), stroke=node.role)
            element = node.content
        else:
            element = _FlowShape(
                node.content,
                shape,
                node.role,
                peer_key=str(self._ranks[node.id]),
            )
        return _RankAnchor(
            node.id,
            _PortMarkers(element, node.ports, node.role),
            direction=self.direction,
        )

    def _port_side(self, ref: FlowRef) -> str:
        if ref.port is None:
            return "auto"
        node = self._node_by_id[ref.node]
        return next(port.side for port in node.ports if port.name == ref.port)

    def _build_ranked_bands(self) -> Element:
        rank_values = sorted(set(self._ranks.values()))
        bands = []
        for rank in rank_values:
            elements = [self._node_element(node) for node in self.nodes
                        if self._ranks[node.id] == rank]
            if self.direction == "right":
                bands.append(Column(*elements, gap="md", align="center",
                                    equal_widths=True))
            else:
                bands.append(Row(*elements, gap="md", align="center",
                                 equal_widths=True))
        # Connected anchors already reserve a direction-aware wire shaft on
        # both rank faces. A large stack gap double-charged that clearance
        # and made even simple process chains look loosely typeset.
        has_forward_labels = any(
            edge.label and edge.kind == "flow" for edge in self.edges
        )
        # One medium corridor contains a shaft, arrowhead, and print-safe
        # air.  Labeled ranks receive the next semantic step so text never
        # lands on either node.  This replaces both failure modes: the old
        # double endpoint margin (too loose) and a bare ``xs`` gap (overlap).
        rank_gap = "lg" if has_forward_labels else "md"
        return (Row(*bands, gap=rank_gap, align="center")
                if self.direction == "right"
                else Column(*bands, gap=rank_gap, align="center"))

    def _build_lane_grid(self) -> Element:
        """Cross-flow banding via the named-row :class:`Grid`.

        Corresponding lanes stay on one straight band across every rank and
        empty ``(lane, rank)`` slots read as air. Orientation follows the
        flow ``direction``:

        * ``"right"`` -- lanes are horizontal rows, ranks advance rightward
          as columns, and a ``lane=None`` node spans the whole band stack
          (the natural home for a shared root or sink).
        * ``"down"`` -- ranks are rows advancing downward (``rank_labels``
          caption the left gutter), lanes are side-by-side columns, and each
          named lane heads its column via a labelled enclosure.
        """
        from ..grid import Grid

        lanes = list(self.lanes)
        ranks = sorted(set(self._ranks.values()))
        elements = {node.id: self._node_element(node) for node in self.nodes}

        def _cell(elems):
            if len(elems) == 1:
                return elems[0]
            return Column(*elems, gap="sm", align="center")

        def _nodes_at(rank, lane):
            return [elements[n.id] for n in self.nodes
                    if self._ranks[n.id] == rank and n.lane == lane]

        if self.direction == "right":
            columns: list[dict] = []
            for rank in ranks:
                here = [n for n in self.nodes if self._ranks[n.id] == rank]
                per_lane: dict[str, list] = {}
                spanning: list = []
                for node in here:
                    if node.lane is None:
                        spanning.append(elements[node.id])
                    else:
                        per_lane.setdefault(node.lane, []).append(elements[node.id])
                column: dict = {lane: _cell(es) for lane, es in per_lane.items()}
                if spanning:
                    if per_lane:
                        raise ValueError(
                            "a rank cannot mix lane nodes with a lane=None "
                            "spanning node")
                    column[tuple(lanes)] = _cell(spanning)
                columns.append(column)
            return Grid(rows=lanes, columns=columns,
                        row_labels=self.lane_labels or None,
                        row_gap="lg", col_gap="lg")

        # direction == "down": ranks are rows, lanes are columns. Ranks are
        # keyed by their author-given name (``rank_labels``/``rank_order`` use
        # those names) rather than the internal integer index.
        index_name = {self._ranks[node.id]: node.rank
                      for node in self.nodes if node.rank is not None}
        row_name = {rank: index_name.get(rank, str(rank)) for rank in ranks}
        row_names = [row_name[rank] for rank in ranks]
        columns = []
        for lane in lanes:
            col: dict = {}
            for rank in ranks:
                here = _nodes_at(rank, lane)
                if here:
                    col[row_name[rank]] = _cell(here)
            if self.lane_labels and lane in self.lane_labels:
                col["_panel"] = self.lane_labels[lane]
            columns.append(col)
        row_labels = None
        if self.rank_labels:
            row_labels = {row_name[rank]: self.rank_labels[name]
                          for rank in ranks
                          if (name := index_name.get(rank)) in self.rank_labels}
        return Grid(rows=row_names, columns=columns, row_labels=row_labels,
                    row_gap="lg", col_gap="xl")

    def _build(self) -> Element:
        if self.lanes is not None:
            ranked = self._build_lane_grid()
        else:
            ranked = self._build_ranked_bands()

        members = {
            group.id: tuple(node.id for node in self.nodes if node.group == group.id)
            for group in self.groups
        }
        # A group whose members share one cross-flow band reads as a wide
        # parallel lane.  Its label belongs beside that lane, not in the
        # graph as a fake fifth node and not above it as a new stage.
        label_sides = {}
        for group in self.groups:
            member_ranks = {self._ranks[node_id]
                            for node_id in members[group.id]}
            label_sides[group.id] = (
                "right"
                if (group.label and self.direction == "down"
                    and len(members[group.id]) > 1
                    and len(member_ranks) == 1)
                else "top"
            )
        arranged: Element = _GroupOverlay(
            ranked, self.groups, members, label_sides)
        for edge in self.edges:
            src_refs, dst_refs = self._refs(edge.src), self._refs(edge.dst)
            src: Union[str, list[str]] = (src_refs[0].node if len(src_refs) == 1
                                          else [ref.node for ref in src_refs])
            dst: Union[str, list[str]] = (dst_refs[0].node if len(dst_refs) == 1
                                          else [ref.node for ref in dst_refs])
            kwargs = dict(label=edge.label, color=edge.role,
                          dashed=edge.dashed, head=edge.head)
            if len(src_refs) == 1 and len(dst_refs) == 1:
                if edge.kind == "feedback":
                    if self.direction == "right":
                        kwargs.update(src_side="bottom", dst_side="bottom")
                    else:
                        kwargs.update(src_side="right", dst_side="right")
                else:
                    src_side = self._port_side(src_refs[0])
                    dst_side = self._port_side(dst_refs[0])
                    # Forward graph edges leave and enter perpendicular to
                    # their rank faces. Explicit FlowPorts still win.
                    if src_side == "auto":
                        src_side = "right" if self.direction == "right" else "bottom"
                    if dst_side == "auto":
                        dst_side = "left" if self.direction == "right" else "top"
                    kwargs.update(src_side=src_side, dst_side=dst_side)
            else:
                kwargs["orientation"] = (
                    "horizontal" if self.direction == "right" else "vertical"
                )
            connector = Connect(src, dst, **kwargs)
            self._connectors.append(connector)
        return Column(arranged, *self._connectors, gap="none", align="center")

    def measure(self, theme: Theme) -> BBox:
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self.child.render(canvas, x, y, theme)


def _soft_placeholder(role):
    """Keep string-content fallback import-free; Box resolves at render time."""
    return role.soft() if hasattr(role, "soft") else "bg_subtle"


__all__ = [
    "FlowPort", "FlowRef", "FlowNode", "FlowEdge", "FlowGroup", "FlowGraph",
]
