"""Codegen tests.

Generic codegen-pipeline invariants are parametrized over the reference
archetypes so a regression in any archetype shows up here. Archetype-
specific tests (template body strings, module census, material
distribution) live in their own sections below.

Add a new archetype: append a row to ARCHETYPES; the generic suite
picks it up automatically.
"""

from __future__ import annotations

import json
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
from plant_sim.codegen.validator import validate_lpy
from plant_sim.render.derive import derive
from plant_sim.render.export import export_to_obj_with_sidecar
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.seed import Seed
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent


# ---- Reference archetypes ----

_ECHINACEA_ARCH = {
    "yaml": "species/asteraceae/echinacea_purpurea.yaml",
    "scientific_name": "Echinacea purpurea",
    "archetype": "rosette_scape_composite",
    "template_suffix": "rosette_scape_composite.lpy.j2",
    "filename_stem": "echinacea_purpurea",
    "real_material_id": "ray_floret_purple",
}
_ANDROPOGON_ARCH = {
    "yaml": "species/poaceae/andropogon_gerardii.yaml",
    "scientific_name": "Andropogon gerardii",
    "archetype": "tiller_clump",
    "template_suffix": "tiller_clump.lpy.j2",
    "filename_stem": "andropogon_gerardii",
    "real_material_id": "panicle_bronze",
}
ARCHETYPES = [
    pytest.param(_ECHINACEA_ARCH, id="echinacea"),
    pytest.param(_ANDROPOGON_ARCH, id="andropogon"),
]


@pytest.fixture(scope="module", params=ARCHETYPES)
def arch(request) -> dict:
    return request.param


@pytest.fixture(scope="module")
def lpy_text(arch) -> str:
    sp = Species.from_yaml(REPO / arch["yaml"])
    return render_archetype(sp, RenderContext(seed=42))


@pytest.fixture(scope="module")
def lpy_path(tmp_path_factory, arch, lpy_text) -> Path:
    p = tmp_path_factory.mktemp(f"gen_{arch['filename_stem']}") / f"{arch['filename_stem']}_seed_42.lpy"
    p.write_text(lpy_text)
    return p


# ---- Generic codegen invariants (parametrized over archetypes) ----

def test_archetype_registered(arch):
    assert arch["archetype"] in available_archetypes()


def test_load_species_returns_species_object(arch):
    sp = load_species(REPO / arch["yaml"])
    assert isinstance(sp, Species)
    assert sp.scientific_name == arch["scientific_name"]


def test_dispatch_template_uses_archetype(arch):
    sp = load_species(REPO / arch["yaml"])
    assert dispatch_template(sp).endswith(arch["template_suffix"])


def test_externs_declared(lpy_text):
    for name in (
        "T_RENDER", "SPECIMEN_SEED", "TIME_OFFSET_DOY",
        "EMERGENCE_OFFSET", "POSITION_X_M", "POSITION_Y_M", "POSITION_Z_M",
    ):
        assert f"extern({name}" in lpy_text, f"missing extern({name}=...)"


def test_generated_lpy_passes_static_validator(lpy_text):
    issues = validate_lpy(lpy_text, raise_on_error=False)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"validator caught issues: {errors}"


def test_lpy_loads_and_derives(lpy_path):
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    assert len(lstring) > 0


def test_scene_at_peak_is_nonempty(lpy_path):
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(lpy_path))
    lstring = lsys.derive()
    lsys.context()["T_RENDER"] = 250.0
    scene = lsys.sceneInterpretation(lstring)
    assert len(scene) > 0, "scene at peak DOY should have shapes"


def test_scene_before_leaf_flush_is_empty(lpy_path):
    """T_RENDER < phenology onset: every renderable's age is negative; nothing emits."""
    from openalea.lpy import Lsystem
    lsys = Lsystem(str(lpy_path))
    lstring = lsys.derive()
    lsys.context()["T_RENDER"] = 50.0
    scene = lsys.sceneInterpretation(lstring)
    assert len(scene) == 0, f"expected 0 shapes pre-flush, got {len(scene)}"


def test_render_at_peak_via_exporter(tmp_path: Path, arch, lpy_path):
    """Exporter must round-trip lstring → OBJ + sidecar without raising."""
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / f"{arch['filename_stem']}.obj"
    out_obj, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    assert out_obj.exists() and out_sidecar.exists()


def test_render_pre_flush_via_exporter(tmp_path: Path, arch, lpy_path):
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / f"{arch['filename_stem']}_preflush.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 50.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    assert sidecar["meta"]["scene_shape_count"] == 0


