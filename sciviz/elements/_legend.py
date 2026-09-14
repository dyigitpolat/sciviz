"""Legend / LegendItem: color-swatch + label rows."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ._text import Text


class LegendItem(Element):
    """Single entry in a :class:`Legend`: a swatch element + a text label.

    The swatch can be any :class:`Element` (a small :class:`Box`, a
    :class:`Badge`, a :class:`Matrix`, ...) -- this lets legends pair
    non-trivial icons with descriptions without reinventing the layout.

    Parameters
    ----------
    swatch : Element
        Visual swatch (rendered verbatim at its intrinsic size).
    text : str
        Label text, rendered to the right of the swatch.
    gap : str or float, optional
        Horizontal spacing between swatch and text. Left unset it is a
        TEXT-RELATIVE bearing (see :attr:`_LABEL_BEARING`), which is the
        thing a key actually needs; pass a token or a number to override.
    text_size : str
        Theme size token for the label.
    text_color : str
        Colour for the label (default ``"muted"``).
    """

    # The swatch-to-label gap belongs to the TYPE, not to the layout grid.
    # It was ``"xs"``, a spacing token that scales with ``theme.unit``, and a
    # figure compressed towards a print width drives ``unit`` down until the
    # gap prints under one point: the label then touches the swatch it names
    # and the key reads as one smeared run instead of discrete entries. A
    # bearing proportional to the label's own size holds a visible word-space
    # at every scale, and stays smaller than ``Legend``'s between-item gap, so
    # an item still binds tighter to its own swatch than to its neighbour.
    _LABEL_BEARING = 0.42

    def __init__(self, swatch: Element, text: str, *,
                 gap: Optional[Union[str, float]] = None,
                 text_size: str = "small",
                 text_color: str = "muted"):
        self.swatch = swatch
        self.text = text
        self.gap = gap
        self.text_size = text_size
        self.text_color = text_color

    def _gap_px(self, theme: Theme) -> float:
        if self.gap is not None:
            return theme.gap_px(self.gap)
        return theme.size_px(self.text_size) * self._LABEL_BEARING

    def _row(self, theme: Theme):
        from ..layout import Row
        return Row(
            self.swatch,
            Text(self.text, size=self.text_size, color=self.text_color),
            gap=self._gap_px(theme), align="center",
        )

    def measure(self, theme: Theme) -> BBox:
        return self._row(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._row(theme).render(canvas, x, y, theme)


class Legend(Element):
    """Compact horizontal key.

    Three forms (use whichever matches the data you have):

    * ``Legend(LegendItem(Box(...), "leaf page"), LegendItem(...), ...)`` --
      positional items with custom swatch elements.  Preferred form.
    * ``Legend(items=[("#3b82f6", "Active"), ("#e2e8f0", "Pruned")])`` --
      the legacy kwarg form: pairs of (colour, label) drawn as small
      rectangles.  Supported for backward compatibility.
    * ``Legend(scale=("blues", 5), label="|w|")`` -- a sequential colour
      ramp for heatmap-like data.
    """

    def __init__(self, *children,
                 items: Optional[List[Tuple[str, str]]] = None,
                 scale: Optional[Tuple[str, int]] = None,
                 label: Optional[str] = None,
                 swatch_size: float = 14.0,
                 orientation: str = "horizontal",
                 gap: Union[str, float] = "md",
                 max_width: Optional[float] = None):
        self._children = list(children)
        self.items = items
        self.scale = scale
        self.label = label
        self.swatch_size = swatch_size
        self.orientation = orientation
        self.gap = gap
        # A key is subordinate to the thing it explains, so it must not be
        # what sets the figure's width. With a budget the items flow onto a
        # second line instead of pushing the whole figure past it; without
        # one the legend keeps its historical single-row behaviour.
        self.max_width = max_width

    def _resolved_items(self, theme: Theme) -> List[Tuple[str, str]]:
        if self.items is not None:
            out = []
            for col, lbl in self.items:
                out.append((theme.color_of(col), lbl))
            return out
        if self.scale is not None:
            palette_name, n = self.scale
            palette = theme.palette(palette_name)
            # Pick n evenly spaced samples
            if n <= 1:
                picks = [palette[-1]]
            else:
                picks = [palette[int(i * (len(palette) - 1) / (n - 1))]
                         for i in range(n)]
            labels = ["low"] + [""] * (n - 2) + ["high"] if n >= 2 else ["—"]
            return list(zip(picks, labels))
        return []

    def _positional_container(self):
        """The legend's title is not another item, and is not spaced like one.

        Inserting the title into the item run gave it the SAME gap as the gap
        between an item's swatch and its neighbour, so a bold title read as
        glued to the first swatch. The items keep their own even rhythm and the
        title is separated from that run by a wider gap, which is what makes it
        read as a heading for the run rather than as part of it.
        """
        from ..layout import Column, Row, WrapRow
        horizontal = self.orientation == "horizontal"
        cls = Row if horizontal else Column
        if horizontal and self.max_width is not None:
            items = WrapRow(*self._children, gap=self.gap,
                            line_gap="xs", max_width=self.max_width,
                            align="center")
        else:
            items = cls(*self._children, gap=self.gap, align="center")
        if not self.label:
            return items
        return cls(
            Text(self.label, size="small", color="text", weight="700"),
            items,
            gap="md", align="center",
        )

    def measure(self, theme: Theme) -> BBox:
        if self._children:
            return self._positional_container().measure(theme)
        items = self._resolved_items(theme)
        sw = self.swatch_size
        pad = theme.unit * 0.6
        if self.orientation == "horizontal":
            w = 0.0
            if self.label:
                w += theme.text_width(self.label, "small", bold=True) + theme.unit
            for _, lbl in items:
                w += sw + pad
                if lbl:
                    w += theme.text_width(lbl, "small") + theme.unit
            h = max(sw, theme.text_height("small"))
            return BBox(w, h)
        else:
            w = sw + theme.unit
            if self.label:
                w = max(w, theme.text_width(self.label, "small", bold=True))
            for _, lbl in items:
                if lbl:
                    w = max(w, sw + theme.unit + theme.text_width(lbl, "small"))
            h = len(items) * (sw + pad)
            if self.label:
                h += theme.text_height("small") + pad
            return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if self._children:
            self._positional_container().render(canvas, x, y, theme)
            return
        items = self._resolved_items(theme)
        sw = self.swatch_size
        pad = theme.unit * 0.6
        sz = theme.size_px("small")
        size = self.measure(theme)

        if self.orientation == "horizontal":
            cx = x
            cy_swatch = y + (size.h - sw) / 2
            cy_text = y + size.h / 2 + sz * 0.35
            if self.label:
                canvas.text(cx, cy_text, self.label,
                           size=sz, fill=theme.text_muted,
                           weight="600")
                cx += theme.text_width(self.label, "small", bold=True) + theme.unit
            for color, lbl in items:
                canvas.rect(cx, cy_swatch, sw, sw * 0.7,
                           fill=color, stroke=theme.color_of("border_strong"),
                           stroke_width=0.3, rx=1)
                cx += sw + pad
                if lbl:
                    canvas.text(cx, cy_text, lbl,
                               size=sz, fill=theme.text_muted)
                    cx += theme.text_width(lbl, "small") + theme.unit

