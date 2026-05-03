"""Pydantic models for the materials/library.json shape.

The viewer reads this library at runtime; the codegen validator cross-checks
that species YAMLs reference only existing material_ids. This schema lets
the test suite catch malformed library edits before they cause render-time
mysteries.

A material entry is one of:
  - Static: `color: "#hex"` (constant across the season)
  - Phenological: `color_curve: [{doy, color}, ...]` (linear-interpolated by DOY)

Each entry also carries roughness, metalness, and side (for three.js).
The `type` field is reserved for future material types (currently only
MeshStandardMaterial is supported).
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Six-digit hex color, e.g. "#3a6b40"
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class ColorKeyframe(BaseModel):
    """One entry in a phenological color curve."""

    model_config = ConfigDict(extra="forbid")

    doy: int = Field(ge=1, le=366, description="Day-of-year for this keyframe.")
    color: HexColor = Field(description="6-digit hex color (e.g. '#3a6b40').")


class MaterialEntry(BaseModel):
    """One material in the library JSON.

    Exactly one of `color` or `color_curve` must be provided. The renderer
    evaluates `color_curve` by linear interpolation between adjacent DOY
    keyframes; T_RENDER values outside the curve clamp to the nearest end.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["MeshStandardMaterial"] = Field(
        default="MeshStandardMaterial",
        description="three.js material class name. Currently only MeshStandardMaterial is supported.",
    )
    color: HexColor | None = Field(
        default=None,
        description="Static 6-digit hex color (constant across the season).",
    )
    color_curve: list[ColorKeyframe] | None = Field(
        default=None,
        description="DOY-keyed color keyframes; linear interpolation between adjacent entries.",
    )
    roughness: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="three.js roughness, 0=smooth/shiny to 1=rough/matte.",
    )
    metalness: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="three.js metalness, 0=non-metal to 1=metal.",
    )
    side: Literal["FrontSide", "BackSide", "DoubleSide"] = Field(
        default="DoubleSide",
        description="three.js Side enum string. Use DoubleSide for thin organs (leaves, petals) so back faces render.",
    )

    @model_validator(mode="after")
    def exactly_one_color_source(self) -> "MaterialEntry":
        if self.color is None and self.color_curve is None:
            raise ValueError("material entry must provide either `color` or `color_curve`")
        if self.color is not None and self.color_curve is not None:
            raise ValueError("material entry cannot have both `color` and `color_curve` (pick one)")
        if self.color_curve is not None:
            if len(self.color_curve) < 2:
                raise ValueError("color_curve needs at least 2 keyframes")
            doys = [kf.doy for kf in self.color_curve]
            if doys != sorted(doys):
                raise ValueError(f"color_curve keyframes must be sorted by doy (got {doys})")
        return self


class MaterialLibrary(BaseModel):
    """The whole materials/library.json document."""

    model_config = ConfigDict(extra="forbid")

    entries: dict[str, MaterialEntry]

    @classmethod
    def from_json_file(cls, path) -> "MaterialLibrary":
        import json
        from pathlib import Path
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # Top level is a {id: entry-dict} map; wrap as {entries: ...}
        return cls.model_validate({"entries": data})
