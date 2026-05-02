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

def test_lowercase_accepted():
    s = Seed("xqf2d6s1")
    assert s.canonical() == "XQF2D6S1"


def test_hyphen_optional():
    a = Seed("XQF2-D6S1")
    b = Seed("XQF2D6S1")
    assert a == b


def test_space_separator_accepted():
    s = Seed("XQF2 D6S1")
    assert s.canonical() == "XQF2D6S1"


def test_crockford_io_l_normalization():
    """Crockford rule: I/L -> 1, O -> 0 on parse (visual ambiguity)."""
    # `00OO00LL` -> Crockford fix -> `00000011` (base32) -> int 0b00001_00001 = 33.
    # `Seed("00000011")` would hit the all-digits path and parse as int 11, so
    # we compare against the integer Seed directly to test the base32 path.
    assert Seed("00OO00LL") == Seed(33)


def test_integer_string_accepted():
    """Backward compat: '42' parses as integer 42."""
    assert Seed("42") == Seed(42)
    assert Seed("1337") == Seed(1337)


# ---- Validation ----

def test_wrong_length_rejected():
    with pytest.raises(ValueError, match="expected exactly"):
        Seed("ABC")
    with pytest.raises(ValueError, match="expected exactly"):
        Seed("ABCDEFGHIJ")  # 10 chars (after I -> 1 normalization, still 10)


def test_invalid_alphabet_rejected():
    # 'U' isn't in Crockford
    with pytest.raises(ValueError, match="invalid base32 char"):
        Seed("00000UUU")


def test_negative_int_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        Seed(-1)


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
