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

## 25. Option B housing (variant B) and the mitigation study (2026-10-30; rf2/head/rf2_head.py --variant=B, rf2/rf2_mitigation.py; MODELED / measured on the solids)
- **Variant B** (`RF2_VARIANT=B` or `--variant=B`; outputs in `rf2/head/out_B/`; option A is unchanged in `out/`). Runner steps: `head:B`, `head-check:B`, `head-section:B`. Geometry:
  - **Heights:** H 15.65 mm; shell wall to 14.15, lid 14.15-15.65; display flex 13.1-13.5 with the LEDs to the lid.
  - **Coil:** 5 rows x 6 columns (r 113.4-105.4, rows from z 4.4) in a channel with its inner wall at r 103.8-104.6.
  - **12 printed winding combs** (1.3 mm slots, 0.3 mm teeth, resin print) set the columns for the owner's column-by-column, down-and-up winding.
  - **Boards:** CB1D on the AB1 tier (board z 6.6-8.2). MP1 moves to (-72, 3) and TXJ to (-94.5, 0); the netlist positions are still option A's (stage 4).
  - **Shield:** MG 841AR nickel coat on the shell's inner face, joined to SH1, one 2 mm slit.
  - **Potting:** syntactic foam around the coil, silicone gel analog, 832TC epoxy HV (kept >= 3 mm from the winding), syntactic silicone digital.
- **head-check:B, all passing:**
  - 22 closed meshes; 210 part pairs, no interference;
  - litz to shell 0.5 mm, to the channel wall 0.2;
  - islands >= 3.4 mm to the walls, >= 3.5 mm to each other; HV envelopes >= 14.9 mm from every LV island;
  - LED tops at the lid underside; flex 1.0 mm from the gland boss.
  - Mass 693 g (islands-only potting; option A 761 g), 852 g full fill. Potting volumes: analog 35 cm3, HV 24 cm3, digital 190 cm3.
- **Mitigation study (rf2_mitigation.py):**
  - **Coatings on a chip (field cut at 100 kHz / echo):**
    - ferrite-loaded paint mu' 10 (UNVERIFIED): 25 %, no echo;
    - 841AR nickel paint: 0 %, no echo (electrostatic screen only);
    - copper can 35 um: 32 %, echo 0.43 x noise;
    - mu-metal 0.1 mm: 99.85 %, but a slow strong target (diffusion time 43 us).
    - None of them is a practical shield for a millitesla-range, 100 kHz pulse inside the coil. Layout, timing and distance are the protection.
  - **Passive 'sacrificial' shorted loop (r 10 mm at the AB1A edge):** removes 17 % at its centre and adds an echo of 29 x noise (1.9 / K). With a resistor (tau 0.1 us): 2 %, no echo. Not worth it.
  - **Active bucking loops** in series with the transmit coil under AB1A / AB1B, opposite sense:
    - 7 turns of r 16 mm cut B at the board centre from 2.33 to 0.23 mT for -0.6 % depth (338 / 518 mm);
    - but the field at the board edge nearest the coil RISES from 5.45 to 7.48 mT. It moves the field, it does not remove it: only for a part that must sit at a board centre.
  - **Receive-board copper** (QA / QB, 16.99 m x 0.8 mm), R and depth change against 35 um with an ASSUMED 1.7 nV amplifier:
    - 18 um: 20.3 ohm, -0.43 %;
    - 35 um: 10.4 ohm;
    - 70 um: 5.2 ohm, +0.24 %;
    - 105 um: 3.5 ohm, +0.32 %.
    - Option B keeps the rigid 0.8 mm SB1R boards at 35 um; flex receive boards (option C) would cost 0.4 %.
- **System review across every lens:** docs/SYSTEM_REVIEW_OPTIONB.md.

## 26. Option B clean sheet: radial fin boards (variant BF; supersedes variant B's board islands) (2026-10-30; rf2/rf2_layout.py, rf2/head/rf2_head.py --variant=BF; MODELED / measured on the solids)
- **Why:** variant B kept option A's board outlines (the RF1 discs AB1A / AB1B, D78 CB1D) and moved only what collided (owner: "why are you using any of the old spec?"). BF designs the bay around the physics of the zone map instead.
- **Principle (rf2_layout.py):** the rim coil is axisymmetric, so its field has no azimuthal component. A board standing in a radial plane (a fin) has every loop normal along phi:

| Orientation | B across the board (peak) | EMF / cm2 | Receive coupling / cm2 | Solid-plane echo vs flat |
|---|---|---|---|---|
| flat (variant B) | 5.5 mT | 0.095 V | 67 nH | 1 |
| radial fin, exact | 0.000 mT | 0 | 0.0002 nH | about 1e-11 |
| fin, 1 deg tilt | 0.096 mT | 0.0017 V | 1.2 nH | 3e-4 |
| fin, 3 deg tilt | 0.29 mT | 0.005 V | 3.5 nH | 2.6e-3 |
| fin, 3 deg twist about the vertical | 0.11 mT | 0.0019 V | 1.3 nH | 1.6e-5 |

  - The coil-lead pair (178 deg) breaks the symmetry only locally: a fin in the lead plane sees 4.4 mT, a fin 4 deg away 0.08 mT. The HV fins sit at 170 / 186 deg.
  - The field on the axis is 1.2 mT axial, the same as elsewhere: a central hole has no electromagnetic role.
