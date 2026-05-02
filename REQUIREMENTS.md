# Plantae — Requirements

**Last updated:** 2026-05-02
**Scope:** consolidates decisions across design doc v0.3.1, Phase 0 kickoff, Echinacea + Andropogon spike findings, OPEN_QUESTIONS, V2 browser-runtime plan, and architectural conversations through 2026-05-02.
**Status legend:** ✅ shipped · 🔄 in progress · 📋 planned · ❓ open
**Principles:** see `engineering_principles.md`. Entries are tagged with relevant principles `(P1)` to `(P7)` where the alignment is load-bearing.

---

## What plantae is

An algorithmic plant simulator that lets non-technical contributors (botanists, naturalists) author species in plain YAML and renders them as continuous-time 3D specimens in a browser. The substrate is L-systems, the canonical biological-fractal formalism (Lindenmayer 1968): small recursive rule sets produce the self-similar structure plants actually exhibit. Each specimen has a shareable seed (BOI-style — copy/paste/read aloud the same string anywhere to reproduce the same plant exactly). Communities of plants are built by sampling many specimens from a shared scene seed. A user can select an arbitrary map shape and fill it with plants drawn from a species mix and density spec, reproducible from the scene seed.

Plantae's scope ends at design and plant-list export. Procurement, supplier matching, and ecommerce live in a separable downstream product (related: Regional Native Plant Marketplace concept). Plantae produces portable exports (scene artifact for the design, plant-list BOM for procurement) that any compatible system can consume. Plant material is supported in both seed and transplant forms (plugs, containers, bare-root, B&B, etc.); form selection drives the BOM but not the rendering.

Built on the OpenAlea ecosystem (L-Py + PlantGL) for Phase 0; planned migration to a browser-side runtime for V2 production.

---

## Functional Requirements

### Authoring (botanist surface)

- **F1** ✅ Species defined in YAML files at `species/<family>/<genus_species>.yaml`. No code required.
- **F2** ✅ Two reference species (*Echinacea purpurea*, *Andropogon gerardii*) ship as worked examples.
- **F3** ✅ Two archetypes ship: `rosette_scape_composite` (Asteraceae forbs), `tiller_clump` (Poaceae grasses).
- **F4** ✅ Schema validation provides specific, field-level error messages.
- **F5** ✅ JSON Schema export wires into VS Code's yaml-language-server for inline tooltips and autocomplete.
- **F6** 📋 Phase 1: three more archetypes (`recursive_branch_forb`, `crown_tree`, `clonal_meta`) — kickoff §11.
- **F7** 📋 Phase 2: ≥25 species across the Reference Species Set (design doc §17).

### Generation pipeline

- **F8** ✅ YAML → `.lpy` codegen via Jinja2 templates with material-id and length-unit awareness.
- **F9** ✅ Static validator catches multi-character module references not declared, multi-line `-->` rules, color slot indices outside 0..6, and material_ids missing from the library.
- **F10** ✅ Persistent-marker pattern injected for `queryable: true` modules so per-instance state survives in the lstring.
- **F11** ✅ Length values converted from species-declared unit to meters (canonical) at codegen time.
- **F12** ✅ `template_override` escape hatch in YAML for one-off morphology that doesn't fit a shared archetype.
- **F13** 📋 V2: codegen gains TypeScript emission target alongside `.lpy` (V2.1).

### Rendering

- **F14** ✅ Continuous-time interpretation: one derivation produces an lstring; slider scrubs by re-running interpretation only at varying T_RENDER.
- **F15** ✅ Age-aware geometry via `sigmoid_grow(age, growth_days, max_value)` — modules with `t_birth > T_RENDER` produce no geometry.
- **F16** ✅ OBJ + JSON sidecar export with `material_id` mapping per shape (PlantGL has no glTF codec — see A2).
- **F17** 📋 V2: browser-side generation; no server, no OBJ export.

### Materials

- **F18** ✅ Material library at `materials/library.json`, validated against Pydantic `MaterialEntry` schema.
- **F19** ✅ Phenological color curves (DOY-keyed keyframes, linear-interpolated client-side).
- **F20** ✅ Three.js material loader applies materials per shape from the sidecar.
- **F21** 📋 Phase 4+: per-specimen material variation (sun/shade leaves, microhabitat shifts).

### Viewer

