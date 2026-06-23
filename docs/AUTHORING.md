# Authoring sciviz diagrams

This is the single authoritative reference for `sciviz`. Skim it once to
see what the library offers; cherry-pick sections as you build figures.
Every code block below is executed by
[`tests/test_authoring_examples.py`](../tests/test_authoring_examples.py),
so everything you see here is guaranteed to keep running.

## Philosophy

* **Author intent, not coordinates.** You never type an `(x, y)`. You
  build a tree of elements; the library measures each element bottom-up
  and paints it top-down. Parents own placement.
* **One way to connect.** `Connect(src, dst, ...)` subsumes every
  arrow / bus / flow / labeled primitive we ever shipped. Mode is
  inferred from the shape of its arguments.
* **Semantic tokens.** Prefer `size="label"`, `gap="lg"`,
  `color="accent"`, `color="positive"` to hex values and explicit
  pixel counts. A single `Theme.slides()` can then re-skin a paper
  figure for a presentation.
* **Composition over configuration.** Every primitive is an
  `Element`; wrap with `Region`, `Captioned`, `Badge`, `Brace`, or
  your own subclass to add meaning, not arguments.

## Anatomy of a minimal figure

```python
from sciviz import Diagram, Row, Panel, Matrix, Math, Text

d = Diagram(
    title="My figure",
    subtitle="Subtitle (optional)",
    body=Row(
        Panel("a", "Input",  Matrix((8, 8))),
        Panel("b", "Output", Math(r"$y = Wx$")),
    ),
    footer=Text("Optional footer element."),
)
```

`Diagram` is the single export gate: it owns the title / footer band
and drives `.save("figure.svg" | ".pdf" | ".png")` and
`.save_all("figure")`.

For paper figures that already have a LaTeX caption, use:

```python
from sciviz import Diagram, Text

d = Diagram.for_paper(Text("Captioned body"))
```

This removes title/subtitle/footer chrome and uses a tighter content
margin. SVG, PDF, and PNG preserve the theme's live font stack by default.
Use `text_mode="outline"` only when a PDF toolchain cannot resolve the
required fonts and glyph-path output is preferable.

## Layout primitives

Signatures at call sites:

```
Row(*children, gap="md", align="center", equal_widths=False)
Column(*children, gap="md", align="center")
Panel(tag, title, child)
Grid(*children, cols=..., col_align=...)
AlignedStack(*children, axis="vertical", gap="md")
Spacer(w, h)
FixedSize(child, width=..., height=...)
Separator(length=..., orientation="horizontal", style="solid")
EqualGrid(*children, columns=3, equal="both")
BalancedColumns(*children, columns="auto", gap="md")
Card(header, body, role=Palette.blue)
Stripe(*items, role=Palette.blue)
StepCell("Activation Quantization", visual, role=Palette.red)
```

`Row` / `Column` filter out `None` children silently, so optional
pieces read naturally. `align` takes `"start" | "center" | "end"`,
plus `"stretch"` on `Row`: it inflates every child to the tallest
child's height so side-by-side siblings (e.g. two `Panel`s) share one
outer height, then top-aligns them. Children that can grow vertically
(`Panel`, `Box`) do; leaf text is left at its natural height. Use it
instead of padding shims when adjacent framed panels should line up
top and bottom -- the shorter `Panel` centres its content in the
enlarged box automatically.

### EqualGrid vs BalancedColumns

`EqualGrid` broadcasts one uniform cell to every child -- the right
tool when the children are peers of the same shape. `BalancedColumns`
is its complement for *unequal* children (cards of different heights):
children flow top-to-bottom, in declared order, into side-by-side
columns, and the container picks the contiguous split that minimises
the tallest column. Authors declare reading order and adjacency; the
library owns where the column breaks fall.

Both accept `columns=<int>` (fixed) or `columns="auto"`. On its own
`"auto"` means the square-ish default; combined with a diagram-level
`target_aspect` (see *Physical targets* below) it lets the target
fitter reflow the container -- redistribute the same children over a
different column count -- to land the figure in the requested printed
shape.

