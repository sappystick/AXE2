# Evaluation of an owner-supplied component list (2026-10-30): applicable or not, and what each would add

No design change was made from this list (owner's instruction). MODELED numbers come from the repository's models. Vendor figures are cited from web results and are UNVERIFIED until the datasheet is on disk.

## Basis numbers (computed)
- **Coil-equivalent field noise** of the option-B rim coil (N A = 0.98 m2, 1.7 nV/rtHz front end): e_n / (2 pi f N A).
  - 150 Hz: 1836 fT/rtHz; 1 kHz: 275; 6 kHz: 46; 10 kHz: 28; 100 kHz: 2.8; 1 MHz: 0.28 fT/rtHz.
- **A 1 g gold sphere** decays with tau about 28 us: its signal sits near 5.7 kHz and above. A PI receiver needs microsecond time resolution.
- **TX node:** 460 V at turn-off against a 100 nV gate floor = 193 dB.
- **Quadrupole null leakage** (rf2_timing): null 3e-5 -> quad channel clean at 9.2 us; 1e-5 -> 8.7 us; 3e-6 -> 8.2 us. The mono channel is clean at 16.3 us either way.

## Verdicts

| Item | Verdict | Why |
|---|---|---|
| QuSpin zero-field OPM as the receiver | **not applicable** | Vendor: 7-15 fT/rtHz in 3-100 Hz, dynamic range +-5 nT, bandwidth about 150 Hz, latency about 5 ms. A PI decay is 5-50 kHz and microseconds long. The TX pulse (1.2 mT at the centre) is 2.4e5 x its range; even the Earth's field is 1e4 x. Our coil already reaches 46 fT/rtHz at 6 kHz and 2.8 fT/rtHz at 100 kHz, where the targets are. Heated vapour cell, laser, about 1 W per sensor. |
| Fluxgate as the PI receiver | not applicable | pT-class noise, kHz bandwidth: about 100x worse than the coil at PI frequencies. |
| **Fluxgate gradiometer as a passive ferrous channel** | **applicable, new** | It replaces the MEMS magnetometer idea of stage 3 with a far quieter sensor: iron distorts the Earth's field, gold does not. The practical limit is removing the head's rotation in the 50 uT field (a 3 g nail at 100 mm is about 90 nT, about 2e-6 of the Earth's field), so it must be a gradiometer (two matched sensors, head + shaft), read between pulses. Risk: the permalloy core near the coil is itself a small magnetic target and is driven by every TX pulse; bench test. |
| INA849 instrumentation amplifier | **applicable to QA / QB / REF3, not the mono** | TI lists 1 nV/rtHz (the list's '0.1 uV/rtHz' would be 100 nV, 145x worse: a unit slip). On the mono, the LMH6629 (0.69 nV/rtHz, verified) is quieter. A true differential input with high CMRR suits the floating differential quadrupole boards and REF3. Datasheet to fetch (bandwidth, overload recovery). |
| AD7768-4, 24 bit | not an improvement | 256 kSPS maximum (not several MSPS), sigma-delta filters with group delay: about 4 us per sample, and the filter smears a decay in time. Quantisation is not our limit: the preamp noise at the ADC is about 30x the ADC's own noise. The AD7389-4 (16 bit SAR, 2 MSPS, true instantaneous samples) stays the better fit (stage 3). |
| FPGA active TX bucking | **not applicable to the mono; a small part applies to QA / QB** | The mono transmits and receives on the same coil, and the receive window starts after the TX current has stopped: there is no simultaneous 'blast' to subtract. Cancelling the 460 V flyback to the 100 nV floor needs 193 dB; DACs reach about 120 dB, and ADC -> FPGA -> DAC latency is >= 1 us. The MP1 limiter already keeps the front end from blinding (recovery 14.7 us). A static analog null trim on QA / QB (a small scaled TX pick-up) would move their clean time from 9.2 to about 8.2 us: little gain, because the mono at 16.3 us is the limit. Section 25 also showed that a series bucking loop moves the field rather than removing it. |
| Differential reference sensor on the shaft | **already in the design** (REF3) | REF3 is a 3-axis reference coil 0.6 m up the shaft (rf2_emi, rf2_ref3), at PI bandwidth. An OPM could not follow PI frequencies. The geomagnetic field is static: a dB/dt coil sees it only through the sweep (about 1 Hz), far below the gates. New in stage 3: the AD7389-4 samples REF3 at the same instant as the receivers, so hum and sferics can be subtracted sample by sample. |
| FPGA digital lock-in, multi-frequency | **concept applies, in PI form; hardware not needed** | A lock-in follows a continuous-wave (VLF / multi-frequency) transmitter. Its PI counterparts are already planned: synchronous averaging over the pulse train, multi-period ground balance, and, with full-waveform capture, a decay-time-constant spectrum (multi-exponential fit). The receive-window data rate (about 0.6 M samples/s) fits the RP2354. A Zynq (watts) or Jetson / Hailo (2.5-60 W) would need cooling hardware inside a potted head (no metal heat sinks, rule 5) and drain the battery. If heavier compute is ever needed, it belongs in the handle or a phone. |
| Machine-learning classification | **applicable, new (firmware)** | The full decay curves (stage 3) give features a classifier can use: time-constant spectrum, amplitude vs bearing, sweep speed (IMU), ferrous flag (gradiometer), ground state. A small model (trees or a tiny network, kilobytes) runs on the M33 or in a phone app. It needs a labelled library of targets in several soils from the bench and the field. Use it on top of the physics ground model, not instead of it. |

## Adds to the plan
1. Ferrous gradiometer channel (fluxgate pair, head + shaft): bench test of the core's own response to the TX pulse.
2. INA849 (or equal) for the QA / QB / REF3 inputs: fetch the datasheet.
3. ML target-ID: start a labelled decay-curve library once full-waveform capture exists.
