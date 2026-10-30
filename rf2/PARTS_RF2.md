# RF2 parts selection (2026-10-29)

Owner rule for RF2: no part is kept because the first design used it. Each new function is chosen against stated criteria. A number counts only when it comes from the manufacturer datasheet (repo rule 7). Anything else is marked **UNVERIFIED** and is not used to sign anything off.

Verification status (2026-10-30 update: TI PDFs download normally, and LMH6629, OPA1612, TPS7A94 and TPS7A20 are now verified; ADI, Microchip and Infineon still refuse plain fetches):
- Analog Devices: answered HTTP 503 to automated fetches.
- Microchip: answered 403.
- Retrying with a disguised browser user agent was refused, as it should be.

The candidates below therefore carry distributor or search figures until the PDFs are supplied or the sites answer.

## MP1 mono preamp: input protection (largest performance lever)
**Criteria:**
- withstand the 460 V flyback with margin (>= 630 V class, rule 6);
- keep the resistance in the signal path small, since its thermal noise adds directly to the 1.7 nV/rtHz receive budget;
- limit the clamp current to within the clamp diodes' repetitive rating;
- fast recovery.

| Topology | Series R at rest | Noise (4kTR) | Energy into the protection per pulse | Recovery to 1 mV | Source |
|---|---|---|---|---|---|
| v1: 3 x 470 ohm CRCW2512 per leg (built in MP1 v1) | 1410 ohm | 4.83 nV/rtHz | 786 uJ | 12.9 us | out/rf2_mp1_spice.json |
| **v2: depletion-mode HV MOSFET current limiter + 22 ohm** | **64 ohm** | **1.03 nV/rtHz** | **79 uJ** | 12.9 us | out/rf2_mp1_spice.json |

Both simulations use generic ngspice models (level-1 NMOS, VTO -2.5 V, about 42 ohm). The v2 peak clamp current of 284 mA is above the about 30 mA that the generic model's saturation current implies; that needs the real part's SPICE model.

Reading: v2 removes almost all of the protection noise. With an op-amp of about 1 nV/rtHz the front end would sit near 1.4 nV/rtHz instead of about 5. By the repo's depth scaling (SNR^(1/5.1)), that is about +28 % mono depth over v1. **This is the recommended MP1 v2 topology,** pending the part verification below.

