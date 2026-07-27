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
required fonts and glyph-path output is preferable. Outlining is
weight- and style-faithful: the export registers the resolved family's
bold / italic / bold-italic font files alongside the regular face and
outlines each text run with the face matching its `font-weight` /
`font-style`, so `weight="700"` and `italic=True` survive into the PDF
exactly as they render in the PNG.

Text measurement is metrics-based: `Theme.text_width` measures the
actual glyph advance widths of the resolved theme font (selecting the
real bold face for bold text), matching what the exporters render.
Long bold values therefore centre symmetrically inside `Card` /
`Column(align="center")` without per-figure padding workarounds.

## Layout primitives

Signatures at call sites:

```
Row(*children, gap="md", align="center", equal_widths=False, equal_heights=None, balance_outer=False)
Column(*children, gap="md", align="center")
WrapRow(*children, gap="sm", max_width=..., line_align="start", hang=0.0)
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
pieces read naturally. `align` takes `"start" | "center" | "end" |
"stretch"`; any other value raises `ValueError` (it used to degrade
silently to centring). `"stretch"` stretches the cross axis: `Row`
inflates every child to the tallest child's height so side-by-side
siblings (e.g. two `Panel`s) share one outer height, then top-aligns
them; `Column` inflates every child to the widest child's width so a
stacked spine of `Card`s or `Box`es shares one outer width, then
left-aligns them. Children that can grow (`Panel`, `Box`, `Card`) do;
leaf text is left at its natural size. Use it instead of padding shims
or hand-set uniform widths when adjacent framed siblings should line
up edge to edge -- a stretched `Panel` centres its content in the
enlarged box automatically.

**Sibling-frame rule.** A `Row` whose visible children are all *framed*
siblings (`Panel`, `Card`, `StepCell`) equalises their heights by
default, with no flags: side-by-side framed boxes of uneven height read
as an accident, never as information, so the library removes the
unevenness for you. Mixed rows (a panel next to a caption `Text`) are
left alone. `equal_heights=True` forces equalisation for unframed
children (e.g. two `Box`es); `equal_heights=False` opts a framed row
out. `align="stretch"` still implies equalisation for any row.

For a bilateral architecture or comparison with one semantic hub, use
`Row(left, hub, right, balance_outer=True)`. The outer systems receive equal
slots and pack inward while the hub stays on the exact figure centreline;
unequal left/right labels therefore cannot skew the whole composition.
Exactly three visible children participate (layout-invisible `Connect`
specifications do not count).

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

### WrapRow and Chip -- flowing runs of tags

`WrapRow` is the flow complement of `Row`: children run left-to-right
and wrap onto new lines within a width budget (`max_width`, defaulting
to the theme's word-wrap budget), so a variable-length run of small
peers consumes bounded width and grows downward instead of pushing the
figure wider. The budget is a wrap threshold, not a clip: a child wider
than the budget still gets its own line at natural width. `hang`
indents every line after the first, marking continuations of the run
above (e.g. citation chips that wrapped past their taxonomy leaf).

`Chip` is the tag it usually carries: a compact pill that hugs its
text. Where `Box` enforces a paper-node minimum silhouette so
structural nodes survive print reduction, a `Chip` stays visually
subordinate to the node it annotates -- citation tags, keywords,
counts, states.

```python
from sciviz import Box, Chip, Diagram, Palette, WrapRow

