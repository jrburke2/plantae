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
    GradeTag,
    MaterialForm,
    MaterialMeta,
    OriginRange,
    Provenance,
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

# Each row: (fixture, required_substrings). Tuple within means "any of these"
# (used for Pydantic version-portable error wording).
@pytest.mark.parametrize("fixture,required_substrings", [
    ("invalid_phenology_order.yaml",
     ["phenology doy values must be strictly increasing", "leaf_flush_doy"]),
    ("invalid_height_range_inverted.yaml",
     ["range min"]),
    ("invalid_missing_required.yaml",
     ["family", ("missing", "field required")]),
    ("invalid_unknown_archetype.yaml",
     ["archetype"]),
])
def test_invalid_fixture_rejected(fixture, required_substrings):
    with pytest.raises(ValidationError) as exc:
        Species.from_yaml(FIX / fixture)
    msg = str(exc.value).lower()
    for req in required_substrings:
        if isinstance(req, tuple):
            assert any(alt in msg for alt in req), f"none of {req} found in: {msg}"
        else:
            assert req in msg, f"{req!r} not found in: {msg}"


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


# ---- F43 / F44 / F45: material form, grade, provenance ----

def test_echinacea_material_grade_provenance_loaded():
    sp = Species.from_yaml(SPECIES / "asteraceae" / "echinacea_purpurea.yaml")
    assert MaterialForm.plug in sp.material.allowed_forms
    assert sp.material.default_form == MaterialForm.plug
    assert GradeTag.restoration_grade in sp.grade
    assert GradeTag.ornamental_grade in sp.grade
    assert sp.provenance.ecoregion == "EPA_L3_54"
    assert sp.provenance.origin_range is not None
    assert sp.provenance.origin_range.lat == (35.0, 45.0)


def test_andropogon_material_grade_provenance_loaded():
    sp = Species.from_yaml(SPECIES / "poaceae" / "andropogon_gerardii.yaml")
    assert sp.material.default_form == MaterialForm.seed
    assert sp.grade == [GradeTag.restoration_grade]
    assert sp.provenance.ecoregion == "EPA_L3_54"
    assert sp.provenance.origin_range is None        # demonstrates the optional case


def test_default_form_must_be_in_allowed_forms():
    with pytest.raises(ValidationError, match="default_form"):
        MaterialMeta(allowed_forms=[MaterialForm.seed], default_form=MaterialForm.plug)


def test_allowed_forms_must_be_non_empty():
    with pytest.raises(ValidationError):
        MaterialMeta(allowed_forms=[], default_form=MaterialForm.seed)


def test_grade_must_be_non_empty():
    with pytest.raises(ValidationError):
        # Build a valid Species kwargs by reading the canonical YAML and
        # zeroing out grade — easiest path through the existing field stack.
        import yaml as _yaml
        data = _yaml.safe_load((SPECIES / "asteraceae" / "echinacea_purpurea.yaml").read_text())
        data["grade"] = []
        Species.model_validate(data)


def test_provenance_origin_range_optional():
    p = Provenance(ecoregion="EPA_L3_54")
    assert p.origin_range is None


@pytest.mark.parametrize("kwargs", [
    {"lat": (-100.0, 0.0), "lon": (0.0, 10.0)},      # lat below -90
    {"lat": (0.0, 100.0), "lon": (0.0, 10.0)},       # lat above 90
    {"lat": (0.0, 10.0), "lon": (-200.0, 0.0)},      # lon below -180
    {"lat": (0.0, 10.0), "lon": (0.0, 200.0)},       # lon above 180
    {"lat": (10.0, 0.0), "lon": (0.0, 10.0)},        # lat min > max
    {"lat": (0.0, 10.0), "lon": (10.0, 0.0)},        # lon min > max
])
def test_origin_range_lat_lon_validation(kwargs):
    with pytest.raises(ValidationError):
        OriginRange(**kwargs)


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