def test_generate_with_seed_changes_stochastic_draws(arch):
    sp = load_species(REPO / arch["yaml"])
    src_a = generate(sp, seed=42)
    src_b = generate(sp, seed=43)
    assert "SPECIMEN_SEED = 42" in src_a
    assert "SPECIMEN_SEED = 43" in src_b


def test_write_uses_content_addressed_filename(arch, tmp_path: Path):
    """Filenames embed the canonical 8-char base32 seed (not raw int)."""
    sp = load_species(REPO / arch["yaml"])
    path = write(sp, output_dir=tmp_path, seed=4711)
    canonical = Seed(4711).canonical()
    assert path.name == f"{arch['filename_stem']}_seed_{canonical}.lpy"
    assert path.exists()
    if arch["archetype"] == "rosette_scape_composite":
        # Echinacea: extern still carries the int form
        assert f"SPECIMEN_SEED = {4711}" in path.read_text()


# ---- One-off codegen invariants (no need to parametrize) ----

def test_dispatch_template_honors_override(tmp_path: Path):
    sp_text = (REPO / _ECHINACEA_ARCH["yaml"]).read_text() + "\ntemplate_override: my/custom/foo.lpy.j2\n"
    p = tmp_path / "override.yaml"
    p.write_text(sp_text)
    sp = load_species(p)
    assert dispatch_template(sp) == "my/custom/foo.lpy.j2"


def test_write_runs_validator_and_blocks_on_error(tmp_path: Path):
    """If the validator finds errors, write() should raise and not produce a file."""
    bad = tmp_path / "bad.lpy.j2"
    bad.write_text(
        "module Plant(t)\n"
        "production:\n"
        "Plant(t) :\n"
        "    produce UndeclaredFoo(t)\n"
    )
    repo_templates = REPO / "templates"
    test_dir = repo_templates / "_test"
    test_dir.mkdir(exist_ok=True)
    test_template = test_dir / "bad.lpy.j2"
    test_template.write_text(bad.read_text())
    try:
        sp_text = (REPO / _ECHINACEA_ARCH["yaml"]).read_text() + "\ntemplate_override: _test/bad.lpy.j2\n"
        yaml_path = tmp_path / "bad_species.yaml"
        yaml_path.write_text(sp_text)
        sp = load_species(yaml_path)
        from plant_sim.codegen.validator import ValidationError
        with pytest.raises(ValidationError) as exc:
            write(sp, output_dir=tmp_path, seed=99)
        assert "UndeclaredFoo" in str(exc.value)
        assert not (tmp_path / f"{_ECHINACEA_ARCH['filename_stem']}_seed_99.lpy").exists()
    finally:
        test_template.unlink(missing_ok=True)
        try:
            test_dir.rmdir()
        except OSError:
            pass


# ---- Echinacea-specific assertions ----

@pytest.fixture(scope="module")
def echinacea_lpy_text() -> str:
    sp = Species.from_yaml(REPO / _ECHINACEA_ARCH["yaml"])
    return render_archetype(sp, RenderContext(seed=42))


@pytest.fixture(scope="module")
def echinacea_lpy_path(tmp_path_factory, echinacea_lpy_text: str) -> Path:
    p = tmp_path_factory.mktemp("gen_echinacea_specific") / "echinacea_purpurea_seed_42.lpy"
    p.write_text(echinacea_lpy_text)
    return p


def test_echinacea_template_body(echinacea_lpy_text: str):
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


def test_echinacea_lengths_converted_to_meters(echinacea_lpy_text: str):
    """Echinacea height_range = [24, 48] inches -> [0.6096, 1.2192] meters."""
    assert "0.609600" in echinacea_lpy_text   # 24 in
    assert "1.219200" in echinacea_lpy_text   # 48 in


def test_echinacea_persistent_markers_survive_in_lstring(echinacea_lpy_path: Path):
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


def test_echinacea_scene_grows_over_time(echinacea_lpy_path: Path):
    """Shape count rises non-trivially as T_RENDER advances through phenology."""
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
    assert counts[-1] > counts[1], f"shape count did not grow over time: {counts}"


# ---- Andropogon-specific assertions ----

@pytest.fixture(scope="module")
def andropogon_lpy_text() -> str:
    sp = Species.from_yaml(REPO / _ANDROPOGON_ARCH["yaml"])
    return generate(sp, seed=42)


@pytest.fixture(scope="module")
def andropogon_lpy_path(tmp_path_factory, andropogon_lpy_text: str) -> Path:
    p = tmp_path_factory.mktemp("gen_andropogon_specific") / "andropogon_gerardii_seed_42.lpy"
    p.write_text(andropogon_lpy_text)
    return p


