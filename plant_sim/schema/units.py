"""Unit-system abstraction.

Length values in the species YAML are bare numbers. The species declares
a `units` block at the top of the YAML; the codegen converts those values
to the canonical internal unit (meters) when emitting the generated .lpy.

Built-in length units are provided. Contributors who need a unit not
covered here can either:
  (a) define a custom length unit inline in the species YAML
      (`units.length: {name: my_unit, meters_per_unit: 0.42}`), or
  (b) call `register_length_unit(...)` programmatically before validating.

Angles are always degrees in this project (design doc commitment).
Calendar dates are always day-of-year (DOY, 1-366). Neither is configurable.

Canonical internal length unit: METERS. The codegen normalizes every
length-tagged YAML value to meters before .lpy emission. Templates and
viewer work in meters. This decouples the contributor's preferred unit
system from the rendering pipeline and lets a single scene compose
specimens authored in different unit systems (Phase 3).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


# Built-in length unit name -> meters-per-unit conversion factor.
# Add to this table to extend permanently; for one-off custom units,
# use CustomLengthUnit inline in the YAML.
_BUILTIN_LENGTH_UNITS: dict[str, float] = {
    "m": 1.0,
    "cm": 0.01,
    "mm": 0.001,
    "in": 0.0254,
    "ft": 0.3048,
    "yd": 0.9144,
}


def register_length_unit(name: str, meters_per_unit: float) -> None:
    """Programmatic extension point for unit systems not covered above.

    Call this before loading a species YAML that references the new unit.
    """
    if meters_per_unit <= 0:
        raise ValueError(f"meters_per_unit must be > 0, got {meters_per_unit}")
    if name in _BUILTIN_LENGTH_UNITS:
        raise ValueError(f"length unit {name!r} is already registered")
    _BUILTIN_LENGTH_UNITS[name] = meters_per_unit


def known_length_units() -> list[str]:
    """List currently-registered length unit names."""
    return sorted(_BUILTIN_LENGTH_UNITS.keys())


class CustomLengthUnit(BaseModel):
    """Inline definition of a length unit the species YAML wants to use.

    Example:
        units:
          length:
            name: foo_units
            meters_per_unit: 0.42
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Display name for the unit.")
    meters_per_unit: float = Field(
        gt=0,
        description="Conversion factor: 1 unit = N meters. Must be > 0.",
    )


# A length-unit declaration is either a registered name string or an
# inline custom definition.
LengthUnitDecl = Annotated[
    str | CustomLengthUnit,
    Field(description="Length unit: a registered name (e.g. 'in', 'cm', 'm') or an inline {name, meters_per_unit} object."),
]


class UnitSystem(BaseModel):
    """Per-species unit declaration.

    Default is imperial inches, matching the USA-centric reference YAMLs
    in the design doc. Override per species.
    """

    model_config = ConfigDict(extra="forbid")

    length: LengthUnitDecl = Field(
        default="in",
        description="Length unit used for all length-typed fields in this species YAML.",
    )
    # Angle unit is always degrees; not currently configurable. Add if/when
    # we need radian-native species.
    angle: Literal["deg"] = "deg"
    # Calendar coordinate is always day-of-year.
    calendar: Literal["doy"] = "doy"

    def length_to_meters(self, value: float) -> float:
        """Convert a length value (in this system's length unit) to meters."""
        if isinstance(self.length, CustomLengthUnit):
            return value * self.length.meters_per_unit
        # Registered string name
        if self.length not in _BUILTIN_LENGTH_UNITS:
            raise ValueError(
                f"Unknown length unit {self.length!r}. "
                f"Known units: {known_length_units()}. "
                f"Either use a registered name, define an inline custom unit, "
                f"or call register_length_unit() before loading."
            )
        return value * _BUILTIN_LENGTH_UNITS[self.length]

    def length_range_to_meters(self, lo_hi: tuple[float, float]) -> tuple[float, float]:
        """Convenience: convert a (lo, hi) length range to (lo_m, hi_m)."""
        lo, hi = lo_hi
        return self.length_to_meters(lo), self.length_to_meters(hi)
