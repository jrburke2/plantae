"""Cross-language runtime primitives for plantae generation.

Anything in this package must have a bit-identical TypeScript twin in
`viewer/`. The Python side is the reference; the TS side chases parity.
Cross-runtime parity tests live in `tests/test_pcg_vectors.py` (Python emit)
and `viewer/test/parity.test.mjs` (Node consume).
"""
