"""Cross-check tests: SpeciesLibrary, MixLibrary, and the per-artifact checkers."""

from __future__ import annotations

from pathlib import Path

import pytest

from plant_sim.codegen.cross_check import (
    MixLibrary,
    SpeciesLibrary,
    check_mix_against_species,
    check_scene_against_libs,
)
from plant_sim.schema.mix import Mix, MixComponent
from plant_sim.schema.scene import (
    ApplicationRate,
    Boundary,
    GeoJSONPolygon,
    KeySpecimen,
    MixEntry,
    Scene,
    SpeciesEntry,
)
from plant_sim.schema.species import GradeTag, MaterialForm, Species

REPO = Path(__file__).resolve().parent.parent
SPECIES_DIR = REPO / "species"
MIX_DIR = REPO / "mixes"


# ---- SpeciesLibrary ----

def test_species_library_loads_reference_species():
    lib = SpeciesLibrary.load(SPECIES_DIR)
    assert lib.has("echinacea_purpurea")
    assert lib.has("andropogon_gerardii")
    sp = lib.get("echinacea_purpurea")
    assert sp is not None and sp.scientific_name == "Echinacea purpurea"


def test_species_library_skips_invalid_yaml(tmp_path: Path):
    """A YAML that doesn't schema-validate is silently skipped at library load."""
    (tmp_path / "broken.yaml").write_text("not_a_species: true\n")
    lib = SpeciesLibrary.load(tmp_path)
    assert not lib.has("broken")


def test_species_library_skips_schema_dir(tmp_path: Path):
    """The species/_schema/ directory should not be walked into."""
    schema_dir = tmp_path / "_schema"
    schema_dir.mkdir()
    (schema_dir / "stray.yaml").write_text("scientific_name: fake\n")  # would be invalid anyway
    lib = SpeciesLibrary.load(tmp_path)
    assert not lib.has("stray")


# ---- MixLibrary ----

def test_mix_library_loads_demo_mix():
    lib = MixLibrary.load(MIX_DIR)
    assert lib.has("restoration_demo_mix")


def test_mix_library_handles_missing_dir(tmp_path: Path):
    lib = MixLibrary.load(tmp_path / "definitely_does_not_exist")
    assert lib.mixes == {}


# ---- check_mix_against_species ----

def test_demo_mix_passes_cross_check():
    species_lib = SpeciesLibrary.load(SPECIES_DIR)
    mix = Mix.from_yaml(MIX_DIR / "restoration_demo_mix.yaml")
    assert check_mix_against_species(mix, species_lib) == []


def _real_species_pair() -> dict[str, Species]:
    return {
        "echinacea_purpurea": Species.from_yaml(SPECIES_DIR / "asteraceae" / "echinacea_purpurea.yaml"),
        "andropogon_gerardii": Species.from_yaml(SPECIES_DIR / "poaceae" / "andropogon_gerardii.yaml"),
    }


def test_mix_with_unknown_species_rejected():
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    bad_mix = Mix(
        name="bad", display_name="Bad", description="",
        grade=GradeTag.restoration_grade,
        components=[
            MixComponent(species="andropogon_gerardii", weight_pct=50),
            MixComponent(species="not_a_real_species", weight_pct=50),
        ],
    )
    issues = check_mix_against_species(bad_mix, species_lib)
    assert len(issues) == 1
    assert "not_a_real_species" in issues[0].message
    assert "not found in species library" in issues[0].message


def test_mix_with_species_lacking_seed_form_rejected():
    species = _real_species_pair()
    # Strip seed from andropogon's allowed_forms (in-memory mutation; tests the check)
    species["andropogon_gerardii"].material.allowed_forms = [MaterialForm.plug, MaterialForm.bare_root]
    species["andropogon_gerardii"].material.default_form = MaterialForm.plug
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=species)

    bad_mix = Mix(
        name="bad", display_name="Bad", description="",
        grade=GradeTag.restoration_grade,
        components=[
            MixComponent(species="echinacea_purpurea", weight_pct=50),
            MixComponent(species="andropogon_gerardii", weight_pct=50),
        ],
    )
    issues = check_mix_against_species(bad_mix, species_lib)
    assert len(issues) == 1
    assert "andropogon_gerardii" in issues[0].message
    assert "seed" in issues[0].message.lower()


def test_mix_with_grade_mismatch_rejected():
    """andropogon is restoration_grade only; mix declared as ornamental_grade should fail."""
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    bad_mix = Mix(
        name="bad", display_name="Bad", description="",
        grade=GradeTag.ornamental_grade,
        components=[
            MixComponent(species="andropogon_gerardii", weight_pct=50),
            MixComponent(species="echinacea_purpurea", weight_pct=50),
        ],
    )
    issues = check_mix_against_species(bad_mix, species_lib)
    assert any(
        "andropogon_gerardii" in i.message and "ornamental_grade" in i.message
        for i in issues
    )


