"""Regression test for the cross-runtime parity fixture.

Re-runs the Python implementation against the committed JSON vectors and
asserts byte-equality. This catches accidental drift in `pcg.py` or
`Seed.derive`. Cross-runtime parity (Python ↔ JS) is gated separately by
the Node test consuming the same fixture.

If this test fails after an intentional algorithm change:
    python -m plant_sim.runtime._emit_vectors > tests/fixtures/pcg_vectors.json

…and remember to update the JS port and re-run the Node parity test
in the same commit, since changing the algorithm is a breaking change
to every committed seed-derived artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from plant_sim.runtime._emit_vectors import build_vectors

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pcg_vectors.json"


def test_fixture_matches_current_implementation():
    committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    regenerated = build_vectors()
    assert regenerated == committed, (
        "PCG/derive output drifted from the committed fixture. If this is "
        "intentional, regenerate the fixture and update the JS port + Node "
        "parity test in the same commit."
    )


def test_fixture_has_expected_shape():
    """Smoke check on the fixture itself (in case it gets corrupted)."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["draws_per_seed"] == 1000
    assert len(data["pcg_seeds"]) == 100
    assert len(data["derive_cases"]) >= 20
    # Each PCG entry has the right shape
    for entry in data["pcg_seeds"]:
        assert isinstance(entry["seed"], int)
        assert len(entry["first_n"]) == data["first_n_verbatim"]
        assert len(entry["sha256"]) == 64  # hex sha256
    # Each derive entry has the right shape
    for entry in data["derive_cases"]:
        assert len(entry["parent"]) == 8
        assert len(entry["child"]) == 8
        assert isinstance(entry["salts"], list)
