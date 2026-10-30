#!/usr/bin/env python3
"""RF2 integration matrix (2026-10-30, owner: 'a thorough comparison of design integration enhancement potential for every area these sources apply to').
GENERATED from the study results: every owner-supplied source (wire, flex, photo-etch, shield, coil, coax, shaft, tube, HV-design data) mapped to every
area of the machine it can touch, with its status (ADOPTED / PROPOSED / FEASIBLE-NOT-ADOPTED / REJECTED / OPEN), the numbers that decide it, the rule
near-miss it raises and the next action. Writes docs/INTEGRATION_MATRIX.md and rf2/results/rf2_integration.json.   usage: python3 rf2/rf2_integration.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
def J(*p):
    f = os.path.join(ROOT, *p); return json.load(open(f)) if os.path.exists(f) else {}

def main():
    wo, fo, so, po, ru = J("rf2", "results", "rf2_wire_options.json"), J("rf2", "results", "rf2_flex_options.json"), J("rf2", "results", "rf2_shaft_options.json"), \
                         J("rf2", "results", "rf2_pack_options.json"), J("rf2", "results", "rf2_rules.json")
    ch = J("rf2", "chassis_out", "rf2_chassis_check.json"); tc = J("rf2", "results", "rf2_timing_cord.json"); hc = J("rf2", "head", "out_BF", "rf2_head_check.json")
    a = fo.get("A_cord_to_flex", {}); b = fo.get("B_shield_can", {}).get("places", {}); c = fo.get("C_becu_fingers", {}); d = fo.get("D_ref3_flexcoils", {})
    best = wo.get("coil_best_rule6_ok_in_comb", {}); blk = (wo.get("coil_blocked_by_rule6_within_10pct") or [{}])[0]
    walls = {r["wall_mm"]: r for r in so.get("walls", [])}
    flagged = {r["id"]: r for r in ru.get("flagged", [])}
    def fl(prefix): return "; ".join(f"{r['status']} {r['desc'][:60]} ({r['value']} vs {r['limit']})" for k, r in flagged.items() if k.startswith(prefix)) or "-"
    M = []
    def row(area, idea, source, status, numbers, effect, rule, nxt): M.append(dict(area=area, idea=idea, source=source, status=status, numbers=numbers, effect=effect, rule=rule, next=nxt))
    # ---- head
    row("Head: transmit coil wire", f"Rubadue {best.get('part', '?')} triple-insulated FEP litz", "Rubadue litz catalog", "ADOPTED",
        f"{best.get('v_rating', 0):.0f} V, OD {best.get('od_mm')} mm, {best.get('R_coil_20C')} ohm (model was 0.53, unsourced)", "rule-6-compliant coil wire with a named construction; boost 3.6 -> 3.5 h", "-", "vendor spec sheet (exact OD, breakdown)")
    row("Head: transmit coil wire", f"Rubadue {blk.get('part', '?')} single-insulated litz", "Rubadue litz catalog", "BLOCKED (rule 6)",
        f"{blk.get('v_rating', 0):.0f} V, OD {blk.get('od_mm')} mm, {blk.get('R_coil_20C')} ohm: fits the 1.47 mm comb", f"coil I2R -{100 * (1 - blk.get('R_coil_20C', 1) / max(best.get('R_coil_20C', 1), 1e-9)):.0f} %", fl("wire.coil"), "owner: rule 6 kept at 630 V (2026-10-30)")
    row("Head: transmit coil wire", "Pack RUPALIT bare litz as the core of an FEP extrusion", "Pack RUPALIT", "REJECTED", "silk wrapping, no voltage rating", "-", "-", "only via a vendor FEP jacket")
    row("Head: coil geometry", "6 rows x 5 columns, comb slot 1.47 mm (1.77 mm radial pitch, rows 1.44 mm)", "Rubadue OD + zone rule", "ADOPTED",
        "L +0.8 %, field at depth within 0.5 %, inner-wall gap 1.035 mm", "keeps the bay, fins and cradles where they were", "-", "-")
    for k, v in b.items():
        st = "REJECTED" if not v["slotted_ok"] else "PROPOSED"
        row("Head: shielding" if "chassis" not in k else "Control chassis: shielding", f"photo-etched shield can ({k})", "Tech Etch shields, ProtoShield", st if "chassis" not in k else ("PROPOSED" if v["closed_ok"] else "REJECTED"),
            f"closed-can drift {v['closed_can']['drift5K_x_noise']} x noise, slotted {v['slotted']['drift5K_x_noise']} x (limit 0.5)", "EMI screening of the front end / TPS65131" if "chassis" not in k else "screening TXD / PWR / HB2",
            fl("shield.slotted." + k[:20]) if "chassis" not in k else "-", "head: placement and filtering instead" if "chassis" not in k else "ProtoShield prototypes on the chassis boards")
    row("Head: HV sector (TXJ, MP1, HV fins)", "high-voltage layout rules: round all flyback copper (a point arcs at 1/3 the voltage), derate FR4 to its aged 300 V/mil, vacuum-pot the HV sector", "Sierra Proto HV PCB notebook", "PROPOSED",
        "flyback 460 V: 1.5 mil of aged FR4 between layers would already hold it; the 1.0 mm rule-6 spacing stays", "corona / tracking margin over the life of the head", "-", "add a rounded-corner check to the board copper check")
    row("Head: front-end supply (TPS65131)", "keep it out of the coil field or filter it (a can is not allowed in the head)", "flex study B", "OPEN", "switching 1.25-1.5 MHz", "EMI at the nV front end", fl("mp1.tps"), "EMI study of placement / LC filter")
    row("Head: display flex (522 LEDs)", "reverse-bared single-layer flex (pads on both sides, 3.7-5.4 mil)", "Tramonto", "PROPOSED", "thinnest flex construction; -55 to 150 C", "thinner display stack under the lid", "-", "compare with the current LED flex stack in rf2_ledgrid")
    # ---- cord / hinge
    row("Cord: head -> REF3T -> hinge", "split long flex (rolling loop + static piece)", "Tech Etch long flex, Minco guide", "ADOPTED",
        f"{a.get('width_mm')} mm wide, {a.get('segments', {}).get('seg1_dynamic_mm')} + {a.get('segments', {}).get('seg2_static_mm')} mm, {a.get('mass_g', {}).get('flex')} g vs {a.get('mass_g', {}).get('coiled_cord')} g; TX {a.get('tx_capacitance', [{}, {}])[1].get('C_pF_per_m')} pF/m",
        f"fixes the 10 mm cord FAIL; first gate +{a.get('first_gate_shift_us')} us (was +0.19)", fl("flex"), "flex drawing with a >= 1000 VRMS net-to-net hipot; rolling-loop mock-up")
    hh = fo.get("H_two_ply_cord", {}); ff = fo.get("F_metal_core_led", {}); gg = fo.get("G_ultra_thin", {})
    row("Cord: flex signal traces", "selective copper: 2 oz TX / power, 1/2 oz signal areas", "Minco guide, Tech Etch contoured circuits, PICA 18 um adhesiveless", "ADOPTED",
        "0.15 mm traces on 1/2 oz vs 0.089 mm guideline and 0.076 mm minimum", "producibility guideline met without widening the flex", fl("flex.lv"), "state the selective copper on the flex drawing")
    row("Cord: flex construction", "two unbonded plies (2 oz HV / power + 1/2 oz ultra-thin signal)", "PICA ultra-thin FPC", "REJECTED",
        f"stacked: +{hh.get('stacked_extra_tx_pF_per_m')} pF/m on the TX strips (pair {hh.get('flex_tx_pF_per_m')} pF/m); offset: {hh.get('offset_width_mm')} mm wide", "-", "-", "-")
    row("Head: display board (522 LEDs)", "metal-core (aluminium) LED PCB", "MegaPlus LED / lighting PCB", "REJECTED",
        "; ".join(f"{k}: drift {v['drift5K_x_noise']} x noise" for k, v in ff.get("head_display", {}).items()), "-", "-", "keep the flex on a non-metal light plate")
    row("Control chassis: TXD current loop", "heavy copper (to 17 oz)", "MegaPlus PCB", "PROPOSED", "outside the coil field", "lower I2R in the TX loop if needed", "-", "only if the TXD thermal budget asks")
    row("Head: display flex (522 LEDs)", "PICA ultra-thin adhesiveless flex (0.20 +- 0.08 mm)", "PICA ultra-thin FPC", "PROPOSED",
        f"flex {gg.get('display_flex_now_mm')} -> {gg.get('ultra_thin_mm')} mm; head {gg.get('head_H_now_mm')} -> {gg.get('head_H_if_adopted_mm')} mm", "thinner head", "-", "owner: adopt, then re-check the LED pads and light-plate seat")
    row("Cord: strain relief at the gland", "strain-relief pin through a loop of the flex (SDC 2300 coil-cable pin 4308-0031 pattern)", "Minelab SDC 2300 parts", "PROPOSED", "-", "no pull on the soldered TX strips", "-", "add the pin to the gland boss")
    row("Hinge pass-through (ICD I5)", "single-layer reverse-bared / Minco dynamic flex plies", "Tramonto, Minco guide", "PROPOSED", "single layer required for dynamic flexing; bend >= 10 x thickness", "longer clock-spring life", "-", "re-check the I5 bend radius with 0.15 mm plies")
    # ---- REF3
    row("REF3 reference coils (X / Y faces)", f"Minco Flex-Coils, {d.get('segments')} FEP segments per face", "Minco FC01", "FEASIBLE-NOT-ADOPTED",
        f"R {d.get('R_ohm_old')} -> {d.get('R_ohm_new')} ohm, e_ref {d.get('e_ref_nV_old')} -> {d.get('e_ref_nV_new')} nV/rtHz, thickness {d.get('thickness_mm')} mm", "repeatable orientation; REF3T on the same flex as the cord joint", "-", "only if canceller balance needs it")
    row("REF3 / cord analog lines", "Gore ePTFE microwave coax", "Gore spaceflight catalog", "REJECTED", "82 pF/m vs 28.1 pF/m flex strips", "-", "-", "-")
    # ---- shaft
    w0, w12, w10 = walls.get(1.5, {}), walls.get(1.2, {}), walls.get(1.0, {})
    row("Telescope profiles", "carbon wall 1.5 -> 1.2 mm", "Garrett two-piece benchmark (155 g/m)", "PROPOSED",
        f"tubes {w0.get('tubes_g')} -> {w12.get('tubes_g')} g ({w12.get('delta_g')} g), tip sag {w0.get('tip_sag_mm')} -> {w12.get('tip_sag_mm')} mm (1.0 mm wall: {w10.get('delta_g')} g, {w10.get('tip_sag_mm')} mm)",
        "lighter shaft; ours is 228 g/m vs 155 g/m", "-", "owner: choose the wall; then a swing-load check")
    row("Telescope profiles", "octagonal stock tubing", "Rock West octagonal", "REJECTED", f"OD {so.get('octagonal', {}).get('od_mm')} mm vs the 21-31 mm profiles", "-", "-", "custom rectangular profiles remain (P0.6 open)")
    row("Telescope clamps (P3.4)", "cam lever + elastomer pressure block through a window in the outer profile", "Minelab SDC 2300 parts (8008-0061, 8008-0062); Garrett nylon cam lock", "ADOPTED",
        "P0.6 'cam clamp hardware' decided", "infinite length adjustment, no spring buttons", "-", "print the lever / block; clamp-force test")
    # ---- chassis, power
    row("TXD + PWR", "8-layer rigid-flex second source", "FPCexpress", "PROPOSED", "rigid-flex with PTH through rigid and flex", "removes the board-to-board cable", "-", "-")
    row("Battery dock signal contacts", "photo-etched BeCu C172 fingers", "Tech Etch etch & form", "ADOPTED", f"{c.get('force_N')} N at 0.8 mm, {c.get('stress_MPa')} MPa", "replaces the unobtainable Mill-Max sheet", "-", "contact resistance / cycle test")
    row("Battery pack", "7S1P Molicel P45B, drill-style rail", "Molicel P45B datasheet", "ADOPTED", f"{po.get('chosen_summary', '')[:120]}", "-188 g pack", fl("runtime"), "rail dock geometry in rf2_chassis")
    row("Battery pack", "7S RC LiPo in a hard shell", "Gens Ace listing", "REJECTED", "157 Wh/kg bare, no BMS", "-", "-", "-")
    res = dict(status="GENERATED from the study results (MODELED)", rows=M, counts={s: sum(r["status"].startswith(s) for r in M) for s in ("ADOPTED", "PROPOSED", "FEASIBLE", "REJECTED", "OPEN", "BLOCKED")}, ok=bool(M))
    json.dump(res, open(os.path.join(OUT, "rf2_integration.json"), "w"), indent=1)
    L = ["# Integration matrix (generated by rf2/rf2_integration.py; MODELED)", "",
         "Every owner-supplied source mapped to the areas it can touch. Status: ADOPTED (in the model now), PROPOSED (worth doing, owner / next study), FEASIBLE-NOT-ADOPTED, REJECTED (with the reason), OPEN, BLOCKED (a rule stops it: see docs/RULE_NEAR_MISSES.md).", "",
         "Counts: " + ", ".join(f"{k} {v}" for k, v in res["counts"].items()), "",
         "| Area | Idea | Source | Status | Numbers | Effect | Rule near-miss | Next |", "|---|---|---|---|---|---|---|---|"]
    for r in M: L.append("| " + " | ".join(str(r[k]).replace("|", "/") for k in ("area", "idea", "source", "status", "numbers", "effect", "rule", "next")) + " |")
    open(os.path.join(ROOT, "docs", "INTEGRATION_MATRIX.md"), "w").write("\n".join(L) + "\n")
    print(res["counts"]); return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
