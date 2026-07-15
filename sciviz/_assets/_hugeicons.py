"""Hugeicons stroke-rounded free icon bank (lazy-loaded from bundled SVGs).

Source: `hugeicons.com <https://hugeicons.com/icons/stroke-rounded>`_, free
tier, distributed under MIT via the official ``@hugeicons/core-free-icons``
npm package. Unlike :mod:`sciviz._assets._lucide` (path data baked directly
into a Python dict), this bank ships ~5,500 standalone ``.svg`` files under
``hugeicons/icons/`` plus a ``hugeicons/manifest.json`` keyword/description
index (see ``hugeicons/README.md``). Shapes are parsed from disk and cached
on first use rather than loaded eagerly at import time.

Each icon may mix ``path``, ``circle``, ``rect``, and ``ellipse`` elements
(unlike Lucide's path-only icons) and may vary ``stroke-width`` and
``opacity`` per shape. :class:`sciviz.Icon` resolves ``stroke="currentColor"``
/ ``fill="currentColor"`` against the requested icon color at render time.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

HUGEICONS_VIEWBOX = (0.0, 0.0, 24.0, 24.0)

_HERE = Path(__file__).parent
_ICONS_DIR = _HERE / "hugeicons" / "icons"
_MANIFEST_PATH = _HERE / "hugeicons" / "manifest.json"

Shape = Tuple[str, Tuple[Tuple[str, str], ...]]


@lru_cache(maxsize=1)
def hugeicons_names() -> Tuple[str, ...]:
    """All icon names available in the bank, sorted."""
    if not _ICONS_DIR.is_dir():
        return ()
    return tuple(sorted(p.stem for p in _ICONS_DIR.glob("*.svg")))


@lru_cache(maxsize=1)
def _name_set() -> frozenset:
    return frozenset(hugeicons_names())


def has_hugeicon(name: str) -> bool:
    return name in _name_set()


@lru_cache(maxsize=1)
def hugeicons_manifest() -> Dict[str, dict]:
    """The keyword/description manifest, keyed by icon name.

    Returns ``{}`` if the manifest hasn't been generated yet -- the SVG
    bank and manifest are independent artifacts of the same fetch pipeline.
    """
    if not _MANIFEST_PATH.exists():
        return {}
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def search_hugeicons(query: str, limit: int = 20) -> Tuple[str, ...]:
    """Substring-match ``query`` against names and manifest keywords/tags.

    A small in-process convenience for interactive lookup; authoring
    workflows should generally search ``manifest.json`` directly since it
    also carries descriptions and categories.
    """
    q = query.lower().strip()
    if not q:
        return ()
    manifest = hugeicons_manifest()
    hits = []
    for name in hugeicons_names():
        haystack = [name]
        entry = manifest.get(name)
        if entry:
            haystack.extend(entry.get("keywords", ()))
            haystack.append(entry.get("description", ""))
            haystack.append(entry.get("category") or "")
        if any(q in h.lower() for h in haystack):
            hits.append(name)
            if len(hits) >= limit:
                break
    return tuple(hits)


@lru_cache(maxsize=512)
def load_hugeicon_shapes(name: str) -> Tuple[Shape, ...]:
    """Parse ``<name>.svg`` into an immutable ``(tag, (attrs...))`` tuple.

    Raises :class:`KeyError` for unknown names so callers (namely
    :class:`sciviz.Icon`) can present a single unified error message.
    """
    path = _ICONS_DIR / f"{name}.svg"
    if not path.exists():
        raise KeyError(name)
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    shapes = []
    for el in root:
        tag = re.sub(r"^\{[^}]*\}", "", el.tag)
        shapes.append((tag, tuple(sorted(el.attrib.items()))))
    return tuple(shapes)
