"""Backwards-compatible shim: re-exports :mod:`sciviz.auto.labelplacer`.

Authors should not import from this module directly; the canonical
location is :mod:`sciviz.auto.labelplacer`. This shim keeps internal
imports (``from .._labelplacer import place_label`` in composition
code) functional during the reorganization.
"""

from .auto.labelplacer import *  # noqa: F401, F403
from .auto.labelplacer import place_label  # noqa: F401
