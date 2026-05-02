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


def test_neither_color_nor_curve_errors():
    with pytest.raises(ValidationError) as exc:
        MaterialEntry(roughness=0.5)
    assert "either `color` or `color_curve`" in str(exc.value)


def test_both_color_and_curve_errors():
    with pytest.raises(ValidationError) as exc:
        MaterialEntry(
            color="#3a6b40",
            color_curve=[{"doy": 100, "color": "#a8c878"}, {"doy": 200, "color": "#3a6b40"}],
        )
    assert "cannot have both" in str(exc.value)


def test_color_curve_must_be_doy_sorted():
    with pytest.raises(ValidationError) as exc:
        MaterialEntry(color_curve=[
            {"doy": 280, "color": "#b85a2c"},
            {"doy": 100, "color": "#a8c878"},
        ])
    assert "sorted by doy" in str(exc.value)


def test_color_curve_needs_two_keyframes():
    with pytest.raises(ValidationError) as exc:
        MaterialEntry(color_curve=[{"doy": 100, "color": "#a8c878"}])
    assert "at least 2 keyframes" in str(exc.value)


def test_invalid_hex_color_rejected():
    with pytest.raises(ValidationError):
        MaterialEntry(color="not_a_hex")
    with pytest.raises(ValidationError):
        MaterialEntry(color="#zzz")


def test_doy_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ColorKeyframe(doy=400, color="#3a6b40")


def test_roughness_metalness_clamped_to_unit_range():
    with pytest.raises(ValidationError):
        MaterialEntry(color="#3a6b40", roughness=1.5)
    with pytest.raises(ValidationError):
        MaterialEntry(color="#3a6b40", metalness=-0.1)


def test_unknown_side_rejected():
    with pytest.raises(ValidationError):
        MaterialEntry(color="#3a6b40", side="UpsideDownSide")


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
