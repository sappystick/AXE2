#!/usr/bin/env python3
"""RF2 variant engine (owner 2026-10-31): enumerates EVERY combination of the axes in rf2/rf2_variant_axes.py, evaluates each with the
study models, scores it the rf2_select way, lists every broken rule at its location (nothing is excluded, nothing is adopted), finds the
Pareto front and the champion per objective, and appends a line to rf2/results/variants_history.jsonl so the tool's results can be compared
run to run as axes are added. Extend it by editing rf2_variant_axes.py (see its docstring); new parameter kinds go in evaluate_combo().

Models used: rf2_lowL_options (coil L/R/current, PI gate calibrated to MP1 v2 16.43 us, depth model, power and runtime, switch TJ, flex width;
hybrid RX), rf2_fold_options (shaft mass / sag / collapsed / hinges / POF link), rf2_shaft_options (telescope walls), rf2_pack_options (packs).
ASSUMED here: cord-flex stack 0.15 mm + 0.035 mm for 3 oz + 0.095 mm for a second TX copper layer; rolling-loop rule 2 x 40 x stack <= bore - 4
(rf2_chassis); clock-spring drum radius 17 mm; fold walls scale mass x t / 1.2 and the tube part of the sag x 1.2 / t; POF 0.60 W, 28 g with
transceivers; planar RX 8 g; dissipative clamp loses the 75 % the regenerative clamp recovers (rf2_continuous budget).

usage: python3 rf2/rf2_variants.py [--fix axis=id ...] [--top N] [--list] [--no-history]"""
import os, sys, json, math, itertools, argparse, subprocess, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
import rf2_lowL_options as LO, rf2_cordflex as CFX
from rf2_select import WEIGHTS, M_SAT, M_SYS
from rf2_variant_axes import AXES as CORE_AXES, load_plugins
PLUGINS = load_plugins()
AXES = CORE_AXES + [ax for pl in PLUGINS for ax in pl.AXES]
DIG_W = 3 * 0.45 + 2 * 0.3; POF_W, POF_G, RX_G = 0.60, 1.6 * 4.0 + 6 * 2.0, 8.0
BORE = 21.0 - 2 * 1.2; DRUM_R = 17.0
FOLD_KEY = {"fold x1": "fold x1 (mid) + chassis hinge", "fold neck+mid": "fold neck + mid + chassis hinge", "fold x2": "fold x2 (thirds) + chassis hinge"}
J = lambda f: json.load(open(os.path.join(OUT, f)))

class Ctx:
    def __init__(s):
        s.fold = J("rf2_fold_options.json"); s.walls = {w["wall_mm"]: w for w in J("rf2_shaft_options.json")["walls"]}
        try: s.hex = J("rf2_hex_section.json")
        except Exception: s.hex = None
        for pl in PLUGINS:
            if hasattr(pl, "prepare"): pl.prepare(s)
        po = J("rf2_pack_options.json"); s.packs = {o["key"]: o for o in po["options"]}; s.pack0 = s.packs[po["chosen"]]; s.cache = {}
    def shaft(s, name):
        if name.startswith("telescope"): return next(r for r in s.fold["rows"] if r["mechanism"].startswith("telescope"))
        for k, v in FOLD_KEY.items():
            if name.startswith(k): return next(r for r in s.fold["rows"] if r["mechanism"] == v and r["profile"] == name[len(k) + 1:])
        raise KeyError(name)
    def elec(s, N, p, sw, rx, tx2, scale):
        k = (N, p, sw, rx, tx2, scale)
        if k not in s.cache:
            mo, _ = LO.evaluate(N, p, sw, False, False, tx2=tx2, flex_scale=scale)
            if rx == "mono" or "depth_cm" not in mo: s.cache[k] = dict(mo, gate=mo.get("first_gate_us"))
            else:
                h = LO.hybrid(N, p, sw, False, tx2, flex_scale=scale)
                s.cache[k] = dict(mo, **{kk: h[kk] for kk in ("depth_cm", "runtime_scan_h", "runtime_boost_h")}, gate=h["gate_planar_us"], gate_mono=h["gate_mono_us"]) if h.get("reachable") else dict(mo, gate=None, unreachable=True)
        return s.cache[k]

