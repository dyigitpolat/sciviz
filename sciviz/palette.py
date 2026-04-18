"""Semantic color resolution.

Instead of asking authors to type ``"#3b5fa0"`` or remember which hex code
matches the theme, the :class:`Palette` provides:

* **Semantic roles** -- ``Palette.alert``, ``Palette.success``, ``Palette.info``,
  ``Palette.warn``, ``Palette.neutral``, ``Palette.muted``.  Each is a
  :class:`ColorRef` that the renderer resolves against the active theme.
* **Named bases** -- ``Palette.red``, ``Palette.blue``, ``Palette.green``,
  etc., all theme-adjusted (paper-safe in the paper theme, more saturated
  in the slides theme).
* **Stable palette assignment** -- ``Palette.next("micro_batch_1")`` returns
  a color from the categorical palette, deterministically keyed on the
  given string.  All later requests for the same key get the same colour.
* **Tints / shades** -- ``Palette.alert.soft()``, ``Palette.blue.dark()``.

Concrete hex strings are still accepted everywhere a color is expected,
so this is purely additive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# ColorRef
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorRef:
    """A theme-resolvable color reference.

    A ``ColorRef`` has three resolution modes:

    1. ``role``   -- a semantic role ("alert", "success", "info", ...) that
                     resolves against the theme's role palette.
    2. ``named``  -- a named base hue ("red", "blue", "green", ...) that
                     resolves to the theme-adjusted version.
    3. ``literal`` -- an explicit hex string ("#3b5fa0") that passes through.

    Modifiers ``soft`` and ``dark`` produce derived references.
    """
    role: Optional[str] = None
    named: Optional[str] = None
    literal: Optional[str] = None
    variant: str = "fill"           # "fill" | "soft" | "dark" | "stroke"

    def soft(self) -> "ColorRef":
        return ColorRef(self.role, self.named, self.literal, "soft")

    def dark(self) -> "ColorRef":
        return ColorRef(self.role, self.named, self.literal, "dark")

    def stroke(self) -> "ColorRef":
        return ColorRef(self.role, self.named, self.literal, "stroke")

    def __post_init__(self):
        n = sum(x is not None for x in (self.role, self.named, self.literal))
        if n == 0:
            raise ValueError("ColorRef needs role, named, or literal")
        if n > 1:
            raise ValueError("ColorRef cannot mix role/named/literal")


# ---------------------------------------------------------------------------
# Palette namespace
# ---------------------------------------------------------------------------

class _PaletteMeta(type):
    """Class with both class-attribute color refs and a stateful next()."""

    # semantic roles
    @property
    def alert(cls):    return ColorRef(role="alert")
    @property
    def success(cls):  return ColorRef(role="success")
    @property
    def info(cls):     return ColorRef(role="info")
    @property
    def warn(cls):     return ColorRef(role="warn")
    @property
    def neutral(cls):  return ColorRef(role="neutral")
    @property
    def muted(cls):    return ColorRef(role="muted")
    @property
    def emphasis(cls): return ColorRef(role="emphasis")
    @property
    def accent(cls):   return ColorRef(role="accent")

    # named hues
    @property
    def red(cls):     return ColorRef(named="red")
    @property
    def orange(cls):  return ColorRef(named="orange")
    @property
    def amber(cls):   return ColorRef(named="amber")
    @property
    def yellow(cls):  return ColorRef(named="yellow")
    @property
    def green(cls):   return ColorRef(named="green")
    @property
    def teal(cls):    return ColorRef(named="teal")
    @property
    def cyan(cls):    return ColorRef(named="cyan")
    @property
    def blue(cls):    return ColorRef(named="blue")
    @property
    def indigo(cls):  return ColorRef(named="indigo")
    @property
    def violet(cls):  return ColorRef(named="violet")
    @property
    def purple(cls):  return ColorRef(named="purple")
    @property
    def pink(cls):    return ColorRef(named="pink")
    @property
    def gray(cls):    return ColorRef(named="gray")

    # Paper-faithful architecture accents (saturated pastels).  Each one
    # resolves via the theme so a future theme swap can recolor every
    # architecture diagram by changing a single value.
    @property
    def accent_proc(cls):   return ColorRef(named="accent_proc")
    @property
    def accent_shared(cls): return ColorRef(named="accent_shared")
    @property
    def panel_soft(cls):    return ColorRef(named="panel_soft")
    @property
    def muted_label(cls):   return ColorRef(named="muted_label")


class Palette(metaclass=_PaletteMeta):
    """Semantic colour API.

    Static usage:

        Palette.alert         # theme's "alert" role -> a paper-safe red
        Palette.success.soft()
        Palette.blue.dark()
        Palette.literal("#3b5fa0")

    Stable categorical assignment:

        Palette.next("worker_0")    # deterministic; returns same color
                                    # for the same key on later calls
    """

    @staticmethod
    def literal(hex_color: str) -> ColorRef:
        return ColorRef(literal=hex_color)

    # ----- stable palette assignment -----
    _key_to_idx: dict = {}
    _next_idx: int = 0

    @classmethod
    def next(cls, key: Optional[str] = None) -> ColorRef:
        """Return the next color from the categorical palette.

        If ``key`` is provided, the assignment is stable: the same key
        returns the same colour on all subsequent calls (within a process).
        """
        if key is not None and key in cls._key_to_idx:
            idx = cls._key_to_idx[key]
        else:
            idx = cls._next_idx
            cls._next_idx += 1
            if key is not None:
                cls._key_to_idx[key] = idx
        return ColorRef(role=f"_cat:{idx}")

    @classmethod
    def reset(cls):
        """Reset the categorical assignment counter (use between figures)."""
        cls._key_to_idx.clear()
        cls._next_idx = 0


# ---------------------------------------------------------------------------
# Resolver: ColorRef + Theme -> hex
# ---------------------------------------------------------------------------

# Paper-theme defaults for semantic roles.
_PAPER_ROLES = {
    "alert":    "#b91c1c",
    "success":  "#2d7a70",
    "info":     "#3b5fa0",
    "warn":     "#b45309",
    "neutral":  "#0b1220",
    "muted":    "#374151",
    "emphasis": "#1e3a8a",
    "accent":   "#134e4a",
}

# Slides-theme defaults
_SLIDES_ROLES = {
    "alert":    "#dc2626",
    "success":  "#10b981",
    "info":     "#3b82f6",
    "warn":     "#f59e0b",
    "neutral":  "#0f172a",
    "muted":    "#475569",
    "emphasis": "#1e40af",
    "accent":   "#065f46",
}

# Named hues, paper version (muted, print-safe)
_PAPER_NAMED = {
    "red":    "#b91c1c",
    "orange": "#c2410c",
    "amber":  "#b45309",
    "yellow": "#a16207",
    "green":  "#15803d",
    "teal":   "#0f766e",
    "cyan":   "#0e7490",
    "blue":   "#3b5fa0",
    "indigo": "#4338ca",
    "violet": "#6d28d9",
    "purple": "#7c3aed",
    "pink":   "#be185d",
    "gray":   "#4b5563",
    # Paper-faithful architecture accents.  Values are duplicated in
    # :class:`Theme` so both ``Theme.color_of("accent_proc")`` and
    # ``Palette.accent_proc`` resolve to the same hex.
    "accent_proc":   "#fbe5a8",
    "accent_shared": "#c1e1c1",
    "panel_soft":    "#c0cbd7",
    "muted_label":   "#475569",
}

# Named hues, slides version (more vivid)
_SLIDES_NAMED = {
    "red":    "#dc2626",
    "orange": "#ea580c",
    "amber":  "#f59e0b",
    "yellow": "#eab308",
    "green":  "#16a34a",
    "teal":   "#14b8a6",
    "cyan":   "#06b6d4",
    "blue":   "#3b82f6",
    "indigo": "#6366f1",
    "violet": "#8b5cf6",
    "purple": "#a855f7",
    "pink":   "#ec4899",
    "gray":   "#64748b",
    # slides overrides: richer saturation
    "accent_proc":   "#fcd34d",
    "accent_shared": "#86efac",
    "panel_soft":    "#94a3b8",
    "muted_label":   "#334155",
}

# Categorical palette (used by Palette.next()) for paper
_PAPER_CATEGORICAL = [
    "#3b5fa0", "#2d7a70", "#b45309", "#6d28d9",
    "#991b1b", "#0e7490", "#be185d", "#44403c",
    "#15803d", "#a16207", "#4338ca", "#7c3aed",
]


def _hex_to_rgb(s: str):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    """Linear interpolation in RGB space."""
    a = _hex_to_rgb(hex_a)
    b = _hex_to_rgb(hex_b)
    return _rgb_to_hex(*(a[i] * (1 - t) + b[i] * t for i in range(3)))


def _soft(hex_color: str) -> str:
    """Return a tint suitable for a fill behind text."""
    return _mix(hex_color, "#ffffff", 0.85)


def _dark(hex_color: str) -> str:
    """Return a darker shade suitable for a stroke or hover."""
    return _mix(hex_color, "#000000", 0.25)


def resolve_color(ref, theme) -> str:
    """Resolve any color spec (string, ColorRef, None) to a hex string.

    This is the single entry point used by every element when it needs
    to convert an author-supplied color value into a hex string for SVG.
    """
    if ref is None:
        return "none"
    if isinstance(ref, str):
        # could be a hex literal, a theme attribute name, or a legacy alias
        return theme.color_of(ref)
    if not isinstance(ref, ColorRef):
        raise TypeError(f"Color must be str, ColorRef, or None; got {type(ref)}")

    # active palette tables
    is_slides = (theme.bg == "#fafbfc" or getattr(theme, "_is_slides", False))
    role_table = _SLIDES_ROLES if is_slides else _PAPER_ROLES
    named_table = _SLIDES_NAMED if is_slides else _PAPER_NAMED
    cat_table = _PAPER_CATEGORICAL  # same in both themes

    if ref.literal is not None:
        base = ref.literal
    elif ref.role is not None:
        if ref.role.startswith("_cat:"):
            idx = int(ref.role.split(":")[1])
            base = cat_table[idx % len(cat_table)]
        else:
            base = role_table.get(ref.role, theme.text)
    else:  # named
        base = named_table.get(ref.named, theme.text)

    if ref.variant == "soft":
        return _soft(base)
    if ref.variant == "dark":
        return _dark(base)
    return base
