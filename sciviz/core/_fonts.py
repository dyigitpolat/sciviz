"""Font assets and PDF-safe text export helpers.

The SVG path is live text with an embedded ``@font-face`` rule.  PDF export
uses a font-aware converter when available and falls back to outlining text
before handing the SVG to CairoSVG, because CairoSVG cannot be relied on to
honour embedded fonts consistently across machines.
"""

from __future__ import annotations

import base64
import functools
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _weight_is_bold(weight) -> bool:
    """Classify a CSS ``font-weight`` value as bold (>= 600)."""
    if weight is None:
        return False
    w = str(weight).strip().lower()
    if w in {"bold", "bolder"}:
        return True
    try:
        return float(w) >= 600.0
    except ValueError:
        return False


def _style_is_italic(style) -> bool:
    return str(style).strip().lower() in {"italic", "oblique"}


@dataclass(frozen=True)
class FontAsset:
    """A font file known to sciviz."""

    name: str
    css_family: str
    ttf_path: Path
    woff2_path: Optional[Path] = None
    weight_range: str = "100 900"
    # Face classification: which requested (weight, style) this file serves.
    bold: bool = False
    italic: bool = False

    @property
    def svg_path(self) -> Path:
        return self.woff2_path if self.woff2_path is not None else self.ttf_path

    @property
    def svg_format(self) -> str:
        if self.woff2_path is not None:
            return "woff2"
        suffix = self.ttf_path.suffix.lower()
        if suffix == ".otf":
            return "opentype"
        return "truetype"

    @property
    def mime(self) -> str:
        if self.woff2_path is not None:
            return "font/woff2"
        if self.ttf_path.suffix.lower() == ".otf":
            return "font/otf"
        return "font/ttf"

    @property
    def embeddable(self) -> bool:
        """Whether this face is suitable for SVG ``@font-face`` embedding."""
        if self.woff2_path is not None:
            return True
        return self.ttf_path.suffix.lower() in {".ttf", ".otf"}


