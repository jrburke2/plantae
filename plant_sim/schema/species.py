"""Pydantic v2 models for the species YAML contract.

Field-naming conventions:
- snake_case throughout
- plurals for collections (`leaf_count_range`)
- `_deg` suffix for angles (always degrees in this project)
- `_doy` suffix for calendar coordinates (day-of-year, 1-366)
- NO unit suffix on length fields. The unit is configurable per species
  via the top-level `units:` block (see `units.py`).

Defaults follow design doc Section 5: organ-level modules default
`queryable=True` (so they survive as queryable markers in the lstring),
internal dispatchers default `False` (consumed by L-Py rewriting).

The `parameters` block is dispatched on `archetype` via a `mode="before"`
model validator: the YAML's parameters dict is coerced to the right
RosetteScapeCompositeParameters / TillerClumpParameters subclass before
the rest of the species fields validate.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from plant_sim.schema.units import UnitSystem


# === Enums ===

class GrowthForm(str, Enum):
    herbaceous_perennial = "herbaceous_perennial"
    perennial_grass = "perennial_grass"
    annual = "annual"
    biennial = "biennial"
    shrub = "shrub"
    tree = "tree"
    vine = "vine"


class Phyllotaxis(str, Enum):
    spiral = "spiral"
    distichous = "distichous"
    opposite = "opposite"
    whorled = "whorled"


ArchetypeName = Literal["rosette_scape_composite", "tiller_clump"]


class MaterialForm(str, Enum):
    """Plant material form for procurement. Canonical enum; F43."""
    seed = "seed"
    plug = "plug"
    container_1gal = "container_1gal"
    container_3gal = "container_3gal"
    bare_root = "bare_root"
    bnb = "B&B"
    bulb_corm_rhizome = "bulb_corm_rhizome"
    cutting = "cutting"


class GradeTag(str, Enum):
    """Use-case grade per species. F44."""
    restoration_grade = "restoration_grade"
    ornamental_grade = "ornamental_grade"


# === Reusable range types ===

def _range_check(v: tuple, *, allow_equal: bool) -> tuple:
    if len(v) != 2:
        raise ValueError(f"range must be a 2-element [min, max], got {len(v)} elements")
    lo, hi = v
    if allow_equal:
        if lo > hi:
            raise ValueError(f"range min ({lo}) must be <= max ({hi})")
    else:
        if lo >= hi:
            raise ValueError(
                f"range min ({lo}) must be < max ({hi}); use a single value or widen the range"
            )
    return v


def _strict_range(v: tuple) -> tuple:
    return _range_check(v, allow_equal=False)


def _inclusive_range(v: tuple) -> tuple:
    return _range_check(v, allow_equal=True)


def _lat_range(v: tuple) -> tuple:
    lo, hi = _inclusive_range(v)
    if lo < -90.0 or hi > 90.0:
        raise ValueError(f"latitude range must be within [-90, 90], got [{lo}, {hi}]")
    return v


def _lon_range(v: tuple) -> tuple:
    lo, hi = _inclusive_range(v)
    if lo < -180.0 or hi > 180.0:
        raise ValueError(f"longitude range must be within [-180, 180], got [{lo}, {hi}]")
    return v


IntRangeStrict = Annotated[tuple[int, int], AfterValidator(_strict_range)]
IntRangeInclusive = Annotated[tuple[int, int], AfterValidator(_inclusive_range)]
FloatRangeInclusive = Annotated[tuple[float, float], AfterValidator(_inclusive_range)]
LatRange = Annotated[tuple[float, float], AfterValidator(_lat_range)]
LonRange = Annotated[tuple[float, float], AfterValidator(_lon_range)]


# === Plant material form metadata (F43) ===

class MaterialMeta(BaseModel):
    """Plant material form metadata per species (F43)."""

    model_config = ConfigDict(extra="forbid")

    allowed_forms: list[MaterialForm] = Field(
        min_length=1,
        description="Material forms this species supports (e.g. seed, plug, container_1gal). At least one.",
    )
    default_form: MaterialForm = Field(
        description="Default form for BOM rows. Must be one of allowed_forms.",
    )

    @model_validator(mode="after")
    def default_in_allowed(self) -> MaterialMeta:
        if self.default_form not in self.allowed_forms:
            raise ValueError(
                f"default_form {self.default_form.value!r} must be one of allowed_forms "
                f"({[f.value for f in self.allowed_forms]})"
            )
        return self


# === Provenance (F45) ===

class OriginRange(BaseModel):
    """Lat/lon bounding box for a species' native origin."""

    model_config = ConfigDict(extra="forbid")

    lat: LatRange = Field(description="Latitude range [min, max] in WGS84 degrees, -90..90.")
    lon: LonRange = Field(description="Longitude range [min, max] in WGS84 degrees, -180..180.")


