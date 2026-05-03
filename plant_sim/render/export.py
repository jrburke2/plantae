"""Export PlantGL Scene to OBJ + JSON sidecar with material_id mapping.

Per Step 0's export-format decision (OPEN_QUESTIONS.md): PlantGL has no
glTF codec, so we output OBJ + a JSON sidecar mapping shape names to
material_ids. The viewer reads both.

Bridge (verified Step 0):
  PlantGL Shape.id is stable per-derivation (small integer per shape).
  PlantGL OBJ writer emits one `o SHAPEID_<id>_<addr>` per shape.
  We post-process the OBJ to rewrite `o SHAPEID_<id>_<addr>` -> `o SHAPE_<id>`
  so names are stable across renders (the addr suffix changes per process).
  Sidecar maps {SHAPE_<id> -> material_id} so the viewer can three.js-OBJLoader
  the OBJ, then iterate `obj.children` and look up each `mesh.name` in the sidecar.

material_id detection convention:
  Any module whose LAST parameter is a string is treated as a renderable
  module carrying that string as its material_id. The first parameter must
  be the module's birth time (t_birth or equivalent); the exporter uses it
  for the age-aware "did this module produce a shape?" check.

Phase 0 supports the rosette_scape_composite archetype's renderable module
shape; Step 8's tiller_clump archetype updates will follow the same
convention.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from openalea.lpy import Lsystem
    from openalea.plantgl.scenegraph import Scene


@dataclass
class ShapeMaterialEntry:
    name: str          # `SHAPE_<id>` — matches the rewritten OBJ group name
    shape_id: int      # PlantGL Shape.id
    material_id: str   # key into materials/library.json


# === Renderable-module detection (LAST-param-string convention) ===

def _module_renderable_info(module: Any) -> tuple[float, str] | None:
    """Return (t_birth, material_id) if this module is a renderable, else None.

    Convention:
    - First parameter must be birth time (numeric).
    - Last parameter must be material_id (string).
    - At least 2 parameters total.
    """
    try:
        name = module.name  # noqa: F841 — placeholder for future per-module logic
        params = list(module)
    except (AttributeError, TypeError):
        return None
    if len(params) < 2:
        return None
    t_birth = params[0]
    mat_id = params[-1]
    if not isinstance(t_birth, (int, float)):
        return None
    if not isinstance(mat_id, str):
        return None
    return float(t_birth), mat_id


def _renderables_in_lstring_order(lstring: Any) -> Iterable[tuple[float, str]]:
    """Walk the lstring and yield (t_birth, material_id) for each renderable module."""
    for module in lstring:
        info = _module_renderable_info(module)
        if info is not None:
            yield info


# === Age check matching the template's interpretation guard ===

def _renderable_produced_shape(
    t_birth: float, t_render: float, time_offset_doy: float, emergence_offset_days: float
) -> bool:
    """Whether this renderable contributes a non-degenerate shape to the Scene.

    Mirrors the template's `if age < 0: produce *` guard AND the behavior
    of `sigmoid_grow(age, ...) -> 0.0 when age <= 0`. PlantGL silently drops
    zero-extent geometry (~l(0), F(0), @O(0)), so age == 0 also yields no
    shape. Strict `age > 0` matches.
    """
    age = (t_render + time_offset_doy) - (t_birth + emergence_offset_days)
    return age > 0


# === OBJ post-processing: rewrite shape names to be stable across renders ===

_SHAPEID_RE = re.compile(r"^o SHAPEID_(\d+)_\d+\s*$", re.MULTILINE)


def _rewrite_obj_shape_names(obj_text: str) -> str:
    """Rewrite `o SHAPEID_<id>_<addr>` -> `o SHAPE_<id>` for stable names."""
    return _SHAPEID_RE.sub(r"o SHAPE_\1", obj_text)


# === Public export entry point ===

def export_to_obj_with_sidecar(
    lsys: "Lsystem",
    lstring: Any,
    t_render: float,
    output_obj_path: Path | str,
    *,
    sidecar_meta: dict | None = None,
) -> tuple[Path, Path]:
    """Render at t_render, write OBJ + JSON sidecar. Returns (obj_path, sidecar_path).

    The OBJ is post-processed to use stable per-id shape names. The sidecar
    JSON has structure:

        {
          "meta": {
            "t_render": 200.0,
            "scene_shape_count": 30,
            "lpy_file": "...",      # filled if sidecar_meta provided
            ...
          },
          "shapes": [
            {"name": "SHAPE_2", "shape_id": 2, "material_id": "leaf_mature_green"},
            ...
          ]
        }
    """
    output_obj_path = Path(output_obj_path)
    output_obj_path.parent.mkdir(parents=True, exist_ok=True)

    ctx = lsys.context()
    time_offset_doy = float(ctx.get("TIME_OFFSET_DOY", 0.0))
    emergence_offset_days = float(ctx.get("EMERGENCE_OFFSET", 0.0))

    # Set T_RENDER and run interpretation.
    ctx["T_RENDER"] = float(t_render)
    scene = lsys.sceneInterpretation(lstring)

    # Walk lstring, find renderables that produced shapes (age >= 0).
    rendered_renderables: list[str] = []
    for t_birth, mat_id in _renderables_in_lstring_order(lstring):
        if _renderable_produced_shape(t_birth, t_render, time_offset_doy, emergence_offset_days):
            rendered_renderables.append(mat_id)

    if len(rendered_renderables) != len(scene):
        # This is a real correspondence error; the exporter assumption broke.
        # Fail loudly so the bug doesn't silently produce a wrong sidecar.
        raise ExportError(
            f"Renderable/shape mismatch: lstring filter produced "
            f"{len(rendered_renderables)} renderables but Scene has "
            f"{len(scene)} shapes. The exporter's renderable-detection "
            f"convention may need updating, or interpretation is producing "
            f">1 shape per renderable module."
        )

    # Build sidecar entries
    entries: list[ShapeMaterialEntry] = []
    for shape, mat_id in zip(scene, rendered_renderables):
        sid = int(shape.id)
        entries.append(ShapeMaterialEntry(
            name=f"SHAPE_{sid}",
            shape_id=sid,
            material_id=mat_id,
        ))

    # Save OBJ via PlantGL, then post-process names.
    scene.save(str(output_obj_path))
    obj_text = output_obj_path.read_text(encoding="utf-8")
    output_obj_path.write_text(_rewrite_obj_shape_names(obj_text), encoding="utf-8")

    # Write sidecar
    sidecar_path = output_obj_path.with_suffix(".materials.json")
    meta = {"t_render": float(t_render), "scene_shape_count": len(scene)}
    # Pull template metadata from the L-Py context if present. Codegen
    # bakes TEMPLATE_ARCHETYPE / TEMPLATE_VERSION into every generated
    # .lpy as externs (V2 plan §4.3); surfacing them in the sidecar lets
    # the viewer show "(rosette_scape_composite v1.0.0)" next to the seed
    # and lets future scenes detect template-version drift.
    # LsysContext.get is a Boost.Python binding that requires an explicit
    # default — the dict-style single-arg form raises ArgumentError.
    arch = ctx.get("TEMPLATE_ARCHETYPE", None)
    ver = ctx.get("TEMPLATE_VERSION", None)
    if arch is not None:
        meta["template_archetype"] = str(arch)
    if ver is not None:
        meta["template_version"] = str(ver)
    if sidecar_meta:
        meta.update(sidecar_meta)
    sidecar_path.write_text(json.dumps({
        "meta": meta,
        "shapes": [
            {"name": e.name, "shape_id": e.shape_id, "material_id": e.material_id}
            for e in entries
        ],
    }, indent=2), encoding="utf-8")

    return output_obj_path, sidecar_path


class ExportError(RuntimeError):
    """Raised when the exporter's lstring/Scene correspondence assumption fails."""
