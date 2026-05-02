"""Reusable seed-mix definitions (F57).

Mixes are commercial restoration products: a named bundle of multiple
species at specified weight percentages. Plantae uses them as first-class
artifacts on the scene side (referenced by name in scene YAML) and emits
mix rows in the BOM (parent metadata + per-species components).

Mix YAML lives at `mixes/<mix_name>.yaml`. The `name` field must match
the filename stem.

This module defines the schema-level shape and validators (weights sum
to 100, components unique, name matches filename). Cross-checks against
the species library (component species exist, each has `seed` in
allowed_forms, grade compatibility) live in a future cross-check
function alongside the BOM emitter.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from plant_sim.schema.species import GradeTag


# weight_pct sum must be within this of 100 (float tolerance)
_WEIGHT_PCT_TOLERANCE = 0.01


class MixComponent(BaseModel):
    """One species line item in a mix."""

    model_config = ConfigDict(extra="forbid")

    species: str = Field(
        min_length=1,
        description="Species canonical name (e.g. 'andropogon_gerardii') matching a file in species/.",
    )
    weight_pct: float = Field(
        gt=0, le=100,
        description="This species' share of the mix total by weight, in percent (0-100].",
    )


class Mix(BaseModel):
    """Seed-mix definition — a reusable commercial bundle of multiple species (F57)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        description="Slug-form mix id; must match the YAML filename stem (e.g. 'tallgrass_prairie_mix').",
    )
    display_name: str = Field(
        min_length=1,
        description="Human-readable mix name (e.g. 'Tallgrass Prairie Mix').",
    )
    description: str = Field(
        default="",
        description="Optional free-text description of the mix's intended use.",
    )
    grade: GradeTag = Field(
        description="Use-case grade for the mix. Components must each include this grade.",
    )
    components: list[MixComponent] = Field(
        min_length=2,
        description="Two or more species components; weight_pct values must sum to 100 (within tolerance).",
    )

    @model_validator(mode="after")
    def weights_sum_to_100(self) -> Mix:
        total = sum(c.weight_pct for c in self.components)
        if abs(total - 100.0) > _WEIGHT_PCT_TOLERANCE:
            raise ValueError(
                f"mix component weight_pct values must sum to 100, got {total:.4f}"
            )
        return self

    @model_validator(mode="after")
    def components_unique_species(self) -> Mix:
        seen: set[str] = set()
        for c in self.components:
            if c.species in seen:
                raise ValueError(f"duplicate species in mix: {c.species!r}")
            seen.add(c.species)
        return self

    @classmethod
    def from_yaml(cls, path: Path | str) -> Mix:
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        mix = cls.model_validate(data)
        expected = path.stem
        if mix.name != expected:
            raise ValueError(
                f"mix name {mix.name!r} does not match filename stem {expected!r}"
            )
        return mix
