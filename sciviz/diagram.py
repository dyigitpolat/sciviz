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
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from .core import (
    Element, BBox, Canvas, Theme, DEFAULT_THEME,
    FontRegistry, outline_svg_text,
)


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
                 background: Optional[str] = None,
                 chrome: str = "full",
                 auto_fit: bool = True,
                 max_fit_passes: int = 2,
                 auto_trim: bool = False):
        self.body = body
        if chrome not in ("full", "none", "footer-only"):
            raise ValueError("chrome must be 'full', 'none', or 'footer-only'")
        self.chrome = chrome
        self.title = None if chrome in ("none", "footer-only") else title
        self.subtitle = None if chrome in ("none", "footer-only") else subtitle
        self.footer = None if chrome == "none" else footer
        self.theme = theme
        self.background = background
        self.auto_fit = auto_fit
        self.max_fit_passes = max(1, int(max_fit_passes))
        # ``auto_trim`` complements ``auto_fit``: after any growth pass,
        # check the ink bbox against the canvas and shrink the canvas so
        # the final figure does not carry oversized blank margins on
        # any edge. Default off to keep backwards-compatible behaviour;
        # ``for_paper`` opts in because tight paper figures suffer most
        # from accidental whitespace.
        self.auto_trim = auto_trim
        self._last_render_size: Optional[BBox] = None

    @classmethod
    def for_paper(cls, body: Element, **kwargs) -> "Diagram":
        """Construct a caption-friendly paper figure with no title chrome."""
        kwargs.setdefault("chrome", "none")
        kwargs.setdefault("auto_trim", True)
        return cls(body, **kwargs)

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
        m = self._margin()
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

    def _margin(self) -> float:
        if self.chrome == "none":
            return self.theme.unit * 0.5
        return self.theme.diagram_margin

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

    def _render_canvas(self, size: BBox, *, offset_x: float = 0.0,
                       offset_y: float = 0.0) -> Canvas:
        canvas = Canvas()
        m = self._margin()
        # paper: title left-aligned at content origin
        body_for_render = self._body_for_render()
        body_sz = body_for_render.measure(self.theme)
        content_x = (size.w - max(body_sz.w,
                                  self.footer.measure(self.theme).w if self.footer else 0)) / 2
        if content_x < m:
            content_x = m

        y = m + offset_y
        content_x += offset_x
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
        body_x = (size.w - body_sz.w) / 2 + offset_x
        body_for_render.render(canvas, body_x, y, self.theme)
        y += body_sz.h

        if self.footer:
            y += self.theme.unit * 2.0
            footer_sz = self.footer.measure(self.theme)
            footer_x = (size.w - footer_sz.w) / 2 + offset_x
            self.footer.render(canvas, footer_x, y, self.theme)
        return canvas

    def _svg_from_canvas(self, canvas: Canvas, size: BBox, *,
                         embed_fonts: bool = True) -> str:
        bg = self.background or self.theme.bg
        registry = FontRegistry.default(self.theme.font_family) if embed_fonts else None
        return canvas.to_svg(size.w, size.h, bg=bg,
                             font_family=self.theme.font_family,
                             embed_fonts=embed_fonts,
                             font_registry=registry)

    def render(self, *, embed_fonts: bool = True) -> str:
        """Produce SVG source for the diagram."""
        size = self.measure()
        offset_x = 0.0
        offset_y = 0.0
        canvas = self._render_canvas(size)
        if self.auto_fit:
            for _ in range(self.max_fit_passes - 1):
                ink = canvas.ink_bbox
                if ink is None:
                    break
                x0, y0, x1, y1 = ink
                grow_l = max(0.0, -x0)
                grow_t = max(0.0, -y0)
                grow_r = max(0.0, x1 - size.w)
                grow_b = max(0.0, y1 - size.h)
                if max(grow_l, grow_t, grow_r, grow_b) <= 0.5:
                    break
                offset_x += grow_l
                offset_y += grow_t
                size = BBox(size.w + grow_l + grow_r,
                            size.h + grow_t + grow_b)
                canvas = self._render_canvas(size, offset_x=offset_x,
                                             offset_y=offset_y)
        if self.auto_trim:
            size, offset_x, offset_y, canvas = self._auto_trim_render(
                size, offset_x, offset_y, canvas)
        self._last_render_size = size
        return self._svg_from_canvas(canvas, size, embed_fonts=embed_fonts)

    def _auto_trim_render(self, size: BBox, offset_x: float, offset_y: float,
                          canvas: Canvas):
        """Shrink the rendered canvas if any edge has > ``margin`` blank.

        ``auto_fit`` already grows the canvas to contain overflowing ink,
        but it never shrinks it when the body measured larger than the
        ink actually painted (a common outcome of recent measurement
        upgrades). This method preserves at least ``_margin()`` of blank
        space on every edge but removes any extra blank that exceeds
        twice the margin -- keeping the trim conservative so authors
        who *want* whitespace can still place spacers in the body.

        The shrink also rebalances the body's centering offset: when
        the canvas width changes, ``_render_canvas`` already shifts the
        body by ``(new_w - body_w)/2``; we layer an additional offset
        only for the asymmetric excess so the ink ends up flush with
        the desired margin on the trimmed side without crossing the
        opposite side.
        """
        ink = canvas.ink_bbox
        if ink is None:
            return size, offset_x, offset_y, canvas
        x0, y0, x1, y1 = ink
        margin = self._margin()
        # Allow a small extra cushion before trimming kicks in, so we
        # never tighten so aggressively that paint near the edge looks
        # cropped at common viewport zoom levels.
        cushion = margin
        excess_l = max(0.0, x0 - margin - cushion)
        excess_t = max(0.0, y0 - margin - cushion)
        excess_r = max(0.0, (size.w - x1) - margin - cushion)
        excess_b = max(0.0, (size.h - y1) - margin - cushion)
        if max(excess_l, excess_t, excess_r, excess_b) <= 0.5:
            return size, offset_x, offset_y, canvas
        new_w = max(margin * 2 + (x1 - x0), size.w - excess_l - excess_r)
        new_h = max(margin * 2 + (y1 - y0), size.h - excess_t - excess_b)
        # ``_render_canvas`` centers the body on the new size, which
        # already absorbs ``(excess_l + excess_r) / 2`` of the trim
        # symmetrically. Only the asymmetric part needs an explicit
        # offset; otherwise we would shift the body left twice and
        # clip its ink off the new left edge.
        offset_x += (excess_r - excess_l) / 2.0
        offset_y += (excess_b - excess_t) / 2.0
        new_size = BBox(new_w, new_h)
        canvas = self._render_canvas(new_size, offset_x=offset_x,
                                     offset_y=offset_y)
        return new_size, offset_x, offset_y, canvas

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def save(self, path: Union[str, os.PathLike], *,
             dpi: float = 192.0, scale: Optional[float] = None,
             embed_fonts: bool = True,
             pdf_backend: str = "auto",
             text_mode: str = "auto") -> Path:
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
        text_mode : {"auto", "live", "outline"}
            ``auto`` preserves live SVG text so PNG/PDF follow the same font
            stack as SVG. Use ``outline`` only when a PDF pipeline cannot
            resolve the needed fonts and glyph-path output is preferred.
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        svg_source = self.render(embed_fonts=embed_fonts)
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
            size = self._last_render_size or self.measure()
            if scale is None:
                scale = dpi / 96.0
            if text_mode == "outline":
                svg_source = outline_svg_text(
                    svg_source,
                    FontRegistry.default(self.theme.font_family),
                    self.theme.font_family,
                )
            elif text_mode not in ("auto", "live"):
                raise ValueError("text_mode must be 'auto', 'outline', or 'live'")
            data = resvg_py.svg_to_bytes(
                svg_string=svg_source,
                width=int(size.w * scale),
                height=int(size.h * scale),
            )
            with open(out, "wb") as fh:
                fh.write(bytes(data))
            return out
        if ext == ".pdf":
            self._save_pdf(svg_source, out, backend=pdf_backend,
                           text_mode=text_mode)
            return out
        raise ValueError(
            f"Unsupported output extension {ext!r}. Use .svg, .pdf, or .png."
        )

    def save_all(self, base_path: Union[str, os.PathLike], *,
                 formats=("svg", "pdf", "png"), dpi: float = 192.0,
                 **save_kwargs):
        """Save the diagram to multiple formats sharing a base path (no ext)."""
        base = Path(base_path)
        if base.suffix:
            base = base.with_suffix("")
        out_paths = []
        for fmt in formats:
            out_paths.append(self.save(f"{base}.{fmt}", dpi=dpi, **save_kwargs))
        return out_paths

    def _save_pdf(self, svg_source: str, out: Path, *, backend: str,
                  text_mode: str) -> None:
        chosen = backend
        if backend == "auto":
            chosen = self._probe_pdf_backend()
        if chosen in ("rsvg-convert", "inkscape"):
            try:
                self._save_pdf_external(svg_source, out, chosen)
                return
            except Exception:
                if backend != "auto":
                    raise
                chosen = "cairosvg"
                text_mode = "outline"
        if chosen != "cairosvg":
            raise ValueError(
                "pdf_backend must be 'auto', 'cairosvg', 'rsvg-convert', or 'inkscape'"
            )
        try:
            import cairosvg  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Exporting to .pdf requires cairosvg when no font-aware "
                "external converter is available. Install with: pip install cairosvg"
            ) from e
        if text_mode == "outline":
            svg_source = outline_svg_text(
                svg_source,
                FontRegistry.default(self.theme.font_family),
                self.theme.font_family,
            )
        elif text_mode not in ("auto", "live"):
            raise ValueError("text_mode must be 'auto', 'outline', or 'live'")
        cairosvg.svg2pdf(bytestring=svg_source.encode("utf-8"),
                         write_to=str(out))

    @staticmethod
    def _probe_pdf_backend() -> str:
        if shutil.which("rsvg-convert"):
            return "rsvg-convert"
        if shutil.which("inkscape"):
            return "inkscape"
        return "cairosvg"

    @staticmethod
    def _save_pdf_external(svg_source: str, out: Path, backend: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "figure.svg"
            svg_path.write_text(svg_source, encoding="utf-8")
            if backend == "rsvg-convert":
                subprocess.run(
                    ["rsvg-convert", "-f", "pdf", "-o", str(out), str(svg_path)],
                    check=True,
                )
                return
            if backend == "inkscape":
                subprocess.run(
                    ["inkscape", str(svg_path), "--export-type=pdf",
                     f"--export-filename={out}"],
                    check=True,
                )
                return
        raise ValueError(f"Unknown PDF backend {backend!r}")

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
