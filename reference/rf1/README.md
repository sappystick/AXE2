# RF1: rigid-flex redesign, side experiment (started 2026-10-29)

**Status: MODELED side experiment, phase 1 done.** Not part of the sign-off, the pipeline, the regress suite or any release. The baseline design is read and never written: every input the study reads is recorded with its sha256 in `results/rf1_phase1.json` together with the baseline commit. Any generator that a later phase changes is first copied into `experiments/RF1_rigidflex/src/` and changed there.

**Fixed (owner, 2026-10-29):** receive coils SB1R-QA/QB, the HTA antenna, the six TX formers and their litz, every printed part. **Free:** how the electronics are split into boards and how they connect: flex, rigid-flex or the circular rigid boards.

## Concepts

| | A: catalog FFC (B12 decision) | B: soldered flex jumpers | C: head rigid-flex (RF1 main line) |
|---|---|---|---|
| What | separate rigid boards, 0.5 mm FFC + connectors at the duct edges | separate rigid boards, custom 2-layer flex strips soldered / hot-bar bonded to pads (no connector) | AB1A + AB1B + CB1D + LB1 one rigid-flex panel (6L rigid sections, 2L flex core), HTA a flex tail, SB1R leads a soldered flex jumper |
| Hand joints in the head (today 66) | 18 (LB1, HTA and SB1R wires stay; the link becomes 4 reflowed connectors) | 12 bonded ends | 5 |
| Boards testable alone | yes | yes | no (panel test + test pads) |
| Fab | standard | standard + simple flex | rigid-flex vendor, every change re-spins the panel |

## Phase 1 results (`rf1_study.py`, MODELED / mesh-checked)

| Question | Result |
|---|---|
| AB1 <-> CB1D link fit on the meshes (link_path_check, imported unchanged) | baseline IDC ribbon 6 / 16 FAIL; catalog FFC 0 / 14; rigid-flex hinge (0.2 mm, no connector) 0 / 14 |
| Headroom (rigid-flex hinge) | 10.4 mm under LB1 (ribbon -4.4, FFC 8.4), 7.2 mm under the septum (ribbon -2.6, FFC 5.2) |
| CB1D -> LB1 hinge, CB1D -> HTA tail | rise 10.6 / 15.9 mm, S-fold needs 8.0 mm at a 2.0 mm fold radius (10 x 0.2 mm): both fit; flex about 15 / 21 mm |
| Receive-coil lead pair, 60 mm | loop area 10.2 mm2 (AWG36 touching) to 60 mm2 (loose 1 mm) today, 3.0 mm2 fixed on a broadside flex pair; capacitance about 5 pF either way |
| Eddy rule 5 | the board graph is a tree (no closed loop around the axis); hatched planes in the hinges; FR4 / polyimide stiffeners only (the vendor also offers stainless and aluminium: excluded) |
| Vendor (Rigiflex pages, `ds/`) | D228 fits the 18 x 24 in panel; 0.10 / 0.10 mm trace / space covers our finest; 6L 1.6 mm rigid-flex with 1 oz is a listed build; polyimide er 4, DF 0.04, water absorption 2.9 % |

What this does **not** show yet: any change in leak, noise or detection. The loop-area ratio is geometry only; the pickup needs the TX field along the lead path (phase 2).

## Where the real improvement is

1. **Build quality and repeatability (large, near certain):** 66 -> 5 hand joints in the head; the receive-lead loop area becomes a fixed 3 mm2 instead of 10-60 mm2 that depends on dressing, so the air leak becomes a calibratable constant instead of a per-unit variable. This is the gain RF1 can deliver for sure.
2. **Receive chain clean-sheet (large, MODELED next):** the AB1 sections are laid out from scratch in RF1, so the known receive defects go in at the same time: VREF / VCM buffer stability (OPEN_ITEMS 30), OPA2211 input range (31), chip-orientation robustness (B11), header pad rings (33). These are performance items; the flex is what lets the layout start over without the header constraint.
3. **Digital noise next to the receive coils (medium, to be modeled):** the ADC SPI (SCLK >= 27.2 MHz) runs between hatched ground layers in the hinge instead of an open ribbon.
4. **Not changed by RF1:** TX (litz, 20 A, 460 V taps stay wire, rules 5 / 6), the shaft cords (a 356 mm telescoping stroke needs dynamic flex: not proposed), the neck and handle boards.

