"""Static asset bundles shipped inside the :mod:`sciviz` package.

At present this is just the :mod:`~sciviz._assets._lucide` icon set: a
curated ~50-icon subset of `Lucide <https://lucide.dev>`_ (MIT-licensed)
whose SVG path data is baked into the package so ``Icon("camera")`` has
zero runtime dependencies.

Authors should reach for :class:`sciviz.Icon`, not this module directly.
"""

from __future__ import annotations

from ._lucide import LUCIDE_ICONS, LUCIDE_VIEWBOX

__all__ = ["LUCIDE_ICONS", "LUCIDE_VIEWBOX"]