class Provenance(BaseModel):
    """Provenance attribute for ecotype-aware procurement (F45)."""

    model_config = ConfigDict(extra="forbid")

    ecoregion: str = Field(
        min_length=1,
        description="Ecoregion code: Bailey or EPA Level III/IV (e.g. 'EPA_L3_54').",
    )
    origin_range: OriginRange | None = Field(
        default=None,
        description="Optional lat/lon bounding box of the species' native origin range.",
    )


# === Common header components ===

class Habitat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: list[str] = Field(
        min_length=1,
        description="Primary habitat associations (e.g. mesic_prairie, oak_savanna). At least one required.",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="Optional secondary habitat associations.",
    )
    cc_value: int = Field(
        ge=0, le=10,
        description="Coefficient of Conservatism, 0-10 (Wilhelm 2017). Higher = more conservative / habitat-specialist.",
    )


class Phenology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leaf_flush_doy: int = Field(
        ge=1, le=366,
        description="Day-of-year when leaves emerge (post-dormancy).",
    )
    peak_doy: int = Field(
        ge=1, le=366,
        description="Day-of-year of peak vegetative growth.",
    )
    senescence_onset_doy: int = Field(
        ge=1, le=366,
        description="Day-of-year when senescence begins (color change, leaf decline).",
    )
    abscission_doy: int = Field(
        ge=1, le=366,
        description="Day-of-year when leaves drop / above-ground biomass dies back.",
    )

    inflorescence_emerge_doy: int | None = Field(
        default=None, ge=1, le=366,
        description="Day-of-year when inflorescence first appears. Optional for non-flowering archetypes.",
    )
    inflorescence_peak_doy: int | None = Field(
        default=None, ge=1, le=366,
        description="Day-of-year of peak bloom. Optional.",
    )
    inflorescence_senescence_doy: int | None = Field(
        default=None, ge=1, le=366,
        description="Day-of-year when bloom ends. Optional.",
    )
    inflorescence_persist_winter: bool = Field(
        default=False,
        description="True if dried inflorescence remains visible into winter (e.g. Echinacea cones).",
    )
    culm_persist_winter: bool = Field(
        default=False,
        description="True if grass culm/stem remains standing into winter (e.g. Andropogon, Sorghastrum).",
    )
    fruit_persist: bool = Field(
        default=False,
        description="True if fruits remain on the plant beyond seed dispersal.",
    )

    @model_validator(mode="after")
    def check_ordering(self) -> Phenology:
        chain = (
            ("leaf_flush_doy", self.leaf_flush_doy),
            ("peak_doy", self.peak_doy),
            ("senescence_onset_doy", self.senescence_onset_doy),
            ("abscission_doy", self.abscission_doy),
        )
        for (na, va), (nb, vb) in zip(chain, chain[1:]):
            if not va < vb:
                raise ValueError(
                    f"phenology DOY values must be strictly increasing: "
                    f"{na}={va} must be < {nb}={vb}"
                )

        infl = [
            ("inflorescence_emerge_doy", self.inflorescence_emerge_doy),
            ("inflorescence_peak_doy", self.inflorescence_peak_doy),
            ("inflorescence_senescence_doy", self.inflorescence_senescence_doy),
        ]
        if all(v is not None for _, v in infl):
            for (na, va), (nb, vb) in zip(infl, infl[1:]):
                if va > vb:  # type: ignore[operator]
                    raise ValueError(
                        f"inflorescence DOY values must be non-decreasing: "
                        f"{na}={va} must be <= {nb}={vb}"
                    )
        return self


