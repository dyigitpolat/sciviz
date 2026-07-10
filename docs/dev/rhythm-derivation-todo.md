# Rhythm derivation TODO

Status: design note; no public API is proposed as stable yet.

## Goal

SciViz authors should declare content, semantics, and visual ideas. The library
should derive a coherent visual rhythm that is immediately suitable for a
research paper: typography, component scale, spacing, padding, strokes,
arrowheads, routing clearance, plot geometry, and negative space should feel
like one designed system.

Rhythm is not a global "make this figure smaller" factor. It is the set of
relationships between visual quantities:

- headline, section, node, tick, annotation, and caption type;
- text size, line height, padding, and wrapping width;
- node size, plot viewport, data marks, and surrounding panels;
- border, data-line, connector, arrowhead, and grid weights;
- sibling gaps, panel insets, route corridors, and outer margins;
- the amount and distribution of occupied and unoccupied space.

A simple three-node flow should use larger, more generous elements than a
dense six-panel dashboard. A dense chart inside that dashboard may compact its
ticks and marks without miniaturising an adjacent simple architecture panel.
The result must remain deterministic, readable at its final physical size,
and faithful to every declared semantic item and relationship.

## Existing contracts to preserve

Rhythm derivation should extend the current architecture rather than create a
second styling system.

- `Theme` is the single source of truth for semantic type roles, spacing,
  wrapping, stroke weights, arrow size, and colour.
- `Element.measure(theme)` and `Element.render(...)` are the composition
  boundary. Rendered ink must remain inside the measured box.
- `content_bbox`, `primary_anchor_bbox`, `inflate_to`, shared columns, shape
  peers, and stretch absorbers already let containers negotiate alignment and
  usable size without author coordinates.
- `Diagram` already owns deep-copied layout trials, scratch rendering,
  reflow alternatives, target-width fitting, target-aspect ranking, automatic
  growth, and trimming.
- `target_width_pt` gives typography a physical meaning. Its current contract
  is important: spacing and wrapping may compress, but fonts are not silently
  reduced below their authored printed size.
- Numeric dimensions are explicit author locks. Semantic values such as
  `size="md"`, `gap="sm"`, and `text_size="label"` are the values eligible for
  automatic resolution.

The eventual pipeline should be:

```text
authored semantics + base Theme + output target
        -> semantic demand analysis
        -> rhythm candidate generation and local negotiation
        -> target-width/aspect fitting
        -> validated layout and render
```

Target fitting and rhythm selection must be one coordinated pipeline. Two
independent passes that both change `unit`, wrapping, or component footprints
will oscillate or undo each other's decisions.

## What not to repeat

Do not walk arbitrary object attributes, count every discovered object, reduce
the result to one pressure number, select one of a few thresholds, and then
uniformly scale the entire theme.

That approach fails for structural reasons:

- Ten data points, ten peer nodes, and ten decorative wrappers do not create
  the same visual pressure.
- A count has no meaning without available area and intended physical size.
- One global factor cannot repair local crowding and local emptiness at the
  same time.
- Thresholds introduce large visual jumps when one label or node is added.
- Uniform plot scaling changes layout feedback while ignoring ticks, legends,
  bar widths, and annotations that actually cause the crowding.
- Generic attribute reflection is brittle, can count aliases twice, and does
  not know which wrappers are visually transparent.
- A layout can pass unit tests while remaining visually unbalanced.

A global density estimate may be useful as one candidate seed. It must not be
the decision mechanism.

## Strategy comparison

| Strategy | Strength | Limitation | Intended use |
|---|---|---|---|
| Global density tiers | Cheap, deterministic, easy to explain | Cannot handle mixed local density; threshold jumps | Candidate seeds only |
| Bounded candidate search | Uses actual measured and rendered outcomes | Needs reliable telemetry and a controlled search space | Recommended figure-level engine |
| Local container negotiation | Handles crowded and sparse regions in one figure | Requires explicit demand and alternative-size protocols | Recommended complement to candidate search |
| Learned ranking | Can encode subtle aesthetic preferences | Opaque, data-hungry, and difficult to make stable | Defer until deterministic metrics and a corpus exist |

The recommended direction is bounded, target-aware candidate search with
local negotiation. A learned model may rank already-valid candidates later;
it should never be responsible for correctness, information preservation, or
legibility.

## 1. Collect semantic demand as a vector

