"""Materials library tests for Step 6.

The library JSON shape is validated by `MaterialLibrary` (Pydantic). We
also verify that every material_id referenced by the canonical species
YAMLs exists in the library (the codegen runs this check at generate
time; this test is a fast belt-and-suspenders so library edits never
silently break the canonical species).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from plant_sim.codegen.validator import MaterialCrossCheck, collect_material_ids
from plant_sim.schema.material import (
    ColorKeyframe,
    MaterialEntry,
    MaterialLibrary,
)
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent
LIB_PATH = REPO / "materials" / "library.json"


# ---- Library validates against the schema ----

def test_library_loads_and_validates():
    lib = MaterialLibrary.from_json_file(LIB_PATH)
    assert len(lib.entries) >= 10, "Phase 0 library should have at least 10 entries"


def test_library_contains_all_phase_0_required_ids():
    """Kickoff Step 6 names ~10 material_ids needed for the two reference species."""
    required = {
        "leaf_mature_green", "leaf_glaucous", "petiole_green",
        "culm_summer_green", "culm_winter_straw",
        "ray_floret_purple", "disk_floret_brown",
        "panicle_bronze", "crown_dark", "default_brown",
    }
    raw = json.loads(LIB_PATH.read_text())
    missing = required - set(raw)
    assert not missing, f"missing material_ids in library: {missing}"


# ---- MaterialEntry validation ----

def test_static_color_entry_validates():
    e = MaterialEntry(color="#3a6b40", roughness=0.65)
    assert e.color == "#3a6b40"
    assert e.color_curve is None


def test_color_curve_entry_validates():
    e = MaterialEntry(color_curve=[
        {"doy": 100, "color": "#a8c878"},
        {"doy": 280, "color": "#b85a2c"},
    ])
    assert e.color is None
    assert len(e.color_curve) == 2


# MaterialEntry validation errors with a specific user-facing message.
@pytest.mark.parametrize("kwargs,expected_substring", [
    ({"roughness": 0.5},
     "either `color` or `color_curve`"),
    ({"color": "#3a6b40",
      "color_curve": [{"doy": 100, "color": "#a8c878"}, {"doy": 200, "color": "#3a6b40"}]},
     "cannot have both"),
    ({"color_curve": [{"doy": 280, "color": "#b85a2c"}, {"doy": 100, "color": "#a8c878"}]},
     "sorted by doy"),
    ({"color_curve": [{"doy": 100, "color": "#a8c878"}]},
     "at least 2 keyframes"),
])
def test_material_entry_message(kwargs, expected_substring):
    with pytest.raises(ValidationError) as exc:
        MaterialEntry(**kwargs)
    assert expected_substring in str(exc.value)


# Field-level rejection cases (any ValidationError counts; Pydantic's own
# constraint messages are not part of our public surface).
@pytest.mark.parametrize("ctor,kwargs", [
    (MaterialEntry, {"color": "not_a_hex"}),
    (MaterialEntry, {"color": "#zzz"}),
    (ColorKeyframe, {"doy": 400, "color": "#3a6b40"}),
    (MaterialEntry, {"color": "#3a6b40", "roughness": 1.5}),       # > unit range
    (MaterialEntry, {"color": "#3a6b40", "metalness": -0.1}),      # < unit range
    (MaterialEntry, {"color": "#3a6b40", "side": "UpsideDownSide"}),  # unknown enum
])
def test_validation_error_raised(ctor, kwargs):
    with pytest.raises(ValidationError):
        ctor(**kwargs)


# ---- Cross-check: every reference species' material_ids exist in library ----

def test_echinacea_yaml_material_ids_in_library():
    sp = Species.from_yaml(REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml")
    checker = MaterialCrossCheck.load(LIB_PATH)
    issues = checker.check_ids(collect_material_ids(sp))
    assert issues == [], f"echinacea references unknown material_ids: {issues}"


def test_andropogon_yaml_material_ids_in_library():
    sp = Species.from_yaml(REPO / "species" / "poaceae" / "andropogon_gerardii.yaml")
    checker = MaterialCrossCheck.load(LIB_PATH)
    issues = checker.check_ids(collect_material_ids(sp))
    assert issues == [], f"andropogon references unknown material_ids: {issues}"
