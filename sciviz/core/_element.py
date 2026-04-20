"""Element: the base class every drawable inherits from.

The layout contract is deliberately small::

    size = element.measure(theme)           # returns BBox(w, h)
    element.render(canvas, x, y, theme)     # draws *inside* (x, y, x+w, y+h)

Every element promises to keep its drawing inside the box it reported.
That is the single invariant that lets parent containers (:class:`Row`,
:class:`Column`, :class:`Panel`, ...) compose children without overlap.
"""

from __future__ import annotations

from typing import Optional

from ._bbox import BBox
from ._canvas import Canvas
from ._theme import Theme


class Element:
    """Base class for every sciviz drawable.

    Subclasses must implement :meth:`measure` and :meth:`render`. They must
    guarantee that ``render(canvas, x, y)`` only paints inside the rectangle
    ``(x, y, x + w, y + h)`` where ``(w, h) == measure()``. This single
    invariant is what makes composition safe.

    Two optional hooks let containers do smarter alignment:

    * :meth:`content_bbox` returns the *inner* content rectangle (inset
      from the outer measure bbox) expressed in the element's local frame
      as ``(x0, y0, w, h)``. Containers like :class:`Row` use this to
      align children on their content centre, not on their outer bbox.
      The default implementation reports the full measure bbox, i.e. no
      inset. Elements that add out-of-band spacing (e.g. :class:`Anchor`
      margins) override this to exclude that spacing.

    * :attr:`primary_anchor` is an optional ``(offset_x, width)`` pair in
      the element's local frame identifying the sub-region that should
      be treated as the "anchor" when centering. Composites like
      :class:`Labeled` expose the source element here so a :class:`Grid`
      cell centers the source on the column axis and lets the trailing
      label flow freely into the inter-cell gap. ``None`` means the
      element has no special anchor and should be centered as a whole.
    """

    # Elements whose layout should be driven by an inner sub-region rather
    # than their full bbox override this to return ``(offset_x, width)``
    # (or a 4-tuple ``(x, y, w, h)``). The default is None.
    primary_anchor = None

    # Declarative placeholders (e.g. ``Connect`` routed/bus specs) live in
    # the tree as zero-size siblings so they can be collected by walkers,
    # but they should NOT contribute a gap in Row/Column/Grid layout.
    # Elements that are pure metadata set this to True.
    is_layout_invisible: bool = False

    def measure(self, theme: Theme) -> BBox:  # pragma: no cover - abstract
        raise NotImplementedError(
            f"{type(self).__name__} must implement measure(theme)")

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:  # pragma: no cover - abstract
        raise NotImplementedError(
            f"{type(self).__name__} must implement render(canvas, x, y, theme)")

    def content_bbox(self, theme: Theme) -> "tuple[float, float, float, float]":
        """Return the element's inner content rectangle in its local frame.

        The tuple is ``(x, y, w, h)`` where ``(0, 0)`` is the top-left of
        the rectangle reported by :meth:`measure`. Default is the whole
        measure bbox.
        """
        b = self.measure(theme)
        return (0.0, 0.0, b.w, b.h)

    def primary_anchor_bbox(self, theme: Theme) -> "Optional[tuple[float, float, float, float]]":
        """Return the primary anchor region ``(x, y, w, h)`` in local coords.

        When an element has an internal sub-region that should drive cell
        centering (e.g. the source box inside a :class:`Labeled`), it
        overrides this method. Default returns ``None``.
        """
        return None

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        """Request that this element render at least ``min_w`` x ``min_h``.

        The default is a no-op: most elements have a fixed intrinsic size
        and silently ignore the request. Containers that *can* honour a
        minimum (notably :class:`sciviz.elements.Box`) override this to
        widen/heighten themselves; transparent wrappers (:class:`Anchor`,
        :class:`FixedSize`) forward the request to their child.

        Used by sibling-aware layouts (:class:`MatchSize` with
        ``stretch=True``, :class:`Column` / :class:`Row` with
        ``equal_widths=True``) to make a row of differently-sized boxes
        actually render at the same size, instead of being centred in
        identical-but-empty slots.
        """
        return None

    def iter_primary_anchors(self, theme: Theme) -> "list[tuple[float, float, float, float]]":
        """Yield every primary-anchor sub-region this element exposes.

        The default element has a single primary anchor -- its
        :meth:`primary_anchor_bbox` (falling back to the whole measure
        bbox). Containers like :class:`Row` override this to expose one
        primary anchor per child, so a cell-to-cell arrow router can fan
        an arrow into each sibling face instead of the silhouette centre.
        """
        pa = self.primary_anchor_bbox(theme)
        if pa is not None:
            return [pa]
        b = self.measure(theme)
        return [(0.0, 0.0, b.w, b.h)]