def evaluate_combo(ctx, P):
    """P: merged parameters of one option per axis -> metrics + rule rows (value, limit, where)"""
    sr = ctx.shaft(P["shaft"]); fold = not P["shaft"].startswith("telescope")
    L_tx = ((P["txd_s"] + 150.0) / 1000 + 0.214 * sum(1 for s in sr["hinges_s_mm"] if s < P["txd_s"])) if fold else CFX.TX_LEN_M * P["txd_s"] / 857.0
    scale = round(L_tx / CFX.TX_LEN_M * (2.0 / P["oz"]), 4)
    e = ctx.elec(P["N"], P["p"], P["sw"], P["rx"], P["tx2"], scale)
    if "depth_cm" not in e or e.get("unreachable"): return None
    pk = ctx.packs[P["pack"]]; wh = pk["Wh_usable"]
    Pb = LO.WH / e["runtime_boost_h"]; Ps = LO.WH / e["runtime_scan_h"]
    if P["data"] == "POF": Pb += POF_W; Ps += POF_W
    if P["clamp"] == "dissip": Pb += 0.75 * LO.F * e["E_pulse_mJ"] * 1e-3 * 2.5; Ps += 0.75 * LO.F * e["E_pulse_mJ"] * 1e-3
    w_eff = (e["W_TX_mm"] / 2 if P["tx2"] else e["W_TX_mm"]) * (2.0 / P["oz"])
    fw = CFX.WIDTH + 2 * (w_eff - CFX.W_TX) - (DIG_W if P["data"] == "POF" else 0.0)
    stack = 0.15 + (0.035 if P["oz"] == 3 else 0.0) + (0.095 if P["tx2"] else 0.0); bend_r = 40 * stack
    hv = 1.5 + 2 * w_eff + 1.0
    t = P["wall"]
    if fold:
        mass_sh = (sr["tubes_and_hinges_g"] - 30 * len(sr["hinges_s_mm"])) * t / 1.2 + 30 * len(sr["hinges_s_mm"])
        sag = sr["tip_sag_rigid_latch_mm"] * 1.2 / t + (sr["tip_sag_mm"] - sr["tip_sag_rigid_latch_mm"])
    else:
        w = ctx.walls[t]; mass_sh, sag = w["tubes_g"], w["tip_sag_mm"]
    R = []
    def rule(name, v, lim, sense, where, kind="target"):
        ok = v <= lim if sense == "<=" else v >= lim; R.append(dict(rule=name, value=round(v, 3), limit=round(lim, 3), sense=sense, ok=bool(ok), where=where, kind=kind))
    rule("TX switch peak vs 80 % IDM", e["I_boost"], 0.8 * LO.SW[P["sw"]]["idm"], "<=", "TXD switch", "safety")
    rule("TX switch TJ in boost vs 125 C", e["Tj_switch_boost_C"], 125.0, "<=", "TXD switch", "safety")
    if fold:
        prof = P["shaft"].split(" ")[-2] + " " + P["shaft"].split(" ")[-1] if "hub" in P["shaft"] else P["shaft"].split(" ")[-1]
        face = (31 - 2 * t) / math.sqrt(3) - 0.6 if "hex" in prof else 31 - 2 * t - 0.6
        rule("HV lane group on one inner face", hv, face, "<=", f"shaft inner face ({prof})")
        rule("flex clock-spring bend: 40 x stack vs drum radius", bend_r, DRUM_R, "<=", "fold hinges")
    else:
        rule("cord-flex width vs bore less 2", fw, BORE - 2.0, "<=", "telescope inner bore")
        rule("rolling loop: 2 x 40 x stack vs bore less 4", 2 * bend_r, BORE - 4.0, "<=", "telescope rolling loop")
    for r in sr["rule_rows"]:
        if ("POF" in r["rule"] or "optical" in r["rule"]) and P["data"] != "POF": continue
        v = sag if "sag" in r["rule"] else r["value"]
        rule(r["rule"], v, r["limit"], r["sense"], f"shaft ({sr['mechanism']})")
    if pk.get("cell_current_frac_of_rating") is not None:
        rule("pack cell current in boost vs coldest-band rating", pk["cell_current_frac_of_rating"] * Pb / ctx.pack0["Wh_usable"] * ctx.pack0["Wh_usable"] / (LO.WH / 2.6), 1.0, "<=", f"battery ({P['pack']})", "safety")
    xt = None
    if ctx.hex:                                                          # REF-pair pickup from the TX strips inside the shaft at turn-off (rf2_hex_section, MODELED)
        if fold:
            prof = P["shaft"].split(" ", 2)[-1]; sh, inn = (prof.split(" ") + ["none"])[:2]
            sh = sh.replace("sq", "square"); c = ctx.hex["coupling"].get(f"{sh}|{inn}")
            M = c["M_tx_ref_nH_per_m"] if c else None
            if M is not None and inn == "hub6_cu": M *= ctx.hex["shielding"]["separator_100kHz"].get(sh, {}).get("Cu_2x18um", 1.0)
        else: M = ctx.hex["coplanar_reference"]["M_tx_ref_nH_per_m"]
        if M is not None: xt = round(M * 1e-9 * (e["I_scan"] / (e["fall_us"] * 1e-6)) * L_tx * 1e3, 2)
    added = (P["rx"] == "hybrid") + (len(sr["hinges_s_mm"]) if fold else 0) + (6 if P["data"] == "POF" else 0) + int(P["tx2"]) + (P["oz"] == 3) * 0
    mass_d = (mass_sh - 210) + (pk["system_delta_g"] - ctx.pack0["system_delta_g"]) + (RX_G if P["rx"] == "hybrid" else 0) + (POF_G if P["data"] == "POF" else 0)
    m = dict(_e=e, extra={}, first_gate_us=e["gate"], depth_cm=e["depth_cm"], runtime_boost_h=round(wh / Pb, 2), runtime_scan_h=round(wh / Ps, 2), P_boost_W=round(Pb, 2),
                flex_width_mm=round(fw, 2), L_tx_m=round(L_tx, 3), shaft_g=round(mass_sh), tip_sag_mm=round(sag, 2), collapsed_mm=sr["collapsed_mm"],
                torque_about_hand_Nm=pk["torque_about_hand_Nm"], ref_crosstalk_mV=xt, mass_delta_g=round(mass_d), added_parts=int(added), rules=R)
    for pl in PLUGINS:
        pl.evaluate(ctx, P, m)
    for r in m["rules"]: r["ok"] = bool(r["value"] <= r["limit"] if r["sense"] == "<=" else r["value"] >= r["limit"]) if r.get("value") is not None else r.get("ok", True)
    m["breaks"] = [r for r in m["rules"] if not r["ok"]]; m.pop("_e")
    return m

