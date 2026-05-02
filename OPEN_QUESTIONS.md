# Open Questions

Running list of decisions deferred during Phase 0. Resolve in Phase 1+ unless they block.

**Principles:** see `engineering_principles.md`. New questions evaluate proposals against P1-P7 explicitly where alignment is non-obvious.

---

## Step 0 — Export format decision (RESOLVED 2026-05-02)

**Q:** glTF or OBJ + JSON sidecar?

**A:** OBJ + JSON sidecar. PlantGL has no glTF codec — `openalea.plantgl.codec` registers only `gts`, `json`, `obj`. Writing `scene.save('foo.gltf')` raises `Cannot find codec to write scene`.

**Bridge for material_id:** PlantGL `Shape.id` is stable per-derivation. OBJ exporter writes `o SHAPEID_<id>_<addr>` per shape (verified 155 groups for 155 shapes). three.js OBJLoader exposes the group name as `mesh.name`. Sidecar JSON maps `{shape_id: material_id}`. Viewer reads both and applies materials from the library.

This downgrades v0.3.1 §10's "glTF as the primary export format" to "OBJ + JSON sidecar for Phase 0 to 3, revisit if glTF support lands in PlantGL or we write a custom exporter."

A custom glTF exporter (PlantGL Scene → triangles → pygltflib + userData) is feasible (~3-5 hr work) but not necessary for Phase 0. Logged as a Phase 3+ improvement if WebGPU instancing performance demands it.

---

## Step 2 — Archetype escape hatch (RESOLVED 2026-05-02)

**Q:** What happens when a species needs morphology that doesn't fit any existing archetype template?

**A:** `Species.template_override: str | None` field added. When set to a path like `templates/custom/some_species_specific.lpy.j2`, the codegen uses that template instead of the archetype default. Most species leave it null and inherit the archetype.

Default policy: build more archetype templates over time (option (a) from the discussion). The override field is the safety valve for genuinely one-off species without forcing a developer to ship a new shared archetype just for them.

Rejected: free-form `custom_productions:` YAML hooks that inject snippets into the generated .lpy. Too much footgun risk for non-technical contributors.

---

## Step 2 — Unit-system agnosticism (RESOLVED 2026-05-02)

