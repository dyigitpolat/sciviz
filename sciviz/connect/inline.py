"""Inline mode: axis-aligned standalone arrow inside a Row/Column.

Absorbs the old ``Arrow`` / ``Connector`` element. Delegates to the existing
:class:`sciviz.elements.Arrow` implementation while :class:`Connect` is in the
transitional period; Phase 3d will extract the arrow rendering helpers into
``sciviz/elements/_arrow_band.py`` and this module will use them directly.
"""
from __future__ import annotations

from typing import List, Optional, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Arrow


class _InlineConnect(Element):
    """Thin wrapper around :class:`Arrow` for inline ``Connect`` mode."""

    def __init__(self, *,
                 labels: List[str],
                 direction: str,
                 length: Optional[float],
                 color: str,
                 label_color: str,
                 italic: bool,
                 size: Union[str, float],
                 head: bool):
        self._arrow = Arrow(
            label=labels if labels else None,
            direction=direction,
            length=length,
            color=color,
            label_color=label_color,
            italic=italic,
            size=size,
            head=head,
        )

    def measure(self, theme: Theme) -> BBox:
        return self._arrow.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._arrow.render(canvas, x, y, theme)
