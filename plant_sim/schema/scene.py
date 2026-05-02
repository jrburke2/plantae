"""Scene YAML schema (F36, F40-F42).

Codifies the rev-2 scene polygon resolution: GeoJSON-shaped Polygon or
MultiPolygon boundary with coord_system flag (geographic vs local_meters),
species_mix accepting both individual-species entries and mix references,
key-specimen pins, and auto-fill spec. Shape comes from
OPEN_QUESTIONS.md → "Scene polygon and key-specimen placement schema
(RESOLVED 2026-05-02)".

Scene cross-checks against the species library (every species_mix.species
and key_specimen.species must exist) live alongside the V2.2 scene
loader; this module owns shape validation only.

GeoJSON coordinate convention: arrays are [lon, lat] when coord_system
is geographic, [x_meters, y_meters] when local_meters.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Iterator, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from plant_sim.schema.seed import Seed
from plant_sim.schema.species import MaterialForm


# Hard cap: cumulative density across all per-species entries.
# Anything above this is almost certainly an authoring error.
_TOTAL_DENSITY_HARD_CAP_PER_M2 = 100.0


# === GeoJSON-shaped geometries ===

# A coordinate is [lon, lat] (geographic) or [x, y] meters (local_meters).
# Tuples after Pydantic validation; YAML accepts lists.
Coordinate = tuple[float, float]


class GeoJSONPolygon(BaseModel):
    """GeoJSON Polygon: outer ring + optional interior holes."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Polygon"]
    coordinates: list[list[Coordinate]] = Field(
        min_length=1,
        description="Rings as [[[c, c], ...], ...]; first is exterior, rest are holes.",
    )

    @model_validator(mode="after")
    def rings_well_formed(self) -> GeoJSONPolygon:
        for i, ring in enumerate(self.coordinates):
            if len(ring) < 4:
                raise ValueError(
                    f"polygon ring {i} must have at least 4 points (3 distinct + closing); got {len(ring)}"
                )
            if ring[0] != ring[-1]:
                raise ValueError(f"polygon ring {i} must be closed (first point == last point)")
        return self


