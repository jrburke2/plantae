# Contributing pipeline / archetype work (for developers)

This guide covers extending the plantae pipeline: adding archetype
templates, growth-function primitives, materials, or schema fields.

If you're adding a species, see
[CONTRIBUTING_botanist.md](CONTRIBUTING_botanist.md) instead.

---

## Setup

```bash
CONDA_SUBDIR=osx-64 mamba env create -f environment.yml   # macOS arm64; drop prefix on Linux/Intel
mamba activate plant_sim
pip install -e .
pytest                                                     # 102 tests, ~5 sec
```

Verify the dev server boots: `plant-sim serve`, open
http://localhost:8000/, scrub the slider.

---

## Architecture in one diagram

```
species YAML  --[Pydantic]-->  Species object
                  Species  --[Jinja2]-->  generated/foo.lpy
                                .lpy   --[L-Py derive()]-->  lstring
                                                   lstring  --[L-Py interpret(T)]-->  PlantGL Scene
                                                                                 Scene  --[exporter]-->  OBJ + materials.json
                                                                                                         OBJ + sidecar  --[three.js]-->  rendered mesh
```

The codegen owns all L-Py syntax weirdness so contributors never write
raw `.lpy` for the common case.

---

## Locked Phase 0 conventions

All in `templates/archetypes/README.md`. Briefly:

- **Y-up, right-handed, origin at the geometric base** of the plant.
- **Internal length unit = meters.** Per-species YAML declares its
  preferred unit; codegen converts before .lpy emission.
- **Angles in degrees** (suffix `_deg` in YAML and templates).
- **Calendar coordinates as DOY** (suffix `_doy`, range 1..366).
- Every template declares the standard externs:
  `T_RENDER`, `SPECIMEN_SEED`, `TIME_OFFSET_DOY`, `EMERGENCE_OFFSET`,
  `POSITION_X_M`, `POSITION_Y_M`, `POSITION_Z_M`.
- Every renderable turtle move (`F()`, `~l()`, `@O()`) must be wrapped in
  a module that carries a `mat_id` parameter (last param). Raw turtle
  emissions outside modules abort the exporter — see Step 8 finding in
  `OPEN_QUESTIONS.md`.

---

## Adding a new archetype template

Worked example: a hypothetical `recursive_branch_forb` archetype.

### 1. Add a Pydantic parameter block

In `plant_sim/schema/species.py`:

```python
class TrunkParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    height_range: FloatRangeInclusive = Field(...)
    branch_angle_deg: float = Field(default=45.0, ge=0, le=180)
    queryable: bool = True
    material_id: str = "stem_default"

class RecursiveBranchForbParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trunk: TrunkParams
    # ... more sub-blocks
```

Add the archetype name to:

```python
ArchetypeName = Literal["rosette_scape_composite", "tiller_clump", "recursive_branch_forb"]

_ARCHETYPE_TO_PARAMS = {
    "rosette_scape_composite": RosetteScapeCompositeParameters,
    "tiller_clump": TillerClumpParameters,
    "recursive_branch_forb": RecursiveBranchForbParameters,
}
```

### 2. Register the template path

In `plant_sim/codegen/generator.py`:

```python
_ARCHETYPE_TO_TEMPLATE = {
    "rosette_scape_composite": "archetypes/rosette_scape_composite.lpy.j2",
    "tiller_clump": "archetypes/tiller_clump.lpy.j2",
    "recursive_branch_forb": "archetypes/recursive_branch_forb.lpy.j2",
}
```

If the archetype uses any new length-typed YAML fields, extend
`_build_meters_dict()` to pre-convert them (so templates reference
`{{ m.trunk.height_max }}` rather than calling
`species.units.length_to_meters()` inline).

### 3. Write the template

`templates/archetypes/recursive_branch_forb.lpy.j2`. Read the existing
two for reference; both are ~150 lines. Pattern:

