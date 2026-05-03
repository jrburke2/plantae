"""PCG-XSL-RR-128/64 — portable PRNG for cross-language determinism.

Python's `random` (Mersenne Twister) and JavaScript's `Math.random`
(implementation-defined per browser) produce different sequences from the
same seed. Plantae's generation must yield identical geometry whether the
template runs in L-Py (Python) or in the browser (TypeScript). The PRNG
beneath every generated artifact must therefore be portable; PCG fits that
bill in ~50 LOC per side.

Algorithm: PCG-XSL-RR-128/64 (Melissa O'Neill, 2014). 128-bit LCG state,
64-bit output via XOR-fold + variable-rotation. Multiplier and default
increment match the canonical pcg-cpp constants. Seeding follows the
canonical setseq pattern (state := inc; step; state += seed; step).

Bit-identical TS twin lives at `viewer/pcg.ts`. Any change here must land
the same change there in the same commit; the cross-runtime parity test
gates this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plant_sim.schema.seed import Seed


MASK128 = (1 << 128) - 1
MASK64 = (1 << 64) - 1
MASK32 = (1 << 32) - 1

# Canonical pcg-cpp default 128-bit multiplier
# = (2549297995355413924 << 64) | 4865540595714422341
PCG_DEFAULT_MULTIPLIER_128 = 47026247687942121848144207491837523525

# Canonical pcg-cpp default 128-bit increment
# = (6364136223846793005 << 64) | 1442695040888963407
PCG_DEFAULT_INCREMENT_128 = 117397592171526113268558934119004209487

# Stream identifier baked into the seeded_rng() factory. Fixed forever:
# changing it shifts every seed's output sequence.
PCG_DEFAULT_STREAM_128 = 0xCAFEF00DD15EA5E5CAFEF00DD15EA5E5

# Pre-computed increment for the default stream:
#   inc = (stream << 1) | 1     (mod 2^128, must be odd)
_DEFAULT_INC = ((PCG_DEFAULT_STREAM_128 << 1) | 1) & MASK128

# Float conversion: top 53 bits → uniform [0, 1) at IEEE-754 double precision.
_FLOAT_DIVISOR = 1.0 / (1 << 53)


class PCG64:
    """PCG-XSL-RR-128/64 generator.

    Use `seeded_rng(seed)` rather than constructing directly unless you need
    a custom increment.
    """

    __slots__ = ("state", "inc")

    def __init__(self, state: int, inc: int = _DEFAULT_INC) -> None:
        # Increment must be odd for the LCG to have full period.
        self.state = state & MASK128
        self.inc = (inc | 1) & MASK128

    def _step(self) -> None:
        self.state = (self.state * PCG_DEFAULT_MULTIPLIER_128 + self.inc) & MASK128

    def next_u64(self) -> int:
        """One 64-bit unsigned draw."""
        self._step()
        st = self.state
        xored = ((st >> 64) ^ (st & MASK64)) & MASK64
        rot = (st >> 122) & 0x3F
        # rotr64
        return ((xored >> rot) | (xored << ((64 - rot) & 63))) & MASK64

    def next_u32(self) -> int:
        """One 32-bit unsigned draw (low 32 bits of next_u64)."""
        return self.next_u64() & MASK32

    def random(self) -> float:
        """Uniform float in [0, 1) with 53 bits of precision."""
        return (self.next_u64() >> 11) * _FLOAT_DIVISOR

    def uniform(self, lo: float, hi: float) -> float:
        """Uniform float in [lo, hi). Matches Python's random.uniform shape."""
        return lo + (hi - lo) * self.random()

    def randint(self, lo: int, hi: int) -> int:
        """Uniform int in [lo, hi] inclusive on both ends.

        Matches Python's random.randint signature. Uses simple modulo, which
        is bias-free for ranges much smaller than 2^64 (all our use sites).
        """
        if hi < lo:
            raise ValueError(f"randint: hi ({hi}) < lo ({lo})")
        n = hi - lo + 1
        return lo + (self.next_u64() % n)


def seeded_rng(seed: "int | Seed") -> PCG64:
    """Construct a PCG64 deterministically from a 40-bit seed (or Seed).

    Seeding follows the canonical pcg-cpp setseq pattern so that small seed
    values still produce well-mixed initial output:

        state = inc
        step()
        state += seed_int
        step()

    The increment is fixed by `PCG_DEFAULT_STREAM_128`. Same seed always
    yields the same stream; changing the stream constant is a breaking
    change to every committed artifact.
    """
    seed_int = int(seed) & MASK128
    rng = PCG64(state=_DEFAULT_INC, inc=_DEFAULT_INC)
    rng._step()
    rng.state = (rng.state + seed_int) & MASK128
    rng._step()
    return rng
