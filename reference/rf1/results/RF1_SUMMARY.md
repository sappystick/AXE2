# RF1 side experiment: results (MODELED, not part of the sign-off)

| Area | Baseline | RF1 | Source |
|---|---|---|---|
| AB1-CB1D link fit on the meshes | 6 / 16 FAIL | 0 / 14 FAIL | rf1_phase1.json |
| Headroom under LB1 / septum (mm) | -4.4 / -2.6 | 10.4 / 7.2 | rf1_phase1.json |
| Hand joints in the head | 66 | 5 | rf1_phase1.json |
| RX lead pickup spread, QA (sigma, mV) | untwisted 26.8123, twisted 0.688 | flex 0.1501 | rf1_phase2.json |
| Worst crosstalk into MONO_IN / VCM_OUT (mV, bound) | 436.878 / 215.343 | 7.107 / 1.36 | rf1_phase2.json |
| Head height (mm), K-top | 47.1 | 40.4 | rf1_cavity.json |
| L5 controller layer | coat only | potted SYN 22.8 cm3, net head mass 0.0 to 4.6 g | rf1_cavity.json |
| OPA2211 input bias vs range (V) | 1.25 vs [2.0, 3.6]: FAIL | 2.5: PASS | rf1_frontend_check.json |
| Stackup rigid / flex (mm) | - | 1.602 / 0.186 | rf1_phase4.json |
| Flattened panel (mm) | - | 331.7 x 171.2 (fits 18 x 24 in: True) | rf1_phase4.json |
| CB1D section swaps placed | - | no collision (8 clusters) | rf1_phase4.json |
| RF1 AB1A route | 0 open (baseline) | 0 open; KiCad DRC errors {}, unconnected 0; independent DRC {} | rf1_ab1_route.json |
| RF1 AB1B route | 0 open (baseline) | 0 open; KiCad DRC errors {}, unconnected 0; independent DRC {} | rf1_ab1_route.json |
