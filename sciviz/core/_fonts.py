"""Font assets and PDF-safe text export helpers.

The SVG path is live text with an embedded ``@font-face`` rule.  PDF export
uses a font-aware converter when available and falls back to outlining text
before handing the SVG to CairoSVG, because CairoSVG cannot be relied on to
honour embedded fonts consistently across machines.

Outlining costs the text itself: glyph paths are vector and print perfectly,
but a reader cannot select, search or copy them, and neither can a screen
reader.  ``outline_svg_text(..., selectable=True)`` therefore keeps the
outlined paths as the *visible* layer and lays an all-but-transparent copy of
the original live ``<text>`` over them, so the PDF carries real text as well
as real curves.  See :func:`_selectable_shadow`.

That copy is laid out by the converter's own font, not by the outliner's, so
it is pinned to the outlined geometry character by character rather than left
to land where it may.  See :func:`_pin_shadow_geometry`.
"""

from __future__ import annotations

import base64
import copy
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
        """The first family in the stack that this machine actually has.

        A font stack is a FALLBACK LIST, so a name the system does not
        carry must fall through to the next name. ``findfont`` raises for a
        missing family, and catching that around the whole loop abandoned
        the rest of the stack: a theme naming one unavailable face first
        silently exported in DejaVu Sans, ignoring the very families the
        author listed behind it.
        """
        if not font_family:
            return None
        try:
            from matplotlib import font_manager
        except Exception:
            return None
        for family in cls._family_candidates(font_family):
            try:
                path = Path(font_manager.findfont(
                    family,
                    fallback_to_default=False,
                ))
            except Exception:
                continue
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                return path, family
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


@functools.lru_cache(maxsize=65536)
def _ref_char_offsets(text: str, fname: str) -> Optional[tuple]:
    """Pen offset of every character of ``text`` at ``_REF_SIZE`` pt.

    The companion of :func:`_ref_advance_width`: that one answers "how wide is
    this run", this one answers "where does each of its glyphs sit inside it".
    The outliner needs the second question answered to place the selectable
    layer on top of the glyphs it outlined (see :func:`_pin_shadow_geometry`),
    and it must be the SAME layout the outlined paths came from, kerning
    included -- matplotlib lays a ``TextPath`` out with this very function.

    Returns ``None`` when the layout cannot be obtained, so callers fall back
    to leaving the text where the renderer puts it.
    """
    if not text:
        return ()
    try:
        import warnings

        from matplotlib import _text_helpers
        from matplotlib.font_manager import get_font

        font = get_font(fname)
        # TextPath lays out at FONT_SCALE (== _REF_SIZE) and 72 dpi, then
        # scales by size / FONT_SCALE. Matching both keeps the offsets in the
        # same reference frame as _ref_advance_width.
        font.set_size(_REF_SIZE, 72)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            offsets = tuple(item.x for item in _text_helpers.layout(text, font))
        if len(offsets) == len(text):
            return offsets
    except Exception:
        pass
    # Fallback: prefix advances. These drop the kerning of the pair that
    # straddles each boundary -- a few thousandths of an em, far below the
    # error this whole mechanism exists to remove.
    out = [0.0]
    for i in range(1, len(text)):
        w = _ref_advance_width(text[:i], fname)
        if w is None:
            return None
        out.append(w)
    return tuple(out)


@functools.lru_cache(maxsize=256)
def _codepoints(font_path: str) -> frozenset:
    """Every codepoint the font file at ``font_path`` can draw."""
    try:
        from matplotlib.ft2font import FT2Font

        return frozenset(FT2Font(font_path).get_charmap().keys())
    except Exception:
        return frozenset()


@functools.lru_cache(maxsize=64)
def _fallback_families(font_family: Optional[str], weight_bold: bool,
                       style_italic: bool) -> tuple:
    """``(css_family, face_file)`` for the SECOND and later families in a stack.

    Both halves are needed and for different consumers: the outliner draws from
    the FILE, while text that stays live must NAME the family so the converter
    resolves the same face itself.
    """
    weight = "bold" if weight_bold else "normal"
    style = "italic" if style_italic else "normal"
    out = []
    try:
        from matplotlib import font_manager
        from matplotlib.font_manager import FontProperties
    except Exception:
        return ()
    for family in FontRegistry._family_candidates(font_family)[1:]:
        try:
            path = Path(font_manager.findfont(
                FontProperties(family=family, weight=weight, style=style),
                fallback_to_default=False,
            ))
        except Exception:
            continue
        if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            out.append((family, path))
    return tuple(out)


