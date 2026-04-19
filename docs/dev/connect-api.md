# Unified `Connect` API

**Status**: implemented (Phase 2 of the "address-eight-weaknesses" plan).

## Motivation

Before this refactor, `sciviz` exposed six classes that all answered the same
question — "how do I draw a line from A to B?":

| Old class   | What it is                                                   |
|-------------|--------------------------------------------------------------|
| `Arrow`     | Axis-aligned directed line inside a `Row`/`Column`.          |
| `Connector` | Thin alias over `Arrow` for ergonomic labels.                |
| `Flow`      | Orthogonally-routed arrow between two named anchors.         |
| `Flowed`    | Container that holds a tree of `Anchor`s + a list of `Flow`s.|
| `Labeled`   | "`Box` -> label" pattern, implemented on top of `Flow`.      |
| `Bus`       | Multi-endpoint spine with a single label.                    |

Authors had to pick the right one on each call site — they are orthogonal in
the implementation, but conceptually they are all "connect things". This
refactor replaces them with one element:

```python
Connect(src, dst, *, label=None, ...)
```

The element inspects the shapes of `src` / `dst` and picks a rendering mode
automatically. Authors never pass `mode=`.

## Signature

```python
Endpoint = str | Element | None

def Connect(
    src: Endpoint | list[Endpoint] = None,
    dst: Endpoint | list[Endpoint] = None,
    *,
    # ---- labels ---------------------------------------------------------
    label: str | list[str] | None = None,
    label_color: ColorRef | str = "muted",
    # ---- sides ----------------------------------------------------------
    src_side: str = "auto",  # "auto" / "left" / "right" / "top" / "bottom" / corner
    dst_side: str = "auto",
    # ---- appearance -----------------------------------------------------
    color: ColorRef | str = "text",
    dashed: bool = False,
    head: bool | str = True,         # True / False / "both" / "src" / "dst"
    # ---- routed mode only ----------------------------------------------
    style: str = "orthogonal",       # "orthogonal" / "curve" / "straight"
    curvature: float = 0.5,
    detour: float = 24.0,
    # ---- inline mode only ----------------------------------------------
    direction: str | None = None,    # "right" / "left" / "up" / "down"
    length: float | None = None,
    italic: bool = True,
    size: str | float = "small",
    # ---- bus mode only -------------------------------------------------
    orientation: str = "auto",       # "auto" / "horizontal" / "vertical"
): ...
```

## Mode auto-detection

The mode is a pure function of the argument shapes. The rule, in order:

1. **inline mode** — `src is None and dst is None`.
   Draws a standalone directed arrow at the current layout slot (inside a
   `Row` / `Column`). Requires `direction`. Absorbs `Arrow` / `Connector`.

2. **bus mode** — either side is a `list` of length ≥ 1 where
   `len(src) + len(dst) >= 3`, *or* either side is a `list` (with the
   opposite side also present). Operates over anchor names only.
   Absorbs `Bus`.

3. **routed mode** — both sides are single endpoints (either anchor
   names or `Element` references), and we did not land in inline or bus.
   If either endpoint is an `Element`, it is wrapped in an auto-`Anchor`
   with a synthesised unique name (`__connect_<id>_src` / `_dst`). This
   covers both `Flow` and `Labeled`.

If the rule produces an ambiguous combination (e.g. `src=None, dst="x"`),
`Connect` raises a clear `TypeError` at construction time.

### Examples

```python
# Inline (axis-aligned, standalone)
Row(boxA, Connect(label="map to", direction="right"), boxB)

# Routed (two named anchors)
Connect("encoder", "decoder", label="features")

# Routed (one side is a direct Element reference)
Connect(boxA, math_label, src_side="right", dst_side="left", style="straight")

# Bus (one source, three sinks)
Connect("main", ["mtp1", "mtp2", "mtp3"], label="Shared", dashed=True)

# Bus (many-to-one)
Connect(["e1", "e2", "e3"], "combine", label="expert outputs")
```

## Registry model

The underlying registry mechanism is unchanged:

- `Anchor(name, child)` still wraps a child and registers the child's
  rendered bbox in the active registry.
- The registry is a `ContextVar` stack, so nested `Connect`s see all
  anchors declared in any ancestor.
- A **container** (`Row`, `Column`, `Grid`, `Diagram`, ...) that finds
  any routed / bus `Connect` in its descendants installs an implicit
  `_FlowResolver` above the subtree and records every encountered
  `Connect` with that resolver, so the author never has to wrap
  anything in a `Flowed(..., flows=[...])`. `Flowed` is effectively
  lifted a level and made invisible.

Inline `Connect`s do not need a resolver — they render themselves in
line with their siblings, exactly like `Arrow` did.

## Capability parity

Every old call site maps to a `Connect` call:

| Old                                                                                | New                                                                        |
|-----------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| `Arrow(label="L", direction="right", length=140, color=c)`                        | `Connect(label="L", direction="right", length=140, color=c)`               |
| `Connector("map to", "hardware")`                                                  | `Connect(label=["map to", "hardware"])`                                    |
| `Flow("a", "b", src_side="right", dst_side="left", curvature=0, dashed=True)`      | `Connect("a", "b", src_side="right", dst_side="left", curvature=0, dashed=True)` |
| `Flowed(inner, flows=[Flow("a","b"), Flow("c","d")])`                              | `inner` with `Connect("a","b")` and `Connect("c","d")` placed anywhere     |
| `Labeled(box, math_label)`                                                         | `Connect(box, math_label, src_side="right", dst_side="left", style="straight", curvature=0)` |
| `Bus(sources="x", sinks=["a","b","c"], label="Shared", dashed=True)`               | `Connect("x", ["a","b","c"], label="Shared", dashed=True)`                 |

### Arrowhead semantics

`head` generalises the old boolean `arrow`:

- `True` (default): arrowhead at destination (one-way).
- `False`: no arrowhead.
- `"src"`, `"dst"`, `"both"`: explicit control.

### Label semantics

Inline mode accepts a `str` or `list[str]` (stacked perpendicular to the axis).
Routed mode accepts a single `str` placed along the curve.
Bus mode accepts a single `str` placed on the spine by the geometric placer.

## Implementation layout

```
sciviz/connect/
    __init__.py       # exports Connect, Anchor
    anchor.py         # the Anchor primitive (moved from composition.py)
    connector.py      # the Connect element (front door)
    _resolve.py       # mode detection + endpoint normalisation + auto-Anchor
    _resolver.py      # the implicit Flowed-equivalent that containers install
    inline.py         # inline geometry (absorbs Arrow)
    routed.py         # anchor-to-anchor routing (absorbs Flow / Flowed / Labeled)
    bus.py            # many-endpoint spine (absorbs Bus)
```

## Migration path

1. Phase 2b implements `Connect`.
2. Phase 2c ports every existing connector test to assert parity.
3. Phase 2d migrates all 12 galleries, with SHA-256 PNG comparison.
4. Phase 2e deletes `Arrow`, `Connector`, `Flow`, `Flowed`, `Labeled`,
   `Bus` entirely. Only `Connect` and `Anchor` remain.

After Phase 2 the entire "connecting things" vocabulary is two nouns.