- **F22** ✅ Three.js viewer with OrbitControls + slider (DOY 1..366).
- **F23** ✅ URL-driven (`?species=&seed=`); refreshable, shareable. `(P1, P6)`
- **F24** ✅ Seed UI: prominent display, copy button, "new seed" button, paste-and-load input.
- **F25** ✅ Visiting `/` generates a fresh random seed by default.
- **F26** 📋 V2: viewer loads generated TS modules; calls `generate(seed, t_render)` directly.
- **F27** 📋 Phase 5+: botanist-facing **species-authoring UI** (taxonomy panel, reference photo, morphology checklist). Distinct from the scene composer in F42; this UI helps a botanist build a single species YAML, the F42 UI helps a user assemble a community scene from existing species.

### Seeds

- **F28** ✅ 8-char Crockford base32 (40-bit space, ~1.1 trillion seeds per species).
- **F29** ✅ Backward compat: integer seeds (`seed=42`) accepted everywhere.
- **F30** ✅ Display form: `XQF2-D6S1` (mid-string hyphen). Canonical form: `XQF2D6S1` (filenames, URLs).
- **F31** ✅ Same seed → bit-identical specimen, every parameter.
- **F32** ✅ Random new-seed endpoint (`GET /seed/random`).
- **F33** ✅ Seed-normalization endpoint (`GET /seed/normalize?seed=...`) for paste validation.
- **F34** 📋 V2.0: hierarchical `Seed.derive(parent, salt)` for per-specimen seeds in communities.
- **F35** 📋 V2.0: PCG portable PRNG so the same seed produces bit-identical output in Python (server) and TypeScript (browser).

### Communities (V2.2+)

- **F36** 📋 Scene/community spec at `scenes/<scene_name>.yaml` (species, density, placement strategy).
- **F37** 📋 Per-specimen seeds derived from a shared scene seed.
- **F38** 📋 Three.js InstancedMesh for same-archetype duplicates.
- **F39** 📋 Phase 3 target: ~500–2000 plants smooth in browser (with instancing + frame caching).
- **F40** 📋 Scene boundary defined as a GeoJSON-shaped `Polygon` or `MultiPolygon` (outer ring plus optional interior holes). Coordinate system is selectable per scene via a `coord_system` flag: `geographic` (lat/lon, recommended for the F42 scene composer UI) or `local_meters` (researcher path). The scene loader projects geographic input to local meters at load time using a flat-earth approximation centered on the polygon centroid (resolved seam S6; <10 km scenes). Auto-fill samples specimens to populate the polygon interior via Poisson disk per species, governed by the species mix and density spec.
- **F41** 📋 Key-specimen manual placement: user pins specific specimens at chosen positions within the scene boundary; positions must use the same `coord_system` as F40. Canonical case: large trees as canopy anchors placed before the matrix is auto-filled (depends on the `crown_tree` archetype landing in Phase 1, F6). Any species is eligible. Auto-fill skips a configurable exclusion circle around each pin (default radius = `species.crown_width` upper bound × 0.5; user-overridable via `exclusion_radius_m`). Per-specimen seed is either derived from `(scene_seed, species, quantized-position-1cm)` by default or overridden inline (BOI-style "pin this exact specimen").
- **F42** 📋 Scene composer UI: draw or import polygon, place key specimens on a basemap, configure species mix and densities, save to `scenes/<scene_name>.yaml`. Phase 5+ in current planning; the underlying scene-spec schema is needed earlier (Phase 3) so hand-authored YAML scenes work without the UI.

### Plant output & export

