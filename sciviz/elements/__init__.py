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
from ._chip import Chip
from ._condition_glyph import ConditionGlyph
from ._cylinder import Cylinder
from ._harvey_ball import HarveyBall
from ._document import Document
from ._mux import Mux
from ._icon import Icon
from ._image import Image
from ._legend import Legend, LegendItem
from ._marker import Marker, draw_marker, marker_radius
from ._matrix import (
    ColorBar,
    ColorScale,
    Matrix,
    MatrixCell,
    MatrixGroup,
    MatrixSelection,
)
from ._obstacles import _register_implicit_obstacle
from ._separator import Separator
from ._text import Span, Text, TextBlock
from ._tokenrow import TokenRow

__all__ = [
    "Text", "TextBlock", "Span", "Box", "Chip", "Matrix", "MatrixCell",
    "MatrixSelection", "MatrixGroup", "ColorScale", "ColorBar", "Legend", "LegendItem",
    "Marker", "draw_marker", "marker_radius",
    "Caption", "ConditionGlyph", "Cylinder", "Document", "HarveyBall", "Mux", "TokenRow", "Icon", "Image", "Separator",
    # Internal; kept for backwards-compatible intra-package imports.
    "Arrow", "Connector",
]
