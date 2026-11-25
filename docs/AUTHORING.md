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

`text_mode="hybrid"` prints exactly what `outline` prints and additionally
lays an all-but-transparent copy of the original text over the glyph paths,
so the PDF is selectable, searchable and readable by a screen reader while
printing the reviewed geometry. That copy would otherwise be laid out by the
converter's own font, which drifts off the ink it covers; every character is
therefore placed at the x its own outlined glyph occupies, so a selection
starts and ends where the printed word does.

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
Panel(tag, title, child, content_align="auto")
Grid(*children, cols=..., col_align=...)
AlignedStack(*children, axis="vertical", gap="md")
SizeGroup(axis="width").add(child)
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
leaf text is left at its natural size. A stretched `Column` co-locates
*painted faces*: a flow-lane margin declared by one `Anchor` (e.g. a
feedback corridor down the left of a spine) offsets every sibling's
face past it, so the corridor is a real column-level lane -- wires
routed in it clear all cards, and the stacked faces (hence their
connector ports) stay collinear. Use it instead of padding shims
or hand-set uniform widths when adjacent framed siblings should line
up edge to edge -- a stretched `Panel` centres its content in the
enlarged box automatically.

**Panel content alignment.** A peer-matched `Panel` is taller than its
own content, and `content_align` says where the child sits in that
surplus. The `"auto"` default pins a *structural* body (a Column/Card
stack) to the content top so comparative panels share a first-row
baseline, while compact leaf visuals centre. When the panels hold
**independent** diagrams -- row i of one means nothing to row i of the
other -- declare `content_align="center"`; sciviz cannot infer
correspondence from structure alone. `"start"` / `"end"` pin
explicitly, and an unknown value raises `ValueError`.

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

### Table -- a typeset table, not a grid of boxes

A comparison that reads as a table in the paper should look like one in
the figure: a bold header row ruled beneath, hairline rules between rows,
text set directly in its column (no box per cell), and one banded row
when a single entry is the point. `Table` carries that furniture as
options over its aligned grid, so the same primitive serves a plain
aligned layout and a finished table:

```python
from sciviz import Diagram, Palette, Table

rows = [["Method", "Feedback", "Topology"],
        ["H-SR", "gate verdict + timing", "serial chain, keep best"],
        ["H-BoN", "none", "parallel, global best"],
        ["CASCADE", "staged gates + incumbent delta", "seed 4, then serial"]]
d = Diagram.for_paper(Table(
    rows,
    header=True,                 # bold header, ruled beneath
    rules="all",                 # hairlines between body rows too
    col_widths=[48, 70, 70],     # wrap budgets: long cells wrap in place
    row_align="start",           # wrapped cells align at the top
    pad_y=1.5,                   # room between a band and its text
    row_fills={3: Palette.orange.soft()},   # the highlighted row
), target_width_pt=252)
```

String cells become `Text`, or a wrapped `TextBlock` in a column with a
budget; `column_styles` sets their size and colour per column. Element
cells (a `Column` of name over source, a `TextBlock` with `Chip` tags
beneath) pass through unchanged. `zebra=` tints every second body row
instead of, or as well as, `row_fills`.

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

### SizeGroup -- one shared size for blocks in different parents

`MatchSize` equalizes children it lays out itself, so it only reaches
siblings inside one container. The blocks that most need equalizing
usually are not: one per row of a `Table`, one per cell of a `Grid`,
one per branch of a tree. Auto-sized blocks in that position come out
ragged -- each as wide as its own longest word -- and a column of
ragged blocks reads as unrelated objects rather than as rungs of one
ladder.

A `SizeGroup` is the membership those blocks are missing. Register each
block and place what `add` returns:

```python
from sciviz import Box, Diagram, SizeGroup, Table, TextBlock

ladder = [(2, "Analytic cost model", "Counts times per-operation costs."),
          (1, "Algorithmic proxy", "Operation counts and spike counts.")]

rungs = SizeGroup()                        # axis="width" (default)
rows = [[rungs.add(Box(title=f"Rung {n}", label=name,
                       wrap=True, max_width=90)),
         TextBlock(reports, max_width=160)]
        for n, name, reports in ladder]
d = Diagram.for_paper(Table(rows, col_align=("start", "start"),
                            row_align="start"))
```

Every member then renders at the widest member's width, so the column
aligns on both edges. `axis="height"` equalizes heights instead (blocks
laid out in a row), and `axis="both"` gives one silhouette. `group(box)`
is shorthand for `group.add(box)`.

Members are grown with the same `inflate_to` request `align="stretch"`
uses, so a member that cannot grow (leaf text) is left at its natural
size rather than centred in an empty slot, and the shared size is
resolved against the theme that measures the figure -- a group inside a
`Diagram` fitted to `target_width_pt` equalizes at the geometry the
figure actually prints.

Reach for `AlignedStack` when whole *rows* must share a column grid, and
for `SizeGroup` when a set of individual blocks must share one size.

### Deliberate negative space: `justify` and `grow`

When a parent grants a `Column` more height than its content needs --
most commonly `Row(align="stretch")` equalising the zones of a
multi-zone overview -- the surplus is laid out deliberately instead of
pooling below whatever content happened to stop first:

- `justify="between"` (default, historical behaviour): surplus grows
  the existing gaps; the first child stays pinned to the top edge and
  the last to the bottom.
- `justify="start" | "center" | "end"`: the block packs to the top,
  centre, or bottom of the granted frame with natural gaps.
- `grow=True` marks the child column that absorbs the parent's surplus
  *before* any gap distribution.
- `Row(..., grow=True)` marks a child *row* the same way: a band of
  cards under a heading takes the column's surplus height, and with
  `align="stretch"` its cards grow to it (default `False`).

The canonical zone grammar combines them:

```python
def zone(title, *content, justify="between"):
    return Column(
        Text(title.upper(), size="tiny", weight="800"),
        Column(*content, gap="md", align="center",
               grow=True, justify=justify),
        gap="sm", align="center",
    )

body = Row(
    zone("Boundary",
         Box("ports", width=70, height=90),
         Box("adapters", width=70, height=30)),
    zone("Core", Box("staged loop", width=90, height=200)),
    zone("Evidence", Box("sealed stack", width=70, height=80),
         justify="center"),
    gap="lg", align="stretch",
)
```

Headers stay on one shared top band; each zone's content column owns
the zone's remaining height and distributes its whitespace (spread for
a multi-block zone, optically centred for a lone card). This replaces
`Spacer` shims and hand-tuned gaps for balancing multi-column figures.

### Justified rows, non-grid columns, and wire lanes

`Row(justify=...)` places the surplus of a row that was granted more
width than it needs (a stretched column, an inflated card): `"start"`
(default), `"center"`, `"end"`, or `"between"` -- a name flush left and
its note flush right, with no spacer. A justified row is a layout of its
own, so it neither offers nor accepts shared grid columns.

Stacked rows of the same shape line up as one grid by default. A column
whose children are *not* a grid -- a station title over its picture, a
caption over a chart -- says so with `Column(share_columns=False)`, and a
two-part title row is then never stretched onto an unrelated two-part
row below it.

A wire that attaches to a title reserves a corridor (a flow lane) above
it. Columns and rows report those lanes (`flow_lanes`) and exclude them
from their `content_bbox`, so a `Row(align="start")` of stations keeps
every title level and runs the corridor above all of them -- also when
the wired element is a small badge centred beside a taller title.

```python
from sciviz import (Anchor, Badge, Box, Column, Connect, Diagram, Row,
                    Text)

def station(n, title, wired=None):
    badge = Badge(n)
    if wired:
        badge = Anchor(wired, badge)
    head = Row(badge, Text(title, weight="700"), gap="xs", align="center")
    return Column(head, Box("picture", width=60, height=30), gap="sm",
                  align="start", share_columns=False)

note = Row(Text("Sample batches", weight="700"),
           Text("every 2nd day", color="muted"),
           justify="between", gap="xs")
body = Column(
    Row(Column(note, Box("a wider slip sets the width", width=170),
               align="stretch", share_columns=False),
        station("4", "Mixing", "mixing"), station("5", "Assay", "assay"),
        gap="md", align="start"),
    Connect("mixing", "assay", src_side="top", dst_side="top",
            label="measured", label_style="on-wire"))
d = Diagram.for_paper(body)
```

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