Add one internal, typed protocol rather than another class-name switch or
attribute walker. The exact names are provisional:

```python
@dataclass(frozen=True)
class RhythmDemand:
    text_by_role: Mapping[str, TextDemand]
    visible_leaves: int
    data_marks: int
    relationships: int
    labeled_relationships: int
    max_parallelism: int
    nesting_depth: int
    repeated_instances: int
    legend_items: int
    axis_ticks: int
    annotations: int
    flexibility: Flexibility

class Element:
    def iter_children(self) -> Iterable[Element]: ...
    def rhythm_demand(self) -> RhythmDemand: ...
```

`TextDemand` should record role, line count, longest unbreakable run, total
characters, wrapping opportunities, and whether the content is math, code, or
ordinary prose. `Flexibility` should describe whether an element may wrap,
reflow, change a semantic size tier, stretch, or must retain an explicit
numeric dimension.

Containers aggregate child demand and add topology. Specialized charts report
marks, series, categories, ticks, legends, annotations, and aspect
preferences directly. Transparent metadata and connection specifications do
not pretend to be visible nodes. Custom elements get a conservative default
and may implement the protocol without importing the rhythm engine.

This protocol also fixes a broader traversal problem: `Diagram` currently
finds reflowable descendants through known fields. One canonical child
iterator should serve reflow discovery, rhythm analysis, diagnostics, and
future tree tooling.

## 2. Derive a coordinated profile, not independent token guesses

A candidate `RhythmProfile` should have several coupled dimensions:

- a type ladder, preserving role order and minimum ratios;
- global and scoped spacing density;
- wrapping targets;
- panel and node padding;
- component-size tier preferences;
- chart viewport, axis, legend, tick, marker, and data-ink geometry;
- border, grid, connector, and data-line weights;
- arrowhead, endpoint tap, and routing-clearance geometry.

Do not optimize each raw token independently. Generate a small family of
coherent candidates around the authored theme and enforce invariants such as:

```text
title > panel title >= section > label > small > tiny > micro
grid < border <= data line
border < connector, unless the connector is intentionally secondary
arrowhead size is proportional to connector weight
padding is proportional to the text line height it surrounds
```

The base theme remains the SSOT. A profile is an immutable derived overlay,
not a new public theme vocabulary. Derived themes must receive fresh mutable
render state rather than sharing `_bg_stack` through a shallow copy.

Explicit numeric values are hard constraints. If an author supplies a numeric
font size, width, height, gap, marker radius, or stroke, rhythm derivation may
measure it but must not rewrite it. Semantic values opt into derivation.

## 3. Make physical size part of the decision

Typography cannot be judged without knowing the printed scale. When
`target_width_pt` is present, every candidate can enforce the actual minimum
font size in points and the final stroke weight. This is the reliable path for
paper-ready automatic rhythm.

Without a physical target, the conservative policy should retain authored
font sizes. The engine may still select wrapping, reflow, semantic component
tiers, and local spacing, but it should not claim that an intrinsic SVG font
is paper-legible at an unknown placement scale.

The current target fitter should consume the selected rhythm profile as its
base. It may tighten spacing and wrapping within declared floors, but should
not independently choose a second typography or component scale.

## 4. Negotiate local pressure

Figure-wide rhythm establishes hierarchy; local scopes solve heterogeneous
content. Useful scopes are:

- the whole figure;
- a panel or card;
- a row or grid of visual peers;
- one chart and its axis/legend system;
- one repeated architecture module.

A parent knows the area and peer relationships it can offer. A child knows
which semantic alternatives it can render. Generalize the existing
`_reflow_options` idea into bounded layout alternatives such as:

```text
preferred semantic tier + minimum tier
single-line label / wrapped label
legend inside / legend outside
3 columns / 2 columns / 1 column
full ticks / thinned ticks
```

Alternatives must preserve content. "Thin ticks" means select a valid subset
of redundant scale marks; it never means remove a category, series,
annotation, state, relationship, or code line.

Peer groups should resolve together. Equal panels should use compatible title
sizes, padding, and component weight even when one child is locally denser.
Local density should be bounded relative to the figure profile so a dashboard
does not look like unrelated themes pasted together.

There are two implementation options worth prototyping:

1. A private `RhythmPlan` side table keyed by stable element paths. This keeps
   the public `measure(theme)` contract but requires every rhythm-sensitive
   element to consult one resolver.
