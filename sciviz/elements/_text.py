"""Text and TextBlock: single-line and multi-line text primitives."""

from __future__ import annotations

from typing import List, Optional, Union

from ..core import BBox, Canvas, Element, Theme


class Text(Element):
    """Single-line text.  Semantic size and colour names are preferred.

    Parameters
    ----------
    content : str
    size : str or float
        Either a semantic name (``"title"``, ``"label"``, ``"small"``, ...)
        or an explicit px value.
    color : str
        Semantic colour (``"dark"``, ``"muted"``, ``"highlight"``, ...) or
        an explicit hex string.
    weight : str
        CSS font-weight keyword: ``"normal"``, ``"600"``, ``"700"``.
    italic : bool
    align : str
        ``"start"``, ``"middle"`` or ``"end"`` controls the SVG text-anchor,
        not the bounding box -- the bbox always matches the rendered width.
    """

    def __init__(self, content: str, *, size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 font: Optional[str] = None,
                 rotate: float = 0.0):
        self.content = content
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.font = font
        # Rotation angle in degrees (CW positive).  When set, the bbox is
        # the AXIS-ALIGNED bbox of the rotated text, so it composes
        # cleanly inside Row/Column.  Use -90 for "reads bottom-up", 90
        # for "reads top-down".
        self.rotate = rotate

    def _resolved_font(self, theme: Theme) -> Optional[str]:
        if self.font is None:
            return None
        if self.font == "mono":
            return getattr(theme, "font_mono", None) or \
                "ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
        return self.font

    def measure(self, theme: Theme) -> BBox:
        bold = self.weight in ("bold", "600", "700")
        w = theme.text_width(self.content, self.size, bold=bold)
        h = theme.text_height(self.size)
        if self.rotate in (90, -90, 270, -270):
            return BBox(h, w)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px(self.size)
        fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        bold = self.weight in ("bold", "600", "700")
        font_w = theme.text_width(self.content, self.size, bold=bold)
        font_h = theme.text_height(self.size)
        if self.rotate in (90, -90, 270, -270):
            cx = x + bbox.w / 2
            cy = y + bbox.h / 2
            anchor = "middle"
            # baseline goes through the centre after rotation
            extra = (
                'dominant-baseline="central"' +
                f' transform="rotate({self.rotate} {cx:.2f} {cy:.2f})"'
            )
            ff = self._resolved_font(theme)
            ff_attr = f' font-family="{ff}"' if ff else ""
            italic_attr = ' font-style="italic"' if self.italic else ""
            weight_attr = (f' font-weight="{self.weight}"'
                           if self.weight != "normal" else "")
            canvas.raw(
                f'<text x="{cx:.2f}" y="{cy:.2f}" '
                f'font-size="{sz:.1f}" fill="{fill}" '
                f'text-anchor="{anchor}"{ff_attr}{italic_attr}{weight_attr} '
                f'{extra}>{self.content}</text>'
            )
            return
        # default unrotated path
        baseline = y + sz * 0.88
        if self.align == "middle":
            tx = x + bbox.w / 2
        elif self.align == "end":
            tx = x + bbox.w
        else:
            tx = x
        canvas.text(tx, baseline, self.content, size=sz, fill=fill,
                   weight=self.weight, italic=self.italic, anchor=self.align,
                   font_family=self._resolved_font(theme))


class TextBlock(Element):
    """Multi-line text block.  Lines are separated by ``\\n``."""

    def __init__(self, content: str, *, size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 line_spacing: float = 1.35, max_width: Optional[float] = None):
        self.content = content
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.line_spacing = line_spacing
        self.max_width = max_width

    def _lines(self, theme: Theme) -> List[str]:
        raw_lines = self.content.split("\n")
        if self.max_width is None:
            return raw_lines
        out = []
        bold = self.weight in ("bold", "600", "700")
        for line in raw_lines:
            words = line.split(" ")
            cur = ""
            for w in words:
                trial = (cur + " " + w).strip()
                if theme.text_width(trial, self.size, bold=bold) <= self.max_width:
                    cur = trial
                else:
                    if cur:
                        out.append(cur)
                    cur = w
            out.append(cur)
        return out

    def measure(self, theme: Theme) -> BBox:
        lines = self._lines(theme)
        bold = self.weight in ("bold", "600", "700")
        widths = [theme.text_width(l, self.size, bold=bold) for l in lines]
        line_h = theme.size_px(self.size) * self.line_spacing
        w = max(widths) if widths else 0.0
        if self.max_width is not None:
            w = max(w, 0.0)
        h = line_h * len(lines)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        lines = self._lines(theme)
        sz = theme.size_px(self.size)
        line_h = sz * self.line_spacing
        fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        for i, line in enumerate(lines):
            baseline = y + sz * 0.88 + i * line_h
            # Accept both "middle" (internal name) and "center" (what
            # most authors reach for) as horizontal centre alignment.
            if self.align in ("middle", "center"):
                tx = x + bbox.w / 2
                svg_anchor = "middle"
            elif self.align == "end":
                tx = x + bbox.w
                svg_anchor = "end"
            else:
                tx = x
                svg_anchor = "start"
            canvas.text(tx, baseline, line, size=sz, fill=fill,
                       weight=self.weight, italic=self.italic,
                       anchor=svg_anchor)

