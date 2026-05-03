"""Render-pipeline tests for Step 5.

Verifies:
- derive() returns (Lsystem, lstring) and applies the RenderContext externs.
- interpret() at varying T_RENDER returns Scenes of the expected shape counts
  (matches Step 3's age-aware tests).
- export_to_obj_with_sidecar() writes both files with matching shape counts.
- The sidecar JSON has stable shape names and valid material_ids.
- The OBJ file has stable `o SHAPE_<id>` group names (no per-process address).
- The CLI `plant-sim render` command works end-to-end.
- Pre-flush export is empty (zero shapes, zero sidecar entries).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from plant_sim.cli import main as cli_main
from plant_sim.codegen.generator import write as codegen_write
from plant_sim.render.derive import derive, interpret
from plant_sim.render.export import (
    ExportError,
    export_to_obj_with_sidecar,
)
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent
ECHINACEA_YAML = REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml"
MATERIALS_LIB = REPO / "materials" / "library.json"


@pytest.fixture(scope="module")
def echinacea_lpy_path(tmp_path_factory) -> Path:
    sp = Species.from_yaml(ECHINACEA_YAML)
    out = tmp_path_factory.mktemp("generated")
    return codegen_write(sp, output_dir=out, seed=42)


@pytest.fixture(scope="module")
def echinacea_derived(echinacea_lpy_path: Path):
    return derive(echinacea_lpy_path)


# ---- derive() and interpret() wrappers ----

def test_derive_returns_lsystem_and_lstring(echinacea_derived):
    lsys, lstring = echinacea_derived
    assert lsys is not None
    assert len(lstring) > 0


def test_interpret_at_peak_nonempty(echinacea_derived):
    lsys, lstring = echinacea_derived
    scene = interpret(lsys, lstring, 250.0)
    assert len(scene) > 0


def test_interpret_pre_flush_empty(echinacea_derived):
    lsys, lstring = echinacea_derived
    scene = interpret(lsys, lstring, 50.0)
    assert len(scene) == 0


# ---- Exporter ----

def test_export_writes_obj_and_sidecar(tmp_path: Path, echinacea_derived):
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "test_render.obj"
    out_obj, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    assert out_obj.exists()
    assert out_sidecar.exists()
    assert out_sidecar.suffix == ".json"
    assert out_sidecar.name == "test_render.materials.json"


def test_sidecar_shape_count_matches_obj_groups(tmp_path: Path, echinacea_derived):
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "echinacea.obj"
    out_obj, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)

    sidecar = json.loads(out_sidecar.read_text())
    obj_text = out_obj.read_text()
    obj_groups = [l for l in obj_text.splitlines() if l.startswith("o ")]

    assert sidecar["meta"]["scene_shape_count"] == len(sidecar["shapes"])
    assert len(obj_groups) == len(sidecar["shapes"])


def test_obj_uses_stable_shape_names(tmp_path: Path, echinacea_derived):
    """OBJ groups should be `o SHAPE_<id>` (stable), not `o SHAPEID_<id>_<addr>` (per-process)."""
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "stable_names.obj"
    out_obj, _ = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    obj_text = out_obj.read_text()
    assert "o SHAPE_" in obj_text, "expected stable `o SHAPE_<id>` group names"
    assert "SHAPEID_" not in obj_text, "address-suffixed names should have been rewritten"


def test_sidecar_names_match_obj_group_names(tmp_path: Path, echinacea_derived):
    """Each sidecar entry's name should equal an `o <name>` line in the OBJ."""
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "names_match.obj"
    out_obj, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)

    sidecar = json.loads(out_sidecar.read_text())
    obj_names = {
        l[2:].strip()
        for l in out_obj.read_text().splitlines()
        if l.startswith("o ")
    }
    sidecar_names = {entry["name"] for entry in sidecar["shapes"]}
    assert sidecar_names == obj_names


def test_sidecar_material_ids_are_in_library(tmp_path: Path, echinacea_derived):
    """Every material_id in the sidecar should exist in materials/library.json."""
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "matlib.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)

    library = json.loads(MATERIALS_LIB.read_text())
    sidecar = json.loads(out_sidecar.read_text())
    for entry in sidecar["shapes"]:
        assert entry["material_id"] in library, (
            f"sidecar material_id {entry['material_id']!r} not in library"
        )


def test_export_pre_flush_writes_empty_files(tmp_path: Path, echinacea_derived):
    """Before leaf flush, no renderables fire and no shapes are emitted."""
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "preflush.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 50.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    assert sidecar["meta"]["scene_shape_count"] == 0
    assert sidecar["shapes"] == []


def test_export_carries_meta_into_sidecar(tmp_path: Path, echinacea_derived):
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "metatest.obj"
    _, out_sidecar = export_to_obj_with_sidecar(
        lsys, lstring, 220.0, obj_path,
        sidecar_meta={"lpy_file": "echinacea_purpurea_seed_42.lpy", "extra": "value"},
    )
    sidecar = json.loads(out_sidecar.read_text())
    assert sidecar["meta"]["t_render"] == 220.0
    assert sidecar["meta"]["lpy_file"] == "echinacea_purpurea_seed_42.lpy"
    assert sidecar["meta"]["extra"] == "value"


def test_sidecar_carries_template_archetype_and_version(tmp_path: Path, echinacea_derived):
    """Sidecar surfaces TEMPLATE_ARCHETYPE / TEMPLATE_VERSION baked into the .lpy."""
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "version.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 200.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    assert sidecar["meta"]["template_archetype"] == "rosette_scape_composite"
    assert sidecar["meta"]["template_version"] == "1.0.0"


def test_export_boundary_case_at_inflo_peak(tmp_path: Path, echinacea_derived):
    """Regression: T_RENDER == INFLO_PEAK_DOY hits an age==0 ScapeSegment boundary.

    sigmoid_grow(0, ...) returns 0 -> PlantGL emits no shape for that segment,
    while the lstring-walk filter would otherwise count it. The exporter
    uses strict age > 0 to match.
    """
    lsys, lstring = echinacea_derived
    obj_path = tmp_path / "boundary.obj"
    # T=200 exactly is INFLORESCENCE_PEAK_DOY for canonical Echinacea.
    out_obj, _ = export_to_obj_with_sidecar(lsys, lstring, 200.0, obj_path)
    assert out_obj.exists()  # Just no ExportError raised


def test_render_context_externs_applied(tmp_path: Path, echinacea_lpy_path: Path):
    """RenderContext fields should land in the lsys context as externs."""
    lsys, lstring = derive(
        echinacea_lpy_path,
        RenderContext(seed=99, time_offset_doy=10.0, emergence_offset_days=2.0),
    )
    ctx = lsys.context()
    assert ctx["TIME_OFFSET_DOY"] == 10.0
    assert ctx["EMERGENCE_OFFSET"] == 2.0


# ---- CLI integration ----

def test_cli_render_writes_both_files(tmp_path: Path, echinacea_lpy_path: Path):
    runner = CliRunner()
    out_dir = tmp_path / "render_out"
    result = runner.invoke(
        cli_main,
        ["render", str(echinacea_lpy_path), "--t", "250", "--output", str(out_dir)],
    )
    assert result.exit_code == 0, result.output
    obj_files = list(out_dir.glob("*.obj"))
    json_files = list(out_dir.glob("*.materials.json"))
    assert len(obj_files) == 1
    assert len(json_files) == 1
    # T_RENDER suffix in filename
    assert "_t250" in obj_files[0].name
