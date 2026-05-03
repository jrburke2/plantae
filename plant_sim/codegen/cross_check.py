"""Cross-checks for schema-valid artifacts against the project libraries.

A schema-valid Mix can still reference a species that doesn't exist; a
schema-valid Scene can reference a missing mix; a per-row form override
can ask for a form the species doesn't support. None of these can be
caught by Pydantic alone — they need the species and mix libraries
loaded.

`SpeciesLibrary` and `MixLibrary` discover and load every YAML in the
respective directory. The check functions take loaded libraries and
return a list of ValidationIssues (same shape used by validate_lpy and
MaterialCrossCheck).

Material-id cross-checking lives in plant_sim/codegen/validator.py
(MaterialCrossCheck); kept there because it sits in the same step as
generated-source validation. This module is for artifact-vs-artifact
checks that run earlier (at validate time) and don't need codegen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from plant_sim.codegen.validator import ValidationIssue
from plant_sim.schema.mix import Mix
from plant_sim.schema.scene import MixEntry, Scene, SpeciesEntry
from plant_sim.schema.species import MaterialForm, Species


@dataclass
class SpeciesLibrary:
    """Discover and load every species YAML under a directory."""

    species_dir: Path
    species: dict[str, Species] = field(default_factory=dict)

    @classmethod
    def load(cls, species_dir: Path | str) -> "SpeciesLibrary":
        d = Path(species_dir)
        out: dict[str, Species] = {}
        for path in sorted(d.rglob("*.yaml")):
            # Skip the JSON-Schema scratch directory.
            if "_schema" in path.parts:
                continue
            try:
                sp = Species.from_yaml(path)
            except Exception:
                # A species YAML that doesn't schema-validate gets skipped
                # silently here; `plant-sim validate <that-file>` is the
                # right surface to surface that error to the author.
                continue
            out[path.stem] = sp
        return cls(species_dir=d, species=out)

    def has(self, name: str) -> bool:
        return name in self.species

    def get(self, name: str) -> Species | None:
        return self.species.get(name)


@dataclass
class MixLibrary:
    """Discover and load every mix YAML under a directory."""

    mix_dir: Path
    mixes: dict[str, Mix] = field(default_factory=dict)

    @classmethod
    def load(cls, mix_dir: Path | str) -> "MixLibrary":
        d = Path(mix_dir)
        out: dict[str, Mix] = {}
        if not d.exists():
            return cls(mix_dir=d, mixes=out)
        for path in sorted(d.rglob("*.yaml")):
            try:
                mix = Mix.from_yaml(path)
            except Exception:
                continue
            out[mix.name] = mix
        return cls(mix_dir=d, mixes=out)

    def has(self, name: str) -> bool:
        return name in self.mixes

    def get(self, name: str) -> Mix | None:
        return self.mixes.get(name)


def check_mix_against_species(
    mix: Mix,
    species_lib: SpeciesLibrary,
) -> list[ValidationIssue]:
    """Cross-check a mix's components against the species library.

    Rules:
      - Every component species must exist.
      - Every component species must include `seed` in allowed_forms
        (mixes are seed-form by definition).
      - Every component species must include the mix's grade in its
        grade list (mix grade compatibility).
    """
    issues: list[ValidationIssue] = []
    for c in mix.components:
        sp = species_lib.get(c.species)
        if sp is None:
            issues.append(ValidationIssue(
                severity="error",
                line=0,
                message=(
                    f"mix {mix.name!r} component {c.species!r} not found in species library "
                    f"(loaded from {species_lib.species_dir})"
                ),
            ))
            continue
        if MaterialForm.seed not in sp.material.allowed_forms:
            issues.append(ValidationIssue(
                severity="error",
                line=0,
                message=(
                    f"mix {mix.name!r} component {c.species!r} does not include 'seed' "
                    f"in allowed_forms ({[f.value for f in sp.material.allowed_forms]}); "
                    f"mixes are seed-form by definition"
                ),
            ))
        if mix.grade not in sp.grade:
            issues.append(ValidationIssue(
                severity="error",
                line=0,
                message=(
                    f"mix {mix.name!r} grade {mix.grade.value!r} not in component "
                    f"{c.species!r} grade list ({[g.value for g in sp.grade]})"
                ),
            ))
    return issues


def check_scene_against_libs(
    scene: Scene,
    species_lib: SpeciesLibrary,
    mix_lib: MixLibrary,
) -> list[ValidationIssue]:
    """Cross-check a scene against the species and mix libraries.

    Rules:
      - Every species_mix.species (SpeciesEntry) must exist.
      - Every species_mix.mix (MixEntry) must exist.
      - Every key_specimen.species must exist.
      - When a SpeciesEntry overrides `form`, that form must be in the
        species' allowed_forms.
    """
    issues: list[ValidationIssue] = []

    for entry in scene.species_mix:
        if isinstance(entry, SpeciesEntry):
            sp = species_lib.get(entry.species)
            if sp is None:
                issues.append(ValidationIssue(
                    severity="error",
                    line=0,
                    message=(
                        f"scene {scene.name!r} species_mix species {entry.species!r} "
                        f"not found in species library"
                    ),
                ))
                continue
            if entry.form is not None and entry.form not in sp.material.allowed_forms:
                issues.append(ValidationIssue(
                    severity="error",
                    line=0,
                    message=(
                        f"scene {scene.name!r} species_mix entry {entry.species!r} "
                        f"overrides form to {entry.form.value!r}, which is not in the "
                        f"species' allowed_forms "
                        f"({[f.value for f in sp.material.allowed_forms]})"
                    ),
                ))
        elif isinstance(entry, MixEntry):
            if not mix_lib.has(entry.mix):
                issues.append(ValidationIssue(
                    severity="error",
                    line=0,
                    message=(
                        f"scene {scene.name!r} species_mix mix {entry.mix!r} "
                        f"not found in mix library (loaded from {mix_lib.mix_dir})"
                    ),
                ))

    for ks in scene.key_specimens:
        if not species_lib.has(ks.species):
            issues.append(ValidationIssue(
                severity="error",
                line=0,
                message=(
                    f"scene {scene.name!r} key_specimen species {ks.species!r} "
                    f"not found in species library"
                ),
            ))

    return issues
