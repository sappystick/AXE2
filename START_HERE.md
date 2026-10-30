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
- **Passing:** every required step in `run.py` (see STATUS.md). The boards have DRC 0 and 0 unconnected; the housing (variants A, B and BF), wiring, power, LED timing, volume ledger, parity and zone-rule checks pass; the router self-test passes.
- **Done since the first handoff** (details: `rf2/HANDOFF_RF2.md` sections 19-29):
  - Rim-coil shape studies (taper, Rodin, wave) and the ferrite hood studies: none beats option B's plain rim coil; sections 19-23.
  - Option B housing (variant B, 15.65 mm) and the radial-fin clean sheet (variant BF); zone map and mitigation: sections 24-26.
  - Stage 3 parts, datasheet qualification, the fluxgate and decay-library work, and the **FEP litz** choice: sections 27-28.
  - **Light plate, interface, pod, construct** (section 30): opaque conical-well lid for the 522 LEDs, the signature-to-light-and-sound model with the 3-position selector and trigger, the handle pod, and the assembled model with the harness (`out_BF/construct/assembly.glb`).
  - **SPICE and acceleration** (section 31): TI LMH6629 model qualified against its datasheet (`rf2_opamp_qualify.py`); the MP1 v2 chain study found the 2026-10-30 design is **not closed** (amplifier input current 24 mA vs 10 mA, settling 19.5 us vs 16.3 us, noise 1.97 nV/rtHz per leg vs 1.7; docs/CORRECTIONS.md); the in-step result cache (`src/simcache.py`), runner `--why` / `--timing`, `make test`.
  - **Owner updates 2026-10-30** (section 32): power button on the pod; continuous boost checked part by part (open: switch heat sink, regenerative clamp, 4.2 W 630 V damping resistor, coil thermal model); display and audio coding v2 (size = blob radius, depth = pulse, several targets as separate blobs and voices, status screens); multi-target separation by decay time and by position.
  - **Stage 4:** `rf2_zonerules.py` (runner step `zonerules`) turns the zone rules into checks. **Stage 4b, first fin board:** TXF (TXJ as a fin). FEP litz and sleeves are in the head SPEC: section 29.
- **Still open, in order:**
  0. **MP1 v2 protection redesign first** (section 31): limiter candidates, clamp options, a 500 V cascode and the datasheet Coss(V) are all simulated there; none passes yet (best: IXTY01N100D with 2 x BAV199 + 2 x BAT54S per rail, 14.1 mA vs 10 mA and 17.5 us vs 16.3 us; settling is set by the limiter). Next: Rin2 150-220 ohm, a lower clamp rail, the limiter's recovery, or a later first gate, then re-run `study:mp1v2_protect`; also needs the LMH6629 WSON-8 land pattern, and the IXTY / BAV199 vendor models if they can be obtained.
  1. **MP1 v2 as a fin board** (HV1 at 170 deg). Parts decided (docs/INGEST_2026-10-30.md): IXTY08N100D2 limiter, Rin2 100 ohm, LMH6629. Blocked on the LMH6629 stage topology (it is a single op-amp; no SPICE model in the repo), its WSON-8 land pattern, and the TO-252 tab orientation on an 8.4 mm fin (section 29). Put them in `rf2_netlist.py`, then route and check (HV 1.0 mm).
  2. **Phase C.** AB1A / AB1B / CB1D as fins (area budget: analog 32 cm2, digital 85 cm2), CB1D routing (with the display's LMR36520 + TPS22918, the 12 hinge lands and the 4 LED chains), and the neck driver (333 uH / 8.06 A, 12.7 A boost) with the cable in the timing model.
  3. **Stage 5 and parts.** SiC switch with the UCC5350 driver, the AD7389-4 receiver, BAT15 pair option, temperature sensors; confirm with a vendor the FEP litz OD, wall and voltage rating.
  3b. **Pod parts and the interface:** choose the real switch, sounder (magnet-free), battery and shaft dimensions (pod is ASSUMED), measure the liner reflectance and the visible brightness under the receive-window duty, and route the MP1 / AB1 / CB1D harness once their fins exist.
  4. **Battery and runtime budget.** Covers the 7S pack, TX average power, the display, and every fuse and wire rating.
  5. **Fabricator DRC, then the bench** (fluxgate pair, ferrite settling, decay-curve recordings).

## 6. Working rules
See CLAUDE.md. In short:
- Change generators only; every claim gets a check; MODELED wording.
- No closed loop around the axis; HV ≥ 1.0 mm and 630 V parts; no unverified datasheet facts.
- One background job at a time; check progress at every step; commit and push often; never force-push.
