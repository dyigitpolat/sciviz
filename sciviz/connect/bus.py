"""Bus mode: many-endpoint connection through a single spine.

Absorbs the old ``Bus`` class. :class:`_BusConnect` is a zero-size
placeholder that registers a ``Bus`` spec with the active resolver.
"""
from __future__ import annotations

from typing import List, Optional

from ..core import BBox, Canvas, Element, Theme
from ..composition import Bus


class _BusConnect(Element):
    """Zero-size placeholder that declares a bus connection."""

    is_layout_invisible = True

    def __init__(self, *,
                 sources: List[str],
                 sinks: List[str],
                 label: Optional[str],
                 color,
                 dashed: bool,
                 head,
                 orientation: str,
                 auto_route: bool = True,
                 min_shaft: Optional[float] = None,
                 src_room: Optional[float] = None,
                 dst_room: Optional[float] = None,
                 corner_radius: Optional[float] = None,
                 flush_head: bool = False):
        self._bus = Bus(
            sources=sources,
            sinks=sinks,
            label=label,
            dashed=dashed,
            color=color,
            arrow=bool(head) if head is not False else False,
            orientation=orientation,
            auto_route=auto_route,
            min_shaft=min_shaft,
            src_room=src_room,
            dst_room=dst_room,
            corner_radius=corner_radius,
            flush_head=flush_head,
        )

    def measure(self, theme: Theme) -> BBox:
        return BBox(0.0, 0.0)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        from ._resolver import push_pending_connection
        push_pending_connection(self._bus)
