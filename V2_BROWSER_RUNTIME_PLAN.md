# V2: Browser-Side Generation Runtime

**Status:** plan. No implementation work has started. Phase 1 (more archetypes
on the current L-Py runtime) and this V2 work are independent and can proceed
in parallel.

**Source:** discussion 2026-05-02. Decision was to commit to browser-side
generation as the long-term runtime, after concluding that:

1. **The 8-char seed space is ~1.1 trillion combinations.** Pre-baking every
   `(species, seed)` is impossible (~3.85 PB per species). Pre-baking only a
   showcase pool sacrifices the BOI-style "share any seed" UX.
2. **Multiples of the same species in a community must look distinct** for
   plant communities to feel real. That requires per-specimen seed derivation,
   evaluated wherever the rendering happens.
3. **The only architecture that gives both arbitrary seeds AND scales without
   a server** is "the algorithm runs on the user's device" — same model as
   *Binding of Isaac: Rebirth* and similar procedural games.

**Cross-references:**
- REQUIREMENTS.md captures the V2 functional requirements (F13, F17, F26, F35, F50, F53), architectural decisions (A16-A19), and the V2-relevant seams (S5 L-Py↔TS runtime, S9 static-first↔dynamic, S10 Phase 0/1 algorithm correctness↔V2 production architecture).
- engineering_principles.md frames the V2 transition as primarily a P4 (minimum runtime cost on user's machine) move with P5 (determinism) load-bearing for cross-runtime parity.

---

## 1. TL;DR

- The codegen gains a **second emission target**: TypeScript modules instead
  of `.lpy` files. Same Jinja templates, different output language.
- The browser loads a generated TS module per species, calls
  `generate(seed, t_render) -> three.js geometry`, and renders directly. No
  L-Py, no PlantGL, no OBJ, no sidecar JSON, no server round trip.
- A portable PRNG (PCG) replaces Python's Mersenne Twister so the same seed
  produces bit-identical output in both runtimes during the transition.
- A hierarchical `Seed.derive(parent, salt)` enables per-specimen seeds from
  a community/scene-level world seed — same pattern as BOI.
- Template versioning surfaces so users know "this seed in this version"
  produced what they're looking at.
- The L-Py path stays as the **dev/spike runtime**, used for prototyping new
  archetypes against the OpenAlea ecosystem, and for CI bake-on-demand.

---

## 2. Why this is the right architecture

The trillion-seed math means **arbitrary-seed UX and pre-baking are
mutually exclusive without a runtime executing somewhere on demand.** Three
runtime locations exist:

| Where the runtime lives | Pros | Cons |
|---|---|---|
| Server (current Phase 0) | Anything works | Hosting cost, scaling cost, single-thread L-Py pin |
| Server in WASM (Pyodide L-Py) | Full OpenAlea compat | Pyodide port doesn't exist; months of C++/Emscripten to fork |
| Browser (this plan) | Truly serverless, scales with users, instant per-seed | Loses arbitrary OpenAlea-model compat; runtime rewrite |

We picked browser. The cost is a one-time runtime rewrite; the benefit is
permanent freedom from server scaling, threading workarounds, and seed-pool
pre-baking.

---

## 3. Architecture overview

```
species/<family>/<species>.yaml                   (UNCHANGED — botanist surface)
        +
templates/archetypes/<archetype>.lpy.j2           (BECOMES OPTIONAL —
                                                   kept for L-Py dev path)
templates/archetypes/<archetype>.ts.j2            (NEW — TS emission target)
        ↓ codegen (Jinja2)
generated/ts/<species>_<seed>.ts                  (NEW — generated TS module)
        ↓ Browser ES module import
        Browser-side generate(seed, t) function
        ↓
three.js Object3D                                  (direct geometry; no OBJ round trip)
        ↓
materials/library.json                             (UNCHANGED)
        ↓
applyMaterialsToObject(obj, sidecar?, library, t)  (UPDATED to derive sidecar
                                                    from emitted geometry)
```

**What survives unchanged:**
- Species YAML schema (`plant_sim/schema/species.py`)
- Materials library (`materials/library.json`) and its Pydantic schema
- Three.js viewer (`viewer/index.html`, `viewer/main.js`) — minor changes only
- Material loader (`viewer/material_loader.js`)
- The 102 schema/units/materials tests
- CLI commands `plant-sim validate`, `plant-sim schema-json`
- Botanist contributor flow (edit YAML, open PR, see preview)

**What changes:**
- Codegen gains a new emission target. Existing `generator.py` grows a
  `--target ts` mode alongside the default `--target lpy`.
- New TS templates per archetype, mirroring the L-Py templates structurally.
- New runtime helpers as TypeScript modules: PRNG, Seed.derive,
  growth functions (sigmoid_grow, alpha_at), turtle interpreter for the
  small subset we need.
- Viewer's `loadFrame()` swaps from "fetch OBJ" to "import generated module
  + call generate()."

**What disappears (for production):**
- Server (`plant_sim/server/app.py`) — keeps existing behavior as dev tool
- L-Py runtime in production path
- OBJ + materials.json sidecar files in production
- The L-Py thread-safety pin (no L-Py = no boost::python in prod)

---

## 4. Load-bearing technical choices

### 4.1 PRNG: PCG-XSL-RR-128/64 in both Python and TypeScript

Python's `random` module uses Mersenne Twister; JavaScript's `Math.random()`
is implementation-defined per browser. **The same seed produces completely
different sequences in each.** Without a portable PRNG, "share a seed" UX
breaks across runtimes.

PCG (https://www.pcg-random.org) is the modern choice: small (~50 LOC each
side), faster than MT, statistically excellent, and trivially portable
because the algorithm is a few well-defined integer operations.

**Implementation tasks:**
- `plant_sim/runtime/pcg.py` — PCG implementation matching the canonical spec
- `plant_sim/runtime/pcg.ts` — JS/TS port producing bit-identical output
- A test suite (Python + Node) that verifies cross-runtime parity for 1000
  arbitrary seeds × 1000 draws each
- The generated `.lpy` files transitionally use `from plant_sim.runtime.pcg
  import seeded_rng` instead of `random.seed`. The generated TS files use
  the same PCG.

### 4.2 Hierarchical seed derivation

Per BOI's pattern: one world seed → derived seeds for floors → rooms → entities.
We need:

```python
class Seed:
    def derive(self, salt: str | int) -> "Seed":
        """Deterministic child seed from (self, salt).

        Same parent + same salt always returns the same child.
        Different salts produce uncorrelated children.

        Implementation: blake3(parent.canonical() || salt) truncated to 40 bits.
        """
```

**Use sites:**
- Scene/community: `scene_seed.derive("specimen", i)` per plant placement
- Per-organ: `specimen_seed.derive("rosette_leaf", j)` if individual organs
  need their own random stream
- Per-template: `specimen_seed.derive(f"archetype:{name}@{version}")` so
  template version changes deterministically shift the seed (see §4.3)

**Implementation tasks:**
- `Seed.derive(salt)` in `plant_sim/schema/seed.py`
- TS port in `viewer/seed.ts`
- Cross-runtime parity test
- A small documentation note in the seed module explaining the hash function
  choice and warning that changing it is a breaking change

### 4.3 Template versioning

Once the algorithm runs in the browser, **changing an archetype template
changes what every seed produces.** A user who saved seed `XQF2-D6S1`
yesterday should not be surprised when the same seed produces a different
plant tomorrow.

Each `templates/archetypes/<archetype>.{lpy,ts}.j2` carries:

```jinja
{# template_version: 1.2.0 #}
```

Generated artifacts (.lpy, .ts, sidecar) include this version. Viewer
displays it next to the seed: `seed: XQF2-D6S1 (rosette_scape_composite v1.2.0)`.

When loading a seed, viewer checks: was this seed previously rendered against
a different version? If so, surface a "this plant looks different now because
the template was updated; compare versions" UI.

**Bumping rules:**
- **Patch (1.2.x):** comment changes, refactors that don't affect output
- **Minor (1.x.0):** new optional features, additive changes
- **Major (x.0.0):** changes that produce visibly different plants for existing seeds

CI can detect patch-vs-minor-vs-major automatically by rendering a fixed set
of (template, seed) regression cases and comparing geometry hashes.

---

## 5. Migration phases

### V2.0 — PRNG + Seed.derive (foundation, ~1 week)

- [ ] Pick PCG variant (likely PCG-XSL-RR-128/64 for 64-bit output truncated
      to our 40-bit seed space)
- [ ] Implement Python PCG in `plant_sim/runtime/pcg.py`
- [ ] Implement TS PCG in `viewer/pcg.ts`
- [ ] Implement `Seed.derive(salt)` Python + TS, with parity test
- [ ] Update generated `.lpy` files to use PCG via the `pcg` module rather
      than `random.seed`. **L-Py path keeps working, just on a different RNG.**
- [ ] Migration: existing pre-baked seeds need to be re-baked under PCG.
      Document as one-time artifact churn.

**Checkpoint:** server still works, but with reproducible outputs across
languages. Adding a TS runtime later doesn't risk seed-output drift.

### V2.1 — Codegen TS target (one archetype, ~3 weeks)

- [ ] Pick archetype to convert first (recommend rosette_scape_composite —
      simpler, smaller surface)
- [ ] Design TS runtime API:
  ```ts
  generate(seed: string, t_render: number, render_ctx?: RenderContext): GenerateResult
  type GenerateResult = { geometry: THREE.Object3D, materials: { [shapeName: string]: string } }
  ```
- [ ] Implement TS-side helpers: PCG, Seed, growth_functions (sigmoid_grow,
      alpha_at, draw_growth_days), Turtle (the subset we need: F, ~l, @O, [, ],
      /, +, &, ;)
- [ ] Add `--target=ts` to `plant_sim generate` CLI
- [ ] Author `templates/archetypes/rosette_scape_composite.ts.j2`
- [ ] Add a test that renders Echinacea via both targets at the same (seed, t)
      and asserts geometry parity (vertex positions within tolerance)
- [ ] Viewer gains a `?runtime=ts|server` URL flag; defaults to server during
      this phase

**Checkpoint:** rosette_scape_composite renders identically in browser and
server for a fixed test set.

### V2.2 — Codegen TS target (second archetype + scene composer, ~4 weeks)

- [ ] Author `templates/archetypes/tiller_clump.ts.j2`
- [ ] Both reference species render in browser
- [ ] Implement scene/community spec (REQUIREMENTS F36, F40-F42):
  ```yaml
  # scenes/midwest_mesic_prairie.yaml
  scene_id: midwest_mesic_prairie
  # F40: arbitrary 2D polygon, geographic or local-meters (see OPEN_QUESTIONS scene-polygon Q1)
  bounds:
    type: local_meters_polygon
    points: [[0,0], [50,0], [50,50], [0,50]]
  # F41: optional manual placement of key specimens before auto-fill
  key_specimens: []
  populations:
    - species: andropogon_gerardii
      density_per_m2: 0.5
      placement: poisson_disk
    - species: echinacea_purpurea
      density_per_m2: 0.05
      placement: poisson_disk
  ```
- [ ] Scene composer takes a scene_yaml + scene_seed → list of
      `(species, position, derived_seed)` placements (F37)
- [ ] Browser renders each placement using the existing TS species modules
- [ ] Test community of 100 specimens — measure FPS, browser memory
- [ ] Implement scene + BOM export (REQUIREMENTS F46, F47, F53; CLI subcommand `plant-sim export`)
- [ ] Lstring caching keyed on `(species_yaml_hash, seed)` (OPEN_QUESTIONS audit item c)

**Checkpoint:** a 100-plant prairie scene renders in browser at >30 fps from
a single shared scene seed; `plant-sim export <scene> --plant-list` emits a
species × form × quantity BOM consumable by downstream procurement systems.

### V2.3 — Production cutover (~2 weeks)

- [ ] Viewer's default runtime flips from `server` to `ts`
- [ ] `plant-sim serve` is documented as dev-only
- [ ] Static deployment of the viewer + generated TS modules to a CDN
- [ ] CI pipeline `bake.yml` is replaced with `build_ts.yml`: regenerates
      TS modules on YAML changes, pushes to the CDN
- [ ] V2.3 ships as the public V1 of plantae

**Checkpoint:** plantae.org (or whatever) is live, fully serverless, supports
arbitrary seeds, supports community scenes, all from static files + browser
compute.

### V2.4 — L-Py becomes purely a dev tool (cleanup, ~1 week)

- [ ] Existing `.lpy.j2` templates kept; useful for spike work and OpenAlea-
      model experiments
- [ ] `plant-sim render` (single-specimen OBJ export) kept for spike workflows
- [ ] Server's render endpoints documented as dev-only
- [ ] CI can still generate OBJ artifacts on PRs as a debug aid

**Checkpoint:** L-Py is no longer in any production code path. Production
depends only on Node-or-equivalent for the build step plus a static file
host.

---

## 6. Coexistence with the current L-Py path

During V2.0–V2.3 (~10 weeks), both runtimes exist. The codegen emits both
formats, the viewer can use either. This is deliberate — it lets:

- **Visual regression testing** between server and browser outputs catches
  TS template bugs early
- **Phase 1 archetype work** (more species) continues uninterrupted on the
  L-Py path; new archetypes get TS templates added once they're proven
- **Botanist contributors** keep getting CI render previews on PRs from the
  L-Py path; the bot comment is the same regardless of how production renders

After V2.3, the L-Py path stays available for:

- Prototyping new archetypes faster (Python iteration is faster than TS port)
- Testing OpenAlea-published `.lpy` models in a familiar runtime
- CI render-on-PR previews if the TS render path is ever flaky

L-Py becomes a research/dev tool, not a production dependency.

---

## 7. Done criteria for V2

V2 is complete when, on a fresh checkout / web visit:

1. Visiting `https://plantae.example/` produces a fresh random seed in the
   URL and renders the default species
2. Pasting any 8-char base32 seed loads the exact same plant on every
   user's machine
3. Loading `https://plantae.example/?scene=midwest_mesic_prairie&seed=ABCDEFGH`
   renders 100+ unique specimens, all derived from the single scene seed
4. Slider scrubs across the season at >30 fps for 100-plant community
5. No HTTP requests during slider scrubbing other than initial asset load
6. Browser bundle is <2 MB compressed
7. Same template + same seed produces visually-identical plants between
   server (dev) and browser (production)
8. CI publishes new TS modules to CDN within 5 min of YAML/template merge
9. `plant-sim export <scene>` emits a portable scene artifact and a
   plant-list BOM (`species × form × quantity`) consumable by downstream
   procurement systems (REQUIREMENTS F46, F47, F53)

---

## 8. Open questions

1. **TS bundler choice.** ESM modules with no build step (current viewer
   pattern) vs Vite/esbuild for tree-shaking and minification. OPEN_QUESTIONS
   audit item (e) revisits this through the principle lens (P3, minimum tool
   surface): the current lean toward esbuild may not survive that scrutiny.
   Likely path: no-build ESM through V2.0 and V2.1, adopt esbuild only when
   bundle pain is concrete.
2. **Web Worker isolation.** Should `generate()` run in a Web Worker so
   the main thread stays responsive during slider scrubs? Probably yes for
   community renders >50 specimens, no for single-specimen.
3. **Geometry instancing.** Three.js InstancedMesh for same-archetype
   specimens. Implementation detail of the scene composer; not blocking V2.0.
4. **Template version pinning per scene.** Should a saved scene URL include
   the template version it was created against, so future template updates
   don't silently change the rendered plants? Probably yes; spec it in V2.2.
5. **OpenAlea-model compatibility loss.** This plan loses the ability to
   directly run published OpenAlea `.lpy` files in production. Phase 0 stub
   said "1-2 weeks of work to add pass-through mode for OpenAlea models" —
   that's now permanently a *server-only* feature. Worth documenting that
   constraint explicitly so we don't promise OpenAlea-import-as-V1-feature
   later.
6. **Mobile performance.** A 100-specimen community on a 2-year-old phone:
   acceptable? Needs measurement before V2.3 ships.

---

## 9. Risks

**R1: TS template authoring is uglier than L-Py.** L-system productions
in `.lpy` files read like a formal grammar; TypeScript equivalents are
imperative procedural code. Template developers will dislike this. Mitigation:
hide as much as possible behind shared turtle/runtime helpers; the per-
archetype template should still be ~100-200 lines of mostly tree-walking.

**R2: Geometry parity bugs between runtimes.** Subtle differences in
math libraries, floating-point rounding, or rendering order can produce
visually-identical-but-numerically-different geometries. Mitigation: a
parity test suite that hashes per-vertex outputs; tolerance set to absolute
0.001m (1mm).

**R3: TS bundle size.** Each archetype + species combo could bloat the
shipped bundle. Mitigation: codegen produces one shared runtime + one tiny
per-species module; only species the user views are loaded.

**R4: Browser memory for large communities.** 1000-plant scene at 50 KB
geometry each = 50 MB. Within budget but tight. LOD / instancing matters
here — not blocking V2.0 but definitely needed before V3 landscapes.

**R5: Lose the OpenAlea ecosystem connection in production.** If V1 had
promised "we can run any OpenAlea-published L-Py model," this plan breaks
that promise. Phase 0 OPEN_QUESTIONS proposed pass-through mode but never
shipped it; we should be explicit it's now research-only, not a public
feature.

---

## 10. Out of scope for V2

Things V2 does NOT do:

- Full OpenAlea model compatibility in production (research-only via L-Py
  dev path)
- Light competition / canopy interaction (Phase 4+)
- GPU compute shader morphology generation (Phase 5+ if ever)
- Multi-year phenology (Phase 4)
- Botanist-facing scene composition UI (Phase 5+)
- Mobile-specific renderer (use the same TS runtime; performance work as
  needed)

If something is out of scope and you find yourself reaching for it, write
it down here and move on.

---

*End of V2 Browser Runtime Plan v0.1.*
