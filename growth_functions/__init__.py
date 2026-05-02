"""Shared growth and phenology functions for L-Py templates.

Generated .lpy files import from this module:

    from growth_functions import sigmoid_grow, alpha_at, seasonal_color, draw_growth_days

The module is on PYTHONPATH after `pip install -e .`. L-Py's `Lsystem(...)`
runs the .lpy as Python so this import works inside L-Py productions and
interpretation rules.

Phase 0 keeps growth windows as scalar constants hardcoded in archetype
templates. Phase 1 may add per-species YAML knobs (mean, stddev) and
stochastic per-instance draws via `draw_growth_days(rng, ...)`. The hook
exists so the template signature can stay stable while the source of
the value evolves.
"""

from __future__ import annotations

import math
import random

__all__ = [
    "sigmoid_grow",
    "alpha_at",
    "seasonal_color",
    "draw_growth_days",
]


def sigmoid_grow(age: float, growth_days: float, max_value: float) -> float:
    """Sigmoidal growth from 0 to max_value over `growth_days`.

    age <= 0           -> 0.0     (not yet started)
    age >= growth_days -> max_value (fully grown)
    in between         -> logistic curve, midpoint at growth_days/2

    Validated empirically by Echinacea + Andropogon spikes.
    """
    if age <= 0:
        return 0.0
    if age >= growth_days:
        return max_value
    x = (age / growth_days) * 12.0 - 6.0
    return max_value / (1.0 + math.exp(-x))


def alpha_at(age: float, lifespan: float, senescence_window: float = 10.0) -> float:
    """Module visibility ramp: 1.0 during life, ramping to 0 over the senescence window.

    age < 0 or age > lifespan -> 0.0  (not visible)
    age in [0, lifespan - senescence_window] -> 1.0
    age in [lifespan - senescence_window, lifespan] -> linear ramp to 0

    Use to fade out leaves during fall senescence.
    """
    if age < 0 or age > lifespan:
        return 0.0
    if age < lifespan - senescence_window:
        return 1.0
    return (lifespan - age) / senescence_window


def seasonal_color(t_render_doy: float, phenology: dict, palette: dict) -> str:
    """Pick a hex color for the current calendar day from a phenology-keyed palette.

    Phase 0 stub: returns the palette's `default` entry. Phase 1+ implements
    keyframed color curves driven by phenology DOY transitions.

    Args:
        t_render_doy: current day-of-year, 1..366.
        phenology: dict of phenology DOY thresholds (e.g. {leaf_flush_doy: 105, ...}).
        palette: material color curve. Phase 0 expects {"default": "#hexstring"}.
    """
    return palette.get("default", "#888888")


# === Extension hook for Phase 1: stochastic growth windows ===
#
# Phase 0 templates use scalar `LEAF_GROWTH_DAYS = 14`. Phase 1 may pass a
# distribution spec (e.g. {"mean": 14, "stddev": 2}) per species; per-instance
# draws happen at production firing via this helper, baking the drawn value
# into the module's parameters where it persists across interpretation passes.

def draw_growth_days(
    rng: random.Random | None,
    mean: float,
    stddev: float = 0.0,
    minimum: float = 0.5,
) -> float:
    """Draw a stochastic growth-window value.

    Phase 0 callers pass stddev=0 -> deterministic constant.
    Phase 1+ callers pass non-zero stddev for per-instance variation.
    The per-specimen rng must be seeded by the caller via `random.seed(SPECIMEN_SEED)`
    so draws are reproducible.

    Args:
        rng: random.Random instance, or None to use the module-level random.
        mean: mean growth-window length in days.
        stddev: standard deviation. 0 = deterministic.
        minimum: floor on the returned value (avoid negative or zero growth windows).
    """
    if stddev <= 0:
        return mean
    r = rng if rng is not None else random
    return max(minimum, r.gauss(mean, stddev))
