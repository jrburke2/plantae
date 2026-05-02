"""Validator tests for Step 4.

The validator is intentionally narrow: it only catches the specific
classes of error the spike findings flagged. Each check has its own
focused test using a tiny .lpy fragment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plant_sim.codegen.validator import (
    MaterialCrossCheck,
    ValidationError,
    ValidationIssue,
    collect_material_ids,
    validate_lpy,
)
from plant_sim.schema.species import Species

REPO = Path(__file__).resolve().parent.parent


def _issues_with_severity(issues, sev: str) -> list[ValidationIssue]:
    return [i for i in issues if i.severity == sev]


# ---- Multi-character module declarations ----

def test_undeclared_module_in_production_errors():
    src = """
module DeclaredOnly(t)

production:
DeclaredOnly(t) :
    produce DeclaredOnly(t + 1) UndeclaredFoo(t)
"""
    with pytest.raises(ValidationError) as exc:
        validate_lpy(src)
    msg = str(exc.value)
    assert "UndeclaredFoo" in msg
    assert "must be declared" in msg


def test_declared_module_passes():
    src = """
module Plant(t)
module Leaf(t_birth)

production:
Plant(t) :
    produce Plant(t + 1) Leaf(t)
"""
    issues = validate_lpy(src, raise_on_error=False)
    assert _issues_with_severity(issues, "error") == []


def test_python_keywords_in_production_dont_false_positive():
    src = """
module Plant(t)

production:
Plant(t) :
    if t > 5:
        produce Plant(t + 1)
    else:
        produce Plant(t)
"""
    issues = validate_lpy(src, raise_on_error=False)
    assert _issues_with_severity(issues, "error") == []


# ---- No multi-line --> rules ----

def test_multiline_arrow_rule_errors():
    src = """
module Leaf(t)

interpretation:
Leaf(t) -->
    [&(80) ;(2) ~l(1.0)]
"""
    with pytest.raises(ValidationError) as exc:
        validate_lpy(src)
    assert "single-line `-->`" in str(exc.value)


def test_single_line_arrow_rule_passes():
    src = """
module Leaf(t)

interpretation:
Leaf(t) --> [&(80) ;(2) ~l(1.0)]
"""
    issues = validate_lpy(src, raise_on_error=False)
    assert _issues_with_severity(issues, "error") == []


# ---- Color slot range 0..6 ----

def test_color_slot_out_of_range_errors():
    src = """
module Leaf(t)

interpretation:
Leaf(t) --> ;(7) ~l(1.0)
"""
    with pytest.raises(ValidationError) as exc:
        validate_lpy(src)
    assert "outside the valid range 0..6" in str(exc.value)
    assert ";(7)" in str(exc.value)


def test_color_slot_in_range_passes():
    src = """
module Leaf(t)

interpretation:
Leaf(t) --> ;(0) ;(6) ~l(1.0)
"""
    issues = validate_lpy(src, raise_on_error=False)
    assert _issues_with_severity(issues, "error") == []


# ---- Real generated Echinacea passes ----

def test_real_generated_echinacea_validates():
    from plant_sim.codegen.generator import generate
    sp = Species.from_yaml(REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml")
    src = generate(sp, seed=42)
    issues = validate_lpy(src, raise_on_error=False)
    errors = _issues_with_severity(issues, "error")
    assert errors == [], f"Echinacea generation should validate clean; got: {errors}"


# ---- Material cross-check ----

def test_material_cross_check_passes_for_canonical_echinacea():
    sp = Species.from_yaml(REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml")
    checker = MaterialCrossCheck.load(REPO / "materials" / "library.json")
    issues = checker.check_ids(collect_material_ids(sp))
    assert issues == [], f"unexpected material issues: {issues}"


def test_material_cross_check_catches_typo(tmp_path: Path):
    """A species YAML with a typoed material_id should raise an error."""
    yaml_text = (REPO / "species" / "asteraceae" / "echinacea_purpurea.yaml").read_text()
    yaml_text = yaml_text.replace("ray_floret_purple", "ray_floret_purplezzz")
    p = tmp_path / "typo.yaml"
    p.write_text(yaml_text)
    sp = Species.from_yaml(p)
    checker = MaterialCrossCheck.load(REPO / "materials" / "library.json")
    issues = checker.check_ids(collect_material_ids(sp))
    assert len(issues) == 1
    assert "ray_floret_purplezzz" in str(issues[0])
