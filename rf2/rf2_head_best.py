#!/usr/bin/env python3
"""Best head design 'across the board' (owner 2026-10-31). MODELED; nothing adopted.

Question: which coil (TX / RX model), drive (switch, clamp, current, PWM flat-top), and head build (litz, winding, preamp, placement, board stack,
cord lanes, connectors, splice) gives the best numbers on EVERY target at once, with the pack and the shaft held at today's choices?
Objective (maximin): maximise the WORST of the four ratios coin / 60.2 cm, 1 g gold / 30.2 cm, 0.1 g gold / 15.0 cm, boost runtime / 2.6 h, so
the winner improves all of them as evenly as possible; ties broken by head mass. Two envelopes: today's head (D 233 x 25.4 mm) and a free
head (D 180-300, H 15-35 mm). Every rule is a constraint (a design that breaks one is infeasible; the record keeps it).
Stages:
 1. continuous coil / drive search with the clean-sheet physics (rf2_cleansheet.evaluate, calibrated within 1.4 % to today's machine):
    Optuna TPE, 4 processes, constraints = broken rules, then a scipy Powell polish on the maximin objective.
 2. the head build options of the variant engine (plugins coil_winding, boards, wiring + the core rx / switch / txd axes) with the coil axis
    pinned to today's comb: coordinate search on the same maximin objective (rf2_variants.evaluate_combo, all rule rows).
 3. the transmit driver for the winning coil in ngspice (rf2_txd_spice topology: low-side SiC + shunt, freewheel branch for the flat-top,
    hysteretic coil-current loop, clamp): ramp, PWM frequency and ripple, fall, peak VDS, clamp energy.
Writes rf2/results/rf2_head_best.json and docs/HEAD_BEST.md.   usage: python3 rf2/rf2_head_best.py [--budget 45]"""
import os, sys, json, math, time, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
REF = dict(coin_25mm_silver=60.2, gold_1g=30.2, gold_0p1g=15.0, boost=2.6)
FIX = {"cell": "Molicel P45B", "S": 7, "P": 1, "profile": "square", "af": 31.0, "wall": 1.2, "L_shaft": 0.98}

def ratios(m):
    d = m["depth_cm"]; return dict(coin=d["coin_25mm_silver"] / REF["coin_25mm_silver"], g1=d["gold_1g"] / REF["gold_1g"], g01=d["gold_0p1g"] / REF["gold_0p1g"], boost=m["boost_h"] / REF["boost"])

def stage1_worker(args):
    env, budget, seed = args
    import optuna, rf2_cleansheet as CS
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    B = dict(CS.BOUNDS); C = {k: list(v) for k, v in CS.CATS.items()}
    for k, v in FIX.items():
        if k in C: C[k] = [v]
        else: B[k] = (v, v)
    if env == "head233": B["D"], B["H"] = (233.0, 233.0), (25.4, 25.4)
    def obj(trial):
        d = {}
        for k in CS.CONT: d[k] = trial.suggest_float(k, *B[k])
        for k in CS.INTS: d[k] = trial.suggest_int(k, int(B[k][0]), int(B[k][1]))
        for k, v in C.items(): d[k] = trial.suggest_categorical(k, v)
        e = CS.evaluate(d); trial.set_user_attr("viol", float(sum(e["viol"])))
        return min(ratios(e["m"]).values()) if e["m"].get("depth_cm") else 0.0
    st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed, constraints_func=lambda t: [t.user_attrs.get("viol", 1e3)], multivariate=True))
    st.enqueue_trial({**{k: CS.TODAY[k] for k in CS.CONT + CS.INTS}, **{k: (FIX.get(k, CS.TODAY[k])) for k in C}, "D": B["D"][0] if env == "head233" else CS.TODAY["D"], "H": B["H"][0] if env == "head233" else CS.TODAY["H"]})
    t0 = time.time(); n = 0
    while time.time() - t0 < budget: st.optimize(obj, n_trials=200); n += 200
    feas = [t for t in st.trials if t.value is not None and t.user_attrs.get("viol", 1) == 0]
    return [(t.value, t.params) for t in sorted(feas, key=lambda t: -t.value)[:20]], n

