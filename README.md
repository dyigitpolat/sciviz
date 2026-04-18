# sciviz

**Opinionated, compositional, paper-ready diagrams for scientific computing.**

`sciviz` lets you build publication-quality figures from a declarative,
bounding-box layout model.  You describe *what* the figure contains; the
library handles typography, colour, alignment, math typesetting, and
overlap avoidance.

```python
from sciviz import Diagram, Row, Panel, Math, BarChart, Palette

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

## Design principles

1. **Declarative.**  You compose elements, not coordinates.
2. **Opinionated, paper-first.**  Defaults target print: white background,
   hairline borders, Computer Modern math, muted print-safe palette.  Call
   `Theme.slides()` for the looser slide aesthetic.
3. **Bbox composition.**  Every element reports its extent; parents handle
   placement.  Containment guarantees no sibling overlap.
4. **Semantic colour.**  `color=Palette.alert`, `color=Palette.blue`,
   `color=Palette.next("worker_0")` — never hex.  Concrete hex still works
   as an escape hatch via `Palette.literal("#abc")`.
5. **No manual spacers.**  `Section`, `Strip`, `Tokens`, `Sequence`, ...
   absorb the spacing arithmetic.  When you do reach for `Spacer`, it's
   for *intentional* irregularity.
6. **Vector math.**  `Math(r"$...$")` renders LaTeX through matplotlib's
   `mathtext` as SVG paths — no raster, no font dependency.
7. **Generic primitives in core; specialization in `examples/`.**  Core
   ships building blocks that span domains.  Domain-specific presets
   (attention heads, LoRA, quantization buckets) are examples that you
   import explicitly and copy-modify.

## Architecture

```
sciviz/
  core.py         Theme, BBox, Canvas, Element base class
  layout.py       Spacer, Row, Column, Stack, Grid, Panel, Padded, Framed,
                  FixedSize
  elements.py     Text, TextBlock, Box, Arrow, Connector, Matrix, Legend,
                  Note, Caption, MiniGrid
  math.py         Math, auto_text     (LaTeX via matplotlib mathtext)
  charts.py       Table, BarChart
  primitives.py   Heatmap, Histogram, MeshArray
  specialized.py  Pyramid, Timeline, Tree, Scatter
  structures.py   Strip, Section, BlockGroup, LayeredGraph
  graphs.py       Token, Tokens, BipartiteGraph, NodeTree, Sequence,
                  FlowChart
  composition.py  Inline, Card, KeyValue, Bullets
  ml.py           NNLayer, Pipeline, Tensor   (generic ML primitives)
  palette.py      Palette, ColorRef           (semantic colour system)
  diagram.py      Diagram (root container with title/subtitle/footer + export)
  examples/
    ml.py         AttentionHead, LoRA, QuantBins   (domain-specific presets)
```

## Core contract

```python
class Element:
    def measure(self, theme) -> BBox: ...
    def render(self, canvas, x, y, theme) -> None: ...
```

Every drawable promises to keep its rendering inside the bounding box it
reports.  That single invariant lets sibling elements compose without
overlap — containers simply measure each child, place it, and advance.

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

## Layout primitives that absorb manual work

| Pattern | Old way | New way |
|---|---|---|
| Equal-width token cells | `Row(Spacer, Box, Spacer, Box, ...)` | `Tokens([(label, role), ...])` |
| Title + rule + body + caption | `Column(Text, Spacer, Body, Spacer, Caption)` | `Section(title, body, caption=...)` |
| Phase/group framing | manual `Box` + caption arithmetic | `BlockGroup(child, label=...)` |
| Two-column DAG | hand-routed lines | `BipartiteGraph(left, right, edges)` |
| Tree of pages | hand-routed lines | `NodeTree(tree_tuple)` |
| UML message diagram | abused `Timeline` | `Sequence(actors, messages)` |
| Layered DAG | hand-routed lines | `LayeredGraph(layers, edges)` |

## Gallery

Twelve showcase figures ship in `gallery/`, each under 60 lines.

| Diagram | Domain | Topic | Primary primitive |
|---|---|---|---|
| `memory_hierarchy.py` | hardware | CPU cache pyramid | `Pyramid` (auto-shaded) |
| `roofline.py` | perf-engineering | A100 FP16 roofline | `Scatter` (log-log + lines) |
| `pipeline_parallelism.py` | ML systems | GPipe schedule | `Timeline` + `Palette.next` |
| `paxos.py` | distributed | Two-phase consensus | `Sequence` (UML lifelines) |
| `speculative_decoding.py` | ML inference | Draft + target protocol | `Tokens` (auto-aligned) |
| `bplus_tree.py` | data structures | Linked leaves | `NodeTree` (15 lines!) |
| `diffusion.py` | ML theory | Forward/reverse Markov chain | `Heatmap` |
| `amortized_analysis.py` | algorithms | Doubling array push() | `Histogram` |
| `crossbar_pruning.py` | ML hardware | Row/col pruning | `MeshArray` (grid + peripherals) |
| `deepseek_v3.py` | ML systems | DeepSeek-V3 architecture | composed primitives |
| `action_conditioning_modes.py` | ML | Action conditioning injection modes | composed primitives |
| `ttt_mlp.py` | ML | In-place test-time training MLP | `Bus` + composed primitives |

## Math

Renders LaTeX through matplotlib's `mathtext` to vector SVG paths.  Cached
by `(latex, size, color, bold)` so reused expressions don't re-render.

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

Or install manually:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[pdf]"      # omit [pdf] if you only need SVG; add for PDF/PNG
```

After you build and publish a wheel or sdist, consumers can run `pip install sciviz` (or `pip install 'sciviz[pdf]'`) the same way.

Runtime: **matplotlib** (required for `Math` and layouts). **cairosvg** is only needed for PDF/PNG export; SVG does not use it.

## Theme

```python
from sciviz import Theme

theme = Theme.slides()                    # rounded panels, vivid colours
theme = Theme().with_overrides(unit=8.0)  # partial customisation
```

## Version

0.3.0 — paper-ready theme, `Palette` colour system, `Strip`/`Section`/
`BlockGroup`/`LayeredGraph` structural primitives, `Heatmap`/`Histogram`/
`MeshArray` general primitives, specialization moved to `examples/`,
12 showcase figures spanning hardware, systems, algorithms, theory, and ML.
