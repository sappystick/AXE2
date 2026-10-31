# RF2 enhancement plan: what to analyse and upgrade next, area by area (2026-10-30)

Each area lists:
- **Now:** what the current RF2 numbers rest on.
- **Open question:** what has not been checked.
- **Study:** the study that answers it, with the installed tool that does the work.
- **Accept:** the acceptance metric.

Every result is MODELED until bench data exists. A study that moves a number also updates the dependent studies and the sign-off (`make rf2-signoff`).

The fairness rule from the RF2 studies stays fixed: compare designs at equal energy per pulse (10.8 mJ) in the same receive chain (1.7 nV/rtHz, same gates). Depth is quoted for gold spheres, 1 / 5 / 20 g.

Already done with the new tools:
- **Field code:** `head/rf2_field_xcheck.py` shows the repo's loop field agrees with magpylib to 1.3e-10 relative at 30 points down to 500 mm. Every depth number therefore rests on checked field code.
- **Front end:** `head/rf2_mp1_spice.py` (ngspice) chose the MP1 v2 protection topology.

## Priority order (expected depth gain per unit of work)

| # | Area | Why first | Tool |
|---|---|---|---|
| 1 | MP1 v2 front end (noise) | about +28 % mono depth modeled (front end 1.4 instead of about 5 nV/rtHz); parts mostly verified | ngspice / spicelib, rf2_boards |
| 2 | Winding self-capacitance and turn-off (first gate time) | small gold lives in the early gates; the first gate (16.3 us) is set by L, C and damping, and C is ASSUMED (500 pF) | gmsh + scikit-fem (electrostatic), ngspice |
| 3 | TX bundle cross-section (columns x rows, radius, height) | B / sqrt(L) at depth is the depth figure at fixed energy | loop_B + magpylib, optuna |
| 4 | Litz choice (strands, AC resistance, eddy decay inside the winding) | strand eddy currents add a late tail that looks like a target | scikit-fem (2D eddy), analytic |
| 5 | Quadrupole null under build tolerances | the null decides how much TX leaks into the bearing channel | magpylib Monte Carlo |
| 6 | SH1 shield and nearby metal decay | every ring / track loop is a small target with its own tau | scikit-fem transient, loop L/R model |
| 7 | Former / channel: tolerance, potting, thermal | the turn positions set L and the null | cadquery (STEP), trimesh, rf2_head_check |
| 8 | Ground and EMI with the as-built coil | re-run ground balance and EMI cancellation on the final geometry | rf2_ground, rf2_ground_dsp, rf2_emi |
| 9 | Firmware on the target | timing of gates, LED blanking and audio on the real MCU | arm-none-eabi-gcc, host tests |

## 1. Transmit coil geometry

- **Now:** 26 turns in 3 columns (r 113.4 / 111.8 / 110.2 mm) x 9 rows from z 4.4 mm, pitch 1.6 mm; 333 uH, 8.06 A, 10.8 mJ. Chosen by rf2_coil_search / rf2_receiver_combo among discrete formations.
- **Open question:**
  - Is 3 x 9 the best cross-section in the channel? Wider and flatter, taller and thinner, or split into two bundles (top and bottom of the 25.4 mm height)?
  - Does moving the bundle down (closer to the ground) beat a larger radius?
- **Study:** `rf2_tx_xsection.py`.
  - optuna over (columns, rows, r_outer, z0, pitch) inside the channel envelope from `rf2_head.SPEC`;
  - objective: the 1 g and 5 g noise-limited depth at fixed energy (B / sqrt(L) at depth, from loop_B);
  - turn-off from rf2_timing with C taken from study 2.
  - Cross-check the winner's field with magpylib (as rf2_field_xcheck).
- **Accept:** the best cross-section and its depth gain, or "3 x 9 within 2 %" with the curve. If it changes, update SPEC, then the channel, ledger and harness via sign-off.

## 2. Winding capacitance and turn-off (the first gate)

- **Now:** node capacitance 500 pF ASSUMED; critical damping 408 ohm; first gate 16.3 us.
- **Open question:** what are the real inter-turn and turn-to-shield capacitances of this bundle in its channel, with potting (er 3.5-4.2, ASSUMED class values)? A lower C gives a faster decay and an earlier gate, so more depth on small gold.
- **Study:** `rf2_coil_capacitance.py`.
  - gmsh 2D axisymmetric mesh of the bundle cross-section, channel walls, potting and SH1;
  - scikit-fem electrostatic solve, giving the capacitance matrix and the lumped C seen by the switch (the turns form a voltage ladder);
  - feed C into rf2_timing / rf2_mp1_spice (ngspice) to get the first gate.
  - Variants: spacing between columns, a lower-er potting zone at the coil, and a split bundle.