- **Layout (variant BF, all head checks pass):**
  - **13 radial fins**, 1.0 mm boards, z 4.0-12.4, r 19-103, parts 1.2 mm on both faces:
    - HV1 at 170 deg (MP1 v2 function), HV2 at 186 deg (TXJ: coil leads and the shaft TX pair); both start at r 40, >= 15 mm from any LV board;
    - analog A1-A3 at 100 / 122 / 144 deg;
    - digital D1-D8 at 214-71 deg.
  - **Printed central hub** (r 20) with slots for the LV fins' inner edges and a **4 mm central bore** through which the bay is potted from the centre outward.
  - **LV hub board** (r 20.5, z 11.6-12.4): star interconnect by soldered flex tails, no ring traces.
  - **Paired floor rails** on a printed floor hold each fin to < 1 deg.
  - **Radial sector walls** at 89 / 156 / 198 deg (the HV1 output flex passes the 156 deg wall's slot).
  - Coil, channel, combs, nickel screen coat, SH1 / QA / QB, display and lid as variant B.
- **Board area** (parts area, both faces) against the boards they replace:
  - analog 3 fins x 10.6 = 32 cm2 (AB1A + AB1B 25 cm2);
  - digital 8 x 10.6 = 85 cm2 (CB1D 48 cm2);
  - HV 2 x 8.0 = 16 cm2 (MP1 + TXJ 11.3 cm2).
- **head-check:BF:** 28 parts, 378 pairs, no interference; fins >= 0.5 mm to each other, the hub board and the walls; HV >= 15.2 mm to LV; mass 712 g (islands-only potting); potting analog 49, HV 31, digital 194 cm3.
- **What this changes downstream (stage 4 / Phase C):** the RF1 AB1A / AB1B / CB1D layouts and the MP1 / TXJ boards are re-laid out as fins (long, 8.4 mm tall boards: one row of parts per face, a bus along the fin). The netlist and the board generator need a 'fin' outline type.
- **Not modeled:**
  - fins' coupling into the quadrupole (bearing) channel, which is not axisymmetric;
  - parts' own thickness (3-D pieces such as the IXTY tab still see B_z and B_r over their height);
  - the display, which stays a horizontal flex (lead-frame drift, section 24).

## 27. Stage 3: parts, sensors, materials (2026-10-30; docs/STAGE3_PARTS.md, rf2/rf2_switch.py, DATASHEET_LOG RF2-DS-STAGE3)
- **Display drift withdrawn:** the SK9822-EC20 is a PCB-holder package (datasheet): 5e-6 x noise (CORRECTIONS).
- **TX switch:**
  - The IPB65R095C7's Coss is about 400 pF at the 26 V tail (READ): node 582 pF, gate 17.1 us.
  - The Wolfspeed C3M0280090J (900 V SiC) is about 110 pF: gate 14.0 us; 0.1 g 179 -> 195 mm; with syntactic potting 13.5 us, 197 mm.
  - Needs a +15 / -4 V gate driver.
- **Receiver:** AD7389-4 (4 x 16 bit simultaneous, 2 MSPS) proposed to digitise the full decay of mono, QA, QB and REF3; the gates move into firmware.
- **IMU BMI270:**
  - sweep speed and phase -> speed-matched filters;
  - position on the arc + quadrupole bearing -> target map on the display;
  - tilt -> ground model;
  - shock blanking;
  - auto re-zero when still.
- **Magnetometer (new, passive ferrous channel):** a 3 g nail about 0.9 mG at 100 mm against about 0.4 mG noise (vendor figure, UNVERIFIED). It needs the IMU orientation removed to < 0.1 %. Bench test.
- **Materials:**
  - Parylene C on analog / HV fins (moisture, leakage);
  - PTFE / FEP litz and syntactic foam (low eps);
  - glass-filled resin for the coil supports (low CTE).
- **Datasheets still to fetch:** docs/STAGE3_PARTS.md section 6.

## 28. Datasheet qualification, ferrous gradiometer, decay library (2026-10-30; rf2/rf2_qualify.py, rf2_fluxgate.py, rf2_decaylib.py; DATASHEET_LOG RF2-DS-OWNER2)
- **Owner datasheets (9):** BAT15-03W, MMC5983MA, LIS2MDL, UCC5350-Q1, SCS Parylene, GS-065-011-1-L, Rubadue litz, 3M glass bubbles, INA849. Values in the DATASHEET_LOG. Qualification:
  - **UCC5350-Q1 (SB, split outputs, +15 / -4 V):** qualifies as the SiC gate driver.
  - **GaN GS-065-011-1-L:** Coss about 125 pF at 26 V (READ), gate 13.74 us, against the SiC's 13.54 us. No gain, less voltage margin: SiC kept.
  - **BAT15-03W:** VR max 4 V, so ONLY as an anti-parallel pair across the LMH6629 input (BAV199 rail clamps stay). IF 110 mA sets Rin2 >= 57 ohm: 68 ohm. Mono noise 1.54 nV/rtHz; mono depth 346 / 442 / 530 mm (1 / 5 / 20 g) at the 16.3 us gate, against 340 / 434 / 521.
  - **INA849 on QA / QB:** 1.08 nV/rtHz; quadrupole (bearing) range 136 / 189 -> 145 / 201 mm (1 / 20 g).
  - **Syntactic potting** (3M bubble eps 1.2-2.0, Lichtenecker mixing ASSUMED): K1 at 60 % in silicone eps 1.75 (winding 92 pF, gate 13.5 us with SiC); in epoxy 1.88. iM30K (dense, crush-proof) 2.4-2.9: use K1 / K15.
  - **Parylene:** ParyFree on the analog / near-coil fins (eps 2.35, DF 0.0007, WVTR 0.09); N or C on the HV fins (7000 / 5600 V/mil).
  - **Magnetometers:** MMC5983MA (0.4 mG, disturbing field 10 G < the 12 G pulse: SET / RESET each pulse) or LIS2MDL (+-49 G, 3 mG). Both see only large or elongated iron (correction below).
  - **Litz:** fluoropolymer insulation available (Rubadue); permittivity still UNVERIFIED.
- **Ferrous gradiometer (rf2_fluxgate.py, docs/BENCH_FLUXGATE.md).** SUPERSEDED for a real sensor by section 34 (DRV425 datasheet noise; CORRECTIONS). Generic 10 pT/rtHz sensor, range at 1e-4 / 1e-5 residual mismatch:
  - 3 g lump 70 / 160 mm;
  - nail along the field 250 / 525 mm, across 60 / 135 mm;
  - 100 g lump 250 / 520 mm.
  - The head sensor sees 1.22 mT per TX pulse.
  - **Correction:** the earlier "0.9 mG at 100 mm" for a 3 g nail was 10x too high (CORRECTIONS).
- **Decay library v0 (data/decaylib, docs/DECAY_LIBRARY.md):** 2878 SIMULATED entries with ground balance in the features; baseline 85 % on simulated data. Compact non-ferrous and rings overlap by physics.
- **Litz insulation (added 2026-10-30, rf2_qualify section D; DATASHEET_LOG RF2-DS-FEP).** FEP eps 2.1 (Gund technical note). The gap between turns is modeled as insulation and potting in series (50 / 50 ASSUMED):

| Insulation | Potting | eps of the gap | Winding C | First gate | 0.1 / 1 g |
|---|---|---|---|---|---|
| FEP | K1 syntactic in silicone | 1.91 | 101 pF | 13.62 us | 197 / 344 mm |
| enamel + nylon serve (eps 3.5 ASSUMED) | K1 syntactic | 2.33 | 123 pF | 13.92 us | 196 / 343 mm |
| FEP | 832TC epoxy | 2.68 | 141 pF | 14.15 us | 194 / 343 mm |
| enamel + nylon | 832TC epoxy | 3.60 | 190 pF | 14.73 us | 191 / 342 mm |

  - **FEP chosen** over PTFE: same eps, but PTFE creeps (both sources), and coil geometry must not move.
  - The winding remains a small part of the node (the SiC switch and the leads are about 160 pF).

## 29. Stage 4 zone-rule checks, Stage 4b fin boards, FEP litz and sleeves (2026-10-30; rf2/head/rf2_zonerules.py, TXF in rf2_netlist.py; MODELED / tool-checked)
- **Stage 4: `rf2/head/rf2_zonerules.py` (runner step `zonerules`).** The zone map's rules (section 24) are now automatic checks that fail the run:
  - **BOM:** no aluminium electrolytic, metal-can or ferrite part, and no inductor, in any netlist board.
  - **Copper (read back from the built boards):** no solid copper zone; a hatched zone needs a declared slit border; no closed copper loop above 0.1 cm2 on the analog / HV boards (MP1, TXJ, TXF). KiCad edge keep-outs are rule areas and are skipped (my first version counted them and wrongly failed every board).
  - **Fins:** board height = slot height (8.4 mm), board thickness = fin thickness (1.0 mm), board inside the fin's radial span, rail tilt < 1 deg.
  - **Head SPEC (variant BF):** FEP litz, FEP sleeves and the Parylene coating are present; the comb slot (1.3 mm) clears the litz OD (1.2 mm) by 0.1 mm; HV fins are 8 deg from the lead path (178 deg), limit 4 deg.
  - **Self-test:** a synthetic aluminium can and a 2.6 cm2 copper loop are both caught, so the checks can fail.
  - **Not covered:** the temperature-drift side of a metal part is still the zone study's job (rf2_zones.py), not a board check. The loop-area check measures closed copper loops in one net; a signal-and-return loop between two nets is not measured yet.
- **Stage 4b, first fin board: TXF.** TXJ's function (coil litz, shaft cable and sense wire for each leg) as a 32.0 x 8.4 x 1.0 mm fin at 186 deg, fin centre r 86 (rim end r 102, inside the fin's r 40-103 span).
  - TXJ's two columns become two groups end to end along the radius, 3.5 mm apart; each leg is a straight 2.5 mm bus on both copper layers (a locked pre-route: Freerouting could not route a 2.5 mm class between 3 mm pads and fell back to 0.2 mm tracks, which KiCad DRC rightly rejected).
  - **Result:** DRC 0, 0 unconnected, HV clearance 3.25 mm (rule 6: 1.0 mm), parity clean, Gerbers written. TXJ is unchanged and stays the option A / B board.
  - **Added to the board builder:** a `bus` key (locked straight buses) and fin placement in head coordinates (`placement_in_head` for a board with `head.fin`).
- **Litz and sleeves: FEP (SPEC `materials`, variants B and BF).** FEP-insulated litz for the coil (eps 2.1, no creep); FEP-jacketed hookup wire for the shaft HV pair and sense wires, and FEP tubing over the litz lead pair; Parylene (ParyFree, else C) on the analog and near-coil fins; K1 syntactic foam around the coil. Winding capacitance with FEP litz in K1 foam: 101 pF, first listen 13.62 us (section 28).
  - **UNVERIFIED, must be confirmed with a vendor before ordering:** the finished litz OD (1.2 mm is carried over from the enamel-served wire), the FEP wall thickness, and the voltage rating of the finished FEP wire (>= 630 V, rule 6). The eps 2.1 is from a supplier technical note, not a grade datasheet.