leaf = WrapRow(
    Box("ANN-to-SNN conversion", fill=Palette.violet.soft(),
        stroke=Palette.violet, text_size="small"),
    Chip("Rueckauer 2017", color=Palette.violet),
    Chip("QCFS", color=Palette.violet),
    gap="xs", max_width=180.0, hang="lg",
)
d = Diagram(title="taxonomy leaf", body=leaf)
```

Unlike `Row`, a `WrapRow` performs no sibling shape equalisation:
flow content keeps its intrinsic size so lines pack tightly.

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

`head` describes directionality rather than a drawing primitive: `True` or
`"end"` gives the usual destination arrowhead, `False` or `"none"` gives an
undirected line, `"start"` reverses the head, and `"both"` expresses a
bidirectional relationship. The same values work for inline and routed
connections, so authors never need arrow glyphs or paired one-way wires.

Routed wires keep a *clearance* margin from every card that is not one
of their own endpoints (default `theme.unit * 4/3`; pass
`clearance=<px>` to pin it). When a corridor is too narrow for the
full margin the router degrades it gradually instead of hugging card
borders, wires never ride co-linearly on top of an earlier wire when a
parallel lane exists, and perpendicular crossings render as hop arcs.
Obstacles are *ink-complete*: beyond anchors and regions, every
free-standing text run on the canvas (zone headers, captions, chips
that are not anchors) blocks wires and labels alike, so a routed wire
never runs through a title that happened not to be anchored.

**Labels are part of the route contract.** A wire whose arms cannot
carry its caption is not a valid wire, and three mechanisms enforce
that generically:

* *Corridor reservation.* Labeled flows between two facing pinned
  sides (`right` toward `left`, `bottom` toward `top`) reserve, before
  layout freezes, half the measured caption extent plus a gap on each
  facing margin, so the corridor as a whole is guaranteed to fit the
  caption. Any other side pairing implies a dog-leg whose long arm
  lives in shared space and reserves only the caption's smaller
  extent. Break long captions with `"\n"` -- connector labels are
  multi-line-aware and measure as blocks -- to keep corridors compact.
* *Capacity-aware routing.* The planner rejects candidate routes with
  no arm long and clear enough to host the caption (beside the arm,
  rotated along a vertical arm, or centred on the arm) while
  alternatives exist; clearance degrades before the caption's home is
  ever given up.
* *Two-phase placement with a halo fallback.* Wires draw first, then
  every label is placed against the complete set of wires, cards, free
  text, and earlier labels. In a corridor walled on both sides the
  label falls back to the schematic convention: centred on its own
  wire over a background halo. A placed label overlapping other ink is
  treated as an error (`tests/test_label_route_contract.py` locks the
  zero-overlap invariant).

Label orientation follows the wire: horizontal legs take horizontal
labels, and a vertical leg takes a 90-degree rotated label only when
the leg is long enough to genuinely carry the rotated text (leg length
>= label width plus clearance). Short vertical hops -- the card-to-card
gaps of a stacked column -- prefer a horizontal label beside the wire,
so sibling edges in one spine share one reading direction regardless of
label length; the other orientation remains a collision fallback either
way. Multi-line captions never prefer rotation regardless of leg
length: a block reads as stacked horizontal lines, and rotating it
yields parallel columns of tilted text. Routed-flow captions read at `Theme.connector_label_size`
(default `"small"`); dense multi-panel overviews may override it one
step down, e.g.
`Theme().with_overrides(connector_label_size="tiny")`. If a label still
collides, improve the semantic structure rather than nudging pixels.

Placement scoring is lexicographic and hugs the wire: a caption must
clear all ink (the hard invariant), stay within its own arm's span
(overhanging an endpoint or elbow is a last-resort demotion, never a
hard failure), sit on the convex side of a bent route (the outside of
the dog-leg, away from the route's own legs; straight routes keep the
caller's preference), satisfice clearance at one gap unit, and only
then settle as close to the arm's midpoint as possible -- surplus
breathing room never pulls a caption off its wire into whatever void
the canvas happens to have.

**Known limitation (proposed enhancement).** Captions are never
re-wrapped by the placer: a one-line caption beside a short vertical
leg keeps its authored width even when it protrudes far past the leg.
Auto-reflowing such captions at natural break points to match arm
proportions is a proposed future enhancement, deliberately deferred
because it would change caption typography globally. Until then, break
wide captions manually with `"\n"` -- multi-line captions measure as
blocks and reserve narrower corridors.

Bus geometry derives from the *flow direction* (source-cluster centroid
toward sink-cluster centroid), never from incidental cluster spread; the
spine sits in the clear inter-cluster gap. When a cluster is stacked
along the flow axis -- so straight taps would strike through sibling
endpoints -- the taps exit sideways onto a rail that runs alongside the
cluster and joins the spine once, and sink entries stay strictly
axis-aligned.

**Auto-routing is on by default.** Every `Connect` — routed, bus, and
inline — runs through the router by default (`auto_route=True`). Pass
`auto_route=False` to fall back to a straight segment (routed mode); the
flag is a no-op for bus/inline since those are axis-aligned by
construction. An explicit `style=` still wins, so existing calls that
pin `style="curve"` or `style="straight"` keep working.

Ports are selected from geometry rather than fixed midpoints. When two
parallel node faces overlap, the connector projects the narrower face onto
the wider one and uses one shared coordinate; aligned links therefore stay
straight. Fan-in/fan-out ports preserve those projections and separate only
when two wires would otherwise occupy the same attachment point.

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

## Grouping: Region, Brace, Captioned, Badge, Docked

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

### Docked overlays and tapered modules

`Docked` expresses a decoration that belongs on a node boundary or across a
node group. A center decoration may inherit the primary child's width/height
and sit at the upper, middle, or lower third. `Mux` provides a tapered module;
horizontal labels wrap from its semantic size rather than forcing authors to
pick a width:

```python
from sciviz import Box, Docked, Mux, Palette, Row, Diagram