# === rosette_scape_composite parameter blocks ===

class RosetteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leaf_count_range: IntRangeStrict = Field(
        description="Min and max number of basal leaves in the rosette. Stochastic per specimen.",
    )
    leaf_template: str = Field(
        default="lanceolate",
        description="Leaf shape template id (e.g. lanceolate, lanceolate_serrate, ovate).",
    )
    leaf_length_range: FloatRangeInclusive = Field(
        description="Min and max blade length in the species' declared length unit. Stochastic per specimen.",
    )
    petiole_length_range: FloatRangeInclusive | None = Field(
        default=None,
        description="Optional min and max petiole length in declared length units. Omit for sessile leaves.",
    )
    phyllotaxis: Phyllotaxis = Field(
        default=Phyllotaxis.spiral,
        description="Leaf arrangement: spiral, distichous (alternate 180), opposite, whorled.",
    )
    divergence_angle_deg: float = Field(
        default=137.5, ge=0, le=360,
        description="Phyllotaxy divergence angle in degrees. 137.5 = golden angle (most spirals).",
    )
    queryable: bool = Field(
        default=True,
        description="If true, codegen injects the persistent-marker pattern so RosetteLeaf modules survive in the lstring as queryable markers.",
    )
    material_id: str = Field(
        default="leaf_mature_default",
        description="Material library id used for rosette leaves. See materials/library.json.",
    )


class ScapeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count_range: IntRangeInclusive = Field(
        description="Min and max number of scapes per specimen.",
    )
    height_range: FloatRangeInclusive = Field(
        description="Min and max scape height in declared length units.",
    )
    branching: Literal["simple", "branched"] = Field(
        default="simple",
        description="Scape branching pattern.",
    )
    leaf_count_on_scape: IntRangeInclusive = Field(
        default=(0, 0),
        description="Min and max cauline leaves on scape (0 if scape is leafless).",
    )
    queryable: bool = Field(
        default=True,
        description="Persistent-marker pattern for Scape modules.",
    )
    material_id: str = Field(
        default="culm_summer_green",
        description="Material library id used for the scape stem.",
    )


class InflorescenceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["composite_head", "raceme", "panicle", "spike", "umbel", "corymb", "cyme"] = Field(
        default="composite_head",
        description="Inflorescence morphology category.",
    )
    diameter: FloatRangeInclusive = Field(
        description="Min and max inflorescence diameter in declared length units.",
    )
    ray_count_range: IntRangeStrict = Field(
        description="Min and max number of ray florets (composite heads).",
    )
    ray_droop: bool = Field(
        default=False,
        description="True if ray florets droop downward (e.g. Echinacea, Rudbeckia).",
    )
    queryable: bool = Field(
        default=True,
        description="Persistent-marker pattern for Inflorescence modules.",
    )
    ray_material_id: str = Field(
        default="ray_floret_default",
        description="Material library id for ray florets.",
    )
    disk_material_id: str = Field(
        default="disk_floret_default",
        description="Material library id for the central disk.",
    )


class RosetteScapeCompositeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rosette: RosetteParams
    scape: ScapeParams
    inflorescence: InflorescenceParams


# === tiller_clump parameter blocks ===

class ClumpParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tiller_count: int = Field(
        ge=1,
        description="Mature tiller count in the clump.",
    )
    tiller_height_range: FloatRangeInclusive = Field(
        description="Min and max flowering-tiller height in declared length units.",
    )
    fraction_flowering: float = Field(
        ge=0, le=1,
        description="Fraction of tillers that flower (0..1). Andropogon mature: ~0.3.",
    )
    vegetative_height_fraction: float = Field(
        default=0.6, ge=0, le=1,
        description="Vegetative tiller height as a fraction of flowering tiller height.",
    )
    queryable: bool = Field(
        default=True,
        description="Persistent-marker pattern for the Clump module.",
    )


class TillerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leaf_count_range: IntRangeInclusive = Field(
        description="Min and max leaves per tiller. Stochastic per tiller.",
    )
    phyllotaxy_deg: float = Field(
        default=180.0, ge=0, le=360,
        description="Distichous grasses: 180. Spiral: 137.5.",
    )
    queryable: bool = Field(
        default=True,
        description="Persistent-marker pattern for Tiller modules so each is queryable.",
    )
    leaf_material_id: str = Field(
        default="leaf_mature_default",
        description="Material library id for grass blades.",
    )
    culm_material_id: str = Field(
        default="culm_summer_green",
        description="Material library id for the culm.",
    )


class PanicleParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raceme_count_range: IntRangeInclusive = Field(
        description="Min and max racemes per panicle ('turkey foot' for Andropogon: 2-5).",
    )
    raceme_length: float = Field(
        gt=0,
        description="Raceme length in declared length units.",
    )
    raceme_divergence_deg: float = Field(
        default=35.0, ge=0, le=180,
        description="Angle from culm vertical at which racemes diverge.",
    )
    queryable: bool = Field(
        default=True,
        description="Persistent-marker pattern for Panicle modules.",
    )
    material_id: str = Field(
        default="panicle_default",
        description="Material library id for the panicle.",
    )


class TillerClumpParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clump: ClumpParams
    tiller: TillerParams
    panicle: PanicleParams


# === Top-level Species ===

ArchetypeParameters = RosetteScapeCompositeParameters | TillerClumpParameters

_ARCHETYPE_TO_PARAMS: dict[str, type[BaseModel]] = {
    "rosette_scape_composite": RosetteScapeCompositeParameters,
    "tiller_clump": TillerClumpParameters,
}


class Species(BaseModel):
    """A single species archetype + parameters. The contributor surface."""

    model_config = ConfigDict(extra="forbid")

    scientific_name: str = Field(
        min_length=1,
        description="Binomial scientific name (e.g. 'Echinacea purpurea').",
    )
    common_name: str = Field(
        min_length=1,
        description="Vernacular common name.",
    )
    family: str = Field(
        min_length=1,
        description="Botanical family (e.g. Asteraceae, Poaceae).",
    )
    archetype: ArchetypeName = Field(
        description=(
            "Morphological archetype that selects the .lpy template. "
            "Phase 0 supports: rosette_scape_composite, tiller_clump."
        ),
    )
    growth_form: GrowthForm = Field(
        description="High-level growth-form category.",
    )

    units: UnitSystem = Field(
        default_factory=UnitSystem,
        description="Unit system for length values in this YAML. Default: imperial inches.",
    )

    height_range: FloatRangeInclusive = Field(
        description="Mature plant height range in declared length units.",
    )
    crown_width: FloatRangeInclusive = Field(
        description="Mature crown width range in declared length units.",
    )
    habitat: Habitat
    references: list[str] = Field(
        min_length=1,
        description="Bibliographic references supporting the parameter values.",
    )
    phenology: Phenology
    parameters: ArchetypeParameters = Field(
        description="Archetype-specific parameter block. Schema dispatched on `archetype`.",
    )

    material: MaterialMeta = Field(
        description="Plant material form metadata (allowed forms + default form). F43.",
    )
    grade: list[GradeTag] = Field(
        min_length=1,
        description="Use-case grade(s): restoration_grade, ornamental_grade, or both. F44.",
    )
    provenance: Provenance = Field(
        description="Provenance: ecoregion code plus optional origin lat/lon range. F45.",
    )

    template_override: str | None = Field(
        default=None,
        description=(
            "Optional escape hatch: relative path to a custom .lpy.j2 template "
            "to use instead of the archetype default. Use only when the standard "
            "archetype template doesn't fit. Most species leave this null."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def dispatch_parameters(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        archetype = data.get("archetype")
        params = data.get("parameters")
        if archetype in _ARCHETYPE_TO_PARAMS and isinstance(params, dict):
            params_cls = _ARCHETYPE_TO_PARAMS[archetype]
            data["parameters"] = params_cls.model_validate(params)
        return data

    @classmethod
    def from_yaml(cls, path: Path | str) -> Species:
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
