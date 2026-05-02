# Open Questions

Running list of decisions deferred during Phase 0. Resolve in Phase 1+ unless they block.

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

## Pending — Per-specimen material variation

**Q:** Sun-leaves vs shade-leaves, microhabitat color shifts. Currently `material_id` is baked at codegen time per species, not per specimen. Phase 4+ ecology problem; logged so it's not a surprise.

---

## Pending — Coordinate convention adoption

Locked in `templates/archetypes/README.md` as: Y-up, right-handed, origin at geometric base, internal unit meters. All archetype templates and the viewer must follow.

---

## Pending — Lstring caching

`derive()` is 1-10 ms; multi-specimen scenes will call it 100s of times. Server-side memoization keyed on `(species_yaml_hash, seed)` is required for Phase 3 and trivial to add in Step 7. Not building yet.
