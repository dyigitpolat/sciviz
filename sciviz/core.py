"""Core infrastructure for sciviz.

This module defines the four foundational types:

* :class:`Theme`   -- opinionated visual tokens (colors, type, spacing).
* :class:`BBox`    -- a simple (width, height) bounding box.
* :class:`Canvas`  -- an SVG accumulator with primitive drawing helpers.
* :class:`Element` -- the base class every drawable inherits from.

The layout contract is deliberately small:

    size = element.measure(theme)           # returns BBox(w, h)
    element.render(canvas, x, y, theme)     # draws *inside* (x, y, x+w, y+h)

Every element promises to keep its drawing inside the box it reported. That
is the single invariant that lets parent containers (:class:`Row`, :class:`Column`,
:class:`Panel`, ...) compose children without any overlap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

@dataclass
class Theme:
    """Visual tokens for a sciviz diagram.

    Defaults target a *paper* aesthetic: white background, thin strokes,
    sharp corners, compact typography.  For a "slides" look (rounded
    panels, saturated colours, loose spacing) call ``Theme.slides()``.

    Authors rarely touch these fields directly -- they use semantic names
    like ``size="label"`` or ``color="highlight"`` which are resolved to
    the values here.
    """

    # -- surfaces -----------------------------------------------------------
    bg: str = "#ffffff"
    bg_panel: str = "#ffffff"
    bg_subtle: str = "#f6f7f9"
    border: str = "#9ca3af"           # darker, more visible in print
    border_strong: str = "#4b5563"
    grid: str = "#6b7280"

    # -- semantic colors (muted paper palette) -----------------------------
    primary: str = "#1e3a8a"          # dark navy
    primary_fill: str = "#3b5fa0"     # slightly darker than slide blue
    primary_soft: str = "#dbe3f1"
    accent: str = "#134e4a"           # deep teal
    accent_fill: str = "#2d7a70"
    accent_soft: str = "#c7e5df"
    highlight: str = "#991b1b"        # dark red
    highlight_fill: str = "#b91c1c"
    highlight_soft: str = "#fde8e8"
    warning: str = "#92400e"
    warning_fill: str = "#b45309"

    # -- named paper accents (for architecture diagrams: paper-faithful) --
    # These are the saturated-but-paper-safe pastels that architecture
    # figures like DeepSeek-V3 use for "processing" (yellow/gold) and
    # "shared" (green) families.  Using semantic tokens lets a future
    # theme recolor an entire figure by swapping these values.
    accent_proc: str = "#fbe5a8"       # saturated butter yellow
    accent_shared: str = "#c1e1c1"     # saturated soft green
    # Soft dusty blue-gray for dashed module bounding boxes.
    panel_soft: str = "#c0cbd7"
    # Dark-enough gray for "Shared"-style connector labels.
    muted_label: str = "#475569"

    # -- text --------------------------------------------------------------
    text: str = "#0b1220"             # near-black, high contrast
    text_muted: str = "#374151"       # darker muted for print readability
    text_light: str = "#4b5563"
    text_faint: str = "#6b7280"
    text_inverse: str = "#ffffff"

    # -- disabled ----------------------------------------------------------
    disabled_fill: str = "#e5e7eb"
    disabled_stroke: str = "#9ca3af"
    disabled_text: str = "#6b7280"

    # -- typography --------------------------------------------------------
    # A neutral sans family for labels, with serif math via the Math element.
    font_family: str = "'Helvetica Neue', Helvetica, Arial, sans-serif"
    font_mono: str = "'Inconsolata', 'Menlo', 'Consolas', monospace"
    font_serif: str = "'Computer Modern Serif', 'Latin Modern Roman', 'Times New Roman', serif"

    font_title: float = 15.0
    font_subtitle: float = 11.0
    font_panel_title: float = 11.0
    font_panel_tag: float = 11.0
    font_section: float = 10.0
    font_label: float = 10.0
    font_small: float = 9.0
    font_tiny: float = 8.0
    font_micro: float = 6.5           # precision/metadata subscripts
    font_math: float = 11.0           # math labels beside boxes -- slightly
                                      # larger than a plain "label" so LaTeX
                                      # glyphs read proportionally with the
                                      # box label they flank

    # -- spacing -----------------------------------------------------------
    unit: float = 6.0                 # base spacing unit (tighter for paper)
    panel_padding: float = 12.0
    panel_radius: float = 1.5         # near-sharp corners
    diagram_margin: float = 16.0

    # -- stroke weights (all diagrams default to hairlines) ---------------
    hairline: float = 0.6
    line: float = 0.9
    thick: float = 1.3
    connector: float = 1.6   # arrows / connectors / flow lines

    # -- palettes (paper-appropriate: desaturated, print-safe) ------------
    sequential_blues: List[str] = field(default_factory=lambda: [
        "#f4f6fb", "#e1e8f3", "#c8d4e9", "#a7bad8",
        "#7f99c2", "#5b7bb0", "#3d619b", "#264a82",
    ])
    sequential_emeralds: List[str] = field(default_factory=lambda: [
        "#f0f9f6", "#d6ebe3", "#b6dacc", "#8cc1ae",
        "#60a38c", "#3d846f", "#28665a", "#184b44",
    ])
    sequential_ambers: List[str] = field(default_factory=lambda: [
        "#fdf8ed", "#f8edd0", "#f2dfa8", "#e9cb78",
        "#d6ae4b", "#b98b2f", "#936a22", "#6b4c18",
    ])
    sequential_grays: List[str] = field(default_factory=lambda: [
        "#ffffff", "#eceef1", "#d5d9df", "#b6bcc6",
        "#8e96a4", "#6b7383", "#4a5363", "#2a3141",
    ])
    diverging: List[str] = field(default_factory=lambda: [
        "#6b1917", "#b04040", "#e08585", "#f3c2c2",
        "#f6f6f6",
        "#c2d2eb", "#7f9dcf", "#3f62a3", "#1c3670",
    ])
    categorical: List[str] = field(default_factory=lambda: [
        "#3b5fa0", "#2d7a70", "#b45309", "#6d28d9",
        "#991b1b", "#0e7490", "#be185d", "#44403c",
    ])

    # ---------------- class factories -------------------------------------

    @classmethod
    def slides(cls) -> "Theme":
        """Return a version of the theme tuned for slides (rounded, saturated)."""
        return cls(
            bg="#fafbfc",
            border="#e2e8f0",
            border_strong="#cbd5e1",
            primary="#1e40af", primary_fill="#3b82f6",
            accent="#065f46", accent_fill="#10b981",
            highlight="#b91c1c", highlight_fill="#dc2626",
            panel_radius=8.0,
            panel_padding=20.0,
            unit=8.0,
            diagram_margin=32.0,
            font_title=22.0, font_subtitle=13.0,
            font_panel_title=14.0, font_panel_tag=13.0,
            font_label=11.0, font_small=10.0, font_tiny=9.0,
            line=1.0, thick=1.5,
        )

    # ---------------- API -------------------------------------------------

    def with_overrides(self, **kwargs) -> "Theme":
        """Return a copy of this theme with selected fields replaced."""
        from dataclasses import replace
        return replace(self, **kwargs)

    # semantic size name -> px
    _SIZE_MAP = {
        "title": "font_title",
        "subtitle": "font_subtitle",
        "panel": "font_panel_title",
        "section": "font_section",
        "label": "font_label",
        "small": "font_small",
        "tiny": "font_tiny",
        "micro": "font_micro",
        "math": "font_math",
    }

    def size_px(self, size: Union[str, float]) -> float:
        """Resolve a semantic size name (``"label"``) or a raw px value to px."""
        if isinstance(size, (int, float)):
            return float(size)
        attr = self._SIZE_MAP.get(size, "font_label")
        return float(getattr(self, attr))

    # semantic color name -> hex
    _COLOR_MAP = {
        "text": "text", "dark": "text",
        "muted": "text_muted", "light": "text_light", "faint": "text_faint",
        "inverse": "text_inverse", "white": "text_inverse",
        "primary": "primary", "primary_fill": "primary_fill",
        "accent": "accent", "accent_fill": "accent_fill",
        "highlight": "highlight", "highlight_fill": "highlight_fill",
        "warning": "warning", "warning_fill": "warning_fill",
        "border": "border", "grid": "grid", "disabled": "disabled_text",
    }

    def color_of(self, name) -> str:
        """Resolve a color spec to a hex string.

        Accepts:
          * ``None``                                  -> ``"none"``
          * a :class:`sciviz.palette.ColorRef`        -> resolved against this theme
          * literal hex (``"#..."``, ``"none"``, ``"rgb(...)"``) -> pass-through
          * semantic alias in :attr:`_COLOR_MAP`       (``"muted"``, ``"highlight"``, ...)
          * named role in :attr:`_ROLE_PALETTE`        (``"blue"``, ``"red"``, ...)
          * direct theme attribute                     (``"highlight_soft"``, ``"bg_panel"``, ...)
          * unknown string -> pass-through
        """
        if name is None:
            return "none"
        # Late import to avoid cycle (palette imports nothing from core)
        from .palette import ColorRef, resolve_color
        if isinstance(name, ColorRef):
            return resolve_color(name, self)
        if not isinstance(name, str):
            raise TypeError(f"color_of expects str|ColorRef|None, got {type(name).__name__}")
        if name.startswith("#") or name == "none" or name.startswith("rgb"):
            return name
        attr = self._COLOR_MAP.get(name)
        if attr is not None:
            return getattr(self, attr)
        # named role -> palette-aware fill
        if name in self._ROLE_PALETTE:
            return self._ROLE_PALETTE[name]
        if hasattr(self, name):
            val = getattr(self, name)
            if isinstance(val, str):
                return val
        return name

    # role -> (fill, soft_fill, stroke, text_on_fill)
    # Authors say `color="red"` and the theme picks coordinated, paper-safe shades.
    @property
    def _ROLE_PALETTE(self):
        return {
            "blue":   "#3b5fa0",
            "green":  "#2d7a70",
            "amber":  "#b45309",
            "purple": "#6d28d9",
            "red":    "#991b1b",
            "teal":   "#0e7490",
            "pink":   "#be185d",
            "gray":   "#44403c",
            # warm/cool semantic aliases
            "warm":   "#b45309",
            "cool":   "#3b5fa0",
            "neutral": "#44403c",
            # Palette semantic roles -- so theme.color_of("alert") etc. work
            "alert":    "#b91c1c",
            "success":  "#2d7a70",
            "info":     "#3b5fa0",
            "warn":     "#b45309",
            "emphasis": "#1e3a8a",
            "accent":   "#134e4a",
        }

    def role(self, name: str, variant: str = "fill") -> str:
        """Get a coordinated color from a named role.

        Variants:
          - "fill"    -- saturated fill suitable for shapes with white text
          - "soft"    -- pale tint suitable as background
          - "stroke"  -- darker variant suitable for borders
          - "ink"     -- text-friendly variant (darkest)

        Examples
        --------
        >>> theme.role("red", "fill")    # "#991b1b"
        >>> theme.role("red", "soft")    # "#fde8e8"
        >>> theme.role("blue", "ink")    # "#1e3a8a"
        """
        if name == "auto":
            # caller should resolve "auto" via :meth:`role_for_index`
            return self._ROLE_PALETTE["blue"]
        base = self._ROLE_PALETTE.get(name)
        if base is None:
            return self.color_of(name)
        if variant == "fill":
            return base
        if variant == "stroke" or variant == "ink":
            return self._darken(base, 0.30)
        if variant == "soft":
            return self._lighten(base, 0.85)
        return base

    def role_for_index(self, i: int) -> str:
        """Return the i-th role name (cycled).  Used to assign auto colors."""
        names = ["blue", "green", "amber", "purple", "red", "teal", "pink", "gray"]
        return names[i % len(names)]

    @staticmethod
    def _hex_to_rgb(c: str):
        c = c.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    @staticmethod
    def _rgb_to_hex(r, g, b):
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    @classmethod
    def _darken(cls, c: str, t: float) -> str:
        r, g, b = cls._hex_to_rgb(c)
        r, g, b = (max(0, v * (1 - t)) for v in (r, g, b))
        return cls._rgb_to_hex(r, g, b)

    @classmethod
    def _lighten(cls, c: str, t: float) -> str:
        r, g, b = cls._hex_to_rgb(c)
        r, g, b = (min(255, v + (255 - v) * t) for v in (r, g, b))
        return cls._rgb_to_hex(r, g, b)

    @staticmethod
    def is_light(hex_color: str) -> bool:
        """Return True if color is light enough to need dark text on top."""
        if not hex_color.startswith("#"):
            return True
        c = hex_color.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            return True
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return L > 0.58

    def text_on(self, fill: str) -> str:
        """Return the appropriate text color for placement on top of ``fill``."""
        return self.text if self.is_light(fill) else self.text_inverse

    # semantic gap tokens -> px
    _GAP_MAP = {
        "none": 0.0, "xs": 0.5, "sm": 1.0, "md": 1.75,
        "lg": 3.0, "xl": 4.5, "2xl": 6.5, "3xl": 10.0,
    }

    def gap_px(self, gap: Union[str, float]) -> float:
        """Resolve ``"lg"``-style gap to px, multiples of :attr:`unit`."""
        if isinstance(gap, (int, float)):
            return float(gap)
        return self._GAP_MAP.get(gap, 2.0) * self.unit

    # approximate text width (used for layout; actual width depends on renderer)
    _WIDE = set("MWm%&@—")
    _NARROW = set(".,;:'!|il1[](){}")

    def text_width(self, s: str, size: Union[str, float], bold: bool = False) -> float:
        """Conservative estimate of rendered text width in px.

        This is an *approximation* — real width depends on the installed font.
        It is tuned slightly large so layouts stay safe even with wider fonts.
        """
        if s is None or s == "":
            return 0.0
        sz = self.size_px(size)
        factor = 0.59 if bold else 0.56
        base = len(s) * sz * factor
        base += sum(sz * 0.18 for c in s if c in self._WIDE)
        base -= sum(sz * 0.22 for c in s if c in self._NARROW)
        return max(base, 4.0)

    def text_height(self, size: Union[str, float]) -> float:
        """Vertical footprint (ascender + descender + gutter) of one text line."""
        return self.size_px(size) * 1.25

    # color-scale helpers
    _PALETTE_MAP = {
        "blues": "sequential_blues",
        "emeralds": "sequential_emeralds",
        "ambers": "sequential_ambers",
        "grays": "sequential_grays",
        "diverging": "diverging",
    }

    def palette(self, name: str) -> List[str]:
        attr = self._PALETTE_MAP.get(name, "sequential_blues")
        return getattr(self, attr)

    def color_scale(self, value: float, palette: str = "blues",
                    vmin: float = 0.0, vmax: float = 1.0) -> str:
        """Map a scalar to a color in the named palette (clamped to [vmin, vmax])."""
        scale = self.palette(palette)
        if vmax == vmin:
            t = 0.5
        else:
            t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
        idx = int(round(t * (len(scale) - 1)))
        return scale[idx]


DEFAULT_THEME = Theme()


# ---------------------------------------------------------------------------
# BBox
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Simple (width, height) pair. All sciviz elements measure to this."""
    w: float
    h: float

    def expand(self, *, dx: float = 0, dy: float = 0) -> "BBox":
        return BBox(self.w + dx, self.h + dy)