- **F43** 📋 Plant material form per species. Canonical enum: `seed`, `plug`, `container_1gal`, `container_3gal`, `bare_root`, `B&B`, `bulb_corm_rhizome`, `cutting`. Species YAML declares `material.allowed_forms: [...]` (required, non-empty subset) and `material.default_form: <enum>` (required, must be in `allowed_forms`). Per-row override available via `species_mix[i].form` in the scene YAML; per-specimen override is YAGNI until a consumer asks. Default is per-species (not per-grade). A revisit on woody-species `bareroot_grade` distinction is deferred to when the `crown_tree` archetype lands.
- **F44** 📋 Use-case grade per species: `grade: [...]` containing `restoration_grade`, `ornamental_grade`, or both. Mirrors the marketplace concept's explicit split. Drives downstream sorting and substitution rules in procurement consumers; substitution itself is purely a marketplace concern (not a plantae output).
- **F45** 📋 Provenance attribute per species. Structured: `provenance.ecoregion: "<code>"` (Bailey or EPA Level III/IV) plus optional `provenance.origin_range: {lat: [min, max], lon: [min, max]}` lat/lon bounding box. Enables ecotype-aware procurement downstream.
- **F46** 📋 Scene export = scene YAML passthrough with version frontmatter. The `plant-sim export` CLI emits `<scene>.plantae-scene.yaml` (a copy of the input scene YAML, with `plantae_version` and `scene_schema_version` added at the top) into the output directory alongside the BOM. No separate "scene artifact" format. `(P6, P2)`
- **F47** 📋 Plant-list (BOM) export from a scene: canonical JSON at `<scene>.bom.json`, CSV adapter at `<scene>.bom.csv`. Two row types via discriminated union: `species` rows (one row per scene species_mix entry, with form-appropriate `quantity = {value, unit}`; closed unit enum: `count`, `lb_PLS`, `oz`, `g`) and `mix` rows (mix metadata + total quantity + `components: [{species, weight_pct, weight}]`). Per-species roll-ups across mix and standalone entries are a marketplace concern; plantae emits the structured BOM, consumer computes totals. Top-level versioning fields (`plantae_version`, `bom_schema_version`) on every BOM. `(P6)`
- **F57** 📋 Reusable seed-mix definitions at `mixes/<mix_name>.yaml`. Schema: `name`, `display_name`, `description`, `grade`, `components: [{species, weight_pct}]` where weights sum to 100. Scenes reference mixes via `species_mix[i].mix: "<name>"` with `application_rate: {value, unit}` (canonical unit `lb_PLS_per_acre` for now); BOM emits `mix` rows with the per-component breakdown. All component species must exist and must include `seed` in `allowed_forms`. Lands in Phase 1 with F43–F45.

### CLI

- **F48** ✅ `plant-sim validate <yaml>` — schema validation, fast feedback.
- **F49** ✅ `plant-sim schema-json -o <path>` — emit JSON Schema for IDE.
- **F50** ✅ `plant-sim generate <yaml> [--seed N|XYZ|random] [--output DIR]` — YAML → `.lpy`.
- **F51** ✅ `plant-sim render <lpy_file> [--t DOY] [--output DIR]` — `.lpy` → OBJ + sidecar.
- **F52** ✅ `plant-sim serve [--port N] [--host H]` — dev server + viewer.
- **F53** 📋 `plant-sim export <scene> [--scene] [--plant-list] [--format json|csv] [--output DIR]` — emit scene artifact and/or BOM for downstream procurement systems.

### CI / build pipeline

- **F54** ✅ `.github/workflows/tests.yml` — pytest on every push and PR.
- **F55** ✅ `.github/workflows/render.yml` — generate + render + comment on PRs that touch species/templates/codegen/materials.
- **F56** 📋 V2.3+: replace bake-on-PR with TS module build; static deploy to CDN.

---

## Architectural Requirements (locked decisions)

