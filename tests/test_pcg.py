"""Tests for PCG-XSL-RR-128/64.

Bit-exact cross-language parity is gated separately by the JSON-vector
fixture and the Node parity test. These tests cover only the Python-side
contract: determinism, ranges, and the public API surface.
"""

from __future__ import annotations

import pytest

from plant_sim.runtime.pcg import (
    MASK32,
    MASK64,
    PCG64,
    PCG_DEFAULT_INCREMENT_128,
    PCG_DEFAULT_MULTIPLIER_128,
    seeded_rng,
)
from plant_sim.schema.seed import Seed


# ---- Determinism ----

def test_same_seed_same_sequence():
    a = seeded_rng(42)
    b = seeded_rng(42)
    assert [a.next_u64() for _ in range(100)] == [b.next_u64() for _ in range(100)]


def test_different_seeds_diverge():
    a = seeded_rng(42)
    b = seeded_rng(43)
    seq_a = [a.next_u64() for _ in range(100)]
    seq_b = [b.next_u64() for _ in range(100)]
    assert seq_a != seq_b
    # And the first draws should differ (not just somewhere down the line)
    assert seq_a[0] != seq_b[0]


def test_seed_accepts_seed_object():
    s = Seed("XQF2D6S1")
    a = seeded_rng(s)
    b = seeded_rng(s.to_int())
    assert [a.next_u64() for _ in range(10)] == [b.next_u64() for _ in range(10)]


def test_seed_zero_works():
    # Canonical pcg-cpp seeding mixes the state via two bumps, so seed=0 is
    # not a degenerate "all zero" stream.
    rng = seeded_rng(0)
    first = rng.next_u64()
    assert first != 0
    # And seed=0 differs from seed=1
    assert first != seeded_rng(1).next_u64()


# ---- Output-range invariants ----

def test_next_u64_is_64_bit():
    rng = seeded_rng(1234)
    for _ in range(1000):
        v = rng.next_u64()
        assert 0 <= v <= MASK64


def test_next_u32_is_32_bit():
    rng = seeded_rng(1234)
    for _ in range(1000):
        v = rng.next_u32()
        assert 0 <= v <= MASK32


def test_random_in_unit_interval():
    rng = seeded_rng(1234)
    for _ in range(1000):
        v = rng.random()
        assert 0.0 <= v < 1.0


def test_uniform_in_range():
    rng = seeded_rng(1234)
    for _ in range(1000):
        v = rng.uniform(2.5, 7.5)
        assert 2.5 <= v < 7.5


def test_uniform_handles_negative_range():
    rng = seeded_rng(1234)
    for _ in range(100):
        v = rng.uniform(-3.0, -1.0)
        assert -3.0 <= v < -1.0


@pytest.mark.parametrize("lo,hi", [(0, 0), (3, 8), (-5, 5), (0, 100)])
def test_randint_inclusive_range(lo, hi):
    rng = seeded_rng(1234)
    for _ in range(500):
        v = rng.randint(lo, hi)
        assert lo <= v <= hi


def test_randint_rejects_inverted_range():
    rng = seeded_rng(1)
    with pytest.raises(ValueError):
        rng.randint(5, 3)


# ---- Statistical sanity ----

def test_randint_distribution_roughly_uniform():
    rng = seeded_rng(99)
    counts = [0] * 10
    for _ in range(10_000):
        counts[rng.randint(0, 9)] += 1
    # Each bucket should be near 1000 ± 4σ. Generous bounds — this is a
    # smoke test, not a formal goodness-of-fit test.
    for c in counts:
        assert 800 < c < 1200, f"bucket count {c} too far from 1000"


def test_random_mean_near_half():
    rng = seeded_rng(99)
    n = 10_000
    total = sum(rng.random() for _ in range(n))
    mean = total / n
    assert 0.48 < mean < 0.52


# ---- Constants are the canonical pcg-cpp values ----

def test_canonical_constants():
    # Multiplier: PCG_128BIT_CONSTANT(2549297995355413924, 4865540595714422341)
    assert PCG_DEFAULT_MULTIPLIER_128 == (2549297995355413924 << 64) | 4865540595714422341
    # Increment: PCG_128BIT_CONSTANT(6364136223846793005, 1442695040888963407)
    assert PCG_DEFAULT_INCREMENT_128 == (6364136223846793005 << 64) | 1442695040888963407


# ---- PCG64 direct construction ----

def test_pcg64_inc_forced_odd():
    # Per the LCG spec, increment must be odd for full period.
    rng = PCG64(state=0, inc=42)  # 42 is even
    assert rng.inc & 1 == 1


def test_pcg64_state_masked_to_128():
    rng = PCG64(state=(1 << 200), inc=1)
    assert rng.state == 0  # high bits dropped
