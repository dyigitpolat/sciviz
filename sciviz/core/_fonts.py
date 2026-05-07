"""Font assets and PDF-safe text export helpers.

The SVG path is live text with an embedded ``@font-face`` rule.  PDF export
uses a font-aware converter when available and falls back to outlining text
before handing the SVG to CairoSVG, because CairoSVG cannot be relied on to
honour embedded fonts consistently across machines.
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FontAsset:
    """A font file known to sciviz."""

    name: str
    css_family: str
    ttf_path: Path
    woff2_path: Optional[Path] = None
    weight_range: str = "100 900"

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
        """
        font_path = cls._resolve_family(font_family)
        if font_path is None or not font_path.is_file():
            font_path = cls._dejavu_path()
        if font_path is None or not font_path.is_file():
            raise RuntimeError(
                "Could not locate a usable font. sciviz PDF-safe export "
                "requires matplotlib font data or a system font."
            )
        name = font_path.stem.replace(" ", "-").lower()
        return cls([
            FontAsset(
                name=name,
                css_family=f"sciviz-{font_path.stem}",
                ttf_path=font_path,
            )
        ])

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
    def _resolve_family(cls, font_family: Optional[str]) -> Optional[Path]:
        if not font_family:
            return None
        try:
            from matplotlib import font_manager

            for family in cls._family_candidates(font_family):
                path = Path(font_manager.findfont(
                    family,
                    fallback_to_default=False,
                ))
                if path.is_file() and path.suffix.lower() in {".ttf", ".otf"}:
                    return path
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

    @property
    def root_font_family(self) -> str:
        families = [f'"{font.css_family}"' for font in self.fonts]
        return ", ".join(families + ["sans-serif"])

    def css(self) -> str:
        rules = []
        for font in self.fonts:
            data = base64.b64encode(font.svg_path.read_bytes()).decode("ascii")
            rules.append(
                "@font-face { "
                f"font-family: \"{font.css_family}\"; "
                f"src: url(data:{font.mime};base64,{data}) "
                f"format(\"{font.svg_format}\"); "
                f"font-weight: {font.weight_range}; "
                "font-style: normal; "
                "font-display: block; "
                "}"
            )
        return "\n".join(rules)


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
    from matplotlib.textpath import TextPath

    registry = registry or FontRegistry.default(font_family)
    font = registry.primary
    root = ET.fromstring(svg_source)

    for parent in list(root.iter()):
        replacements: list[tuple[ET.Element, ET.Element]] = []
        for child in list(parent):
            if _strip_namespace(child.tag) != "text":
                continue
            text = "".join(child.itertext())
            if not text:
                continue
            if any(_strip_namespace(desc.tag) == "tspan" for desc in child):
                # Keep structured tspans live; these are rare in paper figures
                # and preserving them avoids accidental style loss.
                continue

            size = _float_attr(child, "font-size", 11.0)
            x = _float_attr(child, "x", 0.0)
            y = _float_attr(child, "y", 0.0)
            weight = child.attrib.get("font-weight", "normal")
            style = child.attrib.get("font-style", "normal")
            anchor = child.attrib.get("text-anchor", "start")
            baseline = child.attrib.get("dominant-baseline", "alphabetic")
            prop = FontProperties(fname=str(font.ttf_path), size=size,
                                  weight=weight, style=style)
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
            d = _path_to_svg_d(text_path)
            attrs = {
                "d": d,
                "fill": child.attrib.get("fill", "#0b1220"),
                "transform": f"translate({x + dx:.3f},{y + dy:.3f})",
            }
            if "opacity" in child.attrib:
                attrs["opacity"] = child.attrib["opacity"]
            if "transform" in child.attrib:
                attrs["transform"] = child.attrib["transform"] + " " + attrs["transform"]
            replacements.append((child, ET.Element("path", attrs)))

        for old, new in replacements:
            idx = list(parent).index(old)
            parent.remove(old)
            parent.insert(idx, new)

    return ET.tostring(root, encoding="unicode")
