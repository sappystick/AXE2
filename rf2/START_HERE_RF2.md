# RF2 clean-sheet head: start here (for a new Claude session or account)

This page takes a fresh cloud container (or a Linux / WSL machine) from nothing to the exact point where the last session stopped. Follow it top to bottom. Everything here is **MODELED / tool-checked**: there has been no fabricator DRC, no CAM review and no bench test.

## 0. What RF2 is (one paragraph)

RF2 is a side experiment inside the Arx / PHI-FOLD 233 repo: a clean-sheet 1-inch (25.4 mm) detector head of the existing 233 mm diameter.
- **Transmit / receive:** a 26-turn rim mono coil (333 uH, 8.06 A, 10.8 mJ per pulse) transmits and receives.
- **Quadrupole receivers:** two boards, SB1R-QA / QB, give bearing and pinpoint.
- **Shielding and reference:** a split-ring shield board (SH1) and a 3-axis reference coil on the shaft (REF3).
- **Sectors:** the head is divided into HV (156-198 deg), analog (89-156 deg) and digital (the rest).

Nothing in RF2 changes the baseline design (`docs/`, `src/`), which has its own sign-off (`make signoff`).

## 1. Get the code

```bash
git clone https://github.com/sappystick/ARX.git && cd ARX
git checkout claude/hopeful-bell-wms3xo        # the RF2 working branch (latest RF2 commits)
git log --oneline -5                           # newest first; compare with section 6
```

In a Claude Code cloud session the repo is already cloned. Check out the branch above, or the branch the owner names.

## 2. Install every tool (one command, about 10 min, about 4 GB)

```bash
RF2_TOOLS=1 scripts/bootstrap.sh               # same as: make rf2-tools
```

The script is idempotent and only adds packages. It ends with a self-test that must print `environment OK` and an `rf2 tools` line.

| Layer | What gets installed | Why |
|---|---|---|
| KiCad 9 (PPA, added by hand) | kicad, kicad-cli, the pcbnew Python module | board build, DRC, Gerbers |
| KiCad libraries (apt) | kicad-footprints, kicad-symbols, kicad-packages3d (3.3 GB of STEP / VRML) | real footprints and 3D part models |
| Python (requirements.txt) | numpy, scipy, matplotlib, pillow, gerbonara, shapely, manifold3d ... | every generator and check |
| Python (requirements-rf2.txt, pinned) | kiutils 1.4.8, cadquery 2.8.0, pyvista 0.49.2, trimesh 5.2.0, magpylib 6.0.1, spicelib 1.6.4, meshio 5.3.5, InteractiveHtmlBom 2.12.0 | schematics, STEP export, rendering, mesh tools, independent field code, SPICE driving, BOM pages |
| Simulation (apt) | ngspice 42, gmsh 4.12 | circuit simulation, meshing |
| Firmware (apt) | gcc-arm-none-eabi 13.2, libnewlib-arm-none-eabi | Pico / Cortex-M firmware builds |
| Off-screen GL (apt) | libosmesa6, libegl1, libgl1 | pyvista renders with no display |
| Router | openjdk-25-jre-headless, plus Freerouting 2.4.1 from Maven Central (sha256 pinned, `scripts/fetch_freerouting.sh`) | autorouting (`src/pcb/freeroute.py`) |

Known not to install on Python 3.13: kikit 1.8.1 and skidl 3.0.0 (legacy setup.py dependencies). kicad-cli covers panels and fab outputs, and kiutils covers schematics.

If a download fails, read `/root/.ccr/README.md` (the cloud proxy). GitHub release downloads are blocked in the cloud containers, which is why the Freerouting jar comes from Maven Central.

## 3. Rebuild and check everything RF2 has

```bash
make rf2-signoff                 # = python3 rf2/head/rf2_signoff.py ; writes rf2/STATUS_RF2.md
python3 tests/regress.py --allow-skip     # repo regression (baseline + RF2 rows)
```

The sign-off runs these, in order:
1. netlist consistency;
2. housing and seats (STL);
3. the SH1 shield board;
4. the SB1R variant (needs `make setup` and `make sbq-fast` in work/);
5. the routed boards TXJ, MP1 and LR1;
6. the magpylib field cross-check;
7. the MP1 ngspice protection study;
8. REF3 sizing;
9. housing checks;
10. wiring / power / timing;
11. the volume ledger;
12. netlist parity.

**Routing is incremental** (owner rule, 2026-10-30):
- A board is re-routed only when its netlist entry or `rf2_boards.py` changed (hash stored in its check file).
- When it is re-routed, `rf2_boards.resume_input` copies the copper of the last routed board onto the new build, except copper within 2 mm of a pad that moved.
- It then deletes only the items KiCad DRC flags, and Freerouting routes only the open connections.
- `RF2_FULL=1` forces a full route; `--cold` on rf2_signoff forces every board.
- If the pre-routes / template leave nothing open, no autorouter runs at all (`route.mode` = template).
- LR1 is the dense LED display (522 LEDs, 13 rings): layout, nets and copper all come from `head/rf2_ledgrid.py` (HANDOFF section 16). The earlier 42-LED ring used `head/rf2_ring_template.py` (kept for history): one cell per LED, the chain links, the power stubs and the 4 irregular links (hinge feeds, outer-to-inner jump). It routes in about 14 s and is deterministic. Freerouting stalled on this board (no pass completed in 5 min for 4 connections).
- Never delete a routed `PF233-RF2-*.kicad_pcb` by hand: it is the resume point.