def _margin(r):
    vals = [min((x["limit"] / x["value"]) if x["sense"] == "<=" else (x["value"] / x["limit"]), M_SAT) for x in r["rules"] if x["value"] and x["limit"] and x["value"] > 0 and x["limit"] > 0]
    return min(vals) if vals else M_SAT

def score_one(r, base, m0, weights=None):
    w = weights or WEIGHTS
    sig = math.prod(r["depth_cm"][k] / base["depth_cm"][k] for k in base["depth_cm"]) ** (1 / 3)
    nonstd = sum(1 for a, v in r["combo"].items() if v != TODAY[a])
    f = dict(mass_g=M_SYS / (M_SYS + r["mass_delta_g"]), runtime_h=r["runtime_boost_h"] / base["runtime_boost_h"], signal=sig, margin=_margin(r) / m0,
             attach=1.0 / (1 + 0.1 * r["added_parts"]), footprint=base["collapsed_mm"] / r["collapsed_mm"], verify=max(0.5, 1.0 - 0.05 * nonstd))
    r["factors"] = {k: round(v, 3) for k, v in f.items()}; r["score"] = round(sum(w[k] * f[k] for k in w), 4)
    r["status"] = "OK" if not r["breaks"] else "BREAKS " + "; ".join(f"{b['rule']} ({b['value']} vs {b['limit']}) at {b['where']}" for b in r["breaks"])
    return r["score"]

def score_all(rows, base, weights=None):
    m0 = _margin(base)
    for r in rows: score_one(r, base, m0, weights)

def pareto(rows):
    K = np.array([[r["runtime_boost_h"], *r["depth_cm"].values(), -r["mass_delta_g"], -r["collapsed_mm"], -r["tip_sag_mm"]] for r in rows])
    front = np.ones(len(rows), bool)
    for i0 in range(0, len(rows), 400):
        A = K[i0:i0 + 400][:, None, :]; ge = (K[None, :, :] >= A).all(2) & (K[None, :, :] > A).any(2)
        front[i0:i0 + 400] = ~ge.any(1)
    for r, f in zip(rows, front): r["pareto"] = bool(f)

