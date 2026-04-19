"""Generic data-display primitives.

* :class:`Heatmap`     -- general 2D scalar field.
* :class:`Histogram`   -- vertical bar histogram.
* :class:`MeshArray`   -- 2D grid with optional peripheral annotations.
* :class:`VectorTiles` -- compact row of tiny bars / arrows.
* :class:`StackedBoxes`-- a small stack of labeled rectangles.
"""

from ._heatmap import Heatmap
from ._histogram import Histogram
from ._mesharray import MeshArray
from ._stackedboxes import StackedBoxes
from ._vectortiles import VectorTiles

__all__ = ["Heatmap", "Histogram", "MeshArray", "VectorTiles", "StackedBoxes"]
