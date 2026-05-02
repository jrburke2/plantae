# Contributing a species (for botanists)

You don't need to know any code to add a species to plantae. You edit a
YAML file, open a PR, and CI renders the result and posts a preview.

If you're a developer adding archetypes or pipeline features, see
[CONTRIBUTING_developer.md](CONTRIBUTING_developer.md) instead.

---

## What you need

- A web browser
- A GitHub account
- ~15 minutes
- A reference for your species' biology — height range, leaf size,
  flowering time, etc. The Wilhelm + Rericha *Flora of the Chicago Region*
  is the project's primary reference.

You don't need to install Python, conda, L-Py, or three.js. CI handles
the rendering. If you DO want to render locally, see the README's
"Quick demo" section.

---

## The 5-minute workflow

### 1. Pick an archetype

An "archetype" is a morphological pattern that fits a class of species.
Phase 0 supports two:

| Archetype                 | Use for                              | Reference species          |
|---------------------------|--------------------------------------|----------------------------|
| `rosette_scape_composite` | Forbs with basal rosette + flowering scapes + composite-head inflorescences | *Echinacea purpurea* |
| `tiller_clump`            | Bunchgrasses with multiple flowering culms | *Andropogon gerardii* |

Pick the one that best matches your species. If neither fits, see
[CONTRIBUTING_developer.md](CONTRIBUTING_developer.md) — but skim the
existing archetypes first; they often fit more species than you'd think.

### 2. Copy the closest reference species

Find a species that uses your archetype, copy its YAML, change the
values. The two reference YAMLs:

- [`species/asteraceae/echinacea_purpurea.yaml`](species/asteraceae/echinacea_purpurea.yaml) — `rosette_scape_composite`
- [`species/poaceae/andropogon_gerardii.yaml`](species/poaceae/andropogon_gerardii.yaml) — `tiller_clump`

Save your copy at `species/<your_family>/<genus_species>.yaml` (lowercase,
underscores). Examples:
- `species/asteraceae/rudbeckia_hirta.yaml`
- `species/poaceae/sorghastrum_nutans.yaml`

### 3. Edit the values

Every field has a description. If you open the YAML in **VS Code with
the Red Hat YAML extension installed**, you'll see hover tooltips and
autocomplete for free — the project ships its JSON Schema and the
`# yaml-language-server: $schema=...` header at the top of every species
YAML wires it up.

Walking through the Echinacea YAML field by field:

```yaml
scientific_name: Echinacea purpurea       # binomial scientific name
common_name: purple coneflower            # vernacular
family: Asteraceae                        # botanical family
archetype: rosette_scape_composite        # which template this YAML uses
growth_form: herbaceous_perennial         # one of: herbaceous_perennial,
                                          # perennial_grass, annual,
                                          # biennial, shrub, tree, vine

units:
  length: in                              # in / cm / m / mm / ft / yd, or
                                          # an inline custom-unit definition
                                          # (see CONTRIBUTING_developer.md)

height_range: [24, 48]                    # min, max plant height
crown_width: [12, 24]                     # min, max crown width

habitat:
  primary: [mesic_prairie, dry-mesic_prairie]
  secondary: [savanna, garden]
  cc_value: 5                             # Coefficient of Conservatism
                                          # (Wilhelm 2017), 0..10

references:
  - "Wilhelm, G.S. and Rericha, L. 2017. Flora of the Chicago Region."
                                          # at least one citation required

phenology:                                # all dates as day-of-year (1..366)
  leaf_flush_doy: 105                     # leaves emerge
  peak_doy: 180                           # peak vegetative growth
  senescence_onset_doy: 275               # senescence begins
  abscission_doy: 315                     # leaves drop / dieback
  inflorescence_emerge_doy: 175           # inflorescence first appears
  inflorescence_peak_doy: 200             # peak bloom
  inflorescence_senescence_doy: 245       # bloom ends
  inflorescence_persist_winter: true      # dried structure overwinters

parameters:                               # archetype-specific block
  rosette:
    leaf_count_range: [6, 14]             # min, max leaves per specimen
    leaf_template: lanceolate_serrate     # leaf shape (Phase 0 stub)
    leaf_length_range: [4, 8]             # min, max blade length (in `units`)
    petiole_length_range: [1, 3]          # optional; omit for sessile leaves
    phyllotaxis: spiral                   # spiral / distichous / opposite / whorled
    divergence_angle_deg: 137.5           # 137.5 = golden angle
    queryable: true                       # leave true; advanced use
    material_id: leaf_mature_green        # see materials/library.json
  scape:
    count_range: [1, 5]
    height_range: [24, 48]
    branching: simple                     # simple / branched
    leaf_count_on_scape: [2, 4]
    queryable: true
    material_id: culm_summer_green
  inflorescence:
    type: composite_head                  # composite_head / raceme / panicle / spike / umbel / corymb / cyme
    diameter: [3, 4]
    ray_count_range: [13, 21]
    ray_droop: true                       # true if rays droop downward
    queryable: true
    ray_material_id: ray_floret_purple
    disk_material_id: disk_floret_brown
```

