"""Common diagram elements.

These are the generic building blocks used across every sciviz diagram:
:class:`Text`, :class:`TextBlock`, :class:`Box`, :class:`Matrix`,
:class:`Legend`, :class:`LegendItem`, :class:`Caption`, :class:`TokenRow`.

The low-level :class:`Arrow` / :class:`Connector` primitives live here
too but are hidden from the public API; authors reach for
:class:`sciviz.connect.Connect` instead.
"""

from ._arrow import Arrow, Connector
from ._box import Box
from ._caption import Caption
from ._legend import Legend, LegendItem
from ._matrix import Matrix
from ._obstacles import _register_implicit_obstacle
from ._text import Text, TextBlock
from ._tokenrow import TokenRow

__all__ = [
    "Text", "TextBlock", "Box", "Matrix", "Legend", "LegendItem",
    "Caption", "TokenRow",
    # Internal; kept for backwards-compatible intra-package imports.
    "Arrow", "Connector",
]