### AlignedStack -- cross-parent column alignment

When you stack rows or grids that should share column widths across
*different parents* (e.g. a schedule over two pipeline stages),
wrap them in `AlignedStack` instead of hand-computing widths:

```python
from sciviz import AlignedStack, Table, Box, Diagram, Text

def row(a, b, c):
    return Table(
        [[Box(Text(a), width=60), Box(Text(b), width=60), Box(Text(c), width=60)]],
        col_align=("center", "center", "center"),
        gap_x="sm",
    )

body = AlignedStack(
    row("load", "fwd", "wait"),
    row("load large batch", "fwd", "bwd"),
    gap="sm",
)
d = Diagram(title="Aligned schedule", body=body)
```

`AlignedStack` does a two-pass measure: it collects every participant's
per-column width, broadcasts the max back, and tells each child to
re-measure with the shared widths. Participants are `Table`, `Row`,
and the named-row `Grid`. Children that don't expose column widths
simply stack normally.

### Semantic cards and step cells

For compact pipeline or architecture diagrams, prefer the compound
primitives over hand-sized boxes:

```python
from sciviz import Card, EqualGrid, MiniMatrix, Palette, StepCell, Stripe

phase = Card(
    "Quantization",
    Stripe(
        StepCell("Activation Quantization", MiniMatrix(role=Palette.red), role=Palette.red),
        StepCell("Weight Quantization", MiniMatrix(role=Palette.red), role=Palette.red),
        role=Palette.red,
    ),
    role=Palette.red,
)
body = EqualGrid(phase, columns=1, equal="both")
```

`StepCell` wraps full names, reserves room for a thumbnail, and displays
conditional structure with a `ConditionGlyph` rather than code-like text
such as `if act_q`.

### Separator

A thin rule that stretches to fill its container's main axis. Perfect
for release-note dividers or group separators inside a `Column`:

```python
from sciviz import Column, Row, Separator, Text, Diagram

body = Column(
    Text("Added"),
    Separator(orientation="horizontal", style="dashed"),
    Text("Changed"),
    gap="sm", align="start",
)
d = Diagram(title="Changelog", body=body)
```

A `Separator` inside a `Row` defaults to vertical; inside a `Column`,
to horizontal. You can pin it explicitly with `orientation=`, and
`style="solid" | "dashed" | "dotted"`.

## Text, math, and inline styled runs

Signatures:

```
Text("caption",  size="label", color="muted", weight="700")
TextBlock("multi\nline paragraph", max_width=280, line_spacing=1.35)
Math(r"$\hat y = \mathrm{softmax}(Wx)$")
Inline("The energy ", "$E = mc^2$", " is conserved.")
```

`Inline` splices text and inline math on a shared baseline; strings
beginning and ending with `$` auto-coerce to `Math`.

### Structured runs with `Span`

Both `Text` and `TextBlock` accept a list of runs instead of a plain
string. Each run is either a string or a `Span(...)` carrying inline
style overrides (`color`, `size`, `weight`, `italic`):

```python
from sciviz import Text, Span, Diagram, Column

label = Text([
    "compute = ",
    Span("312", color="primary", weight="700"),
    " ",
    Span("TFLOP/s", color="muted", size="small"),
])
d = Diagram(title="Run example", body=Column(label))
```

Structured runs keep the whole line on one baseline (SVG `<tspan>`)
and participate in width/height measurement like plain text. They
replace the "box around one coloured phrase" pattern you might have
used before.

## Icons and images