def test_andropogon_template_body(andropogon_lpy_text: str):
    assert "Axiom: Clump" in andropogon_lpy_text
    assert "module Tiller(" in andropogon_lpy_text
    assert "module Panicle(" in andropogon_lpy_text
    assert "module CulmSegment(" in andropogon_lpy_text  # the wrapper added in Step 8
    assert 'LEAF_MAT = "leaf_mature_green"' in andropogon_lpy_text
    assert 'PANICLE_MAT = "panicle_bronze"' in andropogon_lpy_text


def test_andropogon_module_census_plausible(andropogon_lpy_path: Path):
    """Census plausibility for Andropogon @ seed=42, mature.

    Deterministic counts (Tiller, Crown) are exact; rng-driven counts
    (Panicle, Raceme, GrassLeaf) live in plausibility ranges so future
    rng-related changes don't keep invalidating the test.
    """
    lsys, lstring = derive(andropogon_lpy_path, RenderContext(seed=42))
    counts: Counter = Counter()
    for m in lstring:
        try:
            counts[m.name] += 1
        except AttributeError:
            pass
    # Deterministic from species.parameters.clump.tiller_count = 20.
    assert counts["Tiller"] == 20, f"expected 20 Tillers, got {counts['Tiller']}"
    assert counts["Crown"] == 20, f"expected 20 Crowns, got {counts['Crown']}"
    # 20 tillers x fraction_flowering=0.3 => expected ~6 panicles, +/- ~2 stddev.
    assert 3 <= counts["Panicle"] <= 9, (
        f"unexpected Panicle count: {counts['Panicle']}"
    )
    # 2-5 racemes per panicle => 6..45 total range across 3..9 panicles.
    assert 6 <= counts["Raceme"] <= 45, f"unexpected Raceme count: {counts['Raceme']}"
    # 4-7 leaves per tiller => 80..140 total.
    assert 80 <= counts["GrassLeaf"] <= 140, f"unexpected GrassLeaf count: {counts['GrassLeaf']}"


def test_andropogon_sidecar_material_distribution_at_peak(tmp_path: Path, andropogon_lpy_path: Path):
    """All four Andropogon material_ids should appear in the rendered sidecar."""
    lsys, lstring = derive(andropogon_lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / "matdist.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    mats = {e["material_id"] for e in sidecar["shapes"]}
    expected = {"culm_summer_green", "leaf_mature_green", "crown_dark", "panicle_bronze"}
    assert expected <= mats, f"missing materials: {expected - mats}"


# ---- CLI integration ----

@pytest.mark.parametrize("arch_dict", [_ECHINACEA_ARCH, _ANDROPOGON_ARCH], ids=["echinacea", "andropogon"])
def test_cli_generate_writes_file(arch_dict, tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "generated"
    result = runner.invoke(
        cli_main,
        ["generate", str(REPO / arch_dict["yaml"]), "--output", str(out), "--seed", "7"],
    )
    assert result.exit_code == 0, result.output
    expected = out / f"{arch_dict['filename_stem']}_seed_{Seed(7).canonical()}.lpy"
    assert expected.exists()
    assert "Wrote" in result.output


def test_cli_generate_accepts_string_seed(tmp_path: Path):
    """BOI-style shareable string seeds work end-to-end through the CLI."""
    runner = CliRunner()
    out = tmp_path / "generated"
    result = runner.invoke(
        cli_main,
        ["generate", str(REPO / _ECHINACEA_ARCH["yaml"]),
         "--output", str(out), "--seed", "XQF2-D6S1"],
    )
    assert result.exit_code == 0, result.output
    expected = out / "echinacea_purpurea_seed_XQF2D6S1.lpy"
    assert expected.exists()
    assert "XQF2-D6S1" in result.output


def test_cli_generate_rejects_invalid_yaml(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("scientific_name: x\n")  # missing many required fields
    runner = CliRunner()
    result = runner.invoke(cli_main, ["generate", str(bad), "--output", str(tmp_path)])
    assert result.exit_code != 0
    assert "INVALID YAML" in result.output


@pytest.mark.parametrize("arch_dict", [_ECHINACEA_ARCH, _ANDROPOGON_ARCH], ids=["echinacea", "andropogon"])
def test_cli_generate_rejects_unknown_material(arch_dict, tmp_path: Path):
    yaml_text = (REPO / arch_dict["yaml"]).read_text().replace(
        arch_dict["real_material_id"], "definitely_not_a_real_material_id"
    )
    p = tmp_path / "bad_material.yaml"
    p.write_text(yaml_text)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["generate", str(p), "--output", str(tmp_path)])
    assert result.exit_code != 0
    assert "definitely_not_a_real_material_id" in result.output
