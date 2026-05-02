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

## Pending — Material id validation against library

**Q:** Schema currently treats `material_id` as an arbitrary string. Should the validator cross-check that the id exists in `materials/library.json`?

**Likely answer:** Yes. Phase 0 stub library now exists at `materials/library.json` with the ids needed for Echinacea + Andropogon. Cross-check belongs in Step 4 codegen validator.

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

## Pending — Per-specimen material variation

**Q:** Sun-leaves vs shade-leaves, microhabitat color shifts. Currently `material_id` is baked at codegen time per species, not per specimen. Phase 4+ ecology problem; logged so it's not a surprise.

---

## Pending — Coordinate convention adoption

Locked in `templates/archetypes/README.md` as: Y-up, right-handed, origin at geometric base, internal unit meters. All archetype templates and the viewer must follow.

---

## Pending — Lstring caching

`derive()` is 1-10 ms; multi-specimen scenes will call it 100s of times. Server-side memoization keyed on `(species_yaml_hash, seed)` is required for Phase 3 and trivial to add in Step 7. Not building yet.

---

## Pending — Scene polygon and key-specimen placement schema (NEW 2026-05-02)

Driven by F40–F42 in REQUIREMENTS. Communities need a concrete scene-spec format before Phase 3. Several sub-questions:

**Q1: Polygon coordinate format.**
Three candidates:
- (a) Geographic (lat/lon, likely GeoJSON `Polygon` or `MultiPolygon`). Pros: maps directly to user intent ("outline this prairie remnant on a basemap"); composable with public datasets (parcel boundaries, NLCD tiles, restoration footprints). Cons: forces a projection step at scene-load time; non-trivial math at the polygon edges if the scene is large enough for projection distortion to matter (probably not for restoration-scale work, but flag).
- (b) Scene-local meters (the canonical internal unit per A4). Pros: zero projection math; matches everything downstream. Cons: divorced from real-world geography; user has to translate from a basemap manually.
- (c) Both, with a flag in the YAML. Pros: lets researchers pick. Cons: doubles the schema surface and the test matrix.

**Lean:** (c) but with (a) as the recommended path for the scene composer UI (F42), and (b) as the unadorned researcher path. The scene loader projects (a) into local meters at load time using a flat-earth approximation centered on the polygon centroid (good enough for <10 km scenes).

**Q2: Auto-fill placement algorithm.**
Density spec is per-species (e.g., `Andropogon gerardii: 4 plants/m²`). Candidates:
- Poisson disk sampling (spatial blue noise). Most ecologically plausible at moderate densities; minimum-distance constraint avoids visual clumping artifacts.
- Per-species density × polygon area, placed via grid jitter. Simpler; clumping more visible.
- Cluster + matrix mix (e.g., Echinacea in clusters, grasses uniform). Realistic but adds parameters.

**Lean:** Poisson disk per species, then composite. Defer cluster behavior to Phase 4+.

**Q3: Key-specimen interaction with auto-fill.**
When a user pins a 12 m oak in the middle of a polygon, the auto-fill should probably not place dense grass directly under the trunk. Two implementation strata:
- (a) Geometric exclusion only — auto-fill skips a circle of radius `r` around each key specimen. Cheap and dumb; user-tunable.
- (b) Ecological exclusion — density falloff that varies by species pair (e.g., grass density drops under tree canopy, woodland species rise). This is real Phase 4+ light-competition territory and shouldn't gate F41.

**Lean:** ship (a) for V2.2; (b) waits for Phase 4+.

**Q4: Key-specimen seed semantics.**
- Default: derive per-specimen seed from `(scene_seed, position_x, position_y, species)` so the same scene seed always produces the same oak in the same spot.
- Override: allow `key_specimens: [{species, position, seed: "XQF2D6S1"}]` for the BOI-style "I love this exact specimen, pin it across scenes" pattern.

Both should be supported. The default keeps reproducibility automatic; the override gives the seed-curation crowd what they want.

