"""plant-sim CLI entry point.

Phase 0 progress:
  validate     [Step 2]  schema-validate a YAML (species, mix, or scene); cross-checks for mix/scene
  schema-json  [Step 2]  emit JSON Schema for IDE tooling
  generate     [Step 4]  YAML -> .lpy (calls codegen, runs validator, writes file)
  render       [Step 5]  .lpy -> OBJ + materials.json sidecar (stub)
  serve        [Step 7]  dev server with live slider viewer (stub)
"""

import json
import sys
from pathlib import Path

import click
import yaml
from pydantic import ValidationError as PydanticValidationError

from plant_sim.codegen.cross_check import (
    MixLibrary,
    SpeciesLibrary,
    check_mix_against_species,
    check_scene_against_libs,
)
from plant_sim.codegen.generator import (
    available_archetypes,
    load_species,
    write as write_lpy,
)
from plant_sim.codegen.validator import (
    MaterialCrossCheck,
    ValidationError as LpyValidationError,
    collect_material_ids,
)
from plant_sim.schema.mix import Mix
from plant_sim.schema.scene import Scene
from plant_sim.schema.seed import Seed
from plant_sim.schema.species import Species

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MATERIALS_LIB = REPO_ROOT / "materials" / "library.json"
DEFAULT_SPECIES_DIR = REPO_ROOT / "species"
DEFAULT_MIX_DIR = REPO_ROOT / "mixes"


def _detect_yaml_kind(yaml_path: Path) -> str:
    """Return 'species', 'mix', 'scene', or 'unknown' based on top-level keys."""
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return "unknown"
    if "scientific_name" in data:
        return "species"
    if "boundary" in data:
        return "scene"
    if "components" in data:
        return "mix"
    return "unknown"


@click.group()
@click.version_option("0.0.1", prog_name="plant-sim")
def main() -> None:
    """Algorithmic plant simulator: YAML in, OBJ + materials out, slider works."""


@main.command()
@click.argument("yaml_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--species-dir", type=click.Path(exists=True, file_okay=False),
              default=str(DEFAULT_SPECIES_DIR),
              help="Species library root (used for mix/scene cross-checks).")
@click.option("--mix-dir", type=click.Path(file_okay=False),
              default=str(DEFAULT_MIX_DIR),
              help="Mix library root (used for scene cross-checks). Missing dir is OK.")
def validate(yaml_file: str, species_dir: str, mix_dir: str) -> None:
    """Schema-validate a YAML (species, mix, or scene) and run cross-checks.

    Detects the YAML kind by top-level keys:
      scientific_name -> species; boundary -> scene; components -> mix.
    """
    path = Path(yaml_file)
    kind = _detect_yaml_kind(path)

    if kind == "species":
        try:
            sp = load_species(path)
        except PydanticValidationError as e:
            click.echo(f"INVALID: {yaml_file}", err=True)
            click.echo(str(e), err=True)
            sys.exit(1)
        click.echo(f"OK: {yaml_file}")
        click.echo(f"  scientific_name : {sp.scientific_name}")
        click.echo(f"  archetype       : {sp.archetype}")
        click.echo(f"  units.length    : {sp.units.length}")
        click.echo(f"  height_range    : {sp.height_range} ({sp.units.length_range_to_meters(sp.height_range)} m)")
        if sp.template_override:
            click.echo(f"  template_override: {sp.template_override}")
        return

    if kind == "mix":
        try:
            mix = Mix.from_yaml(path)
        except (PydanticValidationError, ValueError) as e:
            click.echo(f"INVALID MIX: {yaml_file}", err=True)
            click.echo(str(e), err=True)
            sys.exit(1)
        species_lib = SpeciesLibrary.load(species_dir)
        issues = check_mix_against_species(mix, species_lib)
        if issues:
            click.echo(f"INVALID MIX (cross-check): {yaml_file}", err=True)
            for i in issues:
                click.echo(f"  {i.message}", err=True)
            sys.exit(1)
        click.echo(f"OK: {yaml_file}")
        click.echo(f"  mix             : {mix.name}")
        click.echo(f"  components      : {len(mix.components)}")
        click.echo(f"  grade           : {mix.grade.value}")
        return

    if kind == "scene":
        try:
            scene = Scene.from_yaml(path)
        except PydanticValidationError as e:
            click.echo(f"INVALID SCENE: {yaml_file}", err=True)
            click.echo(str(e), err=True)
            sys.exit(1)
        species_lib = SpeciesLibrary.load(species_dir)
        mix_lib = MixLibrary.load(mix_dir)
        issues = check_scene_against_libs(scene, species_lib, mix_lib)
        if issues:
            click.echo(f"INVALID SCENE (cross-check): {yaml_file}", err=True)
            for i in issues:
                click.echo(f"  {i.message}", err=True)
            sys.exit(1)
        click.echo(f"OK: {yaml_file}")
        click.echo(f"  scene           : {scene.name}")
        click.echo(f"  coord_system    : {scene.boundary.coord_system}")
        click.echo(f"  species_mix     : {len(scene.species_mix)} entries")
        click.echo(f"  key_specimens   : {len(scene.key_specimens)}")
        return

    click.echo(
        f"ERROR: could not detect YAML kind for {yaml_file}. "
        f"Expected a species (scientific_name), mix (components), or scene (boundary).",
        err=True,
    )
    sys.exit(1)


