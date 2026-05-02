"""Scene schema tests (F36, F40-F42)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from plant_sim.schema.scene import (
    AutoFillSpec,
    Boundary,
    GeoJSONMultiPolygon,
    GeoJSONPolygon,
    KeySpecimen,
    MixEntry,
    Scene,
    SpeciesEntry,
    project_to_local_meters,
)
from plant_sim.schema.species import MaterialForm

REPO = Path(__file__).resolve().parent.parent
SCENES = REPO / "scenes"


# ---- Happy path: demo scene loads ----

def test_demo_scene_loads():
    s = Scene.from_yaml(SCENES / "prairie_demo.yaml")
    assert s.name == "prairie_demo"
    assert s.scene_seed is not None
    assert s.scene_seed.canonical() == "PRAR1234"
    assert s.boundary.coord_system == "local_meters"
    assert len(s.species_mix) == 2
    assert isinstance(s.species_mix[0], MixEntry)
    assert isinstance(s.species_mix[1], SpeciesEntry)
    assert len(s.key_specimens) == 1
    assert s.auto_fill.algorithm == "poisson_disk"


def test_scene_seed_optional():
    """scene_seed is optional; runtime derives from name when omitted."""
    s = _minimal_scene_dict()
    s.pop("scene_seed", None)
    scene = Scene.model_validate(s)
    assert scene.scene_seed is None


# ---- Boundary geometry ----

def test_polygon_geometry_loads():
    boundary = Boundary(
        coord_system="local_meters",
        geometry=GeoJSONPolygon(
            type="Polygon",
            coordinates=[[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]],
        ),
    )
    assert boundary.coord_system == "local_meters"


def test_multipolygon_geometry_loads():
    boundary = Boundary(
        coord_system="local_meters",
        geometry=GeoJSONMultiPolygon(
            type="MultiPolygon",
            coordinates=[
                [[(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]],
                [[(10, 10), (15, 10), (15, 15), (10, 15), (10, 10)]],
            ],
        ),
    )
    assert isinstance(boundary.geometry, GeoJSONMultiPolygon)
    assert len(boundary.geometry.coordinates) == 2


def test_polygon_with_hole():
    """Outer ring + interior hole (e.g. parking-lot island in a prairie remnant)."""
    poly = GeoJSONPolygon(
        type="Polygon",
        coordinates=[
            [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)],     # outer
            [(40, 40), (60, 40), (60, 60), (40, 60), (40, 40)],   # hole
        ],
    )
    assert len(poly.coordinates) == 2


def test_polygon_unclosed_ring_rejected():
    with pytest.raises(ValidationError, match="must be closed"):
        GeoJSONPolygon(
            type="Polygon",
            coordinates=[[(0, 0), (10, 0), (10, 10), (0, 10)]],   # missing closing point
        )


def test_polygon_too_few_points_rejected():
    with pytest.raises(ValidationError, match="at least 4 points"):
        GeoJSONPolygon(
            type="Polygon",
            coordinates=[[(0, 0), (10, 10), (0, 0)]],   # 3 points = degenerate
        )


@pytest.mark.parametrize("coord", [
    (200.0, 41.5),     # lon > 180
    (-200.0, 41.5),    # lon < -180
    (-90.0, 91.0),     # lat > 90
    (-90.0, -91.0),    # lat < -90
])
def test_geographic_coords_out_of_bounds_rejected(coord):
    with pytest.raises(ValidationError, match=r"(longitude|latitude) out of"):
        Boundary(
            coord_system="geographic",
            geometry=GeoJSONPolygon(
                type="Polygon",
                coordinates=[[coord, (0, 0), (10, 10), coord]],
            ),
        )


# ---- species_mix entries ----

def test_species_entry_alone_valid():
    e = SpeciesEntry(species="andropogon_gerardii", density_per_m2=4)
    assert e.species == "andropogon_gerardii"
    assert e.form is None


def test_species_entry_with_form_override():
    e = SpeciesEntry(species="echinacea_purpurea", density_per_m2=2, form=MaterialForm.plug)
    assert e.form == MaterialForm.plug


def test_mix_entry_alone_valid():
    e = MixEntry(mix="restoration_demo_mix", application_rate={"value": 8, "unit": "lb_PLS_per_acre"})
    assert e.mix == "restoration_demo_mix"
    assert e.application_rate.value == 8


def test_entry_with_both_species_and_mix_rejected():
    """species_mix entries are discriminated; entries with both keys fail both candidates."""
    s = _minimal_scene_dict()
    s["species_mix"] = [{
        "species": "andropogon_gerardii",
        "density_per_m2": 4,
        "mix": "x",
        "application_rate": {"value": 1, "unit": "lb_PLS_per_acre"},
    }]
    with pytest.raises(ValidationError):
        Scene.model_validate(s)


def test_species_mix_empty_rejected():
    s = _minimal_scene_dict()
    s["species_mix"] = []
    with pytest.raises(ValidationError):
        Scene.model_validate(s)


def test_total_density_over_hard_cap_rejected():
    s = _minimal_scene_dict()
    # Two species at 60/m² each = 120/m² total > 100 cap
    s["species_mix"] = [
        {"species": "a", "density_per_m2": 60},
        {"species": "b", "density_per_m2": 60},
    ]
    with pytest.raises(ValidationError, match="exceeds hard cap"):
        Scene.model_validate(s)


def test_density_per_m2_must_be_positive():
    with pytest.raises(ValidationError):
        SpeciesEntry(species="a", density_per_m2=0)
    with pytest.raises(ValidationError):
        SpeciesEntry(species="a", density_per_m2=-1)


# ---- Key specimens ----

def test_key_specimens_default_empty():
    s = _minimal_scene_dict()
    s.pop("key_specimens", None)
    scene = Scene.model_validate(s)
    assert scene.key_specimens == []


def test_key_specimen_with_seed_and_exclusion_radius():
    ks = KeySpecimen(
        species="quercus_alba",
        position=(10.0, 20.0),
        exclusion_radius_m=6.0,
        seed="OAKXY123",
    )
    assert ks.exclusion_radius_m == 6.0
    assert ks.seed is not None


def test_key_specimen_position_out_of_geographic_bounds_rejected():
    s = _minimal_scene_dict(coord_system="geographic")
    s["key_specimens"] = [{"species": "a", "position": (-91.0, 100.0)}]   # both out of range
    with pytest.raises(ValidationError, match=r"key specimen (longitude|latitude) out of"):
        Scene.model_validate(s)


# ---- Auto-fill ----

def test_auto_fill_defaults():
    spec = AutoFillSpec()
    assert spec.algorithm == "poisson_disk"


# ---- Projection helper ----

def test_project_to_local_meters_noop_for_local():
    b = Boundary(
        coord_system="local_meters",
        geometry=GeoJSONPolygon(
            type="Polygon",
            coordinates=[[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]],
        ),
    )
    out = project_to_local_meters(b)
    assert out is b   # same object — explicit no-op


def test_project_geographic_centroid_lands_at_origin():
    """After projection, the polygon centroid (mean of all coords) should be ~(0, 0)."""
    # 0.001° square centered around (-90, 41.5)
    b = Boundary(
        coord_system="geographic",
        geometry=GeoJSONPolygon(
            type="Polygon",
            coordinates=[[
                (-90.0005, 41.4995),
                (-89.9995, 41.4995),
                (-89.9995, 41.5005),
                (-90.0005, 41.5005),
                (-90.0005, 41.4995),
            ]],
        ),
    )
    out = project_to_local_meters(b)
    assert out.coord_system == "local_meters"
    assert isinstance(out.geometry, GeoJSONPolygon)

    # Centroid of projected coordinates
    coords = out.geometry.coordinates[0]
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    assert abs(cx) < 1e-6
    assert abs(cy) < 1e-6


def test_project_geographic_distances_match_flat_earth_math():
    """A 0.001° × 0.001° square at lat=41.5° should project to ~83 m × 111 m."""
    b = Boundary(
        coord_system="geographic",
        geometry=GeoJSONPolygon(
            type="Polygon",
            coordinates=[[
                (-90.0005, 41.4995),
                (-89.9995, 41.4995),
                (-89.9995, 41.5005),
                (-90.0005, 41.5005),
                (-90.0005, 41.4995),
            ]],
        ),
    )
    out = project_to_local_meters(b)
    assert isinstance(out.geometry, GeoJSONPolygon)
    coords = out.geometry.coordinates[0]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    width_m = max(xs) - min(xs)
    height_m = max(ys) - min(ys)

    expected_width = 0.001 * 111_320.0 * math.cos(math.radians(41.5))    # ~83.4 m
    expected_height = 0.001 * 111_320.0                                  # ~111.3 m
    assert width_m == pytest.approx(expected_width, rel=0.001)
    assert height_m == pytest.approx(expected_height, rel=0.001)


# ---- Helpers ----

def _minimal_scene_dict(*, coord_system: str = "local_meters") -> dict:
    """Build a minimal valid Scene dict that can be tweaked per-test."""
    if coord_system == "local_meters":
        coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    else:
        coords = [(-90.0, 41.5), (-89.99, 41.5), (-89.99, 41.51), (-90.0, 41.51), (-90.0, 41.5)]
    return {
        "name": "test",
        "scene_seed": "TESTSEED",
        "boundary": {
            "coord_system": coord_system,
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        },
        "species_mix": [{"species": "a", "density_per_m2": 1}],
    }
