"""LaTeX math rendering -> inline SVG paths.

This module provides :class:`Math`, a sciviz element that renders a LaTeX-like
math expression (matplotlib ``mathtext`` syntax) into vector SVG paths using
matplotlib's Agg backend with ``svg.fonttype='path'``.

The rendered paths are inlined into the sciviz output SVG, which means:

* The output converts cleanly to PDF via cairosvg without rasterisation.
* No font dependencies -- glyphs are vectorised at render time.
* The expression can be arbitrarily complex (fractions, sums, matrices, ...).

Internally we cache by (latex, fontsize, color, weight) to avoid re-rendering
the same expression multiple times in one diagram.
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from typing import Optional, Tuple, Union

from ..core import Element, BBox, Canvas, Theme


# ---------------------------------------------------------------------------
# matplotlib setup is deferred until first use (to keep import cheap and
# to avoid a hard dependency for users who don't need math)
# ---------------------------------------------------------------------------

_MPL_INITIALIZED = False

def _init_mpl():
    global _MPL_INITIALIZED
    if _MPL_INITIALIZED:
        return
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.fonttype"] = "path"
    matplotlib.rcParams["svg.hashsalt"] = "sciviz"
    matplotlib.rcParams["mathtext.fontset"] = "cm"      # Computer Modern
    matplotlib.rcParams["font.family"] = "serif"
    matplotlib.rcParams["font.serif"] = ["cmr10", "DejaVu Serif", "Times"]
    _MPL_INITIALIZED = True


_VIEWBOX_RE = re.compile(
    r'viewBox="([\-\d.]+)\s+([\-\d.]+)\s+([\-\d.]+)\s+([\-\d.]+)"'
)
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.DOTALL)
_SVG_CLOSE_RE = re.compile(r"</svg>\s*$", re.DOTALL)
# matplotlib emits an outer <g> whose transform maps its internal coordinate
# system to the viewBox of its SVG; we want to keep the outer g so our own
# group transform is simple.


@lru_cache(maxsize=256)
def _render_math_svg(latex: str, fontsize: float,
                     color: str, bold: bool) -> Tuple[str, float, float]:
    """Render a math expression and return ``(inner_svg, width_px, height_px)``.

    The returned ``inner_svg`` is the body of matplotlib's SVG (everything
    inside ``<svg>...</svg>``), aligned so that (0, 0) is the top-left of the
    rendered expression.
    """
    _init_mpl()
    import matplotlib.pyplot as plt

    # Work in a big scratch figure; crop afterwards.
    # We set dpi=100 so 1 matplotlib unit = 1 px.
    fig = plt.figure(figsize=(12, 2), dpi=100)
    fig.patch.set_alpha(0.0)
    weight = "bold" if bold else "normal"
    txt = fig.text(0, 1, latex, fontsize=fontsize, color=color,
                   ha="left", va="top", weight=weight)
    # Draw once so the text has an extent we can measure.
    fig.canvas.draw()
    bbox = txt.get_window_extent()

    # Target SVG size in inches. pad_inches="tight" below will crop further,
    # but we set figure size roughly to text size for efficiency.
    pad_in = 0.02
    w_in = (bbox.width / fig.dpi) + 2 * pad_in
    h_in = (bbox.height / fig.dpi) + 2 * pad_in
    fig.set_size_inches(w_in, h_in)

    # Re-anchor: put the text at y=<h_in>-pad so it sits at the top of the figure
    txt.set_position((pad_in / w_in, 1 - pad_in / h_in))

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight",
                pad_inches=pad_in, transparent=True)
    plt.close(fig)
    svg_full = buf.getvalue().decode("utf-8")

    # Parse viewBox to learn width/height
    vb = _VIEWBOX_RE.search(svg_full)
    if vb is None:
        raise RuntimeError(
            f"matplotlib did not emit a viewBox for latex: {latex!r}")
    _, _, w_px, h_px = (float(v) for v in vb.groups())

    # Strip everything up to and including the opening <svg ...> tag
    m = _SVG_OPEN_RE.search(svg_full)
    if m is None:
        raise RuntimeError("matplotlib did not emit an <svg> tag")
    inner = svg_full[m.end():]
    inner = _SVG_CLOSE_RE.sub("", inner)
    return inner, w_px, h_px


# ---------------------------------------------------------------------------
# Math element
# ---------------------------------------------------------------------------

class Math(Element):
    """A LaTeX-typeset mathematical expression.

    Parameters
    ----------
    latex : str
        A matplotlib-mathtext expression, wrapped in ``$...$`` if not already.
        Plain-text portions outside dollar signs are rendered as regular text.
    size : str or float
        Semantic font size token or explicit px value.  Paper default is
        ``"label"`` (~10 px).
    color : str
        Semantic colour name or hex.
    bold : bool
        Use a bold font variant.
    scale : float
        Post-measurement scale multiplier (useful for small adjustments without
        stepping to the next semantic size).
    """

    def __init__(self, latex: str, *,
                 size: Union[str, float] = "math",
                 color: str = "text",
                 bold: bool = False,
                 scale: float = 1.0):
        if not (latex.startswith("$") and latex.endswith("$")):
            # Assume the whole thing is math; wrap for user convenience
            self.latex = f"${latex}$"
        else:
            self.latex = latex
        self.size = size
        self.color = color
        self.bold = bold
        self.scale = scale
        self._cached: Optional[Tuple[str, float, float, float]] = None

    # measurement -----------------------------------------------------------

    def _fetch(self, theme: Theme) -> Tuple[str, float, float]:
        fs = theme.size_px(self.size) * self.scale
        col = theme.color_of(self.color)
        inner, w_px, h_px = _render_math_svg(self.latex, float(fs), col, self.bold)
        return inner, w_px, h_px

    def measure(self, theme: Theme) -> BBox:
        inner, w, h = self._fetch(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        inner, w, h = self._fetch(theme)
        # Wrap the matplotlib-emitted group in our own translate.
        canvas.raw(
            f'<g transform="translate({x:.3f} {y:.3f})" '
            f'class="sciviz-math">'
            f'{inner}'
            f'</g>'
        )