"""Shareable specimen seeds.

Same idea as Binding of Isaac: Rebirth — a fixed-length string a user
can copy, paste, or read aloud to reproduce the exact same specimen.

Format:
  - 8 characters of Crockford base32 (alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`)
  - 8 chars × 5 bits = 40 bits = ~1.1 trillion distinct seeds
  - Crockford excludes I, L, O, U to avoid ambiguity; on parse we
    accept I/i -> 1, L/l -> 1, O/o -> 0 (Crockford forgiveness rule)
  - Displayed with a hyphen at the midpoint for readability:
    canonical "XQF2D6S1" -> displayed "XQF2-D6S1"
  - Case-insensitive on parse; canonical storage is uppercase

Backward compatibility:
  - Integer seeds (e.g. `seed=42`, `seed=1337`) still work everywhere:
    parsed as int and converted to canonical base32 (`0000001A`,
    `00000019`). Old generated .lpy filenames change shape but the
    underlying randomness is identical.
"""

from __future__ import annotations

import os
import re
from typing import Any

# Crockford base32: skips I, L, O, U for visual unambiguity.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SEED_LEN = 8                  # 40 bits
SEED_BITS = SEED_LEN * 5
SEED_MAX = (1 << SEED_BITS) - 1
DISPLAY_SPLIT = SEED_LEN // 2  # hyphen midway through

# Crockford forgiveness: I/L -> 1, O -> 0
_CROCKFORD_FIX = str.maketrans("ILOilo", "110110")
# Strip allowed separators on parse
_STRIP_RE = re.compile(r"[\s\-]+")


class Seed:
    """An 8-character base32 specimen seed.

    Construct from int, string (canonical or display form), or another
    Seed. Use `Seed.random()` for a fresh random seed.
    """

    __slots__ = ("_int",)

    def __init__(self, value: "Seed | int | str") -> None:
        if isinstance(value, Seed):
            self._int = value._int
        elif isinstance(value, int):
            if not 0 <= value <= SEED_MAX:
                # Integer seeds can be outside the 40-bit window for
                # backward compat (legacy `seed=42` etc.). We still
                # accept any non-negative int by reducing modulo SEED_MAX+1.
                if value < 0:
                    raise ValueError(f"seed integer must be non-negative, got {value}")
                value = value & SEED_MAX
            self._int = value
        elif isinstance(value, str):
            self._int = _parse_seed_string(value)
        else:
            raise TypeError(
                f"Seed accepts int, str, or Seed; got {type(value).__name__}"
            )

    @classmethod
    def random(cls) -> "Seed":
        """Generate a fresh random seed from os.urandom."""
        n = int.from_bytes(os.urandom((SEED_BITS + 7) // 8), "big") & SEED_MAX
        return cls(n)

    def to_int(self) -> int:
        """Integer form. Pass to `random.seed()` etc."""
        return self._int

    def canonical(self) -> str:
        """Uppercase, no separators. Used in filenames and URLs."""
        return _int_to_seed_string(self._int)

    def display(self) -> str:
        """Human-friendly with mid-string hyphen, e.g. 'XQF2-D6S1'."""
        c = self.canonical()
        return f"{c[:DISPLAY_SPLIT]}-{c[DISPLAY_SPLIT:]}"

    def __int__(self) -> int:
        return self._int

    def __str__(self) -> str:
        return self.display()

    def __repr__(self) -> str:
        return f"Seed({self.display()!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Seed):
            return self._int == other._int
        if isinstance(other, int):
            return self._int == (other & SEED_MAX)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._int)

    # === Pydantic v2 hook ===
    # Accept int, str, or Seed in model fields; serialize as the
    # canonical string so JSON and YAML round-trip cleanly.

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any):
        from pydantic_core import core_schema

        def validate(value: Any) -> "Seed":
            return cls(value)

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda s: s.canonical(), return_schema=core_schema.str_schema()
            ),
        )


def _int_to_seed_string(n: int) -> str:
    """Convert non-negative int (≤ SEED_MAX) to 8-char canonical seed string."""
    if n < 0 or n > SEED_MAX:
        raise ValueError(f"int {n} out of range 0..{SEED_MAX}")
    chars = []
    for _ in range(SEED_LEN):
        chars.append(ALPHABET[n & 0x1F])
        n >>= 5
    return "".join(reversed(chars))


def _parse_seed_string(s: str) -> int:
    """Parse seed string back to int. Accepts:

    - Canonical: 'XQF2D6S1'
    - Display:   'XQF2-D6S1'
    - Spaced:    'XQF2 D6S1'
    - Lower:     'xqf2-d6s1'
    - Numeric:   '42'  (integer string for backward compat; bigger ints
      are also accepted and reduced modulo SEED_MAX+1)
    """
    s = s.strip()
    # Pure-digit input -> integer seed (legacy behavior)
    if s.isdigit():
        return int(s) & SEED_MAX

    # Otherwise treat as base32; normalize separators, case, and Crockford
    # ambiguous letters.
    cleaned = _STRIP_RE.sub("", s).translate(_CROCKFORD_FIX).upper()
    if len(cleaned) != SEED_LEN:
        raise ValueError(
            f"seed string {s!r} normalized to {cleaned!r} ({len(cleaned)} chars); "
            f"expected exactly {SEED_LEN} base32 chars after stripping separators"
        )
    n = 0
    for c in cleaned:
        try:
            n = (n << 5) | ALPHABET.index(c)
        except ValueError:
            raise ValueError(
                f"invalid base32 char {c!r} in seed {s!r}; "
                f"alphabet is {ALPHABET!r}"
            ) from None
    return n
