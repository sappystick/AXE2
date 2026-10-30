# AXE2 corrections (earlier statements found wrong; ARX history in CORRECTIONS_ARX.md)

| Old claim | Correct statement | Evidence |
|---|---|---|
| Thin-head options "modeled depth 136 mm (1 g) / 190 mm (20 g), unchanged" (INGEST_2026-10-30, HANDOFF section 17, chat 2026-10-30) | Those numbers were the **quadrupole** (bearing / pinpoint) channel, from rf2_coil_search.evaluate, which scores a transmit coil through the RX-Q boards. The **mono** detection channel, same model, MP1 v2 noise, 16.3 us gate: **A 25.4 mm: 341 / 436 / 525 mm (1 / 5 / 20 g); B 15.7 mm: 340 / 434 / 521; C 12.1 mm: 341 / 434 / 521**. The SDC 2300-class 8 in mono in the same chain: 320 / 408 / 490. The conclusion (thinning costs no modeled depth) stands. The earlier 20 g "500 mm" was capped by the 0.5 m depth grid; the grid now runs to 1.0 m. | rf2/rf2_depth_levers.py, rf2/results/rf2_depth_levers.json |
