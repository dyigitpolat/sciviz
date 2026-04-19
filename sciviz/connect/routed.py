"""Routed mode: two named anchors, orthogonal (or curved) routing.

Absorbs the old ``Flow`` / ``Labeled`` classes. :class:`_RoutedConnect`
constructs a ``Flow`` spec and defers its execution to the enclosing
``_FlowResolver`` (see :mod:`sciviz.connect._resolver`).
"""
from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme
from ..composition import Flow


class _RoutedConnect(Element):
    is_layout_invisible = True

    """A zero-size placeholder that declares a routed connection.

    It records itself with the active resolver at `render` time. Actual
    drawing is done by the resolver after the child tree has rendered.
    """

    def __init__(self, *,
                 src_name: str,
                 dst_name: str,
                 label: Optional[str],
                 src_side: str,
                 dst_side: str,
                 color,
                 label_color,
                 dashed: bool,
                 head,
                 style: str,
                 curvature: float,
                 detour: float):
        self._flow = Flow(
            src_name, dst_name,
            src_side=src_side,
            dst_side=dst_side,
            color=color,
            label=label,
            dashed=dashed,
            curvature=curvature,
            detour=detour,
            arrow=bool(head) if head is not False else False,
            style=style,
        )
        # Preserve the head spec for richer arrowhead control if we need it.
        self._head_spec = head

    def measure(self, theme: Theme) -> BBox:
        return BBox(0.0, 0.0)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        # Register with the active resolver stack. If no resolver is
        # installed, fall back silently: the Diagram top-level always
        # installs one, so this only happens in isolated tests.
        from ._resolver import push_pending_connection
        push_pending_connection(self._flow)
