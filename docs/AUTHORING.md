# Authoring sciviz diagrams

A short guide to idiomatic sciviz code. Read this after the README's
quick-start example; the goal here is to show the full vocabulary and
the patterns that make it work.

## Philosophy

* **Author intent, not coordinates.** You never type an `(x, y)`.
  You build a tree of elements; the library measures each element
  bottom-up and paints it top-down.
* **One way to connect.** `Connect(src, dst, ...)` replaces every
  arrow/bus/flow/labeled primitive we ever shipped. It auto-detects
  its mode from the shape of its arguments.
* **Semantic tokens.** Prefer `size="label"`, `gap="lg"`,
  `color=Palette.alert` to hex values and explicit pixel counts.
  Authoring against tokens lets a single `Theme.slides()` switch
  re-skin a paper figure for a presentation.

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
    footer=Text("Optional footer element, prints beneath the body."),
)
```

`Diagram` is the single export gate: it owns the title / footer band
and drives `.save("figure.svg" | ".pdf" | ".png")` and `.save_all("figure")`.

## Layout primitives

Signatures (call sites only — these are not runnable on their own):

```
Row(*children, gap="md", align="center", equal_widths=False)
Column(*children, gap="md", align="center")
Panel(tag, title, child)               # "(a) Encoder" framed block
Grid(*children, cols=..., col_align=...)
Spacer(w, h)                           # only for intentional gaps
FixedSize(child, width=..., height=...)
```

`Row` and `Column` filter out `None` children silently — handy for
optional pieces. `align` takes `"start" | "center" | "end"`.

## Text & math

Signatures:

```
Text("caption",  size="label", color="muted", weight="700")
TextBlock("multi\nline paragraph", max_width=280, line_spacing=1.35)
Math(r"$\hat y = \mathrm{softmax}(Wx)$")
Inline("The energy ", "$E = mc^2$", " is conserved.")
```

`Inline` splices text and inline math on a shared baseline; strings
beginning and ending with `$` auto-coerce to `Math`.

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
Row(Box("input"), Connect(direction="right"), Box("output"))
```

Routed example (a wire between two named anchors):

```python
Row(
    Anchor("a", Box("alpha")),
    Anchor("b", Box("beta")),
    Connect("a", "b", label="alpha \u2192 beta"),
)
```

Bus example (many sources fan into one sink):

```python
Connect(["t1", "t2", "t3"], "sink", label="concat", head=False)
```

Every `Connect` accepts `color`, `label`, `label_color`, `dashed`,
`curvature`, `head`. Defaults are picked so a plain `Connect("a", "b")`
looks right in paper style.

## Anchors

Wrap an element in `Anchor("name", element)` to give the connector
system a stable handle. The anchor tracks the child's rendered bbox
no matter how deeply the child is nested, and `Connect` reserves
margin for the wire automatically.

```python
Row(
    Anchor("encode", Panel("a", "Encoder", Matrix((4, 4)))),
    Anchor("decode", Panel("b", "Decoder", Math(r"$Wx + b$"))),
    Connect("encode", "decode", label="latents"),
)
```

## Colour

```python
from sciviz import Palette, Theme

color=Palette.alert                    # semantic role
color=Palette.success.soft()           # soft tint
color=Palette.blue                     # named hue
color=Palette.next("worker_0")         # stable categorical
color=Palette.literal("#8b5cf6")       # explicit hex (escape hatch)

theme = Theme.slides()                 # rounded-corner presentation theme
theme = Theme().with_overrides(unit=8.0)
```

`Palette.next(key)` is idempotent: the same key always returns the
same colour within a process, so cross-panel consistency is free.

## When you actually need manual placement

Avoid it. Ninety-five percent of the time the answer is:

* "I want these things centred" -> put them in a `Row` with `align="center"`.
* "I want two things at the same horizontal axis" -> use a `Column`
  with `align="center"`.
* "I want equal-width cells" -> `Row(..., equal_widths=True)` or
  `LabeledChain`.
* "I want shared column widths across rows" -> `Grid`.
* "I want decorative arrows" -> `Connect` (inline / routed / bus).

If you still need a custom layout, subclass `Element` and implement
`measure(theme)` + `render(canvas, x, y, theme)`; containment is the
only rule.
