# sciviz

**Opinionated, compositional, paper-ready diagrams for scientific computing.**

`sciviz` lets you build publication-quality figures from a declarative,
bounding-box layout model. You describe *what* the figure contains;
the library handles typography, colour, alignment, math typesetting,
arrow routing, and overlap avoidance.

```python
from sciviz import Diagram, Row, Panel, Math, BarChart

d = Diagram(
    title="Post-training quantization",
    body=Row(
        Panel("a", "Rounding formula",
              Math(r"$Q(w) = \mathrm{round}(w / s) \cdot s$")),
        Panel("b", "Memory footprint",
              BarChart([
                  ("FP32", 28.0, "28.0 GB"),
                  ("INT8",  7.0,  "7.0 GB"),
                  ("INT4",  3.5,  "3.5 GB"),
              ], highlight_first=True)),
    ),
)
d.save("figure.pdf")    # also .svg and .png
```

Read [`docs/AUTHORING.md`](docs/AUTHORING.md) for the single-document
tour of every primitive -- icons, images, line charts, generic trees,
aligned stacks, structured text runs, and the rest of the vocabulary.

## Design principles

1. **Declarative.**  You compose elements, not coordinates.
2. **Opinionated, paper-first.**  Defaults target print: white background,
   hairline borders, Computer Modern math, muted print-safe palette. Call
   `Theme.slides()` for the looser slide aesthetic.
3. **Bbox composition.**  Every element reports its extent; parents
   handle placement. Containment guarantees no sibling overlap.
4. **One way to connect.**  `Connect` subsumes arrows, buses, inline
   connectors, and labeled wires. Author intent, the backend routes.
5. **Semantic colour.**  `color=Palette.alert`, `color=Palette.blue`,
   `color=Palette.next("worker_0")` — never hex. Concrete hex still
   works as an escape hatch via `Palette.literal("#abc")`.
6. **Export-safe typography.**  SVG export embeds a known font; PDF and PNG
   export use the same outlined text path by default, so missing glyph boxes
   and PDF/PNG font drift are not accepted output.
7. **Vector math.**  `Math(r"$...$")` renders LaTeX through matplotlib's
   `mathtext` as SVG paths — no raster, no font dependency.

## Package layout

```
sciviz/
  core/           Element, BBox, Canvas, Theme
  layout/         Row, Column, Panel, Spacer, FixedSize, AlignedStack
  elements/       Text, TextBlock, Span, Box, Matrix, Legend, Caption,
                  TokenRow, Icon, Image, Separator
  composition/    Inline, Captioned, Badge, Brace (+ Brace.spanning),
                  Card, EqualGrid, Stripe, StepCell, SoftLegend,
                  Group, Region (label_position/annotations/corner_badge),
                  LabeledChain, MatchSize, LoopIcon
  connect/        Connect, Anchor       -- the only public connector API
  grid/           Grid                  -- per-column alignment
  charts/         Table, AlignedColumns, BarChart
  primitives/     Heatmap, Histogram, MeshArray, VectorTiles, StackedBoxes
  specialized/    Pyramid, Timeline, Scatter, LineChart, Series, Annotate,
                  Sparkline, MiniGraph, MiniMatrix, MiniTimeline, MiniRaster
  structures/     Section, BlockGroup
  graphs/         Tree, TreeNode, NodeTree, Token, Tokens, Sequence
  math/           Math                  -- LaTeX via matplotlib mathtext
  palette/        Palette, ColorRef     -- semantic colour system
  _assets/        bundled Lucide icon SVG paths
  auto/           router, labelplacer   -- layout assistants (internal)
  diagram.py      Diagram               -- root container with export
```

Lower packages must not import higher packages; this is enforced by
`tests/test_import_direction.py`.

## Core contract

```python
class Element:
    def measure(self, theme) -> BBox: ...
    def render(self, canvas, x, y, theme) -> None: ...
```

Every drawable promises to keep its rendering inside the bounding box
it reports. That single invariant lets sibling elements compose without
overlap — containers simply measure each child, place it, and advance.

## Connecting things: `Connect`

```python
from sciviz import Row, Box, Anchor, Connect

# Inline: a bare arrow between neighbours in a Row / Column.
Row(Box("in"), Connect(), Box("out"))

# Routed: a wire between two named anchors, planned around obstacles.
Row(
    Anchor("a", Box("alpha")),
    Anchor("b", Box("beta")),
    Connect("a", "b", label="to beta"),
)

# Bus: many sources fan into a single label or destination.
Connect(["a1", "a2", "a3"], "sink", label="concat")

# Labeled: a source element decorated with a short-arrow label.
Connect.labeled(Anchor("op", Box("f")), Math(r"$y = f(x)$"))
```