- **Accept:** a computed C replaces the ASSUMED 500 pF, and the first gate is recomputed.

## 3. Receive: mono channel and quadrupole

- **Now:** the mono receive is the same rim coil (TX = RX), with MP1 at 1.7 nV/rtHz budget. The quadrupole boards (SB1R-QA / QB) are exact full rings (repo rule: no spirals).
- **Open questions:**
  - **Mono:** MP1 v2 (front end of section 1 in PARTS_RF2.md). The series resistor at the LMH6629 input is not yet sized (abs max +-10 mA, -0.5 V).
  - **Quad:** how deep is the TX null after placement and etch tolerances (board rotation, centre offset, layer registration), and how much bearing accuracy is left?
- **Studies:**
  - **MP1 v2:** extend `rf2_mp1_spice.py` with the clamp-to-input resistor sweep (noise against the input-current peak), using the real depletion MOSFET model once its datasheet is supplied.
  - **Quadrupole:** `rf2_quad_tolerance.py`, a magpylib Monte Carlo over offset 0-0.3 mm, rotation 0-0.5 deg and a 0.05 mm etch error, giving the null distribution and the residual TX volts at the first gate.
- **Accept:**
  - **MP1 v2:** the resistor value, then MP1 v2 routed and checked.
  - **Quadrupole:** the 95th-percentile null, and a placement tolerance written into the assembly notes.

## 4. Litz and winding losses

- **Now:** a light litz winding (mass and resistance from rf2_receiver_combo); the AC effects of the strands are not modeled.
- **Open question:** strand count and diameter against AC resistance at the turn-off spectrum, and the eddy decay inside the copper itself, which shows up as a late signal.
- **Study:** `rf2_litz.py`, an analytic proximity / skin loss calculation per strand option, checked by a scikit-fem 2D eddy solve of a bundle cross-section; output the copper's own decay tau against the earliest gate.
- **Accept:** the litz spec (strands x AWG) with its copper tau below the first gate by a stated factor.

## 5. Former, channel and housing

- **Now:** printed channel and walls (manifold3d STL), checks in rf2_head_check (closed meshes, clearances, seats).
- **Open questions:**
  - Turn-position tolerance in the printed channel (which feeds L and the null).
  - Potting shrinkage (1.4 % for 832TC, DATASHEET_LOG).
  - A machined or moulded former needs STEP, not STL.
- **Studies:**
  - **STEP export:** `rf2_step_export.py` writes cadquery STEP of the channel, lid and shell for CAM / moulding quotes.
  - **Tolerance stack:** trimesh checks of each turn site against the channel; the sensitivity of L and the null to a 0.1 mm turn shift, by reusing study 3.
- **Accept:** STEP files beside the STLs, and a tolerance table in HANDOFF_RF2.md.

## 6. Shield SH1 and metal near the coil

- **Now:** SH1 has 37 split rings and passes the no-loop-around-axis check. Its eddy decay has not been computed.
- **Open question:** each ring segment and every board loop (MP1, TXJ, the LR1 flex buses) is a small conductor in the TX field, so what is its decay tau and induced volts at the first gate?
- **Study:** `rf2_metal_decay.py`.
  - For each copper feature, take its polygon from the KiCad boards (pcbnew) and the TX field there from loop_B;
  - compute L/R per loop (analytic thin-film), induced EMF and decay;
  - give the summed signal at the first gate against the receive noise.
  - Use scikit-fem for the SH1 ring cross-section if the analytic answer is marginal.
- **Accept:** a table of the worst five features, each below noise at the first gate, or a design change.

## 7. LED ring flex (LR1) and the other boards

- **Now:** LR1 is a 2-layer flex with open C-shaped buses (no loop around the axis).
- **Open questions:**
  - The bus area and the SK9822 clock current switching near the RX coil.
  - The LEDs are held dark in the receive windows (firmware). Is that enough?
- **Study:** add LR1's buses to study 6, plus the induced voltage from the LED current loops (rf2_emi-style coupling with the real track geometry from the routed board).
- **Accept:** the coupling of each bus loop to the mono and the quadrupole channels, each below noise.

## 8. Ground, EMI and DSP on the final geometry

- **Now:** rf2_ground, rf2_ground_dsp and rf2_emi use the study coil.
- **Study:** re-run all three on the SPEC coil with C from study 2 and the MP1 v2 noise.
- **Accept:** updated depth versus ground severity, and the EMI cancellation residual.

## 9. Firmware