## Phases

1. **Done:** census, mesh fit, fold radii, lead loop area, loop check, vendor fit (`results/rf1_phase1.json`, `results/rf1_head_concept.png`).
2. Receive-lead pickup: copy `sbq_sim.py` into `src/`, add the flex-tail path and the TX field along it; leak and its spread (wire dress Monte Carlo vs fixed flex). Hinge crosstalk SCLK -> RX input.
3. Clean-sheet AB1 section: copy `afe_design.py` / `afe_layout.py` into `src/`, apply items 30 / 31 (isolation resistor or reference driver; VCM / amplifier choice) and the rotating decoupling group (B11); route with the repo router.
4. Rigid-flex board definition: one outline with rigid and flex regions, stackup drawing (6L rigid, 2L flex core, coverlay, FR4 stiffeners), hinge routing with hatched GND, fold-line keep-outs (no vias or pads within 1 mm of a fold); DRC with drc.py per region; KiCad 9 has no per-region stackup, so the fab drawing carries it.
5. Compare A / B / C on the same table (fit, leak, noise, joints, test, cost from real quotes) and decide; only then does anything move into the main design (B12).

## Phase 2 results (`rf1_phase2.py`, on a copy of the receive simulation; MODELED)

Receive-lead pickup, 300 units per case, peak mV at turn-off (the same scale as the board leak in `kit_v22/sbq_sim.json`; lead path ASSUMED):

| QA board | mean | sigma | 95 % of units below |
|---|---|---|---|
| AWG36 untwisted (dress varies) | -1.6 | 26.8 | 49.3 |
| AWG36 twisted (5-15 mm pitch) | -0.03 | 0.69 | 1.27 |
| flex broadside pair at the design orientation | 0.09 | 0.15 | 0.31 |
| flex at the worst orientation (routed carelessly) | 3.0 | - | - |
| board leak for comparison: aligned / 0.1 mm / 0.5 mm offset | 0.008 / 0.015 / 0.13 | | |

The lead pair is part of the receive null: untwisted wire alone is 100-1000 x the aligned board leak. Flex cuts the unit-to-unit spread 4-5 x against a good twisted pair, and its mean is a fixed offset (calibratable). The flex must be routed at the design orientation (loop plane along the field): rule for phase 4. QB: 15.6 / 0.63 / 0.08 mV sigma.

Clock crosstalk into the analog lines of the AB1 <-> CB1D link (2D finite-difference C and L, upper bounds on a 100 pF node, 3.3 V edge in 2 ns):

| victim | ribbon (today) | RF1 hinge (guard traces + ground layer) |
|---|---|---|
| MONO_IN, worst aggressor | 437 mV | 7.1 mV |
| MONO_IN from SCLK | 62 mV | 0.22 mV |
| VCM_OUT, worst aggressor | 215 mV | 1.4 mV |

## Cavity and potting (`rf1_cavity.py`, MODELED, envelope volumes)

With hinges instead of headers and three part swaps on CB1D (OKI-78SR module -> TI LMR36015 + Bourns SRN4018-6R8M; Pico 2 W on pins -> chip-down RP2354A without the radio; headers -> hinges), the tallest CB1D part is 2.5 mm (was 10.2) and the tallest AB1 part 1.6 mm (was the 4 mm header + 5 mm socket).

| layer | baseline | needs | saving |
|---|---|---|---|
| L1 gallery | 5.8 | 2.2 | 3.6 |
| L2 analog cell | 10.2 | 6.05 | 4.15 |
| L5 controller | 11.8 | 5.1 | 6.7 |

