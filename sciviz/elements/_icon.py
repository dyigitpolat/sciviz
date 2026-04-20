"""Icon: compact stroke-based pictogram drawn from the Lucide subset.

Authors call ``Icon("camera")`` -- no SVG authoring required. The icon
renders at the requested ``size`` square while preserving the linecap /
linejoin look of the Lucide family.

Unknown names raise with the full list of available icons so typos are
self-diagnosing at measure time.
"""

from __future__ import annotations

from typing import Union

from .._assets import LUCIDE_ICONS, LUCIDE_VIEWBOX
from ..core import BBox, Canvas, Element, Theme


class Icon(Element):
    """A Lucide-family pictogram at a fixed square size.

    Parameters
    ----------
    name : str
        Icon name (see :data:`sciviz._assets.LUCIDE_ICONS`). Unknown names
        raise :class:`KeyError` at construction time with the available
        set in the message.
    size : float or str
        Side length in px, or a semantic size token resolved against the
        theme (``"small"``, ``"label"``, ``"title"``, ...). Defaults to
        ``"label"`` so icons typographically match inline text.
    color : str or ColorRef
        Stroke color. Semantic tokens preferred (``"dark"``, ``"muted"``,
        ``"highlight"``, a palette role).
    stroke_width : float
        Stroke width in the *viewBox* coordinate system (24 units). The
        default 1.75 mirrors Lucide's own.
    opacity : float
    """

    def __init__(self, name: str, *,
                 size: Union[float, str] = "label",
                 color: str = "dark",
                 stroke_width: float = 1.75,
                 fill: str = "none",
                 opacity: float = 1.0):
        if name not in LUCIDE_ICONS:
            options = ", ".join(sorted(LUCIDE_ICONS)[:10])
            raise KeyError(
                f"Unknown icon {name!r}. "
                f"Available: {len(LUCIDE_ICONS)} icons, e.g. {options} ... "
                f"(see sciviz._assets.LUCIDE_ICONS for the full list)."
            )
        self.name = name
        self.size = size
        self.color = color
        self.stroke_width = float(stroke_width)
        # ``"none"`` (default) -- Lucide's pure-stroke look.
        # ``"match"``          -- fill the shape with ``color`` (solid glyph).
        # Any colour string    -- explicit fill colour.
        self.fill = fill
        self.opacity = float(opacity)

    def _size_px(self, theme: Theme) -> float:
        if isinstance(self.size, (int, float)):
            return float(self.size)
        return theme.size_px(self.size) * 1.2

    def measure(self, theme: Theme) -> BBox:
        s = self._size_px(theme)
        return BBox(s, s)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        s = self._size_px(theme)
        stroke = theme.color_of(self.color)
        if self.fill == "match":
            fill = stroke
        elif self.fill == "none":
            fill = "none"
        else:
            fill = theme.color_of(self.fill)
        canvas.svg_path(
            x, y, s, s,
            paths=LUCIDE_ICONS[self.name],
            viewbox=LUCIDE_VIEWBOX,
            stroke=stroke,
            stroke_width=self.stroke_width,
            fill=fill,
            opacity=self.opacity,
        )