- **A1** ✅ **L-Py + OpenAlea** as Phase 0 substrate. L-systems are the canonical biological-fractal formalism: small recursive rule sets produce the self-similar structure plants exhibit at every scale (branch, leaf, shoot, organ). Validated by Echinacea spike (+9) and Andropogon spike (4/4 PASS).
- **A2** ✅ **OBJ + JSON sidecar export** (not glTF). PlantGL has no glTF codec — `Cannot find codec to write scene`. Bridge: `Shape.id → "o SHAPE_<id>"` group → three.js `mesh.name` → sidecar lookup → material library. `(P6)`
- **A3** ✅ **Y-up, right-handed, origin at geometric base** of the plant. Matches three.js + glTF defaults.
- **A4** ✅ **Meters as canonical internal length unit.** Codegen converts species-declared units to meters at .lpy emission.
- **A5** ✅ **Configurable length unit per species YAML.** Built-in units: m, cm, mm, in, ft, yd. Inline custom units: `{name, meters_per_unit}`. Programmatic registration: `register_length_unit(...)`.
- **A6** ✅ **Angles in degrees** (suffix `_deg`). Calendar coordinates in DOY (suffix `_doy`).
- **A7** ✅ **DOY-based T_RENDER** (fractional 1..366). Phenology DOYs are MEDIAN; per-specimen `EMERGENCE_OFFSET` shifts comparisons (Phase 0 = 0; Phase 1 wires `phenology.emergence_jitter_days`).
- **A8** ✅ **Persistent-marker pattern** for queryable modules: `expanded` boolean parameter; on first fire the rule re-emits self with `expanded=True` alongside children; subsequent iterations preserve unchanged.
- **A9** ✅ **Every renderable turtle move (`F()`, `~l()`, `@O()`) wrapped in a module with a `mat_id` parameter.** Raw turtle emissions abort the exporter with a clear "renderable/shape mismatch" error. Self-documenting constraint.
- **A10** ✅ **Standard externs every template declares:** `T_RENDER`, `SPECIMEN_SEED`, `TIME_OFFSET_DOY`, `EMERGENCE_OFFSET`, `POSITION_X_M`, `POSITION_Y_M`, `POSITION_Z_M`. RenderContext plumbed since Step 2 to avoid Phase 3 retrofit.
- **A11** ✅ **`template_override` escape hatch** for one-off species. Default policy: build more shared archetypes; override only when justified.
- **A12** ✅ **8-char Crockford base32 seeds** (excludes I/L/O/U for visual unambiguity; accepts I→1, L→1, O→0 on parse).
- **A13** ✅ **Single-worker `ThreadPoolExecutor` for L-Py work.** L-Py + boost::python is fundamentally thread-unsafe — concurrent `Lsystem(...)` calls abort with `boost::python::error_already_set`.
- **A14** ✅ **`extra="forbid"` on every Pydantic model.** YAML typos error loudly instead of silently passing.
- **A15** ✅ **Strict `age > 0` filter in exporter.** Matches `sigmoid_grow(0, ...) → 0` boundary; PlantGL omits zero-extent geometry.
- **A16** 📋 **V2: PCG-XSL-RR-128/64 portable PRNG** in both Python and TypeScript. Replaces Mersenne Twister; same seed produces bit-identical sequences cross-runtime.
- **A17** 📋 **V2: Browser-side generation as production architecture.** Codegen emits TypeScript modules; browser runs algorithm directly. Server kept as dev/research tool. See V2_BROWSER_RUNTIME_PLAN. `(P4)`
- **A18** 📋 **V2: Hierarchical seed derivation** via `Seed.derive(parent, salt)`. BOI-style world → specimen → organ; the same operation applied recursively at every scale, a fractal of identity. Hash function (likely BLAKE3-truncated) explicitly locked for cross-runtime parity.
- **A19** 📋 **V2: Template versioning surfaced everywhere.** Generated artifacts and viewer display the template version that produced them; users see "this seed in template v1.2.0."

---

## Seams

Seams are tensions in the system resolved by finding a useful boundary between two related-but-distinct things, or that are still being worked. Each entry carries the sides, the cut, the rationale, and references to the F/A/NF/OPEN_QUESTIONS entries that embody it. Status: ✅ resolved, 🔄 active. Resolved seams stay in this list since the cut and rationale remain useful long after the decision.

- **S1** ✅ **Plantae ↔ marketplace.** Sides: design tool / procurement product. Cut: plantae produces a portable plant-list BOM and stops; marketplace consumes the BOM and handles supplier matching, pricing, ecommerce, regulatory compliance. Rationale: ecommerce non-functional requirements (PCI, sales tax, regulatory variance, live-plant returns) are heavy and orthogonal to the algorithmic core. Refs: F46, F47; OPEN_QUESTIONS "Plantae and marketplace separation." `(P7)`

- **S2** ✅ **Botanist ↔ developer contributor.** Sides: non-coding species author / template and codegen author. Cut: YAML files at `species/<family>/<genus_species>.yaml` (botanist surface) vs Jinja2 templates at `templates/archetypes/` and Python codegen (developer surface). Rationale: lower the contributor floor for species addition without sacrificing architectural rigor for new archetypes. Refs: F1, F4, F5, F12; CONTRIBUTING_botanist.md and CONTRIBUTING_developer.md.

- **S3** ✅ **Generation ↔ rendering.** Sides: lstring production (one `derive()` per species+seed, cached in memory) / geometry interpretation (re-runs at every T_RENDER tick). Cut: the cached lstring is the hand-off; PlantGL and three.js never see the L-system. Rationale: continuous-time slider scrub demands cheap re-interpretation; expensive derivation amortizes once per (species, seed). Refs: F14, F15.

