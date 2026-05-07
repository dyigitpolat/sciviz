"""Text and TextBlock: single-line and multi-line text primitives.

Two construction modes are supported, in priority order:

1. **Plain string** -- ``Text("hello")``. Uses the style attributes on
   the Text instance (``size``, ``color``, ``weight``, ``italic``).
2. **Structured runs** -- ``Text([("Principle 1:", {"weight": "700"}),
   " ", "instruction adherence ", Span("(weight 4)", color="negative")])``.
   Each run is either a plain string (inheriting the Text defaults) or
   a ``(text, style_dict)`` tuple that overrides any of ``color``,
   ``weight``, ``italic``, and ``size`` for that segment.

The :func:`Span` helper is sugar for the tuple form:

    Span("hello", weight="700", color="negative")
    # -> ("hello", {"weight": "700", "color": "negative"})

Structured runs compose transparently with ``align``, ``rotate``, and
``font``: the runs share the line baseline, so a single ``<text>``
element with nested ``<tspan>`` is emitted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


Run = Tuple[str, Dict[str, Any]]
RunInput = Union[str, Run]


def Span(text: str, **style: Any) -> Run:
    """Sugar for a single styled run.

    ``Span("hello", weight="700", color="negative")`` is exactly
    equivalent to ``("hello", {"weight": "700", "color": "negative"})``,
    and both forms may be freely mixed inside a :class:`Text` or
    :class:`TextBlock`.

    Accepted style keys: ``color``, ``weight``, ``italic``, ``size``.
    Any other key passes through but is currently ignored.
    """
    return (text, dict(style))


def _normalize_runs(runs: Sequence[RunInput]) -> List[Run]:
    """Normalise a mixed list of strings and ``(text, style)`` tuples."""
    out: List[Run] = []
    for item in runs:
        if isinstance(item, str):
            out.append((item, {}))
        elif isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            out.append((item[0], dict(item[1] or {})))
        else:
            raise TypeError(
                f"Text run must be str or (str, dict); got {item!r}")
    return out


def _run_width(theme: Theme, text: str, base_size, base_weight: str,
               style: Dict[str, Any]) -> float:
    size = style.get("size", base_size)
    weight = style.get("weight", base_weight)
    bold = weight in ("bold", "600", "700")
    return theme.text_width(text, size, bold=bold)


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _text_ink_y(theme: Theme, size) -> tuple[float, float]:
    """Return the visual text band inside sciviz's single-line text box.

    The normal text measure includes a small safety gutter. Alignment should
    follow the actual line band, not that gutter, otherwise icons and text in
    headers/cards appear optically off-centre.
    """
    sz = theme.size_px(size)
    baseline = sz * 0.88
    ascent = sz * 0.82
    descent = sz * 0.22
    return baseline - ascent, ascent + descent


class Text(Element):
    """Single-line text. Semantic size and colour names are preferred.

    Parameters
    ----------
    content : str or list of runs
        Either a plain string or a list of runs (``str`` or
        ``(str, style_dict)``). See module docstring.
    size : str or float
        Default size (overridden per-run in structured mode).
    color : str
        Default colour.
    weight : str
        Default CSS font-weight (``"normal"``, ``"600"``, ``"700"``).
    italic : bool
        Default italic flag.
    align : str
        ``"start"``, ``"middle"`` / ``"center"`` or ``"end"``.
    font, rotate : pass-through to the single-line renderer.
    """

    def __init__(self, content: Union[str, Sequence[RunInput]], *,
                 size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 font: Optional[str] = None,
                 rotate: float = 0.0):
        if isinstance(content, str):
            self._runs: List[Run] = [(content, {})]
            self.content = content
        elif isinstance(content, (list, tuple)):
            self._runs = _normalize_runs(content)
            self.content = "".join(t for t, _ in self._runs)
        else:
            raise TypeError(
                f"Text content must be str or a sequence of runs; got {type(content)}")
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.font = font
        self.rotate = rotate

    @property
    def is_runs(self) -> bool:
        return len(self._runs) > 1 or bool(self._runs[0][1])

    def _resolved_font(self, theme: Theme) -> Optional[str]:
        if self.font is None:
            return None
        if self.font == "mono":
            return getattr(theme, "font_mono", None) or \
                "ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
        return self.font

    def _total_width(self, theme: Theme) -> float:
        if not self.is_runs:
            bold = self.weight in ("bold", "600", "700")
            return theme.text_width(self.content, self.size, bold=bold)
        total = 0.0
        for text, style in self._runs:
            total += _run_width(theme, text, self.size, self.weight, style)
        return total

    def measure(self, theme: Theme) -> BBox:
        w = self._total_width(theme)
        h = theme.text_height(self.size)
        if self.rotate in (90, -90, 270, -270):
            return BBox(h, w)
        return BBox(w, h)

    def content_bbox(self, theme: Theme) -> tuple[float, float, float, float]:
        bbox = self.measure(theme)
        if self.rotate in (90, -90, 270, -270):
            return (0.0, 0.0, bbox.w, bbox.h)
        top, h = _text_ink_y(theme, self.size)
        return (0.0, top, bbox.w, h)

    def _render_plain(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px(self.size)
        fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        if self.rotate in (90, -90, 270, -270):
            cx = x + bbox.w / 2
            cy = y + bbox.h / 2
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
                f'text-anchor="middle"{ff_attr}{italic_attr}{weight_attr} '
                f'{extra}>{_xml_escape(self.content)}</text>'
            )
            return
        baseline = y + sz * 0.88
        if self.align in ("middle", "center"):
            tx = x + bbox.w / 2
            svg_anchor = "middle"
        elif self.align == "end":
            tx = x + bbox.w
            svg_anchor = "end"
        else:
            tx = x
            svg_anchor = "start"
        canvas.text(tx, baseline, self.content, size=sz, fill=fill,
                    weight=self.weight, italic=self.italic, anchor=svg_anchor,
                    font_family=self._resolved_font(theme))

    def _render_runs(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        sz = theme.size_px(self.size)
        default_fill = theme.color_of(self.color)
        bbox = self.measure(theme)
        baseline = y + sz * 0.88
        # Resolve anchor position.
        if self.align in ("middle", "center"):
            tx = x + bbox.w / 2
            svg_anchor = "middle"
        elif self.align == "end":
            tx = x + bbox.w
            svg_anchor = "end"
        else:
            tx = x
            svg_anchor = "start"
        ff = self._resolved_font(theme)

        # Build opening <text>.
        parts = [f'x="{tx:.2f}"', f'y="{baseline:.2f}"',
                 f'font-size="{sz:.2f}"', f'fill="{default_fill}"']
        if ff:
            parts.append(f'font-family="{ff}"')
        if self.weight != "normal":
            parts.append(f'font-weight="{self.weight}"')
        if self.italic:
            parts.append('font-style="italic"')
        if svg_anchor != "start":
            parts.append(f'text-anchor="{svg_anchor}"')

        # Emit each run as a <tspan>.
        tspans: List[str] = []
        for text, style in self._runs:
            attrs: List[str] = []
            rsize = style.get("size")
            if rsize is not None and rsize != self.size:
                attrs.append(f'font-size="{theme.size_px(rsize):.2f}"')
            rcolor = style.get("color")
            if rcolor is not None and rcolor != self.color:
                attrs.append(f'fill="{theme.color_of(rcolor)}"')
            rweight = style.get("weight")
            if rweight is not None and rweight != self.weight:
                attrs.append(f'font-weight="{rweight}"')
            rital = style.get("italic", self.italic)
            if bool(rital) != bool(self.italic):
                attrs.append(
                    f'font-style="{"italic" if rital else "normal"}"')
            if attrs:
                tspans.append(
                    f'<tspan {" ".join(attrs)}>{_xml_escape(text)}</tspan>')
            else:
                tspans.append(_xml_escape(text))

        canvas.raw(f"<text {' '.join(parts)}>{''.join(tspans)}</text>")

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        if not self.is_runs:
            self._render_plain(canvas, x, y, theme)
        else:
            self._render_runs(canvas, x, y, theme)


LineSpec = Union[str, Sequence[RunInput]]


class TextBlock(Element):
    """Multi-line text block.

    Each line may be:

    * a plain string (existing behaviour), or
    * a list of runs (``str`` or ``(str, style_dict)``, like :class:`Text`).

    For backwards compatibility, the single-argument form still accepts a
    plain ``\\n``-separated string and splits it into lines that share
    the block's default style.
    """

    def __init__(self, content: Union[str, Sequence[LineSpec]], *,
                 size: Union[str, float] = "label",
                 color: str = "dark", weight: str = "normal",
                 italic: bool = False, align: str = "start",
                 line_spacing: float = 1.35,
                 max_width: Optional[float] = None):
        if isinstance(content, str):
            self._raw: List[LineSpec] = list(content.split("\n"))
            self.content = content
        elif isinstance(content, (list, tuple)):
            self._raw = list(content)
            self.content = "\n".join(
                l if isinstance(l, str)
                else "".join(t for t, _ in _normalize_runs(l))
                for l in self._raw
            )
        else:
            raise TypeError(
                f"TextBlock content must be str or a sequence of lines; "
                f"got {type(content)}")
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.align = align
        self.line_spacing = line_spacing
        self.max_width = max_width

    def _lines_as_text(self) -> List[Text]:
        out: List[Text] = []
        for line in self._raw:
            if isinstance(line, str):
                out.append(Text(line, size=self.size, color=self.color,
                                weight=self.weight, italic=self.italic,
                                align=self.align))
            else:
                out.append(Text(list(line), size=self.size, color=self.color,
                                weight=self.weight, italic=self.italic,
                                align=self.align))
        return out

    def _wrapped_lines(self, theme: Theme) -> List[LineSpec]:
        """Apply ``max_width`` word-wrapping to plain-string lines.

        Lines given as structured runs are left untouched -- wrapping
        them sensibly would require reflowing across runs and is left as
        future work.
        """
        if self.max_width is None:
            return list(self._raw)
        out: List[LineSpec] = []
        bold = self.weight in ("bold", "600", "700")
        for line in self._raw:
            if not isinstance(line, str):
                out.append(line)
                continue
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
        lines = self._wrapped_lines(theme)
        widths: List[float] = []
        bold = self.weight in ("bold", "600", "700")
        for line in lines:
            if isinstance(line, str):
                widths.append(theme.text_width(line, self.size, bold=bold))
            else:
                runs = _normalize_runs(line)
                widths.append(
                    sum(_run_width(theme, t, self.size, self.weight, s)
                        for t, s in runs))
        line_h = theme.size_px(self.size) * self.line_spacing
        w = max(widths) if widths else 0.0
        if self.max_width is not None:
            w = max(w, 0.0)
        h = line_h * len(lines)
        return BBox(w, h)

    def _line_widths(self, theme: Theme) -> list[float]:
        widths: list[float] = []
        bold = self.weight in ("bold", "600", "700")
        for line in self._wrapped_lines(theme):
            if isinstance(line, str):
                widths.append(theme.text_width(line, self.size, bold=bold))
            else:
                runs = _normalize_runs(line)
                widths.append(
                    sum(_run_width(theme, t, self.size, self.weight, s)
                        for t, s in runs))
        return widths

    def content_bbox(self, theme: Theme) -> tuple[float, float, float, float]:
        lines = self._wrapped_lines(theme)
        if not lines:
            return (0.0, 0.0, 0.0, 0.0)
        bbox = self.measure(theme)
        widths = self._line_widths(theme)
        line_h = theme.size_px(self.size) * self.line_spacing
        ink_top, ink_h = _text_ink_y(theme, self.size)
        x0 = float("inf")
        x1 = float("-inf")
        for w in widths:
            if self.align in ("middle", "center"):
                lx = (bbox.w - w) / 2
            elif self.align == "end":
                lx = bbox.w - w
            else:
                lx = 0.0
            x0 = min(x0, lx)
            x1 = max(x1, lx + w)
        y0 = ink_top
        y1 = (len(lines) - 1) * line_h + ink_top + ink_h
        return (x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        lines = self._wrapped_lines(theme)
        sz = theme.size_px(self.size)
        line_h = sz * self.line_spacing
        bbox = self.measure(theme)
        for i, line in enumerate(lines):
            y_line = y + i * line_h
            if isinstance(line, str):
                t = Text(line, size=self.size, color=self.color,
                         weight=self.weight, italic=self.italic,
                         align=self.align)
            else:
                t = Text(list(line), size=self.size, color=self.color,
                         weight=self.weight, italic=self.italic,
                         align=self.align)
            tb = t.measure(theme)
            # Align the line within the block's full width.
            if self.align in ("middle", "center"):
                tx = x + (bbox.w - tb.w) / 2
            elif self.align == "end":
                tx = x + (bbox.w - tb.w)
            else:
                tx = x
            t.render(canvas, tx, y_line, theme)
