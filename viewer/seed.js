// Seed — bit-identical TS twin of plant_sim/schema/seed.py for the parts
// the browser runtime needs.
//
// 8-character Crockford base32, 40 bits. Same algorithm as the Python
// side; cross-runtime parity is gated by the Node parity test consuming
// the same JSON fixture both sides regenerate against.
//
// Surface kept minimal for V2.0: construct from int or canonical string,
// canonical/display/toInt accessors, and `derive(...salts)`. The
// hyphen/lowercase/Crockford-forgiveness parsing in pyland's Seed is for
// user-pasted input today handled by the server; port if/when the viewer
// owns seed parsing.

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const SEED_LEN = 8;
const SEED_BITS = SEED_LEN * 5;
// 40 bits — well below 2**53, so it fits in Number safely. Don't compute
// via `1 << 40` (JS shifts mod 32) or use bitwise & on values > 2**31.
const SEED_SPACE = 2 ** SEED_BITS; // 2**40
const SEED_MAX = SEED_SPACE - 1;
const DISPLAY_SPLIT = SEED_LEN / 2;

const ALPHABET_INDEX = (() => {
  /** @type {Record<string, number>} */
  const m = {};
  for (let i = 0; i < ALPHABET.length; i++) m[ALPHABET[i]] = i;
  return m;
})();

const _textEncoder = new TextEncoder();

/**
 * @param {number} n
 * @returns {string}
 */
function intToSeedString(n) {
  if (n < 0 || n > SEED_MAX) {
    throw new RangeError(`int ${n} out of range 0..${SEED_MAX}`);
  }
  const chars = [];
  for (let i = 0; i < SEED_LEN; i++) {
    chars.push(ALPHABET[n & 0x1F]);
    n = Math.floor(n / 32);
  }
  return chars.reverse().join("");
}

/**
 * @param {string} s
 * @returns {number}
 */
function parseCanonical(s) {
  if (s.length !== SEED_LEN) {
    throw new Error(
      `seed string ${JSON.stringify(s)} is ${s.length} chars; expected ${SEED_LEN}`,
    );
  }
  let n = 0;
  for (const c of s) {
    const v = ALPHABET_INDEX[c];
    if (v === undefined) {
      throw new Error(
        `invalid base32 char ${JSON.stringify(c)} in seed ${JSON.stringify(s)}`,
      );
    }
    n = n * 32 + v;
  }
  return n;
}

export class Seed {
  /**
   * @param {Seed | number | bigint | string} value
   */
  constructor(value) {
    if (value instanceof Seed) {
      this._int = value._int;
    } else if (typeof value === "bigint") {
      if (value < 0n) {
        throw new RangeError(`seed bigint must be non-negative, got ${value}`);
      }
      this._int = Number(value & ((1n << 40n) - 1n));
    } else if (typeof value === "number") {
      if (!Number.isInteger(value) || value < 0) {
        throw new RangeError(
          `seed number must be a non-negative integer, got ${value}`,
        );
      }
      // % not & — & is 32-bit in JS, would silently truncate the high 8 bits.
      this._int = value % SEED_SPACE;
    } else if (typeof value === "string") {
      this._int = parseCanonical(value);
    } else {
      throw new TypeError(
        `Seed accepts number, bigint, string, or Seed; got ${typeof value}`,
      );
    }
  }

  /** @returns {string} 8-char uppercase Crockford base32 */
  canonical() {
    return intToSeedString(this._int);
  }

  /** @returns {string} mid-string hyphen, e.g. 'XQF2-D6S1' */
  display() {
    const c = this.canonical();
    return `${c.slice(0, DISPLAY_SPLIT)}-${c.slice(DISPLAY_SPLIT)}`;
  }

  /** @returns {number} the underlying 40-bit integer */
  toInt() {
    return this._int;
  }

  /**
   * Deterministic child seed from (this, salts...).
   *
   * Same parent + same salts always returns the same child. Different
   * salts produce uncorrelated children.
   *
   * Encoding (must mirror seed.py exactly):
   *
   *   sha256(
   *     parent.canonical (ASCII)
   *     || NUL || tag(salt_1) || bytes(salt_1)
   *     || NUL || tag(salt_2) || bytes(salt_2) ...
   *   )[:5]   // first 5 bytes, big-endian → 40-bit Seed
   *
   * Tags: "s" + UTF-8 for str, "i" + 8-byte big-endian unsigned for int.
   * NUL separator + per-salt tag prevents derive("ab") colliding with
   * derive("a","b") and derive("42") colliding with derive(42).
   *
   * SHA-256 is used because both runtimes get it native (Python stdlib /
   * browser Web Crypto). Changing the hash is a breaking change to every
   * committed seed-derived artifact.
   *
   * Async because crypto.subtle.digest is async. The viewer already
   * `await`s plenty; one more is fine.
   *
   * @param {...(string | number | bigint)} salts
   * @returns {Promise<Seed>}
   */
  async derive(...salts) {
    const parts = [_textEncoder.encode(this.canonical())];
    for (const s of salts) {
      if (typeof s === "boolean") {
        // Match Python: bool is rejected explicitly.
        throw new TypeError("salt must be string or int, not boolean");
      } else if (typeof s === "string") {
        parts.push(new Uint8Array([0x00, 0x73])); // NUL + "s"
        parts.push(_textEncoder.encode(s));
      } else if (typeof s === "number" || typeof s === "bigint") {
        const big = typeof s === "bigint" ? s : BigInt(s);
        if (typeof s === "number" && !Number.isInteger(s)) {
          throw new TypeError(`int salt must be an integer, got ${s}`);
        }
        if (big < 0n || big >= 1n << 64n) {
          throw new RangeError(`int salt must be in [0, 2**64); got ${s}`);
        }
        parts.push(new Uint8Array([0x00, 0x69])); // NUL + "i"
        const buf = new ArrayBuffer(8);
        new DataView(buf).setBigUint64(0, big, false); // big-endian
        parts.push(new Uint8Array(buf));
      } else {
        throw new TypeError(
          `salt must be string or int; got ${typeof s}`,
        );
      }
    }
    // Concat all parts into one Uint8Array
    const total = parts.reduce((n, p) => n + p.byteLength, 0);
    const buf = new Uint8Array(total);
    let offset = 0;
    for (const p of parts) {
      buf.set(p, offset);
      offset += p.byteLength;
    }
    const digest = new Uint8Array(
      await globalThis.crypto.subtle.digest("SHA-256", buf),
    );
    // Take first 5 bytes, big-endian → 40-bit int. Constructor masks to
    // 40 bits via modulo (Seed already enforces the range).
    let n = 0;
    for (let i = 0; i < 5; i++) {
      n = n * 256 + digest[i];
    }
    return new Seed(n);
  }
}
