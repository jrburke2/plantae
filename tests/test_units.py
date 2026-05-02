"""Unit-system tests.

Verify that:
- Built-in length units convert to canonical meters correctly.
- A species declared in metric loads with values in its native unit but
  the unit-conversion helper returns meters consistently.
- Inline custom-unit definitions work.
- Unknown unit names produce clear errors.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from plant_sim.schema.species import Species
from plant_sim.schema.units import (
    CustomLengthUnit,
    UnitSystem,
    known_length_units,
)

FIX = Path(__file__).parent / "fixtures"


# ---- Built-in length units ----

def test_inches_to_meters():
    us = UnitSystem(length="in")
    assert us.length_to_meters(1.0) == pytest.approx(0.0254)
    assert us.length_to_meters(48.0) == pytest.approx(1.2192)


def test_centimeters_to_meters():
    us = UnitSystem(length="cm")
    assert us.length_to_meters(100.0) == pytest.approx(1.0)


def test_meters_passthrough():
    us = UnitSystem(length="m")
    assert us.length_to_meters(2.5) == 2.5


def test_feet_to_meters():
    us = UnitSystem(length="ft")
    assert us.length_to_meters(7.0) == pytest.approx(2.1336)


def test_known_units_listed():
    names = known_length_units()
    assert {"m", "cm", "mm", "in", "ft", "yd"} <= set(names)


# ---- Range-conversion helper ----

def test_length_range_conversion():
    us = UnitSystem(length="in")
    lo_m, hi_m = us.length_range_to_meters((24.0, 48.0))
    assert lo_m == pytest.approx(0.6096)
    assert hi_m == pytest.approx(1.2192)


# ---- Metric YAML loads with native values, converts cleanly ----

def test_metric_species_loads_with_native_values():
    sp = Species.from_yaml(FIX / "valid_echinacea_metric.yaml")
    # Native values stored as written (no premature conversion).
    assert sp.height_range == (61.0, 122.0)
    assert sp.parameters.rosette.leaf_length_range == (10.0, 20.0)
    # Conversion to canonical meters.
    lo_m, hi_m = sp.units.length_range_to_meters(sp.height_range)
    assert lo_m == pytest.approx(0.61)
    assert hi_m == pytest.approx(1.22)


def test_imperial_and_metric_yaml_yield_same_meters():
    """Same plant declared in two different unit systems should normalize to ~equal meters."""
    imp = Species.from_yaml(Path(__file__).resolve().parent.parent / "species/asteraceae/echinacea_purpurea.yaml")
    met = Species.from_yaml(FIX / "valid_echinacea_metric.yaml")

    imp_height_m = imp.units.length_range_to_meters(imp.height_range)
    met_height_m = met.units.length_range_to_meters(met.height_range)

    # 24 in = 0.6096 m vs metric YAML rounded at 61 cm = 0.61 m.
    # 48 in = 1.2192 m vs 122 cm = 1.22 m. Within rounding noise.
    assert math.isclose(imp_height_m[0], met_height_m[0], abs_tol=0.01)
    assert math.isclose(imp_height_m[1], met_height_m[1], abs_tol=0.01)


# ---- Inline custom unit ----

def test_inline_custom_unit():
    sp = Species.from_yaml(FIX / "valid_echinacea_custom_unit.yaml")
    assert isinstance(sp.units.length, CustomLengthUnit)
    assert sp.units.length.name == "hand"
    # 6 hands * 0.1016 m/hand = 0.6096 m (= 24 inches; matches imperial Echinacea)
    lo_m, hi_m = sp.units.length_range_to_meters(sp.height_range)
    assert lo_m == pytest.approx(0.6096)
    assert hi_m == pytest.approx(1.2192)


# ---- Unknown unit name produces a clear error ----

def test_unknown_unit_name_errors():
    us = UnitSystem(length="cubit")  # name validates as a string; conversion is lazy
    with pytest.raises(ValueError) as exc:
        us.length_to_meters(1.0)
    assert "Unknown length unit" in str(exc.value)
