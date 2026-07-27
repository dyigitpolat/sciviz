"""Cycle: an ordered loop of stages laid out around a rectangular ring.

A staged process that returns to its own start -- propose, evaluate,
record, propose again -- has exactly one piece of layout freedom that
matters: *the shape of the ring*. Six stages read equally well as three
columns of two or two rows of three; which one is right depends on the
page, not on the process.

``Cycle`` makes that freedom explicit and hands it to the layout engine.
The author declares stages in cycle order and what each hand-off is
called; the container places them on a rectangle's perimeter, derives
every connector's attachment side from the placement it actually chose,
and exposes the alternative shapes through the reflow protocol so an
:class:`~sciviz.Aspect` annotation (or a diagram-level
``target_aspect``) can pick one::

    Aspect("landscape", Cycle(
        Anchor("propose", propose_card),
        Anchor("screen", screen_card),
        ...,
        edges=["propose()", "sealed market", None, ...],
    ))

Re-shaping the ring never asks the author to restate a single side hint.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme
from ..composition import Anchor
from ..grid import Grid
from .connector import Connect

Shape = Tuple[int, int]

#: Corner names accepted by ``start=``, in clockwise order.
_CORNERS = ("top-left", "top-right", "bottom-right", "bottom-left")

#: How many perimeter slots may stay empty. One slack slot lets an odd
#: number of stages still form a rectangular ring; more than that would
#: read as a broken loop rather than a loop.
_MAX_SLACK = 1


def ring_positions(shape: Shape, *, start: str = "top-left",
                   direction: str = "clockwise") -> List[Tuple[int, int]]:
    """Return the ``(row, col)`` perimeter walk of a ``rows x cols`` grid.

    The walk begins at ``start`` and winds in ``direction``; consecutive
    entries are always grid-adjacent, and the last entry is adjacent to
    the first, so a cycle drawn along it closes without a diagonal.
    """
    rows, cols = shape
    if rows < 1 or cols < 1:
        raise ValueError("Cycle shape must have positive rows and columns")
    if rows == 1:
        walk = [(0, c) for c in range(cols)]
    elif cols == 1:
        walk = [(r, 0) for r in range(rows)]
    else:
        walk = [(0, c) for c in range(cols)]
        walk += [(r, cols - 1) for r in range(1, rows)]
        walk += [(rows - 1, c) for c in range(cols - 2, -1, -1)]
        walk += [(r, 0) for r in range(rows - 2, 0, -1)]
    if direction not in ("clockwise", "counterclockwise"):
        raise ValueError(
            "Cycle direction must be 'clockwise' or 'counterclockwise'")
    if direction == "counterclockwise" and len(walk) > 2:
        walk = [walk[0]] + walk[:0:-1]
    if start not in _CORNERS:
        raise ValueError(f"Cycle start must be one of {_CORNERS}")
    corner = {
        "top-left": (0, 0),
        "top-right": (0, cols - 1),
        "bottom-right": (rows - 1, cols - 1),
        "bottom-left": (rows - 1, 0),
    }[start]
    if corner in walk:
        k = walk.index(corner)
        walk = walk[k:] + walk[:k]
    return walk


def ring_shapes(count: int) -> List[Shape]:
    """Every rectangular ring shape that can carry ``count`` stages.

    Shapes are ordered widest-first so a tie between equally-scoring
    candidates resolves deterministically.
    """
    if count <= 0:
        return []
    if count <= 3:
        return [(1, count), (count, 1)] if count > 1 else [(1, 1)]
    out: List[Shape] = []
    for rows in range(2, count):
        for cols in range(2, count):
            perimeter = 2 * (rows + cols) - 4
            if count <= perimeter <= count + _MAX_SLACK:
                out.append((rows, cols))
    out.sort(key=lambda s: (s[0], -s[1]))
    return out


def _sides(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[str, str]:
    """Attachment sides for a hand-off from cell ``a`` to cell ``b``."""
    dr, dc = b[0] - a[0], b[1] - a[1]
    if dr == 0 and dc > 0:
        return ("right", "left")
    if dr == 0 and dc < 0:
        return ("left", "right")
    if dc == 0 and dr > 0:
        return ("bottom", "top")
    if dc == 0 and dr < 0:
        return ("top", "bottom")
    return ("auto", "auto")


class Cycle(Element):
    """An ordered cycle of stages placed around a rectangular ring.

    Parameters
    ----------
    *stages : Element
        The stages in cycle order. Pre-wrapped :class:`~sciviz.Anchor`
        children keep their names (so feedback connectors declared
        elsewhere can address them); bare elements are anchored under
        generated names.
    edges : sequence, optional
        One entry per hand-off, aligned with ``stages``: entry ``i``
        describes the connector from stage ``i`` to stage ``i + 1``, and
        the last entry closes the loop. Each entry may be ``None`` (a
        plain arrow), a string (its label), a mapping of
        :class:`~sciviz.Connect` keyword arguments, or ``False`` to draw
        no connector at all. A shorter sequence leaves the remaining
        hand-offs plain.
    shape : "auto" or (rows, cols)
        ``"auto"`` opts the ring into the layout engine's reflow search:
        an enclosing :class:`~sciviz.Aspect` annotation or a
        diagram-level ``target_aspect`` chooses among
        :func:`ring_shapes`. A pinned tuple fixes the ring.
    start : str
        Which corner stage one occupies: ``"top-left"`` (default),
        ``"top-right"``, ``"bottom-right"``, ``"bottom-left"``.
    direction : str
        ``"clockwise"`` (default) or ``"counterclockwise"``.
    row_gap, col_gap : str or float
        Ring corridors. The gaps are where hand-off captions live, so
        they double as the connector label budget.
    """

    def __init__(self, *stages: Element,
                 edges: Optional[Sequence[Any]] = None,
                 shape: Union[str, Shape] = "auto",
                 start: str = "top-left",
                 direction: str = "clockwise",
                 row_gap: Union[str, float] = "md",
                 col_gap: Union[str, float] = "md"):
        cells = [s for s in stages if s is not None]
        if len(cells) < 2:
            raise ValueError("Cycle needs at least two stages")
        self.start = start
        self.direction = direction
        self.row_gap = row_gap
        self.col_gap = col_gap
        self.edges = list(edges) if edges is not None else []
        self._anchors: List[Anchor] = [
            c if isinstance(c, Anchor) else Anchor(f"cycle{id(self)}s{i}", c)
            for i, c in enumerate(cells)
        ]
        self._shapes = ring_shapes(len(self._anchors))
        if shape == "auto":
            self._auto_shape = True
            self.shape = self._shapes[0]
        else:
            self._auto_shape = False
            self.shape = self._validate_shape(shape)
        self._grid: Optional[Grid] = None
        self._connects: List[Connect] = []
        self._rebuild()

    # -- shape handling --------------------------------------------------

    def _validate_shape(self, shape) -> Shape:
        if (not isinstance(shape, (tuple, list)) or len(shape) != 2):
            raise TypeError("Cycle shape must be 'auto' or a (rows, cols) pair")
        rows, cols = int(shape[0]), int(shape[1])
        walk = ring_positions((rows, cols), start=self.start,
                              direction=self.direction)
        if len(walk) < len(self._anchors):
            raise ValueError(
                f"Cycle shape {(rows, cols)} has {len(walk)} perimeter "
                f"slots but {len(self._anchors)} stages")
        return (rows, cols)

    @property
    def stage_names(self) -> List[str]:
        """Anchor names of the stages, in cycle order."""
        return [a.name for a in self._anchors]

    #: Reflow protocol consumed by the ``Diagram`` target fitter.
    def _reflow_options(self) -> List[Shape]:
        if not self._auto_shape or len(self._shapes) < 2:
            return []
        return list(self._shapes)

    def _apply_reflow(self, shape) -> None:
        self.shape = self._validate_shape(shape)
        self._rebuild()

    # -- assembly --------------------------------------------------------

    def _edge_spec(self, index: int) -> Optional[Dict[str, Any]]:
        if index >= len(self.edges):
            return {}
        spec = self.edges[index]
        if spec is False:
            return None
        if spec is None:
            return {}
        if isinstance(spec, str):
            return {"label": spec}
        if isinstance(spec, dict):
            return dict(spec)
        raise TypeError(
            "Cycle edges entries must be None, False, a label string, or a "
            "dict of Connect keyword arguments")

    def _rebuild(self) -> None:
        rows, cols = self.shape
        walk = ring_positions(self.shape, start=self.start,
                              direction=self.direction)
        placed = walk[:len(self._anchors)]
        row_names = [f"r{i}" for i in range(rows)]
        columns: List[Dict[str, Element]] = [dict() for _ in range(cols)]
        for anchor, (r, c) in zip(self._anchors, placed):
            columns[c][row_names[r]] = anchor
        self._grid = Grid(rows=row_names, columns=columns,
                          row_gap=self.row_gap, col_gap=self.col_gap)
        connects: List[Connect] = []
        n = len(self._anchors)
        for i in range(n):
            spec = self._edge_spec(i)
            if spec is None:
                continue
            src, dst = self._anchors[i], self._anchors[(i + 1) % n]
            src_side, dst_side = _sides(placed[i], placed[(i + 1) % n])
            spec.setdefault("src_side", src_side)
            spec.setdefault("dst_side", dst_side)
            connects.append(Connect(src.name, dst.name, **spec))
        self._connects = connects

    # -- element protocol -------------------------------------------------

    @property
    def children(self) -> List[Element]:
        """Grid plus the ring connectors.

        Connector specs are layout-invisible; they live in ``children``
        so anchor/pending walkers discover them exactly as they discover
        connectors written by hand in a ``Row``.
        """
        return [self._grid, *self._connects]

    def measure(self, theme: Theme) -> BBox:
        return self._grid.measure(theme)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._grid.inflate_to(min_w, min_h)

    def content_bbox(self, theme: Theme):
        return self._grid.content_bbox(theme)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        self._grid.render(canvas, x, y, theme)
        for spec in self._connects:
            spec.render(canvas, x, y, theme)

    def __repr__(self) -> str:
        return (f"Cycle({len(self._anchors)} stages, shape={self.shape}, "
                f"{self.direction})")
