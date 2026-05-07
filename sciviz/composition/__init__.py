"""Higher-level composition primitives.

These eliminate the most common patterns we kept writing manually:

* :class:`Inline`       -- baseline-aligned mixed text/math, no manual Spacers.
* :class:`Captioned`    -- wrap a child with a numbered badge or titled caption.
* :class:`LabeledChain` -- horizontal items with auto-aligned top/bottom labels.
* :class:`Badge`        -- small filled circle for numbered/lettered markers.
* :class:`LoopIcon`     -- '\u21bb' glyph for "repeat N times" annotations.
* :class:`Brace`        -- horizontal curly brace with an optional label.
* :class:`Anchor` / :class:`Flow` / :class:`Flowed` -- declarative curved arrows
  between named elements, resolved after their bboxes are known.
* :class:`Labeled`      -- a source element annotated by a short arrow to a label.
* :class:`MatchSize`    -- stretch siblings to share a major-axis dimension.
* :class:`Group`        -- Row with an automatic brace + label beneath.
* :class:`Region`       -- labeled bordered container with outside label.
* :class:`Bus`          -- multi-endpoint connector routed through a single spine.

Implementation lives in the private submodules; this file re-exports
the full surface so existing intra-package imports
(``from ..composition import Anchor, Flow``) keep working.
"""

from ._anchor import Anchor, _anchor_stack, _side_point, _side_point_frac
from ._badge import Badge
from ._banner import Banner
from ._brace import Brace
from ._bus import Bus
from ._captioned import Captioned
from ._compound import Card, ConditionSpec, EqualGrid, SoftLegend, StepCell, Stripe
from ._flow import Flow, Labeled
from ._flowed import Flowed
from ._group import Group
from ._inline import Inline
from ._labeledchain import LabeledChain
from ._loopicon import LoopIcon
from ._matchsize import MatchSize
from ._region import Region
from ._stackedtiles import StackedTiles

__all__ = [
    "Inline", "Banner", "Captioned", "Card", "ConditionSpec",
    "EqualGrid", "SoftLegend", "StepCell", "Stripe", "LabeledChain",
    "Badge", "LoopIcon", "Brace",
    "Anchor", "Flow", "Flowed", "Labeled",
    "MatchSize", "Group", "Region", "Bus", "StackedTiles",
]
