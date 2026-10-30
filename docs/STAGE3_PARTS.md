# AXE2 option B, stage 3: parts, sensors and materials (2026-10-30)

Everything is **MODELED / tool-checked** unless it cites a datasheet in `data/datasheets/` (logged in `docs/DATASHEET_LOG_ARX.md`).
- **READ:** a value read from a datasheet curve.
- **UNVERIFIED:** no datasheet on disk yet.

## 1. What stage 3 changed

| Finding | Before | Now | Source |
|---|---|---|---|
| Display LEDs are foil on a PCB, not a copper lead frame | 5500 x noise, 120 x / K (assumed 2 x 2 x 0.2 mm copper) | 5e-6 x noise, no drift | OPSCO Rev A0 "PCB holder package"; rf2_zones; CORRECTIONS |
| TX switch Coss in the decay tail | 500 pF node assumed | IPB65R095C7 about 400 pF at 26 V (READ) -> 582 pF node, gate 17.1 us | rf2_switch.py |
| SiC switch C3M0280090J (900 V) | - | about 110 pF at 25 V (READ) -> 292 pF node, gate 14.0 us | rf2_switch.py |

Depth per switch (0.1 / 1 / 20 g):
- IPB65R095C7: 179 / 339 / 520 mm.
- C3M0280090J: 195 / 343 / 522.
- C3M0280090J + syntactic potting: 197 / 344 / 522.
- Bound for a 60 pF switch (UNVERIFIED): 203 / 346 / 523.
- **The 0.1 g gain is +9 % (small, fast gold; also a cleaner early decay for the signature).**

## 2. Recommended parts per subsystem

| Subsystem | Today | Recommended | Why | Status |
|---|---|---|---|---|
| TX switch | Infineon IPB65R095C7 (650 V CoolMOS) | **Wolfspeed C3M0280090J** (900 V SiC, D2PAK-7) | Coss in the tail 400 -> 110 pF; 900 V against the 460 V flyback (1.96x, rule 6). Needs a +15 / -4 V gate drive (the TC4420 is single-supply: a bipolar driver is a stage-5 item). | verified datasheet; driver open |
| HV limiter (MP1 v2) | IXTY08N100D2 (TO-252, tab) | keep | On a radial fin the tab lies in the field-free plane (rf2_layout): the 2710 x echo of a flat mount goes away. | verified |
| Input clamp | BAV199 (2 pF, 5 nA) | keep; candidate Infineon BAT15-03W (Schottky, 0.28 pF typ / 0.35 max, SOD-323) | lower C on the input node | BAT15 datasheet to fetch (leakage) |
| Mono preamp | LMH6629 (0.69 nV/rtHz) | keep; two in parallel for 0.9 nV system noise (rf2_depth_levers: +12 % depth) | best voltage noise at a 22-100 ohm source | verified |
| Receiver digitiser | analog gates / integrators (AB1) | **AD7389-4**: 4 x 16 bit simultaneous, 2 MSPS, aperture jitter 20 ps | full decay curve of mono, QA, QB and REF3 every 0.5 us; gates, matched filters and decay fitting in firmware (signature clarity); one chip, simultaneous, so REF3 cancels interference sample by sample | verified (owner upload) |
| Alternative digitiser | - | AD4134 (24 bit, 1.5 MSPS, alias-free) | more resolution, but its filters smear a decay in time | verified; not chosen |
| IMU | (ARX CB1D: gyro) | **Bosch BMI270** (6-axis, LGA 2.5 x 3 x 0.83 mm, gyro < 7 mdps/rtHz, ODR to 6.4 kHz, aux I2C for a magnetometer, HW sync < 1 us) | section 3 | verified |
| Magnetometer (new) | - | MEMSIC MMC5983MA (+-8 G, 0.4 mG rms, SET / RESET) or ST LIS2MDL (+-50 G) | section 4 | datasheets to fetch |
| Temperature | - | 2 x digital sensors (coil channel, MP1 fin) | coil R and L tempco -> damping and offset model | to choose |
| Capacitors | - | MLCC only (C0G / NP0 in signal paths) | no metal cans (rf2_zones) | rule |

## 3. The gyro / IMU (BMI270): what it adds

