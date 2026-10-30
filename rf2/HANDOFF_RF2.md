# RF2 clean-sheet head: handoff (2026-10-29, updated 2026-10-30)

A new session starts at `START_HERE_RF2.md` (install, rebuild, where we stopped). Upgrade studies are in `ENHANCEMENT_PLAN_RF2.md`. The full regeneration is now one command: `make rf2-signoff`, which writes STATUS_RF2.md.

RF2 is a side experiment. The baseline design (src/, work/, docs/) is untouched. Everything here is **MODELED or tool-checked**: nothing has been ordered, built or measured. "Checked" below means measured on the generated solids / boards by the scripts named, not proven in hardware. Numbers come from the result files; none is typed by hand.

## 0. How to regenerate (repo root, about 2 minutes)
```
python3 rf2/head/rf2_head.py          # spec + every printed part, seat and envelope (STL, about 1 s)
python3 rf2/head/rf2_shield_pcb.py    # SH1 shield board: KiCad file, KiCad DRC, Gerbers + drill, loop check
python3 rf2/head/rf2_head_check.py    # measured checks: closed meshes, envelope, interference, seats, clearances, mass, potting
python3 rf2/head/rf2_wiring.py        # wiring C01-C12, ADC map, power tree, timing / PWM, physical slot probes
python3 rf2/head/rf2_head_figure.py   # out/rf2_head_layout.png (plan + section); rf2_wiring.py also writes out/rf2_wiring.png
```
The physics studies behind every choice: `rf2_coil_search.py`, `rf2_receiver_combo.py`, `rf2_ground.py`, `rf2_ground_dsp.py`, `rf2_timing.py`, `rf2_pinpoint.py`, `rf2_petal_ring.py`, `rf2_disk_rx.py`, `rf2_emi.py` (README steps 1-9). Generated meshes are git-ignored (the litz mesh alone is 16 MB); the JSON results are committed.