def _fallback_faces(font_family: Optional[str], weight_bold: bool,
                    style_italic: bool) -> tuple:
    """The face files of the SECOND and later families in a font stack.

    A theme's ``font_family`` is a stack precisely so a glyph the preferred
    face lacks can be drawn by the next one; live SVG and the resvg PNG
    exporter both honour that stack per glyph. This returns the same stack as
    outline-able font files so the PDF path can honour it too.
    """
    return tuple(path for _family, path
                 in _fallback_families(font_family, weight_bold, style_italic))


def _segment_by_coverage(text: str, primary: Path,
                         fallbacks: tuple) -> list:
    """Split ``text`` into maximal ``(substring, face)`` runs by coverage.

    Returns a single run on the primary face whenever the primary face covers
    everything, which is the overwhelmingly common case and the one that must
    stay byte-for-byte identical to the previous behaviour.
    """
    primary_cmap = _codepoints(str(primary))
    if not primary_cmap or all(ord(c) in primary_cmap for c in text):
        return [(text, primary)]

    def face_for_char(ch: str) -> Path:
        if ord(ch) in primary_cmap or ch in "\n\t":
            return primary
        for path in fallbacks:
            if ord(ch) in _codepoints(str(path)):
                return path
        return primary            # nothing covers it: keep the authored face

    runs: list = []
    for ch in text:
        face = face_for_char(ch)
        if runs and runs[-1][1] == face:
            runs[-1][0] += ch
        else:
            runs.append([ch, face])
    return [(t, f) for t, f in runs]


def measure_text_width(text: str, size_px: float,
                       font_family: Optional[str] = None, *,
                       bold: bool = False,
                       italic: bool = False) -> Optional[float]:
    """Measured advance width of one text line in px, or ``None``.

    Uses the same font files the exporters embed/outline, selecting the face
    per requested weight and style, and -- like them -- honouring the family
    stack per glyph. Measuring a mixed string against the preferred face alone
    charges every fallback glyph a ``.notdef`` advance instead of its real
    width, and layout then sizes the box for a character it is not going to
    draw: that is how "value ~= spike count / T" ended up overflowing its card
    while the same string outlined correctly. Returns ``None`` when no usable
    font (or matplotlib) is available so callers can fall back to a heuristic.
    """
    if not text:
        return 0.0
    registry = _registry_for(font_family)
    if registry is None:
        return None
    face = registry.face_for("bold" if bold else "normal",
                             "italic" if italic else "normal")
    fallbacks = _fallback_faces(font_family, bold, italic)
    widths = []
    for line in text.split("\n"):
        if not line:
            widths.append(0.0)
            continue
        total = 0.0
        for segment, seg_face in _segment_by_coverage(line, face.ttf_path,
                                                      fallbacks):
            w = _ref_advance_width(segment, str(seg_face))
            if w is None:
                return None
            total += w
        widths.append(total)
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


# ---------------------------------------------------------------------------
# The invisible text layer that gives an outlined PDF its text back
# ---------------------------------------------------------------------------
# Cairo composites in 8-bit alpha and drops anything that quantises to zero:
# a ``<text>`` at ``fill-opacity="0"`` (or ``fill="none"``, or ``opacity="0"``)
# is elided from the PDF entirely -- no glyphs, no font, nothing to select.
# 1/255 = 0.00392 is therefore the FLOOR, not a choice: the smallest alpha that
# survives the converter. It costs one grey level out of 255 on the page, which
# is below the reproduction threshold of any printer and of the eye, and it is
# painted directly over glyph paths of the same colour, so in practice it lands
# on ink that is already dark. 0.004 clears the floor with a margin against
# rounding without approaching visibility.
_SHADOW_FILL_OPACITY = "0.004"

