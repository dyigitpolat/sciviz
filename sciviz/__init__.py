"""sciviz -- opinionated, compositional diagrams for scientific ML papers.

Quick start
-----------

    from sciviz import Diagram, Row, Panel, Matrix, Math, Anchor, Connect

    d = Diagram(
        title="My Figure",
        body=Row(
            Anchor("in",  Panel("a", "Input",  Matrix((8, 8)))),
            Anchor("out", Panel("b", "Output", Math(r"$Wx + b$"))),
            Connect("in", "out"),       # declarative wire, auto-routed
        ),
    )
    d.save_all("figure")   # writes figure.svg, figure.pdf, figure.png

Design principles
-----------------

1. **Declarative.**  You describe *what* to show, not *where*.
2. **Opinionated.**  A single paper-ready theme.  Call ``Theme.slides()``
   for the looser slide aesthetic.
3. **Bbox composition.**  Every element reports its extent; parents handle
   placement.  Containment guarantees no overlap between siblings.
4. **One way to connect.**  :class:`Connect` subsumes arrows, buses,
   inline connectors, and labeled wires -- author intent, let the
   backend route.
5. **Semantic tokens.**  ``gap="lg"``, ``size="label"``, ``color="highlight"``.
6. **Vector math.**  :class:`Math` renders LaTeX via matplotlib as SVG
   paths -- embeds cleanly into the output PDF.

Package layout
--------------

* ``sciviz.core``       -- :class:`Element`, :class:`BBox`, :class:`Canvas`,
                           :class:`Theme`.
* ``sciviz.layout``     -- :class:`Row`, :class:`Column`, :class:`Panel`,
                           :class:`Spacer`, :class:`FixedSize`.
* ``sciviz.elements``   -- :class:`Text`, :class:`Box`, :class:`Matrix`,
                           :class:`Legend`, :class:`Caption`, :class:`TokenRow`.
* ``sciviz.composition``-- :class:`Inline`, :class:`Captioned`, :class:`Badge`,
                           :class:`Brace`, :class:`Group`, :class:`Region`,
                           :class:`LabeledChain`, :class:`MatchSize`,
                           :class:`LoopIcon`.
* ``sciviz.connect``    -- :class:`Connect`, :class:`Anchor`.
* ``sciviz.grid``       -- :class:`Grid` (declarative per-column alignment).
* ``sciviz.charts``     -- :class:`Table`, :class:`AlignedColumns`,
                           :class:`BarChart`.
* ``sciviz.primitives`` / ``sciviz.specialized`` / ``sciviz.structures`` /
  ``sciviz.graphs``     -- domain-specific visualisations (heatmaps,
                           pyramids, token graphs, sections, ...).
* ``sciviz.math``       -- :class:`Math` (LaTeX-via-matplotlib).
* ``sciviz.palette``    -- :class:`Palette`, :class:`ColorRef`.
* ``sciviz.auto``       -- :mod:`sciviz.auto.router`,
                           :mod:`sciviz.auto.labelplacer`; automatic
                           layout assistants used by the backend.

Lower packages must not import higher packages -- see
``tests/test_import_direction.py``.
"""

# ----- core infrastructure -------------------------------------------------
from .core import (
    Theme,
    DEFAULT_THEME,
    BBox,
    Canvas,
    Element,
)

# ----- layout primitives ---------------------------------------------------
from .layout import (
    Spacer,
    FixedSize,
    Row,
    Column,
    Panel,
)

# ----- generic elements ----------------------------------------------------
from .elements import (
    Text,
    TextBlock,
    Box,
    Matrix,
    Legend,
    LegendItem,
    Caption,
    TokenRow,
)

# ----- math ----------------------------------------------------------------
from .math import Math

# ----- charts --------------------------------------------------------------
from .charts import Table, AlignedColumns, BarChart

# ----- specialized ---------------------------------------------------------
from .specialized import Pyramid, Timeline, Scatter

# ----- structures (high-level layout primitives) --------------------------
from .structures import Section, BlockGroup

# ----- general primitives -------------------------------------------------
from .primitives import Heatmap, Histogram, MeshArray, VectorTiles, StackedBoxes

# ----- color system --------------------------------------------------------
from .palette import Palette, ColorRef

# ----- composition ---------------------------------------------------------
from .composition import (
    Inline,
    Captioned,
    LabeledChain,
    Badge,
    LoopIcon,
    Brace,
    MatchSize,
    Group,
    Region,
)
from .grid import Grid

# ----- unified connector ---------------------------------------------------
from .connect import Connect, Anchor

# ----- generic graphs ------------------------------------------------------
from .graphs import (
    Token,
    Tokens,
    NodeTree,
    Sequence,
)

# ----- top-level Diagram ---------------------------------------------------
from .diagram import Diagram

__all__ = [
    # core
    "Theme", "DEFAULT_THEME", "BBox", "Canvas", "Element",
    # layout
    "Spacer", "FixedSize", "Row", "Column", "Grid", "Panel",
    # elements
    "Text", "TextBlock", "Box",
    "Matrix", "Legend", "LegendItem", "Caption", "TokenRow",
    # math
    "Math",
    # charts
    "Table", "AlignedColumns", "BarChart",
    # specialized
    "Pyramid", "Timeline", "Scatter",
    # structures
    "Section", "BlockGroup",
    # primitives
    "Heatmap", "Histogram", "MeshArray", "VectorTiles", "StackedBoxes",
    # color
    "Palette", "ColorRef",
    # composition
    "Inline", "Captioned", "LabeledChain",
    "Badge", "LoopIcon", "Brace",
    "MatchSize", "Group", "Region",
    # unified connector
    "Connect", "Anchor",
    # graphs
    "Token", "Tokens", "NodeTree", "Sequence",
    # root
    "Diagram",
]

__version__ = "0.3.0"
