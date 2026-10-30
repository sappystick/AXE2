# AXE2

AXE2 is a clean-sheet 1-inch (D233 × 25.4 mm) pulse-induction detector head. Every part is produced by a generator: the housing parts, the routed boards (KiCad + Gerbers), the system netlist, the checks and the physics studies. The whole set is driven by one smart runner. Split from [ARX](https://github.com/sappystick/ARX) on 2026-10-30.

**Status:** MODELED / tool-checked. See `STATUS.md` (generated) and `START_HERE.md`.

```bash
make tools            # install + self-test (KiCad 9, libraries, ngspice, gmsh, ARM gcc, Java 25 + Freerouting, pinned Python)
python3 run.py        # run only what is needed: failed / changed / missing / dependents
python3 run.py --failed
```

| Folder | Contents |
|---|---|
| `rf2/head/` | head generators: SPEC + housing (`rf2_head.py`), system netlist, boards (`rf2_boards.py`, display `rf2_ledgrid.py`, shield, receive-board variant), checks, renders; outputs in `rf2/head/out/` |
| `rf2/` | physics studies (coil formation, receivers, ground, EMI, timing, pinpoint, ...), results, handoff, parts, enhancement plan |
| `src/pcb/` | routing and board tools: Freerouting step (stall watchdog), A* fallback router, Gerber geometry, DRC helpers, SB1R generator |
| `reference/rf1/` | RF1 rigid-flex work: routed AB1A / AB1B, CB1D placement (Phase C starts here) |
| `data/` | datasheets (verified values in `docs/DATASHEET_LOG_ARX.md`), reference inputs |
| `state/` | runner ledger (results of every step); logs are not committed |
| `docs/` | references to ARX, corrections, assumptions, conventions |
