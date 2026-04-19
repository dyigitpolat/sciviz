"""Core infrastructure for sciviz.

This package defines the four foundational types:

* :class:`Theme`   -- opinionated visual tokens (colors, type, spacing).
* :class:`BBox`    -- a simple (width, height) bounding box.
* :class:`Canvas`  -- an SVG accumulator with primitive drawing helpers.
* :class:`Element` -- the base class every drawable inherits from.

Implementation lives in the private submodules; this file re-exports
the public surface so existing imports like ``from sciviz.core import
Element`` keep working.
"""

from ._bbox import BBox
from ._canvas import Canvas, _build_text_runs, _fmt, _xml_escape
from ._element import Element
from ._theme import DEFAULT_THEME, Theme

__all__ = ["BBox", "Canvas", "Element", "Theme", "DEFAULT_THEME"]