# The shadow paints one colour and one colour only. It must NOT inherit the
# authored fill, because the authored fill is not guaranteed to be a colour a
# converter can parse: CairoSVG silently ABANDONS ``fill-opacity`` for a fill it
# cannot resolve (an unresolved palette token, ``currentColor``, a ``url(#...)``
# reference) and paints the run solid instead -- which would stamp every such
# label on the page at full strength. Pinning the colour makes the shadow
# invisible by construction rather than by luck. Which colour is immaterial at
# 1/255 alpha; black is the value every parser agrees on.
_SHADOW_FILL = "#000000"

# Attributes the shadow must NOT keep, and why each one would break it:
#   opacity          - multiplies fill-opacity, dragging it back under the
#                      1/255 floor (a 0.5-opacity note would vanish again).
#   fill, fill-opacity - the shadow sets its own; see ``_SHADOW_FILL``.
#   stroke-*         - the synthetic-semibold stroke (see
#                      ``Canvas.apply_text_stroke``) is painted at FULL opacity
#                      by CairoSVG, which would print the shadow in plain sight.
_SHADOW_DROP_ATTRS = ("opacity", "fill", "fill-opacity", "stroke-opacity",
                      "stroke-width", "stroke-linejoin", "paint-order")


def _family_segments(text: str, primary: Path, fallbacks: tuple) -> list:
    """Split ``text`` into ``(substring, css_family_or_None)`` runs.

    ``None`` means "the authored family already covers this"; a name means the
    run must say which family to use because the authored one cannot draw it.
    The sibling of :func:`_segment_by_coverage`, resolving to family NAMES for
    text that stays live rather than to files for text being outlined.
    """
    primary_cmap = _codepoints(str(primary))
    if not primary_cmap or all(ord(c) in primary_cmap for c in text):
        return [(text, None)]

    def family_for_char(ch: str) -> Optional[str]:
        if ord(ch) in primary_cmap or ch.isspace():
            return None
        for family, path in fallbacks:
            if ord(ch) in _codepoints(str(path)):
                return family
        return None               # nothing covers it: keep the authored family

    runs: list = []
    for ch in text:
        family = family_for_char(ch)
        if runs and runs[-1][1] == family:
            runs[-1][0] += ch
        else:
            runs.append([ch, family])
    return [(t, f) for t, f in runs]


def _ns_of(tag: str) -> str:
    """The ``{namespace}`` prefix of ``tag``, or ``""``."""
    return tag[:tag.index("}") + 1] if "}" in tag else ""


def _covers(path: Path, text: str) -> bool:
    """Whether the face at ``path`` can draw every non-space character."""
    cmap = _codepoints(str(path))
    if not cmap:
        return False
    return all(ch.isspace() or ord(ch) in cmap for ch in text)


