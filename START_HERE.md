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
  - **Display v3 and the flip-up screen** (section 33): small dots and a centre lock while sweeping, a sonar ring with echoes when the trigger is held, light and sound on one clock, 4 LED and 4 audio profiles; a push-release flip-up 128 x 128 screen cassette behind the power button.
  - **Datasheet batch 3** (section 34, DATASHEET_LOG RF2-DS-OWNER3; 21 owner PDFs):
    - Keep the BAT54S pair in the MP1 v2 clamp. A worst-case BAV199 recovery (trr 3 us) stretches the single-BAV199 settling to 21.4 us.
    - Nexperia US3M is a second source for the clamp diode; the ARF RF MOSFETs and the 650 V D2PAK rectifiers are not adopted.
    - Heat sink TJ 101 C. The DRV425 roughly halves the ferrous-channel ranges.
    - Candidates: BQ76952, LTC4365, TMP117, UCC28780, KSC2 TE.
    - The Murata piezos are 4 kHz resonant and end-of-life.
  - **Audio, system layout and pod v2** (section 35):
    - Magnet-free piezo with tones moved to 3.0-7.6 kHz.
    - Four sealed modules: HEAD, TXD, POD, PACK.
    - The TX driver moved up the shaft (s 255-345 mm) by an echo search.
    - BQ76952 is the main power switch; PM2, LTC4365 and AU1 are removed.
    - 7S2P pack: 7.8 h scan.
    - The pod's electronics are placed in the annulus around the tube; the v1 bore fault is fixed.
    - Next: rf2_timing with the TX pair, regenerative buck SPICE, RS-485 part, screen datasheet.
  - **Upper assembly v1 and REF3 sleeve** (section 36; `docs/SYSTEM_TOPOGRAPHY.md` for where every station stands):
    - Ergonomic grip, pilot trigger, flip-up screen and quick-swap battery are modeled and checked.
    - The REF3 box became a sleeve on the shaft.
    - The TX driver is at s 330-420.
    - NEXT (owner): telescoping instead of folding, a working cuff (straight forearm line), flex in the shaft channels.
  - **Chassis v2** (section 37, `rf2/rf2_chassis.py`):
    - SDC 2300-style hinged telescopic chassis with three keyed rectangular profiles.
    - REF3 coils sit in the outer profile.
    - The TX driver is in the chassis.
    - The inverted control-stick grip has the cuff on one straight forearm line.
    - Folds to 497 x 249 x 186 mm.
  - **ICD + cable timing + datasheets + slim-down** (section 38):
    - `docs/ICD.md` (12 interfaces) and `docs/PROTOTYPE_ROADMAP.md` (1 / 40 done).
    - First gate +0.19 us with the cord.
    - Screen and RS-485 chosen; Rd = 2 x PR03 806 ohm.
    - Shaft profiles 31 / 26 / 21 mm; chassis 62 x 31 mm; folds 494 x 233 x 160 mm.
  - **Roadmap 4 / 40** (section 39):
    - EMI re-run done.
    - MP1 v2: current fixed by 1.0 / 4.0 V clamp rails; settling 1.0 us late.
    - Connectors verified: JST GH, Panasonic Y5B.
    - Printable yoke and cuff pass DFM; the head lid fails on thin light-plate webs.
  - **Roadmap 6 / 40** (section 40):
    - MP1 v2 settling closed in SPICE: 13.66 us vs the 16.48 us first gate, using +-12 V clamp rails and a series isolation switch. Parts: TMUX7212, TPS65131, TL431 (worst case 14.58 us).
    - The DFM wall metric is now max(ray, inscribed sphere).
    - Lid light plate 2.4 mm with a 0.9 mm land: the lid passes, head 16.55 mm, optics 0.825.
  - **Integration matrix** (section 47, `docs/INTEGRATION_MATRIX.md`):
    - Every owner source mapped to every area.
    - SDC cam-lever clamp adopted.
    - Shaft walls 1.2 mm would save 50 g (proposed).
    - HV notebook rules: aged Kapton 2000 V/mil.
  - **Minco / Gore** (section 46):
    - Cord-flex insulation is based on Minco data (hipot >= 1000 VRMS on the drawing), so P0.1 closes; readiness 7 / 40.
    - Flex-Coil REF3 is feasible but not adopted; Gore coax is rejected.
  - **Owner decisions applied** (section 45):
    - Cord is a split long flex: first gate +0.14 us.
    - BeCu dock fingers.
    - Coil is 6 rows x 5 columns of 1000 V triple-FEP litz (0.60 ohm); head 759 g.
  - **Flex / etch brochures** (section 44, `rf2_flex_options.py`):
    - A long flex cord fits and is 76 g lighter (owner to adopt).
    - Shield cans in the head are rejected (eddy echo).
    - BeCu dock fingers proposed.
  - **Wire datasheets** (section 43, `rf2_wire_options.py`):
    - The coil resistance is corrected from 0.53 to 0.601 ohm.
    - The coil cord with every conductor needs 10 mm, against the 7 mm spec.
    - Rule-6 near-misses on 600 V litz and TX pair wire wait for an owner decision.
  - **Pack 7S1P Molicel P45B, rated on continuous boost** (section 42):
    - Runtime: 3.6 h boost / 5.9 h scan; the 6 h target is relaxed by the owner.
    - System 2500 g; the drill-style dock is not drawn yet.
    - Rule near-miss report: `docs/RULE_NEAR_MISSES.md`, listed in every report.
  - **Drill-style rail pack study** (section 41, `rf2_pack_options.py`):
    - The rail is feasible: about -60 g with the same cells.
    - An RC LiPo is heavier, not lighter.
    - The weight saver is a 7S1P 21700 pack (LG M50T): -249 g, 6.57 h scan, torque about the hand +0.26 N m.
  - **Owner updates 2026-10-30** (section 32): power button on the pod; continuous boost checked part by part (open: switch heat sink, regenerative clamp, 4.2 W 630 V damping resistor, coil thermal model); display and audio coding v2 (size = blob radius, depth = pulse, several targets as separate blobs and voices, status screens); multi-target separation by decay time and by position.
  - **Stage 4:** `rf2_zonerules.py` (runner step `zonerules`) turns the zone rules into checks. **Stage 4b, first fin board:** TXF (TXJ as a fin). FEP litz and sleeves are in the head SPEC: section 29.
- **Still open, in order:**
  0. **MP1 v2 protection: closed in SPICE** (section 40). Parts chosen and re-checked with datasheet values: TMUX7212 switch, TPS65131 +15 / -10 V, TL431 clamp rails +14 / -9 V; worst settling 14.58 us. Next: an EMI study of the TPS65131's 1.25-1.5 MHz switching, TL431 stability, the switch noise, switch timing from CB1D, and the LMH6629 WSON-8 land pattern.
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