def stage1(env, budget, workers):
    import multiprocessing as mp, rf2_cleansheet as CS
    from scipy.optimize import minimize
    with mp.get_context("fork").Pool(workers) as pool: parts = pool.map(stage1_worker, [(env, budget, 11 + k) for k in range(workers)])
    cand = sorted([c for p, _ in parts for c in p], key=lambda c: -c[0])[:6]; n = sum(x for _, x in parts)
    B = dict(CS.BOUNDS); [B.__setitem__(k, (v, v)) for k, v in FIX.items() if k in B]
    if env == "head233": B["D"], B["H"] = (233.0, 233.0), (25.4, 25.4)
    best = None
    for v, x in cand:                                                     # Powell polish of the continuous variables on the maximin objective
        lo = np.array([B[k][0] for k in CS.CONT]); hi = np.array([B[k][1] for k in CS.CONT]); hi = np.where(hi > lo, hi, lo + 1e-9)
        def f(u):
            d = dict(x, **{k: float(lo[i] + np.clip(u[i], 0, 1) * (hi[i] - lo[i])) for i, k in enumerate(CS.CONT)}); e = CS.evaluate(d)
            return -(min(ratios(e["m"]).values()) if e["m"].get("depth_cm") else 0) + 10 * sum(e["viol"])
        u0 = (np.array([x[k] for k in CS.CONT]) - lo) / (hi - lo); r = minimize(f, u0, method="Powell", options=dict(maxfev=300, xtol=1e-3))
        d = dict(x, **{k: float(lo[i] + np.clip(r.x[i], 0, 1) * (hi[i] - lo[i])) for i, k in enumerate(CS.CONT)}); e = CS.evaluate(d)
        if not e["feasible"]: d, e = x, CS.evaluate(x)
        sc = min(ratios(e["m"]).values())
        if best is None or sc > best[0]: best = (sc, d, e)
    sc, d, e = best; m = e["m"]
    keep = ["D_mm", "H_mm", "r_mean_mm", "N", "p", "bundle", "litz", "I_scan_A", "I_boost_A", "T_flat_us", "V_clamp", "switch", "rx", "cord", "L_uH", "R_coil", "gate_us", "gate_planar_us",
            "depth_cm", "boost_h", "scan_h", "P_boost_W", "Tj_C", "head_g", "total_g", "torque_Nm", "sag_mm", "flex_w_mm", "edge"]
    summ = CS.summary(e) if hasattr(CS, "summary") else {k: m.get(k) for k in keep}
    return dict(env=env, trials=n, maximin=round(sc, 4), ratios={k: round(v, 3) for k, v in ratios(m).items()}, design={k: summ.get(k) for k in keep if k in summ}, x=d,
                broken=[(r["rule"], r["where"]) for r in e["rules"] if not r["ok"]], edge=[f"{r['rule']} @ {r['where']} ({r['value']} vs {r['limit']})" for r in e["rules"] if r["ok"] and r.get("status") == "EDGE"])

def stage2(budget_iter=4):
    """head build options of the variant engine around today's comb; coordinate search on the maximin objective"""
    import rf2_variants as V
    ctx = V.Ctx(); head_axes = ["switch", "txd", "rx", "flex_cu", "preamp", "head_placement", "board_stack", "litz", "winding", "cord_lanes", "connectors", "splice", "data"]
    opt = {ax["name"]: ax["options"] for ax in V.AXES}
    seeds = [dict(V.TODAY), dict(V.TODAY, switch="NTBG", rx="hybrid"), dict(V.TODAY, switch="NTBG", rx="hybrid", txd="s400"), dict(V.TODAY, switch="NTBG", txd="s400")]
    def ev(c):
        P = {}; [P.update(next(o for o in opt[a] if o["id"] == c[a])["p"]) for a in opt]; m = V.evaluate_combo(ctx, P)
        if m is None or m["breaks"]: return -1.0, m
        return min(ratios(dict(depth_cm=m["depth_cm"], boost_h=m["runtime_boost_h"])).values()), m
    steps = 0; overall = None
    for seed in seeds:                                                    # coordinate ascent from several seeds (joint moves such as switch + RX need a seed)
        cur = dict(seed); best, bm = ev(cur)
        for _ in range(budget_iter):
            improved = False
            for a in head_axes:
                for o in opt[a]:
                    c = dict(cur, **{a: o["id"]}); v, m = ev(c); steps += 1
                    if v > best + 1e-9: best, bm, cur, improved = v, m, c, True
            if not improved: break
        if overall is None or best > overall[0]: overall = (best, bm, cur)
    best, bm, cur = overall
    # free improvements: options that keep every target ratio (within 0.1 %) and lower mass, REF pickup or part count, with no broken rule
    free = []
    for a in head_axes:
        for o in opt[a]:
            if o["id"] == cur[a]: continue
            c = dict(cur, **{a: o["id"]}); v, m = ev(c); steps += 1
            if m is None or v < best - 1e-3: continue
            gain = dict(mass_g=m["mass_delta_g"] - bm["mass_delta_g"], parts=m["added_parts"] - bm["added_parts"], ref_pickup_mV=(m.get("ref_crosstalk_mV") or 0) - (bm.get("ref_crosstalk_mV") or 0),
                        extra={k: v2 for k, v2 in (m.get("extra") or {}).items() if "pF" in k or "pickup" in k})
            if (gain["mass_g"] < 0 or gain["parts"] < 0 or gain["ref_pickup_mV"] < 0) and gain["mass_g"] <= 0 and gain["parts"] <= 0 and gain["ref_pickup_mV"] <= 0: free.append(dict(axis=a, option=o["id"], desc=o["desc"], **gain))
    freeL = free
    return dict(maximin=round(best, 4), combo={k: v for k, v in cur.items() if v != V.TODAY[k]}, depth_cm=bm["depth_cm"], boost_h=bm["runtime_boost_h"], gate_us=bm["first_gate_us"],
                mass_delta_g=bm["mass_delta_g"], ref_crosstalk_mV=bm.get("ref_crosstalk_mV"), extra=bm.get("extra"), evaluations=steps, free_improvements=freeL,
                edge=[f"{r['rule']} @ {r['where']} ({r['value']} vs {r['limit']})" for r in bm["rules"] if r["ok"] and r["value"] and r["limit"] and abs(r["value"] / r["limit"] - 1) <= 0.05])

