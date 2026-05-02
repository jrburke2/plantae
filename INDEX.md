# plantae — docs bundle

Snapshot taken 2026-05-02. Code lives at https://github.com/jrburke2/plantae.

## Read in this order

| # | File | What it is |
|---|---|---|
| 00 | REQUIREMENTS.md | **Start here.** Consolidated functional + architectural + non-functional requirements across all docs. The single source of truth for what plantae does, what's locked in, what's planned, what's deferred. Now includes the Seams section (S1–S11) enumerating active and resolved structural cuts, and the Plant Output & Export section (F43–F47, F53). |
| 01 | README.md | Project orientation, quick demo, layout, CLI reference. |
| 02 | V2_BROWSER_RUNTIME_PLAN.md | The plan to migrate from server-side L-Py to browser-side TypeScript generation. Path C with transitional hybrid. |
| 03 | OPEN_QUESTIONS.md | Running log of architectural decisions made during Phase 0 + V2 planning, with rationale. Now includes audit-against-principles items (a–e) and scene/key-specimen/export schema sub-questions. |
| 04 | CONTRIBUTING_botanist.md | How non-technical contributors add a species: YAML workflow, no code required. |
| 05 | CONTRIBUTING_developer.md | How developers extend the pipeline: archetypes, growth functions, materials, schema. |
| 06 | templates_archetypes_README.md | Locked conventions for archetype-template authors (Y-up, meters, degrees, DOY, externs, the persistent-marker pattern). |
| 07 | materials_README.md | Material library schema (static color vs phenological color curves). |
| 08 | design_doc_v0.3.1.md | Source design doc — the original architecture vision authored before Phase 0. Some details superseded by Phase 0 + V2 decisions; see REQUIREMENTS.md for current truth. |
| 09 | phase_0_implementation_kickoff.md | Source kickoff doc for Phase 0. The 10-step plan that's now complete. |
| 10 | spike_1_echinacea_FINDINGS.md | Findings from the 2026-05-02 Echinacea spike that validated L-Py as the substrate (+9). |
| 11 | spike_2_andropogon_FINDINGS.md | Findings from the 2026-05-02 Andropogon spike (4/4 PASS) that validated L-Py for population-style architectures and discovered the persistent-marker pattern. |

## Sibling docs (cross-project)

| File | What it is |
|---|---|
| engineering_principles.md | Cross-project engineering principles (P1 usability, P2–P4 minima, P5–P7 architectural commitments). Applies to plantae, the regional native plant marketplace, and anything else built under this banner. One doc to prevent drift. |
| native_plant_marketplace_concept.md | Working sketch of the regional native plant marketplace business concept. Plantae's plant-list BOM is the procurement handoff to this product (seam S1). |

## Where to start by audience

- **You're a stakeholder/collaborator new to the project:** read 01, 00, 02 in that order.
- **You want to understand the architecture deeply:** read 00 (especially the Seams section), 02, 06, 10, 11.
- **You're a botanist contributor:** read 04 (and skim 01).
- **You're a developer contributor:** read 05, 06, 00; consult engineering_principles.md.
- **You want the source design vision:** read 08, 09 (note: superseded in places by 00, 02).

## Status as of snapshot

- **Phase 0:** complete. 125 tests passing. Two reference species online.
- **Phase 1 (more archetypes):** planned, not started.
- **V2 (browser runtime):** planned in 02, not started. Coexists with Phase 1 work.

### 2026-05-02 changes (this snapshot)

- REQUIREMENTS gained the Plant Output & Export F-section (F43–F47), the export CLI subcommand (F53), the Seams section (S11 entries), and inline principle tags where alignment is load-bearing.
- OPEN_QUESTIONS gained the plantae↔marketplace separation as a resolved discussion, the plant-output-and-export schema pending section, the scene-polygon and key-specimen-placement pending section, and the audit-against-principles pending section (items a–e, early reads).
- engineering_principles.md authored as new cross-project sibling doc.
- native_plant_marketplace_concept.md gained a "Plantae integration" section formalizing the BOM handoff seam (S1).
- README, V2 plan, developer contributing guide updated to reference the new structure.
