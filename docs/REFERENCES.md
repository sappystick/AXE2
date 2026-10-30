# What AXE2 took from ARX, and why

AXE2 was split from ARX (sappystick/ARX, branch `claude/hopeful-bell-wms3xo`, commit 6420510, 2026-10-30). The ARX baseline is a 1.5-inch head with six petal formers and a vault. AXE2 keeps only what the clean-sheet 1-inch head uses or will use; the baseline stays in ARX.

| AXE2 path | From ARX | Why it is here |
|---|---|---|
| `rf2/` | `experiments/RF2_cleansheet/` (all tracked files) | the design: studies, head generators, routed boards, results, docs |
| `reference/rf1/` | `experiments/RF1_rigidflex/` | the routed AB1A / AB1B analog sections and the CB1D placement that Phase C reworks; RF1 studies and results |
| `src/pcb/freeroute.py` | `src/pcb/freeroute.py` | the Freerouting step (AXE2 adds a stall watchdog) |
| `src/pcb/astar_route.py` | new in AXE2 | the fallback router for open connections |
| `src/pcb/sbq_export.py`, `models3d.py` | same | generator of the SB1R quadrupole receive boards (`rf2_sb1r_variant.py` patches a copy: outline without the r 116 tab) |
| `src/pcb/gerber_geom.py` | same | layer geometry from Gerbers (checks that the copper of the variant is identical) |
| `src/pcb/kicad_drc.py`, `dru_gen.py` | same | KiCad DRC with the SB1R rules |
| `data/reference/sbq_geometry.json`, `GERBER_SB1R_QA`, `GERBER_SB1R_QB` | `work/kit_v22/` (generated in ARX by `make sbq-fast`) | the quadrupole board geometry and its baseline Gerbers (input and reference) |
| `data/reference/sim_head1.json` | `data/results/` | the baseline receiver sim that `rf2_figure.py` compares with |
| `data/datasheets/` | `data/seed/datasheets/` (25 of 43) | the parts this head uses or Phase C will use: LEDs, preamp, LDOs, display power, clamp diode, resistors, TX switch / driver / diode, fuse, battery cells and connector, gyro, potting |
| `docs/DATASHEET_LOG_ARX.md`, `CORRECTIONS_ARX.md`, `ASSUMPTIONS_ARX.md`, `CONVENTIONS.md` | `docs/` | the evidence trail; RF2 rows are marked RF2; baseline rows kept for provenance |

Not taken (baseline only): the petal formers and vault, the baseline boards (LB1, CB1D baseline, PB1R, PM2, HB2, AU1), the baseline pipeline and releases. If a later AXE2 phase needs one of them (for example the neck driver from PB1R, or the handle boards), copy it in, record it in this table and add its check to `run.py`.
