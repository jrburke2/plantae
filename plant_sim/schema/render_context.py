"""Per-render execution context.

A `RenderContext` parameterizes one render of one specimen. Phase 0 only
ever uses default values, but plumbing this through the codegen API now
saves a Phase 3 retrofit when the scene composer needs per-specimen
seeds, time offsets, and world positions.

The codegen passes these to the .lpy file via `extern(...)` parameters.
The template references them by name.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from plant_sim.schema.seed import Seed


class RenderContext(BaseModel):
    """Per-render parameters; defaults are correct for single-specimen Phase 0 use."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    seed: Seed = Field(
        default_factory=lambda: Seed(42),
        description=(
            "Specimen seed — 8-char Crockford base32 (e.g. 'XQF2-D6S1') or an "
            "integer for backward compat. Same species + same seed = bit-identical "
            "specimen. Shareable: paste a seed string into the viewer URL or "
            "another instance to reproduce the exact specimen."
        ),
    )
    time_offset_doy: float = Field(
        default=0.0,
        description="Calendar offset in days. A specimen established last spring vs this spring has a different time_offset.",
    )
    emergence_offset_days: float = Field(
        default=0.0,
        description=(
            "Per-specimen jitter around the species' median phenology DOYs. Drawn from "
            "random.gauss(0, jitter) by the codegen at axiom time. Phase 0 always 0; "
            "Phase 1+ reads `phenology.emergence_jitter_days` from species YAML."
        ),
    )
    position_x_m: float = Field(
        default=0.0,
        description="World x position in meters. Used by the scene composer; ignored for single-specimen renders.",
    )
    position_y_m: float = Field(
        default=0.0,
        description="World y position in meters (vertical / up axis per project convention).",
    )
    position_z_m: float = Field(
        default=0.0,
        description="World z position in meters.",
    )
