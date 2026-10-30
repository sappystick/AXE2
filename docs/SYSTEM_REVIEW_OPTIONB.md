# AXE2 option B: system review through every lens (2026-10-30)

Everything here is **MODELED / tool-checked**. Sources are in rf2/HANDOFF_RF2.md sections 17-25. Status words:
- **done:** modeled and checked in `run.py`.
- **open:** a stage 3-5 task.
- **bench:** needs a measurement.

The lenses applied to every subsystem:
1. **Field / echo:** what the transmit pulse does to it, and what it sends back into the receiver.
2. **Noise:** its contribution to the receive noise.
3. **Drift:** temperature and mechanical stability of any fixed signal.
4. **Power / EMI out:** what it emits during the receive window.
5. **Mechanics / potting / thermal.**
6. **Make / test.**

## Transmit coil (5 x 6 rim mono, 26 turns, 323 uH, 8.17 A, 10.8 mJ)

| Lens | Finding | Status |
|---|---|---|
| Field / echo | The coil shape is at the physical optimum for the footprint: taper, Rodin, waves, ferrite, magnets and Halbach all model equal or worse (sections 19-23). | done |
| Noise | Litz copper (6 g/m) thermal noise is inside the 1.7 nV front-end budget. | done |
| Drift | Combs and syntactic foam fix the turns. A 0.1 mm turn movement changes L and the null: bench creep test. | bench |
| Winding | Owner's column-by-column, down-and-up order: 166 V max between neighbours, against 202 V for a layered winding. | done |
| Potting | Syntactic foam (eps about 1.8, UNVERIFIED): gate 15.96 us, against 16.93 us for 832TC epoxy. | done; eps open |
| Make | Printed combs, 1.3 mm slots, 0.3 mm teeth (resin print). | open: print test |

## Transmit driver, clamp and damping (neck / shaft side)

| Lens | Finding | Status |
|---|---|---|
| Timing | The first gate is set mostly by the 368 pF outside the winding (switch Coss, leads, damping). Cutting it to 100-150 pF gives a 12.9-13.6 us gate and 0.1 g 196-199 mm. | open: stage 3 switch search |
| Field / echo | The coil leads are run through the heel slot to TXJ. | done |
| Make | TXJ moved to (-94.5, 0) in variant B. | open: netlist variant, stage 4 |

## Mono receive (MP1 v2)

| Lens | Finding | Status |
|---|---|---|
| Noise | v2: 1.7 nV/rtHz, +23 % depth over v1 (decided). Two LMH6629 per input: 0.9 nV, +12 %. Schottky clamp with Rin2 47 ohm: 1.2 nV. | open: stage 3 / 5 |
| Field / echo | The IXTY08N100D2 TO-252 tab: 2710 x noise, tau 19.8 us. Stand it edge-on or find a tab-less 1 kV depletion FET. | open: stage 3 |
| Field | MP1 zone 2.1-2.9 mT, 0.036-0.051 V per cm2 of loop. A 1.2 uA step in a 1 cm2 loop equals the gate noise. | done (rules) |
| Recovery | 14.7 us, inside the 16.3 us gate; checked by `mp1-spice`. | done |

## Quadrupole receive (QA / QB, rigid SB1R)

| Lens | Finding | Status |
|---|---|---|
| Noise | 10.4 ohm at 35 um. 70 um: +0.24 %; flex 18 um: -0.43 %. Keep rigid 35 um. | done |
| Field | Ground-cancelling by symmetry; it gives the bearing, not the depth. | done |
| Drift | Board tilt against the null (study 3). | open |

## Shielding

| Lens | Finding | Status |
|---|---|---|
| Electrostatic | SH1 split rings (bottom) plus an 841AR nickel coat on the shell wall (tau 1 ns: no echo) give a slit Faraday screen around the coil against ground / hand capacitance. | done (geometry); bench: capacitive ground test |
| Magnetic | No practical magnetic shield inside the coil. Ferrite costs depth (sections 22-23); conductive cans and mu-metal are targets. | done |
| Rule 5 | One closed SH1 ring = 2.2e7 x noise. Every ring and coat keeps its slit. | done: stage 4 makes it a board check |

## Analog boards (AB1A / AB1B)

| Lens | Finding | Status |
|---|---|---|
| Field / echo | 2.3-6.7 mT. A solid plane is 1.5e5 x noise and a closed hatch border 590 x; hatched with slit borders, about 0. | done (rule); stage 4 check |
| Coupling | A 0.52 uA step in a 1 cm2 loop at the edge nearest the coil equals the gate noise. Loops < 0.1 cm2, differential, quiet during the receive window. | open: AB1 rework, Phase C |
| Parts | No aluminium electrolytics (7.5e4 x noise, 217 / K drift). | done (rule); stage 4 BOM check |
| Bucking loop | Moves the field from the board centre to its edge. Not adopted. | done |

## Controller (CB1D, RP2354A) and power (LMR36520 + TPS22918 LED rail)

| Lens | Finding | Status |
|---|---|---|
| Field | 1.2-1.35 mT. Buck inductors far below saturation. | done |
| EMI out | 2.6-2.8 uA per cm2 loop equals the gate noise. Buck converters and clocks are quiet or synchronised outside the receive window (spread-spectrum off, switching phase-locked to the pulse). | open: Phase C |
| Echo | Plane rules as for AB1. | stage 4 |

## Display (LR1, 522 SK9822-EC20)

| Lens | Finding | Status |
|---|---|---|
| Echo | Lead frames 5500 x noise with 120 x / K drift (2 x 2 x 0.2 mm ASSUMED). Outer rings dominate: r 104 is 39 %. | open: real lead frame (stage 3); temperature sensor + offset model (stage 5) |
| EMI out | LEDs dark and clock stopped in the receive window (timing check 877.5 us < 1162.2 us). | done |
| Mechanics | Hinge bend ratio 10:1 at 0.4 mm (26.7:1 as 0.15 mm PURE.flex). | done |

## Housing, potting, thermal

| Lens | Finding | Status |
|---|---|---|
| Geometry | Variant B 15.65 mm, all checks pass, 693 g. | done |
| Potting | Coil channel: syntactic (low eps). HV: 832TC (48 kV per 3.2 mm). Analog: silicone gel (no stress on parts). Digital: syntactic silicone. | done (spec); the eps / DF of gel and syntactic are open (stage 3) |
| Thermal | Potting turns the head into one thermal mass: fixed-metal drift (display, tabs) follows its temperature. A temperature sensor near the display and one near MP1. | open: stage 5 |
| Mechanics | 15.65 mm shell over a D233 span: stiffness of the lid and skid. | open: FEM / print test |

## Ground and processing

| Lens | Finding | Status |
|---|---|---|
| Ground | Multi-period ground balance plus the quadrupole null (modeled earlier). Real soil decides the field depth. | bench |
| DSP | Matched gates (golden ratio), 100-400 pulse averaging (400: +13 % depth). | done (model); firmware Phase C |

## Stage 3 shopping list (parts search)
1. Tab-less 1 kV depletion FET, or an edge-on mount for the IXTY08N100D2.
2. Low-capacitance Schottky input clamp.
3. A dual-amplifier option for 0.9 nV.
4. A low-Coss transmit switch and low-capacitance leads.
5. SK9822-EC20 mechanical drawing (lead frame).
6. Permittivity / DF of silicone gel and syntactic foam.
7. Flexible ferrite sheet (Wuerth WE-FSFS, TDK IFL) only if shielding the electronics from the coil is wanted later.
8. MLCC-only bulk capacitance for every rail.