- **Still open in Stage 4b:**
  - **MP1 v2 as a fin (HV1 at 170 deg, r 40-103):** needs a decision on the LMH6629 stage and its footprint. The LMH6629 is a single op-amp, and the WSON-8 (NGQ08A) has pins 1 PD, 2 FB, 3 IN-, 4 IN+, 5 V-, 6 COMP, 7 OUT, 8 V+ (TI SNOSB18I, read). Its minimum stable gain is 4 (COMP low) or 10, so a per-leg gain stage followed by a low-noise difference stage is the likely topology, but no LMH6629 SPICE model is in the repo and the WSON land pattern has not been read, so the noise and stability of the whole chain are not yet modeled. The IXTY08N100D2 pins are read (1 gate, 2 and 4 drain / tab, 3 source); its land pattern shows a 6.40 mm tab pad, which leaves little of the fin's 7.4 mm usable height, so the tab pad orientation along the fin needs checking.
  - **AB1A / AB1B / CB1D as fins:** Phase C (the RF1 boards are not in the netlist yet); the fin areas (analog 32 cm2, digital 85 cm2) are the budget.

## 30. Light plate, wave-map interface, handle pod, assembled construct (2026-10-30; rf2/rf2_lightplate.py, rf2/rf2_ui.py, head/rf2_pod.py, head/rf2_construct.py; MODELED)
- **Light plate (variants B and BF; option A keeps the clear lid).** The lid is an opaque matt black PETG plate with one conical well over each of the 522 LEDs (bottom Ø2.9 mm just clear of the 2.0 mm square emitter's 2.83 mm diagonal, mouth Ø6.0 mm, through the 1.5 mm lid: cone half-angle 46 deg). The wall carries a **white diffuse non-metal liner** (TiO2 paint); the well is filled flush with clear resin, which seals the plate and acts as a lens.
  - **Optics (Monte Carlo, Lambertian 2 x 2 mm emitter, liner reflectance 0.90 ASSUMED):** exit efficiency 0.97 with the cone against 0.41 for a straight Ø2.9 mm bore with an absorbing wall; beam median half-angle about 40 deg, 90 % inside 60 deg. At reflectance 0.98 it is 0.99.
  - **A metallised liner is banned:** metal near the coil is an echo target (rule 5, zone rules). A mirror finish needs its own eddy study; the zone-rule check now asserts the liner is non-metal.
  - **Checks (head-check:BF / B):** 522 wells for 522 LEDs, centre offset 0.0 mm, web 2.04 mm at the mouth (printable minimum 0.8 mm ASSUMED), head height unchanged at 15.65 mm. **Numbers that moved:** option B mass 693 -> 677 g (islands only; full fill 852 -> 836 g), option BF 712 -> 696 g (910 -> 894 g); option A unchanged at 761 g.
  - **Not modeled:** the clear resin's refractive losses, the liner's real reflectance, light leaking through the 1.5 mm PETG walls, and what the lit wells look like to a person (no human-factors test).
- **Interface model (`rf2_ui.py`, step `ui`).** Redundant coding, so colour is never the only channel:
  - **Class -> hue and timbre:** iron red (0 deg) with a 150-220 Hz buzz; foil / thin ring violet (280 deg) with a soft 700 Hz sine; non-iron by decay time tau: 10 us gold-yellow (50 deg) through green (about 150 deg at 100 us) to cyan-blue (200 deg at 300 us), pitch 400 to 1200 Hz. This is the **decay class, not the metal**: conductivity x size^2 is ambiguous (DECAY_LIBRARY.md).
  - **Size -> brightness and loudness. Depth -> ripple speed and beep rate** (12 rings/s and 16 beeps/s at the surface, falling with depth).
  - **Wave map:** a ripple spreads from the target's position over the 13 rings; a target within 12 mm of the head centre collapses it to the centre ring (bullseye). Figure: `out/rf2_ui_wavemap.png`; sample audio: `out/audio_*.wav`.
  - **Mode selector (AUDIO | LED | BOTH):** audio is silent, and the display dark, until a detection above the confidence threshold (0.5, ASSUMED). In BOTH the ripple emission and the beep onset share one clock.
  - **Trigger:** hold = pinpoint / enhanced projection (1.5 x ripple rate and more pulses averaged: 400 pulses is about +13 % depth on 1 g, section 18); double-press = set signature (store class and tau, +-0.15 decade): matches get the full light and sound, other targets 35 %.
  - **Checks (15, all can fail):** silence without a detection, mode isolation, phase lock, depth and size monotonic, hues at least 30 deg apart, pitch rises with tau, signature match / reject, pinpoint faster, dark when idle, bullseye, determinism.
  - **Constraint kept:** LEDs are written only in the quiet slot and are dark in receive windows (section 24 timing plan); the model gives frame content, not timing. The achievable visible brightness is limited by that duty (not modeled).
- **Handle pod (`head/rf2_pod.py`, step `pod`).** A printed control pod: three-position detented selector collar (30 deg apart, 10 mm or more between detents on the collar) with icon windows, an underside trigger lever with a tactile-switch pocket (travel at the finger 2.4 mm), a sounder pocket under a drilled grille, and a battery bay. **Every dimension is ASSUMED** (no shaft, switch, sounder or battery datasheet in the repo); the checks prove the arrangement fits itself with 1.6 mm walls and no interference. **The sounder lives in the pod, not the head:** a loudspeaker magnet or any ferrite is a metal target next to the coil; use a magnet-free piezo or a remote sounder.
- **Construct (`head/rf2_construct.py`, step `construct`).** One assembled model of variant BF: 34 components (printed housing, 13 fin boards as real 1.0 mm slabs, receive and shield boards, coil, harness, saddles, three potting cavities) as `out_BF/construct/assembly.glb` with a component manifest (`assembly_manifest.json`) and a view (`assembly_view.png`).
  - **Harness:** four wires from TXF (coil litz A / B to the coil's lead slot, shaft cable A / B up through the gland), each: pad face, 3 mm straight strain relief, a lane in the 178 deg gap between the HV fins, the destination. The lane (offset from the fin and height) is searched so wires keep 0.3 mm to each other and to every solid. Result: wire-to-wire 0.349 mm, wire-to-solid 0.30 mm or more, cable passes the Ø8 gland hole, no wire sweeps round the axis (rule 5). Lengths 15.7 / 35.0 (coil litz), 18.4 / 35.2 mm (cable). Loop areas: coil lead pair 0.92 cm2, shaft pair 1.22 cm2 (bounds, in the fin gap; twist the pairs).
  - **Molded wire saddles:** printed posts (Ø2.4) from the floor with a half-round notch for the wire, about every 22 mm; a lane under 5 mm gets none (held by the pad's strain relief and the potting, must be <= 25 mm long: two wires here are).
  - **Potting cavities:** analog 53.4, HV 33.2, digital 205.0 cm3 (free volume minus every solid, wire and saddle), filled from the hub bore. **Open:** vent paths (the display flex covers the lid over the bay, so vents go through the shell wall's high side).
  - **PENDING (listed, not checked):** the MP1 v2 sense wires (MP1 v2 fin not built), the MP1 LV output flex through the 156 deg wall, the AB1 / CB1D fins (Phase C), pad solder cups and strain-relief clips. No STEP export: the model is mesh (GLB / STL); a STEP of the printed parts is not built.

## 31. SPICE models, MP1 v2 chain findings, and the test / simulation acceleration program (2026-10-30; MODELED / tool-checked)
- **The three SPICE PDFs (AN-1516, SLOA071, the DAC models article) are method documents, not part models.** They do not give the data an MP1 v2 build needs. What they led to: TI's own LMH6629 SPICE model (TI snom339, TINA-TI; PSpice copy snom133) and OPAx211 model (sbombw9), saved in `data/spice/` with checksums (`SHA256SUMS`, checked by `tests/selftest.py`). AN-1516's test circuits became the bench `rf2/head/rf2_opamp_qualify.py`.
  - **LMH6629 model: qualified.** 14 of 14 comparisons with the datasheet's typical column (3 dB bandwidth 838 vs 900 MHz at gain 10, AVOL 78.6 vs 78.5 dB, en 0.69 nV and in 2.6 pA at 1 MHz, slew 1636 vs 1600 V/us, rise 0.83 vs 0.90 ns, Ib 14.7 vs 15 uA, Iq 16.0 vs 15.5 mA, overload recovery inside 2 ns, open-loop phase -134 deg at 1 GHz vs -142, CMRR 82 vs 87 dB). The registry `state/qualified_models.json` records the pass against the model file's checksum and the bench's checksum; the chain study refuses a model that changed or never passed. The model was written against datasheet SNOSB18E; the repo has SNOSB18I.
  - **Not obtained or not usable:** Littelfuse (IXTY08N100D2) and Nexperia (BAV199) models: HTTP 403, so both stay datasheet-anchored generics. The TI OPAx211 model converts to ngspice (`spice_compat.py`) but then shows a constant 2.85 V output offset, so the difference stage is a behavioral OPA211 (GBW 80 MHz, 1.1 nV/rtHz, SBOS377L). **Still missing for the MP1 v2 board:** the LMH6629 WSON-8 (NGQ08A) land pattern (not read yet) and the TO-252 tab orientation on the 8.4 mm fin.
  - **Other uploads:** `Highspeed_.pdf` is the LMH6629 datasheet already in the repo (same SHA-256). The ADI OP470 (quad, specified at +-15 V, 3.2 nV/rtHz typ) cannot run on the +5 V analog rail and is about 3x noisier than the OPA211: not chosen.
- **MP1 v2 chain study (`rf2/head/rf2_mp1v2_chain.py`, step `study:mp1v2_chain`) shows the design chosen on 2026-10-30 is not closed.** Chain: IXTY08N100D2 limiter (Rsrc 22) -> BAV199 clamp -> Rin2 -> LMH6629 (gain 10, COMP high) per leg -> difference stage (gain 2.4) -> 24 overall. Both legs, 460 V turn-off from the 8.06 A coil.

  | Rin2 | Rf / Rg | gain | -3 dB | noise per leg equivalent (100 kHz) |
  |---|---|---|---|---|
  | 47 | 240 / 26.7 | 23.5 | 25 MHz | 1.65 nV/rtHz |
  | 47 | 90 / 10 | 23.5 | 25 MHz | 1.57 |
  | 68 | 240 / 26.7 | 23.5 | 25 MHz | 1.77 |
  | 100 | 240 / 26.7 | 23.4 | 25 MHz | **1.93** |
  | 100 | 90 / 10 | 23.4 | 25 MHz | 1.86 |
  | v1 (3 x 470 ohm, OPA2211 difference amp) | | 9.9 | | 6.69 |

  - **Noise:** 1.93 nV/rtHz per leg equivalent with the chosen values, not the 1.7 used in the depth model (about -2.1 % depth if the sixth-root rule of section 18 holds). (First reported as 1.97: the stand-in stage's DC-operating-point error, below, inflated it.) It is still about 3.4 x below v1's modeled 6.7 (v1's real chain gain is 9.9, not 24, and its noise 6.7, not 5.0).
  - **Amplifier input current:** with the coil released into the 460 V clamp the LMH6629 input takes **24 mA (Rin2 100) to 35 mA (Rin2 68)**; its rating is 10 mA. A second BAV199 pair on the amplifier input does not help. The clamp node reaches 6.5 V at about 0.4 A: the charge the limiter's Cds passes (24 pF x 460 V, about 11 nC with the linear capacitance; the datasheet's own C(V) slope suggests about half, an extrapolation past its 40 V graph) goes through the clamp diodes. The rest of the Rsrc sweep (47 to 220 ohm) leaves the peak unchanged: it is displacement current, set before the source resistor.
  - **Recovery:** the stage-1 outputs settle to 1 mV at the coil terminals after **19.5 us**, not inside the 16.3 us gate (14.7 us was the clamp node alone). The stand-in second stage is excluded (it has no anti-windup; an earlier version of this study measured 30 us at the output and that was the stand-in's own windup).
  - **Limiter candidates (the four IXYS sheets and the Infineon BAV199 uploaded 2026-10-30; DATASHEET_LOG RF2-DS-LIMITERS).** Same chain, Rin2 100, Rsrc 22, each limiter with its datasheet numbers (max RDS(on), Coss / Crss at 25 V held constant: pessimistic):

    | Limiter | BVDSX | RDS(on) max | Coss / Crss | clamp RS | noise per leg | clamp node peak | LMH6629 input peak | settles to 1 mV |
    |---|---|---|---|---|---|---|---|---|
    | IXTY08N100D2 (chosen) | 1000 V | 21 ohm | 24 / 6.5 pF | 2 | 1.93 nV | 6.52 V | 24.3 mA | 19.5 us |
    | **IXTY01N100D** | 1000 V | 80 ohm (50 typ) | 12 / 2 pF | 2 | 2.21 nV | 6.03 V | 19.5 mA | 17.5 us |
    | IXTY02N50D | **500 V: fails rule 6** | 30 ohm | 25 / 5 pF | 2 | 1.95 nV | 6.50 V | 24.2 mA | 18.5 us |
    | IXTY08N50D2 | **500 V: fails rule 6** | 4.6 ohm | 35 / 11 pF | 2 | 1.85 nV | 6.95 V | 28.5 mA | 20.9 us |
    | IXTY08N100D2, clamp at its datasheet-MAX forward drop | 1000 V | 21 ohm | 24 / 6.5 pF | 4 | 1.93 nV | 7.34 V | 32.4 mA | 19.4 us |
    | IXTY01N100D, clamp at max forward drop | 1000 V | 80 ohm | 12 / 2 pF | 4 | 2.21 nV | 6.40 V | 23.2 mA | 17.5 us |

    - **What the comparison says.** The spike is displacement current through the limiter's Coss and Crss, so the part with the least capacitance protects best: the IXTY01N100D cuts the clamp-node peak by 0.5 V and the amplifier current by 20 %, and settles 2 us sooner. But it still has 19.5 mA (rating 10 mA) and 17.5 us (gate 16.3 us), and its 50-80 ohm channel costs noise (2.21 nV at the 80 ohm maximum against 1.93 nV). **No single candidate closes the design.** The two 500 V parts are out on rule 6 and are no better on the spike (the 4.6 ohm part is the quietest, 1.85 nV, but the worst spike).
    - **The clamp diode matters as much as the limiter.** Using the BAV199's datasheet-maximum forward drop (1.25 V at 150 mA) instead of the typical raises the clamp node to 7.3 V and the amplifier current to 32 mA for the current part. Both BAV199 sheets stop at 150 mA, so the diode's drop at the 0.4 A spike is an extrapolation either way.
    - **Next candidates to simulate (not done):** the IXTY01N100D with parallel or Schottky clamp devices (a lower drop at 0.4 A), a cascode of two 500 V devices (Coss in series is half, and 2 x 4.6 ohm is 9.2 ohm, but it needs voltage balancing and each device would see 230 V peak), and the datasheet's own Coss(V) fall beyond 40 V (an extrapolation).
  - **Protection options (`rf2/head/rf2_mp1v2_protect.py`, step `study:mp1v2_protect`; owner 2026-10-30: clamp first, then a cascode, then the Coss(V) curves).** Diodes fitted to their datasheet forward-voltage tables (BAV199 maxima, identical in the Nexperia and Infineon sheets; BAT54 max from Diodes DS11005, typical from onsemi BAT54LT1/D; every fit extrapolates past its table to the 0.4 A spike). Rin2 100 ohm, Rsrc 22 ohm.

    | Limiter | Clamp (per leg, each rail) | noise per leg | clamp node | LMH6629 input | settles | per-diode peak (rating) |
    |---|---|---|---|---|---|---|
    | IXTY01N100D | 1 x BAV199 (max) | 2.21 nV | 6.31 V | 22.2 mA | 17.4 us | 194 mA (500) |
    | IXTY01N100D | 2 x BAV199 | 2.21 | 6.18 | 20.9 | 17.4 | 97 |
    | IXTY01N100D | BAV199 + BAT54S (max) | 2.21 | 6.06 | 19.8 | 17.5 | BAT54 166 (300) |
    | IXTY01N100D | BAV199 + BAT54S (typ) | 2.21 | 5.65 | 15.8 | 17.6 | BAT54 200 (300) |
    | IXTY01N100D | 2 x BAT54S (max) | 2.21 | 5.80 | 17.2 | 17.5 | 99 (300) |
    | IXTY01N100D | 2 x BAV199 + 2 x BAT54S (typ) | 2.21 | 5.52 | 14.5 | 17.5 | BAT54 101 (300) |
    | IXTY08N100D2 | 1 x BAV199 (max) | 1.93 | 6.59 | 25.0 | 19.2 | 431 (500) |
    | IXTY08N100D2 | 2 x BAV199 + 2 x BAT54S (typ) | 1.93 | 5.68 | 16.0 | 19.6 | BAT54 220 (300) |
    | IXTY08N100D2, Coss(V) charge-equivalent (14.0 / 6.3 pF) | 1 x BAV199 | 1.93 | 6.42 | 23.3 | 19.2 | 287 |
    | IXTY01N100D, Coss(V) charge-equivalent (7.7 / 2.4 pF) | 1 x BAV199 | 2.21 | 6.24 | 21.5 | 17.4 | 143 |
    | **IXTY01N100D, Coss(V) charge-equivalent** | **2 x BAV199 + 2 x BAT54S (typ)** | 2.21 | **5.48** | **14.1** | 17.5 | BAT54 76 |
    | Cascode 2 x IXTY08N50D2 (Coss(V) to 230 V) | 1 x BAV199 | **1.86** | 6.82 | 27.3 | 19.6 | 641 (**above 500**) |
    | Cascode 2 x IXTY08N50D2 | 2 x BAV199 + 2 x BAT54S (typ) | 1.86 | 5.81 | 17.3 | 20.2 | BAT54 323 (**above 300**) |

    - **1. Clamp:** a lower clamp drop is the strongest lever on the amplifier current: 22.2 -> 14.5 mA with two BAV199 and two typical BAT54S per rail. It does not change the noise (the clamps are reverse-biased at rest) or the settling. But it relies on the BAT54's typical forward drop: at its datasheet maximum the Schottky is no better than a BAV199 at 0.4 A (fit: 1.96 V against 1.55 V). The BAT54 has 2 uA maximum leakage (BAV199: 5 nA) and up to 10 pF.
    - **2. Cascode:** two 500 V depletion FETs in series share the flyback (upper 195 V, lower 262 V peak, both under 80 % of 500 V) and give the lowest noise (1.86 nV). But the upper gate divider and the larger capacitances inject more charge: 27.3 mA with one BAV199, settling 19.6-20.2 us, and the clamp diodes exceed their repetitive ratings. Not better. Whether a two-device 500 V stack meets rule 6 (630 V parts) is also a rule question.
    - **3. Coss(V):** integrating the datasheet curves to the real peak VDS (graph to 40 V, power-law extrapolation beyond) gives charge-equivalent capacitances of 14.0 pF (IXTY08N100D2) and 7.7 pF (IXTY01N100D) instead of the 24 / 12 pF at 25 V. The constant-capacitance results were pessimistic by only 3-7 % on the amplifier current: the charge below 10 V, where the capacitance is hundreds of pF, dominates.
    - **No option passes** (amplifier input < 10 mA, settling < 16.3 us, diodes inside their repetitive ratings). The best, IXTY01N100D with two BAV199 and two BAT54S per rail, reaches 14.1 mA and 17.5 us. **Settling is set by the limiter, not the clamp** (17.4-17.6 us for every IXTY01N100D option, 19.2-19.6 us for the IXTY08N100D2). The coil node alone is quiet sooner (its 460 V clamp lasts L x I / V = 5.8 us, then about 6 us of critically damped ring-down), so the front end adds about 4-5 us.
    - **Next levers (not yet simulated):** Rin2 150-220 ohm with the strong clamp (current down, noise up: about 2.4 nV); a lower clamp rail (a dedicated +3.3 V clamp rail would keep the clamp node further from the LMH6629's 5.3 V ESD knee); the limiter's recovery (gate network, Rsrc); or a first gate at about 18 us and its cost in small-target depth (rf2_timing).
    - **Simulation note.** The stand-in second stage's output limit was a max() / min() behavioral source; it made ngspice return an inconsistent DC operating point (its pole node at 6.4 V while its output sat at 2.5 V), which appeared as about 150 uA of false current in the reverse-biased clamp diodes and inflated the noise (IXTY01N100D 2.43 -> 2.21 nV, IXTY08N100D2 1.97 -> 1.93 nV; the transients moved < 0.5 %). It is now a smooth tanh limit, and the self-test checks the operating point. Saving only the measured vectors and reltol 1e-3 made each transient about 30 x faster; the study re-runs two reference cases at the tight settings and agrees within 0.33 %.
  - **Clamp rail:** the clamp current goes into the +5VA rail (and AGND): 79 uJ per pulse into the rail's decoupling is about 1.6 V on 10 uF. The rail needs to absorb it (a larger reservoir, or a separate clamp rail) or the clamp must go elsewhere. v1 has the same issue.
  - **What it means:** the protection has to be redesigned before the board is laid out: reduce the injected charge (a lower-Coss limiter or a cascode / second device), a stiffer low-drop clamp (parallel devices) with a protected rail, and a series resistance that does not cost noise. Candidates to simulate next: parallel clamp diodes (RS 2 -> 1 -> 0.5 ohm), a Schottky second clamp, the datasheet C(V) slope, and a longer first gate (20 us costs 0.1 g depth, section 18).
  - **Model limits:** the FET is a level-1 model without Cgs (Ciss 325 pF is not in it), the BAV199 a generic diode, the second stage a behavioral op-amp, capacitances linear (a voltage-dependent version ran more than 14 minutes per transient and was abandoned).
- **Acceleration program (everything below is in the runner or `make`).**
  - **In-step result cache (`src/simcache.py`).** An expensive deterministic computation whose result is a small JSON value is stored under `state/simcache/` (committed, so a new container starts warm), keyed by the SHA-256 of the function's source, a list of `uses`, the CONTENT of its input files, tool versions and arguments. Adding one point to a sweep runs one point; a board whose copper did not change skips its KiCad DRC and copper check (boards are keyed without KiCad's fresh uuids, timestamps and item order; the display flex step took 230 s the first time and **56 s** with unchanged copper: 3 hits saved 177 s). SPICE benches (qualify, chain), `kicad_drc` and `copper_check` use it. `SIMCACHE=0` bypasses, `SIMCACHE=refresh` recomputes; `make cache` lists it. The chain study's 302 s sweep is now an instant re-run; a change of the function's source re-runs only that function.
  - **Runner upgrades (`run.py`).** The ledger records every input's hash and the last 8 run times, so `--plan` names the changed input ("inputs changed: rf2/head/rf2_boards.py") and estimates the time, `--why STEP` explains one step, `--timing` shows where the time goes (`make why STEP=...`, `make timing`).
  - **Model registry.** `state/qualified_models.json` ties a pass to the model's and the bench's checksums.
  - **Self-test (`tests/selftest.py`, step `selftest`, `make test`).** 16 tests of the tools the checks rely on, each able to fail: cache hit / miss / invalidation by source, by `uses`, by file content / corrupt entry / bypass; the converter; the model checksums; the bench passes the TI model **and fails a wrong model**; the runner skips, names the changed input, sees a missing output and a re-run dependency.
  - **Still one background job at a time** (CLAUDE.md rule 10), so speed comes from not repeating work, not from parallelism.

## 32. Power button, continuous boost, display and audio coding v2, multi-target separation (2026-10-30; owner requests; MODELED)
- **Power button (`head/rf2_pod.py`).** A recessed 12 mm momentary push button on top of the handle pod, directly above the trigger (the thumb's rest while the index finger is on the trigger), 66 mm from the selector collar so the two cannot be confused. Hold 2 s to switch on or off (a knock cannot do it); a light-pipe ring around it shows green on, amber boost, red low battery. It drives the PM2 power-path controller as a soft latch; the PM2 fuse stays in series. Button part ASSUMED (a sealed 12 mm tactile). Checked: no interference, 7.5 mm of wall to the battery bay, 1 mm recess.
- **Continuous boost (`rf2/rf2_continuous.py`, study `continuous`).** The trigger may now be held indefinitely: 12.74 A pulses at 400 Hz, alternating 163 us and 463 us (300 us flat-top), turn-off 9.2 us into the 460 V clamp.

  | Part | Boost, continuous | Rating / limit | Verdict |
  |---|---|---|---|
  | Coil I^2 R (RMS 3.67 A, 0.53 ohm) | 7.1 W into the potted coil channel | thermal only; whole-head surface rise about 9 K at h 8 W/m2K (ASSUMED); the rise inside the foam is NOT modeled | **open** |
  | TX switch C3M0280090J | 12.7 A peak, 3.64 A RMS, 6.1 W | IDM 22 A, ID 7 A (100 C); TJ 89 C with a 5 C/W heat sink (ASSUMED), 283 C on bare PCB | ok **with a heat sink** (neck design) |
  | Clamp diode US3M | 24 mA average, 12.7 A for 9 us per pulse | IO 3 A, IFSM 120 A, 1000 V | ok |
  | Damping resistor Rd 408 ohm | 2.1 W (V^2 / R during the clamp and the on-time) | needs >= 4.2 W, >= 630 V, on the HV fin in the potted head | **open (part and thermal path)** |
  | Clamp absorber | 8.9 W if dissipative | a 460 V TVS stack would need a heat sink; a regenerative clamp returns most of it to the bulk bank | **open (recommend regenerative)** |
  | TXF buses (2.5 mm, both layers, 1 oz ASSUMED) | 1.84 A RMS per layer | +1.2 K (IPC-2221) | ok |
  | Shunt WSL2512 10 mohm | 0.13 W | 1 W at 70 C | ok |
  | Bulk bank 9 x Panasonic ZC 100 uF | 0.38 A RMS each | 1.6 A RMS (100 kHz; the 400 Hz multiplier not read) | ok, multiplier open |
  | Battery (7S, 25.2 V) | 36.4 W (dissipative clamp) / 28.3 W (regenerative, 75 % recovery ASSUMED), incl. 10.6 W head electronics at the LED cap | 2.7 / 3.5 h per 100 Wh in continuous boost; scan mode 20.6 / 17.4 W, 4.9 / 5.8 h per 100 Wh | pack size open |

  - **Boost and MP1 v2:** at 12.74 A the LMH6629 input peak rises only slightly (current design 25.0 -> 27.9 mA; best option 14.1 -> 14.7 mA) but the settling slips by 3.4 us (17.5 -> 20.9 us; 19.2 -> 22.5 us), because the clamp phase lasts L I / V = 9.2 us instead of 5.8 us. The boost first gate moves later accordingly (rf2_timing).
  - **Conclusion:** continuous boost is within the ratings of the switch (with a heat sink), clamp diode, buses, shunt and bulk bank. Before "indefinite" can be claimed: a heat sink for the switch, a regenerative (or heat-sunk) clamp, a >= 4.2 W 630 V damping resistor with a thermal path out of the potting, and a coil-channel thermal model; firmware gets a thermal limit (coil and driver temperature sensors, the "thermal limit" status screen) that backs the boost off if a limit is reached.
- **Display and audio coding v2 (`rf2/rf2_display.py`, step `display`; 12 checks).**
  - Dark while sweeping; a detection lights a **blob at the target's place**. Its **radius grows with the target's size** (1 ring for 0.1 g to all 13 rings at >= 100 g, logarithmic); it **pulses at a rate set by depth** (shallow fast) with a softer edge when deep; **colour = class**, **brightness = confidence**, a **dark cross = iron**, a **white halo = the stored signature matched**.
  - **Several targets:** one blob each; where blobs meet, the boundary LEDs of the weaker blob go dark (a seam) so two blobs are always seen as two; their pulses are phase-staggered. **Audio:** one voice per target in time slots (up to 3), each with its own class pitch, depth beep rate and size loudness; silent in LED mode.
  - **Pinpoint (trigger held):** the view zooms x 2 around the strongest target.
  - **Status screens** (each recognisable by shape): power-on self-test (a ring runs centre to rim: every chain lit once), ground learning (rim fills clockwise), battery gauge, low battery (blinking red at the heel), interference (slow violet rim), sweep too fast (amber arc on the side of motion), thermal limit in boost (segmented orange rim), heartbeat (one faint centre LED every 3 s, optional).
  - Figure: `head/out/rf2_display_frames.png`.
- **Multi-target separation (`rf2/rf2_separation.py`, study `separation`).** How the firmware can tell two targets apart:
  - **By decay time, from one pulse** (full waveform on the AD7389-4; non-negative decomposition over 80 decay constants, then a model-selection test that keeps two components only if they clearly beat one, BIC > 10): two targets are resolved (>= 80 %) when their decay times differ by **3 x at SNR 10, 2 x at SNR 30, 1.6 x at SNR 100, 1.3 x at SNR 300**. Without the model-selection test a single target is wrongly split into two in **27-60 %** of cases at SNR 10-100; with it, **0 %** at every SNR tested. Same metal and size give the same decay: those can only be split by position.
  - **By position, from the sweep** (mono |B|^2 of the rim coil, gyro position): two 1 g at 100 mm need about **225 mm** between them; 1 g at 50 mm and 150 mm 110 mm; 1 g at 100 mm and 200 mm 330 mm; two 5 g at 250 mm 275 mm. The rim coil's wide response limits this; the quadrupole bearing channels (not modeled here) separate targets on opposite sides of the head more closely.
  - **Firmware plan:** a target tracker keeps a list (position from gyro x bearing, depth from the response width and amplitude, decay class, confidence) built from both handles, and only reports a second target when the model-selection test and the spatial map agree; that list drives the display and the audio.

## 33. Display and audio v3 (clean, lock-on, sonar) and the flip-up screen cassette (2026-10-30; owner requests; MODELED)
- **Display v3 (`rf2/rf2_display3.py`, step `display3`; 16 checks).** Supersedes v2 as the default; v2 stays as the 'Map' profile.
  - **Sweep:** dark until a signature; each target is a **small dot** where it is under the head: 1 ring below 1 g, 2 rings 1-10 g, 3 rings above (capped, never smaller than its 3 nearest LEDs), breathing at its depth rate. **Lock-on:** a target within 12 mm of the head centre fills the **central disc (r 16 mm, rings 1-2)** solid in its class colour, a white ring flashes once on acquisition, other targets dim to half; the audio switches to a steady pulsing lock tone.
  - **Trigger held (pinpoint):** a **sonar ring** leaves the centre, runs to the rim in 0.6 s and comes back in 0.6 s, continuously. Where it crosses a target, the target **flashes (echo) and its echo blip sounds at the same instant**; every launch plays a soft ping. Targets therefore light and sound **in order of their distance from the centre** (separated in time as well as place). Centring the head on one gives the same lock as in the sweep.
  - **Light and sound on one clock:** the audio events (ping, echo, beep, lock) are generated from the same timeline as the LED frames; the checks require every echo flash to have its sound within 1 ms.
  - **Profiles** (picked on the flip-up screen): LED **Clean** (default), **Map** (v2 size-scaled blobs), **Sonar** (the ring also while sweeping), **Night** (25 %, lock only); audio **Class tones** (pitch = class, rate = depth; default), **Depth pitch** (pitch falls with depth, class by timbre), **Quiet** (lock and strong targets only), **Stereo** (headphones, each target panned by its bearing).
  - Figures: `head/out/rf2_display3_frames.png`; screen mock-ups `head/out/rf2_screen_mockup.png`.
- **Flip-up screen cassette (`head/rf2_pod.py`).** Behind the power button on top of the pod (the thumb tip):
  - The thumb presses the cassette's **front edge**; a **push-push latch** (spring and heart-shaped cam, as in an SD-card socket) releases it; a torsion spring lifts it; it is pulled up to **70 deg**, where a detent locks it. It hinges on its **rear** edge, so the face tilts toward the user (face normal (0.94, 0, 0.34) toward the grip end).
  - Checked: stowed 0.6 mm below the body surface; 2.0 mm of wall to the battery bay; open, 20 mm clear of the power button and with no interference; the latch keeps 4.7 mm of wall to the power-button pocket; a flex-cable slot runs from the pocket floor to the electronics.
  - **Screen (ASSUMED until a datasheet is on file):** a 1.28 in, 128 x 128 reflective memory LCD of the Sharp LS013B7DH03 class (readable in sunlight, microwatt power; it sits in the handle, about 0.9 m from the coil). Pages: target (depth, size in g equivalent, decay class and decay time, confidence, LOCK or bearing) and settings (LED and audio profiles). Text is limited to 23 characters per line.
  - Render: `head/out/pod/rf2_pod_view.png` (closed and open).
- **Not done:** the screen part and its driver (SPI from the handle UI board), the latch / spring parts, the UI board itself, and any human-factors test of the coding.

## 34. Owner-supplied datasheets, batch 3: clamp recovery, HV parts, power, sensing and UI parts (2026-10-30; MODELED; DATASHEET_LOG RF2-DS-OWNER3)
- **Clamp reverse recovery (new, `rf2_mp1v2_protect.recovery_check`).** The BAV199 fits had no stored charge; the Nexperia 2023 sheet gives trr 0.8 typ / 3 max us (Infineon 0.6 / 1.5).
  - Method: TT = trr / ln 2 (charge-control model, ASSUMED conversion); 8.06 A turn-off.
  - Single BAV199 (IXTY08N100D2): settling 19.17 / 18.95 / 18.01 / **21.35 us** for no TT / Nexperia typ / Infineon max / Nexperia max; up to 36 mA reverse-recovery current.
  - Schottky-assisted (IXTY01N100D, 2 x BAV199 + 2 x BAT54S typ): **17.50 us for every trr**; the BAV199 never conduct.
  - **Decision:** keep the BAT54S pair in the MP1 v2 clamp. Without it, specify the Infineon BAV199 (1.5 us max), or bench-measure trr per lot.
- **HV parts (`rf2/rf2_hvparts.py`, study `hvparts`, 8 checks).**
  - **Clamp diode:** Nexperia US3M is adopted as a second source (full data sheet; 1000 V, 2.17x over the clamp; Cd about 7 pF above 400 V; 23.5 mA average, 0.06 W, TJ about 78 C). The 650 V PNU650200 / 300 pass rule 6 at 1.41x but are oversized D2PAKs: not adopted.
  - **TX switch:** ARF461A/B and ARF1510 are about 2 ohm, about 48-55 W conduction in boost against 6.1 W for the C3M0280090J, and the peak is over their ID rating. They are enhancement mode, so they cannot be the limiter. The ARF1510 is a BeO package: not adopted.
  - **Rd:** no Vishay TR or Ohmite Power-Mox combination gives 408 ohm at >= 4.24 W within the TXF fin; Rd stays OPEN. The TR fits as high-value HV dividers and bleeders (the cascode gate divider, the 460 V bleeder).
  - **Heat sink:** the Ohmite D Series TO-263 is adopted in rf2_continuous (7 C/W READ): **TJ 89 -> 101 C** at 6.08 W, under the 125 C derated limit. Aluminium at the neck is a fixed target: OPEN (echo budget).
- **Ferrous channel (`rf2_fluxgate.py`).** The DRV425 replaces the 10 pT/rtHz assumption (CORRECTIONS).
  - Ranges at 1e-4 / 1e-5 mismatch: 3 g lump 45 / 55 mm; nail along 175 / 200 mm, across 40 / 45 mm; 100 g lump 175 / 200 mm.
  - Its +-2 mT range covers the 1.22 / 1.93 mT TX pulse at the head sensor (boost margin under 5 %).
- **Power path candidates:**
  - **BQ76952** for the 7S pack: monitor, protector, coulomb counter, up to 9 thermistors.
  - **LTC4365** at the handle input: reverse and over-voltage protection, OV about 30.5 V; the 34 V operating limit leaves 4.6 V over a full 29.4 V pack.
  - **TMP117** for the thermal-limit sensors and the display drift sensor: +-0.1 C, 4 per bus, ALERT.
  - **UCC28780** (preferred over the UCC28782) for a regenerative clamp in the pod: 460 V DC up the shaft at about 23 mA. It needs a transformer (ferrite, so not in the head), and its loop regulates an output while a clamp must hold its input: OPEN design study.
- **UI candidates:**
  - **C&K KSC2 TE** (IP67, 10 M cycles, 6.2 x 6.3 mm) for the trigger, the power button (with a light-pipe ring) and profile keys.
  - **C&K ITS** (illuminated) only behind a sealed boot: no sealing rating found; 70 C operating limit.
  - **TPD4E1B06** for connector ESD (0.7 pF, 0.5 nA; not an MP1 rail clamp: it breaks down at 7-9.5 V).
  - **Murata piezos** (PKM22EPPH4001-B0 22 mm, PKLCS1212E4001-R1 12 mm) fit the pocket and are magnet-free, but:
    - both are **to be discontinued** (last order 3/31/2027);
    - both are resonant at 4 kHz; the 200-1400 Hz depth-pitch tones and the 1.8 kHz ping are 15-20 dB down (READ).
    - OPEN: retune the audio coding to 2-8 kHz, or choose a wider-band magnet-free transducer.
- Duplicate uploads not re-filed: Diodes US3M rev 5-2 (adds RthJT 26 C/W); MG 832TC Ver. 4.3.

## 35. Audio route, system architecture and placement, handle pod v2 (2026-10-30; owner: fewest parts, least modification, clean mapped layout; MODELED)
- **Audio (`rf2/rf2_audio.py`, step `audio`, 9 checks): magnet-free piezo, tones moved into its band.**
  - Part and drive: Murata PKLCS1212E4001-R1, SMD on the pod board, driven in bridge from +5 V by 2 x SN74AHCT1G125 (already in the BOM), with 680 ohm per leg.
  - Band and level: tones at 3.0-7.6 kHz, equalised by PWM duty to within 0.5 dB. Floor 78.7 dB at 10 cm (about 63 dB at the ear); 75.7 dB if the unlisted capacitance is 30 nF. Drive 11 mW.
  - Tones: ferrous 3.0-3.2 kHz (25 Hz gate), foil 3.5 kHz (soft), non-ferrous 3.8-7.6 kHz with tau, sonar ping 7.5 kHz.
  - Profiles: Class tones / Depth pitch / Quiet / **Field** (all tones on the 3.3-4.3 kHz resonance, full level). Stereo is dropped: one transducer.
  - Why this beats a class-D amplifier and speaker (ARX AU1):
    - 3 parts plus the transducer, against about 10;
    - no speaker cone in the sealed pod;
    - no audio-frequency magnetic dipole 0.29 m from REF3: 6 pT for the piezo loop against about 5 nT for a speaker coil.
  - rf2_ui.tone_for now delegates to rf2_audio (one tone source).
  - Successor note: the part is to be discontinued; a successor needs only a new response table.
- **System architecture (`rf2/rf2_system.py`, step `system`, 17 checks; map `rf2/results/rf2_system_map.png`): four sealed modules on one shaft bundle.**
  - **HEAD:** sensing and display (unchanged).
  - **TXD:** transmit driver.
  - **POD:** the hand.
  - **PACK:** all power. 7S2P Molicel P30B, 136 Wh usable, 7.8 h scan / 4.8 h continuous boost, under the forearm as the counterweight.
  - **TX driver placement by echo search.** At the baseline "neck at the shaft base" (s 90 mm), the heat sink plus nine aluminium bulk cans echo at about 4900x the gate noise, and a 5 K drift moves that by 97x the noise.
    - Drift falls to 8.0 / 1.5 / 0.36 / **0.098** / 0.03x the noise at s 150 / 200 / 250 / **300** / 350 mm.
    - TXD placed at s 255-345 mm, below the tube.
    - The TX pair grows to 0.3 m: about 15 pF, first gate +0.16 us (first-order, 50 pF/m ASSUMED). Re-run rf2_timing with it.
  - **Removed parts:**
    - PM2 soft latch (Si4401FDY, BZT52C15) and LTC4365: the BQ76952 DSG switch is the main switch, the power button wakes it on TS2 (datasheet: falling edge, 0.7-1.1 V), the pod MCU turns it off over I2C, and the MT60 charge port is keyed;
    - AU1 amplifier and speaker;
    - UCC28780: the regenerative clamp return is a hysteretic buck in the PACK, built from parts already in the BOM (C3M0280090J, UCC5350, US3M).
  - **Continuous-boost heat:**
    - TXD: 6.3 W (switch TJ 101 C on the Ohmite heat sink);
    - PACK: about 1.4 W (buck at 90 % ASSUMED);
    - 460 V DC runs up the shaft in one FEP twisted pair at about 23 mA.
  - **TXD temperature:** a TMP117 in therm mode loads its limits from EEPROM and pulls TXSTAT; there is no bus to the TXD.
  - **Harness, four segments:** gland-TXD 0.30 m; TXD-REF3 0.255 m; REF3-pod 0.25 m; pod-pack 0.20 m.
    - Tube fill 3-8 % of a 22 mm bore.
    - VIN drop 0.053 V in boost.
    - Every HV conductor insulated >= 630 V (rule 6).
    - Ampacities hold.
  - **Rails and buses:**
    - +5V_AUX load 0.16 A of 2 A;
    - every VBAT part rated for 21.0-29.4 V;
    - logic levels compatible;
    - I2C addresses verified from the data sheets: LSM6DSO 0x6A, MMC5983MA 0x30, TMP117 0x48 / 0x49, BQ76952 0x08 (7-bit).
  - **Link:** RS-485 class pair from CB1D to the pod. The head time-stamps LED frames and audio events, and both play them 20 ms later, which keeps the display-v3 coupling across the link (part to choose).
- **Handle pod v2 (`head/rf2_pod.py`, 12 checks; `head/out/pod/rf2_pod_layout.png`).** The tube runs through the pod, so v1 was wrong (CORRECTIONS). v2 places HB2 in the 10 mm annulus:
  - **HB2-T (x 6-92):**
    - 2 selector switches;
    - piezo with 5 sound holes;
    - RP2354A;
    - TLV755P;
    - 4 x AHCT;
    - power switch, 0.4 mm under the cap;
    - 3 x SK9822 under the light pipe;
    - screen FPC connector.
  - **HB2-B (x 100-165):** trigger switch, RS-485, TPD4E1B06 and J1, 18 mm from the tube's grommeted exit.
  - **Side flex arm:** x 90-102, r 16.9, >= 1 mm of wall to every void.
  - **Selector:** two cam lobes at +-46.7 deg press vertical plungers at +-16.7 deg, one per side detent; both are free at the centre with >= 30 deg margin. No magnet.
  - **Screen pocket:** floor raised to 14.0 mm, leaving 1.2 mm of wall over the bore; tray 26 mm wide; the FPC runs in the 0.5 mm under the tray to a front-wall slot.
  - **Checks:** they fail on v1's geometry (tested by putting v1's trigger slot and screen floor back in).
- **OPEN:**
  - rf2_timing with the TX pair capacitance;
  - the regenerative buck design (SPICE);
  - the RS-485 part;
  - the screen datasheet;
  - the KSC2 TE travel against the plunger and cap stack;
  - a pack housing model;
  - the 3-D shaft and armrest.

## 36. Upper assembly v1, REF3 sleeve, faster geometry pipeline, system topography (2026-10-30; owner requests; MODELED)
- **Upper assembly (`rf2/rf2_upper.py`, step `upper`; `rf2/upper_out/`: STL per part, STEP assembly, `rf2_upper_views.png`).** It replaces the cylindrical pod (head/rf2_pod.py is retired).
  - **Parts:**
    - head exterior: wear skid and yoke ears;
    - yoke with friction pivot (r 85 at the heel);
    - L1 tube with the TXD housing beside it (s 330-420);
    - L2 tube with the REF3 sleeve (s 470-820) and a 0-250 mm telescope with cam lock;
    - upper unit: grip head with thumb button and light ring, flip-up screen (opens 60 deg, 2.7 deg off the eye line), mode dial and pilot trigger with guard;
    - pistol grip with 3 finger wedges, pinky shelf and 18 deg rake;
    - spine (PWR board);
    - cuff and stem;
    - battery bay and quick-swap cartridge (7S2P, slides out rearward with no contact).
  - **Electronics placed and contained:** HB2 parts in the grip head, PWR parts in the spine, TXD parts, cells and BQ board in the cartridge, REF3 windings in the sleeve.
  - **Checks pass:** containment, grip (118 mm, 24-25 mm finger pitch, 135 mm circumference), trigger reach 70 mm, thumb 54 mm, screen view, cuff height 0.78-1.20 m over tilt and telescope, telescope overlap, battery slide, deployed clearance, battery counterweight.
  - **Mass and torque:** 2.46 kg in total; wrist torque 6.5 N m (7.6 without the battery behind the hand).
- **Owner review of v1 (OPEN, next):**
  - no shaft folding: telescope instead;
  - the cuff does not work: the forearm cannot sit in it and reach the grip, so it needs a straight forearm axis;
  - the cuff may fold;
  - model the flex / rigid-flex runs in shaft channels.
  - The fold search is kept only as a retired record (best package 449 x 239 x 233 mm against the 520 x 320 x 210 target).
- **REF3 sleeve (owner: the 112 mm box goes).** `head/rf2_ref3.py` now also sizes a sleeve on the tube: X / Y saddle-coil pairs (nested turns, 120 deg saddles) plus a Z solenoid under a 1 mm cover.
  - Chosen: 350 mm long, OD 33.8 mm, 0.2 mm wire (X / Y, gain 3) and 0.15 mm (Z, gain 4).
  - Cost: depth penalty -2.33 % worst axis (the box was -1.39 %), with 332 g copper.
  - Lighter alternative: 31 mm OD, 211 g, -3.25 %.
  - The head base was rejected for REF3: it would see the targets, and the canceller would subtract them.
  - OPEN: re-run rf2_emi with the sleeve's e_ref (2.6-3.4 nV/rtHz).
- **Echo model correction (CORRECTIONS).** `rf2_system` used only Bz.
  - Now: blocks (the heat sink) at worst-case |B|, closed cans (bulk capacitors, cells) linked by the field along their axis, laid laterally where mirror symmetry keeps it small.
  - TXD moved to s 330-420: 5 K drift 0.20 x the gate noise; the TX pair 0.33 m adds +0.17 us (first-order).
- **Geometry pipeline (owner: no long blind runs).** The upper build went from more than 10 minutes, unfinished, to 53 s cold and 18 s with a cache hit:
  - groups are tessellated once into voxel-deduplicated surface samples (2 mm);
  - candidate transforms are numpy;
  - clearance is a KD-tree query after a bounding-box prune;
  - hinge offsets come by bisection;
  - exact OCC distances run only on the winner;
  - per-phase timings print live and are saved;
  - the search is memoised in state/simcache (`geom.upper.fold`).
  - Two silent faults were found on the way and fixed:
    - a mirrored placement frame turned solids inside out (negative volume, zero distances);
    - an edge-subdividing sampler made millions of points.
- **System topography (`rf2/rf2_topography.py`, step `topography` -> `docs/SYSTEM_TOPOGRAPHY.md`).** Generated station by station from the handle tip to the head edge: maturity (CHECKED / MODELED / CONCEPT / OPEN), the runner steps and their last results, numbers read from outputs, and open items.
