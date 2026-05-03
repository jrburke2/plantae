"""Emit cross-runtime parity vectors for PCG and Seed.derive.

Run as:
    python -m plant_sim.runtime._emit_vectors > tests/fixtures/pcg_vectors.json

The emitted JSON is consumed by:
- tests/test_pcg_vectors.py  (Python regression — guards against drift here)
- viewer/test/parity.test.mjs (Node parity — guards against TS drift)

Format is the contract between Python and TypeScript implementations.
Storing all draws verbatim would balloon the file (~10 MB for 1000×1000),
so each seed stores its first 8 draws plus a SHA-256 digest of the full
1000-draw stream. Bit-exact parity requires both to match.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

from plant_sim.runtime.pcg import seeded_rng
from plant_sim.schema.seed import SEED_MAX, Seed

VERSION = 1
DRAWS_PER_SEED = 1000
FIRST_N_VERBATIM = 8


def _build_pcg_seeds() -> list[int]:
    """Deterministic seed list: edge cases first, then a filler sequence."""
    edges = [0, 1, 42, 1337, SEED_MAX, 0xCAFEF00D, 0xDEADBEEF, 0xBADC0FFEE]
    edges = [s & SEED_MAX for s in edges]
    seeds = list(dict.fromkeys(edges))  # de-dup, preserve order

    # Fill to 100 with a deterministic stride that exercises low/mid/high
    # bits without overlapping the edge values.
    stride = 0x9E3779B9  # golden-ratio constant; well-mixed step
    n = 1
    while len(seeds) < 100:
        candidate = (stride * n) & SEED_MAX
        n += 1
        if candidate not in seeds:
            seeds.append(candidate)
    return seeds


def _emit_pcg_vector(seed_int: int) -> dict[str, Any]:
    rng = seeded_rng(seed_int)
    h = hashlib.sha256()
    first_n: list[str] = []
    for i in range(DRAWS_PER_SEED):
        u = rng.next_u64()
        h.update(u.to_bytes(8, "big"))
        if i < FIRST_N_VERBATIM:
            first_n.append(f"{u:016x}")
    return {
        "seed": seed_int,
        "first_n": first_n,
        "sha256": h.hexdigest(),
    }


# --- derive cases ---
# Each case: (parent_canonical, [salt, ...]) -> child_canonical
# Salts encoded as {"type": "str"|"int", "value": ...} for unambiguous JSON.

DERIVE_CASES: list[tuple[str, list[Any]]] = [
    # Edge parents
    ("00000000", []),
    ("00000000", ["a"]),
    ("00000000", [0]),
    ("ZZZZZZZZ", []),
    ("ZZZZZZZZ", ["specimen", 0]),
    # Ambiguity gates
    ("00000000", ["42"]),
    ("00000000", [42]),
    ("00000000", ["ab"]),
    ("00000000", ["a", "b"]),
    # Realistic use sites
    ("PRAR1234", ["specimen", 0]),
    ("PRAR1234", ["specimen", 1]),
    ("PRAR1234", ["specimen", 1000]),
    ("PRAR1234", ["specimen", (1 << 32) - 1]),
    ("XQF2D6S1", ["rosette_leaf", 0]),
    ("XQF2D6S1", ["rosette_leaf", 5]),
    ("XQF2D6S1", ["scape", 0]),
    ("XQF2D6S1", ["archetype:rosette_scape_composite@1.2.0"]),
    ("XQF2D6S1", ["archetype:tiller_clump@0.1.0"]),
    # Unicode in str salt
    ("00000000", ["échinacée"]),
    ("00000000", ["象形文字"]),
    # Empty string salt
    ("00000000", [""]),
    ("00000000", ["", ""]),
    # int salt edges
    ("00000000", [(1 << 64) - 1]),
    ("00000000", [1 << 32]),
    # Mixed multi-salt chains
    ("PRAR1234", ["specimen", 0, "rosette_leaf", 3]),
    ("PRAR1234", ["specimen", 0, "rosette_leaf", 4]),
    # Two-step derivation = single-step with different first-level child
    ("PRAR1234", ["a"]),
    ("PRAR1234", ["b"]),
]


def _emit_derive_case(parent_canonical: str, salts: list[Any]) -> dict[str, Any]:
    parent = Seed(parent_canonical)
    child = parent.derive(*salts)
    encoded_salts: list[dict[str, Any]] = []
    for s in salts:
        if isinstance(s, str):
            encoded_salts.append({"type": "str", "value": s})
        elif isinstance(s, int):
            encoded_salts.append({"type": "int", "value": s})
        else:
            raise TypeError(f"unsupported salt type {type(s).__name__}")
    return {
        "parent": parent.canonical(),
        "salts": encoded_salts,
        "child": child.canonical(),
    }


def build_vectors() -> dict[str, Any]:
    return {
        "version": VERSION,
        "draws_per_seed": DRAWS_PER_SEED,
        "first_n_verbatim": FIRST_N_VERBATIM,
        "pcg_seeds": [_emit_pcg_vector(s) for s in _build_pcg_seeds()],
        "derive_cases": [_emit_derive_case(p, s) for p, s in DERIVE_CASES],
    }


def main() -> None:
    json.dump(build_vectors(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