# ---- check_scene_against_libs ----

def _local_meters_polygon() -> GeoJSONPolygon:
    return GeoJSONPolygon(
        type="Polygon",
        coordinates=[[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]],
    )


def test_demo_scene_passes_cross_check():
    species_lib = SpeciesLibrary.load(SPECIES_DIR)
    mix_lib = MixLibrary.load(MIX_DIR)
    scene = Scene.from_yaml(REPO / "scenes" / "prairie_demo.yaml")
    assert check_scene_against_libs(scene, species_lib, mix_lib) == []


def test_scene_with_unknown_species_rejected():
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    mix_lib = MixLibrary(mix_dir=Path("/tmp/fake"), mixes={})
    scene = Scene(
        name="bad",
        boundary=Boundary(coord_system="local_meters", geometry=_local_meters_polygon()),
        species_mix=[SpeciesEntry(species="ghost_species", density_per_m2=1)],
    )
    issues = check_scene_against_libs(scene, species_lib, mix_lib)
    assert any("ghost_species" in i.message for i in issues)


def test_scene_with_unknown_mix_rejected():
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    mix_lib = MixLibrary(mix_dir=Path("/tmp/fake"), mixes={})
    scene = Scene(
        name="bad",
        boundary=Boundary(coord_system="local_meters", geometry=_local_meters_polygon()),
        species_mix=[
            MixEntry(mix="ghost_mix", application_rate=ApplicationRate(value=8)),
        ],
    )
    issues = check_scene_against_libs(scene, species_lib, mix_lib)
    assert any("ghost_mix" in i.message and "not found in mix library" in i.message for i in issues)


def test_scene_with_unknown_key_specimen_rejected():
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    mix_lib = MixLibrary(mix_dir=Path("/tmp/fake"), mixes={})
    scene = Scene(
        name="bad",
        boundary=Boundary(coord_system="local_meters", geometry=_local_meters_polygon()),
        species_mix=[SpeciesEntry(species="andropogon_gerardii", density_per_m2=1)],
        key_specimens=[KeySpecimen(species="ghost_oak", position=(5.0, 5.0))],
    )
    issues = check_scene_against_libs(scene, species_lib, mix_lib)
    assert any("ghost_oak" in i.message and "key_specimen" in i.message for i in issues)


def test_scene_with_form_override_not_in_allowed_rejected():
    """If a SpeciesEntry overrides form to something the species doesn't support, error."""
    species_lib = SpeciesLibrary(species_dir=Path("/tmp/fake"), species=_real_species_pair())
    mix_lib = MixLibrary(mix_dir=Path("/tmp/fake"), mixes={})
    # andropogon allowed_forms = [seed, plug, bare_root]; B&B is not allowed
    scene = Scene(
        name="bad",
        boundary=Boundary(coord_system="local_meters", geometry=_local_meters_polygon()),
        species_mix=[
            SpeciesEntry(species="andropogon_gerardii", density_per_m2=1, form=MaterialForm.bnb),
        ],
    )
    issues = check_scene_against_libs(scene, species_lib, mix_lib)
    assert any(
        "andropogon_gerardii" in i.message and "B&B" in i.message and "allowed_forms" in i.message
        for i in issues
    )


# ---- CLI integration ----

def test_cli_validate_passes_for_demo_mix(tmp_path: Path):
    from click.testing import CliRunner
    from plant_sim.cli import main as cli_main
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(MIX_DIR / "restoration_demo_mix.yaml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "restoration_demo_mix" in result.output


def test_cli_validate_passes_for_demo_scene(tmp_path: Path):
    from click.testing import CliRunner
    from plant_sim.cli import main as cli_main
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(REPO / "scenes" / "prairie_demo.yaml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "prairie_demo" in result.output


def test_cli_validate_rejects_scene_with_unknown_mix(tmp_path: Path):
    from click.testing import CliRunner
    from plant_sim.cli import main as cli_main
    bad_scene = tmp_path / "bad.yaml"
    bad_scene.write_text(
        "name: bad\n"
        "boundary:\n"
        "  coord_system: local_meters\n"
        "  geometry:\n"
        "    type: Polygon\n"
        "    coordinates:\n"
        "      - [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]\n"
        "species_mix:\n"
        "  - mix: ghost_mix\n"
        "    application_rate: {value: 8, unit: lb_PLS_per_acre}\n"
    )
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(bad_scene)])
    assert result.exit_code != 0
    assert "ghost_mix" in result.output


def test_cli_validate_rejects_unknown_yaml_kind(tmp_path: Path):
    from click.testing import CliRunner
    from plant_sim.cli import main as cli_main
    bad = tmp_path / "mystery.yaml"
    bad.write_text("just: a_dict\nwithout: any_signature\n")
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(bad)])
    assert result.exit_code != 0
    assert "could not detect YAML kind" in result.output