TODAY = {a["name"]: next(o["id"] for o in a["options"] if o.get("today")) for a in AXES}

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--fix", nargs="*", default=[]); ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--list", action="store_true"); ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--plugin-test", default=None, help="evaluate each option of one plugin's axes with everything else at today's value")
    ap.add_argument("--max-combos", type=int, default=250000, help="above this, search instead of enumerating")
    ap.add_argument("--samples", type=int, default=30000); ap.add_argument("--seeds", type=int, default=30); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--weights", default="default", help="default | learned (rf2/results/rf2_variant_weights.json from rf2_variant_learn.py)"); a = ap.parse_args(argv)
    if a.plugin_test:
        ctx = Ctx(); pl = next(p for p in PLUGINS if p.__name__.endswith(a.plugin_test))
        for ax in pl.AXES:
            for o in ax["options"]:
                P = {}; [P.update(next(oo for oo in A["options"] if oo["id"] == TODAY[A["name"]])["p"]) for A in AXES]; P.update(o["p"])
                m = evaluate_combo(ctx, P); print(ax["name"], o["id"], "gate", m["first_gate_us"], "depth", m["depth_cm"], "boost", m["runtime_boost_h"], "mass", m["mass_delta_g"], "extra", m["extra"])
                for r in m["rules"][-6:]: print("    ", r)
        return 0
    if a.list:
        for ax in AXES: print(f"{ax['name']}: " + ", ".join(o["id"] + ("*" if o.get("today") else "") for o in ax["options"]) + f"   ({ax['help']})")
        return 0
    fix = dict(f.split("=", 1) for f in a.fix); t0 = time.time(); ctx = Ctx(); skipped = []; memo = {}
    weights = WEIGHTS
    if a.weights == "learned" and os.path.exists(os.path.join(OUT, "rf2_variant_weights.json")): weights = J("rf2_variant_weights.json")["learned"]
    space = [[o for o in ax["options"] if ax["name"] not in fix or o["id"] == fix[ax["name"]]] for ax in AXES]
    total = math.prod(len(sp) for sp in space)
    def run(combo):
        cid = {ax["name"]: o["id"] for ax, o in zip(AXES, combo)}; key = "|".join(f"{k}={v}" for k, v in cid.items())
        if key in memo: return memo[key]
        P = {}; [P.update(o["p"]) for o in combo]; m = evaluate_combo(ctx, P)
        r = None if m is None else dict(id=key, combo=cid, **m)
        if r is None: skipped.append(dict(combo=cid, why="TX current not reachable from the bus through the loop resistance"))
        memo[key] = r; return r
    today_c = tuple(next((o for o in sp if o["id"] == TODAY[ax["name"]]), sp[0]) for ax, sp in zip(AXES, space))
    if total <= a.max_combos:
        mode = "full enumeration"
        for combo in itertools.product(*space): run(combo)
    else:
        # search: today, one-factor-at-a-time, random sample, then coordinate ascent from the best seeds (score, and score among no-break rows)
        import random
        mode = f"search ({a.samples} random + one-factor + coordinate ascent from {a.seeds} seeds; space {total})"; rng = random.Random(a.seed)
        run(today_c)
        for i, sp in enumerate(space):
            for o in sp: c = list(today_c); c[i] = o; run(tuple(c))
        for _ in range(a.samples): run(tuple(rng.choice(sp) for sp in space))
        base0 = memo[next(iter(memo))] if memo.get("|".join(f"{ax['name']}={o['id']}" for ax, o in zip(AXES, today_c))) is None else memo["|".join(f"{ax['name']}={o['id']}" for ax, o in zip(AXES, today_c))]
        m0 = _margin(base0)
        def obj(r, nb): return -1e9 if r is None else score_one(r, base0, m0, weights) - (1.0 if nb and r["breaks"] else 0.0)
        idx = lambda r: tuple(next(o for o in sp if o["id"] == r["combo"][ax["name"]]) for ax, sp in zip(AXES, space))
        for nb in (False, True):
            seeds = sorted((r for r in memo.values() if r), key=lambda r: -obj(r, nb))[:a.seeds]
            for sd in seeds:
                cur = list(idx(sd)); best = obj(run(tuple(cur)), nb); improved = True
                while improved:
                    improved = False
                    for i, sp in enumerate(space):
                        for o in sp:
                            if o is cur[i]: continue
                            c = list(cur); c[i] = o; v = obj(run(tuple(c)), nb)
                            if v > best + 1e-9: best, cur, improved = v, c, True
    rows = [r for r in memo.values() if r]
    base = next((r for r in rows if r["combo"] == TODAY), None)
    if base is None: base = dict(rows[0])                                                   # --fix excluded today's machine: score against the first row
    score_all(rows, base, weights); pareto(rows); rows.sort(key=lambda r: -r["score"])
    ok = [r for r in rows if not r["breaks"]]
    obj = dict(score=lambda r: r["score"], small_gold=lambda r: r["depth_cm"]["gold_0p1g"], coin=lambda r: r["depth_cm"]["coin_25mm_silver"], gold_1g=lambda r: r["depth_cm"]["gold_1g"],
               runtime=lambda r: r["runtime_boost_h"], lightest=lambda r: -r["mass_delta_g"], compact=lambda r: -r["collapsed_mm"], stiff=lambda r: -r["tip_sag_mm"], quiet=lambda r: -(r["ref_crosstalk_mV"] if r["ref_crosstalk_mV"] is not None else 1e9))
    champs = {k: dict(any=max(rows, key=f)["id"], no_break=(max(ok, key=f)["id"] if ok else None)) for k, f in obj.items()}
    res = dict(status="MODELED variant engine: nothing adopted; nothing excluded; broken rules named at their location", axes={ax["name"]: [o["id"] for o in ax["options"]] for ax in AXES},
               today=TODAY, fixed=fix, weights=weights, mode=mode, space_size=total, n=len(rows), skipped=skipped, n_ok=len(ok), n_pareto=sum(r["pareto"] for r in rows),
               baseline=dict(id=base["id"], score=base["score"], rank=rows.index(base) + 1 if base in rows else None), champions=champs, run_s=round(time.time() - t0, 1), rows=rows)
    keep = set(r["id"] for r in rows[:300]) | set(r["id"] for r in rows if r["pareto"]) | set(r["id"] for r in ok[:300]) | {base["id"]} | {v for c in champs.values() for v in c.values() if v}
    full = res.pop("rows"); res["rows_kept"] = [r for r in full if r["id"] in keep]; res["rows_note"] = "top 300, best 300 without breaks, the Pareto front, champions and today; every row (metrics + broken rules) in rf2_variants_all.csv.gz"
    json.dump(res, open(os.path.join(OUT, "rf2_variants.json"), "w"), default=float); res["rows"] = full
    import csv, gzip
    with gzip.open(os.path.join(OUT, "rf2_variants_all.csv.gz"), "wt", newline="") as fh:
        w = csv.writer(fh); ax = [a["name"] for a in AXES]
        w.writerow(ax + ["score", "pareto", "gate_us", "coin_cm", "gold1g_cm", "gold0p1g_cm", "boost_h", "scan_h", "mass_delta_g", "sag_mm", "collapsed_mm", "ref_crosstalk_mV", "n_breaks", "breaks"])
        for r in full:
            d = r["depth_cm"]; w.writerow([r["combo"][a] for a in ax] + [r["score"], int(r["pareto"]), r["first_gate_us"], d["coin_25mm_silver"], d["gold_1g"], d["gold_0p1g"], r["runtime_boost_h"], r["runtime_scan_h"],
                                          r["mass_delta_g"], r["tip_sag_mm"], r["collapsed_mm"], r["ref_crosstalk_mV"], len(r["breaks"]), "; ".join(f"{b['rule']} at {b['where']}" for b in r["breaks"])])
    try: sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception: sha = "?"
    hist_f = os.path.join(OUT, "variants_history.jsonl"); hist = [json.loads(l) for l in open(hist_f)] if os.path.exists(hist_f) else []
    entry = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S"), git=sha, mode=mode, space=total, n=len(rows), n_ok=len(ok), axes={k: len(v) for k, v in res["axes"].items()}, fixed=fix, baseline_score=base["score"],
                 best=dict(id=rows[0]["id"], score=rows[0]["score"]), best_no_break=dict(id=ok[0]["id"], score=ok[0]["score"]) if ok else None,
                 best_small_gold_no_break=champs["small_gold"]["no_break"], best_runtime_no_break=champs["runtime"]["no_break"])
    prev_best = max((h["best_no_break"]["score"] for h in hist if h.get("best_no_break") and not h.get("fixed")), default=None)
    entry["improved_vs_history"] = None if prev_best is None else round((entry["best_no_break"]["score"] if entry["best_no_break"] else 0) - prev_best, 4)
    if not a.no_history and not fix: open(hist_f, "a").write(json.dumps(entry) + "\n"); hist.append(entry)
    write_report(res, rows, ok, base, champs, hist, a.top)
    print(f"{len(rows)} variants ({len(skipped)} unreachable) in {res['run_s']} s; {len(ok)} break no rule; Pareto {res['n_pareto']}; today rank {res['baseline']['rank']} score {base['score']}")
    for r in rows[:8]: print(r["score"], r["id"], r["depth_cm"], r["runtime_boost_h"], r["status"][:90])
    print("champions (no break):", {k: v["no_break"] for k, v in champs.items()})
    return 0