2. An internal layout context carrying `Theme`, output target, and scoped
   rhythm. This is architecturally cleaner but requires a careful migration of
   the `Element` contract and compatibility for custom elements.

Do not attach sticky trial decisions to the author's original tree. Existing
`inflate_to` and wrapping floors can mutate during measurement, so candidate
analysis must continue to use deep copies. The selected plan must be applied
once, deterministically, to the final render tree.

## 5. Evaluate real candidates

Use a bounded deterministic search, not an open-ended optimizer. Generate a
small set of candidates from semantic demand and the output target, prune
impossible ones early, then measure and scratch-render deep copies. Cache by a
semantic tree signature plus base-theme and output-target hashes.

Rank candidates lexicographically. Hard constraints must never be traded for
a better aesthetic score.

### Hard constraints

- Every semantic item and relationship in the input inventory survives.
- No text, marker, arrowhead, or visual component is clipped.
- Text and labels do not overlap unrelated content.
- Connectors do not pass through nodes; endpoint normal segments meet the
  configured minimum printed length.
- Minimum effective font and stroke sizes are respected.
- Explicit numeric author values remain exact.
- Colour contrast stays above the paper-theme floor.
- Measure/render containment and deterministic output hold.

### Soft objectives

- meet the target width and requested aspect range;
- preserve a clear type hierarchy;
- keep peer padding, widths, baselines, and visual weights consistent;
- avoid extreme outer-margin asymmetry;
- avoid large accidental empty corridors inside panels and between stages;
- avoid both cramped and excessively loose local occupancy;
- minimize connector detour, bends, crossings, and parallel overlap;
- keep chart marks, axes, legends, annotations, and viewport in balance;
- prefer the least intervention from the authored theme.

Whole-canvas ink occupancy is not a sufficient whitespace metric. A figure
can have a reasonable global ratio and still contain an empty half-panel.
Collect structured telemetry for outer margins, each panel interior, peer gap
variance, largest empty corridor, alignment landmarks, and component-level
ink. Legitimately sparse diagrams should not be filled merely to maximize an
occupancy percentage.

Canvas currently exposes overall `ink_bbox` and minimum text size. Add neutral
layout/render telemetry rather than parsing generated SVG. Raw paths and text
must publish accurate ink bounds before those measurements can be trusted.

## 6. Centralize semantic component geometry

Theme-aware gaps and type already exist, but component geometry remains
fragmented across local dictionaries and fixed constants. Plots are the first
high-value migration target:

- plot viewport alternatives;
- left/right/top/bottom axis budgets;
- tick and axis-label roles;
- tick thinning and label rotation;
- legend footprint and placement;
- bar width, intra-group gap, inter-group gap, and panel inset;
- marker radius, data-line weight, grid weight, and annotation clearance.

These values should resolve through one internal semantic geometry service or
profile. Do not add a generic `plot_scale` to `Theme`: a uniform viewport
factor cannot coordinate the axis, marks, text, and surrounding layout.

After plots, migrate matrices, timelines, repeated modules, miniature plots,
and connector micro-geometry. Each migration should remove duplicated local
constants and add component-specific demand and telemetry.

## 7. Keep the author API small

The desired eventual front door is no larger than:

```python
Diagram.for_paper(
    body,
    target_width_pt=252,
    rhythm="auto",
)
```

Do not expose pressure numbers, per-panel density, font multipliers, plot
scales, or optimization weights as normal author arguments. Authors already
express importance through semantic roles and structure. Add a new semantic
author concept only when the corpus proves the existing vocabulary cannot
represent the intent.

An advanced diagnostic API is more valuable than more tuning knobs:

```python
diagram.explain_rhythm()
```

It should report the semantic inventory, output target, candidates considered,
selected profile, local decisions, constraint violations, floors reached,
explicit opt-outs, and score breakdown. Automatic behavior that cannot
explain itself will be difficult to refine safely.

Keep the feature opt-in until it consistently beats the authored default.
Changing the default is a later product decision, not part of the first
implementation.

## Delivery plan

### Phase 0: lock the evaluation discipline

- [ ] Freeze a representative benchmark subset spanning sparse flows, dense
      dashboards, charts, matrices, repeated modules, and mixed-density
      composites.
- [ ] Store semantic inventories so image quality cannot improve through
      information loss.
- [ ] Keep every comparison round in a new directory.
- [ ] Use isolated PNG-to-PNG visual review separately from declarative-code
      review.