modules = Row(Box("Video DiT"), Box("Action DiT"), gap="sm")
coupled = Docked(
    modules,
    center=Box("Cross-attention", fill=Palette.violet.soft(), stroke="none"),
    center_fit="width",
    center_position="lower",
)
encoder = Mux(
    "Unified Encoder",
    orientation="up",
    vertical_text=False,
    fill=Palette.violet.soft(),
    stroke=Palette.violet,
)
d = Diagram(title="coupled streams", body=Row(coupled, encoder))
```

## Charts and specialised primitives

```
Heatmap(grid, palette="blues")
MeshArray(rows, cols)
VectorTiles(n, color="primary")
StackedBoxes(children)
Pyramid(levels=[...])
Timeline([...])
Scatter(points, x_range=..., y_range=..., grid=True, annotations=[Annotate(...)])
LineChart([Series(points, ...), ...], x_label=..., y_label=..., annotations=[Annotate(...)])
Slopegraph([(label, before, after), ...], left_title=..., right_title=...)
BarChart(rows, orientation="horizontal")
GroupedBarChart([(title, [values], annotation), ...], series=[BarSeries(...), ...])
Table(rows, col_align=..., gap_x="md")
AlignedColumns(*groups, ...)
Tree(TreeNode(...))
```

### Grouped bars with negative, missing, or qualified values

`GroupedBarChart` group values accept plain numbers, `None`, or `Bar`.
Negative values grow downward from the zero baseline (extend the axis floor
with `y_min`, auto-derived when omitted); `None` renders an empty slot so a
series without a measurement keeps its slot alignment across groups; and
`Bar(value, caveat=True)` renders the *qualified* style — lightened fill with
a dashed series-coloured outline — for numbers that are not directly
comparable to their neighbours (subset evaluations, simulated rather than
measured results, projections). Pair a caveat bar with a `Legend` entry that
explains the qualifier.

```python
from sciviz import Bar, BarSeries, Diagram, GroupedBarChart

chart = GroupedBarChart(
    [("small model", [0.4, -0.1]),
     ("large model", [Bar(5.2), Bar(14.3, caveat=True)])],
    series=[BarSeries(name="method A", color="#1d3557"),
            BarSeries(name="method B", color="#e07a30")],
    y_min=-2.0, y_max=16.0, y_step=4.0,
    y_label="accuracy gap (percentage points)",
    show_cards=False, show_target_line=False, show_delta_arrow=False,
)
d = Diagram.for_paper(chart)
```

Pass `log_y=True` when the values span several orders of magnitude. Bars then
grow from the axis floor (`y_min`) with heights proportional to `log10(value)`,
ticks land on each decade, and `y_min`/`y_max` default to the decades that
bracket the data. All plotted values and targets must be strictly positive
(negative bars have no log); a positive `y_min` is required and accepted.

```python
GroupedBarChart(
    [("CIFAR-10", [61.9, 35.2, 6.92, 0.069]),
     ("CIFAR-100", [81.5, 258.0, 25.1, 0.084])],
    series=[BarSeries(color=c) for c in ("#b91c1c", "#b45309", "#0f766e", "#3b5fa0")],
    log_y=True, y_min=0.01, y_max=1000.0,
    y_label="spikes / inference (millions, log)",
    show_cards=False, show_target_line=False, show_delta_arrow=False,
)
```

### Structured matrices and shared color scales

Use `MatrixCell` when the number controlling colour is not the only text a
cell must show. A shared `ColorScale` keeps small multiples comparable;
`MatrixSelection` adds non-destructive, named outlines and `ColorBar` renders
the same scale as a measured element.

```python
from sciviz import ColorBar, ColorScale, Diagram, Matrix, MatrixCell, MatrixSelection, Row

