# Debugging sciviz layouts

When a figure comes out wrong, the question is usually one of:

1. **Why did the router pick that path?** (too many corners, wrong side,
   grazing obstacles)
2. **Why did the label land there?** (overlap, wrong side, extrapolated
   beyond the spine)
3. **What did the automatic systems actually see?** (which anchors,
   which regions, which obstacles)

sciviz ships a per-diagram debug viewer that answers all three in one
HTML file.

## The 30-second tour

```python
from sciviz import Diagram, Row, Anchor, Box, Connect

d = Diagram(body=Row(
    Anchor("a", Box("alpha")),
    Anchor("b", Box("beta")),
    Connect("a", "b", label="to beta"),
))
d.save_debug("debug.html")
```

Open `debug.html` in any browser. You'll see the rendered diagram on
the left, a sidebar on the right with:

* per-overlay checkboxes (anchors, regions, routed paths, label
  obstacles, label candidates, chosen label rect)
* a summary table (total routed paths, paths that retried without
  clearance, label placements, labels with non-zero overlap)
* a list of every router decision and every label decision — click
  one to highlight it in the canvas

Scroll inside the canvas to zoom, drag to pan.

## From the command line

If the figure lives in a standalone `.py` file (e.g. anything in
`gallery/`), skip writing any `save_debug` call:

```bash
sciviz-debug gallery/roofline.py -o roofline.debug.html
```

The script is imported and the first top-level `Diagram` it binds
is used. To pick a specific one, use `--name`:

```bash
sciviz-debug my_figure.py --name fig2 -o fig2.debug.html
```

## What the overlays mean

| Layer               | Colour                | What you see                           |
|---------------------|-----------------------|----------------------------------------|
| Anchors             | thin blue             | every `Anchor(...)` rectangle          |
| Regions             | dashed orange         | `Region` / `BlockGroup` boundaries     |
| Routed paths        | solid green           | the polyline each routed `Connect` emitted |
| Label obstacles     | faint grey fill       | rectangles the label placer avoids     |
| Label candidates    | thin blue / pink      | every rect the placer scored — red if it overlapped an obstacle |
| Chosen label rect   | pink dashed + fill    | the winning candidate, plus the segment it labels |
| Highlight           | solid red             | the currently-inspected routed path    |

Clicking a decision in the sidebar automatically enables the relevant
layers and scrolls it into view.

## Diagnosing typical problems

### "My arrow takes a five-segment detour."

Inspect the router record. Look at:

* `retried_without_clearance: true` — the planner could not find a
  path with the default 8px clearance and fell back to edge-grazing.
  The fix is usually to move or shrink one of the obstacles.
* `required_crossings` — if this list includes a region the arrow
  shouldn't really be crossing, your source and destination anchors
  live in different `Region` / `BlockGroup` containers. Pull one
  anchor out, or extend the enclosing region.

### "My label sits in the wrong place."

Inspect the label record. The sidebar shows:

* `candidates considered: N` — if N is tiny, the spine is too short
  for good options. Lengthen the connector or let the label use a
  secondary side.
* `overlap: x.xx` — non-zero means every candidate hit something;
  the placer picked the least-bad. A sibling's bbox is the usual
  culprit.
* `chosen.side = extrapolated` — the segment itself is so crowded
  that the placer had to step beyond the endpoints. Usually means
  the connector is too short.

### "The arrow comes out the wrong face of my box."

Watch `src_side` / `dst_side` in the sidebar. "auto" means the planner
picked; if it's picking the wrong face, override with
`Connect(..., src_side="right", dst_side="left")`.

## Programmatic access

If you prefer analysing decisions in a notebook instead of a browser,
use the recorder directly:

```python
from sciviz.auto.debug import DebugRecorder, record_into

rec = DebugRecorder()
with record_into(rec):
    d.save("figure.svg")

print(rec.summary())
# {'label_placements': 4, 'label_overlap_nonzero': 1,
#  'router_paths': 6, 'router_retried': 0, 'notes': []}

for p in rec.router_paths:
    if p.retried_without_clearance:
        print("tight route:", p.src_name, "→", p.dst_name)
```

The recorder is **opt-in**: instrumentation sites become no-ops when
no recorder is installed, so normal rendering pays nothing.

## Where the data comes from

Two subsystems emit records:

* `sciviz.auto.router.plan_path` — every routed `Connect` (including
  the endpoints of a bus spine) emits one `RouterRecord`.
* `sciviz.auto.labelplacer.place_label` — every auto-placed label
  (bus spine labels, long-wire labels) emits one
  `LabelPlacementRecord` listing every candidate the solver scored.

The data classes live in `sciviz/auto/debug.py` and are dataclasses
— easy to introspect, serialise, or export to CSV if you want to
dump a production run.

## Limitations

* Only the **automatic** layers are recorded. Manually-positioned
  primitives (the author wrote an explicit `width=...`) do not produce
  records because there's nothing to explain.
* The HTML viewer assumes a reasonably modern browser (anything with
  CSS grid and `PointerEvent`; i.e., 2019+).
* Label records are bound by `owner: str` only when the calling code
  supplies one; bare usages show as `(unnamed)`.
