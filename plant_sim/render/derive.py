"""Thin wrappers around L-Py + PlantGL.

Phase 0:
  load_lsystem(lpy_path)                    -> Lsystem
  derive(lpy_path, render_ctx=None)         -> (Lsystem, lstring)
  interpret(lsys, lstring, t_render)        -> Scene

The derive step is paid once per (species, seed). Slider scrubs only call
interpret, which is 1-2 ms per frame per the spike findings.

L-Py is imported lazily so that schema/codegen tests don't pay the
~600 ms import cost.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from plant_sim.schema.render_context import RenderContext

if TYPE_CHECKING:  # pragma: no cover
    from openalea.lpy import Lsystem
    from openalea.plantgl.scenegraph import Scene


def load_lsystem(lpy_path: Path | str) -> "Lsystem":
    from openalea.lpy import Lsystem
    return Lsystem(str(lpy_path))


def _apply_render_ctx(lsys: "Lsystem", render_ctx: RenderContext) -> None:
    """Push RenderContext fields into the Lsystem context as externs."""
    ctx = lsys.context()
    # Names must match the externs declared in templates/archetypes/README.md.
    ctx["SPECIMEN_SEED"] = render_ctx.seed
    ctx["TIME_OFFSET_DOY"] = float(render_ctx.time_offset_doy)
    ctx["EMERGENCE_OFFSET"] = float(render_ctx.emergence_offset_days)
    ctx["POSITION_X_M"] = float(render_ctx.position_x_m)
    ctx["POSITION_Y_M"] = float(render_ctx.position_y_m)
    ctx["POSITION_Z_M"] = float(render_ctx.position_z_m)


def derive(
    lpy_path: Path | str,
    render_ctx: RenderContext | None = None,
) -> tuple["Lsystem", Any]:
    """Load the .lpy, push render context as externs, run derive() once.

    Returns the Lsystem instance + the derived lstring. Cache both per
    (species, seed) for slider scrubbing — the lstring does not depend
    on T_RENDER.
    """
    lsys = load_lsystem(lpy_path)
    if render_ctx is not None:
        _apply_render_ctx(lsys, render_ctx)
    lstring = lsys.derive()
    return lsys, lstring


def interpret(lsys: "Lsystem", lstring: Any, t_render: float) -> "Scene":
    """Run interpretation at the given fractional DOY. Cheap; per-frame call."""
    lsys.context()["T_RENDER"] = float(t_render)
    return lsys.sceneInterpretation(lstring)