def write_report(res, rows, ok, base, champs, hist, top):
    hdr = "| # | Score | P | Variant | Gate us | Coin / 1 g / 0.1 g cm | Boost h | Scan h | Mass delta g | Sag mm | Collapsed mm | REF pickup mV | Status |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    def line(i, r):
        d = r["depth_cm"]; v = ", ".join(f"{k} {x}" for k, x in r["combo"].items() if x != TODAY[k]) or "today's machine"
        return f"| {i} | {r['score']} | {'P' if r['pareto'] else ''} | {v} | {r['first_gate_us']} | {d['coin_25mm_silver']} / {d['gold_1g']} / {d['gold_0p1g']} | {r['runtime_boost_h']} | {r['runtime_scan_h']} | {r['mass_delta_g']:+d} | {r['tip_sag_mm']} | {r['collapsed_mm']} | {r['ref_crosstalk_mV']} | {r['status']} |"
    byid = {r["id"]: r for r in rows}
    L = ["# Variant engine results (generated by rf2/rf2_variants.py; MODELED)", "", res["status"] + ".",
         f"{res['n']} combinations evaluated ({res['mode']}; space {res['space_size']}; {len(res['skipped'])} unreachable) over " + "; ".join(f"{k} [{' | '.join(v)}]" for k, v in res["axes"].items()) + f". Today: {res['today']}.",
         f"Score: rf2_select weights {res['weights']}; today's machine = {base['score']} (rank {res['baseline']['rank']}). {res['n_ok']} combinations break no rule; {res['n_pareto']} on the Pareto front "
         "(runtime, three depths, mass, collapsed length, sag). Variants are written as the axes that differ from today.", "",
         "## Champions per objective", "", "| Objective | Best, any status | Best that breaks no rule |", "|---|---|---|"]
    for k, v in champs.items():
        a = byid[v["any"]]; b = byid.get(v["no_break"]) if v["no_break"] else None
        fmt = lambda r: (", ".join(f"{kk} {x}" for kk, x in r["combo"].items() if x != TODAY[kk]) or "today") + f" (score {r['score']}, coin/1g/0.1g {r['depth_cm']['coin_25mm_silver']}/{r['depth_cm']['gold_1g']}/{r['depth_cm']['gold_0p1g']} cm, boost {r['runtime_boost_h']} h, {r['mass_delta_g']:+d} g)"
        L.append(f"| {k} | {fmt(a)}{'' if not a['breaks'] else ' - BREAKS ' + str(len(a['breaks'])) + ' rule(s)'} | {fmt(b) if b else '-'} |")
    L += ["", f"## Top {top} by score (all statuses)", "", hdr] + [line(i + 1, r) for i, r in enumerate(rows[:top])]
    L += ["", f"## Top {min(top, len(ok))} that break no rule", "", hdr] + [line(i + 1, r) for i, r in enumerate(ok[:top])]
    L += ["", "## Today's machine", "", hdr, line(res["baseline"]["rank"] or 0, base), "", "## Run history (rf2/results/variants_history.jsonl, last 8)", "",
          "| Time | Git | Combinations | No-break | Best no-break score | Change vs best before |", "|---|---|---|---|---|---|"]
    for h in hist[-8:]: L.append(f"| {h['time']} | {h['git']} | {h['n']} | {h['n_ok']} | {h['best_no_break']['score'] if h.get('best_no_break') else '-'} | {h.get('improved_vs_history')} |")
    L += ["", "Extend: add options or axes in rf2/rf2_variant_axes.py; new parameter kinds in rf2_variants.evaluate_combo(). All rows with factors and rule rows: rf2/results/rf2_variants.json."]
    open(os.path.join(ROOT, "docs", "VARIANTS.md"), "w").write("\n".join(L) + "\n")

if __name__ == "__main__":
    sys.exit(main())