- **K-top (recommended):** L0-L4 keep their z (nothing near the receive coils moves); L5 shrinks 6.7 mm: head 47.1 -> 40.4 mm. L5 becomes a potted zone (syntactic silicone, 22.8 cm3, 13.7-18.3 g) instead of coat-only: the tube saves 13.7 g, so the head mass is about unchanged (0 to +4.6 g); the gain is protection (moisture, microphonics, better heat path than still air). To re-run: head_crosscheck, the HTA coupling (it moves 6.7 mm toward the formers), head thermal with the pour.
- **S (full shrink):** 14.5 mm (head 32.6 mm), but AB1, the septum and the carbonyl-iron absorber move 3.6-7.8 mm toward the receive coils: changes the receive null; not before sbq_sim / check_v22 / head_crosscheck say so.
- Potting: L1 gallery and L2 gel (fixed flex, no connector voids), L4 CI unchanged, L5 SYN (new), every hinge bend outside the pours, LB1 / HTA coat only.

## Phase 4: the head rigid-flex definition (`rf1_phase4.py`, MODELED)

- **Stackup:** 6-layer rigid sections (F, In1 hatched GND, In2, In3, In4 plane / +3V3D island, B) with the 2-layer flex core as In2 / In3: hinge signals leave on In2 over a hatched In3 ground. Rigid 1.602 mm, flex 0.186 mm (vendor: 1.6 / 0.2). LB1 goes 4 -> 6 layers; HTA stays a separate 4-layer board with a hot-bar flex tail (the roof stays removable).
- **Flattened panel:** CB1D at the centre, LB1 across its 15.2 mm S-fold, AB1A / AB1B at the ends of L-shaped 7 mm hinges that leave the CB1D duct edge either side of the LB1 hinge: 332 x 171 mm, fits the 457 x 610 mm panel; copper is 24.5 % of the box (expect a high panel price: get quotes).
- **Fold and transition rules F1-F8:** no via / pad within 1.0 mm of a transition; traces cross folds at 90 deg, no corners or width changes in a bend zone; cross-hatched flex ground; fold radius >= 2.0 mm, static only; FR4 / polyimide stiffeners only (rule 5); no 460 V net on any flex (rule 6); no rigid pour across a fold; ground guards on both sides of every analog hinge line. ASSUMED until the vendor and IPC-2223 confirm.
- **CB1D section:** Pico 2 W module and OKI-78SR leave; RP2354A (QFN-60) + 12 MHz crystal + core inductor + TLV755P 3.3 V and LMR36015 + SRN4018-6R8M come in, placed in the freed areas with 0.3 mm to every kept part (`results/rf1_cb1d_section.png`). The radio leaves with the Pico W (OPEN_ITEMS 42 settled by removal). CB1D is not re-routed in RF1 yet.

## Phase 3: clean-sheet AB1 (`src/ab1/`, MODELED)

`make_rf1_ab1.py` builds the RF1 generator as checked patches of the baseline `afe_design.py` / `afe_layout.py` / `afe_ripup.py`. Changes: hinge-exit lands (J2) and flex-jumper lands (J1) instead of headers; OPA2211 reference VBIAS = 2.5 V (REFOUT through OPA2365 half A, 10 ohm isolation, 1 uF); 1:2 divider into each ADC input (AIN+ 1.25 V DC = VCM); RF 820 ohm (total gain 41.5); 10 ohm isolation on the VCM buffer (OPEN_ITEMS 30); local TLV755P +3V3D next to the ADC island (the hinge no longer carries +3V3D; pin 3 is a ground).

Front-end check (`rf1_frontend_check.py`, against TI SBOS377L and the AD7389-4 Rev. 0): baseline **FAIL** (OPA2211 input 1.25 V, range 2.0-3.6 V); RF1 **PASS** (input 2.5 V, ADC common mode 1.25 V inside 0.2-2.3, offset 0 by construction, 38 % of the ADC differential range used vs 42 % baseline, divider noise 0.1 nV/rtHz vs 1.1 for the amplifier, closed-loop bandwidth 0.96 MHz vs the 318 kHz filter).

