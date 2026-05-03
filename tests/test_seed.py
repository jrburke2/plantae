"""Tests for shareable specimen seeds (BOI-style 8-char base32)."""

from __future__ import annotations

import pytest

from plant_sim.schema.seed import (
    ALPHABET,
    SEED_LEN,
    SEED_MAX,
    Seed,
)


def test_canonical_is_eight_chars():
    s = Seed(42)
    assert len(s.canonical()) == SEED_LEN
    assert all(c in ALPHABET for c in s.canonical())


def test_display_has_midpoint_hyphen():
    s = Seed(42)
    d = s.display()
    assert "-" in d
    assert d.replace("-", "") == s.canonical()


def test_canonical_is_uppercase():
    s = Seed(0xDEADBEEF)
    assert s.canonical() == s.canonical().upper()


# ---- Round-trip ----

def test_int_round_trip():
    for n in (0, 1, 42, 1337, 0xDEADBEEF, SEED_MAX):
        s = Seed(n)
        assert Seed(s.canonical()).to_int() == n
        assert Seed(s.display()).to_int() == n


def test_string_round_trip():
    s1 = Seed.random()
    s2 = Seed(s1.canonical())
    s3 = Seed(s1.display())
    assert s1 == s2 == s3
    assert s1.to_int() == s2.to_int() == s3.to_int()


# ---- Parsing forgiveness ----

@pytest.mark.parametrize("input,expected_int", [
    ("xqf2d6s1", Seed("XQF2D6S1").to_int()),    # lowercase normalizes
    ("XQF2-D6S1", Seed("XQF2D6S1").to_int()),   # hyphen separator optional
    ("XQF2 D6S1", Seed("XQF2D6S1").to_int()),   # space separator accepted
    # Crockford rule: I/L -> 1, O -> 0 on parse (visual ambiguity).
    # `00OO00LL` -> `00000011` (base32) -> int 33.
    ("00OO00LL", 33),
    ("42", 42),                                  # integer-string backward compat
    ("1337", 1337),
])
def test_parse_accepts(input, expected_int):
    assert Seed(input).to_int() == expected_int


# ---- Validation ----

@pytest.mark.parametrize("bad_input,error_match", [
    ("ABC", "expected exactly"),                # too short
    ("ABCDEFGHIJ", "expected exactly"),         # too long (10 chars after I->1 norm)
    ("00000UUU", "invalid base32 char"),        # 'U' isn't in Crockford
    (-1, "non-negative"),                       # negative int
])
def test_parse_rejects(bad_input, error_match):
    with pytest.raises(ValueError, match=error_match):
        Seed(bad_input)


def test_int_above_max_wraps_for_compat():
    """Integers > SEED_MAX are reduced modulo (40-bit window) for backward compat."""
    s = Seed(SEED_MAX + 5)
    assert 0 <= s.to_int() <= SEED_MAX


# ---- Random generation ----

def test_random_produces_valid_seed():
    s = Seed.random()
    assert 0 <= s.to_int() <= SEED_MAX
    assert len(s.canonical()) == SEED_LEN


def test_random_seeds_are_different():
    seeds = {Seed.random().to_int() for _ in range(20)}
    # 40 bits of entropy; vanishing chance of collision in 20 draws
    assert len(seeds) == 20


# ---- Determinism (the load-bearing replay property) ----

def test_same_seed_same_random_draw():
    """Same Seed -> random.seed() -> identical sequence. The replay guarantee."""
    import random
    a, b = Seed("XQF2-D6S1"), Seed("XQF2D6S1")
    random.seed(a.to_int())
    seq_a = [random.random() for _ in range(10)]
    random.seed(b.to_int())
    seq_b = [random.random() for _ in range(10)]
    assert seq_a == seq_b


# ---- Pydantic integration ----

def test_seed_works_in_pydantic_model():
    from pydantic import BaseModel

    class Holder(BaseModel):
        model_config = {"arbitrary_types_allowed": True}
        seed: Seed

    h1 = Holder(seed="XQF2-D6S1")
    h2 = Holder(seed=Seed("XQF2D6S1"))
    h3 = Holder(seed=42)

    assert h1.seed == h2.seed
    assert h3.seed.to_int() == 42

    # Serialization uses canonical form
    assert h1.model_dump()["seed"] == "XQF2D6S1"


# ---- Hierarchical derivation (V2.0 foundation) ----

def test_derive_is_deterministic():
    parent = Seed("XQF2D6S1")
    a = parent.derive("specimen", 0)
    b = parent.derive("specimen", 0)
    assert a == b


def test_derive_different_salts_diverge():
    parent = Seed("XQF2D6S1")
    a = parent.derive("specimen", 0)
    b = parent.derive("specimen", 1)
    c = parent.derive("rosette_leaf", 0)
    assert a != b != c
    assert a != c


def test_derive_different_parents_diverge():
    a = Seed("XQF2D6S1").derive("specimen", 0)
    b = Seed("XQF2D6S2").derive("specimen", 0)
    assert a != b


def test_derive_str_and_int_salts_distinct():
    """derive("42") must not collide with derive(42); type-tag enforces this."""
    parent = Seed(0)
    assert parent.derive("42") != parent.derive(42)


def test_derive_no_concatenation_collision():
    """derive("ab") must not collide with derive("a", "b"); separator enforces this."""
    parent = Seed(0)
    assert parent.derive("ab") != parent.derive("a", "b")


def test_derive_returns_valid_seed():
    s = Seed("XQF2D6S1").derive("anything")
    assert 0 <= s.to_int() <= SEED_MAX
    assert len(s.canonical()) == SEED_LEN


def test_derive_with_no_salts():
    """Zero-arg derive is allowed; it stretches the parent through the hash."""
    parent = Seed(42)
    child = parent.derive()
    assert child != parent  # vanishingly small chance of collision
    # And it's deterministic
    assert child == Seed(42).derive()


@pytest.mark.parametrize("bad_int", [-1, 1 << 64, (1 << 64) + 1])
def test_derive_rejects_int_out_of_range(bad_int):
    with pytest.raises(ValueError, match=r"\[0, 2\*\*64\)"):
        Seed(0).derive(bad_int)


def test_derive_rejects_bool():
    """bool is an int subclass in Python; reject so derive(True) doesn't silently encode as 1."""
    with pytest.raises(TypeError, match="bool"):
        Seed(0).derive(True)


def test_derive_rejects_other_types():
    with pytest.raises(TypeError, match="str or int"):
        Seed(0).derive(3.14)
    with pytest.raises(TypeError, match="str or int"):
        Seed(0).derive(("tuple",))


def test_derive_chain():
    """specimen_seed = scene_seed.derive("specimen", i); leaf_seed = specimen_seed.derive(...)"""
    scene = Seed("PRAR1234")
    specimen = scene.derive("specimen", 0)
    leaf = specimen.derive("rosette_leaf", 0)
    # All distinct
    assert scene != specimen != leaf
    assert scene != leaf
    # Determinism through the chain
    specimen2 = scene.derive("specimen", 0)
    leaf2 = specimen2.derive("rosette_leaf", 0)
    assert leaf == leaf2