class FontRegistry:
    """Registry of fonts used by SVG/PDF exporters."""

    def __init__(self, fonts: list[FontAsset]):
        if not fonts:
            raise ValueError("FontRegistry requires at least one FontAsset")
        self.fonts = list(fonts)

    @classmethod
    def default(cls, font_family: Optional[str] = None) -> "FontRegistry":
        """Return the built-in font registry.

        Resolve the theme's family stack first so older figures keep their
        intended typography. Fall back to matplotlib's bundled DejaVu Sans.

        Beyond the regular face, the bold / italic / bold-italic variants
        of the resolved family are registered too (when they exist as
        distinct font files), so exports select real faces per text weight
        and style instead of silently flattening everything to regular.
        """
        resolved = cls._resolve_family(font_family)
        if resolved is None:
            font_path = cls._dejavu_path()
            css_family = "DejaVu Sans"
        else:
            font_path, css_family = resolved
        if font_path is None or not font_path.is_file():
            raise RuntimeError(
                "Could not locate a usable font. sciviz PDF-safe export "
                "requires matplotlib font data or a system font."
            )
        variants = cls._variant_paths(css_family, font_path)
        has_bold = (True, False) in variants or (True, True) in variants
        fonts: list[FontAsset] = []
        for (bold, italic), path in variants.items():
            if has_bold:
                weight_range = "600 900" if bold else "100 500"
            else:
                weight_range = "100 900"
            fonts.append(FontAsset(
                name=path.stem.replace(" ", "-").lower(),
                css_family=css_family,
                ttf_path=path,
                weight_range=weight_range,
                bold=bold,
                italic=italic,
            ))
        return cls(fonts)

    @classmethod
    def _variant_paths(cls, css_family: str,
                       regular_path: Path) -> "dict[tuple[bool, bool], Path]":
        """Map ``(bold, italic)`` to the distinct font files of a family.

        The regular face is always present. Variant lookups that fail or
        alias back to an already-registered file are skipped, so a family
        shipping only one file degrades to the previous single-face
        behaviour.
        """
        variants: dict[tuple[bool, bool], Path] = {(False, False): regular_path}
        try:
            from matplotlib import font_manager
            from matplotlib.font_manager import FontProperties
        except Exception:
            return variants
        for bold, italic in ((True, False), (False, True), (True, True)):
            try:
                prop = FontProperties(
                    family=css_family,
                    weight="bold" if bold else "normal",
                    style="italic" if italic else "normal",
                )
                path = Path(font_manager.findfont(
                    prop, fallback_to_default=False,
                ))
            except Exception:
                continue
            if (not path.is_file()
                    or path.suffix.lower() not in {".ttf", ".otf", ".ttc"}):
                continue
            if any(path == known for known in variants.values()):
                continue
            variants[(bold, italic)] = path
        return variants

    @staticmethod
    def _family_candidates(font_family: Optional[str]) -> list[str]:
        if not font_family:
            return []
        out: list[str] = []
        for raw in font_family.split(","):
            name = raw.strip().strip("'\"")
            if not name or name.lower() in {"sans-serif", "serif", "monospace"}:
                continue
            out.append(name)
        return out

    @classmethod
    def _resolve_family(cls, font_family: Optional[str]) -> Optional[tuple[Path, str]]:
        if not font_family:
            return None
        try:
            from matplotlib import font_manager

            for family in cls._family_candidates(font_family):
                path = Path(font_manager.findfont(
                    family,
                    fallback_to_default=False,
                ))
                if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                    return path, family
        except Exception:
            return None
        return None

    @staticmethod
    def _dejavu_path() -> Optional[Path]:
        try:
            import matplotlib
            from matplotlib import font_manager

            root = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
            font_path = root / "DejaVuSans.ttf"
            if not font_path.is_file():
                font_path = Path(font_manager.findfont(
                    "DejaVu Sans", fallback_to_default=True
                ))
        except Exception:
            font_path = Path("__missing_sciviz_font__.ttf")
        if not font_path.is_file():
            repo_root = Path(__file__).resolve().parents[3]
            matches = list(repo_root.glob(
                "env/lib/python*/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
            ))
            if matches:
                font_path = matches[0]
        return font_path if font_path.is_file() else None

    @property
    def primary(self) -> FontAsset:
        return self.fonts[0]

    def face_for(self, weight="normal", style="normal") -> FontAsset:
        """The registered face closest to a CSS ``(weight, style)`` pair.

        Exact matches win; a weight match outranks a style match (dropping
        bold is far more visible in print than dropping the slant); the
        primary (regular) face is the final fallback.
        """
        want_bold = _weight_is_bold(weight)
        want_italic = _style_is_italic(style)
        best = self.fonts[0]
        best_score = -1
        for font in self.fonts:
            score = (2 * (font.bold == want_bold)
                     + (font.italic == want_italic))
            if score > best_score:
                best, best_score = font, score
        return best

    @property
    def root_font_family(self) -> str:
        families: list[str] = []
        for font in self.fonts:
            quoted = f'"{font.css_family}"'
            if quoted not in families:
                families.append(quoted)
        return ", ".join(families + ["sans-serif"])

    def css(self) -> str:
        rules = []
        for font in self.fonts:
            if not font.embeddable:
                continue
            data = base64.b64encode(font.svg_path.read_bytes()).decode("ascii")
            rules.append(
                "@font-face { "
                f"font-family: \"{font.css_family}\"; "
                f"src: url(data:{font.mime};base64,{data}) "
                f"format(\"{font.svg_format}\"); "
                f"font-weight: {font.weight_range}; "
                f"font-style: {'italic' if font.italic else 'normal'}; "
                "font-display: block; "
                "}"
            )
        return "\n".join(rules)


# ---------------------------------------------------------------------------
# Text measurement (shared by Theme.text_width)
# ---------------------------------------------------------------------------
# Layout code measures text constantly; both export renderers (resvg for
# PNG, the outline pass for PDF) resolve the same theme font stack, so
# measuring with the *actual* glyph advance widths of that font keeps
# centering symmetric for every weight. Results are cached at a reference
# size (advances scale linearly for scalable fonts).

_REF_SIZE = 100.0
_registry_cache: dict[str, Optional[FontRegistry]] = {}


def _registry_for(font_family: Optional[str]) -> Optional[FontRegistry]:
    key = font_family or ""
    if key not in _registry_cache:
        try:
            _registry_cache[key] = FontRegistry.default(font_family)
        except Exception:
            _registry_cache[key] = None
    return _registry_cache[key]


