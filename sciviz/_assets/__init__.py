"""Static asset bundles shipped inside the :mod:`sciviz` package.

Two icon sources back :class:`sciviz.Icon`:

* :mod:`~sciviz._assets._lucide` -- a curated ~50-icon subset of
  `Lucide <https://lucide.dev>`_ (MIT-licensed), path data baked directly
  into a Python dict for zero-dependency rendering of common glyphs.
* :mod:`~sciviz._assets._hugeicons` -- a ~5,500-icon bank from
  `Hugeicons <https://hugeicons.com/icons/stroke-rounded>`_' free,
  MIT-licensed tier, lazy-loaded from bundled SVG files under
  ``hugeicons/icons/`` with a keyword/description index in
  ``hugeicons/manifest.json`` (see ``hugeicons/README.md``).

Authors should reach for :class:`sciviz.Icon`, not this module directly.
"""

from __future__ import annotations

from ._lucide import LUCIDE_ICONS, LUCIDE_VIEWBOX
from ._hugeicons import (
    HUGEICONS_VIEWBOX,
    has_hugeicon,
    hugeicons_manifest,
    hugeicons_names,
    load_hugeicon_shapes,
    search_hugeicons,
)

__all__ = [
    "LUCIDE_ICONS",
    "LUCIDE_VIEWBOX",
    "HUGEICONS_VIEWBOX",
    "has_hugeicon",
    "hugeicons_manifest",
    "hugeicons_names",
    "load_hugeicon_shapes",
    "search_hugeicons",
]
