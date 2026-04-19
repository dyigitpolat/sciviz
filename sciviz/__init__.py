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
    d.save_all("figure")   # writes figure.svg, figure.pdf, figure.png

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
6. **Aligned charts.**  :class:`Table` and :class:`BarChart` take care of
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
