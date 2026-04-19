"""Layout primitives (Row, Column, Grid, Panel, Spacer, FixedSize).

All layout containers follow the same rules:

* They measure each child, arrange them with automatic spacing, and
  report a bounding box that fully contains every child.
* Children are placed by position -- no child ever needs to know where
  it lives in its parent.

This means a deeply nested diagram always lays out correctly: measuring
is bottom-up, rendering is top-down.
"""

from ._aligned_stack import AlignedStack
from ._column import Column
from ._panel import Panel
from ._row import Row
from ._simple_grid import Grid
from ._spacer import FixedSize, Spacer

__all__ = [
    "Spacer", "FixedSize", "Row", "Column", "Grid", "Panel", "AlignedStack",
]