def stage3(L_uH, R_coil, I_set, v_clamp):
    """ngspice run of the rf2_txd_spice topology with the winning coil (L, R, set current) and clamp"""
    import rf2_txd_spice as TS
    L, RC = L_uH * 1e-6, R_coil; Rd = 408.0 * math.sqrt(L / 333e-6)
    nl = TS.netlist(I_set, TS.CONT.VBUS if hasattr(TS, "CONT") else 25.2, 0.0, 0.0)
    R_loop = RC + TS.CFX.R_TX_LOOP + TS.RDS + TS.RSH; x = I_set * R_loop / 25.2
    tr = -(L / R_loop) * math.log(1 - x) if x < 1 else float("inf"); t_en = tr + TS.T_FLAT; t_stop = t_en + 30e-6
    nl = TS.netlist(I_set, 25.2, t_en, t_stop).replace(f"Lc ca cb {TS.L}", f"Lc ca cb {L}").replace(f"Rcl cb sw {TS.RC}", f"Rcl cb sw {RC}").replace(f"Rd ct sw {TS.RD}", f"Rd ct sw {Rd}") \
        .replace(f"Vcl vcl 0 DC {TS.VCL}", f"Vcl vcl 0 DC {v_clamp}").replace(f"IC={TS.VCL}", f"IC={v_clamp}").replace(f".ic v(cl)={TS.VCL}", f".ic v(cl)={v_clamp}")
    vec = ["i(Vsense)", "v(sw)", "v(sq)"]
    A, _ = TS.CH.ng(nl, "run\nwrdata {OUT} " + " ".join(vec), timeout=1800)
    t = A[:, 0]; i = A[:, 1]; vsw = A[:, 3]; vsq = A[:, 5]
    flat = (t > tr + 10e-6) & (t < t_en - 1e-6); on = vsq > 0.5 * TS.RSH * I_set
    edges = int(np.sum(np.diff(on[flat].astype(int)) == 1)) if flat.any() else 0
    after = t >= t_en; fall = float(t[after][np.argmax(i[after] < 0.01 * I_set)] - t_en) if np.any(i[after] < 0.01 * I_set) else None
    return dict(L_uH=L_uH, R_coil=R_coil, I_set_A=I_set, V_clamp=v_clamp, Rd_ohm=round(Rd), t_ramp_us=round(tr * 1e6, 1), f_pwm_kHz=round(edges / max(t_en - tr - 11e-6, 1e-9) / 1e3, 1),
                ripple_pp_A=round(float(i[flat].max() - i[flat].min()), 3) if flat.any() else None, i_peak_A=round(float(i[t < t_en].max()), 2), fall_us=round(fall * 1e6, 2) if fall else None,
                fall_ideal_us=round(L * I_set / v_clamp * 1e6, 2), vds_peak_V=round(float(vsw.max()), 1), vds_limit_V=0.8 * 900)

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--budget", type=float, default=45.0); ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1)); ap.add_argument("--reuse-stage1", action="store_true"); a = ap.parse_args(argv)
    t0 = time.time(); res = dict(status="MODELED head study (owner 2026-10-31): maximin over coin / 1 g / 0.1 g depth and boost runtime vs today; pack and shaft at today's; nothing adopted", reference=REF, fixed=FIX)
    prev = os.path.join(OUT, "rf2_head_best.json")
    if a.reuse_stage1 and os.path.exists(prev): res["coil_drive"] = json.load(open(prev))["coil_drive"]
    else: res["coil_drive"] = {env: stage1(env, a.budget, a.workers) for env in ("head233", "headfree")}
    for env, r in res["coil_drive"].items(): print(env, r["maximin"], r["ratios"], {k: r["design"].get(k) for k in ("D_mm", "N", "p", "litz", "L_uH", "V_clamp", "I_scan_A", "switch", "rx", "boost_h", "depth_cm")})
    res["head_build"] = stage2(); print("build", res["head_build"]["maximin"], res["head_build"]["combo"], res["head_build"]["depth_cm"], res["head_build"]["boost_h"])
    res["drivers"] = {}
    for env, r in res["coil_drive"].items():
        dz = r["design"]
        try: res["drivers"][env] = stage3(dz["L_uH"], dz["R_coil"], dz["I_scan_A"] * math.sqrt(2.5), min(dz["V_clamp"], 720.0))
        except Exception as ex: res["drivers"][env] = dict(error=str(ex)[:300])
        print("driver", env, res["drivers"][env])
    res["run_s"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(OUT, "rf2_head_best.json"), "w"), indent=1, default=float)
    write_md(res); return 0

