# Plantae — Requirements

**Last updated:** 2026-05-02
**Scope:** consolidates decisions across design doc v0.3.1, Phase 0 kickoff, Echinacea + Andropogon spike findings, OPEN_QUESTIONS, V2 browser-runtime plan, and architectural conversations through 2026-05-02.
**Status legend:** ✅ shipped · 🔄 in progress · 📋 planned · ❓ open

---

## What plantae is

An algorithmic plant simulator that lets non-technical contributors (botanists, naturalists) author species in plain YAML and renders them as continuous-time 3D specimens in a browser. Each specimen has a shareable seed (BOI-style — copy/paste/read aloud the same string anywhere to reproduce the same plant exactly). Communities of plants are built by sampling many specimens from a shared scene seed.

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
- **F23** ✅ URL-driven (`?species=&seed=`); refreshable, shareable.
- **F24** ✅ Seed UI: prominent display, copy button, "new seed" button, paste-and-load input.
- **F25** ✅ Visiting `/` generates a fresh random seed by default.
- **F26** 📋 V2: viewer loads generated TS modules; calls `generate(seed, t_render)` directly.
- **F27** 📋 Phase 5+: botanist-facing scene composition UI (taxonomy panel, reference photo, morphology checklist).

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

### CLI

- **F40** ✅ `plant-sim validate <yaml>` — schema validation, fast feedback.
- **F41** ✅ `plant-sim schema-json -o <path>` — emit JSON Schema for IDE.
- **F42** ✅ `plant-sim generate <yaml> [--seed N|XYZ|random] [--output DIR]` — YAML → `.lpy`.
- **F43** ✅ `plant-sim render <lpy_file> [--t DOY] [--output DIR]` — `.lpy` → OBJ + sidecar.
- **F44** ✅ `plant-sim serve [--port N] [--host H]` — dev server + viewer.

### CI / build pipeline

- **F45** ✅ `.github/workflows/tests.yml` — pytest on every push and PR.
- **F46** ✅ `.github/workflows/render.yml` — generate + render + comment on PRs that touch species/templates/codegen/materials.
- **F47** 📋 V2.3+: replace bake-on-PR with TS module build; static deploy to CDN.

---

## Architectural Requirements (locked decisions)

- **A1** ✅ **L-Py + OpenAlea** as Phase 0 substrate. Validated by Echinacea spike (+9) and Andropogon spike (4/4 PASS).
- **A2** ✅ **OBJ + JSON sidecar export** (not glTF). PlantGL has no glTF codec — `Cannot find codec to write scene`. Bridge: `Shape.id → "o SHAPE_<id>"` group → three.js `mesh.name` → sidecar lookup → material library.
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
- **A17** 📋 **V2: Browser-side generation as production architecture.** Codegen emits TypeScript modules; browser runs algorithm directly. Server kept as dev/research tool. See V2_BROWSER_RUNTIME_PLAN.
- **A18** 📋 **V2: Hierarchical seed derivation** via `Seed.derive(parent, salt)`. BOI-style world → specimen → organ. Hash function (likely BLAKE3-truncated) explicitly locked for cross-runtime parity.
- **A19** 📋 **V2: Template versioning surfaced everywhere.** Generated artifacts and viewer display the template version that produced them; users see "this seed in template v1.2.0."

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

---

## Risks (R)

Tracked in detail in `V2_BROWSER_RUNTIME_PLAN.md` §9 and `OPEN_QUESTIONS.md`. Highlights:

- **R1** ✅ Mitigated: TS template authoring is uglier than L-Py — shared turtle/runtime helpers absorb most ugliness.
- **R2** 📋 Active: geometry parity bugs between runtimes during V2 transition. Mitigation: per-vertex hashing parity test, 1mm absolute tolerance.
- **R3** 📋 Active: TS bundle size growth as archetypes/species multiply. Mitigation: codegen produces one shared runtime + tiny per-species modules; lazy load.
- **R4** 📋 Active: browser memory for large communities. Mitigation: LOD + impostors in Phase 4+.
- **R5** ✅ Acknowledged: V2 loses production OpenAlea-model compatibility. L-Py dev path retains it for research; documented as constraint.
