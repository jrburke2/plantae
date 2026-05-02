"""Step 8 tests: Andropogon (tiller_clump archetype) end-to-end through the
unchanged Phase 0 pipeline.

Mirrors test_codegen.py's Echinacea tests so a regression in either
archetype shows up in the same place.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from plant_sim.codegen.generator import (
    available_archetypes,
    dispatch_template,
    generate,
    write,
)
from plant_sim.codegen.validator import validate_lpy
from plant_sim.render.derive import derive
from plant_sim.render.export import export_to_obj_with_sidecar
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent
ANDROPOGON_YAML = REPO / "species" / "poaceae" / "andropogon_gerardii.yaml"


@pytest.fixture(scope="module")
def lpy_text() -> str:
    sp = Species.from_yaml(ANDROPOGON_YAML)
    return generate(sp, seed=42)


@pytest.fixture(scope="module")
def lpy_path(tmp_path_factory, lpy_text: str) -> Path:
    p = tmp_path_factory.mktemp("generated") / "andropogon_gerardii_seed_42.lpy"
    p.write_text(lpy_text)
    return p


# ---- Codegen ----

def test_archetype_registered():
    assert "tiller_clump" in available_archetypes()


def test_dispatch_picks_tiller_clump():
    sp = Species.from_yaml(ANDROPOGON_YAML)
    assert dispatch_template(sp).endswith("tiller_clump.lpy.j2")


def test_template_renders_without_error(lpy_text: str):
    assert "Axiom: Clump" in lpy_text
    assert "module Tiller(" in lpy_text
    assert "module Panicle(" in lpy_text
    assert "module CulmSegment(" in lpy_text  # the wrapper module added in Step 8
    assert 'LEAF_MAT = "leaf_mature_green"' in lpy_text
    assert 'PANICLE_MAT = "panicle_bronze"' in lpy_text


def test_generated_lpy_passes_static_validator(lpy_text: str):
    issues = validate_lpy(lpy_text, raise_on_error=False)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"validator caught issues in generated Andropogon: {errors}"


# ---- L-Py load + derive ----

def test_lpy_loads_and_derives(lpy_path: Path):
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    assert len(lstring) > 0


def test_module_census_matches_spike_2(lpy_path: Path):
    """Census from Spike 2 (Andropogon @ seed=42, mature):
    20 Tillers, 5 Panicles (one per flowering), ~17 Racemes, ~109 GrassLeaves.
    """
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    counts: Counter = Counter()
    for m in lstring:
        try:
            counts[m.name] += 1
        except AttributeError:
            pass

    assert counts["Tiller"] == 20, f"expected 20 Tillers, got {counts['Tiller']}"
    # Spike 2 with seed=42 produced 5 flowering tillers.
    assert counts["Panicle"] == 5, f"expected 5 Panicles, got {counts['Panicle']}"
    # 2-5 racemes per panicle => 10..25 total.
    assert 10 <= counts["Raceme"] <= 25, f"unexpected Raceme count: {counts['Raceme']}"
    # 4-7 leaves per tiller => 80..140 total.
    assert 80 <= counts["GrassLeaf"] <= 140, f"unexpected GrassLeaf count: {counts['GrassLeaf']}"
    # Crown: one per tiller.
    assert counts["Crown"] == 20, f"expected 20 Crowns, got {counts['Crown']}"


# ---- Render: scene shapes match exporter's renderable filter ----

def test_render_at_peak_succeeds(tmp_path: Path, lpy_path: Path):
    """The load-bearing test: the exporter must not raise ExportError."""
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / "andropogon.obj"
    out_obj, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    assert out_obj.exists() and out_sidecar.exists()


def test_render_pre_flush_is_empty(tmp_path: Path, lpy_path: Path):
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / "preflush.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 50.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    assert sidecar["meta"]["scene_shape_count"] == 0


def test_sidecar_material_distribution_at_peak(tmp_path: Path, lpy_path: Path):
    """All four Andropogon material_ids should appear in the rendered sidecar."""
    lsys, lstring = derive(lpy_path, RenderContext(seed=42))
    obj_path = tmp_path / "matdist.obj"
    _, out_sidecar = export_to_obj_with_sidecar(lsys, lstring, 250.0, obj_path)
    sidecar = json.loads(out_sidecar.read_text())
    mats = {e["material_id"] for e in sidecar["shapes"]}
    expected = {"culm_summer_green", "leaf_mature_green", "crown_dark", "panicle_bronze"}
    assert expected <= mats, f"missing materials: {expected - mats}"


def test_write_uses_content_addressed_filename(tmp_path: Path):
    """Filenames embed the canonical 8-char base32 seed (not raw int)."""
    from plant_sim.schema.seed import Seed
    sp = Species.from_yaml(ANDROPOGON_YAML)
    path = write(sp, output_dir=tmp_path, seed=4711)
    canonical = Seed(4711).canonical()
    assert path.name == f"andropogon_gerardii_seed_{canonical}.lpy"
    assert path.exists()