- [ ] Record the current default as the regression baseline.

### Phase 1: add observation without changing output

- [ ] Add canonical `iter_children()` and typed `RhythmDemand` aggregation.
- [ ] Add structured layout, ink, collision, whitespace, and routing telemetry.
- [ ] Add `explain_rhythm()` in report-only mode.
- [ ] Audit theme-sensitive caches and scratch-render ink bounds.

### Phase 2: build a shadow candidate engine

- [ ] Define immutable profile invariants and a bounded candidate generator.
- [ ] Evaluate candidates on deep copies while rendering the authored default.
- [ ] Log why the shadow winner differs from the default.
- [ ] Verify deterministic selection, bounded runtime, and zero author-tree
      mutation.

### Phase 3: enable safe geometry decisions

- [ ] Integrate spacing, wrapping, and existing reflow alternatives first.
- [ ] Resolve peer groups and local scopes coherently.
- [ ] Keep typography and explicit component dimensions unchanged.
- [ ] Merge target fitting into the same candidate objective.

### Phase 4: mature plots and component geometry

- [ ] Migrate line, scatter, and grouped-bar geometry to semantic resolution.
- [ ] Add chart demand, local occupancy, tick/legend collision, and data-ink
      metrics.
- [ ] Migrate matrices, timelines, repeated structures, and micro-plots.

### Phase 5: enable target-aware typography and stroke rhythm

- [ ] Derive type ladders only when final physical size is known.
- [ ] Enforce printed font/stroke floors and hierarchy ratios.
- [ ] Coordinate connector, border, data-line, grid, marker, and arrow weights.
- [ ] Prove mixed-density figures do not globally miniaturize simple panels.

### Phase 6: opt-in benchmark release

- [ ] Render the complete benchmark and run blind visual/declarative reviews.
- [ ] Reject candidates with any semantic loss or hard violation regardless of
      aesthetic score.
- [ ] Publish diagnostics for every benchmark decision.
- [ ] Consider a default-on policy only after broad no-regression evidence.

## Test and acceptance criteria

Unit and property tests should cover:

- deterministic, idempotent selection and rendering;
- no mutation of the authored tree during candidate trials;
- transparent-wrapper invariance;
- stable aggregation under equivalent composition wrappers;
- semantic sizes respond while numeric sizes remain exact;
- type hierarchy, contrast, and printed legibility floors;
- target fitting begins from one selected rhythm and does not oscillate;
- larger available physical area never selects a denser profile without a
  semantic reason;
- adding one label causes a local/reflow response, not a discontinuous global
  theme jump;
- peer reordering does not change shared size decisions;
- mixed-density panels resolve locally while retaining one figure hierarchy;
- chart matrices over varying series/category counts remain collision-free;
- routing clearance and endpoint perpendicularity scale with final stroke;
- repeated measure/render calls produce identical geometry and bytes.

Benchmark acceptance should require:

1. complete semantic inventory preservation;
2. zero clipping, unrelated overlap, node-crossing connectors, or unreadable
   contrast;
3. minimum effective print sizes at the declared target;
4. materially improved alignment, whitespace distribution, visual-weight
   balance, and plot maturity on the focused corpus;
5. no material regression on examples outside the focused corpus;
6. declarative attempts that do not gain manual coordinates or one-off theme
   overrides to compensate for the engine.

Automated scores are gates and diagnostics, not the final aesthetic oracle.
The final loop must still include hostile, isolated visual review that compares
the reference PNG and generated PNG without seeing implementation intent.

## Open decisions

- Is a physical target mandatory for automatic typography, or should intrinsic
  figures declare an output class such as paper/slides?
- Should scoped decisions use a side-table `RhythmPlan` or a migrated internal
  layout context?
- Which telemetry belongs in `Canvas`, and which belongs in layout elements?
- How should legitimate sparse space be distinguished from accidental empty
  corridors?
- What is the maximum candidate budget that remains interactive for large
  diagrams?
- Which semantic-size dictionaries can be unified without erasing meaningful
  component-specific choices?
- What minimum improvement/no-regression threshold is required before
  `rhythm="auto"` can become a default?

The first implementation task is observation, not scaling: build the semantic
inventory and telemetry, run them against the benchmark, and inspect whether
the proposed signals actually explain the failures before allowing them to
change a single rendered pixel.