A `Stripe` becomes a *slip* with `surface="white"`: an excerpt set off
from a tinted container by its own page-coloured ground, the rail naming
whose it is; `outline=False` drops the frame and `align="start"` sets its
lines flush left. `Document(padding="md")` gives a sheet that carries a
page of content (a quote, headed sections) a page margin; the default
`"sm"` suits a short centred name.

### Titled blocks

A block that carries both a name and a description should not fold them
into one string. `Box(title=...)` heads the block with a line of its own:

```python
from sciviz import Box

block = Box(title="Rung 4", label="Cycle-accurate simulation",
            wrap=True, max_width=90, text_size="small")
```

The title is drawn above the label, bold by default, and it takes part
in the box's wrapping and auto-sizing -- so a titled block still grows to
fit rather than overflowing. `title_size`, `title_weight` and
`title_color` override the defaults (the title inherits the label's size
and colour otherwise). Written as one string, `"Rung 4: Cycle-accurate
simulation"` lets the wrap decide where the name ends, and the name lands
mid-line; as a title it always heads the block. A `Card` remains the
right choice when the body is an element rather than a line of text and
the block wants a filled header band.

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

### Short labels in boxes: centring by ink

A text engine centres a string by its advance box and its line box, not by its ink. A running label never shows
the difference. A short label in a small box does (a step number in a cell, a core's name in a tile, a tag in a
badge): a digit sits low or high by a visible share of the box's padding, and "L1" sits left of the centre.
`Text("2", weight="700", ink_center=True)` draws a plain one-line label with the centre of its glyph outlines on
the centre of its measured box, in both directions, and reports that ink as its content box. The default,
`ink_center=False`, draws every text exactly as before. A figure drawn with matplotlib beside the diagrams has
the same rule: `from sciviz.inkcenter import center_on_ink`, then `center_on_ink(ax.text(x, y, "2", ...))` puts
the label's ink on `(x, y)`. `horizontal=False` or `vertical=False` keeps one direction's own alignment, and
`ref="H"` centres a word by its capitals, so a row of labels shares one baseline.

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
  ever given up. The search is cost-bounded
  (`CrossPolicy.label_detour_ratio`, default 2.0): a caption-feasible
  route wins only while it is not disproportionately longer than the
  label-free route, so a tight layout (e.g. a compressed paper theme)
  produces a direct wire with a halo label, never a runaway sweep
  hunting for an arm (`tests/test_route_label_containment.py`).
* *Two-phase placement with a halo fallback.* Wires draw first, then
  every label is placed against the complete set of wires, cards, free
  text, and earlier labels. In a corridor walled on both sides the
  label falls back to the schematic convention: centred on its own
  wire over a background halo. A placed label overlapping other ink is
  treated as an error (`tests/test_label_route_contract.py` locks the
  zero-overlap invariant).
* *Region containment.* A framed container that registers itself as a
  routing region (`Panel` does) is a hard boundary for the wires it
  contains -- and for their captions: the placer treats the innermost
  region enclosing both endpoints as bounds, so a label near a panel
  frame stays inside the frame (falling back to the on-wire halo, and
  clamping as a last resort) instead of escaping into a neighbouring
  panel's territory.

Label orientation follows the wire: horizontal legs take horizontal
labels, and a vertical leg takes a 90-degree rotated label only when
the leg is long enough to genuinely carry the rotated text (leg length
>= label width plus clearance). Short vertical hops -- the card-to-card
gaps of a stacked column -- prefer a horizontal label beside the wire,
so sibling edges in one spine share one reading direction regardless of
label length; the other orientation remains a collision fallback either
way. Multi-line captions never prefer rotation regardless of leg
length: a block reads as stacked horizontal lines, and rotating it
yields parallel columns of tilted text.

**The rotated-label wrap budget.** Rotation turns the arm into the
caption's whole reading width, so the arm is its wrap budget and the
caption is re-set to *that* arm before the arm is judged. A run long
enough to carry the words gets them back on one line even when an
earlier, narrower corridor folded them -- a caption folded for a place
it no longer occupies is a stale layout decision, and the placer is the
last party that knows which arm the caption ended up on. An arm that
cannot carry them on one line forfeits rotation entirely and the caption
stays upright beside the wire, because a rotated block is not reading
matter in any orientation. Authored `"\n"` is exempt from both halves:
a break you wrote is content, so it is never reflowed and never tilted.
The placer reports what it set on `PlacedLabel.text`; renderers draw
that rather than the string they passed in. Routed-flow captions read at `Theme.connector_label_size`
(default `"small"`); dense multi-panel overviews may override it one
step down, e.g.
`Theme().with_overrides(connector_label_size="tiny")`. If a label still
collides, improve the semantic structure rather than nudging pixels.
`Connect(..., label_frame="capsule")` (or, for every wire of a figure,
`Theme.connector_label_frame="capsule"`) sets a caption as data tokens:
each authored line becomes its own pill in `Theme.label_capsule_fill` /
`label_capsule_stroke`, drawn exactly like a `Chip` of the same size, so
`"count\nsize"` stacks two pills; capsules are never re-wrapped or turned.
`Theme.chip_pad_x` / `chip_pad_y` (fractions of the font size) set the
padding of chips and capsules alike. Arrow weight and head size are the
theme's `connector` (stroke) and `arrow_size` (head, times the stroke).

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

### Facing ports and captions on the wire

`Connect(..., ports="facing")` attaches each end in the half of its side
that faces the other end, so a wire leaving the top of a card toward a
neighbour leaves from the neighbour's side (shorter, and clear of a title
over the far half). `label_style="on-wire"` sets the caption centred on
its own wire over a page-coloured halo, the schematic convention: the
caption costs its own lane rather than a lane beside it. Stacked on-wire
lanes are kept a caption's height apart, and a same-side U route (top to
top, bottom to bottom) runs its bridge in the corridor its stubs reserved
for the caption instead of a step further out. When no leg can carry the
caption it falls back to the beside placement.

```python
from sciviz import Anchor, Box, Column, Connect, Diagram, Row

body = Column(
    Row(Anchor("model", Box("control model", width=90, height=30)),
        Box("filter", width=60, height=30),
        Anchor("gauge", Box("gauge", width=50, height=30)),
        Anchor("pump", Box("pump", width=50, height=30)), gap="lg"),
    Connect("gauge", "model", src_side="top", dst_side="top",
            ports="facing", label="measured level, flow",
            label_style="on-wire"),
    Connect("model", "pump", src_side="top", dst_side="top",
            ports="facing", label="setpoint per zone",
            label_style="on-wire"))
d = Diagram.for_paper(body)
```

### Body ports, inner landings and gutters

A wire lands on an element's *drawing*, not on the edge of a box its own
captions widened: `Element.port_bbox(theme, side)` returns that body (a
`Funnel` returns its taper; `Labeled` its source box), `Anchor` forwards it,
and the connector moves only the tap -- the layout box stays the obstacle.
When the run from the body out to the layout edge would cross the
element's own text or drawing (a funnel's bypass caption), that side keeps
the layout box. A custom element with decorations overrides `port_bbox`;
a wrapper forwards it.

To meet a card at one of its inner parts (a numbered badge, a row), name
the card as the endpoint and the part with `dst_at=` / `src_at=`: the
arrow lands on the card's frame level with the part and never crosses
into the card.

A bridge between two ends runs in the middle of its gutter (the free
interval between real walls, bounded on both sides), a second wire sharing
the gutter takes an even track, and no two wires ride on one line. A beside
caption never sits nearer another wire than its own; an on-wire caption
covers at most half its leg.

