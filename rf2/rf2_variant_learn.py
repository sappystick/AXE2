#!/usr/bin/env python3
"""Learning layer for the variant engine (owner 2026-10-31). Reads what rf2_variants.py evaluated and learns from it; numpy only. MODELED.

1. Main effects: for every axis option, the mean score / no-break rate / depth / runtime change against today's option of that axis, averaged
   over every evaluated combination of the other axes (a full-factorial effect when the engine enumerated everything).
2. Surrogate: ridge regression of the score on one-hot axis options plus all pairwise interactions (closed form, lambda chosen by 5-fold CV).
   Reports R^2 (in- and out-of-fold), the strongest interactions (pairs whose joint effect differs from the sum of their main effects), and
   predicts the score of combinations the engine did not evaluate (used to steer search when the space is too big to enumerate).
3. Robustness: Monte Carlo over the ASSUMED inputs (NTBG hot RDS factor 1.3-1.9, planar-RX channel power 0.2-0.5 W, POF link power 0.41-0.60 W,
   MP1 noise +-15 %, fold-hinge stiffness x0.3-x3 applied to the hinge part of the sag): re-evaluates the top variants under each draw and
   reports how often each one ranks first and its 5-95 % score band. A variant that wins only under one assumption is flagged.
4. Owner preference: rf2/variant_decisions.json records owner choices (prefer / over). Weights on the rf2_select simplex are searched
   (Dirichlet samples around the defaults) for the set that agrees with the most decisions and stays closest to the defaults; written to
   rf2/results/rf2_variant_weights.json (used by `rf2_variants.py --weights learned`). With few decisions this is a weak signal: it says so.
5. Next study: the axis with the largest share of score variance and the ASSUMED input that most changes the ranking.
Writes rf2/results/rf2_variant_learn.json and docs/VARIANTS_LEARNING.md.   usage: python3 rf2/rf2_variant_learn.py [--mc 120]"""
import os, sys, json, csv, gzip, math, argparse, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
import rf2_variants as V, rf2_lowL_options as LO
from rf2_select import WEIGHTS

def load_rows():
    with gzip.open(os.path.join(OUT, "rf2_variants_all.csv.gz"), "rt") as fh:
        rd = csv.DictReader(fh); rows = list(rd)
    axes = [a["name"] for a in V.AXES]
    for r in rows:
        for k in ("score", "coin_cm", "gold1g_cm", "gold0p1g_cm", "boost_h", "scan_h", "mass_delta_g", "sag_mm", "collapsed_mm"): r[k] = float(r[k])
        r["n_breaks"] = int(r["n_breaks"])
    return rows, axes

def main_effects(rows, axes):
    out = {}
    for ax in axes:
        today = V.TODAY[ax]; grp = {}
        for r in rows: grp.setdefault(r[ax], []).append(r)
        t = grp.get(today, [])
        if not t: continue
        mt = lambda g, k: float(np.mean([x[k] for x in g]))
        out[ax] = {o: dict(n=len(g), d_score=round(mt(g, "score") - mt(t, "score"), 4), no_break_rate=round(float(np.mean([x["n_breaks"] == 0 for x in g])), 3),
                           d_coin_cm=round(mt(g, "coin_cm") - mt(t, "coin_cm"), 2), d_gold0p1g_cm=round(mt(g, "gold0p1g_cm") - mt(t, "gold0p1g_cm"), 2),
                           d_boost_h=round(mt(g, "boost_h") - mt(t, "boost_h"), 2), d_mass_g=round(mt(g, "mass_delta_g") - mt(t, "mass_delta_g"), 1)) for o, g in grp.items()}
    return out

