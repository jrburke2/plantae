"""FastAPI dev server for the plant_sim viewer.

Endpoints:

  GET /render/scene.obj?species=<id>&seed=<n>&t=<doy>
  GET /render/scene.materials.json?species=<id>&seed=<n>&t=<doy>
       OBJ + JSON sidecar pair for the requested specimen at that DOY.
       Both files render together on cache miss; subsequent requests for
       the same (species, seed, t) hit the disk cache.

  GET /materials/library.json
       Static material library file (mounted from materials/).

  GET /viewer/...
       Static three.js viewer (mounted from viewer/).

  GET /
       Redirects to /viewer/?species=echinacea_purpurea&seed=42

Caching:
  Per-process in-memory `_DERIVED_CACHE` keyed on (species, seed) holds the
  Lsystem + lstring. Slider scrubs only re-run sceneInterpretation; derive
  is paid once per (species, seed). For multi-process or production use,
  swap this for a real cache (Redis, file-based LRU). Phase 0 is single-
  process dev only.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from plant_sim.codegen.generator import load_species, write as codegen_write
from plant_sim.render.derive import derive
from plant_sim.render.export import ExportError, export_to_obj_with_sidecar
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.seed import Seed

# L-Py + boost::python is NOT thread-safe: concurrent Lsystem() calls from
# multiple threads abort with `libc++abi: terminating due to uncaught exception
# of type boost::python::error_already_set`. Starlette runs sync route handlers
# in a thread pool, so without this pin the server crashes on the first
# concurrent /render hit. Solution: a single-worker executor that serializes
# every L-Py touch onto one stable thread for the lifetime of the process.
_LPY_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lpy-worker")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPECIES_DIR = REPO_ROOT / "species"
OUTPUT_DIR = REPO_ROOT / "output"
GENERATED_DIR = REPO_ROOT / "generated"
MATERIALS_DIR = REPO_ROOT / "materials"
VIEWER_DIR = REPO_ROOT / "viewer"

# (species_id, canonical_seed_str) -> (Lsystem, lstring).
# Module-level so it survives across requests in a single uvicorn worker.
_DERIVED_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}


def _find_species_yaml(species_id: str) -> Path:
    """Locate species/<family>/<species_id>.yaml. 404 if missing."""
    if not species_id.replace("_", "").isalnum():
        raise HTTPException(400, f"invalid species_id {species_id!r}")
    matches = list(SPECIES_DIR.rglob(f"{species_id}.yaml"))
    if not matches:
        raise HTTPException(404, f"species {species_id!r} not found in {SPECIES_DIR}")
    if len(matches) > 1:
        raise HTTPException(500, f"multiple species files match {species_id}: {matches}")
    return matches[0]


def _parse_seed(raw: str) -> Seed:
    try:
        return Seed(raw)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"invalid seed {raw!r}: {e}")


def _ensure_derived(species_id: str, seed: Seed) -> tuple[Any, Any]:
    """Return cached (Lsystem, lstring); derive on first call for this (species, seed)."""
    key = (species_id, seed.canonical())
    if key not in _DERIVED_CACHE:
        sp_yaml = _find_species_yaml(species_id)
        sp = load_species(sp_yaml)
        lpy_path = codegen_write(sp, output_dir=GENERATED_DIR, seed=seed)
        lsys, lstring = derive(lpy_path, RenderContext(seed=seed))
        _DERIVED_CACHE[key] = (lsys, lstring)
    return _DERIVED_CACHE[key]


def _render_paths(species_id: str, seed: Seed, t_doy: int) -> tuple[Path, Path]:
    obj_path = OUTPUT_DIR / f"{species_id}_seed_{seed.canonical()}_t{t_doy:03d}.obj"
    sidecar_path = obj_path.with_suffix(".materials.json")
    return obj_path, sidecar_path


def _ensure_rendered(species_id: str, seed: Seed, t_doy: int) -> tuple[Path, Path]:
    """Render OBJ + sidecar fresh on every call (per kickoff §10).

    The lstring cache in `_ensure_derived` provides the real speedup —
    derive() and Lsystem load are both ~10x more expensive than interpret +
    file write. Skipping interpret on disk-cache-hit saves only a few ms
    per request and risks serving stale files from prior CLI runs.
    """
    obj_path, sidecar_path = _render_paths(species_id, seed, t_doy)
    lsys, lstring = _ensure_derived(species_id, seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        export_to_obj_with_sidecar(
            lsys, lstring, float(t_doy), obj_path,
            sidecar_meta={
                "species": species_id,
                "seed": seed.canonical(),
                "seed_display": seed.display(),
            },
        )
    except ExportError as e:
        raise HTTPException(500, f"export failed: {e}")
    return obj_path, sidecar_path


def reset_cache() -> None:
    """Clear the derived cache. Tests use this to reset between species."""
    _DERIVED_CACHE.clear()


def make_app() -> FastAPI:
    app = FastAPI(title="plant_sim dev server", version="0.0.1")

    def _validate_request(t: float) -> int:
        t_doy = int(t)
        if not (1 <= t_doy <= 366):
            raise HTTPException(400, f"t out of range 1..366: {t_doy}")
        return t_doy

    @app.get("/render/scene.obj")
    async def render_obj(species: str, seed: str = "42", t: float = 200.0):
        t_doy = _validate_request(t)
        seed_obj = _parse_seed(seed)
        loop = asyncio.get_running_loop()
        obj_path, _ = await loop.run_in_executor(
            _LPY_EXECUTOR, _ensure_rendered, species, seed_obj, t_doy,
        )
        return FileResponse(obj_path, media_type="text/plain")

    @app.get("/render/scene.materials.json")
    async def render_sidecar(species: str, seed: str = "42", t: float = 200.0):
        t_doy = _validate_request(t)
        seed_obj = _parse_seed(seed)
        loop = asyncio.get_running_loop()
        _, sidecar_path = await loop.run_in_executor(
            _LPY_EXECUTOR, _ensure_rendered, species, seed_obj, t_doy,
        )
        return FileResponse(sidecar_path, media_type="application/json")

    @app.get("/seed/random")
    def random_seed():
        """Return a fresh seed string. Viewer's 'new seed' button calls this."""
        s = Seed.random()
        return {"canonical": s.canonical(), "display": s.display()}

    @app.get("/seed/normalize")
    def normalize_seed(seed: str):
        """Parse a user-typed seed and return canonical + display forms.
        Used by the viewer's 'paste seed' input to round-trip user input.
        """
        s = _parse_seed(seed)
        return {"canonical": s.canonical(), "display": s.display()}

    @app.get("/health")
    def health():
        return {"status": "ok", "cache_size": len(_DERIVED_CACHE)}

    # Static mounts
    app.mount("/materials", StaticFiles(directory=str(MATERIALS_DIR)), name="materials")
    app.mount("/viewer", StaticFiles(directory=str(VIEWER_DIR), html=True), name="viewer")

    @app.get("/")
    def root(species: str = "echinacea_purpurea", seed: str | None = None):
        """Land on the viewer with a fresh random seed by default.

        BOI-style: every visit is a new specimen. If the user wants to keep
        a particular plant, they copy the seed (or the URL — `?seed=` is
        always present after the redirect). If they pass `?seed=` themselves
        in the URL, we honor it instead of generating a new one.
        """
        if seed is None:
            seed = Seed.random().canonical()
        return RedirectResponse(
            url=f"/viewer/?species={species}&seed={seed}"
        )

    return app


app = make_app()