```jinja
{# header comment #}
{% from "macros/queryable.lpy.j2" import one_shot as queryable_one_shot %}
import math
import random
from growth_functions import sigmoid_grow, alpha_at, draw_growth_days

# === Externs ===
extern(T_RENDER = ...)
extern(SPECIMEN_SEED = ...)
# ... full standard extern set

random.seed(SPECIMEN_SEED)

# === Constants from species YAML ===
TRUNK_HEIGHT_MIN_M = {{ "%.6f" % m.trunk.height_min }}
TRUNK_HEIGHT_MAX_M = {{ "%.6f" % m.trunk.height_max }}
# ...

# === Module declarations ===
module Plant(t_doy, fired)
module Trunk(t_birth, height_m, expanded)
module Branch(t_birth, length_m, mat_id)
# ...

Axiom: Plant(0, False)
derivation length: {{ species.phenology.abscission_doy + 30 }}

# === Productions ===
production:

Plant(t_doy, fired) :
    effective_t = t_doy + TIME_OFFSET_DOY
    if (not fired) and effective_t >= LEAF_FLUSH_DOY + EMERGENCE_OFFSET:
        produce Trunk(t_doy, TRUNK_HEIGHT_M, False) Plant(t_doy + 1, True)
    else:
        produce Plant(t_doy + 1, fired)

# Queryable one-shot dispatcher via macro:
{{ queryable_one_shot("Trunk", "t_birth, height_m", "t_birth, height_m", "Branch(t_birth, height_m * 0.4, BRANCH_MAT)") }}

# Multi-iteration growers (Scape-style) need inline persistent-marker logic.
# See rosette_scape_composite for the worked example.

# === Interpretation ===
interpretation:

Branch(t_birth, length_m, mat_id) :
    age = T_RENDER + TIME_OFFSET_DOY - (t_birth + EMERGENCE_OFFSET)
    if age < 0:
        produce *
    grown_m = sigmoid_grow(age, 14.0, length_m)
    produce ;(2) F(grown_m)

# === Hide bookkeeping modules ===
Plant(t, f) --> ;(0) f(0)
Trunk(t, h, e) --> ;(0) f(0)

endlsystem
```

The validator (Step 4) catches:
- Multi-character module references not declared via `module Name(...)`.
- Multi-line `-->` rules (L-Py rejects).
- Color slot indices outside 0..6 (PlantGL clamps).
- Material IDs not in `materials/library.json`.

### 4. Write a reference species YAML

Same shape as Echinacea / Andropogon. Lives at `species/<family>/<species>.yaml`.

### 5. Add tests

Mirror `tests/test_codegen_andropogon.py`. At minimum:

- archetype is registered
- template renders without error
- generated .lpy passes static validator
- L-Py loads + derives
- module census matches expectations
- render at peak succeeds (exporter doesn't abort)
- pre-flush is empty
- material distribution matches the YAML's material_ids

### 6. Update the archetype README

Add a table entry in `templates/archetypes/README.md` and the
contributor README.

---

## Adding a growth function

`growth_functions/__init__.py`. Stable Phase 0 functions:

- `sigmoid_grow(age, growth_days, max_value) -> float` — 0 → max over
  growth_days, sigmoidal. Validated by both spikes.
- `alpha_at(age, lifespan, senescence_window=10) -> float` — visibility
  ramp for senescence.
- `seasonal_color(t_render_doy, phenology, palette) -> hex` — Phase 0
  stub returning palette default; Phase 2+ implements keyframed curves.
- `draw_growth_days(rng, mean, stddev, minimum)` — extension hook for
  Phase 1+ stochastic growth windows.

Add new functions to `__all__` and template imports as needed. L-Py
files run as Python, so `from growth_functions import ...` works inside
.lpy after `pip install -e .`.

---

## Adding a material

`materials/library.json` — JSON-shaped per the
[`MaterialEntry`](plant_sim/schema/material.py) Pydantic model.

Static color:

```json
"my_new_material": {
  "type": "MeshStandardMaterial",
  "color": "#abcdef",
  "roughness": 0.65,
  "metalness": 0.0,
  "side": "DoubleSide"
}
```

Phenological color curve:

```json
"my_seasonal_material": {
  "type": "MeshStandardMaterial",
  "color_curve": [
    {"doy": 100, "color": "#a8c878"},
    {"doy": 280, "color": "#b85a2c"},
    {"doy": 320, "color": "#5a3a1c"}
  ],
  "roughness": 0.65,
  "metalness": 0.0,
  "side": "DoubleSide"
}
```

Naming convention: `<organ>_<state>_<color_or_treatment>`. See
[`materials/README.md`](materials/README.md).

After editing, `pytest tests/test_materials.py` validates the file.

---

## Adding a schema field

If a new YAML field is needed (e.g., `phenology.emergence_jitter_days`):

1. Add the Field to the appropriate Pydantic model in
   `plant_sim/schema/species.py`. Always include a `description=` so the
   JSON Schema export carries inline help.
2. If it's a length, add it to `_build_meters_dict()` in
   `plant_sim/codegen/generator.py` so templates see the converted
   meters version.
3. Reference it in archetype templates as needed.
4. Run `plant-sim schema-json` to regenerate
   `species/_schema/species.schema.json` so VS Code picks up the new
   field's autocomplete.
5. Add tests covering the new field's validation.

Extra-fields are forbidden, so adding a field never breaks existing
species YAMLs that don't use it.

---

## L-Py idioms (carryover from spike findings)

Documented in long form at the project memory entries:

- **Multi-character module names need `module Name(params)` declaration.**
  L-Py parses undeclared multi-char names character-by-character.
- **Single-line `-->` rules only.** Multi-line interpretation rules abort
  the L-Py parser. Use `:` + `produce` form for multi-line bodies.
- **Persistent marker pattern.** Queryable per-instance modules carry an
  `expanded` boolean parameter. See `templates/macros/queryable.lpy.j2`
  for the macro and `templates/archetypes/rosette_scape_composite.lpy.j2`
  Scape rule for the multi-iteration variant.
- **L-Py + boost::python is NOT thread-safe.** All L-Py calls in the
  server go through a single-worker `ThreadPoolExecutor`. Pre-existing
  pin in `plant_sim/server/app.py` — don't remove without reading the
  related memory entry.
- **PlantGL has no glTF codec.** Phase 0 uses OBJ + JSON sidecar. Step
  0 of the kickoff doc explains the bridge.

---

## CI

Two workflows in `.github/workflows/`:

- **`tests.yml`** — pytest on every push and PR.
- **`render.yml`** — runs on PRs touching `species/**/*.yaml`,
  `templates/**`, `plant_sim/codegen/**`, `plant_sim/render/**`, or
  `materials/library.json`. Generates + renders changed species and
  posts a summary comment.

Both use `conda-incubator/setup-miniconda` with mamba for fast solves.
First run takes ~4 min on ubuntu-latest because openalea3 has a lot of
deps; subsequent runs use the cached env.

---

## Where to look first

| To do this                                       | Read this                                            |
|--------------------------------------------------|------------------------------------------------------|
| Add a new species using existing archetype       | `CONTRIBUTING_botanist.md`                           |
| Add a new archetype template                     | `templates/archetypes/README.md` + this doc          |
| Understand the persistent marker pattern         | `templates/macros/queryable.lpy.j2` + memory entries |
| Understand the export format choice              | `OPEN_QUESTIONS.md` Step 0 entry                     |
| Understand the unit-system design                | `OPEN_QUESTIONS.md` Step 2 entries                   |
| Understand why server uses a single thread       | `plant_sim/server/app.py` comments                   |
| Understand the spike findings (substrate choice) | parent vitae-db `spike/lpy_spike_kit/FINDINGS.md`    |