Render the head (cut-away and exploded view from the generated geometry):

```bash
python3 rf2/head/rf2_render_pv.py      # out/rf2_cutaway.png, out/rf2_exploded.png
```

## 4. Read in this order

1. `CLAUDE.md`: the repo rules. Non-negotiable: change generators, never outputs; every claim gets a check; the eddy-current rule (no closed loops around the axis); the HV rule (>= 1.0 mm, 630 V parts); no fabricated datasheet facts.
2. `rf2/STATUS_RF2.md`: generated; what passes now.
3. `rf2/HANDOFF_RF2.md`: every part of the head, its function, numbers and assumptions.
4. `rf2/PARTS_RF2.md`: the part choices and which are VERIFIED.
5. `rf2/ENHANCEMENT_PLAN_RF2.md`: what to analyse and upgrade next, area by area.
6. `docs/design/DATASHEET_LOG.md`, section RF2-DS-MP1V2: verified values with document numbers.

## 5. Where the files are

| Path | What |
|---|---|
| `rf2/rf2_*.py` | physics studies (coil search, receiver combo, ground, EMI, timing, pinpoint, petal ring, disc RX); results in `results/` |
| `head/rf2_head.py` | SPEC (every dimension) and every printed part (manifold3d -> STL in `head/out/`) |
| `head/rf2_netlist.py` | the system netlist: the single source of truth for boards, parts, pins and harness |
| `head/rf2_boards.py` | builds each board in pcbnew, routes it (Freerouting, incremental), then KiCad DRC, the independent copper check (incl. no loop around the axis), parity and Gerbers |
| `head/rf2_shield_pcb.py`, `rf2_sb1r_variant.py` | SH1 shield and the SB1R outline variant |
| `head/rf2_head_check.py`, `rf2_wiring.py`, `rf2_ledger.py`, `rf2_parity.py` | housing, wiring, volume and parity checks |
| `head/rf2_mp1_spice.py`, `rf2_field_xcheck.py`, `rf2_ref3.py` | ngspice protection study, magpylib field check, REF3 sizing |
| `head/rf2_render.py`, `rf2_render_pv.py` | renders (numpy z-buffer; pyvista / VTK) |
| `head/rf2_signoff.py` | runs it all, writes STATUS_RF2.md |
| `data/seed/datasheets/` | manufacturer PDFs on disk (TI ones fetch normally; ADI, Microchip, Infineon, Littelfuse refused plain fetches on 2026-10-30) |

## 6. Where the last session stopped (2026-10-30)

| Item | Result |
|---|---|
| Phase A/B boards | TXJ and MP1 v1 routed, DRC 0. LR1 is a 2-layer flex section (vendor 0.10 / 0.10 mm rules), template-routed: DRC 0, 0 unconnected, min clearance 0.19 mm, no loop around the axis, parity OK, Gerbers. SH1 and the SB1R variant are clean. |
| LED display | LR1 = 522 SK9822-EC20 in 13 rings from the rim to the centre (rf2_ledgrid.py); DRC 0 / 0, own power-gated LED rail (LMR36520 + TPS22918, verified), 4 chains fit the quiet slot |
| Tools | installed and pinned (section 2); bootstrap self-test passes |
| MP1 v2 front end | ngspice study: a depletion-MOSFET limiter + 22 ohm gives 64 ohm in the signal path (1.03 nV/rtHz) against 1410 ohm (4.83 nV/rtHz) for v1 (generic models). Op-amp LMH6629 (0.69 nV/rtHz) and LDO TPS7A94 are now datasheet-VERIFIED. The depletion MOSFET (DN2470 class) is still UNVERIFIED because no vendor PDF could be fetched. |

**Next steps, in order:**
1. Get a depletion-mode HV MOSFET datasheet + SPICE model: ask the owner for the PDF (Microchip DN2470 or Littelfuse IXTP08N100D2).
2. Size the series resistor between the clamp node and the LMH6629 input (its abs max is +-10 mA input current, -0.5 V input) in `rf2_mp1_spice.py`.
3. Add MP1 v2 to `rf2_netlist.py`, then route and check it with `rf2_boards.py MP1`.
4. Phase C: AB1A / AB1B rework, CB1D routing, the neck driver and the coil ends, so the harness has no pending ends.
5. Real 3D models from `/usr/share/kicad/3dmodels` in the renders and the clearance checks.
6. Run the enhancement studies (ENHANCEMENT_PLAN_RF2.md).
7. Fabricator DRC, then the bench.

## 7. Working rules for the session

- Work on the branch the owner names. Commit with clear messages and push with `git push -u origin <branch>`. Never force-push. Open no PR unless asked.
- Before and after a change: `make rf2-signoff` and `python3 tests/regress.py --allow-skip`. Report any number that moved.
- Wording: MODELED / tool-checked. Never say "proven", "will detect" or "fabrication-ready".
- An earlier claim found wrong gets a row in `docs/CORRECTIONS.md`.
- Long jobs (routing): run one at a time in the background, and never kill other processes by pattern.
