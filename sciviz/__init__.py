"""sciviz -- opinionated, compositional diagrams for scientific ML papers.

Quick start
-----------

    from sciviz import Diagram, Row, Panel, Matrix, Math

    d = Diagram(
        title="My Figure",
        body=Row(
            Panel("a", "Input",  Matrix((8, 8))),
            Panel("b", r"$\\hat y = \\mathrm{softmax}(Wx)$",
                  Math(r"$\\frac{\\partial L}{\\partial W}$")),
        ),
    )
    d.save("figure.pdf")   # also .svg and .png

Design principles
-----------------

1. **Declarative.**  You describe *what* to show, not *where*.
2. **Opinionated.**  A single paper-ready theme.  Call ``Theme.slides()``
   for the looser slide aesthetic.
3. **Bbox composition.**  Every element reports its extent; parents handle
   placement.  Containment guarantees no overlap between siblings.
4. **Semantic tokens.**  ``gap="lg"``, ``size="label"``, ``color="highlight"``.
5. **Vector math.**  :class:`Math` renders LaTeX via matplotlib as SVG
   paths -- embeds cleanly into the output PDF.
6. **Rich ML primitives.**  :class:`Crossbar`, :class:`AttentionHead`,
   :class:`LoRA`, :class:`Tensor`, :class:`NNLayer`, :class:`Pipeline`,
   :class:`QuantBins`.
7. **Aligned charts.**  :class:`Table` and :class:`BarChart` take care of
   cross-row column alignment automatically.
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
    Stack,
    Grid,
    Padded,
    Panel,
    Framed,
)

# ----- generic elements ----------------------------------------------------
from .elements import (
    Text,
    TextBlock,
    Box,
    Arrow,
    Connector,
    Matrix,
    Legend,
    LegendItem,
    Note,
    Caption,
    MiniGrid,
    TokenRow,
)

# ----- math ----------------------------------------------------------------
from .math import Math, auto_text

# ----- charts --------------------------------------------------------------
from .charts import Table, AlignedColumns, BarChart

# ----- specialized ---------------------------------------------------------
from .specialized import Pyramid, Timeline, Tree, Scatter

# ----- structures (high-level layout primitives) --------------------------
from .structures import Strip, Section, BlockGroup, LayeredGraph

# ----- general primitives -------------------------------------------------
from .primitives import Heatmap, Histogram, MeshArray, VectorTiles, StackedBoxes

# ----- color system --------------------------------------------------------
from .palette import Palette, ColorRef

# ----- ML-specific elements (generic primitives) --------------------------
from .ml import (
    NNLayer,
    Pipeline,
    Tensor,
)
# Domain-specific presets live in sciviz.examples.ml:
#     from sciviz.examples.ml import AttentionHead, LoRA, QuantBins

# ----- composition ---------------------------------------------------------
from .composition import (
    Inline,
    Captioned,
    LabeledChain,
    Card,
    KeyValue,
    Bullets,
    Badge,
    LoopIcon,
    Brace,
    Annotated,
    Anchor,
    Flow,
    Flowed,
    Labeled,
    MatchSize,
    Group,
    Region,
    Bus,
)
from .grid import Grid

# ----- generic graphs ------------------------------------------------------
from .graphs import (
    Token,
    Tokens,
    BipartiteGraph,
    NodeTree,
    Sequence,
    FlowChart,
)

# ----- top-level Diagram ---------------------------------------------------
from .diagram import Diagram

__all__ = [
    # core
    "Theme", "DEFAULT_THEME", "BBox", "Canvas", "Element",
    # layout
    "Spacer", "FixedSize", "Row", "Column", "Stack", "Grid",
    "Padded", "Panel", "Framed",
    # elements
    "Text", "TextBlock", "Box", "Arrow", "Connector",
    "Matrix", "Legend", "LegendItem", "Note", "Caption", "MiniGrid", "TokenRow",
    # math
    "Math", "auto_text",
    # charts
    "Table", "AlignedColumns", "BarChart",
    # specialized
    "Pyramid", "Timeline", "Tree", "Scatter",
    # structures
    "Strip", "Section", "BlockGroup", "LayeredGraph",
    # primitives
    "Heatmap", "Histogram", "MeshArray", "VectorTiles", "StackedBoxes",
    # color
    "Palette", "ColorRef",
    # ml
    "NNLayer", "Pipeline", "Tensor",
    # composition
    "Inline", "Captioned", "LabeledChain", "Card", "KeyValue", "Bullets",
    "Badge", "Brace",
    "Annotated", "Anchor", "Flow", "Flowed", "Labeled",
    "MatchSize", "Group", "Region", "Bus",
    "Grid",
    # graphs
    "Token", "Tokens", "BipartiteGraph", "NodeTree", "Sequence", "FlowChart",
    # root
    "Diagram",
]

__version__ = "0.3.0"
