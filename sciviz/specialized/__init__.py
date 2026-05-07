"""Specialized paper-style visualisation elements.

* :class:`Pyramid`  -- stacked-trapezoid layout (memory hierarchies, taxonomies).
* :class:`Timeline` -- horizontal time axis with labelled events and lanes.
* :class:`Scatter`  -- 2D scatter plot with axes and gridlines.
* :class:`LineChart`-- multi-series line plot with inline :class:`Annotate`.
* :class:`GroupedBarChart` -- paired vertical bars with gain arrows per group.
"""

from ._groupedbars import BarGroup, BarSeries, GroupedBarChart
from ._linechart import Annotate, LineChart, Series
from ._mini import MiniGraph, MiniMatrix, MiniRaster, MiniTimeline, SparkLine, Sparkline
from ._pyramid import Pyramid
from ._scatter import Scatter
from ._timeline import Timeline

__all__ = [
    "Pyramid", "Timeline", "Scatter", "LineChart", "Series", "Annotate",
    "GroupedBarChart", "BarGroup", "BarSeries",
    "SparkLine", "Sparkline", "MiniMatrix", "MiniGraph",
    "MiniTimeline", "MiniRaster",
]
