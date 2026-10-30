# AXE2: start here (for a new Claude session or account)

This takes a fresh cloud container, or a Linux / WSL machine, to the exact point where the last session stopped. Everything is **MODELED / tool-checked**: there has been no fabricator DRC, no CAM review and no bench test.

## 1. Get the code
```bash
git clone https://github.com/sappystick/AXE2.git && cd AXE2      # in a Claude cloud session the repo is already cloned
```

## 2. Install every tool (one command, about 10 min, about 4 GB)
```bash
make tools          # = scripts/bootstrap.sh; must end with "environment OK"
```

| Layer | What gets installed | Why |
|---|---|---|
| KiCad 9 (PPA, added by hand) | kicad, kicad-cli, the pcbnew Python module | board build, DRC, Gerbers |
| KiCad libraries (apt) | footprints, symbols, 3D models (3.3 GB) | real parts and 3D models |
| ngspice 42, gmsh 4.12, ARM gcc 13 | apt | circuit simulation, meshing, firmware |
| off-screen GL | libosmesa6, libegl1, libgl1 | renders with no display |
| Java 25 + Freerouting 2.4.1 | apt + Maven Central jar (SHA-256 pinned) | autorouting |
| Python (pinned, `requirements.txt`) | numpy, scipy, matplotlib, shapely, gerbonara, manifold3d, kiutils, cadquery, pyvista, trimesh, magpylib, spicelib, meshio, InteractiveHtmlBom, scikit-fem, optuna | generators, checks, CAD / STEP, renders, fields, SPICE, FEM, parameter search |

In a Claude cloud session the SessionStart hook (`.claude/hooks/session-start.sh`) runs this automatically. GitHub release downloads are blocked in cloud containers, which is why the Freerouting jar comes from Maven Central.

## 3. Rebuild and check
```bash
python3 run.py --plan     # what would run and why
python3 run.py            # runs only what is needed; STATUS.md is regenerated
python3 run.py --failed   # after a failure: re-run only the failed steps
make route-test           # router self-test (rip 4 nets, A* reroute, KiCad DRC)
python3 run.py --with-render --with-studies   # renders and physics studies too
```
`state/ledger.json` (committed) records each step's last result, so a new session knows what passed and what failed without rerunning everything.

## 4. What the design is
- **Envelope:** D233 × 25.4 mm (1 inch).
- **Transmit and receive:** a 26-turn rim mono coil (333 uH, 8.06 A, 10.8 mJ per pulse) does both.
- **Bearing:** two quadrupole receive boards (SB1R-QA / QB, tab-less outline).
- **Shield:** the SH1 split-ring shield.
- **Boards:**
  - **MP1:** the mono preamp. v1 is routed with HV clearance 1.2 mm; v2 is designed but waits on a datasheet.
  - **TXJ:** the coil-lead terminal board, HV clearance 3.4 mm.
  - **LR1:** the display flex, 522 SK9822-EC20 in 13 rings from the rim to the centre, with its own power-gated LED rail.
- **Analog and control:** the analog sections AB1A / AB1B and the controller CB1D come from RF1 (`reference/rf1/`) and are reworked in Phase C.
- **Reference coil:** REF3, a 3-axis reference coil on the shaft.
- **Sectors:** HV 156-198 deg, analog 89-156 deg, digital the rest.

## 5. Where the last session stopped (2026-10-30)
- **Passing:** every required step in `run.py` (see STATUS.md). The boards have DRC 0 and 0 unconnected; the housing, wiring, power, LED timing, volume ledger and parity checks pass; the router self-test passes.
- **Still open, in order:**
  1. **MP1 v2.** Needs the depletion-mode HV MOSFET datasheet + SPICE model (DN2470 or IXTP08N100D2), then the series resistor sized against the LMH6629 input limits (±10 mA, -0.5 V).
  2. **Phase C.** CB1D routing (with the display's LMR36520 + TPS22918, the 12 hinge lands and the 4 LED chains), the AB1A / AB1B rework, and the neck driver (333 uH / 8.06 A, 12.7 A boost) with the cable in the timing model.
  3. **Battery and runtime budget.** Covers the 7S pack, TX average power, the display, and every fuse and wire rating.
  4. **Enhancement studies** (`rf2/ENHANCEMENT_PLAN_RF2.md`). The first two are the winding capacitance → first gate, and the display: pinpoint centre-offset error and LED-to-receiver coupling.
  5. **Fabricator DRC, then the bench.**

## 6. Working rules
See CLAUDE.md. In short:
- Change generators only; every claim gets a check; MODELED wording.
- No closed loop around the axis; HV ≥ 1.0 mm and 630 V parts; no unverified datasheet facts.
- One background job at a time; check progress at every step; commit and push often; never force-push.