## 1. What the design is
A 233 mm, 25.4 mm (1 inch) pulse-induction head (today's head: 47.1 mm), with:
- **Transmit + depth receive:** one rim mono coil (26 turns of 1.2 mm litz, 333 uH, 8.06 A scan / 12.7 A pinpoint boost) that transmits and receives. Every alternative modeled (petal rings, dense stacks, concentric, disc and quadrupole receivers, dual transmit) was shallower at the same pulse energy.
- **Direction channel:** the two baseline quadrupole boards (SB1R-QA / QB): bearing axis, peak-null-peak pinpoint, a ground- and interference-quiet second channel.
- **Interference reference:** a 3-axis coil on the shaft, 0.6 m up, feeding an adaptive canceller.
- **Electrostatic shield:** SH1, a split-ring board under the receive boards (no closed loops).
- **Electronics in the head on rigid-flex:** analog sections AB1A / AB1B (routed in RF1), the CB1D digital/power section, the MP1 mono preamp, the TXJ coil-lead terminal board and an LED ring under the lid. The transmit driver stays in the neck module at the shaft base (baseline PB1R topology).
- **Firmware:** multi-period (PWM) ground balance with an adaptive ground tracker, a decay-time detector that stays silent until a signature, type from the decay time, bearing from the quadrupoles, interference learned from listen-only frames, and a trigger-held pinpoint mode.

## 2. Part-by-part status
| Part | Function | Status | Source |
|---|---|---|---|
| SHELL_LOWER | skid 1.2 mm + wall r 114.5-116.5, z 0-23.9; 2 stack pins | generated, checked | head/rf2_head.py |
| LID | 1.5 mm; 42 LED windows Ø3.0; 6 LED bosses with pins; cable gland (Ø8 in a Ø12 boss) at the heel, r 92 | generated, checked | rf2_head.py |
| COIL_CHANNEL | inner wall r 108.4-109.4, z 3.2-18.8; floor z 3.2-3.8; lead slot 6 mm at 178 deg | generated, checked | rf2_head.py |
| LITZ (26 turns) | 3 columns r 113.4 / 111.8 / 110.2, 9 rows from z 4.4 at 1.6 mm pitch, epoxy-potted | geometry checked; electrical L 333 uH modeled | rf2_receiver_combo.py |
| BAY_WALLS | radial walls at 89 / 156 / 198 deg, r 42-108, z 3.8-20.8, 1.2 mm; LV slot in the 156 deg wall | generated, checked | rf2_head.py |
| CRADLE_AB1A / B | ledge under the 1.2 mm edge keep-out, wall, snap lip; hinge slot facing the centre | generated, checked | rf2_head.py |
| CB1D_TOWER | ledge, wall r 39.3-40.5, snap lip; slots at 106 / 137 / 170 / 186 deg | generated, checked | rf2_head.py |
| TRAY_MP1 / TXJ | ledge + rim; HV slot towards the coil, LV slot opposite | generated, checked | rf2_head.py |
| SH1 shield board | 37 split rings, one spine, plated ground pad at the 22.5 deg stack hole | **KiCad DRC 0 errors / 0 unconnected, Gerbers + drill**, loop-free | head/rf2_shield_pcb.py |
| QA / QB boards | baseline SB1R copper; **outline variant without the r 116 tab needed** (the tab does not fit a 2 mm wall) | copper existing; outline change TO DO | src/pcb/sbq_*.py |
| AB1A / AB1B | analog sections, 6-layer rigid + 2-layer flex core | routed in RF1 (0 open, KiCad DRC clean); **channel gains TO RE-DO for the RF2 map** | experiments/RF1_rigidflex |
| CB1D section | RP2354A, LMR36015 5 V buck, TLV755P 3.3 V | placed in RF1 (no collision); **routing TO DO** | RF1 rf1_phase4.py |
| MP1 | mono preamp, HV-tolerant input | **TO DESIGN** (envelope 26 x 18 mm reserved) | - |
| TXJ | coil-lead terminal board (wire-hole pads, no plug-on joints) | **TO DESIGN** (envelope 9 x 15 mm reserved) | - |
| LED ring | 36 LEDs at r 62.5 (bearing) + 6 at r 22 (class colour), clocked | **TO DESIGN** (annulus r 15-75 reserved) | - |
| REF3 coil | 3 orthogonal 80 mm windings on the shaft, 620 turns/axis (ASSUMED wire) | former generated; **noise not checked** | rf2_head.py, rf2_emi.py |
| Neck TX driver | single switch, clamp about 460 V, flat-top PWM current loop | baseline PB1R topology; **RF2 values to re-design** | src/pcb (baseline) |

## 3. Envelope and vertical budget (rf2_head_check.json, all within 25.4 mm)
| Level | z (mm) |
|---|---|
| skid | 0-1.2 |
| SH1 shield (0.4 mm) | 1.2-1.6 |
| QA, QB (0.8 mm each) | 1.6-2.4, 2.4-3.2 |
| coil floor / litz rows | 3.2-3.8 / 3.8-17.8 |
| bay (all electronics) | 3.8-21.6 (17.8 mm) |
| AB1A/B, MP1 (with parts) | 4.6-10.2 / 4.6-10.6 |
| TXJ (with parts) | 4.6-12.0 |
| CB1D (with parts) | 11.5-19.5 |
| LED ring (with LEDs) | 21.6-23.9 |
| lid | 23.9-25.4 |
Component height rule (from the envelopes): AB1 parts <= 1.0 mm below / 3.0 mm above the board; CB1D <= 2.0 / 4.4 mm; MP1 <= 1.0 / 3.4; LEDs <= 0.8 mm. Edge keep-outs where ledges and lips grip: 1.2 mm on the bottom side, 0.4 mm on the top side.

## 4. Sectors and potting
| Sector | Azimuth | Contents | Potting (full-fill volume) |
|---|---|---|---|
| HV (heel) | 156-198 deg | coil lead slot, TXJ, MP1 input side, gland | high-dielectric-strength epoxy (65.9 cm3) |
| Analog | 89-156 deg | AB1A (r 82, 106 deg), AB1B (r 82, 137 deg); next to the QA / QB lead pads (83-142 deg) and MP1's output | low-permittivity gel (97.0 cm3) |
| Digital / power | the rest | CB1D on the tower at the centre, LED hinge, LV cores | syntactic silicone (422.3 cm3) |
| Coil channel | rim | litz | epoxy (about 38 g) |
| Display | under the lid | LED ring | conformal coat only |
The 89 deg wall (analog | digital) is PETG loaded with carbonyl iron. Full potting of the bay adds about 445 g, so the design pots the analog and HV sectors only (67 g by the volume ledger); see the mass section.

## 5. Seats (how every board is held; all measured, rf2_head_check.json "seats")
- **Board stack (SH1, QA, QB):** sits on the skid; 2 PETG pins Ø3.2 at r 28 (157.5 / 247.5 deg) through the SB1R NPTH holes Ø3.4; the third hole (22.5 deg) carries the shield ground wire.
- **AB1A / AB1B:** cradle ledge to z 5.6 (board underside), wall r +0.3..+1.5, snap lip at z 7.4-8.0; a 10 mm slot faces the centre for the hinge and the receive tails.
- **CB1D:** tower ledge to z 13.5, snap lip at z 15.3-16.0; slots at 106 / 137 deg (hinges to AB1A / AB1B, receive tails), 170 deg (MP1 side) and 186 deg (LV cores from the gland).
- **MP1 / TXJ:** tray ledge to z 5.6, rim to z 8.0; HV slot towards the coil (180 deg), LV slot opposite (0 deg).
- **LED ring:** hangs from 6 lid bosses (Ø4.0 to z 23.1, pins Ø1.8 through Ø2.0 board holes); LEDs sit under the Ø3.0 windows.
- Every seat touches its board only at the ledge (gap 0 by design). Measured gaps: seats to bay walls 1.5-10 mm; envelopes to walls 3.0-10 mm; HV envelopes to the nearest other island 13.1 mm (MP1 to AB1B); litz to the shell wall 0.5 mm and to the channel wall 0.2 mm.

## 6. Wiring (rf2_wiring.json; lengths are straight-line estimates + 15 mm)
| ID | From -> to | Medium | Class | Conductors | Path |
|---|---|---|---|---|---|
| C01 | coil -> TXJ | litz ends | HV | TX_A, TX_B | lead slot 178 deg, HV sector |
| C02 | TXJ -> gland -> neck | shaft cable, HV pair in its own jacket (630 V) | HV | TX_A, TX_B | HV sector, lid gland |
| C03 | TXJ -> MP1 | 2 short wires in the tray HV slots | HV | COIL_SENSE, COIL_RET | HV sector |
| C04 | MP1 -> AB1B | 2-layer flex jumper, hatched ground | analog | MONO_OUT, +5VA, AGND | wall 156 LV slot |
| C05 | QA pads -> AB1A | flex tail soldered to the SB1R pads | analog | QA_P, QA_N | under the tower, slot 106 |
| C06 | QB pads -> AB1B | flex tail | analog | QB_P, QB_N | under the tower, slot 137 |
| C07 | SH1 pad -> AB1A AGND | 0.5 mm wire up the 22.5 deg stack hole | analog | SHIELD | single-point ground |
| C08 / C09 | CB1D -> AB1A / AB1B | rigid-flex hinges | digital | SCLK, CS, SDO1, SDO2, +5V, GND | tower slots 106 / 137 |
| C10 | CB1D -> LED ring | rigid-flex hinge (up) | digital | +5V_LED, GND, LED_DATA, LED_CLK | digital sector |
| C11 | gland -> CB1D | shaft cable LV cores, own sleeve, >= 10 mm from the HV pair | power/digital | VIN, GND, TXCMD±, TXSTAT±, DATA± | along the 198 deg wall, tower slot 186 |
| C12 | gland -> AB1A | 3 shielded twisted pairs | analog | REFX±, REFY±, REFZ± | wall 156 slot, over AB1B at z 11-13 |
Checks: every endpoint exists; HV never on flex and only in the HV sector; **every slot a path uses is probed in the solids and open**; the shaft cable has 16 conductors (2 HV, 8 LV, 6 REF). No plug-on joints inside the head (repo rule): wire-hole pads and hinges only.

**ADC map** (AD7389-4 on each AB1, 4 channels): AB1A = QA, REFX, REFY, REFZ; AB1B = QB, MONO, 2 spare.

## 7. Power (rf2_wiring.json; loads ASSUMED where marked)
VIN about 24 V (7S pack, switched and fused by PM2 in the handle) -> CB1D LMR36015 -> +5 V (load 0.54 A of 1.5 A: LED ring 0.35 A firmware cap, AB1A/B 0.04 A each, MP1 0.02 A, 3.3 V LDO 0.09 A) -> TLV755P +3.3 V (0.08 A of 0.5 A); each AB1 has its local TLV755P +3V3D (RF1). The transmit current never enters the head electronics: the neck driver runs from VIN with its own bulk bank.

## 8. Transmit and receive timing (PWM)
| Item | Value |
|---|---|
| Pulse rate | 400 Hz nominal, chosen per site in 380-420 Hz to sit off VLF stations (fixed rate beats blind jitter for the learning detector); 1 frame in 16 is listen-only (no pulses) |
| Scan pulses | 8.06 A; T1 = 103.2 us (natural ramp) and T2 = 403.2 us (+300 us flat-top), alternating pulse by pulse (multi-period ground balance) |
| Flat-top PWM | in the neck driver's current loop, 200 kHz (ASSUMED), duty about 0.20 (I x (R_coil + R_cable) / VBUS) |
| Pinpoint boost | trigger held: 2.5 x energy, 12.74 A, T1 = 163.2 us, a few seconds (switch rated 20 A) |
| Turn-off | clamp about 460 V; critical damping Rd = 408 ohm (coil capacitance 500 pF ASSUMED); first clean gate 16.3 us (rf2_timing) |
| Receive gates | 16.3, 26.4, 42.7, 69.0, 111.7, 180.8, 292.5, 473.2, 765.6 us |
| LEDs | updated only in the quiet slot after the last gate, dark during receive windows |
| ADC | SCLK >= 27.2 MHz (3 frames in the first gate) |

## 9. Firmware functions (reference code in Python; port to C like fw/)
1. **Ground learning at switch-on** (`rf2_ground_dsp.py`): an 80-frame "ground pump" (bob the coil), then a low-rank ground subspace per receiver (eigen-directions above the electronic noise), learned with a guard window so a target's flanks are not learned as ground.
2. **Silent until a signature:** GLRT over 12 decay constants (10-400 us); silent below the chi-square threshold (false-alarm rate 1e-5 per frame). Modeled: 0 false-alarm frames over severe and moderate ground.
3. **Type:** decay constant -> class (edges 10 / 40 / 200 / 700 us). Modeled 1 g: 27.3 us vs 27.9 true, "small gold".
4. **Direction:** quadrupole axis 0.5 atan2(QB, QA) + 45 deg (calibrated); side from the gyro and the sweep direction. Single-pass range about 80-100 mm for 1 g.
5. **Pinpoint (trigger):** boost + slow pass: bearing within about 1-11 deg and depth about 15 % low at 100 mm for 1 g. Deeper readouts are **not solved** (README step 6).
6. **Interference:** learned from listen-only frames; the 3-axis reference canceller; fence pulses blanked; pulse rate chosen per site.
7. **Output:** LED pixel at the bearing, colour by class, brightness by statistic; audio tone by class (AU1 in the handle).

## 10. Modeled performance (gold spheres; see each README step for the assumptions)
| Condition | 1 g | Source |
|---|---|---|
| no ground, noise-limited (mono channel) | 342-367 mm | steps 2, 3, 7 |
| SDC 2300-class 8 in mono, equal electronics | 330-342 mm | steps 2, 3 |
| mild / moderate / severe viscous ground, multi-period balance | 249 / 228 / 221 mm | step 3 (ASSUMED ground) |
| severe ground, ground exponent tracked perfectly | 274 mm | step 3 |
| under a power line, learned + reference canceller | 295 mm | step 9 (ASSUMED interference) |
| bearing / depth / size readouts | to about 100 mm for 1 g | steps 4, 6 |
These are **model results, not bench data**; ground, interference and several circuit values are assumptions.

## 11. Mass (rf2_head_check.json)
About **761 g** (745 g corrected 2026-10-30 from 702 g, docs/CORRECTIONS.md; +15 g for the 522-LED display flex, section 16): parts plus 67 g of potting at the volume ledger's fill levels. Breakdown: printed parts 220 g (100 % infill, an upper bound), QA + QB 129 g, SH1 37 g, litz 110 g, electronics 103 g (ASSUMED), coil epoxy 38 g, hardware 40 g, potting 67 g (analog-sector gel 32.4 g, HV-sector epoxy 34.7 g; rf2_ledger.json). **Correction:** the earlier 529 g estimate assumed one 0.4 mm receive board; reusing the two 0.8 mm SB1R boards adds about 170 g. Options: a single combined 4-layer QA+QB board, lower infill.

## 12. Measured checks (all pass)
- **Meshes:** every mesh closed and edge-manifold.
- **Envelope:** every part inside r 116.5 and z 0-25.4.
- **Interference:** no interference between any pair of head parts.
- **Seats:** every seat touches its board only at the ledge.
- **Clearances:** all clearances above their limits.
- **LEDs:** every LED is under a window and its top sits at the lid underside.
- **SH1 board:** KiCad DRC 0 errors / 0 unconnected; copper is one piece with no closed loop (the only closed copper path is the 5.4 mm plated pad annulus, eddy time constant about 0.45 us); 2.05 mm from the pin holes; in-trace eddy time constant 0.39 us.
- **Wiring:** endpoints, HV routing, slot probes, ADC channels, power margins all pass.
- The regression suite has a row for this (tests/regress.py).

## 13. Known deviations and corrections
- **Coil height:** the coil rows sit at z 4.4-17.2 (a 0.6 mm printed floor on QB), 1.2 mm higher than in the RF2 studies (3.2-16.0). Re-run rf2_receiver_combo with the built heights before quoting depth for this layout.
- **Shield ring count:** SH1 has 37 rings, not 40. Three positions are lost to the stack-hole band and the edge clearance.
- **Split-trace decay time:** an earlier session statement (split trace decays "in about a nanosecond") was wrong by 1000x; it is about 0.4-0.8 us (README step 9).
- **SB1R tab:** the r 116 locating tab cannot be used inside a 2 mm wall at this diameter; RF2 needs the tab-less outline variant.

## 14. Next steps, in order
1. ~~SB1R outline variant~~ done 2026-10-30 (rf2_sb1r_variant.py).
2. **MP1 mono preamp:** schematic (input protection for about 460 V flyback, 630 V parts, >= 1.0 mm), layout in the 26 x 18 mm envelope, route (repo router + Freerouting step), KiCad DRC, rule-6 check.
3. ~~TXJ~~ done 2026-10-30 (routed, HV 3.4 mm). MP1 v1 is routed too; MP1 v2 (section 15) is next.
4. **AB1A / AB1B channel gains** for the RF2 map (mono and REF levels differ from the baseline channels); regenerate through make_rf1_ab1.py.
5. **CB1D section routing** (RF1 placement), plus the LED-ring board and its hinge.
6. **Neck driver values:** 333 uH / 8.06 A / 12.7 A boost, flat-top PWM loop, clamp and critical damping; include the cable between neck and head in rf2_timing (the 16.3 us gate assumes damping at the coil).
7. **REF3 coil:** check its noise (wire resistance) against the 1.9 nV/rtHz assumed in rf2_emi; consider ferrite rods.
8. **Re-run the depth model** with the built coil heights and the cable; then bench: wind the rim coil, measure L, R, turn-off and the first clean gate, then targets in air, then ground.
9. **Patent and literature search** on the quadrupole + mono combination before any novelty claim.

## 15. Update 2026-10-30 (Phase A / B)
- **System netlist** (`head/rf2_netlist.py`): the single source for every RF2 board, part, pin and harness wire. `rf2_parity.py` checks the built boards and the harness against it. Wires with an end on a board not yet built (AB1A, AB1B, CB1D, the neck, the coil) are listed as pending.
- **Boards routed and checked by `rf2_boards.py`.** Each board is built in pcbnew from the netlist, routed with Freerouting, then checked by KiCad DRC (board rules plus an HV 1.0 mm rule with a 50 mm control run), the independent shapely copper check (with no net forming a loop around the axis), pad parity, and Gerbers + drill.
  - TXJ (12 x 16 mm, HV 3.4 mm) and MP1 v1 (26 x 36 mm, HV 1.2 mm): DRC 0.
  - SH1 (37 split rings) and the tab-less SB1R variant (outline r 114.0, copper identical): clean.
- **LR1 LED ring is now a flex section** (2-layer polyimide plus an FR4 stiffener, vendor 0.10 / 0.10 mm rules) with open C-shaped GND / +5 V buses. At the rigid 0.2 / 0.2 mm rules a trace could not pass between the SK9822-EC20 pads. It is routed by the deterministic template `head/rf2_ring_template.py` (Freerouting stalled):
  - DRC 0, 0 unconnected, min clearance 0.19 mm (rule 0.10), no loop around the axis, parity OK, Gerbers.
  - Data runs in the outer lane and clock in the inner lane, parallel and never crossing on a layer.
  - Each LED and capacitor drops to the open B.Cu buses; +5 V jumps over the GND bus on F.Cu.
  - Links that cross the radial hinge feeds (185 / 195 deg) run on B.Cu.
  - The hinge lands are now JH3 = clock, JH4 = data, so the feeds reach LD1 without a crossing.
- **Incremental routing** (owner rule): a board is re-routed only when its netlist entry changes. A re-route resumes from the last routed copper and routes only the open connections, with fan-out off (`resume_input`, `freeroute.py --no-fanout`).
- **MP1 v2 front end** (ngspice, `head/rf2_mp1_spice.py`, generic models): a depletion-mode HV MOSFET limiter + 22 ohm gives 64 ohm in the signal path (1.03 nV/rtHz), against 1410 ohm (4.83 nV/rtHz) for the v1 resistors. Energy per pulse is 79 against 786 uJ, and recovery is the same 12.9 us. That is about +28 % modeled mono depth with a 1 nV/rtHz op-amp.
  - Datasheet-verified: LMH6629 (0.69 nV/rtHz), TPS7A94 (0.46 uVrms).
  - Not yet verified: the MOSFET (PDF needed). The LMH6629 input limits (+-10 mA, -0.5 V) require a series resistor after the clamps, still to be sized.
- **Field code cross-check:** the loop field behind every RF2 depth number agrees with magpylib to 1.3e-10 (`head/rf2_field_xcheck.py`).
- **Tools:** pinned in requirements-rf2.txt and installed by `RF2_TOOLS=1 scripts/bootstrap.sh` (= `make rf2-tools`), with a self-test.

## 16. Dense LED display (2026-10-30, owner: rings from the rim to the centre, 400+ LEDs)
- **What it is:** LR1 is now a full-disc display flex with **522 SK9822-EC20** in 13 rings: r 104, 96, ..., 16 on an 8 mm grid, plus a 4-LED centre ring at r 8. Ring sizes from the rim inward: 78 / 72 / 65 / 59 / 53 / 46 / 40 / 34 / 27 / 21 / 15 / 8 / 4.
- **Pinpoint display:** the firmware lights the LED in the target's direction, on the ring that matches its distance from the head centre. As the head centres over the target, the light moves inward to the centre ring. The ring spacing should later be checked against a modeled centre-offset error (ENHANCEMENT_PLAN, new item).
- **Single source:** everything comes from `head/rf2_ledgrid.py`: outline, parts, nets, copper (`out/rf2_display.png`).
  - **Cells:** alternate rings run CCW / CW (each cell turned 180°), so neighbouring rings share an open B.Cu power bus. GND and +5V_LED alternate between rings.
  - **Power tree:** two B.Cu spokes along the heel strip feed the buses; each bus joins its spoke at one end only. No loop around the axis (rule 5).
  - **Chains:** 4 serpentine chains (48 / 101 / 158 / 215 LEDs), with polar U-turn jumps between rings.
  - **Hinge:** a flap above CB1D (x' 20-34) carries 12 lands (4 power, 8 data / clock).
  - **Gland:** the flex has a notch around the gland boss (1.0 mm clear).
  - **Mounting:** 6 rim holes at r 110.8 for the lid bosses.
- **Routed with no autorouter:**
  - KiCad DRC 0 errors, 0 unconnected; minimum clearance 0.15 mm (rule 0.10); no loop around the axis; parity; Gerbers + drill.
  - The board step takes about 3.5 min, mostly DRC on about 25,000 segments.
- **Housing:**
  - The clear PETG lid has no windows; the LEDs shine through it, and their transmission is ASSUMED.
  - The housing checks pass: all sites inside the outline, LED tops at the lid underside, no interference.
- **Power** (datasheet-verified, DATASHEET_LOG RF2-DS-DISPLAY): the display has its own rail, an LMR36520 buck (4.2-65 V, 2 A) plus a TPS22918 load switch (2 A).
  - Load: 0.522 A static (522 x 1 mA) plus a 0.85 A firmware brightness cap = 1.372 A against 2 A (31 % margin).
  - The rail is switched off whenever the detector is silent.
  - The main +5 V rail drops to 0.19 A.
- **Data:**
  - The longest chain at 8 MHz takes 878 us, against a quiet slot of 1162 us at 420 Hz. The SK9822-EC20 maximum clock is 15 MHz.
  - Each chain gets one RP2354A PIO state machine (CB1D, Phase C).
- **Moved number:** the head mass is 761 g (was 745 g). The display flex estimate rose from 25 to 40 g (ASSUMED).
- **Still open:**
  - The CB1D side of the 12 hinge lands, plus the LED buck and load switch on CB1D (Phase C).
  - The LED-to-receiver coupling check (ENHANCEMENT_PLAN study 7, now more important with about 0.5 m of buses).
  - Measured lid transmission.

## 17. Ingest of owner-supplied documents (2026-10-30; docs/INGEST_2026-10-30.md)
- **MP1 v2 parts decided from the datasheets:**
  - **Limiter:** IXTY08N100D2 (1000 V, RDS(on) <= 21 ohm, Coss 24 pF) beat DN2470 (700 V, 42 ohm, Coss <= 60 pF).
  - **Rin2 = 100 ohm** before the LMH6629.
  - **Modeled:** front end about 1.7 nV/rtHz against about 5.0 for v1 (about +23 % mono depth); recovery 14.7 us, inside the first gate; turn-off edge spike into the clamps 0.41-0.45 A for about 20 ns (an upper bound, to be measured).
- **Flex rules** (Wuerth CBT 06/25, FCT 07/25) now checked on the display hinge: no vias in the bend, conductors perpendicular, bend ratio >= 10:1, nickel-free finish.
- **Thin head** (`rf2/rf2_thin.py`): the 26-turn rim coil reshaped flatter keeps its inductance and modeled depth.
  - Option B (CB1D lowered to the AB1 tier) gives 15.7 mm.
  - Option C (B + flex receive / shield / display + low-profile parts) gives 12.1 mm.
  - Still to model: the bundle self-capacitance (first gate), the flex receive copper, and the coil-to-AB1 coupling.

## 18. Depth: the detection (mono) channel and the levers (2026-10-30; rf2/rf2_depth_levers.py; docs/CORRECTIONS.md)
- **Which channel:**
  - Detection uses the **mono** channel (the rim coil receiving its own signal).
  - The quadrupole boards give bearing / pinpoint and cancel ground, so they are weak at depth by design.
  - The thin-study figure of 136 / 190 mm was the quadrupole channel (corrected).
- **Mono, modeled** (noise-limited, in air, gold spheres, SNR 3, 100 pulses, MP1 v2 1.7 nV/rtHz, 16.3 us gate):
  - option B (15.7 mm): **340 / 434 / 521 mm** (1 / 5 / 20 g);
  - today's 25.4 mm head: 341 / 436 / 525 mm;
  - SDC 2300-class 8 in mono in the same chain: 320 / 408 / 490 mm.
  - The old petal head (as built, sim_head1) modeled 152 / 225 mm (1 / 20 g) on its best receiver (figure-8): the RF2 mono is the deeper design.
- **Levers on option B (1 / 5 / 20 g, mm):**
  - front end MP1 v1 (5.0 nV): 276 / 357 / 431;
  - MP1 v2 (1.7 nV): 340 / 434 / 521;
  - Schottky clamp, Rin2 47 ohm (1.2 nV): 363 / 462 / 554;
  - two LMH6629 per input (0.9 nV): 381 / 485 / 582;
  - 400 pulses averaged: 385 / 489 / 588;
  - 27 mJ boost: 370 / 471 / 565;
  - first gate 10 us: 350 / 439 / 525;
  - **combined (0.9 nV + 400 pulses + 10 us): 445 / 555 / 662**.
- **Physics limit:**
  - A small target's signal falls about as 1 / depth^6. Doubling the depth needs about 64x the SNR, so no single trick doubles it.
  - The gains come from stacking noise, averaging, energy and gate improvements, and in real ground from ground handling, which this noise-only model does not include.

## 19. Tapered ("T-bone") rim former and winding order (2026-10-30; rf2/rf2_taper.py; MODELED)
- **Question (owner):** a circular former with the same footprint, wide at the top and narrowing with sloped faces toward the bottom, wound down every other groove and back up through the skipped ones, channel by channel.
- **Setting:** option B's window (r 103.8-113.4, z 4.4-12.6), 26 turns, 10.8 mJ, mono channel, MP1 v2 noise, gate computed by `rf2_timing.simulate` with the node capacitance = C_ext (368 pF, from the 500 pF ASSUMPTION) + the winding's own capacitance (energy method, eps_r 2.5 ASSUMED).
- **Results (1 g / 5 g / 20 g mono depth; 0.1 g in brackets):**
  - rect 5 x 6, layered (option B): 340 / 434 / 521 mm (183), C_w 132 pF, gate 16.3 us, max turn-to-turn 202 V.
  - taper wide top, both faces sloped, owner's progressive order: 338 / 431 / 518 mm (183), C_w 113 pF, gate 16.1 us, max turn-to-turn 166 V.
  - taper wide top, outer wall flush, progressive: 339 / 433 / 520 mm, C_w 162 pF, gate 16.6 us, 166 V.
  - taper wide bottom: 340 / 434 / 521 mm (same as rect).
  - classic bank order: worse here (C_w 169-180 pF, up to 386 V between neighbours).
- **Reading:** the shape alone is neutral to -0.6 % (it lifts the copper centroid 1.1 mm away from the ground). The progressive order cuts the worst turn-to-turn voltage 18 % (insulation / rule 6 margin), but the winding is only about a quarter of the 500 pF node, so the gate moves by under 0.7 us.
- **Ceiling:** a perfect winding (C_w = 0) gives a 14.9 us gate: 0.1 g 183 -> 189 mm, 1 g unchanged. Cutting the outside capacitance (switch Coss, leads, damping network) to 100-150 pF gives 12.9-13.6 us and 0.1 g 196-199 mm. That, not the former, is the timing lever, and it mainly sharpens small / fast targets (signature clarity), not depth on 1-20 g.
- **Not modeled:** distributed (transmission-line) winding effects, litz strand capacitance, the real former material eps_r, proximity loss.

## 20. Rodin former, Halbach shell and ferrite cap (2026-10-30; rf2/rf2_rodin.py; MODELED)
- **Upload:** `rodin_core_HIGH.stl` was not a mesh (a 279-byte gzip of a 515-byte STL-viewer settings JSON). The former is parametric; a real export can be checked against it.
- **Formers:** RIM torus in option B's window (major 108.6, tube 4.0) and FLAT pancake torus over the face (r 20-113, 8 mm thick; collides with the islands). Two helices of opposite hand, A shallow (tube radius x 0.875), B deep (x 0.625), 13 toroidal circuits each, 10.8 mJ, mono channel, 500 pF node (ASSUMED for all; crossovers would add C).
- **Results (0.1 / 1 / 5 / 20 g mono depth, mm; head-centre field):**
  - option B rim mono: 183 / 340 / 434 / 521; 1218 uT at the centre.
  - Rodin RIM, toroidal-aiding (helices' poloidal parts cancel): 180 / 336 / 429 / 515; 1212 uT; 22.2 m of wire (+24 %). It is a 26-turn loop with extra wire.
  - Rodin RIM, poloidal-aiding (classic closed toroid): 0 / 0 / 0 / 0; 37 mT inside the tube, 0.3 uT at the centre, 0.04 uT at 100 mm.
  - Rodin FLAT, toroidal-aiding: 188 / 294 / 370 / 442; 4747 uT at the centre (3.9x), +22 % at 100 mm on axis, -11 % at 300 mm; L 81 uH, gate 9.2 us.
  - Rodin FLAT, poloidal-aiding: 0 / 74 / 90 / 106.
- **Focusing (option B coil, permeable half-space at z 13.1, image method, inductance L0 + k M):**
  - NdFeB shell, mu_r 1.05 (k 0.024): 184 / 342 / 437 / 524 (+0.6 %).
  - Ideal soft-ferrite cap, upper bound: 231 / 410 / 523 / 629 (+21 %); L 548 uH, 6.28 A.
- **Halbach shell static field** (900 N42 bars 3 mm, 182 g): 205 mT at the coil, 21.6 mT on the receive boards under it, 7.8 mT at the ground surface below the rim, 0.42 mT at 50 mm, 0.15 mT at 100 mm (Earth's field is about 0.05 mT).
- **Eddy currents in the magnets, into the mono at the 16.3 us gate:** 3 mm bars 3e-10 x noise (invisible); 5 mm bars 286 x noise; 10 mm bars 7e7 x noise (blinding).
- **Reading:**
  - A static magnet field cannot steer or bend the pulsed transmit field: the fields add linearly, and NdFeB is almost non-magnetic to the pulse (mu_r 1.05).
  - What focuses the pulse downward is a high-permeability, non-conducting material above the coil (soft ferrite): up to +21 % depth as an ideal bound; the ARX hood v3 reached about half of the ideal gain.
  - The magnets' 205 mT would saturate any ferrite placed near them, which removes that gain.
- **Not modeled:**
  - the Rodin crossovers' self-capacitance;
  - finite ferrite size, ferrite loss and magnetic viscosity;
  - ground signal induced by the static field when sweeping over magnetic soil;
  - the fixed field's offset on the receive electronics.

## 21. Wave-wound rim coil, stacked with a row-by-row twist (2026-10-30; rf2/rf2_wave.py; MODELED)
- **Question (owner):** keep the stacked 5 x 6 rim coil and the same transmit = mono-receive chain, but make every turn a wave around the ring, the wave phase advancing row by row going up (a stacked, Rodin-like twist).
- **Results (0.1 / 1 / 5 / 20 g mono depth, mm; 10.8 mJ; all columns of a row nested in phase):**
  - flat turns (option B): 183 / 340 / 434 / 521; L 323.4 uH.
  - radial wave 0.8 mm, 13 or 6 waves, with or without a 72 deg / row twist (fits the window): 183 / 339 / 432 / 519 (-0.3 %); L 320 uH.
  - corkscrew 0.8 mm (radial + vertical, 90 deg), twisted: 183 / 339 / 432 / 519. A vertical wave needs 0.8 mm more height than the window has.
  - vertical wave 0.8 mm, twisted: 183 / 340 / 434 / 521 (0 %).
  - radial wave 3 mm (does not fit): -1.2 % with the twist, -1.5 % without.
- **Field ripple around the ring:** 20 mm below the coil 0.4-1.2 % for 0.8 mm waves (the twist cuts it 3x), 5 % for a 3 mm wave without a twist; 100 mm down it is 0.0 % in every case.
- **Reading:** the field at depth comes from the turns' enclosed area and current (the coil's dipole moment). A wave of n >= 6 per circuit is a high-order ripple, gone within about 1/n of the radius. At equal energy the wave only re-shuffles the turns: no depth gain; a small loss for large waves, which pull copper inward.
- **Not modeled:** the wave's extra crossover capacitance and the winding labour.

## 22. Ferrite hood and focusing coil formers (2026-10-30; rf2/rf2_hood.py, rf2/rf2_hood_wide.py; MODELED)
- **Method:**
  - axisymmetric flux-function solver (the ARX hood_axi scheme, vectorised; 380 x 413 graded grid out to 4 m);
  - only the ferrite's reaction field is taken from the grid and added to the exact Biot-Savart field;
  - L = exact air L + reaction flux;
  - gate recomputed for each L;
  - mono channel, 10.8 mJ, gold in air.
- **Checks:**
  - air grid vs Biot-Savart: within 0.25 % at 50-600 mm;
  - ideal plate (mu 1e5): L 546.4 uH vs image method 548.2.
- **Materials** (Ferroxcube sheets, DATASHEET_LOG RF2-DS-FERRITE): 3C90, 4A11, 4C65; a flexible sheet at mu 150 (UNVERIFIED); tile fill 0.95 (ASSUMED).
- **Results (0.1 / 1 / 5 / 20 g mono depth, mm):**

| Case | L uH | Gate us | Depth | Peak B in ferrite | Ferrite mass | Head |
|---|---|---|---|---|---|---|
| option B, no hood | 323 | 16.3 | 183 / 340 / 434 / 521 | - | - | 15.65 |
| cap 0.5-2.0 mm (3C90 or flex sheet) over the bundle | 349-356 | 16.9-17.0 | 179-180 / 338 / 432 / 518-519 | 43-163 mT | 14-58 g | 15.65-16.95 |
| L 1.0 mm (cap + outer wall) | 445 | 18.8 | 165 / 323 / 414 / 497 | 281 mT | 62 g | 15.95 |
| U 0.5-2.0 mm, full walls (3C90 / 4A11 / 4C65) | 579-667 | 21.2-22.6 | 146-153 / 319-322 / 412-415 / 496-499 | 239-667 mT (0.5 mm and 4A11 saturate) | 43-208 g | 15.65-16.95 |
| U 1.0 mm, half walls | 456 | 19.0 | 167 / 331 / 424 / 509 | 251 mT | 68 g | 15.95 |
| owner taper (wide top), no hood / + U 1.0 | 322 / 666 | 16.3 / 22.6 | 182 / 338 / 431 / 518; 145 / 317 / 409 / 494 | - / 363 mT | - / 96 g | |
| focus former low 4 x 7, no hood / + cap 2.0 (fits) | 319 / 370 | 16.2 / 17.3 | 184 / 339 / 433 / 520; 178 / 336 / 430 / 516 | - / 49 mT | - / 67 g | 15.65 |
| full-face disc r 0-114, 0.5 / 1.0 / 2.0 mm, 26 turns | 392-402 | 17.8-18.0 | 182 / 342-343 / 435-437 / 521-524 | 57-260 mT | 93-372 g | 15.65-17.15 |
| same discs, 23 turns (L back to 310-318 uH) | 310-318 | 16.0-16.2 | 186 / 336-338 / 427-429 / 510-513 | | | |
| annulus r 60-114 or r 85-114, 1.0 mm | 388-395 | 17.7-17.8 | 179-181 / 339-341 / 433-435 / 519-521 | 101-107 mT | 83-135 g | 16.15 |
| 2 mm plate widened to r 170 / 300 / 600 / 1500 (outside the head) | 531-551 | 20.4-20.7 | 186-200 / 357-396 / 452-509 / 539-611 | | 0.8-64 kg | |

- **Reading:**
  - Ferrite wrapped round the winding (cap, L, U, the Rodin principle) stores more energy next to the wires: L up to 2x, the gate 4-6 us later. It adds no field at depth: -1 to -7 %.
  - A ferrite layer acts as a mirror only where it reaches well beyond the coil. The coil sits at the head's rim, so a layer inside the head gives at most +0.9 % (2 mm full disc, 372 g).
  - The width sweep shows the gain only appears with the plate at r 300-1500 mm, converging on the ideal-plate bound.
  - Formers: the taper and the low focus former are neutral bare (within 0.6 %) and lose under any wrapped hood.
- **Decision:** no ferrite hood for depth in option B. A thin ferrite layer may still be worth it for something else, to be studied separately:
  - shielding the coil from the display and CB1D electronics above it;
  - stability against the hand and shaft.
  Both would need the magnetic-viscosity measurement first.
- **Correction:** the earlier ideal-cap figure (231 / 410 / 523 / 629 mm, section 20) kept the 16.3 us gate. With the gate recomputed it is 202 / 402 / 518 / 623 mm, and it needs a plate far wider than the head (docs/CORRECTIONS.md).
- **Not modeled:**
  - frequency roll-off of mu;
  - ferrite loss and magnetic viscosity;
  - non-linear B-H (the saturating cases are optimistic);
  - the quadrupole boards under a ferrite layer.

## 23. Fair-Rite 77 / 61, and what beats the option-B rim coil if the footprint grows (2026-10-30; rf2/rf2_hood_size.py; MODELED)
- **Fair-Rite materials (owner datasheets):** 77 (MnZn, mu 2000) behaves like 3C90 and 61 (NiZn, mu 125) like 4C65. Same conclusions as section 22:
  - disc r 0-114: 77 gives 342-343 mm (1 g), 61 gives 340-342 mm;
  - plate to r 300 (outside the head): 77 378 mm, 61 362 mm.
- **Ferrite brim beyond a D233 coil** (2 mm 77, r 100-170 = D340 head, 0.54 kg): 180 / 346 / 440 / 526 (+1.8 % at 1 g). To D460 (1.23 kg): +4.1 %.
- **Larger head, same rim coil moved out, turns cut to hold L at about 323 uH (same driver and gate), no ferrite (0.1 / 1 / 5 / 20 g):**
  - D233 (option B, 26 turns): 183 / 340 / 434 / 521.
  - D260 (24 turns): 188 / 355 / 454 / 547 (+4 to +5 %).
  - D290 (22 turns): 193 / 370 / 475 / 573 (+9 to +10 %).
  - D340 (20 turns): 198 / 393 / 509 / 616 (+16 to +18 %).
  - D400 (18 turns): 199 / 418 / 545 / 660 (+23 to +27 %).
- **D340 coil + 2 mm 77 disc over its face (0.83 kg):** 199 / 399 / 515 / 621 (+1.5 % over the bare D340). The solver run of the bare D340 reproduces the direct calculation exactly (393 / 509 / 616).
- **Reading:**
  - Per millimetre of growth, the coil diameter is the dominant depth lever, worth about 10x a ferrite brim of the same size.
  - Inside any head the ferrite adds 0-2 %.
  - Signature clarity: the gate stays at 16.2-16.5 us in the size sweep (L held), so small-target timing is unchanged; 0.1 g gains +3 to +9 %.
- **Not modeled (these cut the larger head's advantage in the field):**
  - ground and EMI pick-up grow with the loop area;
  - the heavier, wider head's swing and coverage of small targets in trash;
  - pinpoint precision (wider coil, wider response);
  - the mechanical and display changes.

## 24. Option B zone map: stray field, coupling, metal echoes, potting (2026-10-30; rf2/rf2_zones.py; MODELED)
- **Transmit field at the peak current (8.17 A) / largest dB/dt (clamp 460 V):**

| Zone | B centre / nearest edge (mT) | EMF in a flat 1 cm2 loop (V) | Receive coupling of a flat 1 cm2 loop (nH) | Loop current step = gate noise (uA) |
|---|---|---|---|---|
| CB1D | 1.22 / 1.35 | 0.021-0.023 | 15-17 | 2.8 / 2.6 |
| AB1A / AB1B | 2.3 / 6.7 | 0.040-0.116 | 28-81 | 1.5 / 0.52 |
| MP1 | 2.1 / 2.9 | 0.036-0.051 | 25-36 | 1.7 / 1.2 |
| TXJ | 5.2 / 7.0 | 0.090-0.107 | 64-75 | 0.66 / 0.56 |
| display flex | 1.2 / 5.7 | 0.021-0.079 | 15-55 | 2.8 / 0.76 |

- **Metal echoes at the first gate (x gate noise) and their drift (x noise per K):**

| Object | Echo | Drift / K | Rule |
|---|---|---|---|
| solid 35 um plane | CB1D 3.1e5, AB1 1.5e5, MP1 1.2e4, TXJ 1.2e3 | 21-456 | banned |
| hatched plane, CLOSED 0.5 mm border | CB1D 3300, AB1 590, MP1 29, TXJ 2.6 | 0.2-164 | banned: every hatch border gets a slit |
| hatched 1.0 / 0.25 mm, border slit | about 1e-20 | 0 | required |
| aluminium electrolytic can | 2.3e4-7.5e4 | 67-217 | banned in the head: MLCC only |
| IXTY08N100D2 TO-252 tab (tau 19.8 us) | 2710 | 1.9 | stand it edge-on to the field, or another package (stage 3) |
| 522 SK9822-EC20 lead frames (2 x 2 x 0.2 mm ASSUMED) | 5500 (ring r 104: 2140, r 96: 1310, r 88: 685) | 120 | measure the real lead frame; outer rings dominate (see the mitigations) |
| SH1 with one ring left closed | 2.2e7 | 4.6e5 | every ring slit (already the design) |
| MG 841AR nickel paint (1.6 ohm/sq), even closed | 0 (tau 1 ns) | 0 | usable as an electrostatic shield coat |

- **LED mitigations, in order:**
  1. the real lead-frame copper from the SK9822-EC20 drawing (the 2 x 2 x 0.2 mm is an upper bound);
  2. a display-temperature sensor and firmware subtraction of the fixed head offset (a 1 % model of the drift cuts it 100x);
  3. move or thin the outer two rings.
- **Potting next to the coil (winding capacitance -> gate -> depth 0.1 / 1 / 20 g):**
  - syntactic foam eps 1.8 (UNVERIFIED): 95 pF, 15.96 us, 185 / 340 / 521;
  - eps 2.5: 132 pF, 16.33 us, 183 / 340 / 521;
  - silicone eps 2.8 (UNVERIFIED): 148 pF, 16.48 us, 182 / 340 / 521;
  - MG 832TC epoxy eps 3.7 (datasheet; DF 0.1 at 1 MHz, lossy): 195 pF, 16.93 us, 180 / 339 / 520.
  - **Coil channel: low-permittivity syntactic foam; no 832TC epoxy within a few mm of the winding.**
- **Layout rules this gives:**
  - nothing switches during the receive window (CB1D clocks gated or spread, LEDs dark: already the timing plan);
  - analog and TXJ loops under 0.1 cm2, laid edge-on (vertical) where the field is vertical;
  - differential receive paths;
  - no metal cans, no solid planes, no closed borders anywhere in the head.
- **Not modeled:**
  - non-axisymmetric plate modes (the ring model keeps only the symmetric one);
  - the turn-off ramp (a step is used, conservative for fast objects);
  - mechanical motion of boards relative to the coil (a second drift source: needs potting stiffness);
  - the real lead-frame and tab geometry.