scale = ColorScale((-1.0, 1.0), center=0.0)
matrix = Matrix(
    [[MatrixCell(-0.4, "18.2", "-0.4"), MatrixCell(0.7, "23.1", "+0.7")],
     [MatrixCell(0.1, "20.0", "+0.1"), MatrixCell(-0.2, "19.4", "-0.2")]],
    scale=scale,
    selections=[MatrixSelection(0, slice(0, 2), name="active", label="active row")],
    row_labels=["A", "B"], col_labels=["X", "Y"],
    col_label_position="bottom",
    cell_size="xl",
)
d = Diagram.for_paper(Row(matrix, ColorBar(scale, ticks=(-1, 0, 1))))
```

`cell_size` accepts the semantic density tokens `"micro"`, `"tiny"`, `"xs"`,
`"sm"`, `"md"`, `"lg"`, and `"xl"`. Prefer the token that communicates the
matrix's role: `"micro"`/`"tiny"` are intended for compact masks and
paper-scale matrix small multiples, while larger tokens leave room for richer
cell labels. Dense and categorical matrices retain contiguous square cells at
every token size.

`MatrixGroup` labels wrap to their own span (and shrink, with a floor, when a
single word cannot fit), so long group names claim extra header rows instead
of colliding with the neighbouring group.

Row labels may contain newlines: the first line is the label proper and
continuation lines render smaller and muted — sublabels for units,
provenance, or grounding detail (`"Fan-out per core\nLoihi: 4096 edges"`),
the same convention as multiline `Scatter` point labels. This keeps long
annotations from widening the label column at full label size. Column labels
stay single-line (they rotate instead).

### Coverage matrices with `HarveyBall`

For categorical coverage / completion judgments (full, partial, absent), put a
`HarveyBall` in each cell's `mark`: a fraction-filled disc that reads as a
solid dot at `1.0`, a half disc at `0.5`, and a quiet hollow ring at `0.0`.
Any fraction in `[0, 1]` works, so quarter states need no special casing.
Pair the glyphs with a `Legend` that reuses the exact same elements.

```python
from sciviz import Diagram, HarveyBall, Legend, LegendItem, Matrix, MatrixCell, Palette

def coverage(fraction):
    quiet = fraction == 0.0
    return HarveyBall(fraction, size=12.0,
                      color=Palette.gray if quiet else Palette.success,
                      ring=Palette.gray.soft() if quiet else Palette.success)

matrix = Matrix(
    [[MatrixCell(mark=coverage(f)) for f in row]
     for row in [[1.0, 0.5, 0.0], [0.0, 1.0, 1.0]]],
    row_labels=["constraint A", "constraint B"],
    col_labels=["m1", "m2", "m3"],
    cell_size="sm",
)
legend = Legend(
    LegendItem(coverage(1.0), "modeled"),
    LegendItem(coverage(0.5), "proxied"),
    LegendItem(coverage(0.0), "not reported"),
)
```

### Relational line charts and part-to-whole charts

Key line series when another encoding refers to them. `FillBetween` derives a
band over the shared domain and can derive a label at every shared sample from
the paired values. Markers, exact ticks, semantic plot sizes, and in-plot
legend placement remain series/chart data. `Series(marker_fill="hollow")`
draws open markers (the conventional encoding for derived/projected points
next to solid measured ones) and `Series(show_line=False)` makes a marker-only
overlay series, so one visible line can carry mixed point provenance;
`Annotate(..., dot=False)` pins a label to an existing marker without
stamping a second anchor dot; set `dot=False` also for free-floating notes
that reference no single datum. `Annotate` text may contain newlines
(lines stack downward) and `anchor="start"|"middle"|"end"` sets the text
anchor of every line. `Scatter` accepts the same `annotations` list, so
the two charts annotate as one family. A `Scatter` point label may also
contain newlines: the first line renders in the text colour and
continuation lines render muted — per-point detail (a measured value, a
caveat) under the point's name — and the whole block participates in
collision-aware placement.
`DonutChart` derives slice geometry and group summaries directly from `Part`
values.

```python
from sciviz import Diagram, FillBetween, LineChart, Series

