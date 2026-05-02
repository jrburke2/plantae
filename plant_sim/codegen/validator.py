"""Static syntax checks on generated .lpy source.

The codegen owns all L-Py syntax knowledge so contributors never see raw
.lpy. The validator exists to catch the few classes of error that any
hand-modified template might emit, before L-Py gets a chance to die with
an opaque traceback. It runs without importing L-Py.

Checks (all from spike findings + design doc Section 9):
  - Every multi-character module name referenced in productions or
    interpretations must be declared via `module Name(...)` at the top.
  - No multi-line `-->` interpretation rules. The L-Py parser does not
    accept indented continuation lines on `-->` rules (Spike 1 finding).
  - All color slot indices `;(N)` must satisfy 0 <= N <= 6 (PlantGL
    silently clamps higher values).
  - Material id strings referenced in module parameters must exist in
    materials/library.json. (Run via `validate_material_ids`.)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# L-Py reserves single-character module names for built-in turtle commands
# (F, f, A, G, +, -, &, ^, /, \, ~, ;, _, [, ], etc.). Skip them in the
# "must be declared" check; only multi-char names need explicit declarations.
_BUILTIN_SINGLE_CHARS = set("FfGgABCDEHIJKLMNOPQRSTUVWXYZbcdefghijklmnopqrstuvwxyz")
# Exclude common turtle ops; specific declared module names override.
_TURTLE_OP_SINGLE_CHARS = set("Ff")  # F = forward, f = forward no draw

# Words that look like module references but aren't (Python keywords, builtins
# we know are called inside production bodies).
_PYTHON_RESERVED = {
    "if", "else", "elif", "for", "while", "and", "or", "not", "in", "is",
    "True", "False", "None", "produce", "import", "from", "as", "def",
    "return", "yield", "with", "lambda", "pass", "break", "continue",
    "try", "except", "finally", "raise", "class", "global", "nonlocal",
    "assert", "del",
    # L-Py-specific
    "module", "extern", "Axiom", "derivation", "length", "production",
    "interpretation", "endlsystem", "getIterationNb",
    # Functions imported from growth_functions
    "sigmoid_grow", "alpha_at", "seasonal_color", "draw_growth_days",
    # Common stdlib
    "math", "random", "exp", "log", "sin", "cos", "tan", "pi", "sqrt",
    "abs", "min", "max", "int", "float", "str", "bool", "list", "dict",
    "tuple", "set", "len", "range", "round", "print", "type",
    "randint", "uniform", "gauss", "seed", "choice",
}


@dataclass
class ValidationIssue:
    severity: str   # "error" or "warning"
    line: int       # 1-indexed; 0 means file-level
    message: str

    def __str__(self) -> str:
        loc = f"line {self.line}" if self.line else "file"
        return f"[{self.severity.upper()}] {loc}: {self.message}"


class ValidationError(Exception):
    """Raised when the validator finds at least one error-severity issue."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        errs = [i for i in issues if i.severity == "error"]
        msg = f"{len(errs)} validation error(s):\n" + "\n".join(f"  {i}" for i in errs)
        super().__init__(msg)


# --- Individual check functions ---

_MODULE_DECL_RE = re.compile(r"^\s*module\s+([A-Z][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_RULE_REF_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]+)\s*\(")
_COLOR_RE = re.compile(r";\((\d+)\)")
_ARROW_RE = re.compile(r"-->\s*$")  # `-->` followed only by whitespace/EOL = empty rule body


def _check_module_declarations(source: str) -> Iterable[ValidationIssue]:
    declared = set(_MODULE_DECL_RE.findall(source))

    in_productions = False
    in_interpretation = False
    for lineno, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("production:"):
            in_productions = True
            in_interpretation = False
            continue
        if stripped.startswith("interpretation:"):
            in_interpretation = True
            in_productions = False
            continue
        if stripped.startswith("endlsystem"):
            in_productions = in_interpretation = False
            continue
        if not (in_productions or in_interpretation):
            continue

        for name in _RULE_REF_RE.findall(raw):
            if name in declared:
                continue
            if name in _PYTHON_RESERVED:
                continue
            if name in _BUILTIN_SINGLE_CHARS and len(name) == 1:
                continue
            # Multi-char unknown module reference
            yield ValidationIssue(
                severity="error",
                line=lineno,
                message=(
                    f"module {name!r} referenced but not declared via `module {name}(...)`. "
                    f"Multi-character module names must be declared."
                ),
            )


def _check_no_multiline_arrow_rules(source: str) -> Iterable[ValidationIssue]:
    for lineno, raw in enumerate(source.splitlines(), start=1):
        if _ARROW_RE.search(raw):
            yield ValidationIssue(
                severity="error",
                line=lineno,
                message=(
                    "interpretation rule with `-->` has empty body on this line. "
                    "L-Py requires single-line `-->` rules; use `:` + `produce` for multi-line bodies."
                ),
            )


def _check_color_slot_range(source: str) -> Iterable[ValidationIssue]:
    for lineno, raw in enumerate(source.splitlines(), start=1):
        for match in _COLOR_RE.finditer(raw):
            n = int(match.group(1))
            if not (0 <= n <= 6):
                yield ValidationIssue(
                    severity="error",
                    line=lineno,
                    message=(
                        f"color slot `;({n})` is outside the valid range 0..6. "
                        f"PlantGL silently clamps higher values; this is almost always a bug."
                    ),
                )


# --- Top-level entry point ---

def validate_lpy(source: str, *, raise_on_error: bool = True) -> list[ValidationIssue]:
    """Return all validation issues for the given .lpy source.

    By default, raises `ValidationError` if any issue has severity "error".
    Pass `raise_on_error=False` to get the issue list back instead (useful
    for tooling that wants to format errors itself).
    """
    issues: list[ValidationIssue] = []
    issues.extend(_check_module_declarations(source))
    issues.extend(_check_no_multiline_arrow_rules(source))
    issues.extend(_check_color_slot_range(source))

    if raise_on_error and any(i.severity == "error" for i in issues):
        raise ValidationError(issues)
    return issues


# --- Material id cross-check (separate; needs the species YAML) ---

@dataclass
class MaterialCrossCheck:
    library_path: Path
    library: dict = field(default_factory=dict)

    @classmethod
    def load(cls, library_path: Path | str) -> "MaterialCrossCheck":
        p = Path(library_path)
        with p.open() as f:
            library = json.load(f)
        return cls(library_path=p, library=library)

    def check_ids(self, material_ids: Iterable[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for mid in material_ids:
            if mid not in self.library:
                issues.append(ValidationIssue(
                    severity="error",
                    line=0,
                    message=(
                        f"material_id {mid!r} not found in {self.library_path}. "
                        f"Add it to the library or fix the species YAML."
                    ),
                ))
        return issues


def collect_material_ids(species) -> list[str]:
    """Return all material_id strings referenced in a Species object."""
    ids: list[str] = []
    p = species.parameters
    for block_name in ("rosette", "scape", "panicle"):
        block = getattr(p, block_name, None)
        if block is not None:
            for attr in ("material_id", "ray_material_id", "disk_material_id",
                          "leaf_material_id", "culm_material_id"):
                v = getattr(block, attr, None)
                if isinstance(v, str):
                    ids.append(v)
    if hasattr(p, "inflorescence"):
        ids.extend([
            p.inflorescence.ray_material_id,
            p.inflorescence.disk_material_id,
        ])
    if hasattr(p, "tiller"):
        ids.extend([
            p.tiller.leaf_material_id,
            p.tiller.culm_material_id,
        ])
    return ids
