"""Common diagram elements.

These are the generic building blocks used across every sciviz diagram:
:class:`Text`, :class:`TextBlock`, :class:`Box`, :class:`Matrix`,
:class:`Legend`, :class:`LegendItem`, :class:`Caption`, :class:`TokenRow`,
:class:`Icon`, :class:`Image`, :class:`Separator`.

The low-level :class:`Arrow` / :class:`Connector` primitives live here
too but are hidden from the public API; authors reach for
:class:`sciviz.connect.Connect` instead.
"""

from ._arrow import Arrow, Connector
from ._box import Box
from ._caption import Caption
from ._condition_glyph import ConditionGlyph
from ._icon import Icon
from ._image import Image
from ._legend import Legend, LegendItem
from ._matrix import Matrix
from ._obstacles import _register_implicit_obstacle
from ._separator import Separator
from ._text import Span, Text, TextBlock
from ._tokenrow import TokenRow

__all__ = [
    "Text", "TextBlock", "Span", "Box", "Matrix", "Legend", "LegendItem",
    "Caption", "ConditionGlyph", "TokenRow", "Icon", "Image", "Separator",
    # Internal; kept for backwards-compatible intra-package imports.
    "Arrow", "Connector",
]
