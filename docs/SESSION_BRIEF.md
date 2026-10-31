# Session brief (read this first)

## Where the design stands (2026-10-31; MODELED, no bench test)
- **Adopted head and drive (owner 2026-10-31; HANDOFF §55-56):**
  - **Switch:** NTBG080N120SC1 for Q1, Q2 and Q30.
  - **Drive:** 477 V clamp, 8.94 A scan / 14.14 A boost, 318 us flat-top.
  - **TXD:** a pod on the shaft at s 400.
  - **Cord flex:** TX strips 3.22 mm, REF guard trace, Y5B gland ZIFs.
  - **Head:**
    - bank-wound 26-turn coil (0.1 mm higher);
    - PRX planar nulled receive layer and the MP2 second receive board on fin A2;
    - QA/QB at 18 um;
    - glove housing (zone map, pockets, shield slots, potting, channels; 0 interference);
    - head 759 g.
- **Runtime:** boost 2.9 h, scan 5.4 h (P45B 7S1P).
- **Not rebased yet:** the variant engine, plugins, clean-sheet and head-best still use the pre-adoption machine as "today". See the backlog in rf2/ENHANCEMENT_PLAN_RF2.md.

## Open decisions (owner)
1. **Cord flex piece-1 width 18.24 vs 16.6 mm (BLOCKED).** Options: 3 oz TX strips; drop the guard (17.44 mm); relax the 10 K rise; a wider inner tube.
2. **TXD echo at the shortest shaft 0.605 vs 0.5 (FAIL).** Options: limit collapse by 13 mm; move REF3 and the pod up the shaft.

## Pipeline state
- Pipeline 2026-10-31: 47 pass, 7 fail. chassis / system / flex-options fail on the two open decisions (cord width BLOCKED, TXD echo FAIL; flex-options still uses the 18 mm round bore). lowL-options / variant-learn (no rule-clean option left at the new cord width) and cleansheet / head-best (chassis item renamed by the TXD move) fail because they are not rebased: see the backlog.

## Open work
- PRX board artwork.
- HV fin board.
- Cord-flex land board in the head.
- MP2 output tail to the hub.
- Potting densities unconfirmed.

## Commands
- **Pipeline:** `python3 run.py --plan` first, then `python3 run.py --step <id>` or the incremental `python3 run.py -j 3`. Never `--cold` unless asked.
- **Variant engine (owner request only):** `python3 rf2/rf2_variants.py [--fix axis=id] [--list]`; learning `rf2/rf2_variant_learn.py`; Optuna `rf2/rf2_variant_optuna.py`.
- **Knowledge base:** `python3 rf2/rf2_kb.py build | part <name> | search "<q>" | param <sym> | fact <key> | deps <file> | gaps`.
- **Working mode:** CLAUDE.md "Working mode (owner, token budget)".

## Read next
- START_HERE.md
- STATUS.md
- rf2/HANDOFF_RF2.md §55-57
- docs/HEAD_BEST.md
- docs/VARIANTS.md
- docs/RULE_NEAR_MISSES.md
