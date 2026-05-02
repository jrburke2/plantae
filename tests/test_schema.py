"""Schema validation tests.

The two reference species YAMLs in `species/` are loaded directly. Failure
fixtures live in `tests/fixtures/` so changes to the canonical species don't
silently break the failure-path tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from plant_sim.schema.species import (
    RosetteScapeCompositeParameters,
    Species,
    TillerClumpParameters,
)

REPO = Path(__file__).resolve().parent.parent
SPECIES = REPO / "species"
FIX = Path(__file__).parent / "fixtures"


# ---- Happy path: the two canonical species load ----

def test_echinacea_loads():
    sp = Species.from_yaml(SPECIES / "asteraceae" / "echinacea_purpurea.yaml")
    assert sp.scientific_name == "Echinacea purpurea"
    assert sp.archetype == "rosette_scape_composite"
    assert isinstance(sp.parameters, RosetteScapeCompositeParameters)
    assert sp.parameters.rosette.leaf_count_range == (6, 14)
    assert sp.parameters.rosette.leaf_length_range == (4, 8)
    assert sp.parameters.inflorescence.ray_droop is True
    assert sp.phenology.inflorescence_persist_winter is True
    assert sp.units.length == "in"


def test_andropogon_loads():
    sp = Species.from_yaml(SPECIES / "poaceae" / "andropogon_gerardii.yaml")
    assert sp.scientific_name == "Andropogon gerardii"
    assert sp.archetype == "tiller_clump"
    assert isinstance(sp.parameters, TillerClumpParameters)
    assert sp.parameters.clump.tiller_count == 20
    assert sp.parameters.clump.fraction_flowering == 0.3
    assert sp.parameters.panicle.raceme_length == 4.0
    assert sp.phenology.culm_persist_winter is True


def test_rosette_defaults_applied():
    sp = Species.from_yaml(SPECIES / "asteraceae" / "echinacea_purpurea.yaml")
    assert sp.parameters.rosette.queryable is True  # design doc Section 5
    assert sp.parameters.scape.branching == "simple"
    assert sp.template_override is None


# ---- Failure modes produce specific errors ----

def test_phenology_out_of_order():
    with pytest.raises(ValidationError) as exc:
        Species.from_yaml(FIX / "invalid_phenology_order.yaml")
    msg = str(exc.value)
    assert "phenology DOY values must be strictly increasing" in msg
    assert "leaf_flush_doy" in msg


def test_height_range_inverted():
    with pytest.raises(ValidationError) as exc:
        Species.from_yaml(FIX / "invalid_height_range_inverted.yaml")
    assert "range min" in str(exc.value).lower()


def test_missing_required_field():
    with pytest.raises(ValidationError) as exc:
        Species.from_yaml(FIX / "invalid_missing_required.yaml")
    msg = str(exc.value)
    assert "family" in msg
    assert "missing" in msg.lower() or "field required" in msg.lower()


def test_unknown_archetype():
    with pytest.raises(ValidationError) as exc:
        Species.from_yaml(FIX / "invalid_unknown_archetype.yaml")
    assert "archetype" in str(exc.value).lower()


# ---- JSON Schema export contains field descriptions and archetype values ----

def test_json_schema_export_contains_descriptions_and_archetypes():
    schema = Species.model_json_schema()
    rendered = repr(schema)
    assert "rosette_scape_composite" in rendered
    assert "tiller_clump" in rendered
    assert "scientific_name" in rendered
    # Field descriptions should propagate (used by VS Code yaml-language-server)
    assert "Coefficient of Conservatism" in rendered
    assert "scape" in rendered.lower()


# ---- Escape-hatch field exists and accepts an override path ----

def test_template_override_accepts_path(tmp_path: Path):
    # Build a minimal valid YAML with a template_override set.
    src = (FIX / "invalid_missing_required.yaml").read_text().replace(
        "common_name: purple coneflower",
        "common_name: purple coneflower\nfamily: Asteraceae\ntemplate_override: templates/custom/foo.lpy.j2",
    )
    p = tmp_path / "custom.yaml"
    p.write_text(src)
    sp = Species.from_yaml(p)
    assert sp.template_override == "templates/custom/foo.lpy.j2"