1. **Sweep speed and phase.**
   - PI target responses are filtered in time across the sweep.
   - Knowing the speed (gyro yaw rate x shaft length) lets the firmware set the ground-tracking and target filters to the actual speed: a slow sweep is not a weak target.
2. **Position along the sweep.**
   - Integrated yaw plus the accelerometer give where the head is on its arc at each pulse.
   - Combined with the quadrupole bearing, every target response gets a position on a 2-D map under the head: the 522-LED display paints the target where it is.
3. **Tilt.**
   - Head pitch and roll change the ground coupling and the quadrupole ground null.
   - The tilt angle feeds the ground model, which removes a known ground-falsing source.
4. **Knocks.**
   - The accelerometer flags shocks (hitting a rock or root).
   - Pulses inside a shock window are blanked: mechanical flexing changes the coil coupling and looks like a target.
5. **Still in the air.** "No motion" plus a quiet receiver triggers automatic re-zeroing of the fixed head offset (drift).
6. **Placement.**
   - On a digital fin (field-free orientation); its 2.5 x 3 mm package carries foil-level copper only.
   - It is read outside the receive window (its 2 KB FIFO buffers the samples).

## 4. A second, passive detection channel: magnetometer (new)

- **Idea.** Iron distorts the Earth's static field; gold does not. A 3-axis magnetometer read between pulses gives an independent ferrous flag that the eddy-current channel cannot fake. This helps trash rejection (nails, wire) without ground balance.
- **Size of the signal (MODELED, order of magnitude).**
  - A 3 g steel nail is about a sphere of 0.38 cm3 with an apparent susceptibility near 3 (shape-limited).
  - In 50 uT it carries m = 3 V B / mu0, about 4.6e-5 A m2.
  - Its field is about 0.9 mG at 100 mm and 0.11 mG at 200 mm. Against the MMC5983MA's 0.4 mG rms (vendor, UNVERIFIED): useful to about 100-150 mm, more for long iron lying along the field.
- **The catch.** Swinging the head rotates the sensor in the 500 mG Earth field: the orientation from the BMI270 (its aux I2C hub is made for this) must be removed at better than 0.1 % to see a 0.5 mG nail.
- **The TX pulse.** 1.2 mT = 12 G at the centre, above the MMC5983MA's +-8 G range. Its SET / RESET pulse restores the sensor after each TX pulse, and readings are taken in the quiet window. The LIS2MDL's +-50 G range tolerates the pulse but is noisier.
- **Status:** worth a bench test; datasheets to fetch.

## 5. Materials that are not 'metal detector' materials but help

| Material | Where | What it does | Status |
|---|---|---|---|
| Parylene C (vapour-deposited, about 25 um) | every analog and HV fin, before potting | the 'spray on every chip' that is worth having: no field effect (no metal, eps about 3), but it stops moisture and ionic leakage drift on the high-impedance inputs and protects the HV fins | datasheet to fetch |
| Syntactic foam (resin + 3M iM30K glass bubbles) | coil channel | lowest permittivity around the winding: smaller winding C, earlier gate | eps UNVERIFIED |
| PTFE / FEP-insulated litz | the coil | eps 2.1 between turns instead of about 3.5 for polyurethane enamel: smaller winding C | supplier datasheet to fetch |
| Glass-fibre-filled resin for the combs and channel | coil support | low thermal expansion: the coil does not creep with temperature (drift of L and of the null) | material sheet to fetch |
| MG 841AR nickel coat | shell inner face | electrostatic screen, tau 1 ns (no echo) | verified |
| UHMW-PE skid plate | underside | wear and low friction, non-metallic | - |

## 6. Datasheets to get (I could not download them, or they are not searched yet)
1. Infineon BAT15-03W (leakage vs voltage and temperature).
2. MEMSIC MMC5983MA and ST LIS2MDL (range, noise, SET / RESET, field tolerance).
3. A bipolar gate driver for the SiC switch (+15 / -4 V): e.g. TI UCC5350 / UCC27531 class.
4. Parylene C (SCS or Kisco technical sheet: eps, dielectric strength, moisture transmission).
5. PTFE / FEP litz (e.g. New England Wire Technologies, Rubadue): insulation eps, strand count.
6. Syntactic-foam resin and the iM30K permittivity (3M application data).
7. A GaN or other < 60 pF-at-26 V switch rated >= 630 V, if the SiC result is to be beaten (the GaN Systems download failed).
