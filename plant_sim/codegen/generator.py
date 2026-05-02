"""YAML -> .lpy code generator.

Public API:
    load_species(yaml_path)             -> Species
    dispatch_template(species)           -> str (template path relative to templates/)
    render_archetype(species, render_ctx) -> str (rendered .lpy source)
    generate(species, seed=None)         -> str
    write(species, output_dir, seed=None, source_path=None) -> Path
    available_archetypes()               -> list[str]

The persistent-marker pattern is applied via Jinja macros in
`templates/macros/queryable.lpy.j2`. The codegen also runs the validator
(`plant_sim.codegen.validator.validate_lpy`) before writing; errors raise.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from plant_sim.codegen.validator import ValidationError, validate_lpy
from plant_sim.schema.render_context import RenderContext
from plant_sim.schema.species import Species

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

_ARCHETYPE_TO_TEMPLATE = {
    "rosette_scape_composite": "archetypes/rosette_scape_composite.lpy.j2",
    "tiller_clump": "archetypes/tiller_clump.lpy.j2",
}


def available_archetypes() -> list[str]:
    return sorted(_ARCHETYPE_TO_TEMPLATE)


def load_species(yaml_path: Path | str) -> Species:
    return Species.from_yaml(yaml_path)


def dispatch_template(species: Species) -> str:
    """Pick the template path for a species. Honors `template_override`."""
    if species.template_override:
        return species.template_override
    try:
        return _ARCHETYPE_TO_TEMPLATE[species.archetype]
    except KeyError as e:
        raise NotImplementedError(
            f"No template for archetype {species.archetype!r}. "
            f"Available: {available_archetypes()}. "
            f"To use a custom template set `template_override:` in the species YAML."
        ) from e


def _build_meters_dict(species: Species) -> dict:
    """Pre-convert all length-typed fields to meters (canonical internal unit).

    Templates reference `m.<block>.<field>` (always meters) instead of
    calling species.units.length_to_meters() inline. Concentrates the
    unit conversion in one place so templates stay unit-agnostic.
    """
    convert = species.units.length_to_meters

    out: dict = {
        "height_min": convert(species.height_range[0]),
        "height_max": convert(species.height_range[1]),
        "crown_width_min": convert(species.crown_width[0]),
        "crown_width_max": convert(species.crown_width[1]),
    }

    p = species.parameters
    if hasattr(p, "rosette"):
        out["rosette"] = {
            "leaf_length_min": convert(p.rosette.leaf_length_range[0]),
            "leaf_length_max": convert(p.rosette.leaf_length_range[1]),
        }
        if p.rosette.petiole_length_range:
            out["rosette"]["petiole_length_min"] = convert(p.rosette.petiole_length_range[0])
            out["rosette"]["petiole_length_max"] = convert(p.rosette.petiole_length_range[1])
    if hasattr(p, "scape"):
        out["scape"] = {
            "height_min": convert(p.scape.height_range[0]),
            "height_max": convert(p.scape.height_range[1]),
        }
    if hasattr(p, "inflorescence"):
        out["inflorescence"] = {
            "diameter_min": convert(p.inflorescence.diameter[0]),
            "diameter_max": convert(p.inflorescence.diameter[1]),
        }
    if hasattr(p, "clump"):
        out["clump"] = {
            "tiller_height_min": convert(p.clump.tiller_height_range[0]),
            "tiller_height_max": convert(p.clump.tiller_height_range[1]),
        }
    if hasattr(p, "panicle"):
        out["panicle"] = {
            "raceme_length": convert(p.panicle.raceme_length),
        }

    return out


def _build_render_extras(render_ctx: RenderContext) -> dict:
    return {
        "seed": render_ctx.seed,
        "time_offset_doy": render_ctx.time_offset_doy,
        "emergence_offset_days": render_ctx.emergence_offset_days,
        "position_x_m": render_ctx.position_x_m,
        "position_y_m": render_ctx.position_y_m,
        "position_z_m": render_ctx.position_z_m,
        "t_render_default": 200.0,  # peak DOY default; per-render slider overrides
    }


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_archetype(species: Species, render_ctx: RenderContext | None = None) -> str:
    """Render the archetype template for a species. Returns the .lpy source string."""
    if render_ctx is None:
        render_ctx = RenderContext()

    template_path = dispatch_template(species)
    env = _jinja_env()
    template = env.get_template(template_path)

    context = {
        "species": species,
        "render": _build_render_extras(render_ctx),
        "m": _build_meters_dict(species),
    }
    return template.render(**context)


def generate(species: Species, seed: int | None = None) -> str:
    """Convenience wrapper: render with a seed-only RenderContext."""
    render_ctx = RenderContext(seed=seed) if seed is not None else RenderContext()
    return render_archetype(species, render_ctx)


def _content_addressed_filename(species: Species, seed: int) -> str:
    """`<genus>_<species>_seed_<n>.lpy`. Source: scientific_name (deterministic)."""
    base = species.scientific_name.lower().replace(" ", "_").replace(".", "")
    return f"{base}_seed_{seed}.lpy"


def write(
    species: Species,
    output_dir: Path | str,
    seed: int | None = None,
    *,
    skip_validation: bool = False,
) -> Path:
    """Render + validate + write to disk. Returns the file path.

    Raises `ValidationError` if the rendered .lpy fails the syntax checks
    in `plant_sim.codegen.validator.validate_lpy` (unless `skip_validation`
    is set, which is meant for codegen development only).
    """
    seed_to_use = seed if seed is not None else 42
    source = generate(species, seed=seed_to_use)

    if not skip_validation:
        validate_lpy(source)  # raises ValidationError on errors

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / _content_addressed_filename(species, seed_to_use)
    path.write_text(source)
    return path
