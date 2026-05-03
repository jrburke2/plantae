# Archetype templates

Each `<name>.lpy.j2` is a Jinja2 template parameterized over a species
YAML. The codegen (Step 4) reads `species.archetype` to pick the template
and renders it with the species' parameter blocks.

This is the **developer surface**, not the contributor surface.
Botanists work in `species/`. Archetype maintainers work here.

---

## Locked conventions

These hold across every archetype template. Templates that violate them
break multi-specimen scene composition and the viewer.

### Coordinate system

- **Up axis: +Y** (matches three.js + glTF default; no rotation in viewer).
- **Origin: geometric base** of the plant, where it emerges from the ground.
  Specimen at world origin sits its crown at (0, 0, 0).
- **Right-handed.** PlantGL's turtle is right-handed by default; do not flip.

### Internal length unit

- **Meters.** Always meters inside generated .lpy files, the renderer, and
  the viewer.
- The species YAML declares its own length unit (in, cm, m, mm, ft, yd, or
  custom). The codegen normalizes to meters before .lpy emission via
  `species.units.length_to_meters(value)` and `length_range_to_meters(...)`.
- Templates reference fields like `{{ rosette.leaf_length_max_m }}` —
  the codegen pre-computes the `_m` variants from the species' native
  length unit and injects them into the template context.

### Angles

- **Degrees throughout.** L-Py's `+(angle)`, `/(angle)`, `&(angle)` all
  take degrees. No conversion needed.
- Field-name suffix is `_deg` for explicit angles in YAML and templates.

### Time

- **Calendar coordinates: day-of-year (1..366)**, suffixed `_doy`.
- **Growth-window durations: days**, no suffix (e.g. `LEAF_GROWTH_DAYS = 14`).
- **Slider `T_RENDER`: fractional day-of-year (1..366).** A renderer call
  with `T_RENDER=180.0` interprets at June 29 (DOY 180).
- **Phenology DOYs are MEDIAN dates.** Per-specimen variation comes from
  `EMERGENCE_OFFSET`, drawn once per specimen at axiom time and persisted.
  Templates compute effective phenology as `<event>_doy + EMERGENCE_OFFSET`
  before comparing to `T_RENDER + TIME_OFFSET_DOY`.

  Phase 0 sets `EMERGENCE_OFFSET = 0` (no jitter). Phase 1+ wires
  `phenology.emergence_jitter_days` from the species YAML to a
  `random.gauss(0, jitter)` draw at file top.

### Growth windows (Phase 0 hardcoded; extensibility planned)

Phase 0 templates use scalar constants for module growth windows
(`LEAF_GROWTH_DAYS = 14`, `CULM_GROWTH_DAYS = 1`, etc.). They are NOT
exposed via species YAML in Phase 0.