- **Now:** the Python reference DSP (rf2_ground_dsp) plus the baseline C firmware (fw/), host-tested.
- **Study:** port the RF2 detector to C, build it with arm-none-eabi-gcc for the head MCU, and run the host tests that compare it with the Python reference on the simulated sweeps.
- **Accept:** bit-exact or tolerance-matched against the Python reference; the cycle count per pulse fits the 400 Hz frame.

## How to run a study (template)

1. **Script:** a new script `rf2/<name>.py` that reads SPEC from `head/rf2_head.py` (never copy numbers) and writes `results/<name>.json` with a `status` line stating MODELED and the assumptions.
2. **Check:** add a check step to `head/rf2_signoff.py`.
3. **Record:** put new assumptions in `docs/ASSUMPTIONS.md` and datasheet values in `docs/design/DATASHEET_LOG.md`.
4. **Handoff:** one figure per decision, and a paragraph in HANDOFF_RF2.md saying what changed and what is still unproven.

## 10. Display (added 2026-10-30, 522-LED flex)

- **Centre-offset accuracy:**
  - Model the pinpoint centre-offset error (quadrupole null plus the mono peak, against SNR and depth) in `rf2_pinpoint.py`.
  - Accept: the ring spacing (8 mm) is at or below the modeled 1-sigma offset error at the depths that matter, or the spacing changes.
- **LED-to-receiver coupling:**
  - Study 7 now covers about 0.5 m of buses and 522 clocked parts.
  - Compute the induced volts at the mono and quadrupole channels from the bus and lane loops of the routed board, with the stream confined to the quiet slot.
  - Accept: below noise at the first gate.
- **Lid transmission:** measure the clear PETG lid's transmission and diffusion on a printed coupon; set the brightness cap from it.

## 11. From the 2026-10-30 ingest (docs/INGEST_2026-10-30.md)

- **Thin head:**
  - Option B (single electronics tier, 15.7 mm) and option C (flex layers + low-profile parts, 12.1 mm) are modeled with no depth loss: `rf2/rf2_thin.py`.
  - Before choosing, run study 2 (self-capacitance of the 5 x 6 and 4 x 7 bundles) and study 3 (flex receive copper), and check the coil-to-AB1 coupling.
- **MP1 v2:** the parts are decided (IXTY08N100D2, Rin2 100 ohm, LMH6629). Next: board layout and routing. The bench must measure the turn-off edge dV/dt, since the clamp-current spike depends on it.
- **Coil modeling:** add a finite-cross-section / tilt mutual-inductance cross-check (An 2022 Neumann model, or magpylib) for the flatter bundles and for REF3 under shaft tilt.

## Backlog: data, testing and tools (owner 2026-10-31; record only)

### How to add data
- **New chip / datasheet:**
  1. Put the PDF in data/datasheets/.
  2. Add a DATASHEET_LOG row.
  3. Rebuild the KB (`rf2/rf2_kb.py build`).
  4. Add the part as an axis option (rf2/rf2_variant_axes.py or a plugin).
- **New concept:**
  1. Test it in isolation in concepts/.
  2. Write an options study in rf2/.
  3. Add an axis or a plugin in rf2/variant_plugins/.
- **New formula:**
  - Reusable physics goes into concepts/clib.py with a self-test.
  - Study-specific formulas go in the module docstring (the KB indexes them).

### How to strengthen testing
1. **Fidelity ladder:** re-check formula winners with FastHenry, the full SPICE chain, 3D FEM (Elmer when built), and multi-time-constant target and viscous ground models. A disagreement over 10 % gets a flag and a CORRECTIONS row.
2. **Claim-based scenario library (rf2/scenarios/):**
   - target orientation sweeps;
   - ground types (neutral, magnetite, salt);
   - tilt and height wobble;
   - EMI;
   - temperature drift.
3. **Standing devil's-advocate agent:** it asks what physics the model misses that favours this idea. Each answer becomes a new test.
4. **Continuous design search** (coil radius, turns, comb pitch, bucking radius, tube across-flats) with differential evolution or Bayesian optimisation.
5. **Uncertainty on every ASSUMED value;** rank by the worst likely case.
6. **Reality grounding:** wire and flex coupon measurements (docs/WIRE_COUPONS.md, docs/FLEX_COUPONS.md) calibrate the models.
7. **Novelty scoring:** keep a few high-novelty variants in every search.

### Deferred (owner stopped them 2026-10-31)
- **Rebase onto the adopted machine:** the variant engine, its plugins (today flags: NTBG, s400, hybrid, bank, gland_fpc, ref_guard, rx_18um) and the clean-sheet calibration. No double counting. A partial patch of a stopped attempt was kept outside the repo.
- **Re-run of rf2_head_best.py** against the adopted machine, with the real PRX copper (2 x 35 um, about 103 ohm, 1.31 nV/rtHz).
