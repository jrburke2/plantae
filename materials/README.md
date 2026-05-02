# Materials library

`library.json` is the single source of truth for visual materials. Both
the codegen validator (cross-checks species YAML `material_id` references)
and the viewer (applies materials to OBJ shapes via the JSON sidecar
mapping) read from this file.

The Pydantic schema lives at `plant_sim/schema/material.py` and is
validated as part of the test suite.

## Schema

Each top-level key is a `material_id` referenced by species YAMLs. The
value is one of two shapes:

### Static color

```json
"leaf_mature_green": {
  "type": "MeshStandardMaterial",
  "color": "#3a6b40",
  "roughness": 0.65,
  "metalness": 0.0,
  "side": "DoubleSide"
}
```

### Phenological (DOY-keyed) color curve

```json
"culm_summer_green": {
  "type": "MeshStandardMaterial",
  "color_curve": [
    {"doy": 100, "color": "#5e8a4a"},
    {"doy": 220, "color": "#5e8a4a"},
    {"doy": 280, "color": "#a89860"},
    {"doy": 320, "color": "#b89968"}
  ],
  "roughness": 0.7,
  "metalness": 0.0,
  "side": "DoubleSide"
}
```

Keyframes must be sorted by DOY. The viewer linearly interpolates between
adjacent keyframes; T_RENDER values before the first or after the last
keyframe clamp to the nearest end.

### Field reference

| Field          | Type     | Required | Default              | Notes |
|----------------|----------|----------|----------------------|-------|
| `type`         | string   | no       | `MeshStandardMaterial` | Reserved for future material classes |
| `color`        | hex str  | one of   | —                    | 6-digit, e.g. `#3a6b40` |
| `color_curve`  | array    | one of   | —                    | At least 2 keyframes, DOY-sorted |
| `roughness`    | float    | no       | `0.7`                | three.js roughness, 0..1 |
| `metalness`    | float    | no       | `0.0`                | three.js metalness, 0..1 |
| `side`         | string   | no       | `DoubleSide`         | `FrontSide`, `BackSide`, or `DoubleSide` |

Exactly one of `color` or `color_curve` must be present.

## Naming convention

`<organ>_<state>_<color_or_treatment>` — e.g.

- `leaf_mature_green`
- `leaf_glaucous` (state without explicit color suffix)
- `culm_summer_green` (state implies seasonal palette)
- `ray_floret_purple`
- `disk_floret_brown`
- `panicle_bronze`

The `<organ>_<state>_default` form is the fallback id used by archetype
templates when a species YAML doesn't override.

## Adding a new material

1. Edit `library.json`, picking an id that follows the naming convention.
2. Add an entry with either `color` or `color_curve`.
3. Run `pytest tests/test_materials.py` to confirm the library still validates.
4. Reference the new id from a species YAML's `material_id` field.

The codegen's material cross-check (`plant-sim generate`) catches typos
between YAML and library before any L-Py runs.

## Phase 0 vs later

Phase 0 ships ~15 entries covering the rosette_scape_composite (Echinacea)
and tiller_clump (Andropogon) reference species. Per-archetype fallback
defaults like `leaf_mature_default` exist so future contributors can ship a
species YAML without overriding every material.

Later phases (Phase 2+) may add per-component materials (cuticle, tomentum,
abaxial vs adaxial leaf surface) and additional color-curve interpolation
modes (spline, easing, HSL-space). Phase 0 sticks with linear RGB.
