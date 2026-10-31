# Variant engine audit (critic, 2026-10-31; MODELED tooling review)

Scope: rf2/rf2_variants.py (engine), rf2/rf2_variant_axes.py (core axes), rf2/variant_plugins/{boards,coil_winding,wiring}.py, rf2/rf2_variant_learn.py.
Method: code reading, a plugin-isolation invariance script (each plugin removed and re-run on 150 random combinations with its own axes at today's options),
KB look-ups (`python3 rf2/rf2_kb.py part|search`) against data/datasheets and docs/DATASHEET_LOG_ARX.md, the engine's own depth model compared with the
plugins' scaling laws, and a sub-space comparison of full enumeration against search mode. Every fix carries a `# critic 2026-10-31:` comment.
Nothing here is a bench result. Every performance number is MODELED.

## Findings

| # | Sev | Where (file:line, after the fixes) | Finding / evidence | Fixed |
|---|---|---|---|---|
| 1 | HIGH | rf2/variant_plugins/boards.py:223 | **Scoring bias.** The row "MP1 input noise vs the 1.7 nV/rtHz target" was added only for alternative preamps. Today's LMH6629 (2.211 nV/rtHz) fails it too (rf2_rules `mp1.noise`, FAIL +30.1 %), and no option can meet it: the floor without any amplifier is 1.911 nV/rtHz (`ctx.boards["amps"][*]["floor"]`). The row pushed every alternative preamp out of the no-break set for a target the whole machine fails. Fix: the row was removed from the option rows. The target is still reported once, for the machine, by rf2_rules `mp1.noise`. Each option's value against it is kept as `extra.bd_noise_vs_1p7_target_pct` (OPA2211 +46.4 %, INA849_G100 +30.3 %, OP470 +189 %). Choice stated under rule 9. Adding the row to every row instead would leave no row free of breaks (floor > target). | y |
| 2 | MED | boards.py:114-131, 217, 259 | **Depth scaling exponent.** The plugin scaled depth by (N_today/N_new)^(1/6), the far-field z^-6 law. The engine's own depth model (rf2_lowL_options.echo_mono/depth), with the threshold scaled by the noise ratio, gives local exponents of 0.174 (coin), 0.19 (1 g gold) and 0.26-0.28 (0.1 g gold, near field). OP470 example: 0.1 g depth x0.875 (1/6 law) against x0.798 (model). The 1/6 law under-stated the change for small targets by 35-60 %. Fix: new `depth_ratio()` uses the engine model at the combination's coil, scan current and mono gate, for the preamp swap and for the chassis-placement Johnson noise. The 1/6 law stays in the extras (`bd_depth_scale_1_6`) and in BOARDS_COMPONENTS_MAP.md. | y |
| 3 | MED | rf2/rf2_variants.py:81 | **Telescope bore ignored the wall axis.** `BORE = 21 - 2 x 1.2` was fixed, so the rows "cord-flex width vs bore less 2" and "rolling loop vs bore less 4" did not change with w1.0 / w1.5 (bore 19.0 / 18.0 mm). Fix: `bore = 21 - 2 t` per row. Today's value (18.6 mm) is unchanged. | y |
| 4 | MED | rf2_variants.py:88-92, 109 | **Pack cell-current safety row.** (a) It was computed from the core boost power before the plugins ran, so power changes from coil_winding / boards / wiring never reached this safety row. Fix: the value is re-evaluated after the plugins from `m["P_boost_W"]`. (b) Pack E (RC LiPo) has no cell rating in rf2_pack_options and silently had no safety row. Fix: a safety row "cell continuous-current rating on file" (0 vs 1, fails) names the gap, following the plugins' 'datasheet on file' pattern. Pack E rows now show this break. | y |
| 5 | MED | rf2/rf2_variant_learn.py:141-146 | **Learning on a non-random sample.** In search mode about 3,196 of 33,254 rows come from coordinate ascent and cluster around the best seeds. Main effects, variance shares and the surrogate R2 were computed over all rows. Fix: the engine now tags each row's `origin` (enum / ofat / random / ascent; new CSV column). The learning layer uses only enum + random rows (30,000) and reports the all-rows R2 next to it: R2 out-of-fold 0.9928 unbiased against 0.9954 with the ascent rows. The ascent rows inflate R2 slightly. The surrogate stays meaningful because the score is close to additive over the options. | y |
| 6 | MED | rf2_variants.py:192 (search) | **Search mode can miss per-objective champions.** On a 69,120-combination sub-space (switch, txd, shaft, data, wall, clamp, flex_cu, board_stack, cord_lanes, connectors and splice held at today's options), full enumeration and search (300 or 3,000 random samples + ascent) found the same best score (1.077) and the same best no-break score (1.0505), and 7 of 9 no-break champions match. Search missed `small_gold` (16.7 vs 16.8 cm) and `lightest` (-161 g at 300 samples, 14.7 cm / -215 g at 3,000, against -215 g / 15.2 cm). Coordinate ascent optimises the score only. Not fixed: in search mode the per-objective champions are approximate. Adding an ascent per objective would close this. | n |
| 7 | MED | rf2_variants.py:123 | **'Fewer parts' factor.** `attach = 1/(1+0.1 n)` with a negative n (wiring gland_fpc: n = -2) gave 1.25, and the formula is singular at n = -10. rf2_select uses 1 + 0.1·n for fewer parts. Fix: rf2_select's form, giving 1.20 at -2. Best no-break score moved 1.1633 -> 1.1583 from this alone. | y |
| 8 | LOW | rf2_variants.py:21 | **POF mass.** POF_G counted one 1.6 m fibre for 3 links: 18.4 g, while the docstring said 28 g. GH-4001-P 4 g/m is logged in DATASHEET_LOG. Fix: 3 x 1.6 x 4 + 6 x 2 (transceivers, ASSUMED) = 31.2 g; docstring corrected. | y |
| 9 | LOW | coil_winding.py:187, 173 | In hybrid rows the mono depth ratio was evaluated at `e["gate"]`, which is the earlier planar gate. Fix: it now uses `gate_mono` (also added to the cache key). | y |
| 10 | LOW | coil_winding.py:201 | Boost power was rebuilt from the rounded runtime (wh / runtime_boost_h, about ±0.2 %), while boards and wiring use `P_boost_W`. Fix: `P_boost_W` is used. | y |
| 11 | LOW | rf2_variant_learn.py:156 | Every Monte Carlo influence was 0 (the winner never changed in 60 draws), yet `next_study` named 'hot' because it is the first key of the dict. Fix: it now reports "none: the winner did not change in any draw". | y |
| 12 | LOW | rf2_variant_learn.py:121-126 | Owner-decision pairs: an unreachable combination (evaluate_combo -> None) crashed `dict(None)`. Fix: guarded. The pair logic is otherwise correct: each pair differs only in the decided axis, everything else is today's option, and each is scored against today's machine. 3 of 4 decisions agree with the default weights; the default weights disagree with C2 over B, so the learned weights shift weight from runtime to mass. With 4 decisions for 7 weights this is a weak signal, and the tool says so. | y |
| 13 | LOW | boards.py:287 vs rf2_variants.py:21,103 | **Hybrid mass is not a double count.** The engine's RX_G (8 g) is the planar PI receive layer; boards' +8 g is the second MP1-class board. They are two different items, both ASSUMED. Gap: the second board (24 parts in the MP1 v1 netlist) is not in `added_parts`; the engine adds +1 for hybrid. | n |
| 14 | LOW | boards.py:52-54 / 113 | Preamp supply delta is taken against LMH6629 2 x 15.5 mA, but the core head budget (rf2_lowL_options P_HEAD) still carries MP1 v1 at 0.02 A (the plugin's own docstring notes this). Alternatives get a -0.132 W credit against a load today's budget does not charge (about +0.3 % runtime). | n |
| 15 | LOW | boards.py:54-56 | OPA2211 bandwidth uses the GBW at G 100 (80 MHz); OPA1612 uses the GBW at G 1 (40 MHz; the PDF gives 80 MHz at G 100). Both pass the 1 MHz row. | n |
| 16 | LOW | wiring.py:243-244 | one_piece: the joint mass removed uses 2 oz copper and 2 x W_TX whatever `flex_cu` / `tx2` are set to. The R removed (R_flex x 40/L) assumes the lap adds series length, but a soldered lap is in parallel. Effects are under 1 g and under 1 mohm. | n |
| 17 | LOW | boards.py:232 then coil_winding.py:195, wiring.py:220 | Plugins run in a fixed order and add gate deltas. If boards pushed the first gate to the amplifier settle time, coil_winding and wiring would add their deltas on top. With today's recovery times (≤ 0.5 us) this never triggers (settle ≤ 0.887 x gate + 0.5 us). Depth is not re-evaluated at a pushed gate (stated in the extra). | n |
| 18 | LOW | wiring.py:196-197, coil_winding.py:205-210 | Rule rows exist only for non-today options: the rule-6 gaps (1.0 vs 1.0 mm for every lane option), litz OD vs slot (1.372 vs 1.42, 3.4 % headroom), stack top and inner wall. Today's margin is 1.0 (its own sag and collapsed rows sit at their limits), so these rows do not lower any option's margin factor below today's. This breaks if today's minimum margin rises above 1.0. Emitting the same rows for today's machine would remove the asymmetry. | n |
| 19 | LOW | rf2_variants.py:22 POF_W; rf2_variant_learn.py:89 | POF power is 0.60 W, ASSUMED, with Monte Carlo range 0.41-0.60 W. From DATASHEET_LOG (AFBR-1624Z / 2624Z ICCT 21-31 mA, ICCR 20-30 mA), 3 links take 0.62-0.92 W at 5 V and 0.41-0.60 W at 3.3 V. The supply voltage is not stated, so the 5 V case is outside the Monte Carlo range. | n |
| 20 | LOW | rf2_pack_options.json | `cell_current_frac_of_rating` is rounded to 2 decimals (C2 0.04), so the scaled safety row has a coarse base. | n |
| 21 | LOW | rf2/rf2_rules.py:72 (not editable here) | The description says "18 mm bore", but the value used is rf2_flex_options `bore_mm` 18.6. Stale text only. | n |
| 22 | LOW | rf2_variants.py:102 | `(P["oz"] == 3) * 0` is a no-op term in `added`. Cosmetic. | n |

### Datasheet spot-check (fabrication audit): 34 values, none fabricated

Checked with `rf2_kb.py part` / `search` against the PDF text and DATASHEET_LOG:
- LMH6629: en 0.69 nV, in 2.6 pA, IQ 15.5 mA, supply 2.7-5.5 V, CMVR -0.3..3.8 V (log row RF2-DS-MP1V2).
- OPA2211: en 1.1, In 1.7 pA, IQ 3.6 mA/ch, GBW 80 MHz (G 100), supply 4.5-36 V, CM (V-)+2..(V+)-1.4 (log line 33 / 161), overload recovery 500 ns (PDF p9, not logged).
- OPA1612: en 1.1, 4.5-36 V, CM 2.0-3.0 V on 5 V (logged); In 1.7 pA, IQ 3.6 mA, GBW 40 MHz at G 1, recovery 500 ns (PDF p5-6, flagged PDF-only in the plugin).
- INA849: eNI 1 / eNO 45 nV, in 1.1 pA, BW 8 MHz at G 100, settling 0.4 us, supply 8-36 V (logged); IQ 6.2 mA (PDF p7, flagged PDF-only).
- OP470: en 3.2, in 0.4, GBW 6 MHz, Icc 9 mA for four, ±4.5..±18 V (logged).
- TPS65131: VPOS ≤ 15 V, VNEG ≥ -15 V (logged).
- C3M0280090J IDM 22 A (PDF p1). NTBG080N120SC1 IDM 110 A (PDF p1; **not in the DATASHEET_LOG row**, a gap to log).
- JST GH 1.0 A / 50 V; Panasonic Y5B 0.5 A per pin / 50 V; Amass MT60 DC 500 V / 30 A / 0.45 mohm / 1000 cycles (logged; wiring.prepare() checks the exact log text and the PDF: all three True).
- GH-4001-P 4 g/m (logged). Tech Etch ProtoShield 0.254 mm (logged).
- Rubadue TXXL66/38F-2 OD 1.372 mm, 1000 V; double / single FEP 600 V (rf2_wire_options.json from the logged catalog).

Clearly labelled ASSUMED (acceptable, listed for the owner):
- TPS65131 efficiency 80 %; R_P / R_N source impedances.
- MP1 island 8 g; planar RX 8 g; POF 0.60 W and 2 g per transceiver.
- connector masses (JST 0.4 g, Y5B 0.15 g, MT60 5 g, pigtail 0.6 g); guard width 0.5 mm; hatch fill 0.5; polyimide eps 3.4.
- coil diagonal screening x0.5, ground plane z 3.2, eps 2.1.
- clock-spring drum radius 17 mm; 40 x stack bend rule; regen recovery 75 %.
- Tech Etch can 12 x 12 x 3 mm (not counted); 16.9 m of QA/QB trace for the copper-mass delta.

## Baseline check (today invariance)

- Today's combination (every axis at today's option) gives first gate **16.26 us**, boost **2.6 h** (scan 5.19 h), depth coin / 1 g / 0.1 g **60.2 / 30.2 / 15.0 cm**, mass delta **0 g**, added parts 0, breaks 0, score 1.0. **PASS**, before and after the fixes.
- Plugin isolation (450 random combinations, each plugin's own axes at today's options, other axes random, including coil 15x2 / 10x3, hybrid, fold shafts, POF, 3 oz): coil_winding and wiring leave every metric, rule row and extra unchanged (0 differences). boards differs only when rx = hybrid, by design: +8 g for the second receive board and its placement-drift row. **PASS**.

## Rule-11 rows to add to rf2/rf2_rules.py (numeric limits checked in the variant engine / plugins with no row yet)

| Proposed id | Kind | Rule | Today / worst option value vs limit | Status today |
|---|---|---|---|---|
| var.litz.slot_fit | target | litz OD vs comb slot - 0.05 | 1.372 vs 1.42 mm | **EDGE 3.4 %** |
| var.coil.stack_top | target | coil stack top vs channel top z 12.6 | 12.376 vs 12.6 | **EDGE 1.8 %** |
| var.coil.inner_wall | target | inner column edge vs channel inner wall r 104.6 | 105.634 (today) / 104.714 (wide2.0) vs 104.6 | **EDGE 1.0 % / 0.1 %** |
| var.coil.tooth | target | comb tooth vs 0.30 mm | 0.47 today; narrow1.67 0.20 | narrow FAIL |
| var.coil.v_turn | safety | max turn-to-turn voltage vs litz rating | 106 V vs 1000 V | PASS |
| var.coil.reach | target | boost current vs VBUS / R_loop | per option | — |
| var.flex.rule6_txtx / var.flex.rule6_txlv | safety | cord-flex TX_A-TX_B and TX-to-other copper ≥ 1.0 mm | 1.0 vs 1.0 mm (today and every lane option) | **EDGE 0 %** (safety: report only) |
| var.flex.rolling_loop | target | rolling loop 2 x 40 x stack vs bore - 4 | 12.0 vs 14.6 today; 3 oz 14.8 vs 14.6 | 3 oz **BLOCKED 1.4 %** |
| var.flex.clock_spring | target | fold clock spring 40 x stack vs drum r 17 | 6.0-9.8 vs 17 | PASS |
| var.flex.dyn_layers | target | conductive layers in the dynamic flex vs 1 (Minco) | ref_layer2 / tx2: 2 | FAIL for those options |
| var.shaft.hv_face | target | HV lane group width vs one inner face (fold) | per profile | — |
| var.txd.idm80 | safety | TX switch peak vs 80 % IDM | 12.74 vs 17.6 A | PASS (27.6 %) |
| var.mp1.settle_amp | target | MP1 settle + amp overload recovery vs first gate | 14.93 vs 16.26 us (OPA2211) | PASS (8 %) |
| var.mp1.amp_bw | target | stage-1 bandwidth vs 1 MHz | OP470 0.6 MHz | OP470 FAIL |
| var.mp1.amp_supply | safety | rail vs part min / max supply | OPA2211 5 V vs 4.5 V min | PASS (10 %) |
| var.mp1.cm_head | target | input CM headroom at VBIAS 2.5 V | OPA2211 / OPA1612 0.5 V | PASS |
| var.place.drift | target | placement echo drift (5 K) vs 0.5 x gate noise (B_flat, hv1_lead_plane, chassis can, second channel) | B_flat 9.35 vs 0.5 | B_flat FAIL |
| var.place.lead_sep | target | HV fin separation vs 4 deg | hv1_lead_plane 0 vs 4 | FAIL |
| var.conn.y5b_i / var.conn.y5b_v | target / safety | Y5B per pin 0.225 vs 0.5 A; 29.4 vs 50 V | — | PASS |
| var.conn.mt60_rule6 | safety | TX contact rating vs 630 V | MT60 500 V | FAIL (20.6 % short) |
| var.conn.mt60_i | target | TX rms vs 30 A | — | PASS |
| var.conn.b2b_rule6 | safety | TXD-PWR HV connector ≥ 630 V on file | none | FAIL (gap) |
| var.pack.rating_on_file | safety | cell current rating on file (pack E) | none | FAIL (gap) |

## Re-run after the fixes (`python3 rf2/rf2_variants.py --no-history`, `python3 rf2/rf2_variant_learn.py --mc 60`)

| Number | Before (last history line, 06:36) | After |
|---|---|---|
| Combinations evaluated | 33,005 | 33,254 (the search path changed with the new scores) |
| Break no rule | 290 | 416 (preamp alternatives no longer carry the 1.7 nV row; pack E now carries its rating-gap row; bore follows the wall) |
| Pareto front | 1,726 | 1,637 |
| Today's rank / score | 2,677 / 1.0 | 2,860 / 1.0 |
| Best score (any) | 1.211 | 1.206 (same combination; attach factor 1.25 -> 1.20) |
| Best no-break score | 1.1633 | 1.1583 (same combination: NTBG, TXD s400, pack B, bank winding, gland_fpc) |
| Surrogate R2 (out-of-fold) | 0.9948 (all rows) | 0.9928 (30,000 random rows); 0.9954 with the ascent rows |
| Monte Carlo winner | - | the same in 60 of 60 draws; next study names no assumption |

## Remaining risks

- In search mode the per-objective champions are approximate (finding 6). The score optimum was found on the tested sub-space, but that does not prove it for the full 1.4e10 space.
- The depth fix (finding 2) applies the mono-channel ratio to the hybrid combined depth. For the planar channel this is an upper bound.
- Unfixed asymmetric rule rows (finding 18) are harmless only while today's minimum margin stays at 1.0.
- The core head power budget is out of date for MP1 v2 (finding 14); rf2_lowL_options is outside this audit's edit scope.
- NTBG080N120SC1 IDM 110 A and several OPA1612 / INA849 values are read from the PDF but not logged in DATASHEET_LOG (rule 7 gap, flagged in the code).
- The Monte Carlo winner was the same in all 60 draws, but the top no-break list is mostly near-duplicates (winding / splice permutations of one machine). The test shows robustness of that cluster, not of distinct designs.
- Nothing here is verified on hardware; all numbers are MODELED.