def _carry_every_codepoint(shadow: ET.Element, registry: FontRegistry,
                           font_family: Optional[str],
                           pinned: bool = False) -> None:
    """Re-express the shadow so every character names a face that HAS it.

    The shadow is the only copy of the text left in the file, so a codepoint it
    fails to carry is a codepoint the reader cannot select, search or paste --
    the figure would print a "less than or equal" sign that copies as nothing.

    A converter with no glyph-level fallback resolves ONE face for a run and
    draws ``.notdef`` for anything outside it; a ``.notdef`` has no character
    behind it, so it reaches the text layer as a hole. The fix is the same
    family stack the outliner already honours, applied here by NAME: runs the
    preferred family cannot draw are wrapped in a ``<tspan>`` naming the first
    family in the stack that can. The glyph is then real, so the converter maps
    it back to its own codepoint and a paste lands the actual character.

    Nothing happens for text the preferred family covers, which is almost all
    of it -- that shadow stays exactly the structure the node already had.

    How a mixed node is expressed depends on whether the caller can pin the
    result to the outlined geometry (``pinned``):

    * Unpinned, the shadow is laid out by the converter, so being handed one
      run matters more than which family draws it: a centred or right-aligned
      label split into three pieces gets three INDEPENDENT alignments, and the
      text layer then reads back as "4096 Loihi: output edges <=" instead of
      the sentence that is printed. A single family that covers the whole node
      is therefore named on the node, and the split is the last resort.
    * Pinned, every character is placed explicitly, so a split cannot disturb
      alignment or reading order -- and splitting is then strictly better,
      because it leaves each covered run in the AUTHORED family, the very face
      the visible glyphs were outlined from. Re-flowing a whole label through a
      fallback family instead would shift every character off its own glyph by
      the difference between two type designs; small per character, and enough
      after a dozen of them for a text extractor to start reading word breaks
      inside words ("lat ency", "t asks").
    """
    weight = shadow.attrib.get("font-weight", "normal")
    style = shadow.attrib.get("font-style", "normal")

    whole = "".join(shadow.itertext())
    face = registry.face_for(weight, style)
    if not _codepoints(str(face.ttf_path)) or _covers(face.ttf_path, whole):
        return                    # authored family suffices (or is unreadable)
    if not pinned:
        for family, path in _fallback_families(font_family,
                                               _weight_is_bold(weight),
                                               _style_is_italic(style)):
            if _covers(path, whole):
                shadow.set("font-family", family)
                return

    # The text has to be split into per-family runs.

    # Flatten to (text, presentation attributes of the run that owns it).
    # Per-run size / weight / style must survive: they drive the converter's
    # cursor, and a shadow that advances differently from the ink it covers
    # would hand the reader a selection that does not track the words.
    runs: list = []

    def _add(text, attrs):
        if text:
            runs.append((text, attrs))

    _add(shadow.text, {})
    for child in list(shadow):
        if _strip_namespace(child.tag) == "tspan":
            _add("".join(child.itertext()), dict(child.attrib))
        _add(child.tail, {})

    split: list = []
    needs_fallback = False
    for text, attrs in runs:
        run_weight = attrs.get("font-weight", weight)
        run_style = attrs.get("font-style", style)
        face = registry.face_for(run_weight, run_style)
        fallbacks = _fallback_families(font_family,
                                       _weight_is_bold(run_weight),
                                       _style_is_italic(run_style))
        for segment, family in _family_segments(text, face.ttf_path, fallbacks):
            seg_attrs = dict(attrs)
            if family is not None:
                seg_attrs["font-family"] = family
                needs_fallback = True
            split.append((segment, seg_attrs))

    if not needs_fallback:
        return

    ns = _ns_of(shadow.tag)
    shadow.text = None
    for child in list(shadow):
        shadow.remove(child)
    for segment, attrs in split:
        tspan = ET.SubElement(shadow, f"{ns}tspan", attrs)
        tspan.text = segment


# ---------------------------------------------------------------------------
# Pinning the shadow to the ink it shadows
# ---------------------------------------------------------------------------
# ``xml:space``. With the default ("default") a converter COLLAPSES runs of
# spaces and trims the ends of a text element, so the character stream it lays
# out is not the character stream the outliner measured, and every explicit
# position after the first collapsed space addresses the wrong character.
# "preserve" keeps the two streams in step; it changes nothing else here,
# because every character is positioned explicitly anyway.
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _fmt_positions(values) -> str:
    return " ".join(f"{v:.3f}" for v in values)


def _wrap_tails(node: ET.Element) -> None:
    """Move every tail into an explicit ``<tspan>``, in place.

    Text between two ``<tspan>``s (or after the last one) is a *tail* in the
    XML tree, and a tail is not an element, so it cannot carry an attribute.
    A converter that needs a per-run position therefore has nowhere to read one
    from -- and sciviz emits tails routinely, since a run with no styling of
    its own is written as bare text. Wrapping each tail in an attribute-less
    ``<tspan>`` changes no inherited property and makes every run addressable.
    """
    ns = _ns_of(node.tag)
    for el in list(node.iter()):
        kids = list(el)
        for kid in kids:
            if not kid.tail:
                continue
            idx = list(el).index(kid)
            holder = ET.Element(f"{ns}tspan")
            holder.text = kid.tail
            kid.tail = None
            el.insert(idx + 1, holder)


