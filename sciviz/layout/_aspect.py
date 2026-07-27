"""Aspect: annotate a subtree with the printed shape it should take.

``Aspect`` is a fully transparent wrapper -- it measures and renders
exactly like its child -- whose only job is to *declare a goal* the
layout engine then optimises for::

    Aspect("landscape", staged_loop)

The engine reaches the goal by exercising the layout degrees of freedom
that already exist inside the subtree (``columns="auto"`` containers,
:class:`~sciviz.Cycle` shapes, ...). Nothing is scaled, squeezed, or
letterboxed: an aspect annotation never distorts content, it only
chooses among genuine layout alternatives.

The same vocabulary reads at diagram level
(``Diagram(target_aspect="landscape")``) and at component level, and the
two can be combined: annotate the whole figure *and* the one component
whose proportions actually drive it.
"""
from __future__ import annotations

from typing import Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..core._aspect import AspectSpec


class Aspect(Element):
    """Declare the width:height shape a subtree should lay out to.

    Parameters
    ----------
    shape : str or AspectSpec
        ``"portrait"``, ``"square"``, ``"landscape"``, ``"panorama"``, or
        a prebuilt :class:`~sciviz.core._aspect.AspectSpec`.
    child : Element
        The annotated subtree. Measured and rendered unchanged.
    ratio : float or (float, float), optional
        Tighten the named band to a specific width:height proportion.
    weight : float
        Relative importance when several goals compete (default 1.0).
        Raise it on the component whose shape matters most.
    priority : str
        ``"preferred"`` (default) or ``"required"``; see
        :class:`~sciviz.AspectSpec`. A required goal tells the fitter
        that the shape, not the width target, is the point of the
        figure.
    """

    def __init__(self, shape: Union[str, AspectSpec], child: Element, *,
                 ratio: Union[float, Sequence[float], None] = None,
                 weight: float = 1.0, priority: str = "preferred"):
        if isinstance(child, str) or not isinstance(child, Element):
            raise TypeError(
                "Aspect(shape, child): the shape comes first, then the "
                "annotated element")
        if isinstance(shape, AspectSpec):
            spec = shape if (ratio is None
                             and priority == shape.priority) else AspectSpec(
                shape.name, ratio=ratio, priority=priority)
        else:
            spec = AspectSpec(shape, ratio=ratio, priority=priority)
        self.spec = spec
        self.child = child
        self.weight = float(weight)

    # -- goal protocol (read by the Diagram target fitter) ---------------

    def _aspect_goal(self) -> AspectSpec:
        return self.spec

    def aspect_penalty(self, theme: Theme) -> float:
        """Weighted distance between the child's shape and the goal."""
        b = self.child.measure(theme)
        return self.weight * self.spec.penalty(b.w, b.h)

    # -- transparent wrapper --------------------------------------------

    @property
    def is_layout_invisible(self) -> bool:
        return getattr(self.child, "is_layout_invisible", False)

    @property
    def shape_key(self):
        return getattr(self.child, "shape_key", None)

    @property
    def primary_anchor(self):
        return getattr(self.child, "primary_anchor", None)

    def measure(self, theme: Theme) -> BBox:
        return self.child.measure(theme)

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.child.inflate_to(min_w, min_h)

    def content_bbox(self, theme: Theme):
        return self.child.content_bbox(theme)

    def primary_anchor_bbox(self, theme: Theme):
        return self.child.primary_anchor_bbox(theme)

    def iter_primary_anchors(self, theme: Theme):
        return self.child.iter_primary_anchors(theme)

    def stretch_decoration(self, theme: Theme):
        fn = getattr(self.child, "stretch_decoration", None)
        return fn(theme) if callable(fn) else (0.0, 0.0)

    def absorbs_main_axis_stretch(self) -> bool:
        fn = getattr(self.child, "absorbs_main_axis_stretch", None)
        return bool(fn()) if callable(fn) else False

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        self.child.render(canvas, x, y, theme)

    def __repr__(self) -> str:
        return f"Aspect({self.spec!r}, {type(self.child).__name__})"


def collect_aspect_goals(elem, out: list) -> None:
    """Depth-first walk collecting every :class:`Aspect` annotation.

    Mirrors the traversal used for anchors and reflowable containers so
    the order is stable across the deep copies the target fitter makes.
    """
    if elem is None:
        return
    if isinstance(elem, Aspect):
        out.append(elem)
    children = getattr(elem, "children", None)
    if children is not None:
        for c in children:
            collect_aspect_goals(c, out)
    for attr in ("child", "body", "header", "footer", "above", "below",
                 "decoration", "source"):
        sub = getattr(elem, attr, None)
        if isinstance(sub, Element):
            collect_aspect_goals(sub, out)
    wrapped = getattr(elem, "_wrapped", None)
    if wrapped:
        for a in wrapped:
            collect_aspect_goals(a, out)
    cols = getattr(elem, "columns", None)
    if isinstance(cols, list):
        for col in cols:
            if isinstance(col, dict):
                for key, val in col.items():
                    if isinstance(key, str) and key.startswith("_"):
                        continue
                    if isinstance(val, Element):
                        collect_aspect_goals(val, out)