# ---------------------------------------------------------------------------
# Canvas  (raw SVG emitter)
# ---------------------------------------------------------------------------

def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def _fmt(v: float) -> str:
    """Compact float formatting for SVG attributes."""
    if isinstance(v, int):
        return str(v)
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}"


class Canvas:
    """Minimal SVG accumulator.

    Elements call the drawing primitives (:meth:`rect`, :meth:`line`,
    :meth:`text`, ...) which append stringified SVG to an internal buffer.
    The :class:`Diagram` serialises the buffer at export time.

    Arrowhead markers and similar shared definitions are registered on the
    canvas via :meth:`define_marker`; each unique ``(name, color)`` pair is
    only emitted once.
    """

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
        self._defs.append(
            f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="{_fmt(size)}" markerHeight="{_fmt(size)}" '
            f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
        return mid

    # Arrowhead size in pixels = ARROW_HEAD_SCALE * stroke_width.
    # 4.5 gives small, neat heads that read as line terminators at the
    # default 0.9 px stroke (~4 px head) while still scaling up for
    # thick connectors -- matching the tight arrowheads in paper figures.
    ARROW_HEAD_SCALE: float = 4.5

    def define_arrow_marker(self, *, color: str, stroke_width: float,
                            name_hint: str = "arrow") -> str:
        """Register an arrowhead sized to the stroke width.

        The marker width / height scale linearly with ``stroke_width``,
        bounded to a sensible minimum so sub-pixel strokes still get a
        visible (but still small) head.  Use this for every arrow drawn
        via :meth:`Canvas.line` / :meth:`Canvas.path` so heads read as
        line terminators, not filled triangles.
        """
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
        """Render text.  ``y`` is the baseline position."""
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
        self._body.append(f"<text {' '.join(parts)}>{_xml_escape(content)}</text>")

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
            f"<text {' '.join(parts)}>{_xml_escape(base)}"
            f'<tspan font-size="{_fmt(size*0.72)}" baseline-shift="sub">'
            f'{_xml_escape(sub)}</tspan></text>'
        )

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


