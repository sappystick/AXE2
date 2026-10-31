#!/usr/bin/env python3
"""RF2 component selection by weighted factors (owner, 2026-10-31: 'base upgrade decisions on a list of selective factors - weight, ratings, fewer
attachments / offshoots, signal quality, footprint - and automatically select the parts that beat what we have and benefit the whole system'). MODELED.

For every slot (a component role) the incumbent and its candidates carry the same attributes:
  mass_g (lower better)            runtime_h  (continuous boost, the rated case; higher better; from rf2_continuous with the part's resistance)
  signal (slot-specific: first gate us for the TX switch, lower better; noise / capacitance where modelled)
  margin (rating / stress, e.g. V rating / 460 V flyback, I rating / peak; higher better; credit stops at 2 x: enough margin is enough)
  attach (extra parts or offshoots the candidate needs beyond the incumbent's set; lower better)
  footprint_mm2 or volume (lower better)      verify (1 datasheet VERIFIED, 0.7 a value ASSUMED, 0.5 draft / vendor page, 0.3 UNVERIFIED)
Rule checks (owner 2026-10-31: nothing is excluded because of a rule): every candidate is scored and listed; a candidate that breaks a rule (rule 6 >= 630 V
on flyback parts, rule 5 / no metal in the head, absolute-maximum ratings, fit, ampacity, flex bend, sag) is marked BREAKS with the rule, by how much, and
WHERE in the machine it would sit, so the owner can decide; nothing with a break is adopted automatically.
Score per factor = candidate / incumbent (or incumbent / candidate when lower is better), clipped to 0.25-2; mass is scored on the whole machine
(M / (M + delta), M = the chassis mass total), so a few grams on a small part cannot dominate; the slot score is the weighted mean over the
factors the slot has. RECOMMEND when the score is >= 1.05 and verify >= 0.6 (a rule break is shown next to it, never hidden). The weights are the owner's to tune (WEIGHTS).
Writes docs/COMPONENT_SELECTION.md and rf2/results/rf2_select.json.   usage: python3 rf2/rf2_select.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
WEIGHTS = dict(mass_g=0.20, runtime_h=0.20, signal=0.20, margin=0.15, attach=0.10, footprint=0.10, verify=0.05)
LOWER_BETTER = {"mass_g", "signal", "attach", "footprint"}
RECOMMEND_AT = 1.05; V_FLY = 460.0
def J(*p):
    f = os.path.join(ROOT, *p); return json.load(open(f)) if os.path.exists(f) else {}

def runtime_with(rds_hot=None, r_coil=None, r_cable=None):
    """continuous-boost and scan runtime with changed loop resistances (rf2_continuous model, regenerative clamp case)"""
    import rf2_continuous as C
    keep = (C.RDS_HOT, C.R_COIL, C.R_CABLE, C.R_LOOP)
    try:
        if rds_hot is not None: C.RDS_HOT = rds_hot
        if r_coil is not None: C.R_COIL = r_coil
        if r_cable is not None: C.R_CABLE = r_cable
        C.R_LOOP = C.R_COIL + C.R_CABLE + C.RDS_HOT + C.R_SHUNT
        sy = J("rf2", "results", "rf2_system.json")["runtime"]; wh = sy["usable_Wh"]
        base = {m["mode"]: m for m in J("rf2", "results", "rf2_continuous.json")["modes"]}
        out = {}
        for mode, I in C.MODES.items():
            r = C.analyse(mode, I); k = "regenerative clamp (75 % recovery ASSUMED)"
            p_new = r["battery"][k]["P_total_W"]; p_old = base[mode]["battery"][k]["P_total_W"]
            p_sys_old = wh / (sy["boost_continuous_h"] if mode.startswith("boost") else sy["scan_h"])
            out["boost" if mode.startswith("boost") else "scan"] = round(wh / (p_sys_old + (p_new - p_old)), 2)
        return out
    finally:
        C.RDS_HOT, C.R_COIL, C.R_CABLE, C.R_LOOP = keep

def gate_from_node(node_pF):
    cs = sorted((c["node_pF"], c["first_gate_us"]) for c in J("rf2", "results", "rf2_switch.json")["cases"])
    return round(float(np.interp(node_pF, [a for a, _ in cs], [b for _, b in cs])), 2)

def slots():
    S = {}
    # ---- TX switch (Q1 and Q2 of the TXD)
    node0 = 292.0                                                                               # C3M Coss 110 pF + winding + 50 (rf2_switch)
    def sw(name, v_rating, rds_hot, coss26, fp, mass, attach, verify, note, n=1):
        node = node0 - 110 + coss26 * n; rt = runtime_with(rds_hot=rds_hot / n)
        return dict(name=name, mass_g=mass * n, runtime_h=rt["boost"], scan_h=rt["scan"], signal=gate_from_node(node), margin=round(v_rating / V_FLY, 2), attach=attach, footprint=fp * n,
                    verify=verify, hard=dict(rule6=v_rating >= 630), note=note, units=dict(signal="first gate us"))
    S["TX switch (TXD Q1 / Q2)"] = [
        sw("Wolfspeed C3M0280090J (SiC, D2PAK-7)", 900, 0.416 * 1.1, 110, 158, 1.5, 0, 1.0, "incumbent; RDS 416 mohm at 150 C (+10 %)"),
        sw("Infineon IPB65R095C7 (Si CoolMOS, D2PAK)", 650, 0.202 * 1.1, 400, 158, 1.5, 0, 1.0, "RDS 202 mohm typ at 150 C (logged); Coss about 400 pF at 26 V (cliff at the tail voltage)"),
        sw("GaN Systems GS-065-011-1-L (GaN, PDFN 5x6)", 650, 0.150 * 2.0, 125, 30, 0.2, 1, 0.7, "RDS 150 mohm at 25 C, x2 hot ASSUMED; 0-6 V gate (driver change); no avalanche rating"),
        sw("2 x C3M0280090J in parallel", 900, 0.416 * 1.1, 110, 158, 1.5, 1, 1.0, "half the resistance, twice the Coss", n=2)]
    # ---- coil litz (rf2_wire_options candidates that fit the comb and the band)
    wo = J("rf2", "results", "rf2_wire_options.json"); inc = wo.get("coil_best_rule6_ok_in_comb", {}); slot = wo.get("coil", {}).get("comb_slot_mm", 1.47)
    lit = []
    allc = sorted(wo.get("candidates", []), key=lambda c: c["R_coil_20C"]); r_inc = inc.get("R_coil_20C", 9)
    pick = allc[:6] + [c for c in allc if c not in allc[:6] and (c["part"] == inc.get("part") or (c["fits_comb"] and c["R_coil_20C"] < r_inc))]
    for c in pick:                                                                                   # the lowest-resistance constructions + every one that fits with less resistance, whatever rule they break
        rt = runtime_with(r_coil=c["R_coil_20C"])
        lit.append(dict(name=f"Rubadue {c['part']} ({c['kind']} {c['ins']}, OD {c['od_mm']} mm)", mass_g=c["coil_wire_g"], runtime_h=rt["boost"], scan_h=rt["scan"], signal=None,
                        margin=round(c["v_rating"] / V_FLY, 2), attach=0, footprint=round(c["od_mm"] ** 2, 3), verify=0.9, hard=dict(rule6=c["rule6_ok"], fit=c["od_mm"] <= slot - 0.05, freq=c["freq_ok"]), od_mm=c["od_mm"], slot_mm=slot, f_band=c["f_band"],
                        note=f"{c['R_coil_20C']} ohm, {c['f_band']}", incumbent=(c["part"] == inc.get("part")), v_rating=c["v_rating"]))
    lit.sort(key=lambda r: not r.get("incumbent")); S["Coil litz (26 turns)"] = lit
    # ---- cord-flex TX copper
    import rf2_cordflex as CF
    def cu(oz, label, attach, verify):
        t_cu = 0.0014 * 25.4 * oz; r = 2 * 0.017241 * CF.TX_LEN_M / (CF.W_TX * t_cu); stack = CF.STACK_MM + (t_cu - CF.CU_T_MM[2.0])
        rt = runtime_with(r_cable=r); m = 2 * CF.W_TX * t_cu * CF.TX_LEN_M * 1000 * 8.96e-3
        return dict(name=label, mass_g=round(m, 1), runtime_h=rt["boost"], scan_h=rt["scan"], signal=None, margin=round(CF.BEND_R / stack / 10.0, 2), attach=attach, footprint=round(CF.WIDTH * stack, 2),
                    verify=verify, hard=dict(bend=CF.BEND_R / stack >= 10.0, ampacity=CF.ipc2221_width_mm(CF.I_TX, oz=oz) <= CF.W_TX + 1e-9), note=f"TX loop {r:.3f} ohm; loop bend {CF.BEND_R / stack:.0f} x stack (Minco >= 10 x)", units=dict(margin="bend ratio / 10"))
    S["Cord-flex TX strip copper"] = [cu(2.0, "2 oz (incumbent)", 0, 1.0), cu(3.0, "3 oz selective on the TX strips", 0, 0.7), cu(1.0, "1 oz (same width)", 0, 1.0)]
    # ---- battery pack (rf2_pack_options rows)
    po = J("rf2", "results", "rf2_pack_options.json"); ver = {"A": 1.0, "B": 1.0, "C1": 1.0, "C2": 1.0, "D1": 0.5, "D2": 0.5, "E": 0.3, "F": 1.0}
    pk = []
    for o in po.get("options", []):
        pk.append(dict(name=f"{o['key']}: {o['desc']}", mass_g=o["system_delta_g"] + 1000, runtime_h=o["boost_h"], scan_h=o["scan_h"], signal=None, margin=o.get("cell_current_frac_of_rating") and round(1 / o["cell_current_frac_of_rating"], 1) or 1.0,
                       attach=0 if o["key"] not in ("E",) else 2, footprint=round(o["pack_mm"][0] * o["pack_mm"][1] * o["pack_mm"][2] / 1000, 1), verify=ver.get(o["key"], 0.5),
                       hard=dict(cell_current=o.get("cell_current_ok", True) is not False), note="mass = system delta + 1000 (relative)", incumbent=(o["key"] == po.get("chosen"))))
    pk.sort(key=lambda r: not r.get("incumbent")); S["Battery pack"] = pk
    # ---- shaft walls
    so = J("rf2", "results", "rf2_shaft_options.json"); cur = so.get("current_wall_mm")
    SAG_ALLOW = 10.0                                                                            # allowable static tip sag, mm (ASSUMED)
    sh = [dict(name=f"{r['wall_mm']} mm carbon wall", mass_g=r["tubes_g"], runtime_h=None, signal=None, margin=round(SAG_ALLOW / r["tip_sag_mm"], 2), attach=0, footprint=None, verify=0.6,
               hard=dict(sag=r["tip_sag_mm"] <= SAG_ALLOW), note=f"tip sag {r['tip_sag_mm']} mm vs {SAG_ALLOW:.0f} mm allowed (ASSUMED); swing / impact NOT modelled", incumbent=(r["wall_mm"] == cur)) for r in so.get("walls", [])]
    sh.sort(key=lambda r: not r.get("incumbent")); S["Telescope wall"] = sh
    # ---- display flex (owner: 0.20 mm SHELVED)
    S["Display flex (522 LEDs)"] = [dict(name="0.40 mm flex (incumbent, kept)", mass_g=None, runtime_h=None, signal=None, margin=1.0, attach=0, footprint=0.40, verify=1.0, hard={}, note="head 16.55 mm"),
                                    dict(name="0.20 mm PICA ultra-thin (SHELVED by owner)", mass_g=None, runtime_h=None, signal=None, margin=0.6, attach=1, footprint=0.20, verify=0.5, hard={}, note="+-0.08 mm tolerance; stiffeners; wider power traces", shelved=True)]
    # ---- clamp / freewheel diode
    S["Clamp / freewheel diode"] = [dict(name="Nexperia / Diodes US3M (1000 V, SMC)", mass_g=0.2, runtime_h=None, signal=23, margin=round(1000 / V_FLY, 2), attach=0, footprint=56, verify=1.0, hard=dict(rule6=True), note="Cd 23 pF at 4 V"),
                                    dict(name="Good-Ark ES3J (600 V, SMC)", mass_g=0.2, runtime_h=None, signal=40, margin=round(600 / V_FLY, 2), attach=0, footprint=56, verify=1.0, hard=dict(rule6=False), note="CJ 40 pF", v_rating=600)]
    # ---- battery-dock signal contacts
    S["Battery-dock signal contacts"] = [dict(name="photo-etched BeCu fingers (incumbent)", mass_g=0.4, runtime_h=None, signal=None, margin=round(1 / 0.39, 2), attach=0, footprint=4 * 2.54 * 10, verify=0.7, hard={}, note="0.63 N, stress 39 % of ASSUMED yield"),
                                         dict(name="Mill-Max 0906 spring pins", mass_g=1.0, runtime_h=None, signal=None, margin=None, attach=1, footprint=4 * 2.54 * 4, verify=0.3, hard={}, note="sheet UNVERIFIED; needs a pin carrier")]
    return S

M_SAT = 2.0
M_SYS = J("rf2", "chassis_out", "rf2_chassis_check.json").get("mass", {}).get("total_g", 2450)
RULES = {"rule6": ("SAFETY rule 6", "flyback insulation >= 630 V"), "rule5": ("SAFETY rule 5", "no closed metal loop / metal target in the head"),
         "cell_current": ("SAFETY abs-max", "cell continuous discharge rating"), "fit": ("fit", "finished OD seats in the comb slot (slot - 0.05 mm)"),
         "ampacity": ("ampacity", "IPC-2221 width for 3.67 A at a 10 K rise"), "freq": ("frequency band", "litz band reaching >= 50 kHz (turn-off spectrum)"), "bend": ("flex life", "rolling-loop bend >= 10 x the stack (Minco)"), "sag": ("stiffness", "static tip sag <= 10 mm (ASSUMED)")}
WHERE = {"TX switch (TXD Q1 / Q2)": "TXD board in the control chassis, on the 460 V flyback node", "Coil litz (26 turns)": "head coil channel (the flyback winding itself)",
         "Cord-flex TX strip copper": "cord flex TX strips, rolling loop inside the telescope", "Battery pack": "battery dock under the control chassis",
         "Telescope wall": "telescope profiles", "Display flex (522 LEDs)": "head lid / display tier", "Clamp / freewheel diode": "TXD board clamp and freewheel paths (460 V flyback node)",
         "Battery-dock signal contacts": "battery dock contact block"}
def breaks(slot, r):
    out = []
    for k, ok in r.get("hard", {}).items():
        if ok: continue
        rule, req = RULES.get(k, (k, ""))
        if k == "rule6" and r.get("v_rating"): how = f"{r['v_rating']:.0f} V vs 630 V, {100 * (1 - r['v_rating'] / 630):.1f} % short"
        elif k == "fit" and r.get("od_mm"): how = f"OD {r['od_mm']} mm vs {r['slot_mm'] - 0.05:.2f} mm max, {r['od_mm'] - (r['slot_mm'] - 0.05):.2f} mm oversize (a new comb / coil layout, rule 12)"
        elif k == "freq" and r.get("f_band"): how = f"band {r['f_band']} (strands too thick for the turn-off spectrum)"
        else: how = r.get("note", "")
        out.append(dict(rule=rule, requirement=req, by=how, where=WHERE.get(slot, slot), safety=rule.startswith("SAFETY")))
    return out
def score(slot, rows):
    inc = rows[0]; out = []
    for r in rows:
        parts = {}
        for k, w in WEIGHTS.items():
            a, b = r.get(k), inc.get(k)
            if a is None or b is None or a == 0 and b == 0: continue
            if k == "attach": s = 1.0 / (1.0 + max(0.0, a - b)) if a >= b else 1.0 + 0.1 * (b - a)
            elif k == "mass_g": s = M_SYS / (M_SYS + (a - b))                                    # mass is scored on the whole machine (2450 g), not the part alone
            elif k == "margin": s = min(a, M_SAT) / min(b, M_SAT)                                # enough margin is enough: credit stops at 2 x the requirement
            elif k in LOWER_BETTER: s = b / a if a else 2.0
            else: s = a / b if b else 2.0
            parts[k] = round(float(min(2.0, max(0.25, s))), 3)
        wsum = sum(WEIGHTS[k] for k in parts); total = round(sum(WEIGHTS[k] * v for k, v in parts.items()) / wsum, 3) if wsum else 1.0
        br = breaks(slot, r)
        status = "INCUMBENT" if r is inc else ("SHELVED" if r.get("shelved") else
                 ("RECOMMEND" if total >= RECOMMEND_AT and r.get("verify", 0) >= 0.6 else ("BETTER, VERIFY FIRST" if total >= RECOMMEND_AT else "KEEP INCUMBENT")))
        if br: status += " - BREAKS " + ", ".join(b["rule"] for b in br)
        out.append(dict(r, factor_scores=parts, score=total, rule_breaks=br, status=status))
    return out

def main():
    S = {k: score(k, v) for k, v in slots().items() if v}
    rec = {k: [r for r in v if r["status"].startswith("RECOMMEND")] for k, v in S.items()}
    best = {k: max(v, key=lambda r: r["score"]) for k, v in rec.items() if v}
    # combined effect of the recommended electrical swaps on runtime (switch + litz + flex copper together)
    combo = {}
    sw = best.get("TX switch (TXD Q1 / Q2)"); li = best.get("Coil litz (26 turns)"); cu = best.get("Cord-flex TX strip copper")
    if sw or li or cu:
        import rf2_cordflex as CF
        rds = {"Infineon": 0.202 * 1.1, "GaN": 0.150 * 2.0, "2 x": 0.416 * 1.1 / 2}.get(next((k for k in ("Infineon", "GaN", "2 x") if sw and sw["name"].startswith(k)), None), None)
        rc = float(li["note"].split()[0]) if li else None
        rcab = float(cu["note"].split()[2]) if cu else None
        combo = dict(parts=[x["name"] for x in (sw, li, cu) if x], breaks=[b for x in (sw, li, cu) if x for b in x["rule_breaks"]], runtime=runtime_with(rds_hot=rds, r_coil=rc, r_cable=rcab))
    sy = J("rf2", "results", "rf2_system.json")["runtime"]
    res = dict(status="MODELED: factor values from the study results and the datasheet log (ASSUMED where marked); weights owner-tunable", weights=WEIGHTS, recommend_at=RECOMMEND_AT,
               baseline_runtime=dict(boost=sy["boost_continuous_h"], scan=sy["scan_h"]), slots=S, best=dict((k, v["name"]) for k, v in best.items()), combined=combo, ok=bool(S))
    json.dump(res, open(os.path.join(OUT, "rf2_select.json"), "w"), indent=1, default=float)
    L = ["# Component selection by weighted factors (generated by rf2/rf2_select.py; MODELED)", "",
         "Each slot's incumbent scores 1.00. A candidate's factor score is its ratio to the incumbent (better > 1, clipped 0.25-2); the slot score is the weighted mean of the factors the slot has. "
         f"RECOMMEND at >= {RECOMMEND_AT:.2f} with verification >= 0.6. **Nothing is excluded because of a rule** (owner, 2026-10-31): a part that breaks a rule is listed and scored like the others, "
         "marked **BREAKS** with the rule, by how much and where it would sit; nothing with a break is adopted automatically. Safety rules are rule 5, rule 6 and absolute-maximum ratings.", "",
         "Weights: " + ", ".join(f"{k} {v:.2f}" for k, v in WEIGHTS.items()) + f". Baseline runtime: {sy['boost_continuous_h']} h boost / {sy['scan_h']} h scan.", ""]
    for k, rows in S.items():
        L += [f"## {k}", "", "| Part | Status | Score | Rule breaks (where) | Mass g | Boost h | Signal | Margin | Extra parts | Footprint | Verify | Note |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: (r["status"] != "INCUMBENT", -r["score"])):
            sig = r.get("signal"); un = r.get("units", {}).get("signal", "")
            brk = "; ".join(f"**{b['rule']}** ({b['requirement']}): {b['by']} - at the {b['where']}" for b in r["rule_breaks"]) or "-"
            L.append(f"| {r['name']} | **{r['status']}** | {r['score']:.2f} | {brk} | {r.get('mass_g', '-')} | {r.get('runtime_h', '-')} | {sig if sig is not None else '-'} {un} | {r.get('margin', '-')} | {r.get('attach', '-')} | {r.get('footprint', '-')} | {r.get('verify', '-')} | {r['note']} |")
        L.append("")
    if combo: L += ["## Recommended electrical swaps together", "", f"{', '.join(combo['parts'])}{' (includes a rule break: see the rows above)' if combo.get('breaks') else ''}: runtime {combo['runtime']['boost']} h boost / {combo['runtime']['scan']} h scan (baseline {sy['boost_continuous_h']} / {sy['scan_h']})", ""]
    open(os.path.join(ROOT, "docs", "COMPONENT_SELECTION.md"), "w").write("\n".join(L) + "\n")
    for k, v in S.items(): print(k, [(r["name"][:40], r["status"], r["score"]) for r in v])
    print("combined:", combo); return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
