// PCG-XSL-RR-128/64 — bit-identical TS twin of plant_sim/runtime/pcg.py.
//
// Cross-runtime determinism: same seed must produce the same draw sequence
// in Python and the browser. Any change here must land the same change in
// pcg.py in the same commit; the Node parity test gates this.
//
// 128-bit state is BigInt. Slow vs hand-split halves, fine for V2.0 — the
// browser-side use sites don't run PCG in tight loops.

const MASK128 = (1n << 128n) - 1n;
const MASK64 = (1n << 64n) - 1n;
const MASK32 = (1n << 32n) - 1n;

// Canonical pcg-cpp default 128-bit multiplier.
export const PCG_DEFAULT_MULTIPLIER_128 =
  47026247687942121848144207491837523525n;

// Canonical pcg-cpp default 128-bit increment (kept for parity tests; the
// active increment is derived from PCG_DEFAULT_STREAM_128 below).
export const PCG_DEFAULT_INCREMENT_128 =
  117397592171526113268558934119004209487n;

// Stream identifier baked into seededRng(). Same constant as pcg.py.
export const PCG_DEFAULT_STREAM_128 =
  0xCAFEF00DD15EA5E5CAFEF00DD15EA5E5n;

const _DEFAULT_INC = ((PCG_DEFAULT_STREAM_128 << 1n) | 1n) & MASK128;

// 2**-53 as Number — multiply a 53-bit integer by this for [0, 1).
const _FLOAT_DIVISOR = 1.0 / (1 << 30) / (1 << 23);

/**
 * PCG-XSL-RR-128/64 generator.
 *
 * Use `seededRng(seed)` rather than constructing directly unless you need
 * a custom increment.
 */
export class PCG64 {
  /**
   * @param {bigint} state
   * @param {bigint} [inc]
   */
  constructor(state, inc = _DEFAULT_INC) {
    this.state = BigInt(state) & MASK128;
    // Increment must be odd for the LCG to have full period.
    this.inc = (BigInt(inc) | 1n) & MASK128;
  }

  _step() {
    this.state =
      (this.state * PCG_DEFAULT_MULTIPLIER_128 + this.inc) & MASK128;
  }

  /** @returns {bigint} 64-bit unsigned. */
  nextU64() {
    this._step();
    const st = this.state;
    const xored = ((st >> 64n) ^ (st & MASK64)) & MASK64;
    const rot = Number((st >> 122n) & 0x3Fn);
    // rotr64
    const right = xored >> BigInt(rot);
    const left = (xored << BigInt((64 - rot) & 63)) & MASK64;
    return (right | left) & MASK64;
  }

  /** @returns {bigint} 32-bit unsigned (low 32 of nextU64). */
  nextU32() {
    return this.nextU64() & MASK32;
  }

  /** @returns {number} Uniform float in [0, 1) with 53 bits of precision. */
  random() {
    // Match Python: (next_u64() >> 11) * 2**-53
    const top53 = Number(this.nextU64() >> 11n);
    return top53 * _FLOAT_DIVISOR;
  }

  /**
   * @param {number} lo
   * @param {number} hi
   * @returns {number} Uniform float in [lo, hi).
   */
  uniform(lo, hi) {
    return lo + (hi - lo) * this.random();
  }

  /**
   * @param {number} lo
   * @param {number} hi
   * @returns {number} Uniform int in [lo, hi] inclusive.
   */
  randint(lo, hi) {
    if (hi < lo) {
      throw new Error(`randint: hi (${hi}) < lo (${lo})`);
    }
    const n = BigInt(hi - lo + 1);
    return lo + Number(this.nextU64() % n);
  }
}

/**
 * Construct a PCG64 deterministically from a 40-bit seed integer.
 *
 * Mirrors `seeded_rng` in pcg.py. Seeding follows the canonical pcg-cpp
 * setseq pattern so small seed values still produce well-mixed initial
 * output.
 *
 * @param {bigint | number} seed
 * @returns {PCG64}
 */
export function seededRng(seed) {
  const seedInt = BigInt(seed) & MASK128;
  const rng = new PCG64(_DEFAULT_INC, _DEFAULT_INC);
  rng._step();
  rng.state = (rng.state + seedInt) & MASK128;
  rng._step();
  return rng;
}
