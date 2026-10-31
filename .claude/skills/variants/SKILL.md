---
name: variants
description: Run, extend and learn from the AXE2 variant engine (every combination of design options, scored, with every broken rule at its location). Use when the owner asks to compare options, shuffle combinations, find the best variant, add a new component / integration / axis, or record an owner decision.
---

# AXE2 variant engine (multi-agent)

Files:
- `rf2/rf2_variant_axes.py`: core axes (one option per axis has `today=True`), plus `load_plugins()`.
- `rf2/variant_plugins/<domain>.py`: one plugin per domain, each owned by one agent (interface in `rf2/variant_plugins/README.md`). Current domains: coil_winding, boards, wiring.
- `rf2/rf2_variants.py`: the engine. It runs a full enumeration up to `--max-combos`, and above that a search (one-factor-at-a-time, random sample, then coordinate ascent). It scores with the `rf2_select` weights, finds the Pareto front and the per-objective champions, and appends to `rf2/results/variants_history.jsonl`. Outputs: `docs/VARIANTS.md`, `rf2/results/rf2_variants.json`, `rf2/results/rf2_variants_all.csv.gz`.
- `rf2/rf2_variant_learn.py`: main effects, the ridge surrogate with interactions, Monte Carlo robustness over the ASSUMED inputs, and owner-preference weights from `rf2/variant_decisions.json`. Outputs: `docs/VARIANTS_LEARNING.md` and `rf2/results/rf2_variant_weights.json`.
- `rf2/rf2_kb.py`: the knowledge base (SQLite FTS5 over every datasheet page, the DATASHEET_LOG parts, extracted parameters, every result JSON, formulas, modules and run.py steps). Use it to source every number: `python3 rf2/rf2_kb.py part <name> | search "<q>" | param <sym> | fact <key> | formula <word> | deps <file> | gaps`.

## Run
1. Build the knowledge base and run the engine:
   ```
   python3 rf2/rf2_kb.py build
   python3 rf2/rf2_variants.py
   python3 rf2/rf2_variant_learn.py
   ```
2. Variations:
   - fix an axis: `--fix shaft=tele_sq pack=C2`;
   - use the learned weights: `--weights learned`;
   - test one plugin: `--plugin-test <domain>`;
   - list the axes: `--list`.
3. Report from `docs/VARIANTS.md`: the champions (any status / breaks no rule), today's rank, and the top rows with their BREAKS text. Name every broken rule at its location; never exclude a variant because it breaks a rule. Safety rules are reported, never relaxed.

## Extend (multi-agent)
- **New option on an existing axis:** add it to the axis in `rf2_variant_axes.py`, or in the owning plugin.
- **New domain:** spawn one agent per domain, each writing only its own `rf2/variant_plugins/<domain>.py`. Each agent:
  - sources every number from the KB, a study JSON or a logged datasheet (else marks it ASSUMED / UNVERIFIED);
  - leaves today's machine unchanged with today's options;
  - tests with `--plugin-test`.
- **Afterwards:** run a critic agent that audits the plugins and the engine output for fabricated values, unit errors, missing rule rows and today-baseline drift. Then the orchestrator runs the engine and the learning layer, runs `python3 run.py`, and reports every number that moved.
- **Record every owner choice between existing options** in `rf2/variant_decisions.json`. The learning layer re-fits the weights from it.

## Agent roles and solver stack (owner 2026-10-31)
Spawn one agent per role. Every agent sources its numbers from the KB and writes only its own files.

| Role | Owns | Tools (installed by `make tools`) |
|---|---|---|
| Architect | Axes, weights, decisions. Runs `rf2_variants.py`, `rf2_variant_learn.py` and `rf2_variant_optuna.py` (NSGA-II, an independent second search). | numpy, scipy, optuna |
| Draftsman | Parametric geometry and meshes. | cadquery (STEP / STL), gmsh, pyvista, sympy, shapely, manifold3d, KiCad / Freerouting / A* for boards |
| Solver | Fields and parasitics. | magpylib, `concepts/clib.py` (Neumann / Maxwell), FastHenry / FastCap (`/opt/solvers`), scikit-fem, fipy, the 2D section solver `rf2_hex_section.py` |
| Electrician | Drive, receive, power. | ngspice (+ PySpice / spicelib), scikit-rf, `rf2_txd_spice.py`, `rf2_continuous.py`, `rf2_mp1v2_*` |
| Critic | Audits every plugin and run. | The KB, plus re-running checks. Writes `docs/VARIANTS_AUDIT.md`. |

- **Cross-checks:** `rf2/rf2_solver_xcheck.py` (FastHenry coil and strips, SymPy formula checks, scikit-rf line).
- **Elmer FEM, OpenEMS, Meep, FEniCS:** not installed; Elmer and OpenEMS need source builds. Add them through `scripts/fetch_solvers.sh` when a study needs 3D eddy currents in conductive bodies.
- **Targets:** come from the owner and the rules (CLAUDE.md), never from concept text. The Hyperion study ruled out the 1/r² focus and the sub-0.8 µs settle (`docs/HYPERION_EVALUATION.md`), so they are not targets.