- **S4** ✅ **Species-authoring UI ↔ scene-composer UI.** Sides: build a single species YAML / assemble a community scene from existing species. Cut: distinct UIs in distinct phases; F27 owns species-authoring (taxonomy panel, reference photo, morphology checklist), F42 owns scene-composer (polygon, key specimens, density spec). Rationale: single-species and community workflows have different mental models, inputs, and basemap needs. Refs: F27, F42; OPEN_QUESTIONS scene-polygon Q6 (resolved 2026-05-02).

- **S5** 🔄 **L-Py runtime ↔ TypeScript runtime.** Sides: dev/research substrate (Phase 0 onward) / production substrate (V2.3+). Cut: codegen emits both targets through the V2.0–V2.3 transition; cross-runtime parity test in CI; production cutover at V2.3. L-Py path retained post-cutover for research and faster archetype prototyping. Rationale: 1.1T-seed BOI-style UX requires browser-side generation; OpenAlea-model compatibility benefits from server L-Py. Refs: A1, A16, A17, A18; V2_BROWSER_RUNTIME_PLAN.md. `(P4)`

- **S6** ✅ **Geographic coordinates ↔ local-meters coordinates.** Sides: lat/lon polygons for basemap UX and public-dataset composability / scene-local meters for canonical internal unit and zero projection math. Cut: schema accepts both via explicit `coord_system` flag; loader projects geographic input into local meters at scene-load using flat-earth approximation centered on polygon centroid. Rationale: <10km scenes don't suffer projection distortion meaningfully; UX wants geographic; runtime wants meters. Refs: A4, F40; OPEN_QUESTIONS scene-polygon Q1 (resolved 2026-05-02).

- **S7** ✅ **Restoration-grade ↔ ornamental-grade.** Sides: function-first restoration use (PLS lb/acre, ecotype-strict, contractor purchasers) / aesthetic-first ornamental use (specimen quality, looser provenance, retail purchasers). Cut: per-species `grade: [...]` list with `restoration_grade` and/or `ornamental_grade`; drives downstream sorting in procurement consumers. Substitution itself stays in marketplace logic (S1). Rationale: marketplace concept treats this as a defensible positioning leg; both customer segments need first-class support. Refs: F44; marketplace concept "Use-case clarity"; OPEN_QUESTIONS plant-output Q5 (resolved 2026-05-02).

- **S8** ✅ **Regional ecotype ↔ broader supply.** Sides: locally-adapted source material (genetic provenance from the planting region) / broadly-sourced material (often nationally distributed, lower regional fitness). Cut: `provenance.ecoregion` (code) plus optional `provenance.origin_range` (lat/lon bounding box) on species; BOM consumers can filter or weight by provenance match. Rationale: native-plant ecology depends on local adaptation; ecotype provenance is a real differentiator and the marketplace's defensible position. Refs: F45; marketplace concept "Provenance" and "Geography and ecotype focus."

- **S9** 🔄 **Static-first ↔ dynamic-required.** Sides: shippable as static files with no server, no auth, no live data (plantae V2.3+ target) / requires live data, transactions, auth (marketplace by nature). Cut: plantae ships static; marketplace operates dynamic; schema layer is shared, runtime layers are not. Rationale: plantae's user is browsing reproducible art; marketplace's user is transacting on live inventory. Refs: NF14; marketplace concept "Plantae integration." `(P3, P4)`

- **S10** 🔄 **Phase 0/1 algorithm correctness ↔ V2 production architecture.** Sides: prove the algorithmic substrate (L-Py, persistent-marker, archetype expansion, contributor pathway) / ship a production runtime (TS browser-side, PCG portable PRNG, parity tests, CDN deploy). Cut: in transition (V2.0 to V2.3); both runtimes coexist; cutover at V2.3. Needs explicit naming of what stays in each side and what crosses (data formats, schema, parity tests, doc audience, CI gates) when V2 work begins. Refs: V2_BROWSER_RUNTIME_PLAN.md; A16-A19; "Done criteria — V2."