The architecture supports three later sources:
- (b) per-species YAML `growth_windows` block overriding the archetype defaults
- (c) derivation from phenology DOYs (e.g. `leaf_growth_days = peak_doy - leaf_flush_doy`)
- stochastic per-instance draws via `growth_functions.draw_growth_days(rng, mean, stddev)`,
  baked into module parameters at production firing so they persist
  across interpretation passes (same pattern as Andropogon's stochastic tiller heights).

When Phase 1 adds these, the call site changes from `LEAF_GROWTH_DAYS`
(constant) to `draw_growth_days(...)` (returns a float). Templates already
import from `growth_functions` so the swap is local.

### Externs every template must declare

The codegen always passes these via `extern(...)`. Templates reference them:

```
extern(T_RENDER = 180.0)            # slider time, fractional DOY (1..366)
extern(SPECIMEN_SEED = 42)          # rng = seeded_rng(SPECIMEN_SEED) at file top
extern(TIME_OFFSET_DOY = 0.0)       # for specimens established in prior years
extern(EMERGENCE_OFFSET = 0.0)      # per-specimen jitter around phenology medians
extern(POSITION_X_M = 0.0)
extern(POSITION_Y_M = 0.0)
extern(POSITION_Z_M = 0.0)
```

Phase 0 only ever sets `T_RENDER` from the slider; the rest stay at
defaults. Phase 3 scene composer sets per-specimen values to compose
communities. Templates should NOT hardcode any of these.

`EMERGENCE_OFFSET` is set by the codegen to a per-specimen Gaussian draw
(jitter scale from species YAML), seeded by `SPECIMEN_SEED` via
`plant_sim.runtime.pcg.seeded_rng`. Phase 0 jitter is 0 (no variation);
Phase 1 reads `phenology.emergence_jitter_days` from YAML.

Templates use the portable PCG-XSL-RR-128/64 RNG via
`from plant_sim.runtime.pcg import seeded_rng` and a single `rng =
seeded_rng(SPECIMEN_SEED)` at file top. Same algorithm in Python (here)
and TypeScript (V2.1+ browser runtime), gated by a CI parity test.

### Module declaration discipline

- Every multi-character module name needs an explicit `module Name(params)`
  declaration at the top. The codegen emits these from the YAML.
- Every queryable module gets the persistent-marker pattern injected by the
  codegen (the `expanded` flag + `if expanded: produce self(...,True)`
  guard). Templates reference the queryable status via the
  `queryable_production` Jinja macro.

### Interpretation rules

- Single-line `-->` rules only. The L-Py parser does not accept indented
  multi-line continuation of `-->` rules (Spike 1 finding).
- Use `:` + `produce` form for multi-line bodies.
- Color slot indices stay in `0..6` — PlantGL silently clamps higher
  values. Templates emit `material_id` parameters; the renderer applies
  materials from `materials/library.json`. Do not hardcode `;(N)` color
  selectors except for bookkeeping-hide rules.

### Bookkeeping-hide rules

Every internal dispatcher module (Plant clock, RecursiveBundle helpers)
needs a `--> ;(0) f(0)` interpretation rule so it doesn't accidentally
draw geometry.

### Every renderable turtle move belongs in a module

The exporter (`plant_sim.render.export`) walks the lstring and pairs each
PlantGL Shape with the `material_id` parameter on the corresponding
renderable module (convention: last param is a string). If a template
emits a raw `F()`, `~l()`, or `@O()` outside of a module, the resulting
shape has nowhere to attach a `material_id` and the exporter aborts with
a "renderable/shape mismatch" error.

**Wrap every renderable turtle move in a module that carries a mat_id.**
Echinacea uses `ScapeSegment(t_birth, seg_len_m, mat_id)`; Andropogon
uses `CulmSegment(t_birth, length_m, mat_id)`. Both produce `F(grown_m)`
in their interpretation rule. The pattern:

```lpy
module CulmSegment(t_birth, length_m, mat_id)

# In a producer (e.g. LeafLadder):
produce CulmSegment(current_t, seg_len_m, CULM_MAT) [/(rotation) GrassLeaf(...)] LeafLadder(...)

# Interpretation:
CulmSegment(t_birth, length_m, mat_id) :
    age = T_RENDER + TIME_OFFSET_DOY - (t_birth + EMERGENCE_OFFSET)
    if age < 0:
        produce *
    grown_m = sigmoid_grow(age, GROWTH_DAYS, length_m)
    produce ;(N) F(grown_m)
```

Discovered during Step 8 (Andropogon online). The convention is enforced
by the exporter's `Renderable/shape mismatch` error — fast feedback.

---

## Adding a new archetype

1. Add a Pydantic parameter block in `plant_sim/schema/species.py`.
2. Add the archetype name to `ArchetypeName` literal and
   `_ARCHETYPE_TO_PARAMS` dict.
3. Write `templates/archetypes/<name>.lpy.j2` following the conventions above.
   Include a `template_version: 1.0.0` line in the leading Jinja comment
   block (see "Template versioning" below).
4. Write a reference-species YAML demonstrating the archetype.
5. Add tests covering schema validation and template rendering.
6. Document the archetype's parameter reference here.

---

## Template versioning

Each archetype template carries a semver-shaped marker in its leading
Jinja comment block:

```
{# rosette_scape_composite.lpy.j2

template_version: 1.0.0
...
#}
```

The codegen extracts this version and bakes it into every generated
`.lpy` as `extern(TEMPLATE_VERSION = "X.Y.Z")` plus
`extern(TEMPLATE_ARCHETYPE = "<name>")`. The exporter passes both
through into the sidecar JSON `meta`, and the viewer surfaces them next
to the seed (e.g. `XQF2-D6S1 (rosette_scape_composite v1.0.0)`).

### Bump rules

- **Patch (1.2.x):** comment changes, refactors, parameter renames that
  don't move the geometry produced for any committed seed.
- **Minor (1.x.0):** new optional features or additive changes
  (e.g. a new module that defaults off, an extra material slot).
  Existing seeds still render the same plant.
- **Major (x.0.0):** changes that produce visibly different plants for
  existing seeds (e.g. switching the phyllotaxy formula, changing the
  growth-window interpolation, swapping the RNG draw order).

A future CI gate will detect bumps automatically by rendering a fixed
`(template, seed)` regression set and comparing geometry hashes; for now
the bump is a manual judgement call by the template author.

### When to break vs. when to migrate

A major bump is a *deliberate* break in seed → specimen reproducibility.
For most edits — clarifying a comment, renaming a constant, adjusting
template structure that doesn't move modules — patch suffices.

When a major bump is unavoidable, V2.2+ will surface a "this plant
looks different now because the template was updated" UI in the viewer,
keyed off the version stored alongside the seed.
