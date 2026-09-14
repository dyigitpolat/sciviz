"""Theme: opinionated visual tokens (colors, typography, spacing).

Defaults target a *paper* aesthetic: white background, thin strokes,
sharp corners, compact typography. For a "slides" look (rounded panels,
saturated colours, loose spacing) call :meth:`Theme.slides`.

Authors rarely touch the fields directly -- they use semantic names
like ``size="label"`` or ``color="highlight"`` which are resolved to
the values here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Union


@dataclass
class Theme:
    """Visual tokens for a sciviz diagram."""

    # -- surfaces -----------------------------------------------------------
    bg: str = "#ffffff"
    bg_panel: str = "#ffffff"
    bg_subtle: str = "#f6f7f9"
    border: str = "#9ca3af"
    border_strong: str = "#4b5563"
    grid: str = "#6b7280"

    # -- semantic colors (muted paper palette) -----------------------------
    primary: str = "#1e3a8a"
    primary_fill: str = "#3b5fa0"
    primary_soft: str = "#dbe3f1"
    accent: str = "#134e4a"
    accent_fill: str = "#2d7a70"
    accent_soft: str = "#c7e5df"
    highlight: str = "#991b1b"
    highlight_fill: str = "#b91c1c"
    highlight_soft: str = "#fde8e8"
    warning: str = "#92400e"
    warning_fill: str = "#b45309"

    # -- named paper accents (for architecture diagrams: paper-faithful) --
    # Saturated-but-paper-safe pastels that architecture figures use for
    # "processing" (yellow/gold) and "shared" (green) families.
    accent_proc: str = "#fbe5a8"
    accent_shared: str = "#c1e1c1"
    # A grouping surface, not a data encoding. Keep it near-paper-white so
    # nested panels preserve contrast hierarchy instead of becoming a large
    # blue-gray visual mass.
    panel_soft: str = "#eef1f5"
    muted_label: str = "#475569"

    # -- text --------------------------------------------------------------
    text: str = "#0b1220"
    text_muted: str = "#374151"
    text_light: str = "#4b5563"
    text_faint: str = "#6b7280"
    text_inverse: str = "#ffffff"
    # A same-colour stroke painted under every glyph, as a fraction of that
    # run's font size: a synthetic semibold for families that ship Regular and
    # Bold with nothing between. Bold is already the structural tier (titles,
    # headers, lane labels), so it cannot also serve as "a little heavier";
    # this token thickens every tier by the same proportion instead, which
    # darkens small running text without disturbing the weight hierarchy.
    # ``0.0`` disables it and is the default: it is a document-level choice.
    # Useful values are small -- around 0.01 to 0.015 of the font size.
    text_stroke_ratio: float = 0.0

    # -- disabled ----------------------------------------------------------
    disabled_fill: str = "#e5e7eb"
    disabled_stroke: str = "#9ca3af"
    disabled_text: str = "#6b7280"

    # -- typography --------------------------------------------------------
    # A neutral sans family for labels, with serif math via the Math element.
    # The stack includes symbol-rich fallbacks ('DejaVu Sans',
    # 'Lucida Sans Unicode', 'Apple Symbols') so mathematical symbols
    # render even when the primary sans face does not cover the needed
    # Unicode range. PNG export uses resvg which performs glyph-level
    # fallback through this stack automatically.
    font_family: str = ("'Helvetica Neue', Helvetica, Arial, "
                        "'DejaVu Sans', 'Lucida Sans Unicode', "
                        "'Apple Symbols', sans-serif")
    font_mono: str = ("'Inconsolata', 'Menlo', 'Consolas', "
                      "'DejaVu Sans Mono', monospace")
    font_serif: str = "'Computer Modern Serif', 'Latin Modern Roman', 'Times New Roman', serif"

    font_title: float = 15.0
    font_subtitle: float = 11.0
    font_panel_title: float = 11.0
    font_panel_tag: float = 11.0
    font_section: float = 10.0
    font_label: float = 10.0
    font_small: float = 9.0
    font_tiny: float = 8.0
    # ``micro`` follows the same 1pt ladder as label/small/tiny: at the
    # old 6.5pt it printed as by far the least legible text in a paper
    # figure while every sibling token stayed comfortably readable.
    font_micro: float = 7.0
    font_math: float = 11.0

    # -- spacing -----------------------------------------------------------
    unit: float = 6.0
    panel_padding: float = 12.0
    panel_radius: float = 1.5
    diagram_margin: float = 16.0
    # Default word-wrap budget for wrap-enabled labels (``Box(wrap=True)``)
    # in multiples of :attr:`unit`. The diagram width-fitter may compress
    # this token independently once the spacing-density floor is reached:
    # re-wrapping labels onto more lines narrows the figure without
    # touching font sizes or paddings.
    wrap_budget: float = 16.0
    # -- stroke weights (all diagrams default to hairlines) ---------------
    hairline: float = 0.6
    line: float = 0.9
    thick: float = 1.3
    # Connectors should read as relationships, not as a second set of box
    # borders.  A modest step above ``line`` survives print reduction while
    # keeping dense workflows calm.
    connector: float = 1.15

    # Fixed arrowhead marker size keeps every arrow in a diagram visually
    # consistent regardless of which connector primitive draws it.
    arrow_size: float = 3.6

    # Shaft left visible behind an arrowhead, as a multiple of the head's
    # own length. An arrowhead drawn on a stub no longer than itself
    # reads as a triangle glued to the border rather than as an arrow
    # arriving somewhere; connectors reserve head + this much shaft at
    # every end that carries a marker.
    arrow_shaft_ratio: float = 0.8

    # A caption corridor may not out-measure the nodes it separates.
    # Upright text reading along its wire is the legible form and is
    # worth opening a corridor for -- but only up to this fraction of
    # the narrower neighbouring node. Past it the caption is turned
    # across the wire instead, which costs the corridor nothing. This is
    # the knob that produces a MIX: short hand-off captions read along
    # their arrows, long ones step aside, and neither choice is made by
    # hand.
    caption_corridor_ratio: float = 0.35

    # Connector caption size token. Routed-flow labels read at this size;
    # dense multi-panel overview figures may override it down one step
    # (e.g. "tiny") so edge captions stay subordinate to node labels.
    connector_label_size: str = "small"

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

    # -- automatic-contrast bg stack ---------------------------------------
    # Render-time-only state: containers that paint a coloured fill push
    # their resolved bg hex onto this stack before rendering their body
    # and pop it after. Text rendering consults the stack and auto-swaps
    # "white" -> "text" when the current bg is light, so authors writing
    # ``color="white"`` inside a soft-fill Card no longer end up with
    # invisible text.
    _bg_stack: List[str] = field(default_factory=list)

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
            arrow_size=5.0,
        )

    # ---------------- API -------------------------------------------------

    def with_overrides(self, **kwargs) -> "Theme":
        """Return a copy of this theme with selected fields replaced."""
        from dataclasses import replace
        return replace(self, **kwargs)

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

    @property
    def arrow_head_px(self) -> float:
        """Length an arrowhead occupies along its shaft.

        SVG marker units are stroke widths, so the drawn head is the
        marker size times the connector's stroke weight. Deriving it
        here keeps the geometry in one place: a theme that grows its
        arrows automatically grows the stubs that must carry them.
        """
        return float(self.arrow_size) * float(self.connector)

    @property
    def arrow_stub_px(self) -> float:
        """Shortest endpoint stub on which an arrow still reads as one.

        The head plus a visible run of shaft behind it. Routers use this
        as the floor for their perpendicular stubs, and bus spines use
        it as the minimum clearance from the edge they arrow into.
        """
        return self.arrow_head_px * (1.0 + max(0.0, self.arrow_shaft_ratio))

    def size_px(self, size: Union[str, float]) -> float:
        """Resolve a semantic size name (``"label"``) or a raw px value to px."""
        if isinstance(size, (int, float)):
            return float(size)
        attr = self._SIZE_MAP.get(size, "font_label")
        return float(getattr(self, attr))

    _COLOR_MAP = {
        "text": "text", "dark": "text", "ink": "text",
        "muted": "text_muted", "light": "text_light", "faint": "text_faint",
        "inverse": "text_inverse", "white": "text_inverse",
        "primary": "primary", "primary_fill": "primary_fill",
        "accent": "accent", "accent_fill": "accent_fill",
        "highlight": "highlight", "highlight_fill": "highlight_fill",
        "warning": "warning", "warning_fill": "warning_fill",
        # Semantic positive / negative / warning shortcuts: resolve to
        # coordinated role colours (deep ink shade) that pair with the
        # existing soft/fill families.  ``positive = accent (emerald)``,
        # ``negative = highlight (red)``, ``warning = amber``.
        "positive": "accent",
        "negative": "highlight",
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

        If the requested colour resolves to white (``text_inverse``) but
        the current rendering context's background is light, the call
        auto-corrects to the dark text colour. This silently rescues
        ``color="white"`` placed inside a soft-fill Card body (or
        anywhere similar). See :meth:`push_bg` / :meth:`pop_bg`.
        """
        if name is None:
            return "none"
        # Late import avoids a cycle (palette imports nothing from core).
        from ..palette import ColorRef, resolve_color
        if isinstance(name, ColorRef):
            return resolve_color(name, self)
        if not isinstance(name, str):
            raise TypeError(f"color_of expects str|ColorRef|None, got {type(name).__name__}")
        if name.startswith("#") or name == "none" or name.startswith("rgb"):
            return self._auto_contrast(name)
        attr = self._COLOR_MAP.get(name)
        if attr is not None:
            return self._auto_contrast(getattr(self, attr))
        if name in self._ROLE_PALETTE:
            return self._auto_contrast(self._ROLE_PALETTE[name])
        if hasattr(self, name):
            val = getattr(self, name)
            if isinstance(val, str):
                return self._auto_contrast(val)
        return name

    def paint_of(self, name) -> str:
        """Resolve a shape fill/stroke without text auto-contrast.

        ``color_of`` is intentionally context-sensitive so legacy
        ``Text(color="white")`` remains readable when moved into a light
        container. Shape paint must never use that correction: a white box
        inside a pale card is still a white box, not dark text ink.
        """
        if name is None:
            return "none"
        from ..palette import ColorRef, resolve_color
        if isinstance(name, ColorRef):
            return resolve_color(name, self)
        if not isinstance(name, str):
            raise TypeError(
                f"paint_of expects str|ColorRef|None, got {type(name).__name__}"
            )
        if name.startswith("#") or name == "none" or name.startswith("rgb"):
            return name
        attr = self._COLOR_MAP.get(name)
        if attr is not None:
            return getattr(self, attr)
        if name in self._ROLE_PALETTE:
            return self._ROLE_PALETTE[name]
        if hasattr(self, name):
            val = getattr(self, name)
            if isinstance(val, str):
                return val
        return name

    # ---------------- automatic contrast helpers --------------------------

    def push_bg(self, color) -> None:
        """Push the resolved bg colour for the current render container.

        Card / Region / Banner call this just before rendering their
        body so that text colour resolution can detect a light fill.
        """
        if color is None:
            return
        try:
            hex_str = self.paint_of(color) if isinstance(color, str) \
                else self._resolve_for_bg(color)
        except Exception:  # pragma: no cover -- defensive
            return
        if hex_str and hex_str != "none":
            self._bg_stack.append(hex_str)

    def pop_bg(self) -> None:
        """Pop the current bg context (no-op if the stack is empty)."""
        if self._bg_stack:
            self._bg_stack.pop()

    def current_bg(self) -> str | None:
        """The top-of-stack rendered background, or ``None`` if unset."""
        return self._bg_stack[-1] if self._bg_stack else None

    def _resolve_for_bg(self, color) -> str:
        """Resolve a non-string colour spec for bg-tracking purposes."""
        from ..palette import ColorRef, resolve_color
        if isinstance(color, ColorRef):
            return resolve_color(color, self)
        return ""

    @staticmethod
    def _luminance(hex_str: str) -> float:
        """Approximate relative luminance in [0, 1] of an ``#rrggbb`` str."""
        if not hex_str.startswith("#") or len(hex_str) not in (4, 7):
            return 0.5  # unknown -> assume mid-luminance
        if len(hex_str) == 4:
            r = int(hex_str[1] * 2, 16)
            g = int(hex_str[2] * 2, 16)
            b = int(hex_str[3] * 2, 16)
        else:
            r = int(hex_str[1:3], 16)
            g = int(hex_str[3:5], 16)
            b = int(hex_str[5:7], 16)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0

    def is_light(self, hex_str: str, *, threshold: float = 0.55) -> bool:
        """True if the colour is too light to print white text on."""
        return self._luminance(hex_str) >= threshold

    def contrast_text(self, color) -> str:
        """Return ``text_inverse`` or ``text`` such that text is readable
        on the given background colour."""
        hex_str = self.paint_of(color) if isinstance(color, str) \
            else self._resolve_for_bg(color)
        return self.text_inverse if not self.is_light(hex_str) else self.text

    def _auto_contrast(self, hex_str: str) -> str:
        """Swap ``text_inverse`` to dark when the current bg is light.

        Only triggers when the resolved hex matches ``text_inverse``
        exactly; explicit ``"#fafafa"`` or arbitrary lighter pastels are
        left alone so authors who deliberately set a near-white colour
        still get what they asked for.
        """
        if not self._bg_stack:
            return hex_str
        if hex_str.lower() != self.text_inverse.lower():
            return hex_str
        if self.is_light(self.current_bg() or ""):
            return self.text
        return hex_str

    # role -> coordinated paper-safe shade. Authors say ``color="red"``
    # and the theme picks coordinated fills.
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
            "warm":   "#b45309",
            "cool":   "#3b5fa0",
            "neutral": "#44403c",
            "alert":    "#b91c1c",
            "success":  "#2d7a70",
            "info":     "#3b5fa0",
            "warn":     "#b45309",
            "emphasis": "#1e3a8a",
            "accent":   "#134e4a",
            "positive": "#2d7a70",
            "negative": "#b91c1c",
            "warning":  "#b45309",
        }

    def role(self, name: str, variant: str = "fill") -> str:
        """Get a coordinated color from a named role.

        Variants:
          - "fill"    -- saturated fill suitable for shapes with white text
          - "soft"    -- pale tint suitable as background
          - "stroke"  -- darker variant suitable for borders
          - "ink"     -- text-friendly variant (darkest)
        """
        if name == "auto":
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
        """Return the i-th role name (cycled). Used to assign auto colors."""
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

    _GAP_MAP = {
        "none": 0.0, "xs": 0.5, "sm": 1.0, "md": 1.75,
        "lg": 3.0, "xl": 4.5, "2xl": 6.5, "3xl": 10.0,
    }

    def gap_px(self, gap: Union[str, float]) -> float:
        """Resolve ``"lg"``-style gap to px, multiples of :attr:`unit`."""
        if isinstance(gap, (int, float)):
            return float(gap)
        return self._GAP_MAP.get(gap, 2.0) * self.unit

    def wrap_budget_px(self) -> float:
        """Pixel budget for one wrapped label line (see :attr:`wrap_budget`)."""
        return self.unit * self.wrap_budget

    _WIDE = set("MWm%&@—")
    _NARROW = set(".,;:'!|il1[](){}")

    def text_width(self, s: str, size: Union[str, float], bold: bool = False) -> float:
        """Rendered text width in px, weight-aware.

        Measured with the actual glyph advance widths of the resolved
        theme font (the same files the PNG/PDF exporters embed and
        outline), selecting the real bold face for ``bold=True`` -- so
        centering stays symmetric instead of bold labels overflowing
        their measured box. Falls back to a per-character heuristic when
        no usable font is available.
        """
        if s is None or s == "":
            return 0.0
        sz = self.size_px(size)
        from ._fonts import measure_text_width
        measured = measure_text_width(s, sz, self.font_family, bold=bold)
        if measured is not None:
            return max(measured, 4.0)
        factor = 0.59 if bold else 0.56
        base = len(s) * sz * factor
        base += sum(sz * 0.18 for c in s if c in self._WIDE)
        base -= sum(sz * 0.22 for c in s if c in self._NARROW)
        return max(base, 4.0)

    def text_height(self, size: Union[str, float]) -> float:
        """Vertical footprint (ascender + descender + gutter) of one text line."""
        return self.size_px(size) * 1.25

    def text_ink_extents(self, size: Union[str, float]) -> Tuple[float, float]:
        """Ink reach (above, below) the baseline for one line of text.

        The exact reservation an element must make for text it is about
        to draw -- :meth:`text_height` is the *layout* footprint of a
        line (it includes the inter-line gutter), which is smaller than
        the glyph box above the baseline. Shares its constants with
        :meth:`Canvas.text`'s ink accounting.
        """
        from ._canvas import TEXT_INK_ASCENT, TEXT_INK_DESCENT
        px = self.size_px(size)
        return px * TEXT_INK_ASCENT, px * TEXT_INK_DESCENT

    def wrap_lines(self, s: str, size: Union[str, float], max_width: float,
                   bold: bool = False) -> List[str]:
        """Greedy word-wrap of ``s`` into lines no wider than ``max_width``.

        Measured with :meth:`text_width`, so the result respects the real
        font the exporters embed. Explicit newlines are honoured as hard
        breaks. A word wider than ``max_width`` claims a line of its own
        rather than being split mid-word, so callers that own a hard
        width budget must re-measure the returned lines and grow their
        own box for the overflow -- the wrap never silently truncates.
        """
        if not s:
            return []
        lines: List[str] = []
        for paragraph in s.splitlines():
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                trial = f"{current} {word}"
                if self.text_width(trial, size, bold=bold) <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

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
