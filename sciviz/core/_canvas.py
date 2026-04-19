"""Canvas: minimal SVG accumulator with primitive drawing helpers.

Elements call the drawing primitives (:meth:`Canvas.rect`, :meth:`Canvas.line`,
:meth:`Canvas.text`, ...) which append stringified SVG to an internal
buffer. The :class:`sciviz.diagram.Diagram` serialises the buffer at
export time.

Arrowhead markers and similar shared definitions are registered on the
canvas via :meth:`Canvas.define_marker`; each unique ``(name, color)``
pair is only emitted once.
"""

from __future__ import annotations

from typing import List, Optional


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def _build_text_runs(content: str) -> str:
    """XML-escape ``content`` for placement inside a ``<text>``.

    PNG export uses ``resvg`` which performs glyph-level font
    fallback across the author's ``font-family`` stack, so we can
    simply emit the content verbatim and let the renderer pick a
    face that covers each codepoint.
    """
    return _xml_escape(content)


def _fmt(v: float) -> str:
    """Compact float formatting for SVG attributes."""
    if isinstance(v, int):
        return str(v)
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}"


class Canvas:
    """Minimal SVG accumulator."""

    # Arrowhead size in pixels = ARROW_HEAD_SCALE * stroke_width.
    # 4.5 gives small, neat heads that read as line terminators at the
    # default 0.9 px stroke (~4 px head) while still scaling up for
    # thick connectors -- matching the tight arrowheads in paper figures.
    ARROW_HEAD_SCALE: float = 4.5

    def __init__(self):
        self._defs: List[str] = []
        self._body: List[str] = []
        self._marker_ids: dict = {}
        self._next_id: int = 0

    # ------------ defs & markers ------------

    def define_marker(self, *, color: str, size: float = 7.0,
                      name_hint: str = "arr") -> str:
        """Register an arrowhead marker of the given absolute size.

        Prefer :meth:`define_arrow_marker` for arrows -- that sizes the
        head to the stroke width so the triangle matches the shaft.

        Idempotent: repeated calls with the same ``(color, size)`` reuse
        the previously emitted marker.
        """
        key = (color, round(size, 2), name_hint)
        if key in self._marker_ids:
            return self._marker_ids[key]
        mid = f"{name_hint}-{len(self._marker_ids)}"
        self._marker_ids[key] = mid
        # refX=9 places the triangle tip on the line endpoint, so the
        # whole head sits just OUTSIDE the target along the flow
        # direction -- the head touches the target boundary without
        # crossing into it. This matches the convention of paper
        # figures (arrowheads stop at the box edge, not inside it).
        self._defs.append(
            f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="{_fmt(size)}" markerHeight="{_fmt(size)}" '
            f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
        return mid

    def define_arrow_marker(self, *, color: str, stroke_width: float,
                            arrow_size: Optional[float] = None,
                            name_hint: str = "arrow") -> str:
        """Register an arrowhead marker for a line with ``stroke_width`` ink.

        If ``arrow_size`` is given (the preferred path, normally fed from
        :attr:`Theme.arrow_size`), the triangle is rendered at exactly
        that size regardless of stroke width -- so every arrow in a
        diagram reads at the same visual weight. Otherwise the head
        scales linearly with stroke width (legacy behaviour used by
        ad-hoc callers that don't know the current theme).
        """
        if arrow_size is not None and arrow_size > 0:
            size = float(arrow_size)
        else:
            size = max(3.0, stroke_width * self.ARROW_HEAD_SCALE)
        return self.define_marker(color=color, size=size, name_hint=name_hint)

    def raw_def(self, svg: str) -> None:
        self._defs.append(svg)

    def raw(self, svg: str) -> None:
        self._body.append(svg)

    def gen_id(self, prefix: str = "id") -> str:
        self._next_id += 1
        return f"{prefix}{self._next_id}"

    # ------------ primitives ------------

    def rect(self, x: float, y: float, w: float, h: float, *,
             fill: str = "none", stroke: str = "none",
             stroke_width: float = 1.0, rx: float = 0,
             dasharray: Optional[str] = None, opacity: float = 1.0,
             stroke_opacity: float = 1.0) -> None:
        parts = [
            f'x="{_fmt(x)}"', f'y="{_fmt(y)}"',
            f'width="{_fmt(w)}"', f'height="{_fmt(h)}"',
            f'fill="{fill}"',
        ]
        if stroke != "none":
            parts.append(f'stroke="{stroke}"')
            parts.append(f'stroke-width="{_fmt(stroke_width)}"')
            if stroke_opacity < 1.0:
                parts.append(f'stroke-opacity="{_fmt(stroke_opacity)}"')
        if rx > 0:
            parts.append(f'rx="{_fmt(rx)}"')
        if dasharray:
            parts.append(f'stroke-dasharray="{dasharray}"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        self._body.append(f"<rect {' '.join(parts)}/>")

    def circle(self, cx: float, cy: float, r: float, *,
               fill: str = "none", stroke: str = "none",
               stroke_width: float = 1.0, opacity: float = 1.0) -> None:
        parts = [f'cx="{_fmt(cx)}"', f'cy="{_fmt(cy)}"',
                 f'r="{_fmt(r)}"', f'fill="{fill}"']
        if stroke != "none":
            parts.append(f'stroke="{stroke}" stroke-width="{_fmt(stroke_width)}"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        self._body.append(f"<circle {' '.join(parts)}/>")

    def line(self, x1: float, y1: float, x2: float, y2: float, *,
             stroke: str = "#0f172a", stroke_width: float = 1.0,
             dasharray: Optional[str] = None, opacity: float = 1.0,
             marker_end: Optional[str] = None,
             marker_start: Optional[str] = None) -> None:
        parts = [f'x1="{_fmt(x1)}"', f'y1="{_fmt(y1)}"',
                 f'x2="{_fmt(x2)}"', f'y2="{_fmt(y2)}"',
                 f'stroke="{stroke}"',
                 f'stroke-width="{_fmt(stroke_width)}"']
        if dasharray:
            parts.append(f'stroke-dasharray="{dasharray}"')
        if marker_end:
            parts.append(f'marker-end="url(#{marker_end})"')
        if marker_start:
            parts.append(f'marker-start="url(#{marker_start})"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        self._body.append(f"<line {' '.join(parts)}/>")

    def path(self, d: str, *, fill: str = "none", stroke: str = "none",
             stroke_width: float = 1.0, dasharray: Optional[str] = None,
             opacity: float = 1.0, marker_end: Optional[str] = None) -> None:
        parts = [f'd="{d}"', f'fill="{fill}"']
        if stroke != "none":
            parts.append(f'stroke="{stroke}" stroke-width="{_fmt(stroke_width)}"')
        if dasharray:
            parts.append(f'stroke-dasharray="{dasharray}"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        if marker_end:
            parts.append(f'marker-end="url(#{marker_end})"')
        self._body.append(f"<path {' '.join(parts)}/>")

    def polygon(self, points: List[tuple], *, fill: str = "none",
                stroke: str = "none", stroke_width: float = 1.0,
                opacity: float = 1.0) -> None:
        pts = " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in points)
        parts = [f'points="{pts}"', f'fill="{fill}"']
        if stroke != "none":
            parts.append(f'stroke="{stroke}" stroke-width="{_fmt(stroke_width)}"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        self._body.append(f"<polygon {' '.join(parts)}/>")

    def text(self, x: float, y: float, content: str, *,
             size: float = 11.0, fill: str = "#0f172a",
             weight: str = "normal", italic: bool = False,
             anchor: str = "start", opacity: float = 1.0,
             baseline: str = "alphabetic",
             font_family: Optional[str] = None) -> None:
        """Render text. ``y`` is the baseline position."""
        parts = [f'x="{_fmt(x)}"', f'y="{_fmt(y)}"',
                 f'font-size="{_fmt(size)}"', f'fill="{fill}"']
        if font_family is not None:
            parts.append(f'font-family="{font_family}"')
        if weight != "normal":
            parts.append(f'font-weight="{weight}"')
        if anchor != "start":
            parts.append(f'text-anchor="{anchor}"')
        if italic:
            parts.append('font-style="italic"')
        if baseline == "middle":
            parts.append('dominant-baseline="central"')
        elif baseline == "hanging":
            parts.append('dominant-baseline="hanging"')
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        inner = _build_text_runs(content)
        self._body.append(f"<text {' '.join(parts)}>{inner}</text>")

    def text_with_sub(self, x: float, y: float, base: str, sub: str, *,
                      size: float = 11.0, fill: str = "#0f172a",
                      weight: str = "normal", anchor: str = "start") -> None:
        """Render ``base`` followed by a subscript ``sub``."""
        parts = [f'x="{_fmt(x)}"', f'y="{_fmt(y)}"',
                 f'font-size="{_fmt(size)}"', f'fill="{fill}"']
        if weight != "normal":
            parts.append(f'font-weight="{weight}"')
        if anchor != "start":
            parts.append(f'text-anchor="{anchor}"')
        self._body.append(
            f"<text {' '.join(parts)}>{_build_text_runs(base)}"
            f'<tspan font-size="{_fmt(size*0.72)}" baseline-shift="sub">'
            f'{_build_text_runs(sub)}</tspan></text>'
        )

    def svg_path(self, x: float, y: float, w: float, h: float, *,
                 paths: List[str],
                 viewbox: "tuple[float, float, float, float]" = (0.0, 0.0, 24.0, 24.0),
                 stroke: str = "#0f172a", stroke_width: float = 1.5,
                 fill: str = "none",
                 linecap: str = "round",
                 linejoin: str = "round",
                 opacity: float = 1.0) -> None:
        """Place a list of SVG path commands inside an ``(x, y, w, h)`` box.

        Used by :class:`sciviz.Icon` to render a Lucide-style stroke icon
        at any size. Each entry in ``paths`` is the value of a ``d="..."``
        attribute. A nested ``<svg viewBox=...>`` scales the icon so its
        ``viewbox`` maps to ``(w, h)`` in user space while preserving the
        linecap/linejoin perception authors expect.
        """
        vx, vy, vw, vh = viewbox
        attrs = [
            f'x="{_fmt(x)}"', f'y="{_fmt(y)}"',
            f'width="{_fmt(w)}"', f'height="{_fmt(h)}"',
            f'viewBox="{_fmt(vx)} {_fmt(vy)} {_fmt(vw)} {_fmt(vh)}"',
            f'fill="{fill}"',
            f'stroke="{stroke}"',
            f'stroke-width="{_fmt(stroke_width)}"',
            f'stroke-linecap="{linecap}"',
            f'stroke-linejoin="{linejoin}"',
        ]
        if opacity < 1.0:
            attrs.append(f'opacity="{_fmt(opacity)}"')
        inner = "".join(f'<path d="{d}"/>' for d in paths)
        self._body.append(f"<svg {' '.join(attrs)}>{inner}</svg>")

    def image(self, x: float, y: float, w: float, h: float, *,
              href: str,
              preserve_aspect_ratio: str = "xMidYMid meet",
              opacity: float = 1.0) -> None:
        """Place a raster or vector image at ``(x, y)`` sized ``(w, h)``.

        ``href`` is typically a ``data:image/png;base64,...`` URL so the
        image travels with the SVG; external URLs also work but break
        offline export.
        """
        parts = [
            f'x="{_fmt(x)}"', f'y="{_fmt(y)}"',
            f'width="{_fmt(w)}"', f'height="{_fmt(h)}"',
            f'href="{href}"',
            f'preserveAspectRatio="{preserve_aspect_ratio}"',
        ]
        if opacity < 1.0:
            parts.append(f'opacity="{_fmt(opacity)}"')
        self._body.append(f"<image {' '.join(parts)}/>")

    def group_open(self, *, transform: Optional[str] = None,
                   opacity: float = 1.0, clip: Optional[str] = None) -> None:
        attrs = []
        if transform:
            attrs.append(f'transform="{transform}"')
        if opacity < 1.0:
            attrs.append(f'opacity="{_fmt(opacity)}"')
        if clip:
            attrs.append(f'clip-path="url(#{clip})"')
        self._body.append(f"<g {' '.join(attrs)}>")

    def group_close(self) -> None:
        self._body.append("</g>")

    # ------------ serialisation ------------

    def to_svg(self, width: float, height: float, *, bg: str = "#ffffff",
               font_family: str = "Inter, 'Helvetica Neue', Arial, sans-serif") -> str:
        defs = "\n  ".join(self._defs) if self._defs else ""
        body = "\n".join(self._body)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {_fmt(width)} {_fmt(height)}" '
            f'font-family="{font_family}">\n'
            f'<defs>\n  {defs}\n</defs>\n'
            f'<rect width="{_fmt(width)}" height="{_fmt(height)}" fill="{bg}"/>\n'
            f'{body}\n'
            f'</svg>'
        )
