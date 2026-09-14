"""Marker: the chart marker vocabulary as a standalone element.

Charts draw series markers (circle, square, triangle, diamond; solid or
hollow) inside their own render pass, which left legend authors with no
way to show the *same* glyph beside a label -- the usual workaround is a
coloured ``Box``, which silently drops the shape that distinguishes the
series. :class:`Marker` is that glyph as an element, so a legend can pair
the exact mark a chart draws, the way :class:`HarveyBall` already does for
coverage states.

``LineChart``, ``Scatter`` and ``Slopegraph`` render through
:func:`draw_marker`, so a legend built from ``Marker`` cannot drift from
the chart it explains.
"""

from __future__ import annotations

from typing import Union

from ..core import BBox, Canvas, Element, Theme
from ..palette import ColorRef

SHAPES = ("circle", "square", "triangle", "diamond")
FILL_MODES = ("solid", "hollow")

# Marker radius as a multiple of the theme's spacing unit.
SIZE_FACTORS = {"xs": 0.42, "sm": 0.58, "md": 0.75, "lg": 0.95}


def marker_radius(size: Union[str, float], theme: Theme) -> float:
    """Resolve a marker size token (or explicit radius in px) to a radius."""
    if isinstance(size, (int, float)):
        return max(0.5, float(size))
    if size not in SIZE_FACTORS:
        allowed = "/".join(SIZE_FACTORS)
        raise ValueError(f"marker size must be {allowed} or a number")
    return theme.unit * SIZE_FACTORS[size]


def draw_marker(canvas: Canvas, shape: str, cx: float, cy: float,
                radius: float, color: str, theme: Theme,
                fill_mode: str = "solid") -> None:
    """Draw one marker centred on ``(cx, cy)``. Single source of truth."""
    if fill_mode == "hollow":
        fill = theme.color_of("bg")
        stroke = color
        stroke_width = theme.line
    else:
        fill = color
        stroke = "white"
        stroke_width = theme.hairline
    if shape == "circle":
        canvas.circle(cx, cy, radius, fill=fill, stroke=stroke,
                      stroke_width=stroke_width)
    elif shape == "square":
        canvas.rect(cx - radius, cy - radius, 2 * radius, 2 * radius,
                    fill=fill, stroke=stroke, stroke_width=stroke_width)
    elif shape == "triangle":
        canvas.polygon([(cx, cy - radius),
                        (cx + radius, cy + radius),
                        (cx - radius, cy + radius)],
                       fill=fill, stroke=stroke, stroke_width=stroke_width)
    elif shape == "diamond":
        canvas.polygon([(cx, cy - radius), (cx + radius, cy),
                        (cx, cy + radius), (cx - radius, cy)],
                       fill=fill, stroke=stroke, stroke_width=stroke_width)


class Marker(Element):
    """One chart marker as a standalone, measurable element.

    Parameters
    ----------
    shape : str
        ``"circle"`` (default), ``"square"``, ``"triangle"``, or
        ``"diamond"`` -- the same vocabulary ``Series.marker`` accepts.
    color : str or ColorRef
        Theme colour role, hex literal, or palette reference.
    size : str or float
        ``"xs"``/``"sm"``/``"md"``/``"lg"`` token, or an explicit radius
        in px. Pass the same value the series uses and the legend glyph
        matches the plotted one exactly.
    fill : str
        ``"solid"`` (default) or ``"hollow"``, matching
        ``Series.marker_fill``.

    Example
    -------
    >>> Legend(LegendItem(Marker("diamond", color=Palette.red), "measured"))
    """

    def __init__(self, shape: str = "circle", *,
                 color: Union[str, ColorRef] = "primary",
                 size: Union[str, float] = "xs",
                 fill: str = "solid"):
        if shape not in SHAPES:
            raise ValueError(
                f"Marker shape must be one of {SHAPES}; got {shape!r}")
        if fill not in FILL_MODES:
            raise ValueError(
                f"Marker fill must be one of {FILL_MODES}; got {fill!r}")
        self.shape = shape
        self.color = color
        self.size = size
        self.fill = fill

    def measure(self, theme: Theme) -> BBox:
        side = 2.0 * marker_radius(self.size, theme) + theme.line
        return BBox(side, side)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        radius = marker_radius(self.size, theme)
        half = radius + theme.line / 2.0
        draw_marker(canvas, self.shape, x + half, y + half, radius,
                    theme.color_of(self.color), theme, self.fill)