- **S11** ✅ **Specimen ↔ community.** Sides: single-plant rendering (deep, accurate, sub-100ms scrub) / community rendering (many specimens, instancing, per-specimen seed derivation). Cut: scene seed at the community level; per-specimen seeds derived via `Seed.derive(parent, salt)`; three.js InstancedMesh for same-archetype duplicates. The seam recurs at community ↔ landscape (Phase 4+, NF4) using the same operator. Rationale: single-specimen quality demands per-instance fidelity; community scale demands sharing; same algorithm applies at every scale. Refs: F31, F36-F42; A18.

---

## Non-Functional Requirements

### Performance

- **NF1** ✅ Slider scrub feels snappy: ≤100ms per tick perceived latency.
  - Measured: ~1.1ms interpret + ~5ms file I/O + ~10ms three.js load = ~30ms worst case for single specimen.
- **NF2** ✅ Single-specimen full season derive: ≤10ms.
  - Measured: 3ms for Echinacea (127-module lstring), 8.7ms for Andropogon (760+ modules).
- **NF3** 📋 V2: 100-plant community scene at >30 fps in browser.
- **NF4** 📋 V3: 1000+ plant landscape scene with LOD/impostors at interactive frame rates.

### Reproducibility

- **NF5** ✅ Same species + same seed = bit-identical specimen across runs.
- **NF6** ✅ Schema tests act as regression guards on canonical reference YAMLs (e.g., `leaf_count_range == (6, 14)` test catches accidental edits to the canonical Echinacea YAML).
- **NF7** 📋 V2: Same seed produces bit-identical specimen in Python (dev) AND TypeScript (production) runtimes. Cross-runtime parity test in CI.

### Contributor experience

- **NF8** ✅ Botanist can self-serve a new species with no code knowledge — edit YAML, open PR, see preview.
- **NF9** ✅ Pre-Step-3 cleanup: `Field(description="...")` on every schema field for IDE tooltips.
- **NF10** ✅ Schema-only `plant-sim validate` is fast (~50ms) — botanists get instant feedback while editing locally.
- **NF11** ✅ CI catches errors before merge (validation, render, material cross-check).

### Operational

- **NF12** ✅ Fresh-checkout flow works: `mamba env create -f environment.yml && mamba activate plant_sim && pip install -e . && pytest` all pass.
- **NF13** ✅ macOS arm64 supported via Rosetta-emulated osx-64 conda env.
- **NF14** 📋 V2.3: Production deploys as static files only — no server uptime SLA needed for casual users.

---

## Constraints (the hard physical/library limits)

- **C1** ✅ macOS arm64 needs Rosetta-emulated osx-64 conda env (openalea has no native arm64 build).
- **C2** ✅ L-Py + boost::python is not thread-safe (see A13). Concurrent `Lsystem(...)` aborts the process. All L-Py work must serialize to one thread.
- **C3** ✅ PlantGL color slot indices are limited to 0..6 (silently clamped above). Templates emit `material_id` as a parameter and let the renderer apply via library lookup.
- **C4** ✅ PlantGL has no glTF codec (only `gts`, `json`, `obj`). Forces OBJ + JSON sidecar.
- **C5** ✅ Multi-character L-Py module names need explicit `module Name(params)` declarations. Single-char names auto-register.
- **C6** ✅ L-Py interpretation rules with `-->` cannot span multiple lines. Use `:` + `produce` for multi-line bodies.
- **C7** ✅ Python `random` (Mersenne Twister) is not the same as JS `Math.random()`. Cross-runtime seed parity requires a portable PRNG (see A16).

---

## Out of Scope (explicit deferrals — do not let scope creep)

These appear in the design doc and kickoff as deferred. Tracking here so they're not forgotten or accidentally re-promised.

- Light competition / canopy interaction (Phase 4+).
- Multi-year phenology — Phase 0 to 3 model one growing season (Phase 4).
- Below-ground architecture (Phase 4+).
- Per-specimen material variation — sun/shade leaves, microhabitat color shifts (Phase 4+).
- Botanist-facing viewer enhancements (taxonomy panel, reference photo, morphology checklist) — Phase 2-3 product work.
- Performance benchmarking infrastructure — eyeballing acceptable through Phase 0 (Phase 3).
- Direct OpenAlea-published `.lpy` model compatibility in production — research-only via the L-Py dev path after V2.3 (see V2 plan §10).
- GPU compute shader morphology generation — Phase 5+ if ever.
- Mobile-specific renderer — V2 TS runtime targets the same browser build; perf-tune as needed.

---

