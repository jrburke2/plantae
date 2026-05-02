# Plant simulator

Algorithmic plant simulator built on **L-Py + OpenAlea** (substrate validated by 2026-05-02 spikes — score +9 on Echinacea, 4/4 PASS on Andropogon).

YAML in, OBJ + JSON sidecar out (glTF later — see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)), slider scrubs continuous-time growth in a browser.

See `algorithmic_plant_simulator_design_v0.3.1.md` for the architecture, and `phase_0_implementation_kickoff.md` for the build plan.

## Phase 0 status

In progress. Step 0 (export-format gate) complete; OBJ + JSON sidecar selected over glTF after `openalea.plantgl` was found to have no glTF codec. Step 1 scaffolds the repo. Subsequent steps implement schema, codegen, exporter, viewer.

## Setup (Apple Silicon)

```bash
CONDA_SUBDIR=osx-64 mamba env create -f environment.yml
mamba activate plant_sim
mamba config --env --set subdir osx-64
plant-sim --help
```

On Linux/Windows/Intel mac, drop the `CONDA_SUBDIR=` prefix.

## What works today

```
plant-sim --help        # CLI surface (subcommands stub out until later steps)
```
