"""Top-level :class:`Diagram` class with export to SVG, PDF, and PNG.

A :class:`Diagram` is the root of every sciviz figure.  It composes:

    [ title     ]
    [ subtitle  ]
    [   body    ]     <- any Element (Row, Column, Panel, Grid, ...)
    [  footer   ]     <- optional secondary Element

and handles margins, background, and file export.  The body element is what
authors spend most of their time composing; everything else is structural.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from .core import Element, BBox, Canvas, Theme, DEFAULT_THEME


class Diagram:
    """Root container for a sciviz figure.

    Parameters
    ----------
    body : Element
        The main diagram content.  Usually a :class:`Row`, :class:`Column`,
        :class:`Grid`, or :class:`Panel`.
    title : str, optional
        Top-line title rendered above the body.
    subtitle : str, optional
        Secondary line rendered below the title in a muted colour.
    footer : Element, optional
        Content rendered below the body, typically a summary strip.
    theme : Theme, optional
        Custom theme.  Defaults to the opinionated ``DEFAULT_THEME``.
    background : str, optional
        Background colour override.  Defaults to the theme's ``bg``.

    Examples
    --------
    >>> d = Diagram(
    ...     title="My Figure",
    ...     body=Row(Panel("a", "Left", Matrix((4, 4))),
    ...              Panel("b", "Right", Matrix((4, 4)))),
    ... )
    >>> d.save("out.svg")      # vector
    >>> d.save("out.pdf")      # high-quality print
    >>> d.save("out.png")      # raster for web/slides
    """

    def __init__(self, body: Element, *,
                 title: Optional[str] = None,
                 subtitle: Optional[str] = None,
                 footer: Optional[Element] = None,
                 theme: Theme = DEFAULT_THEME,
                 background: Optional[str] = None):
        self.body = body
        self.title = title
        self.subtitle = subtitle
        self.footer = footer
        self.theme = theme
        self.background = background

    # ------------------------------------------------------------------
    # layout helpers
    # ------------------------------------------------------------------

    def _title_height(self) -> float:
        h = 0.0
        if self.title:
            h += self.theme.text_height(self.theme.font_title)
        if self.subtitle:
            h += self.theme.text_height(self.theme.font_subtitle) + self.theme.unit * 0.25
        if self.title or self.subtitle:
            h += self.theme.unit * 1.2
        return h

    def measure(self) -> BBox:
        """Measure total diagram size (including margins, title, footer)."""
        m = self.theme.diagram_margin
        body_sz = self._body_for_render().measure(self.theme)
        footer_sz = self.footer.measure(self.theme) if self.footer else BBox(0, 0)
        content_w = max(body_sz.w, footer_sz.w)
        if self.title:
            tw = self.theme.text_width(self.title, "title", bold=True)
            content_w = max(content_w, tw)
        if self.subtitle:
            sw = self.theme.text_width(self.subtitle, "subtitle")
            content_w = max(content_w, sw)
        title_h = self._title_height()
        body_gap = self.theme.unit * 2.0 if self.footer else 0.0
        total_w = content_w + 2 * m
        total_h = (title_h + body_sz.h
                   + body_gap + footer_sz.h
                   + 2 * m)
        return BBox(total_w, total_h)

    def _body_for_render(self) -> Element:
        """Wrap the body in a _FlowResolver so any ``Connect`` placeholders
        in the tree are auto-resolved without the author writing a
        ``Flowed`` wrapper.

        The wrapper is cached on the ``Diagram`` instance: a fresh resolver
        is used for every top-level render cycle so its ``_margins_applied``
        flag behaves correctly, but within a single ``render()`` call the
        ``measure()`` side-effect and the real ``render()`` share state.
        """
        from .connect._resolver import _FlowResolver
        from .composition import Flowed

        if isinstance(self.body, (Flowed, _FlowResolver)):
            return self.body
        cached = getattr(self, "_resolver_cache", None)
        if cached is None or cached.child is not self.body:
            cached = _FlowResolver(self.body)
            self._resolver_cache = cached
        return cached

    def render(self) -> str:
        """Produce SVG source for the diagram."""
        size = self.measure()
        canvas = Canvas()
        m = self.theme.diagram_margin
        # paper: title left-aligned at content origin
        body_for_render = self._body_for_render()
        body_sz = body_for_render.measure(self.theme)
        content_x = (size.w - max(body_sz.w,
                                  self.footer.measure(self.theme).w if self.footer else 0)) / 2
        if content_x < m:
            content_x = m

        y = m
        if self.title:
            baseline = y + self.theme.font_title * 0.85
            canvas.text(
                content_x, baseline, self.title,
                size=self.theme.font_title,
                fill=self.theme.text,
                weight="700", anchor="start",
            )
            y += self.theme.text_height(self.theme.font_title)
        if self.subtitle:
            y += self.theme.unit * 0.25
            baseline = y + self.theme.font_subtitle * 0.85
            canvas.text(
                content_x, baseline, self.subtitle,
                size=self.theme.font_subtitle,
                fill=self.theme.text_muted,
                weight="400", italic=True, anchor="start",
            )
            y += self.theme.text_height(self.theme.font_subtitle)
        if self.title or self.subtitle:
            y += self.theme.unit * 1.2

        # body: center horizontally within available width
        body_x = (size.w - body_sz.w) / 2
        body_for_render.render(canvas, body_x, y, self.theme)
        y += body_sz.h

        if self.footer:
            y += self.theme.unit * 2.0
            footer_sz = self.footer.measure(self.theme)
            footer_x = (size.w - footer_sz.w) / 2
            self.footer.render(canvas, footer_x, y, self.theme)

        bg = self.background or self.theme.bg
        return canvas.to_svg(size.w, size.h, bg=bg,
                            font_family=self.theme.font_family)

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def save(self, path: Union[str, os.PathLike], *,
             dpi: float = 192.0, scale: Optional[float] = None) -> Path:
        """Save the diagram to a file.

        The file type is inferred from the extension.  Supported:

        * ``.svg`` -- native SVG (always available)
        * ``.png`` -- requires ``resvg-py`` (modern Rust renderer with
          glyph-level font fallback).
        * ``.pdf`` -- requires ``cairosvg``.

        Parameters
        ----------
        path : str or Path
            Output path.  Extension determines format.
        dpi : float
            PNG rasterisation density (dots per inch of the *SVG* coordinate
            system).  192 gives a 2x-retina render.
        scale : float, optional
            Direct scale multiplier for PNG (overrides ``dpi``).
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        svg_source = self.render()
        ext = out.suffix.lower()
        if ext == ".svg":
            out.write_text(svg_source, encoding="utf-8")
            return out
        if ext == ".png":
            try:
                import resvg_py  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "Exporting to .png requires resvg-py. "
                    "Install with: pip install resvg-py"
                ) from e
            size = self.measure()
            if scale is None:
                scale = dpi / 96.0
            data = resvg_py.svg_to_bytes(
                svg_string=svg_source,
                width=int(size.w * scale),
                height=int(size.h * scale),
            )
            with open(out, "wb") as fh:
                fh.write(bytes(data))
            return out
        if ext == ".pdf":
            try:
                import cairosvg  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "Exporting to .pdf requires cairosvg. "
                    "Install with: pip install cairosvg"
                ) from e
            svg_bytes = svg_source.encode("utf-8")
            cairosvg.svg2pdf(bytestring=svg_bytes, write_to=str(out))
            return out
        raise ValueError(
            f"Unsupported output extension {ext!r}. Use .svg, .pdf, or .png."
        )

    def save_all(self, base_path: Union[str, os.PathLike], *,
                 formats=("svg", "pdf", "png"), dpi: float = 192.0):
        """Save the diagram to multiple formats sharing a base path (no ext)."""
        base = Path(base_path)
        if base.suffix:
            base = base.with_suffix("")
        out_paths = []
        for fmt in formats:
            out_paths.append(self.save(f"{base}.{fmt}", dpi=dpi))
        return out_paths

    def save_debug(self, path: Union[str, os.PathLike]) -> Path:
        """Render the diagram while recording every automatic-layout
        decision, then emit a self-contained interactive HTML page at
        ``path``.

        The page embeds the SVG unchanged, overlays every routed-connector
        path, bus spine, obstacle rectangle, and label-placement
        candidate, and exposes per-decision statistics in a side panel.
        It is the primary tool for diagnosing "why is my label sitting
        here" or "why did this arrow detour" bugs.

        Parameters
        ----------
        path : str or Path
            Output path.  Should end in ``.html``; any other extension
            is accepted but a warning is printed.

        Returns
        -------
        Path
            The written file path.
        """
        from .auto.debug import DebugRecorder, record_into
        from .auto._debug_page import render_debug_html

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        recorder = DebugRecorder()
        with record_into(recorder):
            svg_source = self.render()
        size = self.measure()
        html = render_debug_html(
            title=self.title or "sciviz debug",
            svg=svg_source,
            svg_width=size.w,
            svg_height=size.h,
            recorder=recorder,
        )
        out.write_text(html, encoding="utf-8")
        return out

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        s = self.measure()
        return (f"<Diagram title={self.title!r} "
                f"size=({s.w:.0f}x{s.h:.0f})>")
