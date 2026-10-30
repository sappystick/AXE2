# AXE2 decay-curve library: format and status

- **Purpose:** a labelled set of full receive waveforms for target identification (owner list, 2026-10-30).
- **v0 (`sim_v0`):** SIMULATED from the physics models (`rf2/rf2_decaylib.py`). It exists to fix the format, the feature pipeline and a baseline. It says nothing about field performance.

## Files (`data/decaylib/`)
- `<version>_index.json`: `{"schema": ..., "version": ..., "entries": [ {entry}, ... ]}`.
- `<version>_samples.npz`: example waveforms keyed by entry id, plus `t_us`.
  - v0 stores 40 examples; the full set regenerates from the seed (20261030).
  - Bench and field versions store every waveform.

## Entry fields
| Field | Meaning |
|---|---|
| `id` | unique id: `<version>-<class>-<n>` |
| `source` | `simulated` / `bench` / `field` |
| `cls` | physical class: compact_nonferrous, ring_foil, ferrous, ground_viscous, ground_conductive (more classes when real data shows the need) |
| `metal`, `mass_g`, `size_mm`, `mu_r`, `tau_us` | target description (what is known) |
| `depth_mm`, `lateral_mm`, `orientation` | position under the head |
| `ground_bg_x_noise` | unbalanced ground amplitude in noise units (simulated) |
| `snr_20sample` | peak SNR after a 20-sample moving average |
| bench / field only: `soil`, `moisture`, `temperature_C`, `sweep_speed_m_s`, `height_mm`, `firmware`, `operator`, `date`, `gps` (field), `photo` | conditions |

## Receiver assumptions in v0
- **Sampling:** AD7389-4 at 2 MSPS; first sample 13.5 us (SiC switch + syntactic potting), 1000 samples (500 us).
- **Noise:** 1.54 nV/rtHz over 1 MHz, averaged over 100 pulses: 0.154 uV per sample.

## Baseline (rf2/results/rf2_decaylib.json)
- **Data:** 2878 simulated entries; features are 12 geometric gate means, raw plus ground-balanced (1/t projected out).
- **Classifier:** numpy softmax regression.
- **Test accuracy:** 85 % overall (simulated). Per class:
  - ground conductive 98 %, ground viscous 93 %;
  - ferrous 93 % (an ASSUMED model);
  - ring / foil 70 %, compact non-ferrous 64 %.
- **Confusion compact <-> ring:** this is physics. A decay sees conductivity x size^2, so a gold nugget and an aluminium piece of the same time constant decay alike: the classes are physical, not metals.
- **Next features:**
  - the spatial response along the sweep (IMU position);
  - the quadrupole bearing shape;
  - the ferrous flag (gradiometer);
  - the response's change with transmit period (multi-period).

## How to add bench data
Record 100-pulse averages at the AD7389-4 rate. For each target, record:
- several depths (50-400 mm);
- three orientations;
- air and two soils;
- two temperatures.
Fill the fields above with `source = "bench"`. Keep simulated and real entries separate when training and testing, and report real-data accuracy only on held-out real entries.
