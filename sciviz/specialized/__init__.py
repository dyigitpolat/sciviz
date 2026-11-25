"""Specialized paper-style visualisation elements.

* :class:`Pyramid`  -- stacked-trapezoid layout (memory hierarchies, taxonomies).
* :class:`Timeline` -- horizontal time axis with labelled events and lanes.
* :class:`StepLanes` -- lanes over discrete time steps: windows, marks, links.
* :class:`ShareBar` -- one thin bar showing a share of a whole.
* :class:`StepRaster`, :class:`CoreChip`, :class:`LayerNet` -- schematic step blocks, chips of cores, small layered networks.
* :class:`Scatter`  -- 2D scatter plot with axes and gridlines.
* :class:`LineChart`-- multi-series line plot with inline :class:`Annotate`.
* :class:`GroupedBarChart` -- paired vertical bars with gain arrows per group.
* :class:`Slopegraph` -- two-rail before/after comparison with direct labels.
"""

from ._groupedbars import Bar, BarGroup, BarSeries, GroupedBarChart
from ._linechart import Annotate, FillBetween, LineChart, Series, SeriesDelta
from ._mini import (MiniArea, MiniCell, MiniGraph, MiniMatrix, MiniPoint, MiniRaster, MiniScatter,
                    MiniTimeline, SparkLine, Sparkline)
from ._pyramid import Pyramid
from ._scatter import Scatter
from ._slopegraph import SlopeRecord, SlopeReference, Slopegraph
from ._sharebar import ShareBar
from ._steplanes import StepGroup, StepLane, StepLanes, StepLink, StepMark
from ._cores import Core, CoreChip, CoreLink, LayerNet, NetLayer, RasterLink, RasterRow, StepRaster, ThinArrow, PointArrow, PointArrows
from ._timeline import Timeline

__all__ = [
    "Pyramid", "Timeline", "Scatter", "LineChart", "Series", "FillBetween",
    "SeriesDelta", "Annotate",
    "GroupedBarChart", "Bar", "BarGroup", "BarSeries",
    "Slopegraph", "SlopeRecord", "SlopeReference",
    "SparkLine", "Sparkline", "MiniMatrix", "MiniGraph",
    "MiniTimeline", "MiniRaster", "MiniCell", "MiniScatter", "MiniPoint", "MiniArea",
    "StepLanes", "StepLane", "StepGroup", "StepLink", "StepMark", "ShareBar",
    "StepRaster", "RasterRow", "RasterLink", "CoreChip", "Core", "CoreLink", "LayerNet", "NetLayer", "ThinArrow", "PointArrow", "PointArrows",
]