class GeoJSONMultiPolygon(BaseModel):
    """GeoJSON MultiPolygon: list of polygons (each = outer + holes)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Coordinate]]] = Field(
        min_length=1,
        description="List of polygons; each polygon is a list of rings (outer + holes).",
    )

    @model_validator(mode="after")
    def all_rings_well_formed(self) -> GeoJSONMultiPolygon:
        for pi, poly in enumerate(self.coordinates):
            if not poly:
                raise ValueError(f"multipolygon entry {pi} has no rings")
            for ri, ring in enumerate(poly):
                if len(ring) < 4:
                    raise ValueError(
                        f"multipolygon[{pi}] ring {ri} must have at least 4 points; got {len(ring)}"
                    )
                if ring[0] != ring[-1]:
                    raise ValueError(
                        f"multipolygon[{pi}] ring {ri} must be closed (first point == last point)"
                    )
        return self


Geometry = Annotated[
    GeoJSONPolygon | GeoJSONMultiPolygon,
    Field(discriminator="type"),
]


def _iter_all_coords(geometry: GeoJSONPolygon | GeoJSONMultiPolygon) -> Iterator[Coordinate]:
    if isinstance(geometry, GeoJSONPolygon):
        for ring in geometry.coordinates:
            yield from ring
    else:
        for poly in geometry.coordinates:
            for ring in poly:
                yield from ring


# === Boundary ===

class Boundary(BaseModel):
    """Scene boundary: coord_system flag + GeoJSON geometry."""

    model_config = ConfigDict(extra="forbid")

    coord_system: Literal["geographic", "local_meters"] = Field(
        description="Coordinate system: geographic (lon, lat in WGS84) or local_meters (x, y in meters).",
    )
    geometry: Geometry

    @model_validator(mode="after")
    def coords_in_bounds_for_coord_system(self) -> Boundary:
        if self.coord_system == "geographic":
            for lon, lat in _iter_all_coords(self.geometry):
                if not -180.0 <= lon <= 180.0:
                    raise ValueError(f"longitude out of [-180, 180]: {lon}")
                if not -90.0 <= lat <= 90.0:
                    raise ValueError(f"latitude out of [-90, 90]: {lat}")
        return self


# === species_mix entries (discriminated by presence of `species` vs `mix`) ===

class ApplicationRate(BaseModel):
    """Application rate for a mix entry (canonical: lb_PLS_per_acre)."""

    model_config = ConfigDict(extra="forbid")

    value: float = Field(gt=0)
    unit: Literal["lb_PLS_per_acre"] = "lb_PLS_per_acre"


class SpeciesEntry(BaseModel):
    """One species line in species_mix."""

    model_config = ConfigDict(extra="forbid")

    species: str = Field(min_length=1, description="Canonical species name (e.g. 'andropogon_gerardii').")
    density_per_m2: float = Field(
        gt=0, le=_TOTAL_DENSITY_HARD_CAP_PER_M2,
        description="Plants per square meter for this species.",
    )
    form: MaterialForm | None = Field(
        default=None,
        description="Optional form override; defaults to species.material.default_form.",
    )


class MixEntry(BaseModel):
    """One mix line in species_mix."""

    model_config = ConfigDict(extra="forbid")

    mix: str = Field(min_length=1, description="Mix name (matches mixes/<name>.yaml).")
    application_rate: ApplicationRate


SpeciesMixEntry = SpeciesEntry | MixEntry


# === Key specimens ===

class KeySpecimen(BaseModel):
    """Manual specimen pin within the scene boundary."""

    model_config = ConfigDict(extra="forbid")

    species: str = Field(min_length=1)
    position: Coordinate = Field(
        description="Position [lon, lat] (geographic) or [x, y] (local_meters); must match boundary.coord_system.",
    )
    exclusion_radius_m: float | None = Field(
        default=None, gt=0,
        description="Optional override; defaults to species.crown_width upper bound × 0.5.",
    )
    seed: Seed | None = Field(
        default=None,
        description="Optional pinned seed (BOI 8-char base32); defaults to derived from (scene_seed, species, quantized position).",
    )


# === Auto-fill spec ===

class AutoFillSpec(BaseModel):
    """Auto-fill placement algorithm config."""

    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["poisson_disk"] = Field(
        default="poisson_disk",
        description="Auto-fill algorithm; only Poisson disk is supported in V2.2.",
    )


# === Top-level Scene ===

class Scene(BaseModel):
    """Scene specification — the contributor surface for community rendering."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Slug-form scene id; should match the YAML filename stem.")
    description: str = ""

    scene_seed: Seed | None = Field(
        default=None,
        description="Optional 8-char Crockford base32 BOI-style seed; if omitted, runtime derives from name.",
    )

    boundary: Boundary
    species_mix: list[SpeciesMixEntry] = Field(min_length=1)
    key_specimens: list[KeySpecimen] = Field(default_factory=list)
    auto_fill: AutoFillSpec = Field(default_factory=AutoFillSpec)

    @model_validator(mode="after")
    def total_density_under_cap(self) -> Scene:
        total = sum(
            e.density_per_m2 for e in self.species_mix if isinstance(e, SpeciesEntry)
        )
        if total > _TOTAL_DENSITY_HARD_CAP_PER_M2:
            raise ValueError(
                f"total species density across species_mix is {total} plants/m², "
                f"which exceeds hard cap of {_TOTAL_DENSITY_HARD_CAP_PER_M2}; "
                f"likely an authoring error"
            )
        return self

    @model_validator(mode="after")
    def key_specimen_positions_in_coord_system(self) -> Scene:
        if self.boundary.coord_system == "geographic":
            for ks in self.key_specimens:
                lon, lat = ks.position
                if not -180.0 <= lon <= 180.0:
                    raise ValueError(f"key specimen longitude out of [-180, 180]: {lon}")
                if not -90.0 <= lat <= 90.0:
                    raise ValueError(f"key specimen latitude out of [-90, 90]: {lat}")
        return self

    @classmethod
    def from_yaml(cls, path: Path | str) -> Scene:
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# === Geographic → local-meters projection ===

# 1 degree latitude ≈ 111.32 km. Variation with latitude is well below 1%
# at restoration scale (<10 km), so a constant is fine.
_METERS_PER_DEG_LAT = 111_320.0


def project_to_local_meters(boundary: Boundary) -> Boundary:
    """Project a geographic-coord-system Boundary to local meters.

    Uses a flat-earth approximation: project around the polygon centroid
    (mean of all coordinate points) using cosine-of-latitude scaling for
    longitude. Accurate to <1% for scenes under ~10 km, per the seam S6
    decision. No-op when coord_system is already local_meters.
    """
    if boundary.coord_system == "local_meters":
        return boundary

    coords = list(_iter_all_coords(boundary.geometry))
    if not coords:
        raise ValueError("boundary has no coordinates to project")
    lon_c = sum(c[0] for c in coords) / len(coords)
    lat_c = sum(c[1] for c in coords) / len(coords)

    meters_per_deg_lon = _METERS_PER_DEG_LAT * math.cos(math.radians(lat_c))

    def _project(c: Coordinate) -> Coordinate:
        lon, lat = c
        return (
            (lon - lon_c) * meters_per_deg_lon,
            (lat - lat_c) * _METERS_PER_DEG_LAT,
        )

    if isinstance(boundary.geometry, GeoJSONPolygon):
        new_geometry: GeoJSONPolygon | GeoJSONMultiPolygon = GeoJSONPolygon(
            type="Polygon",
            coordinates=[[_project(c) for c in ring] for ring in boundary.geometry.coordinates],
        )
    else:
        new_geometry = GeoJSONMultiPolygon(
            type="MultiPolygon",
            coordinates=[
                [[_project(c) for c in ring] for ring in poly]
                for poly in boundary.geometry.coordinates
            ],
        )

    return Boundary(coord_system="local_meters", geometry=new_geometry)
