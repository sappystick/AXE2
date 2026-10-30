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
                    add(f"cont.{m['mode'][:5]}.{r['part'][:40]}", "safety" if "peak" in r["part"] or "junction" in r["part"] else "target", f"{m['mode']}: {r['part']}", r["load"], r["rating"], "<=", "rf2_continuous.json", unit=r["unit"])
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
        for k, v in fo["B_shield_can"]["places"].items():
            add(f"shield.slotted.{k[:20]}", "target", f"slotted etched shield can in the head, {k}: drift vs 0.5 x gate noise", v["slotted"]["drift5K_x_noise"], 0.5, "<=", "rf2_flex_options.json", unit="x noise")
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