def _pin_shadow_geometry(shadow: ET.Element, positions: list) -> None:
    """Place every shadow character where its outlined glyph actually sits.

    The shadow is laid out by the CONVERTER, using whatever face the converter
    resolves for the named family, while the visible glyphs were laid out by
    the outliner using the font file it opened itself. The two faces are never
    guaranteed to be the same file: a family name can span several optical
    sizes, a converter may synthesise a weight the outliner had a real face
    for, and a run carrying a codepoint the authored family lacks is shadowed
    in a fallback family whose metrics are simply a different design. Whenever
    they differ the shadow advances at its own rate and drifts off the ink:
    the selection highlight a reader drags across a label ends short of the
    word, and an anchored label starts inside it.

    Explicit per-character positions remove the renderer's metrics from the
    answer entirely. Each character is placed at the x its own outlined glyph
    occupies, so the shadow starts where the ink starts, ends where the ink
    ends, and tracks it in between whatever face the converter chose. The
    anchor is spent in computing those positions (an absolutely positioned
    character is its own text chunk, which a renderer would otherwise re-anchor
    one character at a time), so the shadow is re-anchored to ``start``.

    ``textLength`` with ``lengthAdjust="spacingAndGlyphs"`` is the mechanism
    the SVG spec offers for exactly this constraint, and it is deliberately NOT
    used, because it does not survive contact with the renderers. CairoSVG,
    which produces the PDF, does not implement it at all. resvg does, per text
    CHUNK -- and absolute per-character positions make every character its own
    chunk, so each glyph is stretched to the width of the whole label, the
    copies pile up, and 0.4% alpha accumulates into a visible smear (measured:
    36/255 on a figure that is otherwise within 1/255). Positions are the
    portable statement of the same constraint.
    """
    if not positions or len("".join(shadow.itertext())) != len(positions):
        # One position per character or nothing: a list that has slipped out of
        # step with the characters would place them worse than the renderer's
        # own metrics do.
        return
    _wrap_tails(shadow)
    # Positions are absolute, so the anchor has already been applied.
    shadow.set("text-anchor", "start")
    shadow.set(_XML_SPACE, "preserve")
    # The whole list on the root: per SVG it addresses the element's characters
    # including those inside descendants, which is the only way to position a
    # run that a converter has flattened.
    shadow.set("x", _fmt_positions(positions))

    def walk(el: ET.Element, i: int) -> int:
        """Give each run the slice of ``positions`` addressing its characters.

        Every element is descended into so the index keeps step with
        ``itertext()``, but only a ``<tspan>`` is given coordinates: it is the
        one element whose position means "put these characters here".
        """
        start = i
        if el.text:
            i += len(el.text)
        for kid in el:
            i = walk(kid, i)
            if kid.tail:
                i += len(kid.tail)
        if el is not shadow and i > start \
                and _strip_namespace(el.tag) == "tspan":
            el.set("x", _fmt_positions(positions[start:i]))
        return i

    walk(shadow, 0)


def _selectable_shadow(node: ET.Element,
                       registry: Optional[FontRegistry] = None,
                       font_family: Optional[str] = None,
                       positions: Optional[list] = None) -> ET.Element:
    """An all-but-transparent copy of a live ``<text>`` node.

    The copy keeps baseline, transform, font size, weight and style, so the
    converter lays its glyphs down where the visible outlined glyphs already
    are and a selection rectangle tracks the printed word. It paints
    essentially nothing (see ``_SHADOW_FILL_OPACITY``), so the visible layer
    stays exactly the outlined paths that were reviewed and approved.

    Given a ``registry``, it also guarantees that every codepoint is carried by
    a face that can draw it -- see :func:`_carry_every_codepoint`.

    Given ``positions`` (one x per character of the node's text, in the
    coordinates the node itself uses), the copy is pinned to the geometry of
    the glyphs it covers instead of being re-laid-out by the converter -- see
    :func:`_pin_shadow_geometry`.
    """
    shadow = copy.deepcopy(node)
    for el in shadow.iter():
        for attr in _SHADOW_DROP_ATTRS:
            el.attrib.pop(attr, None)
        el.set("stroke", "none")
    shadow.set("fill", _SHADOW_FILL)
    shadow.set("fill-opacity", _SHADOW_FILL_OPACITY)
    # Never let the invisible layer intercept a click in an SVG viewer.
    shadow.set("pointer-events", "none")
    if registry is not None:
        _carry_every_codepoint(shadow, registry, font_family,
                               pinned=bool(positions))
    if positions is not None:
        _pin_shadow_geometry(shadow, positions)
    return shadow