## Reference Species Set (design doc §17)

Phase 0 ships 2; Phase 2 targets 25; ultimate goal is the **Charismatic 100** of the Chicago region prairie/savanna/woodland flora. Categories from the design doc:

- Trees (22)
- Shrubs (13)
- Vines (6)
- Grasses, sedges, rushes (13)
- Branched forbs (15)
- (more categories TBD per design doc full text)

---

## Done criteria — Phase 0 (✅ COMPLETE)

From the kickoff doc, all met:

1. ✅ Round-trip regeneration (YAML edit → identical scene)
2. ✅ Both reference species online (Echinacea + Andropogon)
3. ✅ Slider works in browser, sub-100ms feel; phenological color shifts visible
4. ✅ Materials apply via sidecar lookup
5. ✅ Schema validation catches errors (4 classes of validator + material cross-check)
6. ✅ CI render hook fires + comments on PRs
7. ✅ Two contributor docs exist (botanist + developer)

Plus added during Phase 0: shareable BOI-style seeds (F28–F33), random-by-default seed UX (F25).

---

## Done criteria — V2 (📋 PLANNED)

From V2_BROWSER_RUNTIME_PLAN §7:

1. Visiting site produces fresh random seed in URL; renders default species.
2. Pasting any 8-char base32 seed loads the same plant on every machine.
3. `?scene=<name>&seed=ABCDEFGH` renders 100+ unique specimens from one scene seed.
4. Slider scrubs at >30 fps for 100-plant community.
5. No HTTP requests during slider scrub other than initial asset load.
6. Browser bundle <2 MB compressed.
7. Same template + same seed = visually-identical plants between server (dev) and browser (production). Cross-runtime parity test in CI.
8. CI publishes new TS modules to CDN within 5 min of merge.

---

## Open questions (❓)

Tracked in detail in `OPEN_QUESTIONS.md`. Summary:

- ❓ **TS bundler choice for V2** — esbuild vs Vite vs no-build ESM (currently lean esbuild).
- ❓ **Web Worker isolation** — should `generate()` run in a Web Worker for community renders >50? Probably yes.
- ❓ **Template version pinning per scene** — should saved scenes pin the template version that created them?
- ❓ **Mobile performance** — needs measurement before V2.3 ships.
- ❓ **Per-specimen material variation** — Phase 4+ ecology problem; logged so it's not a surprise.
- ❓ **Scene composer UX for botanists** — Phase 5+ product question.
- ❓ **Scene polygon coordinate format** — geographic (lat/lon, GeoJSON) vs scene-local meters vs both. Drives basemap UX, projection math, and YAML schema. See OPEN_QUESTIONS.
- ❓ **Auto-fill placement algorithm** — Poisson disk vs grid jitter vs per-species density rules; how key-specimen positions interact (exclusion zones, density falloff under canopy).
- ❓ **Key-specimen seed semantics** — derive from `(scene_seed, position)` by default; allow inline override for "pin this exact specimen." Confirm both paths in schema.
- ❓ **Plant material form enum and allowed-form subsets per species** — canonical enum locked above; per-species allowed sets need encoding in schema.
- ❓ **BOM quantity semantics by form** — count for transplants is easy; seed is PLS lb/acre or weight or both; sometimes both forms are reported as alternatives for the same line item.
- ❓ **Export format** — JSON canonical, CSV adapter for the BOM. Scene artifact format TBD (probably JSON-with-embedded-GeoJSON; possibly `.plantae-scene` suffix).

---

## Risks (R)

Tracked in detail in `V2_BROWSER_RUNTIME_PLAN.md` §9 and `OPEN_QUESTIONS.md`. Highlights:

- **R1** ✅ Mitigated: TS template authoring is uglier than L-Py — shared turtle/runtime helpers absorb most ugliness.
- **R2** 📋 Active: geometry parity bugs between runtimes during V2 transition. Mitigation: per-vertex hashing parity test, 1mm absolute tolerance.
- **R3** 📋 Active: TS bundle size growth as archetypes/species multiply. Mitigation: codegen produces one shared runtime + tiny per-species modules; lazy load.
- **R4** 📋 Active: browser memory for large communities. Mitigation: LOD + impostors in Phase 4+.
- **R5** ✅ Acknowledged: V2 loses production OpenAlea-model compatibility. L-Py dev path retains it for research; documented as constraint.