chart = LineChart(
    [Series([(0, 1), (1, 2)], label="baseline", key="base", marker="circle"),
     Series([(0, 2), (1, 4)], label="adapted", key="adapt", marker="square")],
    fills=[FillBetween(
        "base", "adapt",
        labels=lambda _x, low, high: f"+{high - low:.1f}",
    )],
    x_range=(0, 1), y_range=(0, 4), x_ticks=(0, 1), y_ticks=(0, 2, 4),
    size="lg", legend="inside-bottom-right",
)
d = Diagram.for_paper(chart)
```

```python
from sciviz import Diagram, DonutChart, GroupSummary, Part

mix = DonutChart(
    [Part("small video", 40, group="video"),
     Part("large video", 40, group="video"),
     Part("image", 20, group="image")],
    center=GroupSummary(("video", "image"), label="video / image"),
)
d = Diagram.for_paper(mix)
```

### Slopegraphs (one measurement, two conditions)

`Slopegraph` compares paired values across exactly two conditions
(claimed/measured, before/after) with direct endpoint labels instead of
a y-axis. Per-record `color` / `dash` / `marker` encode record classes
(e.g. simulated vs measured evidence), `SlopeReference` draws a dotted
level such as an equivalence bound, and endpoint labels dodge
vertically -- coincident duplicates collapse into one. When dodging
pushes any label visibly off its endpoint (a tight value cluster),
that side's margin widens into a leader lane and thin record-coloured
elbow leaders connect *every* label on the side to its point -- a
uniform connector language, so a leader-less label can never be
misread -- with no author-side offsets.

```python
from sciviz import Diagram, SlopeRecord, SlopeReference, Slopegraph

chart = Slopegraph(
    [SlopeRecord("measured on silicon", 92.5, 91.9, color="blue"),
     SlopeRecord("cycle-accurate simulation", 94.1, 85.1,
                 color="amber", dash="4,3", marker="diamond",
                 annotation="(-9.0 pt)")],
    left_title="pre-deployment", right_title="deployed",
    value_format=".1f",
    references=[SlopeReference(90.0, label="target")],
)
d = Diagram.for_paper(chart)
```

### Semantic flow graphs and detail callouts

`FlowGraph` is for a whole DAG whose ranks, groups, ports, and exact edge
semantics should drive layout. Independent `FlowEdge` objects stay independent;
a list-valued endpoint explicitly requests a bus. Mark exceptional return paths
with `kind="feedback"` instead of choosing geometry.

```python
from sciviz import Diagram, FlowEdge, FlowGraph, FlowGroup, FlowNode

flow = FlowGraph(
    [FlowNode("db", "Trace DB", shape="store", group="sim"),
     FlowNode("run", "Execute", group="sim"),
     FlowNode("report", "Report", shape="document")],
    [FlowEdge("db", "run"), FlowEdge("run", "report")],
    groups=[FlowGroup("sim", label="Simulator")],
)
d = Diagram.for_paper(flow)
```

Pass `lanes=[...]` (with `direction="right"`) when the DAG has parallel tracks
that should read as straight horizontal bands rather than centred ranks: each
node's `lane` pins it to a band, empty `(lane, rank)` slots become air, and a
`lane=None` node spans the whole band stack -- the natural home for a shared
root or sink. `lane_labels` writes each band's name in the left gutter. This is
the form for lineage maps, roadmaps, and two-track comparisons.

```python
from sciviz import Diagram, FlowEdge, FlowGraph, FlowNode, Palette

