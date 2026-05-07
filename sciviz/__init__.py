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

Read the single-doc reference at
[`docs/AUTHORING.md`](../../docs/AUTHORING.md) for the full vocabulary.

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
5. **Semantic tokens.**  ``gap="lg"``, ``size="label"``,
   ``color="positive"``, ``color="negative"``, ``color="warning"``.
6. **Vector math.**  :class:`Math` renders LaTeX via matplotlib as SVG
   paths -- embeds cleanly into the output PDF.

Package layout
--------------

* ``sciviz.core``       -- :class:`Element`, :class:`BBox`, :class:`Canvas`,
                           :class:`Theme`.
* ``sciviz.layout``     -- :class:`Row`, :class:`Column`, :class:`Panel`,
                           :class:`Spacer`, :class:`FixedSize`,
                           :class:`AlignedStack`.
* ``sciviz.elements``   -- :class:`Text`, :class:`Box`, :class:`Matrix`,
                           :class:`Legend`, :class:`Caption`, :class:`TokenRow`,
                           :class:`Icon`, :class:`Image`, :class:`Separator`,
                           :func:`Span`.
* ``sciviz.composition``-- :class:`Inline`, :class:`Captioned`, :class:`Badge`,
                           :class:`Brace`, :class:`Group`, :class:`Region`,
                           :class:`LabeledChain`, :class:`MatchSize`,
                           :class:`LoopIcon`.
* ``sciviz.connect``    -- :class:`Connect`, :class:`Anchor`.
* ``sciviz.grid``       -- :class:`Grid` (declarative per-column alignment).
* ``sciviz.charts``     -- :class:`Table`, :class:`AlignedColumns`,
                           :class:`BarChart`.
* ``sciviz.specialized``-- :class:`Pyramid`, :class:`Timeline`,
                           :class:`Scatter`, :class:`LineChart`,
                           :class:`Series`, :class:`Annotate`.
* ``sciviz.graphs``     -- :class:`Tree` (arbitrary element nodes),
                           :class:`NodeTree`, :class:`Token`, ...
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
    FontAsset,
    FontRegistry,
)

# ----- layout primitives ---------------------------------------------------
from .layout import (
    Spacer,
    FixedSize,
    Row,
    Column,
    Panel,
    AlignedStack,
)

# ----- generic elements ----------------------------------------------------
from .elements import (
    Text,
    TextBlock,
    Span,
    Box,
    Matrix,
    Legend,
    LegendItem,
    Caption,
    ConditionGlyph,
    TokenRow,
    Icon,
    Image,
    Separator,
)

# ----- math ----------------------------------------------------------------
from .math import Math

# ----- charts --------------------------------------------------------------
from .charts import Table, AlignedColumns, BarChart

# ----- specialized ---------------------------------------------------------
from .specialized import (
    Annotate, BarGroup, BarSeries, GroupedBarChart, LineChart, Pyramid,
    MiniGraph, MiniMatrix, MiniRaster, MiniTimeline, Scatter, Series,
    SparkLine, Sparkline, Timeline,
)

# ----- structures (high-level layout primitives) --------------------------
from .structures import Section, BlockGroup

# ----- general primitives -------------------------------------------------
from .primitives import Heatmap, Histogram, MeshArray, VectorTiles, StackedBoxes

# ----- color system --------------------------------------------------------
from .palette import Palette, ColorRef

# ----- composition ---------------------------------------------------------
from .composition import (
    Inline,
    Banner,
    Card,
    Captioned,
    ConditionSpec,
    EqualGrid,
    LabeledChain,
    Badge,
    LoopIcon,
    Brace,
    MatchSize,
    Group,
    Region,
    SoftLegend,
    StepCell,
    StackedTiles,
    Stripe,
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
    Tree,
    TreeNode,
)

# ----- top-level Diagram ---------------------------------------------------
from .diagram import Diagram

__all__ = [
    # core
    "Theme", "DEFAULT_THEME", "BBox", "Canvas", "Element",
    "FontAsset", "FontRegistry",
    # layout
    "Spacer", "FixedSize", "Row", "Column", "Grid", "Panel", "AlignedStack",
    # elements
    "Text", "TextBlock", "Span", "Box",
    "Matrix", "Legend", "LegendItem", "Caption", "ConditionGlyph", "TokenRow",
    "Icon", "Image", "Separator",
    # math
    "Math",
    # charts
    "Table", "AlignedColumns", "BarChart",
    # specialized
    "Pyramid", "Timeline", "Scatter", "LineChart", "Series", "Annotate",
    "GroupedBarChart", "BarGroup", "BarSeries", "SparkLine", "Sparkline",
    "MiniMatrix", "MiniGraph", "MiniTimeline", "MiniRaster",
    # structures
    "Section", "BlockGroup",
    # primitives
    "Heatmap", "Histogram", "MeshArray", "VectorTiles", "StackedBoxes",
    # color
    "Palette", "ColorRef",
    # composition
    "Inline", "Banner", "Card", "Captioned", "ConditionSpec",
    "EqualGrid", "LabeledChain",
    "Badge", "LoopIcon", "Brace",
    "MatchSize", "Group", "Region", "SoftLegend", "StepCell",
    "StackedTiles", "Stripe",
    # unified connector
    "Connect", "Anchor",
    # graphs
    "Token", "Tokens", "NodeTree", "Sequence", "Tree", "TreeNode",
    # root
    "Diagram",
]

__version__ = "0.3.0"