`Connect(src, dst, ...)` auto-detects its mode (inline, routed, or bus)
from the shape of `src` / `dst`. Colour, head shape, curvature, and
dashing all have sensible defaults derived from the theme.
Connector labels are placed through the same obstacle-aware label placer
used by buses and routed wires; placed labels become obstacles for later
labels, and `Diagram(auto_fit=True)` expands the canvas if ink falls just
outside the measured body.

## Paper figures

For paper figures whose captions already carry the title, use
`Diagram.for_paper(body)`. It suppresses title/subtitle/footer chrome and
uses a tighter content margin. Pipeline and architecture diagrams should
prefer `Card`, `EqualGrid`, `Stripe`, `StepCell`, `ConditionGlyph`, and
`SoftLegend` over fixed-size boxes and spacer shims.

## Colour system

```python
from sciviz import Palette

color=Palette.alert            # semantic role -> theme-appropriate red
color=Palette.success.soft()   # light tint of green
color=Palette.blue             # named hue
color=Palette.next("worker_0") # stable categorical: same key -> same colour
color=Palette.literal("#abc")  # explicit escape hatch
```

`Palette.next(key)` is particularly useful for diagrams with multiple
related entities (workers, micro-batches, kernels) that should share
colours across panels — pass the same key string anywhere the colour
should match, and you'll get the same hue.

## Gallery

Twenty-two showcase figures ship in `gallery/`, each under ~60 lines.

Twelve "domain" figures lead with real diagrams from papers and textbooks:

| Diagram | Domain | Topic | Primary primitive |
|---|---|---|---|
| `memory_hierarchy.py` | hardware | CPU cache pyramid | `Pyramid` |
| `roofline.py` | perf-engineering | A100 FP16 roofline | `Scatter` |
| `pipeline_parallelism.py` | ML systems | GPipe schedule | `Timeline` |
| `paxos.py` | distributed | Two-phase consensus | `Sequence` |
| `speculative_decoding.py` | ML inference | Draft + target protocol | `Tokens` |
| `bplus_tree.py` | data structures | Linked leaves | `NodeTree` |
| `diffusion.py` | ML theory | Forward/reverse Markov chain | `Heatmap` |
| `amortized_analysis.py` | algorithms | Doubling array push() | `Histogram` |
| `crossbar_pruning.py` | ML hardware | Row/col pruning | `MeshArray` |
| `deepseek_v3.py` | ML systems | DeepSeek-V3 architecture | composed primitives |
| `action_conditioning_modes.py` | ML | Action conditioning injection | composed primitives |
| `ttt_mlp.py` | ML | In-place test-time training MLP | `Connect` bus + composites |

Ten "feature" figures (`gallery/fig01.py` ... `gallery/fig10.py`)
exercise the new 0.4.0 primitives one at a time: `Image`,
`Brace.spanning`, structured text runs, `Region` side labels and
annotations, `AlignedStack`, corner badges with semantic role colours,
`LineChart` with annotations, `Tree` with per-edge style, icon-heavy
compositions, and `Separator` + `AlignedStack`.

## Math

Renders LaTeX through matplotlib's `mathtext` to vector SVG paths.
Cached by `(latex, size, color, bold)` so reused expressions don't
re-render.

```python
Math(r"$\hat y = \mathrm{softmax}\!\left(\frac{QK^\top}{\sqrt{d_k}}\right) V$")
```

Supported: Greek, sub/superscripts, fractions, sqrt, sums, integrals,
`\mathrm`, `\mathcal`, `\hat`, `\bar`, most operators.
Not supported: `\underbrace`, tikz, environments beyond inline math.

## Installation

From a clone of this repository (recommended for development):

```bash
./scripts/bootstrap.sh   # creates .venv, installs sciviz editable + PDF/PNG deps
source .venv/bin/activate
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[pdf]"      # omit [pdf] for SVG-only
```

Runtime: **matplotlib** (required for `Math`, bundled font assets, and
text-outlining fallback). **resvg-py** is used for PNG export. PDF export
uses `rsvg-convert` or Inkscape when available, otherwise CairoSVG with
outlined text.

## Theme

```python
from sciviz import Theme

theme = Theme.slides()                    # rounded panels, vivid colours
theme = Theme().with_overrides(unit=8.0)  # partial customisation
```

## Version

0.3.0 — unified `Connect` API, clean package split (`core`, `layout`,
`elements`, `composition`, `connect`, `grid`, `charts`, `primitives`,
`specialized`, `structures`, `graphs`, `math`, `palette`, `auto`,
`diagram`), 22 gallery figures, 250+ tests. Wave-7 primitives:
`Icon`, `Image`, `Separator`, `Span`, `AlignedStack`, `LineChart`,
`Annotate`, `Tree`, `Brace.spanning`, enriched `Region`, semantic
role colours.