flow = FlowGraph(
    [FlowNode("root", "Origin", lane=None, rank="r0", role=Palette.gray),
     FlowNode("a1", "Track A: step 1", lane="A", rank="r1", role=Palette.blue),
     FlowNode("a2", "Track A: step 2", lane="A", rank="r2", role=Palette.blue),
     FlowNode("b1", "Track B: step 1", lane="B", rank="r1", role=Palette.success),
     FlowNode("m", "Merge of A and B", lane="mid", rank="r2", role=Palette.violet)],
    [FlowEdge("root", "a1"), FlowEdge("root", "b1"), FlowEdge("a1", "a2"),
     FlowEdge("a1", "m"), FlowEdge("b1", "m")],
    lanes=["A", "mid", "B"],
    lane_labels={"A": "track A", "B": "track B"},
    rank_order=("r0", "r1", "r2"),
)
d = Diagram.for_paper(flow)
```

Use `DetailCallout` when a detail must remain semantically bound to one named
component inside an overview. The library chooses right/below placement and
routes a headless leader.

```python
from sciviz import Anchor, Box, DetailCallout, Diagram, Region, Row

overview = Region(Row(Anchor("sm0", Box("SM 0")), Box("SM")), label="GPU")
detail = Region(Box("Tensor cores + local memory"), label="Inside one SM")
d = Diagram.for_paper(DetailCallout(overview, detail, source="sm0"))
```

### LineChart with inline annotations

Axis ranges default to *automatic*: each omitted `x_range` / `y_range`
is fitted snugly to the data and snapped outward to a nice tick step,
so plots carry no dead whitespace and ticks land on round values. Pass
an explicit tuple only when the range itself is part of the message
(e.g. a shared scale across sibling panels); explicit ranges are always
honoured verbatim. Axis gutters are derived from the labels they hold:
the left pad is the measured width of the y tick labels (plus the title
band), and axis titles sit a fixed small gap from the nearest tick
label rather than a fixed distance from the axis, so the plot area
claims every pixel the labels do not need.

An inside legend corner (`legend="inside-top-right"` and friends) is a
*preference*, not a fixed position. The chart projects every series
segment, marker, and annotation into pixel space and checks the corner
box against that ink: a clear preferred corner is kept; a covered one
relocates to the first clear corner; when no corner is clear and the y
range is automatic, the chart keeps your corner and expands the range
headroom just enough for the legend to clear the data. Legends never
silently sit on data lines, and authors never pre-pad ranges to make
room for them. Inside legends run a slightly smaller font than tick
text and the headroom expansion snaps to half tick steps, so the
legend claims only a modest slice of the range rather than a large
empty band.

```python
from sciviz import LineChart, Series, Annotate, Diagram

chart = LineChart(
    [Series([(i, i*i) for i in range(10)], label="n^2", color="blue"),
     Series([(i, 5*i) for i in range(10)], label="5n", color="amber", dash="4,3")],
    size="md",
    x_label="n", y_label="cost",
    annotations=[Annotate(4, 16, "crossover", color="accent")],
    legend="inside-top-left",
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

`Tree` grows top-down by default; pass `orientation="right"` to grow
left-to-right (root at the left, deeper levels advancing rightward) — the
natural form for taxonomies whose node labels are wide text. `level_gap`
then spaces depths horizontally and `page_gap` stacks siblings vertically;
`level_labels` bands become vertical columns labelled along their top edge.

```python
from sciviz import Tree, Box, Diagram

taxonomy = Tree(
    Tree.node(Box("problem"), children=[
        Tree.node(Box("axis A"), children=[Tree.node(Box("family A1"))]),
        Tree.node(Box("axis B"), children=[Tree.node(Box("family B1"))]),
    ]),
    orientation="right",
)
d = Diagram(title="Taxonomy", body=taxonomy)
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
* "I want stacked cards the same width" -> `Column(..., align="stretch")`.
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

Legibility is checked absolutely, not just on overflow: with
`target_width_pt` set, the smallest text on the canvas is compared
against `min_effective_font_pt` (default 6 pt) at its effective printed
size, and a `UserWarning` fires when authored text sits below the floor
*even when the figure already fits the target width*. Theme size tokens
all clear the default floor -- `micro` is 7 pt, one point below `tiny`
on the same ladder -- so the warning only ever points at explicit raw
sizes.

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