**Q5: Coordinate system for key specimens.**
Must match polygon coordinate system from Q1. If the scene YAML uses geographic polygon, key-specimen positions are lat/lon; if local meters, key specimens are local meters. Mixed mode is forbidden in the schema.

**Q6: Documentation muddle to fix.**
F27 in REQUIREMENTS mentions a "scene composition UI" but the description (taxonomy panel, reference photo, morphology checklist) is actually the species-authoring UI, not the scene composer. F27 should be split into F27 (species-authoring UI) and F42 (scene composer UI, now added). Done in this revision.

---

## Pending — Plant output and export schema (NEW 2026-05-02)

Driven by F43–F47 in REQUIREMENTS, which add plant-material attributes and the export contract that hands off to procurement systems. Plantae-marketplace boundary now resolved (see RESOLVED section above). Outstanding sub-questions:

**Q1: Plant material form enum, locked.**
Initial set: `seed`, `plug`, `container_1gal`, `container_3gal`, `bare_root`, `B&B`, `bulb_corm_rhizome`, `cutting`. Open: do we need a `bareroot_grade` distinction (seedling vs liner vs landscape-size for woody species)? Probably yes for trees, no for forbs. Phase 1 lock the eight; revisit when `crown_tree` lands.

**Q2: Allowed-form subset per species.**
Some species don't tolerate certain forms (taproot species poorly bare-rooted, certain sedges plug-only). Schema needs `allowed_forms: [enum, ...]` per species, not just a single default. Default form per species is also useful (e.g., for *Andropogon gerardii* default to `seed` for restoration grade, `plug` for ornamental).

**Q3: BOM quantity semantics by form.**
- Counts for transplants is straightforward. One *Quercus alba* B&B is one tree.
- Seed needs more care: PLS lb/acre is the standard for restoration drills; broadcast rate may differ; ornamental seed may be sold by the packet/oz. The BOM should report the natural unit per form. Mixed-species seed mixes complicate this since the consumer typically wants total mix weight + per-species PLS percentages, not raw species weights.
- Possible alternative-form reporting: when a scene calls for 5000 little bluestem, the BOM could surface `seed: X lb PLS` AND `plug: 5000 plugs` so the consumer picks based on availability and budget. Maybe a flag.

**Q4: Export format.**
- BOM canonical: JSON. Schema versioned. CSV adapter for spreadsheet users.
- Scene artifact: JSON with embedded GeoJSON polygon + key-specimen feature collection + species mix and density spec. Suggested suffix `.plantae-scene.json`.
- Versioning: every export carries `plantae_version`, `scene_schema_version`, `template_versions: {species: version, ...}` so a procurement consumer knows what it's looking at.

**Q5: Substitution semantics.**
Marketplace concept distinguishes restoration-grade from ornamental-grade. If a species in the BOM is unavailable from any supplier in the consumer's region, the marketplace may want to substitute. Substitution is a marketplace concern, but plantae's grade tag (F44) and provenance tag (F45) are the inputs. Consider whether plantae should also emit substitution hints (e.g., "if *Schizachyrium scoparium* is unavailable, accept *Andropogon gerardii*") or leave that purely to the marketplace.

**Q6: Phase placement.**
- F43, F44, F45 (species attributes) land in Phase 1 alongside the new archetypes — additive YAML schema work.
- F46, F47, F53 (exports + CLI subcommand) land alongside the scene spec, V2.2 territory.
- No marketplace-side work in plantae roadmap. The marketplace product owns its own roadmap.

---

## Pending — Audit against engineering principles (NEW 2026-05-02, early reads)

Five items surfaced from a pass through REQUIREMENTS and OPEN_QUESTIONS against `engineering_principles.md`. All are **early reads, not decisions** — they're proposals to be argued, refined, or rejected. Logged here so they don't fall through the cracks.

### a. Scene composer UI (F42) phasing

