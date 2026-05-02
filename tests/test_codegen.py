"""Codegen tests for Step 3.

Verifies:
- The rosette_scape_composite template renders without error against the
  Echinacea YAML.
- The generated .lpy file loads in L-Py.
- Derivation runs to completion and produces the expected queryable
  marker modules (RosetteLeaf, Scape, InfloHead) in the final lstring.
- sceneInterpretation at peak DOY produces a non-empty Scene.
- sceneInterpretation BEFORE leaf flush produces zero shapes
  (age-aware geometry working).

The persistent-marker pattern is verified by counting marker modules
in the final lstring (Andropogon spike's load-bearing test pattern,
applied to the new rosette_scape_composite archetype).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from click.testing import CliRunner

from plant_sim.cli import main as cli_main
from plant_sim.codegen.generator import (
    available_archetypes,
    dispatch_template,
    generate,
    load_species,
    render_archetype,
    write,
)
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent
ECHINACEA_YAML = REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml"


@pytest.fixture(scope="module")
def echinacea_lpy_text() -> str:
    sp = Species.from_yaml(ECHINACEA_YAML)
    return render_archetype(sp, RenderContext(seed=42))


@pytest.fixture(scope="module")
def echinacea_lpy_path(tmp_path_factory, echinacea_lpy_text: str) -> Path:
    p = tmp_path_factory.mktemp("generated") / "echinacea_purpurea_seed_42.lpy"
    p.write_text(echinacea_lpy_text)
    return p


# ---- Rendering ----

def test_template_renders_without_error(echinacea_lpy_text: str):
    assert "Axiom: Plant" in echinacea_lpy_text
    assert "module RosetteLeaf" in echinacea_lpy_text
    assert "module Scape" in echinacea_lpy_text
    assert "module InfloHead" in echinacea_lpy_text
    # Persistent-marker plumbing
    assert "if expanded:" in echinacea_lpy_text
    assert "if done:" in echinacea_lpy_text
    # Material ids carried through
    assert 'ROSETTE_MAT = "leaf_mature_green"' in echinacea_lpy_text
    assert 'RAY_MAT     = "ray_floret_purple"' in echinacea_lpy_text


def test_lengths_converted_to_meters(echinacea_lpy_text: str):
    """Echinacea height_range = [24, 48] inches -> [0.6096, 1.2192] meters."""
    # Grep for the canonical scape-height range in meters, accounting for float repr.
    assert "0.609600" in echinacea_lpy_text   # 24 in
    assert "1.219200" in echinacea_lpy_text   # 48 in


def test_externs_declared(echinacea_lpy_text: str):
    for name in (
        "T_RENDER", "SPECIMEN_SEED", "TIME_OFFSET_DOY",
        "EMERGENCE_OFFSET", "POSITION_X_M", "POSITION_Y_M", "POSITION_Z_M",
    ):
        assert f"extern({name}" in echinacea_lpy_text, f"missing extern({name}=...)"


# ---- L-Py load + derive ----

def test_lpy_loads_and_derives(echinacea_lpy_path: Path):
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(echinacea_lpy_path))
    lstring = lsys.derive()
    assert len(lstring) > 0


def test_persistent_markers_survive_in_lstring(echinacea_lpy_path: Path):
    """Scape and InfloHead must appear in the final lstring as queryable markers."""
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(echinacea_lpy_path))
    lstring = lsys.derive()
    counts: Counter = Counter()
    for module in lstring:
        try:
            counts[module.name] += 1
        except AttributeError:
            pass

    # With seed=42 the rosette_count_range [6,14] draws SOME number; we check >=1.
    assert counts["RosetteLeaf"] >= 1, "no RosetteLeaf modules in final lstring"
    # Scape: between 1 and 5 per scape_count_range
    assert 1 <= counts["Scape"] <= 5, f"unexpected Scape count: {counts['Scape']}"
    # InfloHead: one per scape (since each scape produces one head)
    assert counts["InfloHead"] == counts["Scape"], (
        f"InfloHead ({counts['InfloHead']}) should equal Scape ({counts['Scape']})"
    )


# ---- sceneInterpretation: age-aware geometry ----

def test_scene_at_peak_is_nonempty(echinacea_lpy_path: Path):
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(echinacea_lpy_path))
    lstring = lsys.derive()
    lsys.context()["T_RENDER"] = 250.0  # well past peak (DOY 200) and inflorescence
    scene = lsys.sceneInterpretation(lstring)
    assert len(scene) > 0, "scene at peak DOY should have shapes"


def test_scene_before_leaf_flush_is_empty(echinacea_lpy_path: Path):
    """T_RENDER < LEAF_FLUSH_DOY (105) -> all sigmoid_grow returns 0 -> scene shapes drop out."""
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(echinacea_lpy_path))
    lstring = lsys.derive()
    lsys.context()["T_RENDER"] = 50.0  # before any phenology event
    scene = lsys.sceneInterpretation(lstring)
    # All renderable modules guard with `if age < 0: produce *`. Before flush,
    # every module's age is negative, so nothing geometric is emitted.
    assert len(scene) == 0, f"expected 0 shapes pre-flush, got {len(scene)}"


def test_scene_grows_over_time(echinacea_lpy_path: Path):
    """Scene shape count should rise monotonically (or at least non-trivially) as T_RENDER advances."""
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(echinacea_lpy_path))
    lstring = lsys.derive()

    counts = []
    for t in (50.0, 110.0, 180.0, 220.0, 280.0):
        lsys.context()["T_RENDER"] = t
        scene = lsys.sceneInterpretation(lstring)
        counts.append(len(scene))

    # Pre-flush 0; mid-season some shapes; mature lots more.
    assert counts[0] == 0
    assert counts[-1] > counts[1], (
        f"shape count did not grow over time: {counts}"
    )


# ---- Generator API surface (Step 4) ----

def test_load_species_returns_species_object():
    sp = load_species(ECHINACEA_YAML)
    assert isinstance(sp, Species)
    assert sp.scientific_name == "Echinacea purpurea"


def test_available_archetypes_lists_rosette_scape_composite():
    arches = available_archetypes()
    assert "rosette_scape_composite" in arches


def test_dispatch_template_uses_archetype():
    sp = load_species(ECHINACEA_YAML)
    path = dispatch_template(sp)
    assert path.endswith("rosette_scape_composite.lpy.j2")


def test_dispatch_template_honors_override(tmp_path: Path):
    sp_text = ECHINACEA_YAML.read_text() + "\ntemplate_override: my/custom/foo.lpy.j2\n"
    p = tmp_path / "override.yaml"
    p.write_text(sp_text)
    sp = load_species(p)
    assert dispatch_template(sp) == "my/custom/foo.lpy.j2"


def test_generate_with_seed_changes_stochastic_draws():
    sp = load_species(ECHINACEA_YAML)
    src_a = generate(sp, seed=42)
    src_b = generate(sp, seed=43)
    # Same template structure but the SPECIMEN_SEED extern differs.
    assert "SPECIMEN_SEED = 42" in src_a
    assert "SPECIMEN_SEED = 43" in src_b


def test_write_uses_content_addressed_filename(tmp_path: Path):
    """Filenames embed the canonical 8-char base32 seed (not raw int)."""
    from plant_sim.schema.seed import Seed
    sp = load_species(ECHINACEA_YAML)
    path = write(sp, output_dir=tmp_path, seed=4711)
    canonical = Seed(4711).canonical()  # e.g. '00000IM7'
    assert path.name == f"echinacea_purpurea_seed_{canonical}.lpy"
    assert path.exists()
    body = path.read_text()
    assert f"SPECIMEN_SEED = {4711}" in body  # int form still in extern


def test_write_runs_validator_and_blocks_on_error(tmp_path: Path):
    """If the validator finds errors, write() should raise and not produce a file."""
    sp = load_species(ECHINACEA_YAML)
    # Patch the template registry to point at a known-bad template
    bad = tmp_path / "bad.lpy.j2"
    bad.write_text(
        "module Plant(t)\n"
        "production:\n"
        "Plant(t) :\n"
        "    produce UndeclaredFoo(t)\n"
    )
    # Use template_override to point at the bad file (relative-to-templates path needed,
    # so write a separate copy in templates/_test/)
    repo_templates = REPO / "templates"
    test_dir = repo_templates / "_test"
    test_dir.mkdir(exist_ok=True)
    test_template = test_dir / "bad.lpy.j2"
    test_template.write_text(bad.read_text())
    try:
        sp_text = ECHINACEA_YAML.read_text() + f"\ntemplate_override: _test/bad.lpy.j2\n"
        yaml_path = tmp_path / "bad_species.yaml"
        yaml_path.write_text(sp_text)
        sp = load_species(yaml_path)
        from plant_sim.codegen.validator import ValidationError
        with pytest.raises(ValidationError) as exc:
            write(sp, output_dir=tmp_path, seed=99)
        assert "UndeclaredFoo" in str(exc.value)
        # Ensure no file was written
        assert not (tmp_path / "echinacea_purpurea_seed_99.lpy").exists()
    finally:
        # Cleanup the test template so it doesn't pollute future runs
        test_template.unlink(missing_ok=True)
        try:
            test_dir.rmdir()
        except OSError:
            pass


# ---- CLI integration ----

def test_cli_generate_writes_file(tmp_path: Path):
    from plant_sim.schema.seed import Seed
    runner = CliRunner()
    out = tmp_path / "generated"
    result = runner.invoke(
        cli_main,
        ["generate", str(ECHINACEA_YAML), "--output", str(out), "--seed", "7"],
    )
    assert result.exit_code == 0, result.output
    expected = out / f"echinacea_purpurea_seed_{Seed(7).canonical()}.lpy"
    assert expected.exists()
    assert "Wrote" in result.output


def test_cli_generate_accepts_string_seed(tmp_path: Path):
    """BOI-style shareable string seeds work end-to-end through the CLI."""
    runner = CliRunner()
    out = tmp_path / "generated"
    result = runner.invoke(
        cli_main,
        ["generate", str(ECHINACEA_YAML), "--output", str(out), "--seed", "XQF2-D6S1"],
    )
    assert result.exit_code == 0, result.output
    expected = out / "echinacea_purpurea_seed_XQF2D6S1.lpy"
    assert expected.exists()
    # Round-trip through display form in the CLI output
    assert "XQF2-D6S1" in result.output


def test_cli_generate_rejects_invalid_yaml(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("scientific_name: x\n")  # missing many required fields
    runner = CliRunner()
    result = runner.invoke(cli_main, ["generate", str(bad), "--output", str(tmp_path)])
    assert result.exit_code != 0
    # Pydantic validation error printed to stderr (mixed in result.output for CliRunner)
    assert "INVALID YAML" in result.output


def test_cli_generate_rejects_unknown_material(tmp_path: Path):
    yaml_text = ECHINACEA_YAML.read_text().replace(
        "ray_floret_purple", "definitely_not_a_real_material_id"
    )
    p = tmp_path / "bad_material.yaml"
    p.write_text(yaml_text)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["generate", str(p), "--output", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "definitely_not_a_real_material_id" in result.output