def design(rows, axes, levels, pairs):
    cols = [(ax, o) for ax in axes for o in levels[ax] if o != V.TODAY[ax]]
    pcols = [((a, oa), (b, ob)) for a, b in pairs for oa in levels[a] if oa != V.TODAY[a] for ob in levels[b] if ob != V.TODAY[b]]
    X = np.zeros((len(rows), 1 + len(cols) + len(pcols)), dtype=np.float32); X[:, 0] = 1
    ci = {c: i + 1 for i, c in enumerate(cols)}
    for n, r in enumerate(rows):
        for ax in axes:
            c = (ax, r[ax])
            if c in ci: X[n, ci[c]] = 1
        for k, ((a, oa), (b, ob)) in enumerate(pcols):
            if r[a] == oa and r[b] == ob: X[n, 1 + len(cols) + k] = 1
    return X, cols, pcols

def ridge(X, y, lam):
    A = X.T @ X + lam * np.eye(X.shape[1]); A[0, 0] -= lam; return np.linalg.solve(A, X.T @ y)

def surrogate(rows, axes):
    levels = {ax: sorted(set(r[ax] for r in rows)) for ax in axes}; pairs = list(itertools.combinations([a for a in axes if len(levels[a]) > 1], 2))
    y = np.array([r["score"] for r in rows]); X, cols, pcols = design(rows, axes, levels, pairs)
    rng = np.random.default_rng(0); fold = rng.integers(0, 5, len(rows)); best = None
    # speed (2026-10-31): the Gram matrix of each fold is the total minus that fold's own block: 6 matrix products instead of 25
    X64 = X.astype(np.float64); G = X64.T @ X64; b = X64.T @ y
    Gk = [X64[fold == k].T @ X64[fold == k] for k in range(5)]; bk = [X64[fold == k].T @ y[fold == k] for k in range(5)]
    def solve(Gm, bm, lam):
        A = Gm + lam * np.eye(Gm.shape[0]); A[0, 0] -= lam; return np.linalg.solve(A, bm)
    for lam in (1e-3, 1e-2, 1e-1, 1.0, 10.0):
        pred = np.zeros_like(y)
        for k in range(5):
            w = solve(G - Gk[k], b - bk[k], lam); pred[fold == k] = X64[fold == k] @ w
        r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
        if best is None or r2 > best[1]: best = (lam, r2)
    w = solve(G, b, best[0]); X = X64; r2_in = 1 - np.sum((y - X @ w) ** 2) / np.sum((y - y.mean()) ** 2)
    inter = sorted(((abs(w[1 + len(cols) + k]), pc, float(w[1 + len(cols) + k])) for k, pc in enumerate(pcols)), reverse=True)[:12]
    var_share = {}
    for ax in axes:
        g = {}
        for r in rows: g.setdefault(r[ax], []).append(r["score"])
        means = [np.mean(v) for v in g.values()]; var_share[ax] = float(np.var(means) / np.var(y)) if np.var(y) > 0 else 0.0
    return dict(lambda_=best[0], r2_cv=round(float(best[1]), 4), r2_in=round(float(r2_in), 4), n_features=X.shape[1],
                top_interactions=[dict(pair=f"{a[0]}={a[1]} x {b[0]}={b[1]}", coef=round(c, 4)) for _, (a, b), c in inter],
                main_coefs={f"{a}={o}": round(float(w[i + 1]), 4) for i, (a, o) in enumerate(cols)},
                variance_share={k: round(v, 3) for k, v in sorted(var_share.items(), key=lambda kv: -kv[1])})

