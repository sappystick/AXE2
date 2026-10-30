# Bench test: fluxgate gradiometer as a passive ferrous channel

Model: `rf2/rf2_fluxgate.py`. Status: MODELED; nothing below has been measured.

## What the model says (to be verified)

Ranges as "1e-4 / 1e-5 mismatch". The DRV425 column uses its datasheet noise (1.5 nT/rtHz typ) and offset drift (5 nT/C, 0.5 K between the sensors ASSUMED); the generic column is the earlier 10 pT/rtHz assumption (UNVERIFIED), kept for comparison (CORRECTIONS 2026-10-30).

| Target (steel) | Field at 100 mm | TI DRV425 | generic 10 pT/rtHz |
|---|---|---|---|
| 3 g compact lump | 6.5 nT | 45 / 55 mm | 70 / 160 mm |
| 50 x 3 mm nail along the Earth's field | 222 nT | 175 / 200 mm | 250 / 525 mm |
| same nail across the field | 4 nT | 40 / 45 mm | 60 / 135 mm |
| 100 g lump | 218 nT | 175 / 200 mm | 250 / 520 mm |

- Range is set by how well the two sensors cancel the Earth's field as the head rotates (residual mismatch), not by sensor noise (10 pT/rtHz ASSUMED).
- Gold has no induced moment: anything this channel sees is ferrous.

## Parts to get
1. Two matched 3-axis fluxgate sensors with datasheets: noise, range, bandwidth, excitation frequency and saturation recovery. Candidates to look at: Stefan Mayer FLC3-70 / FLC100 class, Bartington Mag-13 class (laboratory reference), Texas Instruments DRV425 (an integrated single-axis fluxgate, +-2 mT).
2. A non-magnetic rig: PETG or wood, brass-free (nylon screws).
3. The AXE2 transmit coil and driver (or the ARX bench TX) for the pulse-exposure tests.

## Tests
1. **Noise floor:** both sensors in a quiet place (or a mu-metal can); 10 minutes; spectral density 0.1-10 Hz.
2. **Calibration and rotation residual:**
   - mount both on a 0.6 m PETG rod;
   - rotate it through the head's real sweep (+-45 deg yaw, +-15 deg pitch / roll);
   - fit 12 parameters per sensor (offset, gain, non-orthogonality);
   - report the residual of (lower - upper) in nT and as a fraction of 50 uT.
   - This sets the real range (see the table).
3. **Targets:** the four targets above, at 50 / 100 / 150 / 250 / 400 mm under the lower sensor, nail in both orientations. Compare with the model.
4. **TX pulse exposure:**
   - lower sensor at the head centre, the coil pulsing at 400 Hz;
   - record the sensor output after each pulse and how long it takes to return to its pre-pulse value (+-1 nT);
   - this decides whether it can be read in the 1.16 ms quiet window.
5. **The sensor as a target:**
   - mono residual with and without the sensor (and its permalloy core) at the head centre;
   - must be < 1 x gate noise, or stable enough to subtract (drift per K).
6. **Temperature:** residual mismatch from 10 to 40 C (sun on the head).

## Pass criteria
- Rotation residual <= 1e-4 of the Earth's field after calibration.
- Recovery after a TX pulse < 1 ms.
- Mono residual with the sensor present < 1 x gate noise, or drift < 0.1 x noise per K.