The schema enforces:

- `extra="forbid"`: typos in field names error loudly. If you misspell
  `phenoligy` you'll get a clear validation error.
- Range validation: `[min, max]` with `min < max` (or `min <= max` for
  inclusive ranges).
- DOY ordering: `leaf_flush < peak < senescence < abscission`. CI rejects
  PRs whose phenology is out of order.
- Material IDs must exist in `materials/library.json`. If you want a
  color the library doesn't have, either pick the closest existing one
  or follow [CONTRIBUTING_developer.md](CONTRIBUTING_developer.md) to
  add a new entry.

### 4. Open a PR

Push your branch, open a PR. Two CI checks fire:

- **`tests`** — runs the full pytest suite. If you only added a new
  species YAML, this passes.
- **`render-changed-species`** — generates + renders + comments. Within
  a few minutes, the bot replies on your PR with the rendered shape
  count and material distribution.

If `render-changed-species` fails, the comment shows where: schema
validation, codegen, render, or material lookup. Common causes:

- DOY values out of order — fix the phenology block.
- Range with `min > max` — flip the values.
- Missing required field — check the diff against a reference YAML.
- Unknown `material_id` — pick one from `materials/library.json` or
  ask a developer to add a new color.

After fixing, push again. CI re-runs.

### 5. Review the rendered preview

The bot comment includes a shape count and material distribution at
T_RENDER=200 (peak DOY). For visual review, fetch the branch locally
and run `plant-sim serve`. Phase 2 adds rendered PNG previews in the
PR comment so you don't need to pull locally.

If your specimen looks wrong (counts way off, missing structure,
material miscolored), iterate on the YAML and push again. The bot
re-comments per push.

---

## Length units

Default is imperial inches (`units.length: in`), matching most North
American botanical references. Switch to metric by changing one line:

```yaml
units:
  length: cm

height_range: [60, 122]   # values now interpreted as cm
```

The codegen converts to meters internally before rendering. A specimen
authored in inches and the same specimen authored in cm produce
visually-identical output.

For unusual units (cubits, body-lengths, project-specific), use an
inline definition:

```yaml
units:
  length:
    name: hand
    meters_per_unit: 0.1016
height_range: [6, 12]   # = 0.6096..1.2192 m = 24..48 in
```

---

## What if your species doesn't fit any archetype?

Two escape hatches, in order of preference:

1. **Ask for a new shared archetype.** Open an issue describing the
   morphology. If three or more species in the Reference Species Set
   would benefit, a developer adds a new archetype template (see
   [CONTRIBUTING_developer.md](CONTRIBUTING_developer.md)) and you're
   the first species using it.

2. **`template_override` in your YAML.** For genuinely one-off species
   that don't justify a shared archetype, point at a custom template:

   ```yaml
   template_override: templates/custom/your_weird_species.lpy.j2
   ```

   You'll need a developer to write the custom template. Use sparingly —
   shared archetypes are easier to maintain.

Avoid copying a shared archetype and editing it for your species alone.
That fork breaks future updates to the shared template.

---

## Local rendering (optional)

If you want to render and inspect locally instead of waiting for CI:

```bash
mamba env create -f environment.yml      # one-time, ~3 min
mamba activate plant_sim
pip install -e .

plant-sim validate species/your_family/your_species.yaml
plant-sim serve
# Open http://localhost:8000/?species=your_species&seed=42
```

Drag the slider; iterate on the YAML; refresh.

On Apple Silicon: `CONDA_SUBDIR=osx-64 mamba env create -f environment.yml`.