# ---------------------------------------------------------------------------
# Element base class
# ---------------------------------------------------------------------------

class Element:
    """Base class for every sciviz drawable.

    Subclasses must implement :meth:`measure` and :meth:`render`.  They must
    guarantee that ``render(canvas, x, y)`` only paints inside the rectangle
    ``(x, y, x + w, y + h)`` where ``(w, h) == measure()``.  This single
    invariant is what makes composition safe.

    Two optional hooks let containers do smarter alignment:

    * :meth:`content_bbox` returns the *inner* content rectangle (inset
      from the outer measure bbox) expressed in the element's local frame
      as ``(x0, y0, w, h)``.  Containers like :class:`Row` use this to
      align children on their content centre, not on their outer bbox.
      The default implementation reports the full measure bbox, i.e. no
      inset.  Elements that add out-of-band spacing (e.g. :class:`Anchor`
      margins) override this to exclude that spacing.

    * :attr:`primary_anchor` is an optional ``(offset_x, width)`` pair in
      the element's local frame identifying the sub-region that should
      be treated as the "anchor" when centering.  Composites like
      :class:`Labeled` expose the source element here so a :class:`Grid`
      cell centers the source on the column axis and lets the trailing
      label flow freely into the inter-cell gap.  ``None`` means the
      element has no special anchor and should be centered as a whole.
    """

    # Elements whose layout should be driven by an inner sub-region rather
    # than their full bbox override this to return ``(offset_x, width)``
    # (or a 4-tuple ``(x, y, w, h)``).  The default is None.
    primary_anchor = None

    def measure(self, theme: Theme) -> BBox:  # pragma: no cover - abstract
        raise NotImplementedError(
            f"{type(self).__name__} must implement measure(theme)")

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:  # pragma: no cover - abstract
        raise NotImplementedError(
            f"{type(self).__name__} must implement render(canvas, x, y, theme)")

    def content_bbox(self, theme: Theme) -> "tuple[float, float, float, float]":
        """Return the element's inner content rectangle in its local frame.

        The tuple is ``(x, y, w, h)`` where ``(0, 0)`` is the top-left of
        the rectangle reported by :meth:`measure`.  Default is the whole
        measure bbox.
        """
        b = self.measure(theme)
        return (0.0, 0.0, b.w, b.h)

    def primary_anchor_bbox(self, theme: Theme) -> "Optional[tuple[float, float, float, float]]":
        """Return the primary anchor region ``(x, y, w, h)`` in local coords.

        When an element has an internal sub-region that should drive cell
        centering (e.g. the source box inside a :class:`Labeled`), it
        overrides this method.  Default returns ``None``.
        """
        return None