def robustness(n_mc, top_ids):
    """re-evaluate the listed variants under random draws of the ASSUMED inputs; ranks within the list"""
    rng = np.random.default_rng(1); sw0 = dict(LO.SW["NTBG080N120SC1"]); rx0 = LO.P_RX2_W; pof0 = V.POF_W; nz0 = LO.NOISE_nV
    combos = [dict(kv.split("=") for kv in i.split("|")) for i in top_ids]; wins = np.zeros(len(top_ids)); scores = [[] for _ in top_ids]; drivers = {}
    opt = {ax["name"]: {o["id"]: o for o in ax["options"]} for ax in V.AXES}
    for it in range(n_mc):
        d = dict(hot=rng.uniform(1.3, 1.9), rx=rng.uniform(0.2, 0.5), pof=rng.uniform(0.41, 0.60), noise=rng.uniform(0.85, 1.15), hinge=float(np.exp(rng.uniform(np.log(0.3), np.log(3.0)))))
        LO.SW["NTBG080N120SC1"]["rds"] = 0.110 * d["hot"]; LO.P_RX2_W = d["rx"]; V.POF_W = d["pof"]; LO.NOISE_nV = nz0 * d["noise"]
        ctx = V.Ctx()
        for r in ctx.fold["rows"]:
            if r.get("tip_sag_rigid_latch_mm") is not None: r["tip_sag_mm"] = r["tip_sag_rigid_latch_mm"] + (r["tip_sag_mm"] - r["tip_sag_rigid_latch_mm"]) / d["hinge"]
        today = {ax["name"]: opt[ax["name"]][V.TODAY[ax["name"]]] for ax in V.AXES}
        def ev(cmb):
            P = {}; [P.update(opt[a][cmb.get(a, V.TODAY[a])]["p"]) for a in opt]; m = V.evaluate_combo(ctx, P)
            return None if m is None else dict(m, combo={a: cmb.get(a, V.TODAY[a]) for a in opt})
        base = ev({a: V.TODAY[a] for a in opt}); m0 = V._margin(base); V.score_one(base, base, m0)
        sc = []
        for k, c in enumerate(combos):
            r = ev(c); s = V.score_one(r, base, m0) if r else -1; sc.append(s); scores[k].append(s)
        wins[int(np.argmax(sc))] += 1; drivers.setdefault("draws", []).append(dict(d, winner=int(np.argmax(sc))))
    LO.SW["NTBG080N120SC1"].update(sw0); LO.P_RX2_W = rx0; V.POF_W = pof0; LO.NOISE_nV = nz0
    res = [dict(id=i, p_rank1=round(w / n_mc, 3), score_p5=round(float(np.percentile(s, 5)), 4), score_p50=round(float(np.percentile(s, 50)), 4), score_p95=round(float(np.percentile(s, 95)), 4)) for i, w, s in zip(top_ids, wins, scores)]
    # which assumption moves the winner: correlation of each draw variable with "winner == modal winner"
    modal = int(np.argmax(wins)); D = drivers["draws"]; infl = {}
    for k in ("hot", "rx", "pof", "noise", "hinge"):
        x = np.array([dd[k] for dd in D]); yv = np.array([dd["winner"] == modal for dd in D], float)
        infl[k] = round(float(abs(np.corrcoef(x, yv)[0, 1])) if yv.std() > 0 and x.std() > 0 else 0.0, 3)
    return res, infl