def outline_svg_text(svg_source: str, registry: Optional[FontRegistry] = None,
                     font_family: Optional[str] = None, *,
                     selectable: bool = False) -> str:
    """Replace live SVG text nodes with vector paths.

    This is a conservative fallback for PDF backends with unreliable font
    handling.  It intentionally targets the simple ``<text>`` emitted by
    :class:`Canvas`; complex rich text remains live.

    Outlining resolves ONE face per run, so a codepoint the preferred family
    lacks used to outline as ``.notdef`` -- a tofu box in the PDF, while the
    live-text SVG and the resvg PNG of the same figure drew the glyph
    correctly from the next family in the stack. Runs are therefore segmented
    by coverage first, and each segment is outlined with the first face in the
    stack that can draw it. A run the preferred face covers entirely takes the
    original single-``TextPath`` path unchanged.

    ``selectable=True`` additionally lays an invisible copy of each replaced
    ``<text>`` node over its paths, so the exported PDF keeps selectable,
    searchable, copyable text without changing a single printed pixel. The
    visible layer is byte-for-byte the same outlined geometry either way.
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

    def _prop_file(path, size):
        return FontProperties(fname=str(path), size=size)

    def _path_of(text, prop):
        """``TextPath`` for ``text``, or ``None`` when it draws nothing.

        A coverage segment can be pure whitespace, and matplotlib's ``Path``
        raises on the empty vertex array a space-only string produces. Such a
        segment still ADVANCES the cursor, so it is skipped for ink only.
        """
        if not text.strip():
            return None
        try:
            return TextPath((0, 0), text, prop=prop, usetex=False)
        except Exception:
            return None

    def _segments(text, weight, style):
        """``(substring, face_path)`` runs honouring the family stack."""
        face = registry.face_for(weight, style)
        fallbacks = _fallback_faces(font_family, _weight_is_bold(weight),
                                    _style_is_italic(style))
        return _segment_by_coverage(text, face.ttf_path, fallbacks)

    def _segments_for(text, _size, weight, style):
        """``_segments`` with the size argument the run tuples carry."""
        return _segments(text, weight, style)

    def _offsets(text, face_path, size):
        """Per-character x offsets inside one run, at the run's own size.

        ``None`` when the layout is unavailable, which switches the selectable
        layer back to being positioned by the converter.
        """
        offs = _ref_char_offsets(text, str(face_path))
        if offs is None:
            return None
        k = float(size) / _REF_SIZE
        return [o * k for o in offs]

    def _extend(positions, offs, base):
        """Append one run's absolute positions; ``None`` poisons the list."""
        if positions is None or offs is None:
            return None
        positions.extend(base + o for o in offs)
        return positions

    def _stroke_attrs(node, run_fill, run_size, base_size):
        """Carry a live ``<text>``'s synthetic-semibold stroke onto its paths.

        The stroke is what makes a Regular face read a little heavier than
        Regular (see ``Canvas.apply_text_stroke``), so dropping it here would
        outline the PDF a whole weight lighter than the SVG and the PNG of the
        same figure. Outlined paths carry the glyph coordinates at the run's
        own size, in the same user units the ``<text>`` used, so the width
        transfers unchanged; it is only rescaled when a run overrides the
        element's font size, which is the case ``stroke-width`` inheritance on
        live text would get wrong anyway.
        """
        raw = node.attrib.get("stroke-width")
        if not raw or not run_fill:
            return {}
        try:
            width = float(raw)
        except ValueError:
            return {}
        if width <= 0.0:
            return {}
        if base_size > 0.0 and run_size > 0.0:
            width *= run_size / base_size
        return {"stroke": run_fill, "stroke-width": f"{width:.4f}",
                "stroke-linejoin": "round", "paint-order": "stroke"}

    for parent in list(root.iter()):
        # (replaced node, its outlined geometry, one x per character of the
        # node's text)
        replacements: list = []
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

            if not has_tspan and len(_segments(text, weight, style)) > 1:
                # ---- one run the preferred face cannot draw on its own ----
                # Lay the coverage segments out left to right by advance
                # width, exactly as the tspan branch does, so a fallback glyph
                # sits where the live-text SVG would put it.
                segs = _segments(text, weight, style)
                widths = [ttp.get_text_width_height_descent(
                    t, _prop_file(face, size), False)[0] for t, face in segs]
                total = sum(widths)
                cursor = 0.0
                if anchor == "middle":
                    cursor = -total / 2.0
                elif anchor == "end":
                    cursor = -total
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
                positions: Optional[list] = []
                for (t, face), w in zip(segs, widths):
                    positions = _extend(positions, _offsets(t, face, size),
                                        x + cursor)
                    tp = _path_of(t, _prop_file(face, size))
                    d = _path_to_svg_d(tp) if tp is not None else ""
                    if d:
                        attrs = {
                            "d": d, "fill": fill,
                            "transform": f"translate({x + cursor:.3f},{y + dy:.3f})",
                        }
                        attrs.update(_stroke_attrs(child, fill, size, size))
                        group.append(ET.Element("path", attrs))
                    cursor += w
                replacements.append((child, group, positions))
                continue

            if not has_tspan:
                # ---- single plain run ----
                # ONE coverage segment does not mean the PREFERRED face draws
                # it. A run made entirely of glyphs the preferred family lacks
                # -- a check mark, a half disc, a heavy cross, the marks a
                # matrix cell carries -- is a single segment on the FALLBACK
                # face, and outlining it with the preferred face draws nothing
                # at all (matplotlib raises on the empty vertex array such a
                # run produces). Take the face the coverage pass chose, which
                # is the preferred one whenever it covers the run, so this
                # branch is unchanged for every run that used to work.
                segs = _segments(text, weight, style)
                face_path = (segs[0][1] if segs
                             else registry.face_for(weight, style).ttf_path)
                prop = _prop_file(face_path, size)
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
                attrs.update(_stroke_attrs(child, fill, size, size))
                if "opacity" in child.attrib:
                    attrs["opacity"] = child.attrib["opacity"]
                if "transform" in child.attrib:
                    attrs["transform"] = child.attrib["transform"] + " " + attrs["transform"]
                positions = _extend([], _offsets(text, face_path, size), x + dx)
                replacements.append((child, ET.Element("path", attrs),
                                     positions))
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

            # A run's width is the sum of its coverage segments' widths, not
            # the width the preferred face alone would report: measuring a run
            # that contains a fallback glyph against the preferred face charges
            # that glyph a .notdef advance (and makes matplotlib warn), so the
            # run after it would be laid down in the wrong place.
            widths = [sum(ttp.get_text_width_height_descent(
                              seg_t, _prop_file(seg_face, sz), False)[0]
                          for seg_t, seg_face in _segments_for(t, sz, wt, st))
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
            positions = []
            for (t, sz, wt, st, fl, dyshift), w in zip(runs, widths):
                # A styled run may itself mix covered and uncovered glyphs, so
                # each one is segmented against the family stack too.
                for seg_t, seg_face in _segments_for(t, sz, wt, st):
                    positions = _extend(positions,
                                        _offsets(seg_t, seg_face, sz),
                                        x + cursor)
                    tp = _path_of(seg_t, _prop_file(seg_face, sz))
                    d = _path_to_svg_d(tp) if tp is not None else ""
                    if d:
                        attrs = {
                            "d": d, "fill": fl,
                            "transform": f"translate({x + cursor:.3f},{y + dy + dyshift:.3f})",
                        }
                        attrs.update(_stroke_attrs(child, fl, sz, size))
                        group.append(ET.Element("path", attrs))
                    cursor += ttp.get_text_width_height_descent(
                        seg_t, _prop_file(seg_face, sz), False)[0]
            replacements.append((child, group, positions))

        for old, new, positions in replacements:
            idx = list(parent).index(old)
            parent.remove(old)
            parent.insert(idx, new)
            if selectable:
                # AFTER the paths: the shadow cannot obscure them at 0.4%
                # alpha, but keeping paint order "ink first, text second"
                # makes the layering explicit for anyone reading the SVG.
                parent.insert(idx + 1, _selectable_shadow(
                    old, registry, font_family, positions))

    return ET.tostring(root, encoding="unicode")
