"""Automatic layout assistants.

This package groups the ingredients that let sciviz avoid manual
coordinates:

* :mod:`sciviz.auto.router`       -- topological orthogonal path planner.
* :mod:`sciviz.auto.labelplacer`  -- pure geometric label-placement solver.

Future debug tooling (overlay / HTML viewer / CLI) will land here too.
"""

from . import labelplacer, router

__all__ = ["labelplacer", "router"]