```python
from sciviz import Anchor, Box, Column, Connect, Diagram, Region, Row, Text

card = Anchor("station", Region(Column(Text("Station 5", weight="700"),
                                       Anchor("station_body", Box("body")),
                                       gap="sm"), fill="white"))
body = Column(
    Row(Anchor("request", Box("request")), Box("other"), gap="lg"),
    Row(Box("left"), card, gap="lg"),
    Connect("request", "station", src_side="bottom", dst_side="top",
            dst_at="station_body"),
    gap="lg")
d = Diagram.for_paper(body)
```

### Caption side, funnel outlets, bounded routes and bus hops

Sibling wires that cross one gutter read as a set when their captions
share a side. `label_side` takes the vocabulary of `Arrow`:
`"left"`/`"right"` set the caption upright beside a vertical leg,
`"above"`/`"below"` beside a horizontal one, and `"auto"` (the default)
lets the placer choose per wire.

```python
from sciviz import Anchor, Box, Column, Connect, Diagram, Row
tiers = Column(
    Row(Anchor("m", Box("planner")), Anchor("n", Box("log")), gap="xl"),
    Row(Anchor("a", Box("controller")), Anchor("b", Box("sensor")), gap="xl"),
    Connect("m", "a", src_side="bottom", dst_side="top",
            label="commands", label_side="right"),
    Connect("b", "n", src_side="top", dst_side="bottom",
            label="readings", label_side="right"),
    gap="lg")
d = Diagram.for_paper(tiers)
```

The layout reserves room beside each pinned end of a wire for its shaft
(a caption-sized corridor when the wire is labelled).
`Connect(..., src_room=, dst_room=)` sets that room for one end, in
pixels; `None`, the default, keeps the automatic reservation. Use it
for an end whose shaft already has visible room elsewhere: an arrow
that enters a card inside a `Region` from outside the region runs
through the region's padding, so `dst_room=0` lets the card reach the
region's foot instead of leaving an empty band under it.

An arrowhead that sits on the last bend of its wire reads as a triangle
glued to its target. `Connect(..., min_shaft=)` sets, in pixels, the
least straight shaft that stays visible between the last bend and the
base of the head; `None`, the default, changes nothing. A routed wire
keeps the last bend of a bridged route that far from the head and
reserves the room on a pinned side; a bus (`Connect([a, b], sink, ...)`)
keeps its spine that far from each sink, and takes `src_room=` and
`dst_room=` like a routed wire. An arm the layout fixes shorter (the
elbow of a single-corner route) cannot be lengthened by routing, so
check the result: `diagram.short_shafts(8.0)` lists every drawn
arrowhead whose entering shaft is under 8 px (`diagram.arrow_ends()`
lists them all with tip, bend, run, head and shaft), whatever primitive
drew it.

A bus draws every stroke as its own butt-ended segment, so the outer
corner where an outermost tap turns into the end of the spine stays
open by half a stroke. `Connect([a, b], sink, corner_radius=2.6)` draws
each corner of exactly two strokes as one stroke, rounded by that radius
in pixels (`0`: sharp and closed); a tap on the spine's run stays a T,
and a corner never reaches the next junction or the shaft a head needs.
`flush_head=True` ends each arrowed stroke inside its head, where the
head is as wide as the stroke, so no square stroke end shows beside the
tip of a small head; the tip and the shaft stay where they were. Both
are bus-mode options, off by default (`corner_radius=None`,
`flush_head=False`).

A `Funnel`'s wires land on its flow openings: a wire leaving the narrow
end starts at the outlet's centre (or runs straight where the facing
element overlaps the outlet), a wire arriving at the wide end lands on
the mouth. Put the neighbour level with the neck (a centred `Row`
aligns on the taper) and the wire is one straight line. The bypass arc
lands on the neck's edge, clear of that wire.

Routed wires stay inside the drawing: the planner first looks for a
route within the hull of everything the scope has laid out or drawn,
grown by one lane (earlier wires count, so stacked return lanes keep
their places), and leaves it only when no route inside exists (the
debug log then notes it). A route through a tight gutter that hops one
wire beats an excursion round the whole figure. Two faces across a
gutter shorter than both stubs meet on one line in it (the arrowhead
side keeps its visible stub while the gutter allows), so a collapsed
gutter never grows a spur that overshoots and doubles back. The router's
parallel-wire floor and widest-channel width are `CrossPolicy` fields
(`parallel_floor`, `max_channel`).

A `Bus` hops the wires drawn before it with the routed wires' arc, so a
crossing never reads as one of its junctions.

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

### Rhythm -- one gutter, shared lanes

A token gap is the space between two boxes, and an anchored card's box
includes the flow lanes its wires reserve. So a row of sister cards
spaced `gap="md"` shows a wider gutter wherever a wire or a caption
crosses, and two stacked cards joined by a wire get tail lane + gap +
head lane between them. Pass a `Rhythm` as `gap=` instead, and share
the object between every `Row` (or every `Column`) that should keep one
beat:

```python
from sciviz import Anchor, Box, Column, Connect, Diagram, Rhythm, Row

cards = Rhythm("md")
tiers = Rhythm("sm")
stages = Row(*[Anchor(n, Box(f"stage {n}")) for n in "abcd"], gap=cards)
body = Column(
    Anchor("head", Box("input")),
    stages,
    Connect("head", "b", src_side="bottom", dst_side="top"),
    Connect("a", "b", src_side="right", dst_side="left"),
    Connect("c", "d", src_side="right", dst_side="left", label="ok"),
    gap=tiers,
)
d = Diagram.for_paper(body)
d.render(embed_fonts=False)
assert cards.gutter(d._layout_theme()) >= d._layout_theme().gap_px("md")
```

Every pair of neighbours in every member container is then set one
content-to-content distance, the gutter `max(gap token, largest lane
need)`, whatever crosses it. A wire whose two ends face each other
across a gutter is counted once (its larger end, or both halves of its
caption corridor), so stacked neighbours share one lane instead of
stacking two; lanes of different wires on the two sides still add up.
A Rhythm spaces one axis (one object for rows, another for columns) and
only `Row` and `Column` take one; lanes a `Flowed` scope or a bus
reserves are kept whole. A Rhythm row sets content-to-content gutters,
so it never takes shared slot columns from a stacked neighbour with the
same number of children (as a justified row does not). A Rhythm holds
its containers weakly: a container that is dropped leaves the beat.

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

### Walls, tabs and trays

`Region(border="double")` draws a second wall inside the first: the
conventional mark of a *boundary* (a membrane, a trust boundary) rather than a
grouping. `label_style="tab"` sets the label on the top or bottom wall
(a fieldset legend) instead of above the box; the label may be a string
or any element, `tabs={"top": ..., "bottom": ...}` names both walls, a
`(start, end)` pair sets one tab at each end of a wall (a name and a key),
`tab_align` places each, and `tab_outline=False` leaves a plain knockout
instead of a plate framed in the wall colour. `open_side="top"` leaves one
wall out: a tray whose content runs flush to the open edge, so a group of
titled stages inside it keeps its titles level with stages outside it
(a wire lane over one of its titles stays the tray's outer lane, and the
walls stop below it).

