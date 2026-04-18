# Topological boundary router

## Motivation

The current `Flow` router in `sciviz/composition.py` reasons over a flat set
of anchor rectangles. Every anchor is either an obstacle or one of the two
endpoints; `Region` and `BlockGroup` borders are invisible. That produces
two observable failure modes:

* `_out/deepseek_v3.svg`: every "Cross-Entropy Loss -> L^k" arrow collapses
  into a 5-segment notched path because the straight horizontal would graze
  the `FP32` sub-badge bbox.
* `_out/ttt_mlp.svg`: the `dW -> wdown_i` feedback loop becomes a 5-segment
  detour because `_hblocked` / `_vblocked` treat every anchor as a hard
  obstacle and the visible `Apply` / `Update` dashed regions contribute no
  information to the router.

The user's mental model is simple:

> From source to sink, decide what boundaries **need** to be crossed.
> Prevent any other boundary from being crossed, so the arrow does not go
> through irrelevant objects.

We implement exactly that as a shared, pure-Python path planner that all
connector elements (Flow, Labeled, Bus, Arrow, Connector) delegate to.

## Design

### `sciviz/routing.py`

A new module, rendering-free, unit-testable.

```python
@dataclass(frozen=True)
class Box:
    x: float; y: float; w: float; h: float
    name: str = ""
    kind: str = "anchor"          # "anchor" | "region"

@dataclass(frozen=True)
class Endpoint:
    anchor: Box
    side: str                     # top|bottom|left|right|auto
    tap: float = 8.0

@dataclass(frozen=True)
class Plan:
    waypoints: List[Tuple[float, float]]
    crossings: List[str]          # region names legitimately crossed
    style_hint: str               # "direct"|"L"|"U"|"staircase"

def plan_path(src: Endpoint, dst: Endpoint, *,
              anchors: Sequence[Box],
              regions: Sequence[Box],
              policy: CrossPolicy = DEFAULT_POLICY) -> Plan: ...
```

### Topology

1. Build the containment DAG over `regions`: region R contains box B if the
   centre of B is in R. Regions may nest.
2. For each endpoint compute `ancestors(endpoint)` = enclosing regions
   innermost-first.
3. **Required crossings** = symmetric difference of the ancestor lists. The
   path must exit each region on `ancestors(src) \ ancestors(dst)` and
   enter each region on `ancestors(dst) \ ancestors(src)` exactly once.
4. **Anchor obstacles**: every anchor in `anchors` except src and dst, no
   matter where it lives.
5. **Region obstacles**: every region not on either ancestor list. Regions
   on one-only list are permeable at exactly one crossing.

### Candidate enumeration

Try, in order of increasing corners; return the first plan that passes the
topology check:

1. 0 corners - straight segment when collinear with src/dst centres.
2. 1 corner - `L` with the elbow at either `(dx, sy)` or `(sx, dy)`.
3. 2 corners - `U` / `Z` via a bridge column or row; bridge chosen from
   the maximal free slice inside the allowed x/y slab.
4. 4-corner staircase fallback, same as the current router but gated by
   the topology check.

The topology check computes, for every segment, the set of region
boundaries the segment crosses (axis-aligned segment vs axis-aligned
rectangle intersection). It rejects a candidate if any segment crosses a
boundary not in the required-crossings set, or intersects an anchor
obstacle.

### Renderers

```python
def render_orthogonal(canvas, plan, *, stroke, width, dash, marker_end): ...
def render_curved(canvas, plan, *, stroke, width, dash, marker_end,
                  curvature: float): ...
```

`render_curved` smooths the waypoints with a cardinal cubic spline that
passes through every waypoint with cardinal endpoint tangents so the
arrowheads align with the last segment direction. Both renderers consume
the same `Plan`.

### Making `Region` / `BlockGroup` visible

Currently only `Grid` publishes `__region_col*` entries. We extend:

* `Region.render` in `sciviz/composition.py`: register
  `("__region_<id>", bbox)` on the anchor stack during render.
* `BlockGroup.render` in `sciviz/structures.py`: same.

`Flowed.render` forwards all registry entries with the `__region_` prefix
to `plan_path` as the `regions` list.

### Wire-up

* `Flow._render`: endpoints built from registry, call `plan_path`, then
  `render_orthogonal` (when `style="orthogonal"`) or `render_curved`
  (otherwise). Delete the in-function `_vblocked` / `_hblocked` /
  `clamp_tap` and the three vertical / horizontal / mixed branches.
* `Labeled` already delegates to `Flow`; no change required.
* `Bus`: each branch spur calls `plan_path` with the spine as a local
  "region" so spurs do not cross other spurs.
* `Arrow` / `Connector`: gain an optional `plan=` input; keep the
  fixed-direction defaults for back-compat.

### Arrowhead unification

All routed connectors ask `routing._arrow_marker(canvas, theme, color,
stroke)` for one shared head. Delete per-element ad-hoc marker calls.

## Expected outcomes

| Case | Today | With planner |
|------|-------|---|
| deepseek_v3: `ce -> L^k` | 5 segs, notched | 1 seg, direct |
| ttt_mlp: `dW -> wdown_i` | 5 segs | 2 or 3 segs across the Apply/Update boundary |
| ttt_mlp: `teal -> loss` | 5 segs wrap | 1 seg, direct vertical |
| ttt_mlp: `apply_out -> yvec` | 2 segs, stepped | 1 seg, direct |
| ttt_mlp: backbone `inp -> mlp_plus` | 3 segs under diagram | same (already optimal) |

## Execution order

1. Add `sciviz/routing.py` (pure planner) + unit tests.
2. Add render helpers + tests.
3. Publish `Region` / `BlockGroup` bboxes to the anchor stack + test.
4. Rewrite `Flow._render` against the planner. Delete dead code.
5. Route `Bus`, `Arrow`, `Connector` through the planner where sensible.
6. Unify arrow markers.
7. Add scenario tests for deepseek and ttt_mlp.
8. Regenerate all galleries; run full pytest.
