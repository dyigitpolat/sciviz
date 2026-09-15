"""Generic data-display primitives.

* :class:`Balance`     -- two quantities weighed against each other.
* :class:`Funnel`      -- a staged narrowing of one population.
* :class:`Gauge`       -- one bounded reading with its limits marked.
* :class:`Heatmap`     -- general 2D scalar field.
* :class:`Histogram`   -- vertical bar histogram.
* :class:`MeshArray`   -- 2D grid with optional peripheral annotations.
* :class:`VectorTiles` -- compact row of tiny bars / arrows.
* :class:`StackedBoxes`-- a small stack of labeled rectangles.
"""

from ._balance import Balance, BalancePan
from ._funnel import Funnel, FunnelStage
from ._gauge import Gauge, GaugeMark
from ._heatmap import Heatmap
from ._histogram import Histogram
from ._mesharray import MeshArray
from ._stackedboxes import StackedBoxes
from ._vectortiles import VectorTiles

__all__ = ["Balance", "BalancePan", "Funnel", "FunnelStage", "Gauge",
           "GaugeMark", "Heatmap", "Histogram", "MeshArray", "VectorTiles",
           "StackedBoxes"]
