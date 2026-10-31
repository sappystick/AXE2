#!/usr/bin/env python3
"""RF2 rule near-miss report (2026-10-30, owner: 'where a component fits right under it but the rule blocks it, note that and mention it every time, so we
can decide whether to remove or relax a rule'). GENERATED every run.

Each rule: a measured value from a results file, its limit, the direction, and its kind:
  safety  - never relaxed automatically (HV rule 6, eddy rule 5, part absolute-maximum ratings): reported only
  target  - a design target or an ASSUMED derating; the owner may relax or remove it
Status per rule:
  BLOCKED  - fails by <= 10 % of the limit (a part that 'fits right under it'): the owner decides
  FAIL     - fails by more than 10 %
  EDGE     - passes with <= 5 % headroom
  RELAXED  - the owner relaxed the rule; the value is shown against the old limit every run
  PASS     - passes with more headroom
Writes docs/RULE_NEAR_MISSES.md and rf2/results/rf2_rules.json.   usage: python3 rf2/rf2_rules.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
BLOCK, EDGE = 0.10, 0.05

def J(*p):
    f = os.path.join(ROOT, *p)
    return json.load(open(f)) if os.path.exists(f) else None

def rules():
    R = []
    def add(rid, kind, desc, value, limit, sense, src, relaxed=None, unit=""):
        R.append(dict(id=rid, kind=kind, desc=desc, value=value, limit=limit, sense=sense, unit=unit, source=src, relaxed=relaxed))
    sy = J("rf2", "results", "rf2_system.json")
    if sy:
        rt = sy["runtime"]
        add("runtime.boost", "target", f"continuous-boost runtime (trigger held: the rated case), {rt['pack']}", rt["boost_continuous_h"], 6.0, ">=", "rf2_system.json runtime", relaxed="owner 2026-10-30: 6 h target relaxed; P45B 7S1P chosen", unit="h")
        add("runtime.scan", "target", f"scan runtime, {rt['pack']}", rt["scan_h"], 6.0, ">=", "rf2_system.json runtime", relaxed="owner 2026-10-30: 6 h target relaxed", unit="h")
        th = sy["thermal"]
        add("thermal.txd_tj", "target", "TXD switch junction in continuous boost (125 C design limit; 150 C abs max)", th["txd_switch_TJ_C"], 125.0, "<=", "rf2_system.json thermal", unit="C")
        add("thermal.chassis_rise", "target", "chassis surface rise in continuous boost (natural convection ASSUMED)", th["chassis_surface_rise_K"], 15.0, "<=", "rf2_system.json thermal", unit="K")
        add("thermal.pack_W", "target", "pack dissipation in continuous boost", th["pack_W_boost"], 3.0, "<=", "rf2_system.json thermal", unit="W")
    co = J("rf2", "results", "rf2_continuous.json")
    if co:
        for m in co["modes"]:
            for r in m["rows"]:
                if r.get("rating") and r.get("margin"):
                    safe = "peak" in r["part"] or "junction" in r["part"] or "avalanche" in r["part"] or "rule 6" in (r.get("note") or "")
                    add(f"cont.{m['mode'][:5]}.{r['part'][:40]}", "safety" if safe else "target", f"{m['mode']}: {r['part']}", r["load"], r["rating"], "<=", "rf2_continuous.json", unit=r["unit"])
    # ---- adopted drive and cord upgrades (owner 2026-10-31, HANDOFF section 56)
    ts = J("rf2", "results", "rf2_txd_spice.json")
    if ts:
        lim = ts["limits"]
        add("txd.vds_q1", "safety", "TXD ngspice: Q1 peak VDS (worst case) vs 80 % of VDSS (NTBG080N120SC1 1200 V)", max(c["vds_q1_max_V"] for c in ts["cases"].values()), lim["vds_max_V"], "<=", "rf2_txd_spice.json", unit="V")
        add("txd.vds_q2", "safety", "TXD ngspice: Q2 (freewheel) peak VDS vs 80 % of VDSS", max(c["vds_q2_max_V"] for c in ts["cases"].values()), lim["vds_max_V"], "<=", "rf2_txd_spice.json", unit="V")
        add("txd.i_peak", "safety", "TXD ngspice: peak coil / switch current vs 80 % of IDM 110 A", max(c["i_peak_A"] for c in ts["cases"].values()), lim["i_peak_max_A"], "<=", "rf2_txd_spice.json", unit="A")
        add("txd.fall", "target", "TXD ngspice: boost fall time vs 1.3 x ideal L I / V", ts["cases"]["boost_long_cutoff"]["fall_us"], 1.3 * ts["cases"]["boost_long_cutoff"]["fall_ideal_us"], "<=", "rf2_txd_spice.json", unit="us")
    ch = J("rf2", "chassis_out", "rf2_chassis_check.json")
    if ch and "cord_flex" in ch["checks"]:
        cf = ch["checks"]["cord_flex"]
        if "width_limit_mm" in cf:
            add("cord.width_piece1", "target", "cord flex piece 1 width (TX strips + REF guard) vs the inner bore less 2 mm (18.6 - 2)", cf["width_mm"], cf["width_limit_mm"], "<=", "rf2_chassis_check.json cord_flex", unit="mm")
            add("cord.width_piece2", "target", "cord flex piece 2 width vs the middle bore less 2 mm", cf["piece2_width_mm"], cf["piece2_limit_mm"], "<=", "rf2_chassis_check.json cord_flex", unit="mm")
            add("cord.rolling_loop", "target", "cord flex rolling loop 2 x bend radius vs the inner bore less 4 mm", cf["rolling_loop_2R_mm"], cf["rolling_loop_limit_mm"], "<=", "rf2_chassis_check.json cord_flex", unit="mm")
            add("cord.rule6_gap", "safety", "rule 6: smallest gap next to an HV trace in the cord flex (pieces 1 and 2) vs 1.0 mm", min(cf["rule6_min_gap_mm"]), 1.0, ">=", "rf2_chassis_check.json cord_flex (measured from the lanes)", unit="mm")
    co2 = J("rf2", "results", "rf2_continuous.json")
    if co2:
        sys.path.insert(0, HERE); import rf2_cordflex as CFX
        b_ = next(m for m in co2["modes"] if m["mode"].startswith("boost"))
        add("cord.tx_width_ipc", "target", "cord TX strip width vs the IPC-2221 width (2 oz internal, 10 K) at the rf2_continuous boost rms", round(CFX.W_TX, 3), round(CFX.ipc2221_width_mm(b_["I_rms_coil"]), 3), ">=", "rf2_cordflex / rf2_continuous.json", unit="mm")
    if sy and "txd_min_use" in sy.get("echoes", {}):
        e = sy["echoes"]
        add("txd.echo_nominal", "target", f"TXD pod metal echo drift (5 K) at s {e['txd_at_s_mm']:.0f} (nominal length) vs 0.5 x gate noise", e["txd_drift5K_x_noise"], 0.5, "<=", "rf2_system.json echoes", unit="x noise")
        add("txd.echo_min_use", "target", f"TXD pod metal echo drift (5 K) at s {e['txd_min_use']['s_mm']:.0f} (shortest use length, pod rides the telescope) vs 0.5 x gate noise", e["txd_min_use"]["drift5K_x_noise"], 0.5, "<=", "rf2_system.json echoes", unit="x noise")
        th = sy["thermal"]
        add("thermal.txd_pod_rise", "target", "TXD pod housing surface rise in continuous boost (Q1 heat sink vented; natural convection 8 W/m2K ASSUMED)", th["txd_pod_surface_rise_K"], 15.0, "<=", "rf2_system.json thermal", unit="K")
        add("harness.feed_drop", "target", "pack -> TXD pod feed drop in boost vs 2 % of 25.2 V", sy["harness"]["vin_drop_V_boost"], 0.02 * 25.2, "<=", "rf2_system.json harness", unit="V")
    ic = J("rf2", "results", "rf2_icd.json")
    for r_ in (ic or {}).get("gland_y5b", []):
        tag = r_["connector"].split(" ")[0]
        if r_["i_per_pin_A"]:
            add(f"icd.y5b_i.{tag}", "target", f"head gland Y5B ZIF {r_['connector']}: VIN_H current per pin vs 0.5 A", r_["i_per_pin_A"], r_["i_rating_A"], "<=", "rf2_icd.json gland_y5b (Panasonic ACCTB1E)", unit="A")
            add(f"icd.y5b_v.{tag}", "safety", f"head gland Y5B ZIF {r_['connector']}: VIN_H 29.4 V vs 50 V rated", r_["v_max_V"], r_["v_rating_V"], "<=", "rf2_icd.json gland_y5b (Panasonic ACCTB1E)", unit="V")
    mc = J("rf2", "head", "out", "rf2_mp1v2_close.json")
    if mc and mc.get("parts_closure"):
        pc = mc["parts_closure"]
        add("mp1.settle", "target", "MP1 v2 worst settling vs the first gate with the cord", pc["worst_settle_us"], mc["first_gate_us"], "<=", "rf2_mp1v2_close.json parts_closure", unit="us")
        add("mp1.lmh_in", "safety", "LMH6629 input current (worst case)", max(r["peak_lmh_input_mA"] for r in pc["runs"]), 10.0, "<=", "rf2_mp1v2_close.json", unit="mA")
        add("mp1.bat54_vrrm", "target", "BAT54 reverse voltage (clamp-rail span) vs 80 % of VRRM 30 V", pc["clamp_rail_span_V"], 0.8 * 30.0, "<=", "rf2_mp1v2_close.json", unit="V")
        add("mp1.switch_pin", "safety", "TMUX7212 pin voltage vs VDD (keep inside the supply; abs max VDD + 0.5 V)", max(r["peak_clamp_node_V"] for r in pc["runs"]), pc["switch_supplies_V"][1], "<=", "rf2_mp1v2_close.json", unit="V")
        add("mp1.tps_vpos", "target", "TPS65131 VPOS setting vs its ROC maximum 15 V", pc["switch_supplies_V"][1], 15.0, "<=", "DATASHEET_LOG RF2-DS-MP1V2-SWITCH", unit="V")
        add("mp1.noise", "target", "MP1 v2 input noise per leg vs the 1.7 nV/rtHz target", mc["chosen"]["noise_nV"], 1.7, "<=", "rf2_mp1v2_close.json chosen", unit="nV/rtHz")
    pr = J("rf2", "results", "rf2_print.json")
    if pr:
        for k, v in pr["parts"].items():
            if "wall_p2_mm" in v:
                add(f"dfm.wall.{k[:30]}", "target", f"{k}: wall 2nd percentile vs 0.96 mm (FDM ASSUMED)", v["wall_p2_mm"], 0.96, ">=", "rf2_print.json", unit="mm")
                add(f"dfm.thin.{k[:30]}", "target", f"{k}: area below 1.2 mm vs 3 %", round(100 * v["thin_fraction"], 1), 3.0, "<=", "rf2_print.json", unit="%")
    po = J("rf2", "results", "rf2_pack_options.json")
    if po:
        for o in po["options"]:
            if o.get("cell_current_frac_of_rating") is not None:
                add(f"pack.cell_i.{o['key']}", "safety", f"pack option {o['key']}: cell current in boost at cut-off vs its coldest-band continuous rating", o["cell_current_frac_of_rating"], 1.0, "<=", "rf2_pack_options.json", unit="x rating")
    wo = J("rf2", "results", "rf2_wire_options.json")
    if wo:
        for c in wo["coil_blocked_by_rule6_within_10pct"][:2]:
            add(f"wire.coil.{c['part']}", "safety", f"coil litz {c['part']} ({c['kind']} {c['ins']}, OD {c['od_mm']} mm, {c['R_coil_20C']} ohm: fits the current comb) insulation rating vs rule 6", c["v_rating"], 630.0, ">=", "Rubadue catalog (rf2_wire_options)", unit="V")
        # the round coil cord was replaced by the cord flex (owner 2026-10-30): its wire / packing rows are kept in rf2_wire_options.json as the record, not as live rules
    fo = J("rf2", "results", "rf2_flex_options.json")
    if fo:
        a = fo["A_cord_to_flex"]
        add("flex.seg1_len", "target", "cord-as-flex segment 1 (head -> REF3T, rolling loop) vs Tech Etch preferred length", a["segments"]["seg1_dynamic_mm"], a["te_limit_mm"]["preferred"], "<=", "Tech Etch long flex brochure", unit="mm")
        add("flex.one_piece", "target", "cord-as-flex in one piece (no REF3T joint) vs Tech Etch preferred length (advanced 1524 mm)", a["one_piece_mm"], a["te_limit_mm"]["preferred"], "<=", "Tech Etch long flex brochure", unit="mm")
        add("flex.width", "target", "cord-as-flex width vs the 18 mm bore less 2 mm", a["width_mm"], a["bore_mm"] - 2.0, "<=", "rf2_flex_options.json", unit="mm")
        mi = a.get("minco")
        if mi:
            add("flex.cover_aged", "safety", "cord-flex 1 mil Kapton coverlay, AGED breakdown (2000 V/mil, Sierra HV notebook) vs the 460 V flyback x 2 (630 V rule basis)", fo["A_cord_to_flex"]["minco"]["cover_breakdown_V"], 2 * 630.0, ">=", "Sierra Proto HV notebook 2004 / Minco 2019", unit="V")
            add("flex.withstand", "safety", "cord-flex insulation: Minco typical withstand (1000 VRMS 30 s) vs the rule-6 630 V (drawing hipot required)", mi["withstand_VRMS"], 630.0, ">=", "Minco design guide 2019", unit="V")
            add("flex.lv_min_w", "target", "cord-flex LV traces vs Minco minimum width on their copper (1/2 oz, selective)", 0.15, mi["min_w_2oz_mm"], ">=", "Minco design guide 2019", unit="mm")
            add("flex.lv_producibility", "target", "cord-flex LV traces vs Minco producibility guideline (width >= 5 x copper thickness; 1/2 oz selective copper)", 0.15, mi["producibility_w_mm"], ">=", "Minco design guide 2019", unit="mm")
            add("flex.one_piece_minco", "target", "cord-flex in one piece vs Minco maximum length (5 ft)", a["one_piece_mm"], mi["len_max_mm"], "<=", "Minco design guide 2019", unit="mm")
        for k, v in fo["B_shield_can"]["places"].items():
            add(f"shield.slotted.{k[:20]}", "target", f"slotted etched shield can in the head, {k}: drift vs 0.5 x gate noise", v["slotted"]["drift5K_x_noise"], 0.5, "<=", "rf2_flex_options.json", unit="x noise")
    fd = J("rf2", "results", "rf2_fold_options.json")
    if fd:
        for o in fd["rows"]:
            if o["mechanism"].startswith("telescope") or o["profile"] not in ("square31", "hex31 hub6_cu"): continue
            for r in o["rule_rows"]:
                add(f"opt.fold.{o['mechanism'][:14]}.{o['profile']}.{r['rule'][:20]}", "target", f"fold option {o['mechanism']}, {o['profile']}: {r['rule']}", r["value"], r["limit"], r["sense"], "rf2_fold_options.json")
    lh = J("rf2", "results", "rf2_lowL_options.json")
    for h in (lh or {}).get("hybrid", []):
        for r in h.get("rule_rows", []):
            if r["ok"] and "width" not in r["rule"]: pass
            add(f"opt.hybrid.{h['N']}x{h['p']}.{h['switch'][:4]}{'.TXD400' if h['txd_at_400mm'] else ''}.{r['rule'][:20]}", "safety" if ("IDM" in r["rule"] or "TJ" in r["rule"]) else "target",
                f"hybrid RX option {h['N']}x{h['p']} {h['switch'][:4]}{' TXD400' if h['txd_at_400mm'] else ''}: {r['rule']}", r["value"], r["limit"], "<=", "rf2_lowL_options.json hybrid")
    for fn, tag in (("rf2_lowL_options.json", "lowL"), ("rf2_shaftlink_options.json", "shaft")):
        d = J("rf2", "results", fn)
        if not d: continue
        rows = []
        if tag == "lowL":
            for o in d["options"]:
                if o["N"] == 26 and not o["sep_rx"] and not o["txd_at_400mm"] and o["switch"] == "C3M0280090J": continue        # the baseline is already in rf2_continuous
                name = f"{o['N']}x{o['p']} {o['switch'][:4]}" + ((" +RX" + str(o["sep_rx"])[:2]) if o["sep_rx"] else "") + (" TXD400" if o["txd_at_400mm"] else "") + (" TX2L" if o.get("tx_strips_2layer") else "")
                rows += [(f"opt.lowL.{name}.{r['rule'][:24]}", f"option {name}: {r['rule']}", r) for r in o["rule_rows"]]
        else:
            rows = [(f"opt.shaft.{r['rule'][:30]}", r["rule"], r) for r in d["rule_rows"]]
        for rid, desc, r in rows:
            sense = r.get("sense", ">=" if "VDS" in r["rule"] else "<=")
            add(rid, "safety" if ("IDM" in r["rule"] or "rule 6" in r["rule"] or "TJ" in r["rule"]) else "target", desc, r["value"], r["limit"], sense, fn, unit="")
    return R

def status(r):
    v, L = float(r["value"]), float(r["limit"]); s = 1 if r["sense"] == "<=" else -1
    over = s * (v - L) / abs(L) if L else 0.0                                         # > 0: fails by this fraction of the limit
    if r["relaxed"]: st = "RELAXED"
    elif over > BLOCK: st = "FAIL"
    elif over > 0: st = "BLOCKED"
    elif over > -EDGE: st = "EDGE"
    else: st = "PASS"
    return st, round(100 * over, 1)

def main():
    R = rules()
    for r in R: r["status"], r["over_pct"] = status(r)
    flag = [r for r in R if r["status"] in ("BLOCKED", "RELAXED", "EDGE", "FAIL")]
    res = dict(status="GENERATED from results files each run", n_rules=len(R), counts={s: sum(r["status"] == s for r in R) for s in ("BLOCKED", "RELAXED", "EDGE", "FAIL", "PASS")}, flagged=flag, rules=R)
    res["ok"] = bool(R)
    json.dump(res, open(os.path.join(OUT, "rf2_rules.json"), "w"), indent=1)
    order = {"BLOCKED": 0, "FAIL": 1, "RELAXED": 2, "EDGE": 3}
    L = ["# Rule near-misses (generated by rf2/rf2_rules.py; read this every report)", "",
         "BLOCKED: a part fails a rule by 10 % or less (it fits right under it); the owner decides whether to relax or remove the rule. "
         "RELAXED: the owner relaxed it; shown against the old limit every run. EDGE: passes with 5 % headroom or less. FAIL: misses by more than 10 %. "
         "Safety rules (HV, eddy, absolute-maximum ratings) are never relaxed automatically.", "",
         f"Rules checked: {len(R)}. " + ", ".join(f"{k} {v}" for k, v in res["counts"].items()), "",
         "| Status | Kind | Rule | Value | Limit | Over (+) / headroom (-) | Note |", "|---|---|---|---|---|---|---|"]
    for r in sorted(flag, key=lambda r: (order[r["status"]], -r["over_pct"])):
        L.append(f"| **{r['status']}** | {r['kind']} | {r['desc']} | {r['value']} {r['unit']} | {r['sense']} {r['limit']} {r['unit']} | {r['over_pct']:+.1f} % | {r['relaxed'] or r['source']} |")
    open(os.path.join(ROOT, "docs", "RULE_NEAR_MISSES.md"), "w").write("\n".join(L) + "\n")
    for r in flag: print(r["status"], r["id"], r["value"], r["sense"], r["limit"], r["over_pct"])
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