@functools.lru_cache(maxsize=None)
def _text_to_path():
    from matplotlib.textpath import TextToPath
    return TextToPath()


@functools.lru_cache(maxsize=65536)
def _ref_advance_width(text: str, fname: str) -> Optional[float]:
    """Advance width of ``text`` at ``_REF_SIZE`` pt in the given font file."""
    try:
        import warnings

        from matplotlib.font_manager import FontProperties

        prop = FontProperties(fname=fname, size=_REF_SIZE)
        with warnings.catch_warnings():
            # Codepoints outside the measuring face still advance (via
            # .notdef here, via resvg's glyph-level fallback at render
            # time); matplotlib's per-glyph warning is just noise.
            warnings.simplefilter("ignore")
            w, _h, _d = _text_to_path().get_text_width_height_descent(
                text, prop, False)
        return float(w)
    except Exception:
        return None


def measure_text_width(text: str, size_px: float,
                       font_family: Optional[str] = None, *,
                       bold: bool = False,
                       italic: bool = False) -> Optional[float]:
    """Measured advance width of one text line in px, or ``None``.

    Uses the same font files the exporters embed/outline, selecting the
    face per requested weight and style. Returns ``None`` when no usable
    font (or matplotlib) is available so callers can fall back to a
    heuristic estimate.
    """
    if not text:
        return 0.0
    registry = _registry_for(font_family)
    if registry is None:
        return None
    face = registry.face_for("bold" if bold else "normal",
                             "italic" if italic else "normal")
    widths = []
    for line in text.split("\n"):
        w = _ref_advance_width(line, str(face.ttf_path)) if line else 0.0
        if w is None:
            return None
        widths.append(w)
    return max(widths) * (float(size_px) / _REF_SIZE)


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _float_attr(node: ET.Element, name: str, default: float) -> float:
    raw = node.attrib.get(name)
    if raw is None:
        return default
    m = re.match(r"[-+]?[0-9]*\.?[0-9]+", raw)
    return float(m.group(0)) if m else default


def _path_to_svg_d(path) -> str:
    from matplotlib.path import Path as MplPath

    parts: list[str] = []
    for vertices, code in path.iter_segments():
        if code == MplPath.MOVETO:
            x, y = vertices
            parts.append(f"M{x:.3f},{-y:.3f}")
        elif code == MplPath.LINETO:
            x, y = vertices
            parts.append(f"L{x:.3f},{-y:.3f}")
        elif code == MplPath.CURVE3:
            x1, y1, x2, y2 = vertices
            parts.append(f"Q{x1:.3f},{-y1:.3f} {x2:.3f},{-y2:.3f}")
        elif code == MplPath.CURVE4:
            x1, y1, x2, y2, x3, y3 = vertices
            parts.append(
                f"C{x1:.3f},{-y1:.3f} {x2:.3f},{-y2:.3f} "
                f"{x3:.3f},{-y3:.3f}"
            )
        elif code == MplPath.CLOSEPOLY:
            parts.append("Z")
    return " ".join(parts)