def write_md(res):
    L = ["# Best head design across the board (generated by rf2/rf2_head_best.py; MODELED)", "", res["status"] + ".",
         f"Reference (today): coin {REF['coin_25mm_silver']} cm, 1 g {REF['gold_1g']} cm, 0.1 g {REF['gold_0p1g']} cm, boost {REF['boost']} h. Pack / shaft held: {res['fixed']}.", "",
         "## 1. Coil and drive (continuous, clean-sheet physics)", "", "| Envelope | worst ratio | coin / 1 g / 0.1 g / boost ratios | D x H | coil | L uH | gate us | clamp V | I scan A | switch | RX | coin / 1 g / 0.1 g cm | boost h | head g |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for env, r in res["coil_drive"].items():
        d = r["design"]; rr = r["ratios"]; dc = d.get("depth_cm", {})
        L.append(f"| {env} | {r['maximin']} | {rr['coin']} / {rr['g1']} / {rr['g01']} / {rr['boost']} | {d.get('D_mm')} x {d.get('H_mm')} | {d.get('N')} x {d.get('p')} {d.get('bundle')} {d.get('litz')} | {d.get('L_uH')} | {d.get('gate_us')} | {d.get('V_clamp')} | {d.get('I_scan_A')} | {d.get('switch')} | {d.get('rx')} | {dc.get('coin_25mm_silver')} / {dc.get('gold_1g')} / {dc.get('gold_0p1g')} | {d.get('boost_h')} | {d.get('head_g')} |")
    for env, r in res["coil_drive"].items():
        L += ["", f"{env}: broken rules {r['broken'] or 'none'}; EDGE rows: {r['edge'] or 'none'}"]
    hb = res["head_build"]
    L += ["", "## 2. Head build around today's comb (variant engine: litz, winding, preamp, placement, board stack, lanes, connectors, splice, RX, switch, TXD position)", "",
          f"Worst ratio {hb['maximin']}; changes from today: {hb['combo'] or 'none'}; depth {hb['depth_cm']}; boost {hb['boost_h']} h; first gate {hb['gate_us']} us; mass {hb['mass_delta_g']:+} g; REF pickup {hb['ref_crosstalk_mV']} mV.",
          f"EDGE rows (within 5 %): {hb['edge'] or 'none'}", "", "Free improvements on top (targets unchanged; lower mass, part count or REF pickup):", ""] + \
         [f"- {f['axis']} = {f['option']} ({f['desc']}): mass {f['mass_g']:+} g, parts {f['parts']:+}, REF pickup {f['ref_pickup_mV']:+.2f} mV {f['extra'] if f['extra'] else ''}" for f in hb.get("free_improvements", [])] + ["", "## 3. Transmit driver for each winning coil (ngspice, rf2_txd_spice topology, boost current)", "",
          "| Envelope | L uH | I A | clamp V | Rd ohm | ramp us | PWM kHz | ripple A pp | peak A | fall us (ideal) | VDS peak V (limit) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for env, dr in res["drivers"].items():
        if "error" in dr: L.append(f"| {env} | error: {dr['error']} |"); continue
        L.append(f"| {env} | {dr['L_uH']} | {round(dr['I_set_A'], 2)} | {round(dr['V_clamp'])} | {dr['Rd_ohm']} | {dr['t_ramp_us']} | {dr['f_pwm_kHz']} | {dr['ripple_pp_A']} | {dr['i_peak_A']} | {dr['fall_us']} ({dr['fall_ideal_us']}) | {dr['vds_peak_V']} ({dr['vds_limit_V']}) |")
    L += ["", f"Run time {res['run_s']} s. Absolute depths are optimistic (no ground / EMI / motion noise); the ratios against today are the result."]
    open(os.path.join(ROOT, "docs", "HEAD_BEST.md"), "w").write("\n".join(L) + "\n")

if __name__ == "__main__":
    sys.exit(main())