def preferences(rows, axes):
    f = os.path.join(HERE, "variant_decisions.json")
    dec = json.load(open(f))["decisions"] if os.path.exists(f) else []
    if not dec: return dict(n=0, note="no owner decisions recorded"), None
    full = {}
    path = os.path.join(OUT, "rf2_variants.json"); kept = json.load(open(path))["rows_kept"]
    # need factor vectors: re-evaluate pairs that differ only in the decided axis, everything else today
    ctx = V.Ctx(); opt = {ax["name"]: {o["id"]: o for o in ax["options"]} for ax in V.AXES}
    def ev(cmb):
        P = {}; [P.update(opt[a][cmb.get(a, V.TODAY[a])]["p"]) for a in opt]; m = V.evaluate_combo(ctx, P); return None if m is None else dict(m, combo={a: cmb.get(a, V.TODAY[a]) for a in opt})
    base = ev({}); m0 = V._margin(base); V.score_one(base, base, m0)
    pairs = []
    for d in dec:
        a, b = ev(d["prefer"]), ev(d["over"])
        if a is None or b is None: continue                                  # critic 2026-10-31: an unreachable combination (evaluate_combo -> None) crashed dict(None)
        V.score_one(a, base, m0); V.score_one(b, base, m0); pairs.append((a["factors"], b["factors"], d))
    keys = list(WEIGHTS); w0 = np.array([WEIGHTS[k] for k in keys]); rng = np.random.default_rng(2)
    cand = [w0] + list(rng.dirichlet(w0 * 40, 6000)) + list(rng.dirichlet(np.ones(len(keys)), 3000))
    def agree(w): return sum(1 for fa, fb, _ in pairs if sum(w[i] * fa[k] for i, k in enumerate(keys)) > sum(w[i] * fb[k] for i, k in enumerate(keys)))
    best = max(cand, key=lambda w: (agree(w), -np.abs(w - w0).sum()))
    learned = {k: round(float(v), 4) for k, v in zip(keys, best)}
    out = dict(n=len(dec), agree_default=agree(w0), agree_learned=agree(best), default=WEIGHTS, learned=learned,
               decisions=[dict(prefer=d["prefer"], over=d["over"], note=d.get("note", ""), default_agrees=bool(sum(w0[i] * fa[k] for i, k in enumerate(keys)) > sum(w0[i] * fb[k] for i, k in enumerate(keys)))) for fa, fb, d in pairs],
               note="weak signal: %d decisions for %d weights; the learned set is the one closest to the defaults among those agreeing with the most decisions" % (len(dec), len(keys)))
    return out, learned

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--mc", type=int, default=120); ap.add_argument("--top", type=int, default=12); a = ap.parse_args(argv)
    rows, axes = load_rows(); res = dict(status="MODELED learning layer over the variant engine's evaluated rows (numpy; no external ML library)", n_rows=len(rows))
    # critic 2026-10-31: in search mode the coordinate-ascent rows cluster around the best seeds (not a random sample): main effects, variance
    # shares and the surrogate's R2 are computed on the unbiased rows (full enumeration or the uniform random sample); R2 on every row is kept for comparison.
    unb = [r for r in rows if r.get("origin", "enum") in ("enum", "random")] or rows
    res["sample"] = dict(n_unbiased=len(unb), origins={o: sum(1 for r in rows if r.get("origin", "enum") == o) for o in sorted(set(r.get("origin", "enum") for r in rows))})
    res["main_effects"] = main_effects(unb, axes); res["surrogate"] = surrogate(unb, axes)
    if len(unb) < len(rows): res["surrogate"]["r2_cv_all_rows_incl_ascent"] = surrogate(rows, axes)["r2_cv"]
    srt = sorted(rows, key=lambda r: -r["score"]); ok = [r for r in srt if r["n_breaks"] == 0]
    ids = lambda rs: ["|".join(f"{ax}={r[ax]}" for ax in axes) for r in rs]
    top_any, top_ok = ids(srt[:a.top]), ids(ok[:a.top])
    res["robustness_any"], res["influence_any"] = robustness(a.mc, top_any)
    res["robustness_no_break"], res["influence_no_break"] = robustness(a.mc, top_ok)
    res["preferences"], learned = preferences(rows, axes)
    if learned: json.dump(dict(learned=learned, default=WEIGHTS, source="rf2_variant_learn.py from rf2/variant_decisions.json"), open(os.path.join(OUT, "rf2_variant_weights.json"), "w"), indent=1)
    vs = res["surrogate"]["variance_share"]; infl = res["influence_no_break"]
    res["next_study"] = dict(axis_with_most_score_variance=next(iter(vs)), assumption_that_moves_the_winner_most=(max(infl, key=infl.get) if infl and max(infl.values()) > 0
                             else "none: the winner did not change in any draw"))   # critic 2026-10-31: all-zero influences used to name the first key ('hot')
    json.dump(res, open(os.path.join(OUT, "rf2_variant_learn.json"), "w"), indent=1, default=float)
    L = ["# Variant engine: what it learned (generated by rf2/rf2_variant_learn.py; MODELED)", "", res["status"] + f". Rows: {len(rows)} ({res['sample']['origins']}); main effects, variance shares and the surrogate use the {res['sample']['n_unbiased']} unbiased rows (enumerated or uniform random).", "",
         "## Which axis matters (share of score variance)", "", "| Axis | Share |", "|---|---|"] + [f"| {k} | {v} |" for k, v in vs.items()] + [
         "", "## Main effects vs today's option (averaged over all other axes)", "", "| Axis | Option | n | d score | no-break rate | d coin cm | d 0.1 g cm | d boost h | d mass g |", "|---|---|---|---|---|---|---|---|---|"]
    for ax, d in res["main_effects"].items():
        for o, e in sorted(d.items(), key=lambda kv: -kv[1]["d_score"]): L.append(f"| {ax} | {o}{' (today)' if o == V.TODAY[ax] else ''} | {e['n']} | {e['d_score']:+} | {e['no_break_rate']} | {e['d_coin_cm']:+} | {e['d_gold0p1g_cm']:+} | {e['d_boost_h']:+} | {e['d_mass_g']:+} |")
    s = res["surrogate"]
    L += ["", f"## Surrogate model (ridge, one-hot + pairwise interactions): R2 out-of-fold {s['r2_cv']}, in-sample {s['r2_in']}, {s['n_features']} features", "",
          "Strongest interactions (joint effect beyond the two main effects):", ""] + [f"- {x['pair']}: {x['coef']:+}" for x in s["top_interactions"]] + [
          "", f"## Robustness over ASSUMED inputs ({a.mc} Monte Carlo draws)", "", "Top variants that break no rule:", "", "| Variant (axes that differ from today) | P(rank 1) | score 5 / 50 / 95 % |", "|---|---|---|"]
    def short(i): return ", ".join(f"{kv.split('=')[0]} {kv.split('=')[1]}" for kv in i.split("|") if kv.split("=")[1] != V.TODAY[kv.split("=")[0]]) or "today"
    L += [f"| {short(x['id'])} | {x['p_rank1']} | {x['score_p5']} / {x['score_p50']} / {x['score_p95']} |" for x in res["robustness_no_break"]]
    L += ["", f"Influence of each assumption on who wins (|correlation|): {res['influence_no_break']}", "", "Top variants of any status:", "", "| Variant | P(rank 1) | score 5 / 50 / 95 % |", "|---|---|---|"]
    L += [f"| {short(x['id'])} | {x['p_rank1']} | {x['score_p5']} / {x['score_p50']} / {x['score_p95']} |" for x in res["robustness_any"]]
    p = res["preferences"]
    L += ["", "## Owner preference calibration (rf2/variant_decisions.json)", "", f"{p.get('note', '')}", ""]
    if p.get("n"):
        L += [f"Decisions agreed with: default weights {p['agree_default']}/{p['n']}, learned weights {p['agree_learned']}/{p['n']}.", f"Default {p['default']}", f"Learned {p['learned']}", ""] + \
             [f"- prefer {d['prefer']} over {d['over']} ({d['note']}): default weights agree = {d['default_agrees']}" for d in p["decisions"]]
    L += ["", f"## Next study suggested: axis '{res['next_study']['axis_with_most_score_variance']}' (largest score variance); assumption '{res['next_study']['assumption_that_moves_the_winner_most']}' (moves the winner most): measure it."]
    open(os.path.join(ROOT, "docs", "VARIANTS_LEARNING.md"), "w").write("\n".join(L) + "\n")
    print("R2 cv", s["r2_cv"], "variance share", vs); print("robust no-break", res["robustness_no_break"][:3]); print("prefs", {k: v for k, v in p.items() if k != "decisions"})
    return 0

if __name__ == "__main__":
    sys.exit(main())