@main.command("schema-json")
@click.option("--output", "-o", type=click.Path(dir_okay=False),
              default="species/_schema/species.schema.json",
              help="Output path for the species JSON Schema file.")
def schema_json(output: str) -> None:
    """Emit the species JSON Schema for IDE / yaml-language-server support."""
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schema = Species.model_json_schema()
    out_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    click.echo(f"Wrote {out_path}")


@main.command()
@click.argument("species_yaml", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(file_okay=False), default="generated",
              help="Directory to write the generated .lpy file into.")
@click.option("--seed", type=str, default="42",
              help=("Specimen seed. 8-char Crockford base32 like 'XQF2-D6S1' or "
                    "an integer for backward compat. Use 'random' to generate a fresh seed."))
@click.option("--materials-lib", type=click.Path(exists=True, dir_okay=False),
              default=str(DEFAULT_MATERIALS_LIB),
              help="Path to the materials library JSON file (for material_id cross-check).")
@click.option("--skip-material-check", is_flag=True,
              help="Skip cross-checking material_ids against the library.")
def generate(species_yaml: str, output: str, seed: str,
             materials_lib: str, skip_material_check: bool) -> None:
    """Generate an .lpy file from a species YAML.

    Pipeline:
      1. Schema-validate the YAML (Pydantic).
      2. Cross-check material_ids against the materials library (unless skipped).
      3. Render the archetype template to .lpy source.
      4. Static-validate the .lpy source (declared modules, single-line `-->`, color range).
      5. Write to <output>/<genus>_<species>_seed_<n>.lpy.
    """
    try:
        sp = load_species(species_yaml)
    except PydanticValidationError as e:
        click.echo(f"INVALID YAML: {species_yaml}", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    if sp.archetype not in available_archetypes() and not sp.template_override:
        click.echo(
            f"ERROR: archetype {sp.archetype!r} has no template yet. "
            f"Available: {available_archetypes()}. "
            f"Set `template_override:` in the species YAML to use a custom .lpy.j2.",
            err=True,
        )
        sys.exit(1)

    if not skip_material_check:
        checker = MaterialCrossCheck.load(materials_lib)
        issues = checker.check_ids(collect_material_ids(sp))
        if issues:
            click.echo(f"ERROR: material_id check failed against {materials_lib}:", err=True)
            for i in issues:
                click.echo(f"  {i}", err=True)
            sys.exit(1)

    # Resolve seed: 'random' -> fresh seed; otherwise parse string/int.
    if seed.lower() == "random":
        seed_obj = Seed.random()
    else:
        try:
            seed_obj = Seed(seed)
        except ValueError as e:
            click.echo(f"ERROR: invalid --seed {seed!r}: {e}", err=True)
            sys.exit(1)

    try:
        path = write_lpy(sp, output_dir=output, seed=seed_obj)
    except LpyValidationError as e:
        click.echo(f"ERROR: generated .lpy failed static validation:", err=True)
        for i in e.issues:
            click.echo(f"  {i}", err=True)
        sys.exit(1)

    click.echo(f"Wrote {path}  (seed: {seed_obj.display()})")


@main.command()
@click.argument("lpy_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--t", "t_render", type=float, default=200.0,
              help="T_RENDER (fractional DOY) at which to interpret.")
@click.option("--output", "-o", type=click.Path(file_okay=False), default="output",
              help="Directory to write the OBJ + materials JSON sidecar into.")
def render(lpy_file: str, t_render: float, output: str) -> None:
    """Derive + interpret + export OBJ + sidecar JSON."""
    from plant_sim.render.derive import derive
    from plant_sim.render.export import ExportError, export_to_obj_with_sidecar

    lpy_path = Path(lpy_file)
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    obj_path = out_dir / f"{lpy_path.stem}_t{int(t_render):03d}.obj"

    lsys, lstring = derive(lpy_path)
    try:
        obj_out, sidecar_out = export_to_obj_with_sidecar(
            lsys, lstring, t_render, obj_path,
            sidecar_meta={"lpy_file": lpy_path.name},
        )
    except ExportError as e:
        click.echo(f"ERROR: export failed: {e}", err=True)
        sys.exit(1)
    click.echo(f"Wrote {obj_out}")
    click.echo(f"Wrote {sidecar_out}")


@main.command()
@click.option("--port", type=int, default=8000)
@click.option("--host", type=str, default="127.0.0.1",
              help="Bind host. Default 127.0.0.1 (localhost-only). Use 0.0.0.0 for LAN.")
def serve(port: int, host: str) -> None:
    """Run the dev server with the live slider viewer.

    Open http://localhost:<port>/ in a browser. The root path redirects
    to /viewer/?species=echinacea_purpurea&seed=42; switch species or
    seed via URL params.
    """
    import uvicorn
    click.echo(f"plant_sim dev server starting on http://{host}:{port}")
    click.echo(f"  Viewer:  http://{host}:{port}/viewer/?species=echinacea_purpurea&seed=42")
    click.echo(f"  Health:  http://{host}:{port}/health")
    uvicorn.run("plant_sim.server.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