`tab_style="legend"` sets a tab title on the border line itself with no
plate: the wall alone is interrupted under the text, the region's fill runs
on under it, and the title reserves only its capitals' height. `tab_inset=`
states its position along the wall (px from the border's outer edge),
`tab_pad=` the pad on each side of the text, and `Region.wall_offsets(theme)`
reports where the walls stand inside the measured box.

A region titled on its border line reads as a titled card, so a row aligns
and equalises it on its WALLS (`Region.frame_bbox(theme)`, which an `Anchor`
forwards): the walls line up with the frames beside it and take the row's
shared height (`equal_heights=True`, `align="stretch"`), and the half title
above the top wall rides in the room a taller neighbour leaves free. It adds
to the row's height only where nothing leaves it room. A column lets the half
title ride in the gap to the neighbour above (`Region.wall_overhang(theme)`),
so the gap runs to the wall. `balance_label_padding=True` mirrors the title's
inner half inside the opposite wall, so the content stands centred between
the walls. The title inks the capitals it reserves (`Canvas.text(...,
ink_ascent=)`), so the page does not grow for an ascent it never uses. Every
other region (an outside label, a plate tab) and every row or column without
such a region is laid out as before.

A connector that joins several sources into one trunk and forks it onto
several targets is `sciviz.connect.trunk.trunk_route(sources, targets,
join=, fork=)`: pure geometry, whose `commands(radius)` (rounded `M` / `L` /
`Q` strokes) or `svg_path(radius)` a diagram or a plot script draws. An end
that stands on the trunk gets a straight leg, so single and forked
connectors of one figure share a form.

```python
from sciviz import Column, Diagram, Region, Row, Span, Text

membrane = Text([Span("Cell Membrane", weight="700"),
                 Span(": ions and gradients", color="muted")], size="tiny")
cell = Region(Text("cell interior"), border="double", dashed=False,
              fill="#edf2f8", color="#5a86b0", label=membrane,
              label_style="tab", label_position="bottom",
              label_align="center")
stages = Region(Row(Text("3 Filter", weight="700"),
                    Text("4 Detect", weight="700"), gap="md"),
                dashed=False, open_side="top",
                label="downstream stages", label_style="tab",
                label_position="bottom", label_align="center",
                tab_outline=False)
d = Diagram.for_paper(Row(cell, stages, gap="md", align="start"))
```

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

`Row(equal_widths="painted")` equalises the *painted* widths (`True`
equalises outer boxes): a child whose anchor carries a routed wire's lane
receives the shared face plus its lane, so it is never painted narrower
than its sisters. When a parent
stretches the row, `justify="between"` gives the surplus to the gutters
(equal, wider) instead of the slots; so does a plain `Row(justify=
"between")` of cards that should each hug their content.

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

A `Badge` whose label is an element (an `Icon`) sizes its disc around the
label plus 1.1 theme units. `label_pad=` sets that room instead, so a small
status mark keeps a large glyph: `Badge(Icon("check", size=8.0), size=11.0,
label_pad=3.0)` is an 11 px disc with an 8 px check.

A value a figure withholds keeps its figure's geometry with
`Blank(element)` (`from sciviz.elements._blank import Blank`): the blank
measures as the element and reports its content box, first baseline,
anchor and ports, so rows, columns and tables lay out exactly as with it,
and nothing of it is drawn. `Blank(element, stand_in=other)` draws `other`
centred in that place (a tag that stands in for the withheld value).

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
BarChart(rows, orientation="horizontal", label_size=..., value_size=...)
GroupedBarChart([(title, [values], annotation), ...], series=[BarSeries(...), ...])
Table(rows, col_align=..., gap_x="md", header=True, rules="all", col_widths=[...], zebra=..., row_fills={i: ...}, pad_y=...)
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

`MatrixGroup` labels wrap to their own span, so long group names claim extra
header rows instead of colliding with the neighbouring group. A column group
whose longest word is wider than its span widens the columns it spans (the
deficit shared equally) rather than shrinking the font, so a one-column group
can still carry a worded header at the theme's small size; a row group, whose
span is set by the row height, shrinks with a floor instead.

A column is as wide as the widest thing it must carry: its cells, a horizontal
column label, and its share of a group label's longest word. A horizontal
label wider than its cell therefore widens that column, the way a typeset
table sizes a column to its header, while a rotated label (`col_label_angle`)
costs height instead; columns that nothing widens keep the square cell.

Row labels may contain newlines: the first line is the label proper and
continuation lines render smaller and muted — sublabels for units,
provenance, or grounding detail (`"Fan-out per core\nLoihi: 4096 edges"`),
the same convention as multiline `Scatter` point labels. This keeps long
annotations from widening the label column at full label size.
`row_sublabel_size` (default `"tiny"`) names the size token of those
continuation lines, for a document whose legibility floor sits above the
theme's tiny size. Column labels stay single-line (they rotate instead).

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

### Instrument primitives: `Funnel`, `Gauge`, `Balance`

Three shapes that a reader already knows how to read, for three facts a
bar chart states badly.

`Funnel` is *selection*: a population enters, a rule keeps part of it, and
the ratio is in the silhouette rather than in two numbers the reader has
to divide. Stages are `(label, value)` in order, the first value sets the
full width, and `neck_ratio` gives the last stage a straight neck so a
two-stage funnel still reads as a funnel.

`Gauge` is *one bounded reading with the limits that bound it*. A share, a
utilisation, a duty cycle carries two facts -- where it sits, and what
stops it going further -- and `marks` puts the floor and the ceiling on
the same track as the needle. `style="dial"` reads as an instrument and
`style="bar"` packs into a card or a table row; a mark caption longer than
a word belongs on the bar, whose track carries it underneath.

`Balance` is *which of two is winning*. The beam tilts by the relative
difference `(l - r) / (l + r)`, never by the raw values, so two large
numbers and two small ones in the same ratio tilt the same way and no pair
can tip the beam past `max_tilt`. Give each pan its own colour and the
verdict is legible without reading a single digit.

```python
from sciviz import (Balance, BalancePan, Column, Diagram, Funnel, Gauge,
                    GaugeMark, Palette, Row)

screen = Funnel([("pool", 4), ("kept", 1)], role=Palette.teal,
                width=48, height=34, show_values=False)
share = Gauge(0.62, marks=[GaugeMark(0.25, "floor")], style="bar",
              width=60, height=8, role=Palette.teal, show_value=False,
              end_labels=("none", "all"))
credit = Balance(BalancePan("guided", 1.6, Palette.teal),
                 BalancePan("control", 1.0, Palette.gray),
                 width=64, height=24, show_values=False)
d = Diagram.for_paper(Row(screen, Column(credit, share, gap="xs"), gap="lg"))
```

A funnel can also show the selection as its *members*: give each
`FunnelStage` its `marks` (one colour per member) and the members are
packed as dots into the band that stage occupies, the survivors in the
neck (`mark_size` draws them a size up). `lanes=True` gives every colour
its own lane, so the picture says the selection happened *within* each
group; `orientation="horizontal"` runs the taper left to right;
`bypass="..."` draws a dashed arc over the body with a caption (break it
with `"\n"`) for a selection that is sometimes skipped; the arc leaves a
bracket spanning the whole mouth (every lane steps aside, not one group),
and a wire into the mouth lands on that bracket. Siblings align on
the taper body (`content_bbox`), so a centred neighbour sits level with
the neck.

```python
from sciviz import Diagram, Funnel, FunnelStage, Icon, Palette, Row

pool = ["#1f3f63"] * 5 + ["#b9b9b9"] * 24 + ["#8a8a8a"] * 32
kept = ["#1f3f63"] * 3 + ["#b9b9b9"] * 3 + ["#8a8a8a"] * 4
sieve = Funnel([FunnelStage("sampled", 61, marks=pool),
                FunnelStage("selected", 10, marks=kept, mark_size=1.5)],
               orientation="horizontal", width=48, height=54, lanes=True,
               show_values=False, label_position="none", neck_ratio=0.3,
               role=Palette.literal("#78818c"),
               bypass="bypassed while\nthe sensor is\nwarming up")
d = Diagram.for_paper(Row(sieve, Icon("cpu", size=14), align="center"))
```

### `MiniScatter` -- a point cloud that fits inside a card

The scatter counterpart of `Sparkline`: no ticks, no axis titles, an
optional hairline corner, and a size measured in tens of pixels, because a
thumbnail carries a shape and the card around it carries the words. Points
may be bare `(x, y)` pairs or `MiniPoint` values with their own colour,
radius and `hollow` flag, so one cloud can show ranks, or measured members
beside derived ones. `path` joins a subset with a hairline (a front, a
trajectory) and `vectors` draws `(x, y, dx, dy)` displacement arrows in
data units: where each member is being nudged, rather than replaced.

```python
from sciviz import Diagram, MiniPoint, MiniScatter, Palette, Row

front = [(0.10, 0.82), (0.28, 0.66), (0.46, 0.52), (0.68, 0.40)]
nudged = MiniScatter([MiniPoint(x, y, Palette.teal) for x, y in front],
                     path=front, path_color=Palette.teal,
                     vectors=[(0.28, 0.66, -0.09, 0.09)],
                     width=52, height=34, role=Palette.teal)
ranked = MiniScatter([(0.2, 0.7), MiniPoint(0.5, 0.4, size=2.4),
                      MiniPoint(0.8, 0.6, hollow=True)],
                     width=52, height=34, role=Palette.gray)
d = Diagram.for_paper(Row(nudged, ranked, gap="lg"))
```

`MiniArea(points, color, opacity)` fills a polygon of the scatter's data
plane under every path and point -- a feasible region, a confidence
band -- and the thumbnail clips areas, paths and points to
its window (`clip=True`, the default), so a cropped view never inks
outside its box. Points whose colour would vanish on the page get a
hairline edge in a darker shade of their own colour
(`MiniPoint(edge=...)` names it, `edge="none"` suppresses it).
`MiniRaster` cells may each be a colour (a row of seats coloured by
who holds them) and `spans=[(first, stop, label)]` brackets a run of
columns with a caption. `SparkLine(fill=..., fill_to=...)` paints the
area under a line, so densities stacked at different baselines make a
ridgeline.

```python
from sciviz import (Column, Diagram, MiniArea, MiniPoint, MiniRaster,
                    MiniScatter, SparkLine, Sparkline)

old = [(0.1, 0.8), (0.4, 0.5), (0.8, 0.3)]
cloud = MiniScatter([MiniPoint(0.3, 0.45, "#1f3f63"), *old],
                    areas=[MiniArea([(0.3, 0.45), (0.4, 0.45), (0.4, 0.5),
                                     (0.3, 0.5)], color="#8fa0b3",
                                    opacity=1.0)],
                    path=old, width=50, height=40, corner=True)
seats = MiniRaster([["#b9b9b9"] * 3 + ["#1f3f63"] * 7], cell=4.6,
                   spans=[(0, 3, "reserved")])
xs = [i / 20 for i in range(21)]
ridge = Sparkline([SparkLine([(x, 1 + 1.5 * x * (1 - x)) for x in xs],
                             color="#1f3f63", fill="#8fa0b3", fill_to=1.0),
                   SparkLine([(x, 1.2 * x * (1 - x)) for x in xs],
                             color="#8a8a8a", fill="#d0d0d0", fill_to=0.0)],
                  width=50, height=24, domain=(0, 1), range=(0, 2.5))
d = Diagram.for_paper(Column(cloud, seats, ridge, gap="sm"))
```

### `StepLanes` -- a schedule on a grid of discrete time steps

`Timeline` is a continuous axis with task bars. When the claim is about
*which step* something happens at ("a spike emitted at step t is received
at step t + 1", "the replay arrives one step late"), use `StepLanes`: every
step is one column with a faint gridline through its centre under one axis
of step numbers; a lane's `window` (inclusive first and last step) is a thin
light-gray bar over exactly those columns, square, one height for every
lane (`window_color` outlines it, e.g. in a status colour); `marks` are
filled dots at the step centres (`mark="tick"` draws vertical ticks); and a
`StepLink` is a thin arrow with a small solid head from the edge of one mark
to the edge of another (horizontal within one lane, e.g. a shift). `ghosts`
are hollow dots where an event would have been. A lane with `kind="store"`
is a buffer: a dashed strip over every step.

Lanes are gathered into `StepGroup`s (one scenario each) with a label on the
left (`"\n"` breaks it). A group's `note` (a string or any element, e.g. a
styled outcome `Text`) is the label's last line by default (`notes="label"`),
so the steps get the full remaining width; `notes="right"` sets notes in a
column right of the grid. A group grows if its label and note need more
lines than it has lanes. A `kind="bar"` lane draws a solid bar of `share`
of the grid width from the grid's left edge with its `value` after it, so a
measurement lines up with the schedule above it and its label sits in the
lane-label column.

```python
from sciviz import StepGroup, StepLane, StepLanes, StepLink, Text

lanes = StepLanes([
    StepGroup("one pass", [
        StepLane("layer 1 cores", window=(0, 2), marks=[0, 2], key="l1"),
        StepLane("layer 2 cores", window=(1, 3), marks=[1, 3], key="l2"),
    ], note="reference"),
    StepGroup("two passes", [
        StepLane("stored spikes", kind="store", marks=[0, 2], key="st"),
        StepLane("layer 2 cores", window=(1, 3), marks=[1, 3], key="p2"),
    ], note=Text([("= ", {"color": "success"}), "same output"], size="small")),
    StepGroup("programs whose\noutputs differ", [
        StepLane("no replay", kind="bar", share=0.38, color="alert", value="956 of 2,494"),
        StepLane("replay", kind="bar", share=0.0, value="0 of 2,494"),
    ]),
], steps=range(5), width=244, axis_title="time step",
   links=[StepLink(("l1", 0), ("l2", 1)), StepLink(("l1", 2), ("l2", 3)),
          StepLink(("st", 0), ("p2", 1)), StepLink(("st", 2), ("p2", 3))])
```

Two streams that meet (a residual block: a main path L1 -> L2 -> L3 and a
skip L1 -> L3) stay apart visually: give the skip `StepLink(..., bend=0.07,
dashed=True)`, a quadratic arc that bows `bend` times its length to the left
of its direction of travel (below-left for a link running down and right),
so it passes beside the marks it skips instead of through them; mark the
meeting step with `StepMark(step, "diamond")` (a `StepMark` also gives one
mark its own colour). `StepLane(tag="pass 1")` sets a short muted tag right
of the grid, and `StepGroup(cuts=(0,))` draws a dashed hairline after lane 0
(a pass boundary) across the lane labels and the grid.

For a measured share beside a label and a number outside a grid, use
`ShareBar(share, width=..., color=...)`: a light track for the whole, a solid
fill for the share and a short origin tick, so a share of zero stays visible.

`width` lets the step columns share what the labels leave (`step_w` fixes
them instead). `corner` puts an element (a short panel title) in the label
columns of the axis row. Lane keys must be unique when links name them; two
lanes may share a label if they have distinct `key`s. Links are straight: a
link between non-adjacent lanes crosses the lanes in between, so place a
lane next to the lane it feeds.

### `StepRaster`, `CoreChip`, `LayerNet` -- a schedule drawn as hardware

When a step schedule should read as a schematic rather than a chart, draw the
hardware itself. `StepRaster` is rows over discrete steps where every step is
one small block: a row's `window` lights its blocks in the row's hue, `marks`
are spike dots, `kind="store"` is a dashed buffer (stored spikes), and
`RasterLink`s are thin arrows between dots (`bend` and `dashed` keep a skip
apart from the main path). `cuts` split the columns into phases side by side
(a dashed vertical rule, or `(index, False)` for a plain gap), `titles` head
each phase, and a row's `span` and `line` let one line hold a different row in
each phase. A row's `tag` (a string or any element, e.g. a styled outcome) is
set right of the grid on its line.

`CoreChip` is a chip as a row (or grid) of core blocks: a `Core` has a label,
a hue and a `window`, drawn as a strip of `steps` cells under the block; a core
without a hue is idle (a dashed outline). `CoreLink`s are arrows between cores,
straight between neighbours and an arc over the cores for a skip (`bend` > 0).
`LayerNet` is a small layered network: one node column per `NetLayer`, fan
edges between consecutive layers, skip arcs over the top, labels underneath.
`ThinArrow` is the same thin arrow as an inline element between blocks of a
`Row`, so the figure keeps one arrow style. A `Core`'s `marks` dot steps of
its strip (the steps it sends a spike).

An arrow from a dot of one element to a cell of another (a stored spike
entering a core's window at its step) needs no coordinates: give the
elements a `name` (a `StepRaster` registers `"name:row,col"`, a `CoreChip`
`"name:core"` and `"name:core,step"`) and wrap the composition in
`PointArrows(child, [PointArrow(src, dst)])`. `enter="below"` (or `"above"`,
`"left"`, `"right"`) curves the arrow so it leaves the source level and enters
the destination from that side, across a strip instead of along it; `bend`
and `dashed` work as on the other links. `StepRaster(axis_side="top")` puts
the step labels above the grid.

```python
from sciviz import (Core, CoreChip, PointArrow, PointArrows, RasterRow, Row,
                    StepRaster)

stored = StepRaster([RasterRow("", kind="store", marks=[0, 2])], range(5), cell=9,
                    axis_side="top", name="stored")
pass2 = CoreChip([Core("L2", "#0f766e", (1, 3), [1, 3])], steps=5, core=20,
                 strip_h=5, name="p2")
replayed = PointArrows(Row(stored, pass2, gap=20),
                       [PointArrow("stored:0,2", "p2:0,3", enter="below")])
```

```python
from sciviz import (Column, Core, CoreChip, CoreLink, LayerNet, NetLayer,
                    RasterLink, RasterRow, Row, StepRaster, ThinArrow)

net = LayerNet([NetLayer("L1", 3, "#3b5fa0"), NetLayer("L2", 3, "#0f766e"),
                NetLayer("L3", 2, "#0f766e")], skips=[(0, 2)])
chip = CoreChip([Core("L1", "#3b5fa0", (0, 2)), Core("L2", "#0f766e", (1, 3)),
                 Core("L3", "#0f766e", (2, 4))], steps=5, core=17,
                links=[CoreLink(0, 1), CoreLink(1, 2), CoreLink(0, 2, bend=0.2, dashed=True)])
rows = [RasterRow("L1", "#3b5fa0", (0, 2), [0, 2], span=(0, 4)),
        RasterRow("L2", "#0f766e", (1, 3), [1, 3], span=(0, 4)),
        RasterRow("", kind="store", marks=[5, 7], span=(5, 9), line=0, tag="stored spikes"),
        RasterRow("", "#0f766e", (6, 8), [6, 8], span=(5, 9), line=1)]
raster = StepRaster(rows, list(range(5)) * 2, cell=10, cuts=[5],
                    titles=[(0, "one segment"), (5, "pass 2")],
                    links=[RasterLink((0, 0), (1, 1)), RasterLink((2, 5), (3, 6))])
figure = Column(Row(net, ThinArrow(12), chip), raster)
```

### Legends that reuse the chart's own marker

`Marker` is the chart marker vocabulary (`"circle"`, `"square"`,
`"triangle"`, `"diamond"`; `fill="solid"|"hollow"`) as a standalone
element, so a legend shows the glyph the chart actually plots instead of
a coloured box that drops the shape. `LineChart`, `Scatter` and
`Slopegraph` draw through the same helper: pass the series' own `color`,
`marker_size` and `marker_fill` and the swatch cannot drift from the
plot.

```python
from sciviz import Diagram, Legend, LegendItem, LineChart, Marker, Palette, Series

policies = [("measured", "diamond", Palette.red, "solid"),
            ("baseline", "circle", Palette.gray, "hollow")]
chart = LineChart(
    [Series([(0, 1), (1, 2)], marker=m, marker_size="sm",
            marker_fill=f, color=c)
     for _label, m, c, f in policies],
    size="sm",
)
legend = Legend(*[LegendItem(Marker(m, color=c, size="sm", fill=f), label)
                  for label, m, c, f in policies])
d = Diagram.for_paper(chart)
```

A long key is still subordinate to the figure it explains, so it must
not be what sets the figure's width. `Legend(..., max_width=376)` flows
the items onto a second line inside that budget instead of pushing the
whole figure past it (`orientation="vertical"` remains the choice when
the key should read as a stacked list).

The gap between a swatch and the label it names is a bearing on the
label's own size, not a spacing token, so it survives compression: a
figure squeezed towards a print width drives `theme.unit` down, and a
unit-based gap goes under a point while the type it separates barely
moves, leaving the label touching its swatch. Pass `gap=` on a
`LegendItem` only to override that deliberately.

### Axis titles are prose and wrap

`x_label` / `y_label` wrap to the span they are centred over, so a real
sentence claims another title line in its own gutter instead of drawing
outside the chart's measured box and over whatever sits beside it. Only
a single word too wide to break grows the chart. Use `Theme.wrap_lines`
for the same greedy, font-measured wrap in your own elements, and
`Theme.text_ink_extents` to reserve a text line's true ink (which is
taller than `text_height`, the layout footprint) when you place glyphs
against a hard edge.

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
claims every pixel the labels do not need. The top and right gutters
hold no labels, so they reserve only what the chart pushes past those
edges: a marker centred on the top row, a stroke on the last x value,
a tick label centred on an edge tick, an annotation pinned near a
corner.

An explicit range is a *window*, not a suggestion. `LineChart` and
`Scatter` clip series geometry to the plot rectangle: a polyline is cut
at the edge (and comes back as several runs if it leaves and returns),
a marker is drawn whole when its centre is inside and dropped when it
is not, and a `FillBetween` band is clipped as a polygon. So you can
hand a chart a 500-point curve and show the 130 points the figure is
about without the rest being painted over the tick labels and the
neighbouring panel. With an automatic range the rectangle already
contains the data and clipping changes nothing. Annotations are labels
rather than data and are never clipped; they are measured instead, so
one placed near an edge grows that gutter rather than escaping the box.

When a second quantity shares the x axis but not the units (a hazard
beside a transfer curve, a cost beside an accuracy), give its series
`axis="right"`. That alone grows a secondary y axis: it auto-fits its
own range, snaps to its own nice tick step, draws its own spine, ticks,
and `y2_label`, and claims a right gutter measured from those labels.
It draws no gridlines, so the two quantities stay distinguishable, and
legend placement treats right-axis ink as an obstacle exactly like
left-axis ink (each axis expands its own headroom when needed). A
`FillBetween` or `SeriesDelta` spanning both axes is rejected, since
the area or difference between them has no meaning.

```python
from sciviz import Diagram, LineChart, Series

chart = LineChart(
    [Series([(0, 0.0), (1, 1.0)], label="accuracy", color="blue"),
     Series([(0, 0.02), (1, 0.11)], label="energy", color="amber",
            dash="4,3", axis="right")],
    x_label="scale", y_label="accuracy", y2_label="energy (J)",
)
d = Diagram.for_paper(chart)
```

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

### Pale marks keep an edge

The quietest classes of a categorical palette (`#ededed`, `#d6d6d6`)
vanish as small dots or cells on a white page. `Theme.edge_for_fill(fill)`
returns a darker shade of the fill itself when its contrast with the
ground is under `Theme.mark_edge_contrast` (1.5 by default), and `None`
when the fill carries the shape on its own; solid `Marker`s, `MiniPoint`s
and `MiniRaster` cells use it, so every unit stays countable without a
second colour.

## When you actually need manual placement

Avoid it. Ninety-five percent of the time the answer is:

* "I want these things centred" -> `Row(align="center")`.
* "I want two things at the same vertical axis" -> `Column(align="center")`.
* "I want equal-width cells" -> `Row(..., equal_widths=True)` or `LabeledChain`.
* "I want side-by-side panels the same height" -> `Row(..., align="stretch")`.
* "I want stacked cards the same width" -> `Column(..., align="stretch")`.
* "I want shared column widths across rows" -> `Grid`.
* "I want shared column widths across *different parents*" -> `AlignedStack`.
* "I want these blocks the same width, and they sit in different
  parents" -> `SizeGroup`.
* "I want the block's name to head it, not run into its text" ->
  `Box(title=...)`.
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

`target_aspect` additionally balances the layout toward the printed
shape: the fitter explores every reflow variant and a small grid of
spacing densities, ranking candidates by width fit first, then aspect,
then least compression. Without it a multi-card figure can satisfy the
width as one degenerate tall corridor; with it the balanced
arrangement wins whenever one exists at the authored font sizes. If
the content cannot reach the requested shape, the fitter returns the
closest feasible layout -- it never trades fonts for geometry.

Width does not always fall steadily as spacing compresses: a caption
that no longer fits on its wire is set beside it, a label re-wraps, a
lane moves outward. When the density fixed-point stalls above the
target, the fitter first takes a few secant steps (steady content that
merely converges slowly), then tries the spacing floor: when the floor
lands, the bracket between it and the looser trials is bisected towards
the least compression that still lands. When it does not land and the
trials were monotone (tighter spacing measured narrower), nothing looser
can land either and the fit stops there; width is not always monotone
(a caption set beside its wire at tighter spacing can make the floor
wider than an interior density), so the narrowest trial, not the floor,
is what the fit returns and reports (the wrap continuation likewise stops
after two steps that do not narrow the figure). Text authored exactly at `min_effective_font_pt`
gets no overshoot tolerance at all (a scale-down would print it below
the floor). `Diagram.page_size()` reports the exported page -- connector
lanes and captions outside the laid-out box included -- which is the
size to check against a page budget; `measure()` is the layout box.

### Elastic spacing and the fit report

By default compression is proportional: every spacing token scales with
`unit`, which keeps a fitted figure exactly the size it has always had.
Strokes, arrowheads and fonts never shrink, though, so a gutter scaled
far towards zero can leave bordered cards touching and wires running
along card edges. Print floors are opt-in: set `Theme.min_space` (say
`2.0` points) and every floor switches on at once. Each spacing token
(`gap`, `Card`/`Stripe` padding, `panel_padding`, the diagram margin)
then compresses only down to `min(authored, min_space)`; an authored
value already below the floor is kept as written, and numeric gaps are
never compressed at all (prefer tokens). A wire end keeps its arrowhead
plus `min_space` on both sides (`Theme.arrow_gutter_px()`), a plain tail
keeps `min_space`, and a wire keeps `min_space` from the cards it passes.
`Theme.print_floors` says whether floors are on; code that adds a floor
applies it only then. At the authored unit no floor ever binds.

When a figure still does not land, the fix is content, not spacing.
`Diagram.fit_report()` says what the fit chose and what holds the width
up:

```python
import warnings
from sciviz import Box, Column, Diagram, Row

body = Row(Box("a rather long label that does not wrap"),
           Column(Box("short"), Box("the widest label in the column")),
           gap="lg")
d = Diagram.for_paper(body, target_width_pt=180.0)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    report = d.fit_report()
print(report)  # page, density, trials, ink outside the layout, drivers
assert report.drivers[0][0] == 0  # the top-level split of the width first
```

The drivers walk the width-critical path breadth first: every part of
a `Row` plus any authored numeric gap between them, then the widest
part of anything else, with natural (unstretched) widths. `overflow`
lists ink painted outside the laid-out box (wire detours, captions),
which `page_size()` includes and `measure()` does not.

Measurement inside one fitter trial and one render is memoised
(`sciviz.core._measure_memo`), which makes a deep figure's fit several
times faster; `SCIVIZ_MEASURE_MEMO=0` switches it off when bisecting a
suspected stale size.

### Declaring a shape: the aspect vocabulary

Say the shape you want by name instead of hand-tuning containers until
the proportions come out right:

```python
cards = [Card(Text(f"Stage {i}", color="white", weight="700"),
              Box("detail"), role=Palette.blue) for i in range(6)]
body = EqualGrid(*cards, columns="auto")
d = Diagram.for_paper(body, target_width_pt=505.0, target_aspect="landscape")
```

The names are read the way people say them aloud, as width:height --
`"portrait"` (0.40-0.85), `"square"` (0.85-1.20), `"landscape"`
(1.20-2.60), `"panorama"` (2.40-6.00). The bands are deliberately
broad: a name states the intent, and `AspectSpec("landscape",
ratio=(1.85, 2.4))` tightens it when a page budget demands a specific
proportion. Numbers keep their original *height/width* meaning, so
figures written before the vocabulary existed are unaffected.

The same vocabulary applies to one component, not just the whole
figure:

```python
def zone(name, n):
    return EqualGrid(*[Box(f"{name} {i}", width=48, height=22)
                       for i in range(n)], columns="auto")

body = Row(zone("port", 4), Aspect("landscape", zone("stage", 6)),
           zone("record", 4), gap="lg", align="stretch")
d = Diagram.for_paper(body, target_width_pt=505.0)
```

`Aspect` is a fully transparent wrapper -- it measures and renders
exactly like its child -- that declares a goal for its own subtree.
Nothing is scaled, squeezed, or letterboxed: the engine reaches the
goal only by choosing among layout alternatives that genuinely exist
inside the subtree (`columns="auto"` containers, `Cycle` ring shapes).
Sibling subtrees are left alone, several annotations can coexist
(`weight=` orders them), and a component goal is ranked after the
figure-level one, which is a physical page constraint rather than a
compositional preference. An annotation alone is enough to start the
search: no diagram-level `target_aspect` is required.

**Priority.** By default a declared shape is *preferred*: the width
target comes first and shape breaks ties. When the shape is the point
of the figure and the author will pay for it in print scale, say so:

```python
d = Diagram.for_paper(
    EqualGrid(*[Box(f"stage {i}", width=90, height=40) for i in range(6)],
              columns="auto"),
    target_width_pt=252.0,
    target_aspect=AspectSpec("landscape", ratio=(1.85, 2.4),
                             priority="required"),
)
```

The hard width constraint then becomes `min_effective_font_pt` rather
than `target_width_pt`: the figure may overshoot the column as far as
the type stays readable, and the declared shape decides among the
candidates that clear that floor. "Required" is not "at any cost" --
a variant that would print below the floor is still rejected. The same
graceful degradation applies automatically, without the flag, when *no*
variant can reach the target width: ranking by width would otherwise
veto the declared shape to save a few points of overshoot no reader
sees.

### Cycle -- a staged loop whose shape is the engine's choice

A process that returns to its own start has one piece of layout freedom
that matters: the shape of the ring. Six stages read equally well as
three columns of two or two rows of three, and which is right depends
on the page, not the process. `Cycle` makes that freedom explicit:

```python
def stage(name):
    return Card(Text(name, color="white", weight="700"), Box("detail"),
                role=Palette.blue)

loop = Cycle(
    Anchor("propose", stage("Propose")),
    Anchor("screen", stage("Screen")),
    Anchor("evaluate", stage("Evaluate")),
    Anchor("record", stage("Record")),
    edges=["propose()", None, {"label": "commit", "dashed": True}, None],
    shape="auto",            # the layout engine picks the rectangle
)
d = Diagram.for_paper(Aspect("landscape", loop), target_width_pt=380.0)
```

Stages are given in cycle order and placed around a rectangle's
perimeter; `edges[i]` describes the hand-off from stage `i` to stage
`i + 1`, with the last entry closing the loop (`None` for a plain
arrow, a string for its label, a dict of `Connect` keyword arguments,
`False` for no connector). `Cycle` derives every connector's
attachment side from the placement it actually chose, so re-shaping the
ring never asks the author to restate a single side hint. `start=`
and `direction=` set which corner stage one occupies and which way the
loop winds; `shape="auto"` enters the reflow search, a pinned
`(rows, cols)` opts out. Pre-wrapped `Anchor` children keep their names
so feedback connectors declared elsewhere can address any stage.

Corridor economics are worth knowing before writing edge labels. A
caption on a top/bottom pair reserves half its **height** on both
cards. On a *facing* pair (a right side toward a left side) a
**single-line** caption is costed at the cheaper of its two
orientations, because the placer will rotate it into a narrow corridor
rather than lose it; a multi-line caption stays horizontal (a rotated
block reads as parallel columns of tilted text) and so reserves half
its width. The practical rule: keep hand-off captions to one line and
they stay cheap in any direction. Never delete words to make a figure
fit -- if a caption cannot be placed, that is a layout bug worth
reporting, not an editorial decision.

Two connector rules the router enforces so wires read as wires:

- **Arrow stubs.** Every arrowed endpoint keeps a stub longer than the
  arrowhead drawn on it (`Theme.arrow_stub_px`, derived from
  `arrow_size` and the connector stroke). A head sitting flush on a
  border reads as a triangle glued to a box, so this is a floor even
  when a neighbour crowds the endpoint. Bus spines honour the same
  floor for the edge they arrow into.
- **Crossings are chosen, not stumbled into.** When two endpoints leave
  their boxes the same way, the planner also considers common lanes at
  increasing depth, and prefers the shallowest bridge unless a
  proportionate alternative strictly removes a crossing. A long run
  will take a longer outgoing arm to pass under a short one rather than
  cut through it -- but a detour stays a detour, bounded relative to the
  preferred route.

## Baselines, shared bands and direct ridge labels

Three placement contracts keep side-by-side cards on one visual rhythm
without per-figure numbers.

- **`Row(align="baseline")`** puts the first text baseline of every child
  on one line (CSS `align-items: baseline`). Use it for tiles whose
  titles carry different decorations (a marker, an icon, a badge, none)
  or whose bodies differ in height: `align="center"` centres whole boxes,
  so a shorter tile's title drops. Children without text are centred on
  the aligned band. Elements report `first_baseline(theme)`, measured
  from the top of their `content_bbox()`, so a `Region` label or an
  `Anchor` wire lane is never counted twice. `Column` rejects
  `"baseline"`: a vertical stack has no shared baseline.
- **`SizeGroup(axis="height", fit="slot", align=...)`** makes bands.
  One group per band (title, picture, caption) across sibling cards: each
  member takes the band's shared height while its child keeps its
  natural size and sits in the slot at `align` (`"start"`, `"center"`,
  `"end"`, or `"baseline"`). Pictures are not stretched, a one-line
  caption starts on the same line as its two-line neighbours, and the
  cards come out equally tall with no surplus for their columns to
  spread into empty gaps. The default `fit="grow"` keeps the old
  grow-every-member behaviour.
- **`SparkLine(label=...)`** labels a line directly, at its `fill_to`
  level (else its last point), in a column on `Sparkline(label_side=...)`.
  A label column is rigid (its pitch is the font's), so the chart grows
  its vertical scale until neighbouring labels clear each other; the
  author's `height` is then a minimum. Use it instead of a separate
  `Column` of labels beside a ridgeline, which can never line up with
  the ridges once the figure is fitted.

One group per band across the cards:

```python
from sciviz import Box, Column, Region, Row, SizeGroup, Text

stations = [("Intake", Box(width=40, height=30), Text("one reservoir")),
            ("Filter", Box(width=40, height=50),
             Column(Text("drawn and kept"), Text("by particle size"))),
            ("Storage", Box(width=40, height=40), Text("sealed tank"))]
heads = SizeGroup("height", fit="slot", align="baseline")
pics = SizeGroup("height", fit="slot", align="center")
notes = SizeGroup("height", fit="slot", align="start")
cards = [Region(Column(heads(Text(title, weight="700")), pics(picture),
                       notes(caption), gap="sm", align="start"))
         for title, picture, caption in stations]
body = Row(*cards, gap="md", equal_widths=True)
```

### Structured content: spanning cells, overflow rows, mappings, unit bars, decluttered scatters, point events

Key-value content inside a card is a `Table`, not a stack of free text.
Five opt-in additions make it carry typeset structure; with default
arguments every element renders exactly as before.

- **`TableSpan(content, columns=None, align=None, style=None, rule_above=True)`**
  is a cell covering adjacent columns (`None` covers the rest of the
  row). It is sized after the ordinary cells: a narrow span leaves the
  columns alone, a wide one shares its excess over the columns it covers
  in proportion to their widths. Its string content takes the first
  column's style with `style` laid over it.
- **`Table(max_rows=, more="+ {n} more")`** shows at most `max_rows` body
  rows (the header is not counted) and closes the table with one
  spanning, muted row. `more` is a `str.format` template given `n`, or a
  `TableSpan` whose content is that template. For grouped rows, slice
  each group yourself and close it with a `TableSpan`.
- **`Table(row_styles=, rules_after=)`**: `row_styles` is the row-wise twin
  of `column_styles` (a dict `{row: style}` or one dict per row);
  `rules_after` draws a hairline after the named rows to separate groups.
- **`BarChart(mark="units", wrap=, cell=, rules_after=)`** draws a count as
  a run of countable `MiniRaster` cells beside its label and number, all
  runs starting at one x. `MiniRaster.from_counts([(n, colour), ...],
  columns=)` packs the same composition into a waffle; pair it with a
  `Legend` whose labels carry the counts. `wrap`, `cell` and
  `rules_after` shape unit runs only; with `mark="bar"` they raise.
- **`MiniScatter(declutter="dodge")`** keeps a pile of points readable: the
  last-drawn point keeps its place, true duplicates and redundant hollow
  points are dropped, other colliding points move at most `r_i + r_j`,
  and a point with no free spot is drawn as a ring around the one that
  hides it. No colour disappears.
- **`Timeline` point events**: a task whose duration is `None` is a marker
  at its time (the fourth field a `Marker` or a colour); repeats at one
  time show `×k`. `label_size`, `axis_size` and `tick_labels="ends"`
  shrink the lane gutter and the axis so a timeline fits in a card.

A mapping (what a translation layer takes in and gives out) is a `Table`
recipe, not a separate element: sources in one row, a row of bare `Arrow`
glyphs, targets in the next row, each side typed by `row_styles`, so all
glyphs share one line. Wrap an individual source or target cell (an
Element, e.g. a styled `Text`) in `Anchor` when a wire must land on a
crossing.

```python
from sciviz import (Anchor, BarChart, Column, Diagram, Marker, MiniPoint, MiniScatter,
                    Table, TableSpan, Text, Timeline)
from sciviz.elements import Arrow

params = [["9 channels", "range", "unit"],
          ["humidity", "20-70", "%"], ["period", "0.3-1.0", "s"],
          ["albedo", "0.4-0.9", ""], ["pH", "4-9", ""]]
channels = Table(params + [[TableSpan("Sampling: 100 readings", style={"weight": "700"})]],
                 header=True, rules="rows", col_align=["start", "end", "start"],
                 column_styles=[{}, {}, {"color": "text_muted"}])
short = Table(params, header=True, rules="rows", max_rows=2)   # "+ 2 more"

mapping = Table(
    [["display names", "temp 21", "pressure 1013", "gain x2.0"],
     ["", Arrow(direction="down", label=None), Arrow(direction="up", label=None),
      Arrow(direction="down", label=None)],
     ["logger keys", Anchor("cfg", Text("temp_c=21", font="mono", size="small")),
      "pressure_hpa=1013", "gain 2.0"]],
    col_align=["end", "center", "center", "center"],
    row_styles={0: {"size": "small"}, 2: {"font": "mono", "size": "small"}},
    column_styles=[{"color": "text_muted", "italic": True}, {}, {}, {}])

fruit = BarChart([("Apples", 5, "5", "#1f4e79"),
                  ("Oranges", 24, "24", "#9ca3af"),
                  ("Pears", 32, "32", "#6b7280")],
                 mark="units", wrap=12, label_size="tiny", value_size="tiny",
                 rules_after=(0,))

pile = MiniScatter([MiniPoint(0.05, 0.95, color="#9ca3af"),
                    MiniPoint(0.05, 0.95, color="#1f4e79")],
                   width=64, height=40, declutter="dodge")

events = Timeline([("Calibration", [(0.5, None, "start", Marker("square"))]),
                   ("Samples", [(g + 0.5, None, "sample") for g in (1, 3, 5, 7, 9)])],
                  t_min=0, t_max=10, width=90, lane_h=9, tick_every=1,
                  lane_label_width="auto", label_size="tiny", axis_size="tiny",
                  tick_labels="ends", show_axis=True)
figure = Diagram.for_paper(Column(channels, short, mapping, fruit, pile, events, gap="md"))
```
