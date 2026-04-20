"""StackedTiles: render an element with N offset background copies.

The classic "deck of cards" / "stack of frames" depth motif. The author
provides a single tile and asks for N copies; the foreground copy is
the original child (anchors and markup intact), and ``count - 1``
ghost copies are drawn behind it, each shifted by ``(dx, dy)``.

Useful for:

* Multi-frame video / image-sequence inputs (the ``count=3`` dashed
  frames in a captioning pipeline).
* Showing a worker pool / replica set as a single concept that reads
  visually as "many".
* Stacked notes / cards / pages.

Only the front tile registers as the element's logical anchor: a
:class:`Connect` aimed at the StackedTiles lands on the foreground
copy, not on the depth ghosts.
"""
from __future__ import annotations

from typing import Optional

from ..core import BBox, Canvas, Element, Theme


class StackedTiles(Element):
    """Render ``count`` offset copies of ``tile``, foreground-last.

    Parameters
    ----------
    tile : Element
        The tile to repeat. Drawn once on top with its full markup;
        ``count - 1`` ghosts are drawn behind it at offsets.
    count : int
        Total number of tiles, including the foreground copy.
        Must be >= 1. ``count=1`` collapses to the bare tile.
    offset : tuple[float, float]
        ``(dx, dy)`` per-step shift of the ghost copies, in px.
        Default ``(6, -6)`` produces a back-and-up depth stack like
        a sheaf of papers.
    ghost_opacity : float
        Opacity applied to ghost copies (front tile is always full
        opacity). Default 1.0 -- ghosts paint at full strength,
        relying on overlap to read as depth.
    """

    def __init__(self, tile: Element, *,
                 count: int = 3,
                 offset: tuple[float, float] = (6.0, -6.0),
                 ghost_opacity: float = 1.0,
                 ghost: Optional[Element] = None):
        if count < 1:
            raise ValueError(f"count must be >= 1; got {count}")
        if not 0.0 <= ghost_opacity <= 1.0:
            raise ValueError(
                f"ghost_opacity must be in [0, 1]; got {ghost_opacity}")
        self.tile = tile
        self.count = int(count)
        self.offset = (float(offset[0]), float(offset[1]))
        self.ghost_opacity = float(ghost_opacity)
        # ``ghost`` is an optional stripped-down variant used for the
        # ``count - 1`` background copies. The classic use is a plain
        # dashed outline behind a richly-decorated front tile (icon +
        # labels) so the repetition reads as depth, not visual noise.
        # Must measure the same size as ``tile`` or smaller.
        self.ghost = ghost

    # ---- bbox math -------------------------------------------------------

    def _extents(self, theme: Theme):
        """Return ``(tile_bb, x_min, y_min, w, h)`` for the full stack."""
        b = self.tile.measure(theme)
        # Keep the ghost the same outer size as the front tile so the
        # stack reads as a coherent deck. Elements that don't support
        # ``inflate_to`` (e.g. a bare Text) are drawn at intrinsic size.
        if self.ghost is not None:
            self.ghost.inflate_to(b.w, b.h)
        n = self.count - 1
        dx, dy = self.offset
        # Ghosts span k=1..n steps. Front tile sits at the
        # k=0 origin we *report*; ghosts at +k*offset can extend past it.
        xs = [0.0] + [k * dx for k in range(1, n + 1)]
        ys = [0.0] + [k * dy for k in range(1, n + 1)]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        w = (x_max - x_min) + b.w
        h = (y_max - y_min) + b.h
        return b, x_min, y_min, w, h

    def measure(self, theme: Theme) -> BBox:
        _b, _x0, _y0, w, h = self._extents(theme)
        return BBox(w, h)

    # ---- alignment contract ---------------------------------------------

    def content_bbox(self, theme: Theme):
        """Report the FRONT tile's content bbox, so siblings align on the
        foreground copy rather than on the union of ghost extents.
        """
        b, x0, y0, w, h = self._extents(theme)
        # Front tile sits at local origin (0, 0); shift to outer frame
        # (which starts at min coordinate of the union).
        front_x = -x0
        front_y = -y0
        cx, cy, cw, ch = self.tile.content_bbox(theme)
        return (front_x + cx, front_y + cy, cw, ch)

    def primary_anchor_bbox(self, theme: Theme):
        b, x0, y0, _w, _h = self._extents(theme)
        front_x = -x0
        front_y = -y0
        pa = self.tile.primary_anchor_bbox(theme)
        if pa is None:
            return (front_x, front_y, b.w, b.h)
        ax, ay, aw, ah = pa
        return (front_x + ax, front_y + ay, aw, ah)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        # Forward to the underlying tile so that, e.g., a column-equalise
        # request grows the front tile (and the ghosts that mirror it).
        self.tile.inflate_to(min_w, min_h)

    # ---- rendering -------------------------------------------------------

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b, x0, y0, _w, _h = self._extents(theme)
        front_x = x - x0
        front_y = y - y0
        n = self.count - 1
        dx, dy = self.offset
        ghost = self.ghost if self.ghost is not None else self.tile
        # Paint ghosts back-to-front so the topmost ghost is closest to
        # the front tile (occlusion looks like a deck).
        if self.ghost_opacity >= 1.0:
            for k in range(n, 0, -1):
                ghost.render(canvas, front_x + k * dx,
                             front_y + k * dy, theme)
        else:
            for k in range(n, 0, -1):
                canvas.raw(f'<g opacity="{self.ghost_opacity:.3f}">')
                ghost.render(canvas, front_x + k * dx,
                             front_y + k * dy, theme)
                canvas.raw('</g>')
        self.tile.render(canvas, front_x, front_y, theme)