def outline_svg_text(svg_source: str, registry: Optional[FontRegistry] = None,
                     font_family: Optional[str] = None) -> str:
    """Replace live SVG text nodes with vector paths.

    This is a conservative fallback for PDF backends with unreliable font
    handling.  It intentionally targets the simple ``<text>`` emitted by
    :class:`Canvas`; complex rich text remains live.
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath, TextToPath

    registry = registry or FontRegistry.default(font_family)
    ttp = TextToPath()
    root = ET.fromstring(svg_source)

    def _prop(size, weight, style):
        # ``fname`` makes matplotlib bypass family/weight/style resolution
        # entirely, so the face must be picked here: registry.face_for
        # returns the bold / italic file matching the requested run style
        # instead of flattening every run onto the regular face.
        face = registry.face_for(weight, style)
        return FontProperties(fname=str(face.ttf_path), size=size)

    for parent in list(root.iter()):
        replacements: list[tuple[ET.Element, ET.Element]] = []
        for child in list(parent):
            if _strip_namespace(child.tag) != "text":
                continue
            text = "".join(child.itertext())
            if not text:
                continue

            size = _float_attr(child, "font-size", 11.0)
            x = _float_attr(child, "x", 0.0)
            y = _float_attr(child, "y", 0.0)
            weight = child.attrib.get("font-weight", "normal")
            style = child.attrib.get("font-style", "normal")
            fill = child.attrib.get("fill", "#0b1220")
            anchor = child.attrib.get("text-anchor", "start")
            baseline = child.attrib.get("dominant-baseline", "alphabetic")

            has_tspan = any(_strip_namespace(d.tag) == "tspan" for d in child)

            if not has_tspan:
                # ---- single plain run (unchanged behaviour) ----
                prop = _prop(size, weight, style)
                text_path = TextPath((0, 0), text, prop=prop, usetex=False)
                ext = text_path.get_extents()
                dx = -ext.x0
                if anchor == "middle":
                    dx = -(ext.x0 + ext.x1) / 2.0
                elif anchor == "end":
                    dx = -ext.x1
                dy = 0.0
                if baseline in {"central", "middle"}:
                    dy = (ext.y0 + ext.y1) / 2.0
                elif baseline == "hanging":
                    dy = ext.y1
                attrs = {
                    "d": _path_to_svg_d(text_path),
                    "fill": fill,
                    "transform": f"translate({x + dx:.3f},{y + dy:.3f})",
                }
                if "opacity" in child.attrib:
                    attrs["opacity"] = child.attrib["opacity"]
                if "transform" in child.attrib:
                    attrs["transform"] = child.attrib["transform"] + " " + attrs["transform"]
                replacements.append((child, ET.Element("path", attrs)))
                continue

            # ---- structured runs (tspans): outline each run so PDF backends
            # without per-glyph font fallback still render every codepoint.
            # Runs flow left-to-right by advance width; per-run fill / size /
            # weight / style and sub-baseline shifts are preserved.
            runs: list[tuple[str, float, str, str, str, float]] = []

            def _add(t, sz, wt, st, fl, dyshift):
                if t:
                    runs.append((t, sz, wt, st, fl, dyshift))

            _add(child.text or "", size, weight, style, fill, 0.0)
            for desc in child:
                if _strip_namespace(desc.tag) == "tspan":
                    t_sz = _float_attr(desc, "font-size", size)
                    t_wt = desc.attrib.get("font-weight", weight)
                    t_st = desc.attrib.get("font-style", style)
                    t_fl = desc.attrib.get("fill", fill)
                    shift = t_sz * 0.35 if desc.attrib.get("baseline-shift") == "sub" else 0.0
                    _add("".join(desc.itertext()), t_sz, t_wt, t_st, t_fl, shift)
                _add(desc.tail or "", size, weight, style, fill, 0.0)
            if not runs:
                continue

            widths = [ttp.get_text_width_height_descent(t, _prop(sz, wt, st), False)[0]
                      for (t, sz, wt, st, _fl, _dy) in runs]
            total = sum(widths)
            start = 0.0
            if anchor == "middle":
                start = -total / 2.0
            elif anchor == "end":
                start = -total

            # Vertical baseline alignment from the base-size metrics (matches
            # the single-run branch's intent).
            bext = TextPath((0, 0), "Ag", prop=_prop(size, weight, style),
                            usetex=False).get_extents()
            dy = 0.0
            if baseline in {"central", "middle"}:
                dy = (bext.y0 + bext.y1) / 2.0
            elif baseline == "hanging":
                dy = bext.y1

            group = ET.Element("g")
            if "transform" in child.attrib:
                group.set("transform", child.attrib["transform"])
            if "opacity" in child.attrib:
                group.set("opacity", child.attrib["opacity"])

            cursor = start
            for (t, sz, wt, st, fl, dyshift), w in zip(runs, widths):
                tp = TextPath((0, 0), t, prop=_prop(sz, wt, st), usetex=False)
                d = _path_to_svg_d(tp)
                if d:
                    group.append(ET.Element("path", {
                        "d": d, "fill": fl,
                        "transform": f"translate({x + cursor:.3f},{y + dy + dyshift:.3f})",
                    }))
                cursor += w
            replacements.append((child, group))

        for old, new in replacements:
            idx = list(parent).index(old)
            parent.remove(old)
            parent.insert(idx, new)

    return ET.tostring(root, encoding="unicode")