Currently parked at Phase 5+. P1 (deep usability at every facet) suggests earlier. Communities ship at Phase 3 and would stay hand-authored YAML-only until Phase 5+, which is years of community-rendering capability without the polygon UI that makes it usable for non-technical users (designers, contractors, restoration coordinators). Counter: hand-authored YAML works; researchers and developers can produce scenes without the UI; UI is a contributor-experience improvement, not a blocker for core capability.

**Early read:** move F42 to Phase 3 alongside community rendering, since that's when scenes become a user-facing concept rather than a developer-facing one. Phase 5+ is the right slot only if early users will all be technical, which contradicts the design-to-procurement vision.

### b. Scene artifact (F46) vs scene YAML (F36) duplication

F46 describes a portable scene artifact distinct from `scenes/<scene_name>.yaml` in F36. P2 (minimum architectural complexity) suggests these may be the same artifact under two names. The YAML is already portable, diffable, versionable, and built on open formats (P6). A distinct "scene artifact" export with a separate format adds a schema layer that earns nothing the YAML doesn't already deliver. Counter: the YAML might evolve to carry developer-facing fields (template overrides, generator hints, debug annotations) that aren't appropriate for the procurement-side artifact; distinct schemas keep concerns separate.

**Early read:** the YAML is the scene artifact at a single shared schema. F46 collapses to "CLI ergonomics around the YAML" rather than introducing a new artifact format. If developer-facing fields appear later, scope them with a `_dev` namespace inside the YAML, don't fork the format.

### c. Lstring caching priority

Currently logged as Phase 3 prerequisite, "trivial to add in Step 7. Not building yet." S11 (specimen ↔ community seam) makes lstring caching load-bearing for community work, and ~100 to ~2000 derives at 1-10ms each (NF3 target) is exactly the runtime cost P4 puts downward pressure on. Counter: premature work before the community use case lands; the cache shape might need to differ once we see real access patterns.

**Early read:** no change to actual sequencing, but elevate the status from "deferred" to "build alongside the first multi-specimen render in Phase 3" so it doesn't get forgotten as a forcing function for the community render to feel right. The trivial implementation noted (memoization keyed on `(species_yaml_hash, seed)`) is probably the right starting shape.

### d. glTF revisit for V2 / landscape scale

A2 chose OBJ + JSON sidecar because PlantGL had no glTF codec. The constraint is irrelevant in V2 (no PlantGL). Currently OBJ + JSON wins on P3 (no extra dep, parsers are commodities) and P6 (two open formats). At landscape scale (Phase 4+, NF4 1000+ plants), native glTF instancing (KHR_mesh_instancing) may win on P4 against three.js InstancedMesh-of-OBJ-geometry, since the format itself can encode instances natively rather than the renderer reconstructing them. Counter: not yet, community-scale renders haven't proven the perf problem; switching exporters mid-stream is real cost.

**Early read:** stay OBJ + JSON through V2.3. Re-evaluate at Phase 4+ when landscape rendering starts struggling. The decision tree is cleaner now (PlantGL constraint gone), so a future re-evaluation will be quick if perf data forces it.

### e. V2 bundler choice through the principle lens

OPEN_QUESTIONS leans esbuild over Vite over no-build ESM. P3 (minimum dependency and tool surface) suggests revisiting. No-build raw ESM is zero build tooling; the plantae viewer already runs no-build with native browser imports. esbuild earns its way only when bundle composition or size becomes a real constraint. Counter: V2.2+ communities and species catalog growth may want code splitting and compression that ESM-direct can't offer; the V2 done criterion of <2 MB compressed (V2 §7.6) probably needs a bundler at scale.

**Early read:** no-build raw ESM through V2.0 and V2.1, prove cross-runtime parity and the algorithm port without bundler complexity. Adopt esbuild only when bundle pain is concrete (sizes approaching 2 MB, or HTTP/2 multiplexing not absorbing the request count). P3 says deps earn their way; bundler doesn't earn its way prophylactically.