Routing (the repo's AB1 router, then the Freerouting step where it stalls; unchanged rules: track 0.15, clearance 0.16, via 0.508 / 0.254):

- **Routing status: AB1B routed: 0 open; KiCad 9 DRC 0 errors / 0 unconnected (20 dangling-track warnings, the baseline has 19); independent DRC 0 fails, minimum clearance 0.204 mm** (`build_ab1/final_B/`, `results/rf1_ab1_route.json`).
- **AB1A routed: 0 open; KiCad 9 DRC 0 errors / 0 unconnected (26 dangling-track warnings); independent DRC 0 fails, minimum clearance 0.165 mm; Gerber edge check OK** (`build_ab1/final_A/`). The repo router and repair loop left 1 net open (OUT_GY: U1.7 to RF2; 9 hash-seed routes all left the same net, so the placement, not the net order, was the limit). The Freerouting step (`src/pcb/freeroute.py`, Freerouting 2.4.1, pinned jar) ripped OUT_GY and re-routed it with the repo rules: 62 vias. It also closed VBIAS_O (UB to RISA), which the exported board had open although the router report did not list it.
- Exporter fix found on the way (RF1 copy, patched in `make_rf1_ab1.py`): the stub-to-pad test treated an SMD pad as a sharp rectangle, so a track ending on the rectangle corner of a rounded pad (CVB.2) stayed about 4 um off the copper; KiCad joined it, the independent DRC did not. The baseline `src/pcb/afe_export.py` has the same test (no baseline board triggers it today): OPEN_ITEMS 45.
- One command per board: `FR_RIP=OUT_GY experiments/RF1_rigidflex/src/ab1/finalize_rf1_ab1.sh A build_ab1/rep_A_fin_A_1 "<PUT>"` (export, Freerouting, KiCad Gerbers into `final_<B>/GERBER_AB1<B>`, KiCad DRC, independent DRC, Gerber edge check); then `src/ab1/record_route.py`, `rf1_phase4.py` (F1 now reads the final board), `rf1_summary.py`.
- How: the hinge exit (J2 lands) sits where the baseline header was (east edge, next to the ADC) and the hinge folds up there; the north exit toward the duct left 3-15 nets open. Placement of the RF1 parts (and, on AB1B, D2 / RF1 / CF1 nudged in a 2 mm window) is automatic: `src/ab1/autoplace_rf1.py` (pads and bodies checked, 0.5 mm corridor margin, caps anchored to their pins) and `src/ab1/repair_loop.py` (re-places only the parts within 2.5-5.5 mm of a stuck pin, keeps a result only if fewer nets are open).
- Tried and dropped (recorded in the generator as options, off): matched AIN- dividers (more parts, 8-15 open), swapped buffer halves (the LDO then blocks the +3V3D island), no local LDO on AB1A (5-8 open), the north hinge exit (3-15 open).

## Baseline defect found here (recorded in docs/CORRECTIONS.md, 2026-10-29)

The committed AD7389-4 AB1 biases the OPA2211 inputs at VCM = 1.25 V, below their 2.0 V minimum on a single 5 V supply (TI SBOS377L). RF1 fixes it (phase 3).

## Files

- `rf1_study.py` phase 1 study; `rf1_figure.py` the figure; `rf1_phase2.py` lead pickup and crosstalk; `rf1_cavity.py` condensation and potting;
  `src/ab1/make_rf1_ab1.py` the clean-sheet AB1 as checked patches of the baseline generator (writes the RF1 copies `afe_design.py`, `afe_layout.py`, `afe_ripup.py`);
  `rf1_phase4.py` stackup, flattened panel, fold rules, CB1D section; `results/` outputs; `ds/` the Rigiflex pages (owner-supplied, 2026-10-29); `src/sbq_sim_baseline_copy.py` the receive simulation copy.