| Candidate | Role | Figures (status) | Source |
|---|---|---|---|
| Microchip DN2470 (N-channel depletion-mode vertical DMOS) | current limiter | 700 V, 42 ohm, VGS(off) about -1.5 to -3.5 V; continuous drain current listed as 170 mA (DigiKey, TO-252) **and** 500 mA (another distributor): **UNVERIFIED, conflicting** | [radiolocman listing](https://radiolocman.com/datasheet/data.html?di=428461), [RS](https://uk.rs-online.com/web/p/mosfets/0598941?gb=s), [DigiKey](https://punchouttest.digikey.at/en/products/detail/microchip-technology/DN2470K4-G/4902747) |

## MP1 amplifier
**Criteria:**
- voltage noise <= about 1 nV/rtHz in the 10-100 kHz gate band;
- runs from a single 5 V supply with VBIAS at 2.5 V;
- bandwidth for a gain of about 10 with fast recovery;
- dual.

| Candidate | Figures | Status |
|---|---|---|
| ADI ADA4896-2 | 1 nV/rtHz wideband (2.4 nV/rtHz at 10 Hz), 3-10 V supply, rail-to-rail output, 230 MHz (G = +1), 3 mA per amplifier, MSOP-8 / LFCSP-8 | **UNVERIFIED** (ADI product page and mirrors; [ADI](https://www.analog.com/en/products/ada4896-2.html)) |
| ADI / LTC LT6201 (dual LT6200) | 0.95 nV/rtHz at 100 kHz, rail-to-rail in and out, 2.5-12.6 V (DD package 7 V), 165 MHz | **UNVERIFIED** (third-party copies of the datasheet; [radiolocman](https://www.radiolocman.com/datasheet/data.html?di=525275)) |
| **TI LMH6629** (single) | 0.69 nV/rtHz, 2.6 pA/rtHz; 2.7-5.5 V, specified at 5 V single supply; CMVR -0.30 to 3.8 V; min stable gain 10 (SOT-23-5); 15.5 mA; abs max input current +-10 mA, input -0.5 V to VS | **VERIFIED** (TI SNOSB18I, DATASHEET_LOG RF2-DS-MP1V2). **Chosen for MP1 v2**, with a series resistor between the clamp node and its input (sized against the +-10 mA / -0.5 V limits; adds noise; next step). |
| TI OPA1612 (dual) | 1.1 nV/rtHz at 1 kHz; on 5 V input range 2.0-3.0 V | **VERIFIED** (TI SBOS450C). No gain over OPA2211; not adopted. |
| TI OPA2211 (first-design part) | 1.1 nV/rtHz at 1 kHz; input range on 5 V single supply 2.0-3.6 V (works at VBIAS 2.5 V) | **VERIFIED** (TI SBOS377L, DATASHEET_LOG). It is kept only as the verified fallback, not on habit. |

## Clamp diodes (MP1, receive inputs)
**Criteria:** lowest leakage and capacitance at the preamp input; repetitive current of at least 0.33 A (v1) or 0.3 A (v2 peak, to be confirmed).

The choice is **Nexperia BAV199** (VERIFIED, DATASHEET_LOG U-DS-BAV199): 5 nA maximum leakage, 2 pF, IFRM 500 mA. It is kept on merit, as the lowest-leakage verified option, until a better verified part appears.

## LED display (LR1, flex; 522 LEDs since 2026-10-30)
**Criteria:**
- 2 x 2 mm or smaller;
- a clocked interface, so the firmware can hold the LEDs dark through every receive window without timing-critical one-wire frames;
- 5 V;
- low profile under the lid.

| Candidate | Status |
|---|---|
| OPSCO SK9822-EC20 | **VERIFIED** (datasheet on disk): 2.0 x 2.0 x 0.65 mm, clocked SDI / CKI, 15 MHz, 5 V. Chosen on merit: the only verified clocked 2020 part. |
| HD107S-2020, APA102-2020 | **UNVERIFIED** (no manufacturer PDF read). Candidates if verified; HD107S is advertised with a higher PWM frequency. |

## Analog supply for MP1 and the AB1 sections (new function in RF2)
**Criterion:** an ultra-low-noise LDO from the 5 V buck, so that buck ripple and LDO noise stay below the 1 nV/rtHz front end.

- **TI TPS7A94: chosen** for the MP1 / AB1 analog rail. VERIFIED (SBVS336C): 0.46 uVrms over 10 Hz-100 kHz; PSRR 110 / 95 / 78 dB at 1 / 10 / 100 kHz; VIN 1.7-5.7 V; WSON-10 3 x 3 mm.
- TI TPS7A20: VERIFIED (SBVS338H), 7 uVrms; logic or LED rail only.
- ADI LT3045: **UNVERIFIED** (analog.com refused the fetch).

## What is needed to close this
Supply (or let me fetch once the sites answer) these manufacturer PDFs:
- Microchip DN2470 (and its SPICE model);
- ADI ADA4896-2 (only if it should be compared with the verified LMH6629);
- ADI LT6200 / LT6201 (same);
- HD107S;
- ADI LT3045 (optional; TPS7A94 is verified);
- or a depletion-mode HV MOSFET from a vendor that serves PDFs (for example IXYS / Littelfuse IXTP08N100D2), in place of DN2470.

Each will get a DATASHEET_LOG entry with the exact values, and MP1 v2 will then be drawn, routed and checked like v1.

## Display power (new function, 2026-10-30)
- **TI LMR36520** (own +5V_LED buck, 4.2-65 V in, 70 V transient, 2 A): **VERIFIED**, DATASHEET_LOG RF2-DS-DISPLAY. Chosen over a second LMR36015 (1.5 A), which would leave only 9 % margin at the 1.372 A display load.
- **TI TPS22918** load switch (1-5.5 V, 2 A, 52 mohm): **VERIFIED**. It powers the display down while silent; the 522 x 1 mA static current would otherwise flow all the time.

## MP1 v2 decision (2026-10-30, owner-supplied datasheets; rf2_mp1_spice.py "v2_real_fets")
- **Current limiter: Littelfuse IXTY08N100D2** (VERIFIED, DATASHEET_LOG RF2-DS-HVFET). Gate tied to the far end of 22 ohm (self-biased), as modeled. After the turn-off edge it holds the clamp current at 101 mA.
- **Turn-off edge:** the FET's own capacitance carries C dV/dt into the clamps for about 20 ns at the modeled 16 V/ns edge: 0.41-0.45 A for IXTY08N100D2, 0.86-1.09 A for DN2470.
  - This is an upper bound, because the model releases the coil current instantly into 500 pF.
  - The real edge is set by the switch and the damping network; the bench must measure it.
- **Series resistor Rin2 between the clamp node and the LMH6629 input: 100 ohm.**
  - Why: the clamp node reaches 6.55 V during the edge, and the LMH6629 limit is +-10 mA (input -0.5 V to VS).
  - Front-end series resistance 143 ohm = 1.54 nV/rtHz thermal; with the LMH6629 (0.69 nV/rtHz, 2.6 pA/rtHz) about 1.7 nV/rtHz total, against about 5.0 for v1.
  - Recovery 14.7 us, inside the 16.3 us first gate (v1: 12.9 us).
  - A low-capacitance Schottky clamp at the op-amp input would allow Rin2 of about 47 ohm (about 1.45 nV/rtHz total). That part is UNVERIFIED: a datasheet is needed first.
- **Modeled mono depth gain over v1:** (5.0 / 1.7)^(1/5.1) = about +23 % (RF2 depth scaling SNR^(1/5.1); generic op-amp and diode models; MODELED).
