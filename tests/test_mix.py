"""Mix schema tests (F57)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from plant_sim.schema.mix import Mix, MixComponent
from plant_sim.schema.species import GradeTag

REPO = Path(__file__).resolve().parent.parent
MIXES = REPO / "mixes"


# ---- Happy path ----

def test_demo_mix_loads():
    mix = Mix.from_yaml(MIXES / "restoration_demo_mix.yaml")
    assert mix.name == "restoration_demo_mix"
    assert mix.display_name == "Restoration Demo Mix"
    assert mix.grade == GradeTag.restoration_grade
    assert len(mix.components) == 2
    assert {c.species for c in mix.components} == {
        "andropogon_gerardii",
        "echinacea_purpurea",
    }
    assert sum(c.weight_pct for c in mix.components) == pytest.approx(100.0)


# ---- Validation rules ----

def test_components_must_sum_to_100():
    with pytest.raises(ValidationError, match="sum to 100"):
        Mix(
            name="bad_mix",
            display_name="Bad Mix",
            grade=GradeTag.restoration_grade,
            components=[
                MixComponent(species="a", weight_pct=50),
                MixComponent(species="b", weight_pct=40),
            ],
        )


def test_min_two_components():
    with pytest.raises(ValidationError):
        Mix(
            name="single",
            display_name="Single",
            grade=GradeTag.restoration_grade,
            components=[MixComponent(species="a", weight_pct=100)],
        )


def test_duplicate_species_rejected():
    with pytest.raises(ValidationError, match="duplicate species"):
        Mix(
            name="dupe",
            display_name="Dupe",
            grade=GradeTag.restoration_grade,
            components=[
                MixComponent(species="a", weight_pct=50),
                MixComponent(species="a", weight_pct=50),
            ],
        )


def test_weight_pct_bounds():
    # weight_pct must be > 0 and <= 100
    with pytest.raises(ValidationError):
        MixComponent(species="a", weight_pct=0)
    with pytest.raises(ValidationError):
        MixComponent(species="a", weight_pct=101)
    with pytest.raises(ValidationError):
        MixComponent(species="a", weight_pct=-1)


def test_name_must_match_filename_stem(tmp_path: Path):
    p = tmp_path / "rename_me_mix.yaml"
    p.write_text(
        "name: a_different_name\n"
        "display_name: Mismatch\n"
        "grade: restoration_grade\n"
        "components:\n"
        "  - species: a\n"
        "    weight_pct: 60\n"
        "  - species: b\n"
        "    weight_pct: 40\n"
    )
    with pytest.raises(ValueError, match="does not match filename stem"):
        Mix.from_yaml(p)
