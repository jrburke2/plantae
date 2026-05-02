# plantae

Algorithmic plant simulator built on **L-Py + OpenAlea + three.js**. The substrate is L-systems, the canonical biological-fractal formalism (Lindenmayer 1968): small recursive rule sets produce the self-similar structure plants actually exhibit.

YAML in → OBJ + JSON sidecar out → slider scrubs continuous-time growth in a browser. Communities of plants build from a shared scene seed; a user can select an arbitrary map shape and fill it with plants drawn from a species mix and density spec. Plantae's output ends at design and a portable plant-list BOM; procurement lives in a separable downstream product (see the marketplace concept doc).

Substrate validated by 2026-05-02 spikes (Echinacea +9, Andropogon 4/4).
Phase 0 status: **complete** — two archetypes (rosette_scape_composite,
tiller_clump), two reference species (*Echinacea purpurea*,
*Andropogon gerardii*), full pipeline from YAML to live slider.

**V2 plan:** the algorithm will move to the browser. The codegen will gain a
TypeScript emission target; production becomes serverless and supports
arbitrary BOI-style seeds at scale. See
[V2_BROWSER_RUNTIME_PLAN.md](V2_BROWSER_RUNTIME_PLAN.md) for the full
migration plan. Phase 1 archetype work and V2 runtime work proceed in
parallel; both runtimes coexist during the transition.

**Reference docs:**
- [REQUIREMENTS.md](REQUIREMENTS.md) — single source of truth for what plantae does, planned, and explicitly out of scope. Includes the Seams section enumerating active and resolved structural cuts.
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — running log of architectural decisions (resolved and pending), with rationale.
- [engineering_principles.md](../engineering_principles.md) — cross-project engineering principles (P1 usability, P2-P4 minima, P5-P7 architectural commitments).

## Quick demo

```bash
# Setup (one-time)
mamba env create -f environment.yml      # ~3 min
mamba activate plant_sim
pip install -e .

# Run
plant-sim serve
# Open http://localhost:8000/
```

Drag the slider. The plant grows. Switch species via URL:
`?species=andropogon_gerardii&seed=42`.

On Apple Silicon, prefix the env-create with `CONDA_SUBDIR=osx-64` since
openalea is not yet packaged for arm64. Rosetta 2 handles the rest.

## Add your first species

5-minute workflow. See [CONTRIBUTING_botanist.md](CONTRIBUTING_botanist.md)
for the full version.

1. Pick an archetype that fits your species. Today: `rosette_scape_composite`
   (Asteraceae forbs like Echinacea) or `tiller_clump` (Poaceae grasses like
   Andropogon).
2. Copy a reference species YAML at `species/<family>/<existing>.yaml` to
   `species/<your_family>/<your_species>.yaml`. Edit the values.
3. `plant-sim validate species/.../<your_species>.yaml` — fast feedback.
4. Open a PR. CI generates + renders + posts a summary comment.

If your species doesn't fit either archetype yet, see
[CONTRIBUTING_developer.md](CONTRIBUTING_developer.md) for the path:
either build a new archetype template or set `template_override:` in your
YAML to point at a one-off template.

## Architecture

```
species/<family>/<species>.yaml                       (botanist surface)
        +
templates/archetypes/<archetype>.lpy.j2               (developer surface)
        ↓ codegen (Jinja2 + length conversion + persistent-marker injection)
generated/<species>_seed_<n>.lpy                      (intermediate; gitignored)
        ↓ L-Py derive() once per (species, seed)
in-memory lstring                                     (cached per (species, seed))
        ↓ L-Py sceneInterpretation(T_RENDER) per slider tick
PlantGL Scene
        ↓ exporter walks lstring + Scene in parallel
output/<species>_seed_<n>_t<doy>.obj                  (geometry; gitignored)
output/<species>_seed_<n>_t<doy>.materials.json      (shape_id -> material_id)
        ↓ HTTP fetch from viewer
three.js MeshStandardMaterial per mesh                (color curves evaluated client-side)
```

Read the `OPEN_QUESTIONS.md` file for the running list of architectural
decisions made during Phase 0 (export format, units, persistent marker,
RenderContext plumbing, etc.) plus pending and audit items. Read
`REQUIREMENTS.md` for the consolidated source of truth and the Seams section
enumerating structural cuts. Read `engineering_principles.md` for the
cross-project principles (P1 to P7) the project is built against.

## Layout

```
plantae/
├── README.md, CONTRIBUTING_botanist.md, CONTRIBUTING_developer.md
├── OPEN_QUESTIONS.md
├── pyproject.toml, environment.yml
├── plant_sim/                package
│   ├── cli.py                plant-sim CLI entry points
│   ├── schema/               Pydantic models for species YAML and materials
│   ├── codegen/              YAML -> .lpy (generator + validator)
│   ├── render/               L-Py wrapper + OBJ + sidecar exporter
│   └── server/               FastAPI dev server
├── species/<family>/         botanist contributor surface (YAML)
├── templates/archetypes/     developer surface (Jinja2 .lpy.j2)
├── templates/macros/         shared Jinja macros (persistent-marker)
├── growth_functions/         shared sigmoid/alpha/seasonal helpers
├── materials/                material library JSON + schema docs
├── viewer/                   three.js viewer (HTML + ES modules, no build step)
└── tests/                    pytest suite (102 tests as of Step 8)
```

## CLI

```
plant-sim validate <species_yaml>          schema-validate, fast feedback
plant-sim schema-json -o species/_schema/species.schema.json
                                           emit JSON Schema for IDE tooling
plant-sim generate <species_yaml> [--seed N] [--output DIR]
                                           YAML → .lpy
plant-sim render <lpy_file> [--t DOY] [--output DIR]
                                           .lpy → OBJ + materials sidecar
plant-sim serve [--port 8000] [--host 127.0.0.1]
                                           dev server with live slider viewer
plant-sim export <scene> [--scene] [--plant-list] [--format json|csv]
                                           scene artifact and/or plant-list BOM
                                           for downstream procurement (planned, V2.2)
```

## License

TBD. Add a LICENSE file before public contributions land.
