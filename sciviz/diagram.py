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

import copy
import os
import re
import shutil
import subprocess
import tempfile
import warnings
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
    target_width_pt : float, optional
        Physical print width of the figure, in points (an IEEE column is
        252 pt).  When set, the theme's font tokens are interpreted as
        FINAL printed point sizes at that width: the exported document
        carries a physical ``width``/``height`` (one canvas unit = one
        point), the layout is compressed -- tighter wrap budgets,
        spacing, and padding, never smaller fonts -- until the canvas
        width approaches the target, and a canvas narrower than the
        target is widened to exactly the target.  If the content cannot
        fit at the authored font sizes a :class:`UserWarning` asks the
        author to reduce content; fonts are never silently shrunk.
        Default ``None`` keeps the legacy intrinsic-size behaviour.
    target_aspect : float or (float, float), optional
        Physical aspect target, expressed as height / width.  Only
        meaningful together with ``target_width_pt``.  A tuple gives the
        acceptable range (e.g. ``(1.0, 1.3)`` for "square to moderately
        tall"); a single float is shorthand for ``(0.0, value)`` -- a
        height cap.  When set, the target fitter balances the layout
        toward the range instead of stopping at the first width fit: it
        explores every reflowable container variant (see
        ``EqualGrid(columns="auto")``) and keeps compressing spacing
        while the figure is still too tall, so a 7-card diagram does not
        export as a degenerate single corridor when a balanced
        arrangement exists.  Fonts are never touched.  Default ``None``
        keeps pure width fitting.
    min_effective_font_pt : float
        Legibility floor used by the ``target_width_pt`` overflow
        warning: the printed size the smallest text must keep when the
        figure is scaled to the target width.  Default 6 pt.

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

    # ``target_width_pt`` fitting knobs: how many fixed-point layout
    # compression passes to run, how far spacing may compress (densities
    # below ~0.5 make padding read as cramped), and how much width
    # overshoot is tolerated before the overflow warning fires (a 5%
    # scale-down keeps fonts within ~95% of their authored size).
    # The fixed-point converges to the target from ABOVE (text widths
    # do not scale with density), so enough passes are needed to push
    # the structural overshoot under the half-point snap window of
    # ``_finalize_target_width``; trials are measure-only and cheap.
    _FIT_PASSES = 8
    _FIT_MIN_DENSITY = 0.5
    # When the density floor alone cannot reach the target width, the
    # fixed-point keeps going on the text wrap budget only (fonts and
    # paddings stay): re-wrapping labels onto more lines narrows the
    # figure, and the longest-word floor inside ``Box`` keeps every
    # label legible. Budgets below half the authored value fragment
    # prose into single-word lines, so the scale is floored like the
    # spacing density.
    _FIT_MIN_WRAP = 0.5
    _FIT_TOLERANCE = 1.05
    # Aspect fitting compresses in gentler geometric steps than width
    # fitting (height responds sub-linearly to spacing density).
    _FIT_ASPECT_STEP = 0.85

    def __init__(self, body: Element, *,
                 title: Optional[str] = None,
                 subtitle: Optional[str] = None,
                 footer: Optional[Element] = None,
                 theme: Theme = DEFAULT_THEME,
                 background: Optional[str] = None,
                 chrome: str = "full",
                 auto_fit: bool = True,
                 max_fit_passes: int = 2,
                 auto_trim: bool = False,
                 target_width_pt: Optional[float] = None,
                 target_aspect=None,
                 min_effective_font_pt: float = 6.0):
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
        self.target_width_pt = (float(target_width_pt)
                                if target_width_pt is not None else None)
        self.target_aspect = self._normalise_aspect(target_aspect)
        self.min_effective_font_pt = float(min_effective_font_pt)
        # Lazily-resolved layout-compressed theme (``target_width_pt``
        # fitting); ``None`` until the first measure/render resolves it.
        self._fitted_theme: Optional[Theme] = None
        self._fit_warned = False
        self._last_render_size: Optional[BBox] = None

    @classmethod
    def for_paper(cls, body: Element, **kwargs) -> "Diagram":
        """Construct a caption-friendly paper figure with no title chrome.

        Pass ``target_width_pt`` (e.g. ``252.0`` for an IEEE column) to
        declare the physical width the figure will occupy in the paper;
        theme font sizes then mean final printed points at that width.
        Add ``target_aspect`` (a height/width range such as
        ``(1.0, 1.3)``) to let the fitter also balance the layout --
        reflowing ``columns="auto"`` grids and tightening spacing --
        toward that printed shape.
        """
        kwargs.setdefault("chrome", "none")
        kwargs.setdefault("auto_trim", True)
        return cls(body, **kwargs)

    # ------------------------------------------------------------------
    # layout helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_aspect(target_aspect) -> Optional[tuple[float, float]]:
        """Return ``(min_h_over_w, max_h_over_w)`` or ``None``.

        A single float is shorthand for ``(0.0, value)`` (height cap).
        """
        if target_aspect is None:
            return None
        if isinstance(target_aspect, (int, float)):
            return (0.0, float(target_aspect))
        if isinstance(target_aspect, (tuple, list)) and len(target_aspect) == 2:
            lo, hi = float(target_aspect[0]), float(target_aspect[1])
            if lo > hi:
                lo, hi = hi, lo
            return (lo, hi)
        raise TypeError(
            "target_aspect must be None, a float, or a (min, max) pair"
        )

    def _layout_theme(self) -> Theme:
        """The theme layout and rendering actually use.

        Identical to :attr:`theme` unless ``target_width_pt`` is set, in
        which case it is the layout-compressed derivation resolved by
        :meth:`_fit_theme_to_target` (computed once, then cached).
        """
        if self.target_width_pt is None:
            return self.theme
        if self._fitted_theme is None:
            self._fitted_theme = self._fit_theme_to_target()
        return self._fitted_theme

    def _title_height(self) -> float:
        return self._title_height_for(self._layout_theme())

    def measure(self) -> BBox:
        """Measure total diagram size (including margins, title, footer)."""
        theme = self._layout_theme()
        m = self._margin()
        body_sz = self._body_for_render().measure(theme)
        footer_sz = self.footer.measure(theme) if self.footer else BBox(0, 0)
        content_w = max(body_sz.w, footer_sz.w)
        if self.title:
            tw = theme.text_width(self.title, "title", bold=True)
            content_w = max(content_w, tw)
        if self.subtitle:
            sw = theme.text_width(self.subtitle, "subtitle")
            content_w = max(content_w, sw)
        title_h = self._title_height()
        body_gap = theme.unit * 2.0 if self.footer else 0.0
        total_w = content_w + 2 * m
        total_h = (title_h + body_sz.h
                   + body_gap + footer_sz.h
                   + 2 * m)
        return BBox(total_w, total_h)

    def _margin(self) -> float:
        return self._margin_for(self._layout_theme())

    def _margin_for(self, theme: Theme) -> float:
        if self.chrome == "none":
            return theme.unit * 0.5
        return theme.diagram_margin

    # ------------------------------------------------------------------
    # target-width fitting
    # ------------------------------------------------------------------

    def _compressed_theme(self, density: float,
                          wrap_scale: float = 1.0) -> Theme:
        """Derive a layout-compressed theme: spacing tokens scale by
        ``density`` while every font token keeps its authored size.

        ``unit`` drives semantic gaps, box paddings, and the default
        word-wrap budget (``unit * wrap_budget``), so one knob tightens
        gaps and wrap targets together; ``panel_padding`` and
        ``diagram_margin`` follow so chrome compresses at the same rate
        as content. ``wrap_scale`` additionally compresses the wrap
        budget alone -- the fitter's continuation once the spacing
        density floor is reached.
        """
        base = self.theme
        return base.with_overrides(
            unit=base.unit * density,
            panel_padding=base.panel_padding * density,
            diagram_margin=base.diagram_margin * density,
            wrap_budget=base.wrap_budget * wrap_scale,
        )

    @staticmethod
    def _collect_reflowables(elem, out: list) -> None:
        """Walk an element tree and collect reflow-capable containers
        (those exposing the ``_reflow_options`` protocol) in a stable
        depth-first order."""
        if elem is None:
            return
        options = getattr(elem, "_reflow_options", None)
        if callable(options) and options():
            out.append(elem)
        children = getattr(elem, "children", None)
        if children is not None:
            for c in children:
                Diagram._collect_reflowables(c, out)
        child = getattr(elem, "child", None)
        if child is not None:
            Diagram._collect_reflowables(child, out)
        wrapped = getattr(elem, "_wrapped", None)
        if wrapped:
            for a in wrapped:
                Diagram._collect_reflowables(a, out)

    def _reflow_assignments(self):
        """Cartesian product of every reflowable container's options.

        Only explored when ``target_aspect`` is declared: without an
        aspect goal there is no criterion for preferring one reflow over
        another, so ``columns="auto"`` containers keep their intrinsic
        default. The product is capped so a pathological tree cannot
        make fitting quadratic."""
        if self.target_aspect is None:
            return [()]
        probes: list = []
        self._collect_reflowables(self.body, probes)
        if not probes:
            return [()]
        import itertools
        assignments = list(itertools.product(
            *[r._reflow_options() for r in probes]))
        return assignments[:64]

    def _trial_size(self, theme: Theme, assignment=()) -> BBox:
        """Total diagram size under ``theme``, measured on a throwaway
        copy of the content.

        Sibling-aware layouts (``equal_widths``, shape-peer
        normalisation) record sticky ``min_width`` floors on first
        measure; measuring a candidate theme on the author's tree would
        contaminate later, tighter candidates with the wider floors.
        ``assignment`` optionally pins each reflowable container (in
        depth-first order) to one of its layout variants before
        measuring.
        """
        from .connect._resolver import _FlowResolver
        from .composition import Flowed

        try:
            body = copy.deepcopy(self.body)
            footer = copy.deepcopy(self.footer) if self.footer else None
        except Exception:  # pragma: no cover -- uncopyable author tree
            body = self.body
            footer = self.footer
        if assignment:
            probes: list = []
            self._collect_reflowables(body, probes)
            for elem, choice in zip(probes, assignment):
                elem._apply_reflow(choice)
        if not isinstance(body, (Flowed, _FlowResolver)):
            body = _FlowResolver(body)
        sz = body.measure(theme)
        w, h = sz.w, sz.h
        # Routed connectors, their labels, and margin detours paint ink
        # outside the measured layout box; a measure-only trial would
        # under-report the exported size (the render pass grows the
        # canvas around ink). Render the throwaway copy onto a scratch
        # canvas and widen the trial by any overflow so the fitter
        # optimises the true footprint.
        try:
            scratch = Canvas()
            body.render(scratch, 0.0, 0.0, theme)
            ink = scratch.ink_bbox
        except Exception:  # pragma: no cover -- unrenderable trial copy
            ink = None
        if ink is not None:
            x0, y0, x1, y1 = ink
            w += max(0.0, -x0) + max(0.0, x1 - sz.w)
            h += max(0.0, -y0) + max(0.0, y1 - sz.h)
        if footer is not None:
            fsz = footer.measure(theme)
            w = max(w, fsz.w)
            h += fsz.h + theme.unit * 2.0
        if self.title:
            w = max(w, theme.text_width(self.title, "title", bold=True))
        if self.subtitle:
            w = max(w, theme.text_width(self.subtitle, "subtitle"))
        m = self._margin_for(theme)
        return BBox(w + 2 * m, h + 2 * m + self._title_height_for(theme))

    def _title_height_for(self, theme: Theme) -> float:
        h = 0.0
        if self.title:
            h += theme.text_height(theme.font_title)
        if self.subtitle:
            h += theme.text_height(theme.font_subtitle) + theme.unit * 0.25
        if self.title or self.subtitle:
            h += theme.unit * 1.2
        return h

    def _fit_density(self, target: float, assignment=()):
        """Width-then-aspect fixed-point iteration for one reflow
        assignment.  Returns ``(theme, size, density)``.

        Phase 1 is the historical width fit: compress spacing until the
        canvas width approaches the target.  Phase 2 only runs when
        ``target_aspect`` declares a height ceiling: while the figure is
        still too tall (the exported canvas is widened to the target, so
        printed aspect is ``h / max(w, target)``), spacing keeps
        compressing -- height shrinks with it, width only gets safer.
        """
        theme = self.theme
        density = 1.0
        size = self._trial_size(theme, assignment)
        for _ in range(self._FIT_PASSES):
            if size.w <= target or density <= self._FIT_MIN_DENSITY:
                break
            density = max(self._FIT_MIN_DENSITY, density * target / size.w)
            theme = self._compressed_theme(density)
            size = self._trial_size(theme, assignment)
        # Phase 1b: the spacing floor alone could not reach the target,
        # so keep the fixed-point going on the wrap budget only.  Fonts
        # and paddings stay; wrap-enabled labels re-flow onto more lines
        # (their longest-word floor still applies), so width converges
        # to the true text floor instead of giving up at the spacing
        # floor.
        wrap_scale = 1.0
        for _ in range(self._FIT_PASSES):
            if size.w <= target or wrap_scale <= self._FIT_MIN_WRAP:
                break
            wrap_scale = max(self._FIT_MIN_WRAP,
                             wrap_scale * target / size.w)
            theme = self._compressed_theme(density, wrap_scale)
            size = self._trial_size(theme, assignment)
        if self.target_aspect is not None:
            # Compression is not monotone in height (a tighter wrap
            # budget reflows text onto MORE lines, so cards get
            # narrower but taller), so probe a small density grid
            # around the width fit and keep the best candidate instead
            # of blindly walking downward.
            _, hi = self.target_aspect

            def rank(sz: BBox, dens: float):
                aspect = sz.h / max(sz.w, target)
                return (max(0.0, sz.w - target * self._FIT_TOLERANCE),
                        max(0.0, aspect - hi), -dens, sz.h)

            best = (rank(size, density), theme, size, density)
            steps = (self._FIT_ASPECT_STEP, self._FIT_ASPECT_STEP ** 2,
                     1.0 / self._FIT_ASPECT_STEP,
                     1.0 / self._FIT_ASPECT_STEP ** 2)
            probed = {round(density, 3)}
            for step in steps:
                dens = min(1.0, max(self._FIT_MIN_DENSITY, density * step))
                if round(dens, 3) in probed:
                    continue
                probed.add(round(dens, 3))
                cand_theme = self._compressed_theme(dens, wrap_scale)
                cand_size = self._trial_size(cand_theme, assignment)
                cand = (rank(cand_size, dens), cand_theme, cand_size, dens)
                if cand[0] < best[0]:
                    best = cand
            _, theme, size, density = best
        return theme, size, density

    def _fit_theme_to_target(self) -> Theme:
        """Resolve the theme (and reflow variant) that brings the canvas
        width to ``target_width_pt`` -- and, when ``target_aspect`` is
        declared, the printed aspect into its range -- without touching
        font sizes.

        Candidates are ranked lexicographically: fit the width first,
        then land the aspect in range, then prefer the least-compressed
        spacing, then the shortest figure.  The density never drops
        below :attr:`_FIT_MIN_DENSITY`; whatever width remains past the
        target is reported by the legibility warning at render time
        (see :meth:`_finalize_target_width`).
        """
        target = float(self.target_width_pt)
        if self.target_aspect is None:
            theme = self.theme
            if self._trial_size(theme).w <= target:
                return theme
            theme, _, _ = self._fit_density(target)
            return theme

        lo, hi = self.target_aspect
        best = None
        for assignment in self._reflow_assignments():
            theme, size, density = self._fit_density(target, assignment)
            aspect = size.h / max(size.w, target)
            width_pen = max(0.0, size.w - target * self._FIT_TOLERANCE)
            aspect_pen = max(0.0, lo - aspect, aspect - hi)
            score = (width_pen > 0.0, width_pen, aspect_pen > 1e-9,
                     aspect_pen, -density, size.h)
            if best is None or score < best[0]:
                best = (score, theme, assignment)
        _, theme, assignment = best
        if assignment:
            probes: list = []
            self._collect_reflowables(self.body, probes)
            for elem, choice in zip(probes, assignment):
                elem._apply_reflow(choice)
        return theme

    def _finalize_target_width(self, size: BBox, offset_x: float,
                               offset_y: float, canvas: Canvas):
        """Pin the final canvas to ``target_width_pt``.

        A canvas within half a point of the target is snapped to exactly
        the target -- widened when narrower (body stays centred), or
        trimmed by a sub-point sliver of outer margin when the density
        fixed-point left it a hair over -- so the exported figure drops
        into the paper at scale 1.0 and fonts print at their authored
        point sizes. A canvas that still overshoots the tolerance keeps
        its size -- fonts are never shrunk -- and a :class:`UserWarning`
        reports the effective printed size of the smallest text so the
        author can reduce content instead.
        """
        target = float(self.target_width_pt)
        if size.w <= target + 0.5:
            # Snap to exactly the target: an under-target canvas is
            # widened (body stays centred); a canvas a hair over -- the
            # density fixed-point converges to the target from above,
            # so sub-point overshoot is structural -- gives up at most
            # half a point of outer MARGIN (never ink: the diagram
            # margin is always wider than the nibble). Either way the
            # exported figure drops into the paper at scale 1.0.
            if size.w != target:
                size = BBox(target, size.h)
                canvas = self._render_canvas(size, offset_x=offset_x,
                                             offset_y=offset_y)
        elif size.w > target * self._FIT_TOLERANCE and not self._fit_warned:
            self._fit_warned = True
            scale = target / size.w
            smallest = canvas.min_text_size
            detail = ""
            if smallest is not None:
                eff = smallest * scale
                detail = (f" The smallest text would print at ~{eff:.1f}pt"
                          f" (authored {smallest:.1f}pt)")
                if eff < self.min_effective_font_pt:
                    detail += (f", below the min_effective_font_pt="
                               f"{self.min_effective_font_pt:g} legibility"
                               f" floor")
                detail += "."
            warnings.warn(
                f"Diagram content measures {size.w:.0f}pt wide but "
                f"target_width_pt={target:g}; at the target width the "
                f"figure scales to {scale:.2f}x.{detail} sciviz does not "
                f"shrink fonts to fit -- reduce content (shorter labels, "
                f"fewer columns) or raise target_width_pt.",
                UserWarning, stacklevel=3,
            )
        return size, canvas

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
        theme = self._layout_theme()
        m = self._margin()
        # paper: title left-aligned at content origin
        body_for_render = self._body_for_render()
        body_sz = body_for_render.measure(theme)
        content_x = (size.w - max(body_sz.w,
                                  self.footer.measure(theme).w if self.footer else 0)) / 2
        if content_x < m:
            content_x = m

        y = m + offset_y
        content_x += offset_x
        if self.title:
            baseline = y + theme.font_title * 0.85
            canvas.text(
                content_x, baseline, self.title,
                size=theme.font_title,
                fill=theme.text,
                weight="700", anchor="start",
            )
            y += theme.text_height(theme.font_title)
        if self.subtitle:
            y += theme.unit * 0.25
            baseline = y + theme.font_subtitle * 0.85
            canvas.text(
                content_x, baseline, self.subtitle,
                size=theme.font_subtitle,
                fill=theme.text_muted,
                weight="400", italic=True, anchor="start",
            )
            y += theme.text_height(theme.font_subtitle)
        if self.title or self.subtitle:
            y += theme.unit * 1.2

        # body: center horizontally within available width
        body_x = (size.w - body_sz.w) / 2 + offset_x
        body_for_render.render(canvas, body_x, y, theme)
        y += body_sz.h

        if self.footer:
            y += theme.unit * 2.0
            footer_sz = self.footer.measure(theme)
            footer_x = (size.w - footer_sz.w) / 2 + offset_x
            self.footer.render(canvas, footer_x, y, theme)
        return canvas

    def _svg_from_canvas(self, canvas: Canvas, size: BBox, *,
                         embed_fonts: bool = True) -> str:
        bg = self.background or self.theme.bg
        registry = FontRegistry.default(self.theme.font_family) if embed_fonts else None
        # With a physical target width, one canvas unit IS one point:
        # the document carries a pt-denominated size so PDF export
        # produces a page of exactly that physical width and the
        # authored font sizes survive to print.
        physical_unit = "pt" if self.target_width_pt is not None else None
        return canvas.to_svg(size.w, size.h, bg=bg,
                             font_family=self.theme.font_family,
                             embed_fonts=embed_fonts,
                             font_registry=registry,
                             physical_unit=physical_unit)

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
                # ``_render_canvas`` centres the body on the new canvas,
                # which already absorbs the symmetric half of the
                # growth; the explicit offset must carry only the
                # asymmetric residue or the body lands double-shifted
                # and the pass never converges.
                offset_x += (grow_l - grow_r) / 2.0
                offset_y += (grow_t - grow_b) / 2.0
                size = BBox(size.w + grow_l + grow_r,
                            size.h + grow_t + grow_b)
                canvas = self._render_canvas(size, offset_x=offset_x,
                                             offset_y=offset_y)
        if self.auto_trim:
            size, offset_x, offset_y, canvas = self._auto_trim_render(
                size, offset_x, offset_y, canvas)
        if self.target_width_pt is not None:
            size, canvas = self._finalize_target_width(
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
            if self.target_width_pt is not None:
                # resvg does not parse pt-denominated width/height
                # attributes. The raster size is passed explicitly below
                # and the viewBox fully determines the geometry, so the
                # physical pinning (a PDF/print concern) is dropped here.
                svg_source = re.sub(
                    r'\swidth="[0-9.]+pt" height="[0-9.]+pt"',
                    "", svg_source, count=1)
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
