"""Separator: a thin horizontal or vertical rule.

Visually trivial, layout-useful. A ``Separator`` with ``length=None``
reports a very thin bbox on its minor axis and expects its parent
container to stretch it to fill via the :attr:`stretch` hook; that lets
authors write::

    Column(
        header,
        Separator(),          # stretches to the column's inner width
        body,
    )

without hard-coding a width. Plain :class:`Row` and :class:`Column`
honour the hint (see ``sciviz/layout``), and everything else treats a
``Separator(length=None)`` as a 1px-tall ghost that the author can fix
in place with an explicit ``length``.
"""

from __future__ import annotations

from typing import Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Separator(Element):
    """Thin rule used to break visual runs.

    Parameters
    ----------
    length : float, optional
        Fixed length along the main axis in px. If ``None``, the parent
        container is expected to stretch the separator to fill (see
        :class:`sciviz.Row` / :class:`sciviz.Column`).
    orientation : str
        ``"horizontal"`` (default) or ``"vertical"``.
    style : str
        ``"solid"`` (default), ``"dashed"``, or ``"dotted"``.
    color : str or ColorRef
        Stroke color. ``"muted"`` by default.
    thickness : float, optional
        Line thickness in px. Defaults to the theme's hairline.
    inset : float
        Margin on the *minor* axis -- how much empty space to reserve
        above and below (horizontal) or left and right (vertical) of the
        drawn rule. Keeps the rule from visually butting the neighbours.
    """

    #: Requests that the parent container expand the separator along
    #: its main axis when it has room. Honoured by Row / Column.
    _stretch_axis_default_length: float = 1.0

    def __init__(self, length: Optional[float] = None, *,
                 orientation: str = "horizontal",
                 style: str = "solid",
                 color: str = "muted",
                 thickness: Optional[float] = None,
                 inset: float = 0.0):
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(
                f"orientation must be 'horizontal' or 'vertical'; got {orientation!r}")
        if style not in ("solid", "dashed", "dotted"):
            raise ValueError(
                f"style must be 'solid', 'dashed', or 'dotted'; got {style!r}")
        self.length = None if length is None else float(length)
        self.orientation = orientation
        self.style = style
        self.color = color
        self.thickness = thickness
        self.inset = float(inset)
        self._stretched_length: Optional[float] = None

    # Row / Column consult this to know whether to stretch along the
    # main axis. A Separator without an explicit length is stretchable.
    @property
    def stretch_main_axis(self) -> bool:
        return self.length is None

    def set_stretched_length(self, length: float) -> None:
        """Parent-provided main-axis length used if ``length`` is None."""
        self._stretched_length = float(length)

    def _main_length(self) -> float:
        if self.length is not None:
            return self.length
        if self._stretched_length is not None:
            return self._stretched_length
        return self._stretch_axis_default_length

    def measure(self, theme: Theme) -> BBox:
        t = self.thickness if self.thickness is not None else theme.hairline
        minor = max(t + 2 * self.inset, t)
        main = self._main_length()
        if self.orientation == "horizontal":
            return BBox(main, minor)
        return BBox(minor, main)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        t = self.thickness if self.thickness is not None else theme.hairline
        col = theme.color_of(self.color)
        dash = None
        if self.style == "dashed":
            dash = "4,3"
        elif self.style == "dotted":
            dash = "1,2"
        main = self._main_length()
        if self.orientation == "horizontal":
            cy = y + self.inset + t / 2
            canvas.line(x, cy, x + main, cy,
                        stroke=col, stroke_width=t, dasharray=dash)
        else:
            cx = x + self.inset + t / 2
            canvas.line(cx, y, cx, y + main,
                        stroke=col, stroke_width=t, dasharray=dash)