**Q:** Do we hardcode imperial inches (matching the kickoff's reference YAMLs) or support multiple unit systems?

**A:** Configurable per species. New `UnitSystem` model (`plant_sim/schema/units.py`) with built-in length units (`m`, `cm`, `mm`, `in`, `ft`, `yd`), inline custom units (`{name: ..., meters_per_unit: ...}`), and a programmatic `register_length_unit(...)` extension point for systems we haven't anticipated.

**Canonical internal unit: meters.** Codegen converts at .lpy emission time. Templates and viewer always work in meters. This decouples contributor choice from rendering pipeline and lets a Phase 3 scene composer mix specimens authored in different unit systems.

**Diverged from kickoff Appendix B/C:** dropped `_in` suffix from length field names (e.g., `height_range_in` → `height_range`). The suffix would lie when length unit is configurable. Angle suffix `_deg` retained (always degrees in this project per design doc); calendar suffix `_doy` retained (calendar coordinate, not a unit).

---

## Step 2 — RenderContext plumbing (RESOLVED 2026-05-02)

**Q:** Phase 3 scene composer needs per-specimen `(seed, time_offset, position)`. Build the API for that now or retrofit?

**A:** Build now. `plant_sim/schema/render_context.py` defines `RenderContext` with `seed`, `time_offset_doy`, `position_{x,y,z}_m`. Phase 0 always uses defaults; Phase 3 scene composer fills them in. The codegen will pass these to the template via `extern(...)` parameters. Templates already declare them per `templates/archetypes/README.md`.

---

## Step 2-3 — Pre-Step-3 decisions (RESOLVED 2026-05-02)

**Growth function placement: option (b) — import from `growth_functions/`.**
Generated .lpy files emit `from growth_functions import sigmoid_grow, alpha_at, ...`. Cleaner; one source of truth; refactoring helpers does not regenerate every .lpy. Constraint: the package must be importable (`pip install -e .` puts it on PYTHONPATH).

**Growth windows: option (a) hardcoded in template, with extension hooks.**
Phase 0 templates use scalar constants like `LEAF_GROWTH_DAYS = 14`. The architecture leaves room for:
- (b) per-species YAML `growth_windows` block (Phase 1+)
- (c) derivation from phenology DOY deltas (Phase 1+)
- Stochastic per-instance draws via `growth_functions.draw_growth_days(rng, mean, stddev)` (Phase 1+)

Templates already import from `growth_functions`, so swapping `LEAF_GROWTH_DAYS` (constant) for `draw_growth_days(...)` (function call) is a local change.

**T_RENDER semantic: fractional day-of-year (1..366).**
Phenology DOYs are MEDIAN dates. Per-specimen variation comes from `EMERGENCE_OFFSET`, an extern drawn once per specimen at axiom time and persisted via L-Py module parameters. Phase 0 jitter = 0 (no variation); Phase 1 reads `phenology.emergence_jitter_days` from YAML.

Templates compute effective phenology as `<event>_doy + EMERGENCE_OFFSET` before comparing to `T_RENDER + TIME_OFFSET_DOY`. `RenderContext` carries the new `emergence_offset_days` field; `templates/archetypes/README.md` documents the extern + comparison pattern.

---

## Step 8 — Renderable-turtle-in-module convention (RESOLVED 2026-05-02)

**Finding:** every renderable turtle move (`F()`, `~l()`, `@O()`) must be wrapped in a module that carries a `mat_id` parameter. Raw `F()` emitted directly in a production has no module to attach material to, and the exporter aborts with `Renderable/shape mismatch`.

**Discovered:** Step 8 first attempt at Andropogon. The original spike's `LeafLadder` and `CulmStem` emitted raw `F()` for culm segments. Wrapped them in a new `CulmSegment(t_birth, length_m, mat_id)` module — template-only fix.

**How to apply:** every archetype template follows the pattern. Documented in `templates/archetypes/README.md` ("Every renderable turtle move belongs in a module"). The error is self-documenting — the exporter's mismatch message points at the cause immediately.

**Architectural verdict for Phase 0:** the contributor pathway is real. Andropogon came online with only a new template + the one-line dispatcher entry. Codegen, validator, exporter, viewer, and material loader were all unchanged. The "wrap F() in modules" rule is a TEMPLATE-AUTHORING discipline, not a pipeline limitation.

---

## Material id validation against library (RESOLVED)

**Q:** Schema currently treats `material_id` as an arbitrary string. Should the validator cross-check that the id exists in `materials/library.json`?

**Resolved:** Yes — implemented in `plant_sim/codegen/validator.py` (`MaterialCrossCheck` + `collect_material_ids`). Runs from `write()` and via the `plant-sim generate` CLI. Covered by `test_validator.py::test_material_cross_check_*` and `test_codegen.py::test_cli_generate_rejects_unknown_material`.

---

## Discussion 2026-05-02 — Runtime location for V2 (RESOLVED)

**Q:** Where does the algorithm run for V2 — server (current Phase 0), pre-baked CDN, or browser?

**A:** Browser. The 8-char seed space is ~1.1 trillion combinations per species; pre-baking everything is impossible (~3.85 PB per species), and pre-baking only a showcase pool sacrifices the BOI-style "share any seed" UX. Multi-specimen communities also need per-instance seed derivation evaluated wherever rendering happens. Browser-side generation is the only architecture that solves both.

**How:** Path C with transitional hybrid — codegen gains a TypeScript emission target alongside the existing `.lpy` target. Both runtimes coexist during V2.0–V2.3; production cutover at V2.3 with parity tests guarding the switch. Full plan: [V2_BROWSER_RUNTIME_PLAN.md](V2_BROWSER_RUNTIME_PLAN.md).

**Implications:**
- PRNG portability becomes load-bearing — Python's Mersenne Twister and JS's `Math.random()` produce different sequences from the same seed. PCG (PCG-XSL-RR-128/64) replaces both. ~50 LOC each side.
- Hierarchical seed derivation (BOI's `world → floor → room → entity` pattern) becomes `world → specimen → organ` via `Seed.derive(parent, salt)`. Locks the hash function explicitly so cross-runtime parity holds.
- Template versioning surfaces in viewer + sidecar so users know "this seed in this template version" produced what they're seeing.
- L-Py path becomes dev/research-only after V2.3 — useful for OpenAlea-model experiments and faster archetype prototyping, not production.
- OpenAlea-model pass-through compatibility (proposed in earlier OPEN_QUESTIONS) becomes a research-only feature, not a public V1 promise. Logged here to avoid scope-creep later.

---

## Discussion 2026-05-02 — Plantae and marketplace separation (RESOLVED)

**Q:** Should plantae itself become the ecommerce engine for plant procurement, or hand off to a separable downstream product?

**A:** Hand off. Plantae's scope ends at design and plant-list export. Procurement, supplier matching, payment processing, sales tax, shipping logistics, and regulatory compliance (cross-state live-plant shipping permits, etc.) all live in a separable downstream product (related: Regional Native Plant Marketplace concept). Plantae produces portable exports (scene artifact, plant-list BOM) that any compatible procurement system can consume.

**Why:** The non-functional requirements of running real ecommerce (PCI compliance, sales tax in 50 states, plant-shipping regulatory variance, refund/replacement guarantees on live plant material, live inventory feeds from growers) are heavy and orthogonal to plantae's algorithmic core. Keeping the boundary clean lets the simulator stay simple and lets the marketplace product evolve independently. A user can take their plant list elsewhere if they want to.

**Implications:**
- Plantae's species YAML schema gains form, grade, and provenance attributes (F43–F45) so the export carries enough information to be useful downstream.
- The export function (F47) is the contract surface; format is locked once, evolved with versioning.
- Marketplace integration (cart import, deep links, etc.) is a marketplace-product concern, not a plantae feature. If plantae-marketplace co-evolution wants tighter UX, that lives in shared schema, not shared code.

---

## Per-specimen material variation (DEFERRED to Phase 4+)

**Q:** Sun-leaves vs shade-leaves, microhabitat color shifts. Currently `material_id` is baked at codegen time per species, not per specimen.

**Deferred:** Phase 4+ ecology problem. Will require a per-instance material override mechanism plus the underlying ecology/light-competition model. Not on the near-term roadmap; logged so it's not a surprise when the community renderer makes its absence visible.

---

## Coordinate convention adoption (RESOLVED)

Locked in `templates/archetypes/README.md` and codified as A4 in REQUIREMENTS: Y-up, right-handed, origin at geometric base, internal unit meters. All archetype templates and the viewer follow this convention.

---

## Lstring caching (DEFERRED to Phase 3)

`derive()` is 1-10 ms; multi-specimen scenes will call it 100s of times. Server-side memoization keyed on `(species_yaml_hash, seed)` is required for Phase 3 community rendering. Build alongside the first multi-specimen render so the cache shape is informed by real access patterns (audit item (c) below, early reads, agrees). Implementation is small once the use case lands.

---

## Scene polygon and key-specimen placement schema (RESOLVED 2026-05-02)

Driven by F40–F42 in REQUIREMENTS. Communities need a concrete scene-spec format before Phase 3. Resolutions below; YAML schema sketch at the end.

**Q1: Polygon coordinate format.**
Three candidates:
- (a) Geographic (lat/lon, likely GeoJSON `Polygon` or `MultiPolygon`). Pros: maps directly to user intent ("outline this prairie remnant on a basemap"); composable with public datasets (parcel boundaries, NLCD tiles, restoration footprints). Cons: forces a projection step at scene-load time; non-trivial math at the polygon edges if the scene is large enough for projection distortion to matter (probably not for restoration-scale work, but flag).
- (b) Scene-local meters (the canonical internal unit per A4). Pros: zero projection math; matches everything downstream. Cons: divorced from real-world geography; user has to translate from a basemap manually.
- (c) Both, with a flag in the YAML. Pros: lets researchers pick. Cons: doubles the schema surface and the test matrix.

**Resolved:** (c) — schema accepts both via an explicit `coord_system` flag. (a) is the recommended path for the scene composer UI (F42); (b) is the unadorned researcher path. The scene loader projects (a) into local meters at load time using a flat-earth approximation centered on the polygon centroid (good enough for <10 km scenes; corresponds to seam S6).

**Q2: Auto-fill placement algorithm.**
Density spec is per-species (e.g., `Andropogon gerardii: 4 plants/m²`). Candidates:
- Poisson disk sampling (spatial blue noise). Most ecologically plausible at moderate densities; minimum-distance constraint avoids visual clumping artifacts.
- Per-species density × polygon area, placed via grid jitter. Simpler; clumping more visible.
- Cluster + matrix mix (e.g., Echinacea in clusters, grasses uniform). Realistic but adds parameters.

**Resolved:** Poisson disk per species, then composite. Cluster behavior deferred to Phase 4+.

**Q3: Key-specimen interaction with auto-fill.**
When a user pins a 12 m oak in the middle of a polygon, the auto-fill should probably not place dense grass directly under the trunk. Two implementation strata:
- (a) Geometric exclusion only — auto-fill skips a circle of radius `r` around each key specimen. Cheap and dumb; user-tunable.
- (b) Ecological exclusion — density falloff that varies by species pair (e.g., grass density drops under tree canopy, woodland species rise). This is real Phase 4+ light-competition territory and shouldn't gate F41.

**Resolved:** Ship (a) for V2.2; (b) waits for Phase 4+.

**Q4: Key-specimen seed semantics.**
- Default: derive per-specimen seed from `(scene_seed, position_x, position_y, species)` so the same scene seed always produces the same oak in the same spot.
- Override: allow `key_specimens: [{species, position, seed: "XQF2D6S1"}]` for the BOI-style "I love this exact specimen, pin it across scenes" pattern.

**Resolved:** Both supported. Default keeps reproducibility automatic; override gives the seed-curation crowd what they want.

**Q5: Coordinate system for key specimens.**
**Resolved:** Must match polygon coordinate system from Q1. Geographic polygon → key-specimen positions in lat/lon; local meters polygon → positions in meters. Mixed mode is forbidden in the schema.

**Q6: Documentation muddle to fix.**
F27 in REQUIREMENTS mentions a "scene composition UI" but the description (taxonomy panel, reference photo, morphology checklist) is actually the species-authoring UI, not the scene composer. F27 should be split into F27 (species-authoring UI) and F42 (scene composer UI, now added). Done in this revision.

### Resolved gap fills

Items the rev-2 leans didn't cover, decided 2026-05-02:

- **Polygon shape: GeoJSON `Polygon` or `MultiPolygon`, with rings.** Outer ring + optional interior holes. Use cases: disjoint restoration patches (MultiPolygon); "skip the parking-lot island" (interior ring as hole).
- **Position quantization for the seed-derive default: 1 cm.** Quantize `(x, y)` to 0.01 m (or rounded equivalent in lat/lon at polygon centroid scale) before salting `Seed.derive`. Defensible because sub-cm jitter is below the positional accuracy of any real placement workflow; without quantization, float noise would change derived seeds.
- **Default exclusion radius for key specimens: `species.crown_width` upper bound × 0.5.** Pulls the natural crown half-width from the species YAML's existing `crown_width` range. User can override per pin via `exclusion_radius_m`.
- **Density spec total cap: warn at >20 plants/m² total density per polygon, hard reject at >100.** Conservative numbers; tighten later if needed.
- **Auto-fill ordering rule.** Key specimens placed first (deterministic from scene seed + species_mix order); auto-fill samples in stable per-species order driven by the species_mix list ordering. Reproducibility property: same scene_seed + same scene YAML → identical placements.

### Scene YAML schema (target shape)

```yaml
# scenes/prairie_demo.yaml
name: "prairie_demo"
description: "0.5 ha prairie restoration test scene"

scene_seed: "PRAR-1234"                # 8-char Crockford base32 (BOI-style); derive from name if omitted

boundary:
  coord_system: "geographic"           # or "local_meters"
  geometry:                            # GeoJSON-shaped
    type: "Polygon"                    # or "MultiPolygon"
    coordinates: [
      [[lon, lat], [lon, lat], ...],   # outer ring
      [[lon, lat], ...]                # optional hole
    ]

species_mix:
  - species: "andropogon_gerardii"
    density_per_m2: 4
  - species: "echinacea_purpurea"
    density_per_m2: 2

key_specimens:
  - species: "quercus_alba"            # only after crown_tree archetype lands (F6)
    position: [lon, lat]               # must match boundary.coord_system
    exclusion_radius_m: 6.0            # optional; default species.crown_width upper bound × 0.5
    seed: "OAKXY123"                   # optional; default derived from (scene_seed, species, quantized position)

auto_fill:
  algorithm: "poisson_disk"            # only option for now
  # min_distance_m per species derived from density (~1/sqrt(density))
```

Code landed at `plant_sim/schema/scene.py` 2026-05-02 — Pydantic models for Boundary, GeoJSONPolygon/MultiPolygon, SpeciesEntry, MixEntry, KeySpecimen, AutoFillSpec, and Scene; plus a `project_to_local_meters(boundary)` helper using the flat-earth approximation around the polygon centroid. Cross-checks against the species/mix libraries (every species_mix.species and key_specimen.species exists; mix references resolve) deferred to the V2.2 scene loader.

---

## Plant output and export schema (RESOLVED 2026-05-02)

Driven by F43–F47 in REQUIREMENTS, which add plant-material attributes and the export contract that hands off to procurement systems. Plantae↔marketplace boundary already resolved (S1). Resolutions below; YAML and JSON schema sketches at the end.

**Q1: Plant material form enum.**
Initial set: `seed`, `plug`, `container_1gal`, `container_3gal`, `bare_root`, `B&B`, `bulb_corm_rhizome`, `cutting`. Open question on whether woody species need a `bareroot_grade` distinction (seedling vs liner vs landscape-size).

**Resolved:** Lock the eight forms in Phase 1. Revisit a `bareroot_grade` distinction when the `crown_tree` archetype lands (F6 in Phase 1+); woody species are the only place the distinction matters.

**Q2: Allowed-form subset per species.**
Some species don't tolerate certain forms (taproot species poorly bare-rooted, certain sedges plug-only).

**Resolved:** Species YAML gains `material.allowed_forms: [enum, ...]` (required, list, must be a non-empty subset of the canonical enum) and `material.default_form: <enum>` (required, must be in `allowed_forms`). One default per species — independent of grade. Per-row override available in scene YAML (`species_mix[i].form: "<form>"`); per-specimen override is YAGNI until a consumer asks.

**Q3: BOM quantity semantics by form.**
Counts for transplants vs PLS lb for seed vs packet/oz for ornamental seed; mixed-species seed mixes are a separate concept.

**Resolved:** One form per BOM row, the row's chosen form (species default unless scene-overridden). Quantity is `{value, unit}` with `unit` form-appropriate (closed enum below). Mixed-species seed mixes are a first-class artifact (see Seed mix design below) — not modeled by trying to pivot per-species rows. Alternative-form pivots ("could be 5000 plugs OR X lb seed") are a marketplace concern; plantae does not ship that complexity.

**Q4: Export format.**
- BOM canonical JSON, schema versioned. CSV adapter for spreadsheet users.
- Scene artifact: previously open ("JSON with embedded GeoJSON, suggested suffix `.plantae-scene.json`"); now resolved against audit item (b).

**Resolved:** **The scene YAML IS the scene artifact** — F46 collapses to "the export CLI passes the scene YAML through with version frontmatter, no new format." Resolves audit item (b) below. BOM is the only newly-defined export format; it lands as canonical JSON + CSV adapter. Every export carries `plantae_version` and `bom_schema_version` (or `scene_schema_version` on the passthrough YAML).

**Q5: Substitution semantics.**
Whether plantae should emit substitution hints alongside the grade and provenance tags.

**Resolved:** Substitution stays purely in marketplace logic (per S1). Plantae emits `grade` (F44) and `provenance` (F45) as inputs; no `substitution_hints` field on species or BOM rows.

**Q6: Phase placement.**
**Resolved:**
- F43, F44, F45 (species attributes) land in Phase 1 — additive YAML schema work alongside new archetypes.
- F46 (scene YAML passthrough w/ version frontmatter), F47 (BOM), F53 (`plant-sim export`) land in V2.2.
- F57 (seed mix definitions, NEW; see below) lands in Phase 1 with the species attributes.
- No marketplace-side work on plantae's roadmap.

### Seed mix design (NEW)

Restoration procurement is mix-first: contractors buy "25 lb of Tallgrass Prairie Mix at 30/25/20/15/5/5 percentages," not raw per-species weights. Mixes are a first-class artifact — distinct from per-species form metadata.

**New artifact: reusable mix definitions** at `mixes/<mix_name>.yaml`:

```yaml
# mixes/tallgrass_prairie_mix.yaml
name: "tallgrass_prairie_mix"
display_name: "Tallgrass Prairie Mix"
description: "Standard Midwest tallgrass restoration mix"
grade: "restoration_grade"
components:                                # weight_pct sums to 100 (schema validates)
  - species: "andropogon_gerardii"
    weight_pct: 30
  - species: "schizachyrium_scoparium"
    weight_pct: 25
  - species: "sorghastrum_nutans"
    weight_pct: 20
  - species: "elymus_canadensis"
    weight_pct: 15
  - species: "rudbeckia_hirta"
    weight_pct: 5
  - species: "echinacea_pallida"
    weight_pct: 5
```

**Scene YAML accepts mix entries alongside individual species entries:**

```yaml
species_mix:
  - mix: "tallgrass_prairie_mix"
    application_rate: {value: 8, unit: "lb_PLS_per_acre"}    # mix entries take rate, not density
  - species: "echinacea_purpurea"
    density_per_m2: 2
    form: "plug"
```

**BOM JSON gets `row_type: mix` rows with components:**

```json
{
  "plantae_version": "0.4.0",
  "bom_schema_version": 1,
  "scene_name": "prairie_demo",
  "scene_seed": "PRAR-1234",
  "rows": [
    {
      "row_type": "mix",
      "mix_id": "tallgrass_prairie_mix",
      "mix_display_name": "Tallgrass Prairie Mix",
      "total_quantity": {"value": 4.0, "unit": "lb_PLS"},
      "grade": ["restoration_grade"],
      "components": [
        {"species_canonical": "andropogon_gerardii",     "weight_pct": 30, "weight": {"value": 1.20, "unit": "lb_PLS"}},
        {"species_canonical": "schizachyrium_scoparium", "weight_pct": 25, "weight": {"value": 1.00, "unit": "lb_PLS"}},
        {"species_canonical": "sorghastrum_nutans",      "weight_pct": 20, "weight": {"value": 0.80, "unit": "lb_PLS"}},
        {"species_canonical": "elymus_canadensis",       "weight_pct": 15, "weight": {"value": 0.60, "unit": "lb_PLS"}},
        {"species_canonical": "rudbeckia_hirta",         "weight_pct": 5,  "weight": {"value": 0.20, "unit": "lb_PLS"}},
        {"species_canonical": "echinacea_pallida",       "weight_pct": 5,  "weight": {"value": 0.20, "unit": "lb_PLS"}}
      ]
    },
    {
      "row_type": "species",
      "species_canonical": "echinacea_purpurea",
      "scientific_name": "Echinacea purpurea",
      "form": "plug",
      "quantity": {"value": 200, "unit": "count"},
      "grade": ["restoration_grade", "ornamental_grade"],
      "provenance": {"ecoregion": "EPA_L3_54", "origin_range": null},
      "notes": null
    }
  ]
}
```

**CSV adapter — flat with extra columns:**

`scene_name, row_type, mix_id, mix_display_name, weight_pct, species_canonical, scientific_name, form, quantity_value, quantity_unit, grade, provenance_ecoregion, provenance_lat_min, provenance_lat_max, provenance_lon_min, provenance_lon_max, notes`

- Mix summary row: `row_type=mix`, `form=seed_mix`, `mix_id` populated, `weight_pct` null, species columns null.
- Mix component row: `row_type=mix_component`, `form=seed`, `mix_id` references parent, `weight_pct` populated, species columns populated.
- Standalone species row: `row_type=species`, `mix_id` and `weight_pct` null.

UTF-8 with header row. Per-species roll-ups across mix and standalone entries are a marketplace concern — plantae emits the structured BOM; consumer computes totals.

**Mix validation rules:**
- `components[].weight_pct` must sum to 100 (within float tolerance).
- All component species must exist in `species/` and must include `seed` in their `allowed_forms`.
- Mix grade must match every component species' grade compatibility.
- `application_rate` unit is `lb_PLS_per_acre` for now; `g_per_m²` added when an ornamental use case asks.
- A scene can mix mix entries and individual entries freely; no cross-validation between them.

### Resolved gap fills

- **Quantity unit enum:** `count` (transplants and cuttings), `lb_PLS` (restoration seed; Pure Live Seed pounds), `oz` (ornamental seed), `g` (small ornamental seed). Closed enum; add when a use case appears.
- **Default form is per-species, not per-grade.** A species with both restoration and ornamental grade still has one `default_form`. Scene YAML overrides per row when a different form is desired.
- **Versioning frontmatter on every export:** `plantae_version` always; `bom_schema_version` on the BOM file; `scene_schema_version` on the passthrough scene YAML.
- **Export bundle layout** (output of `plant-sim export <scene>`):
  ```
  <output-dir>/
  ├── <scene>.plantae-scene.yaml    # passthrough of input scene YAML + version frontmatter
  ├── <scene>.bom.json              # canonical BOM
  └── <scene>.bom.csv               # CSV adapter
  ```

### Species YAML — F43/F44/F45 additions sketch

```yaml
# species/asteraceae/echinacea_purpurea.yaml (excerpt)
material:
  allowed_forms: ["seed", "plug", "container_1gal", "bare_root"]
  default_form: "plug"

grade: ["restoration_grade", "ornamental_grade"]    # one or both

provenance:
  ecoregion: "EPA_L3_54"                            # Bailey or EPA L3/L4 code
  origin_range:                                     # optional lat/lon bounding box
    lat: [38.0, 44.0]
    lon: [-92.0, -85.0]
```

Code lands at `plant_sim/schema/species.py` (existing — additive Pydantic fields) and a new `plant_sim/schema/mix.py` for mix definitions during Phase 1; BOM emitter and `plant-sim export` land in V2.2 (likely `plant_sim/export/bom.py`).

---

## Pending — Audit against engineering principles (NEW 2026-05-02, early reads)

Five items surfaced from a pass through REQUIREMENTS and OPEN_QUESTIONS against `engineering_principles.md`. All are **early reads, not decisions** — they're proposals to be argued, refined, or rejected. Logged here so they don't fall through the cracks.

### a. Scene composer UI (F42) phasing

Currently parked at Phase 5+. P1 (deep usability at every facet) suggests earlier. Communities ship at Phase 3 and would stay hand-authored YAML-only until Phase 5+, which is years of community-rendering capability without the polygon UI that makes it usable for non-technical users (designers, contractors, restoration coordinators). Counter: hand-authored YAML works; researchers and developers can produce scenes without the UI; UI is a contributor-experience improvement, not a blocker for core capability.

**Early read:** move F42 to Phase 3 alongside community rendering, since that's when scenes become a user-facing concept rather than a developer-facing one. Phase 5+ is the right slot only if early users will all be technical, which contradicts the design-to-procurement vision.

### b. Scene artifact (F46) vs scene YAML (F36) duplication (RESOLVED 2026-05-02)

F46 originally described a portable scene artifact distinct from `scenes/<scene_name>.yaml` in F36. P2 (minimum architectural complexity) and P6 (open formats) flagged the duplication: the YAML is already portable, diffable, versionable, and built on open standards. A distinct "scene artifact" export with a separate format adds a schema layer that earns nothing the YAML doesn't already deliver. Counter considered: developer-facing fields (template overrides, generator hints, debug annotations) might warrant a separate procurement-side artifact.

**Resolved:** The scene YAML is the scene artifact at a single shared schema. F46 collapses to "scene YAML passthrough with version frontmatter" — the export CLI emits a copy of the scene YAML alongside the BOM, no new format. If developer-facing fields appear later, scope them with a `_dev` namespace inside the YAML rather than forking the format. Resolution co-decided with plant-output schema Q4 (see Resolved section above).

### c. Lstring caching priority

Currently logged as Phase 3 prerequisite, "trivial to add in Step 7. Not building yet." S11 (specimen ↔ community seam) makes lstring caching load-bearing for community work, and ~100 to ~2000 derives at 1-10ms each (NF3 target) is exactly the runtime cost P4 puts downward pressure on. Counter: premature work before the community use case lands; the cache shape might need to differ once we see real access patterns.

**Early read:** no change to actual sequencing, but elevate the status from "deferred" to "build alongside the first multi-specimen render in Phase 3" so it doesn't get forgotten as a forcing function for the community render to feel right. The trivial implementation noted (memoization keyed on `(species_yaml_hash, seed)`) is probably the right starting shape.

### d. glTF revisit for V2 / landscape scale

A2 chose OBJ + JSON sidecar because PlantGL had no glTF codec. The constraint is irrelevant in V2 (no PlantGL). Currently OBJ + JSON wins on P3 (no extra dep, parsers are commodities) and P6 (two open formats). At landscape scale (Phase 4+, NF4 1000+ plants), native glTF instancing (KHR_mesh_instancing) may win on P4 against three.js InstancedMesh-of-OBJ-geometry, since the format itself can encode instances natively rather than the renderer reconstructing them. Counter: not yet, community-scale renders haven't proven the perf problem; switching exporters mid-stream is real cost.

**Early read:** stay OBJ + JSON through V2.3. Re-evaluate at Phase 4+ when landscape rendering starts struggling. The decision tree is cleaner now (PlantGL constraint gone), so a future re-evaluation will be quick if perf data forces it.

### e. V2 bundler choice through the principle lens

OPEN_QUESTIONS leans esbuild over Vite over no-build ESM. P3 (minimum dependency and tool surface) suggests revisiting. No-build raw ESM is zero build tooling; the plantae viewer already runs no-build with native browser imports. esbuild earns its way only when bundle composition or size becomes a real constraint. Counter: V2.2+ communities and species catalog growth may want code splitting and compression that ESM-direct can't offer; the V2 done criterion of <2 MB compressed (V2 §7.6) probably needs a bundler at scale.

**Early read:** no-build raw ESM through V2.0 and V2.1, prove cross-runtime parity and the algorithm port without bundler complexity. Adopt esbuild only when bundle pain is concrete (sizes approaching 2 MB, or HTTP/2 multiplexing not absorbing the request count). P3 says deps earn their way; bundler doesn't earn its way prophylactically.