`sciviz.Icon` renders a bundled stroke-only
[Lucide](https://lucide.dev) pictogram (MIT-licensed) at any requested
size. Colours resolve through the theme:

```python
from sciviz import Icon, Text, Column, Row, Diagram

def chip(name, label, color):
    return Column(Icon(name, size=28, color=color), Text(label), gap="sm", align="center")

body = Row(chip("cpu", "compute", "primary"),
           chip("database", "memory", "accent"),
           chip("shield", "policy", "amber"))
d = Diagram(title="Icons", body=body)
```

`sciviz.Image` embeds raster (PNG/JPEG) or vector (SVG) content via a
`data:` URI. It sniffs intrinsic dimensions so you can pass just a
width and get correct aspect ratio:

```python
from sciviz import Image, Diagram

svg = (b'<?xml version="1.0" encoding="UTF-8"?>'
       b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" '
       b'width="80" height="80">'
       b'<circle cx="40" cy="40" r="30" fill="#1e3a8a"/></svg>')
d = Diagram(title="Embed", body=Image(svg, width=80))
```

## Connecting things

`Connect(src, dst, ...)` replaces `Arrow`, `Connector`, `Flow`,
`Flowed`, `Bus`, and `Labeled`. Mode is inferred:

| Shape                                           | Mode     |
|-------------------------------------------------|----------|
| `Connect()` *(no src/dst)*                      | inline   |
| `Connect(src="a_anchor", dst="b_anchor")`       | routed   |
| `Connect([s1, s2, s3], dst="sink")`             | bus      |
| `Connect(src="src_anchor", dst=["d1", "d2"])`   | bus      |
| `Connect.labeled(source_element, label_element)`| labeled  |

Inline example (a bare arrow between neighbours in a Row):

```python
from sciviz import Row, Box, Connect, Diagram
body = Row(Box("input"), Connect(direction="right"), Box("output"))
d = Diagram(title="inline", body=body)
```

Routed example (a wire between two named anchors):

```python
from sciviz import Row, Anchor, Box, Connect, Diagram
body = Row(
    Anchor("a", Box("alpha")),
    Anchor("b", Box("beta")),
    Connect("a", "b", label="alpha \u2192 beta"),
)
d = Diagram(title="routed", body=body)
```

Bus example (many sources fan into one sink):

```python
from sciviz import Row, Anchor, Box, Connect, Diagram
body = Row(
    Anchor("t1", Box("a")),
    Anchor("t2", Box("b")),
    Anchor("t3", Box("c")),
    Anchor("sink", Box("out")),
    Connect(["t1", "t2", "t3"], "sink", label="concat", head=False),
)
d = Diagram(title="bus", body=body)
```

Every `Connect` accepts `color`, `label`, `label_color`, `dashed`,
`curvature`, `head`. Defaults are picked so a plain `Connect("a", "b")`
looks right in paper style.

Routed wires keep a *clearance* margin from every card that is not one
of their own endpoints (default `theme.unit * 4/3`; pass
`clearance=<px>` to pin it). When a corridor is too narrow for the
full margin the router degrades it gradually instead of hugging card
borders, wires never ride co-linearly on top of an earlier wire when a
parallel lane exists, and perpendicular crossings render as hop arcs.
Labels offset from the wire and dodge cards, other labels, and other
wires automatically -- on short vertical hops where a rotated label
cannot fit, a horizontal label beside the wire is used instead. If a
label still collides, improve the semantic structure rather than
nudging pixels.

**Auto-routing is on by default.** Every `Connect` — routed, bus, and
inline — runs through the router by default (`auto_route=True`). Pass
`auto_route=False` to fall back to a straight segment (routed mode); the
flag is a no-op for bus/inline since those are axis-aligned by
construction. An explicit `style=` still wins, so existing calls that
pin `style="curve"` or `style="straight"` keep working.

## Anchors

Wrap an element in `Anchor("name", element)` to give the connector
system a stable handle. The anchor tracks the child's rendered bbox
no matter how deeply the child is nested, and `Connect` reserves
margin for the wire automatically.

```python
from sciviz import Row, Anchor, Panel, Matrix, Math, Connect, Diagram

body = Row(
    Anchor("encode", Panel("a", "Encoder", Matrix((4, 4)))),
    Anchor("decode", Panel("b", "Decoder", Math(r"$Wx + b$"))),
    Connect("encode", "decode", label="latents"),
)
d = Diagram(title="anchors", body=body)
```

## Grouping: Region, Brace, Captioned, Badge

### Region -- labeled bordered container

`Region(child, label="...", ...)` draws a dashed border around a child
with the label above it (default) or on any side. It supports
`annotations=` for short notes outside the border and `corner_badge=`
for a stickered element:

```python
from sciviz import Region, Box, Text, Diagram

panel = Region(
    Box("core logic"),
    label="Forward",
    label_position="top",
    annotations=[("right", "dominated by GEMM"),
                 ("bottom", "see appendix A")],
    corner_badge=Text("new", color="white", size="tiny"),
)
d = Diagram(title="region", body=panel)
```

`label_position` is `"top"` (default), `"left"`, `"right"`, or
`"bottom"`. Annotations live on any side and wrap a short italic line
of text outside the border. A corner badge is any `Element`, drawn in
the top-right corner.

### Brace -- span a group

Two forms:

```python
from sciviz import Brace, Row, Box, Diagram, Column

# Explicit span
b1 = Brace(200, label="group")

# Self-sizing: brace follows its child's width at measure time.
row = Row(Box("A"), Box("B"), Box("C"), gap="lg")
b2 = Brace.spanning(row, label="shared")
d = Diagram(title="brace", body=Column(row, b2, gap="sm", align="center"))
```

`Brace.spanning` defers the width lookup until measure time, so you
can freely compose the braced group inside an `AlignedStack` or a
`Row(equal_widths=True)` without hand-computing pixels.

### Captioned / Badge / LabeledChain

```python
from sciviz import Captioned, LabeledChain, Badge, Box, Text, Diagram

cap = Captioned(Box("x"), title="FORWARD", title_color="primary")
chain = LabeledChain(
    [Box("attn"), Box("mlp")],
    top_labels=["mixer", "channel mixer"],
)
badge = Badge("+")
d = Diagram(title="wrappers", body=cap)
```

## Charts and specialised primitives

```
Heatmap(grid, palette="blues")
MeshArray(rows, cols)
VectorTiles(n, color="primary")
StackedBoxes(children)
Pyramid(levels=[...])
Timeline([...])
Scatter(points, x_range=..., y_range=..., grid=True)
LineChart([Series(points, ...), ...], x_label=..., y_label=..., annotations=[Annotate(...)])
BarChart(rows, orientation="horizontal")
Table(rows, col_align=..., gap_x="md")
AlignedColumns(*groups, ...)
Tree(TreeNode(...))
```

### LineChart with inline annotations

```python
from sciviz import LineChart, Series, Annotate, Diagram

chart = LineChart(
    [Series([(i, i*i) for i in range(10)], label="n^2", color="blue"),
     Series([(i, 5*i) for i in range(10)], label="5n", color="amber", dash="4,3")],
    x_range=(0, 9), y_range=(0, 80),
    width=260, height=160,
    x_label="n", y_label="cost",
    annotations=[Annotate(4, 16, "crossover", color="accent")],
    legend="right",
)
d = Diagram(title="LineChart", body=chart)
```

### Tree with per-edge style

`Tree` takes *elements* as nodes. Edges carry their own colour, style,
and label:

```python
from sciviz import Tree, Box, Text, Diagram

tree = Tree(Tree.node(
    Text("root"),
    children=[
        (Tree.node(Box("keep")),  {"color": "positive", "label": "accept"}),
        (Tree.node(Box("drop")),  {"color": "negative",
                                    "label": "reject",
                                    "style": "dashed"}),
    ],
))
d = Diagram(title="Tree", body=tree)
```

`NodeTree` stays available for compact multi-cell tree pages
(e.g. a B+-tree diagram); reach for it when the "node" is really a
row of cells. For arbitrary element nodes, prefer `Tree`.

## Colour

```python
from sciviz import Palette, Theme

blue = Palette.blue
soft = Palette.success.soft()
stable = Palette.next("worker_0")
custom = Palette.literal("#8b5cf6")

theme = Theme.slides()
theme = Theme().with_overrides(unit=8.0)
```

`Palette.next(key)` is idempotent: the same key always returns the
same colour within a process, so cross-panel consistency is free.

### Semantic roles

Use role strings where you want meaning over hue:

| Name       | Meaning                          |
|------------|----------------------------------|
| `primary`  | Default foreground accent        |
| `accent`   | Secondary accent (emerald)       |
| `highlight`| Strong attention marker (red)    |
| `muted`    | Low-contrast auxiliary text      |
| `positive` | Success / accept (emerald)       |
| `negative` | Failure / reject (red)           |
| `warning`  | Caution (amber)                  |
| `info`     | Informational (blue)             |

`Theme.role("positive", variant="fill" | "soft" | "stroke" | "ink")`
returns a coordinated shade family; this is what the theme uses
internally to pick tint colours for `Region.fill`,
`Box(fill=...)`, etc.

## When you actually need manual placement

Avoid it. Ninety-five percent of the time the answer is:

* "I want these things centred" -> `Row(align="center")`.
* "I want two things at the same vertical axis" -> `Column(align="center")`.
* "I want equal-width cells" -> `Row(..., equal_widths=True)` or `LabeledChain`.
* "I want side-by-side panels the same height" -> `Row(..., align="stretch")`.
* "I want shared column widths across rows" -> `Grid`.
* "I want shared column widths across *different parents*" -> `AlignedStack`.
* "I want a rule between sections" -> `Separator`.
* "I want a brace that matches this group's width" -> `Brace.spanning(...)`.
* "I want an annotated rectangle" -> `Region(..., annotations=..., corner_badge=...)`.
* "I want decorative arrows" -> `Connect` (inline / routed / bus).

If you still need a custom layout, subclass `Element` and implement
`measure(theme)` + `render(canvas, x, y, theme)`; containment is the
only rule.

## Exporting

```python
from sciviz import Diagram, Text

d = Diagram(title="hi", body=Text("hello"))
d.save_all("out/hello")
```

`save_all(base)` writes `base.svg`, `base.pdf`, and `base.png` in one
call. Individual formats are `save("x.svg")`, `save("x.pdf")`,
`save("x.png")`. PNG export uses `cairosvg` and inherits glyph
fallback from the theme's `font_family` stack.

### Physical targets

Paper figures declare the physical size they will occupy and let the
fitter do the layout work:

```python
from sciviz import Box, Card, Diagram, EqualGrid, Palette, card_header

cards = [Card(card_header(f"Slot {i}"),
              Box("chip", fill=Palette.blue.soft(), stroke=Palette.blue),
              role=Palette.blue) for i in range(6)]
d = Diagram.for_paper(EqualGrid(*cards, columns="auto"),
                      target_width_pt=252.0,            # IEEE column
                      target_aspect=(1.0, 1.3))
```

`target_width_pt` makes theme font tokens mean *final printed points*:
spacing, padding, and wrap budgets compress (fonts never shrink) until
the exported canvas width approaches the target, and a canvas within
half a point of the target is snapped to exactly the target (widened
when under; trimmed by a sub-point sliver of outer margin when the
density fixed-point leaves it a hair over), so `\includegraphics`
scales by exactly 1.0. Spacing density never compresses below its
cramped-padding floor; if the canvas is still over the target there,
the fitter keeps going on the text wrap budget alone
(`Theme.wrap_budget`, consumed by `Box(wrap=True)`): labels re-wrap
onto more lines at their authored font size, bounded by each label's
longest-word floor. Boxes inflated to wider slots by sibling
equalisation re-wrap their labels to the width they were actually
given, so equalised cells fill rather than centre a narrow text
column. The trial measurements are ink-aware -- routed wires, their
labels, and margin detours count toward the footprint.

`target_aspect` (height/width, a `(lo, hi)` range or a single
height-cap float) additionally balances the layout toward the printed
shape: the fitter explores every `columns="auto"` reflow variant and a
small grid of spacing densities, ranking candidates by width fit
first, then aspect, then least compression. Without it a multi-card
figure can satisfy the width as one degenerate tall corridor; with it
the balanced arrangement wins whenever one exists at the authored font
sizes. If the content cannot reach the requested shape, the fitter
returns the closest feasible layout -- it never trades fonts for
geometry.
