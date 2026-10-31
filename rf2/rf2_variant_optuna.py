#!/usr/bin/env python3
"""Optuna optimiser agent for the variant engine (owner 2026-10-31). A second, independent search over the same axes and the same models as
rf2_variants.py: multi-objective NSGA-II (maximise continuous-boost runtime, coin depth and 0.1 g gold depth; minimise the mass change), with every
broken rule as a constraint (Optuna's constraints_func: a variant that breaks a rule is infeasible but still recorded, nothing is excluded from
the record). It reports the feasible Pareto front, the variants it found that the engine's own search never evaluated, and whether any of them
dominates the engine's best no-break variant. Writes rf2/results/rf2_variant_optuna.json.   usage: python3 rf2/rf2_variant_optuna.py [--trials 3000]"""
import os, sys, json, csv, gzip, argparse, time
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
import optuna
import rf2_variants as V
optuna.logging.set_verbosity(optuna.logging.WARNING)

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--trials", type=int, default=3000); ap.add_argument("--seed", type=int, default=7); a = ap.parse_args(argv)
    t0 = time.time(); ctx = V.Ctx(); opt = {ax["name"]: {o["id"]: o for o in ax["options"]} for ax in V.AXES}; rec = {}
    def objective(trial):
        cmb = {ax["name"]: trial.suggest_categorical(ax["name"], [o["id"] for o in ax["options"]]) for ax in V.AXES}
        P = {}; [P.update(opt[k][v]["p"]) for k, v in cmb.items()]; m = V.evaluate_combo(ctx, P)
        if m is None:
            trial.set_user_attr("nb", 99); return 0.0, 0.0, 0.0, 1e4
        nb = len(m["breaks"]); trial.set_user_attr("nb", nb)
        rec["|".join(f"{k}={v}" for k, v in cmb.items())] = dict(combo=cmb, nb=nb, breaks=[f"{b['rule']} at {b['where']}" for b in m["breaks"]], boost_h=m["runtime_boost_h"],
                                                                  coin=m["depth_cm"]["coin_25mm_silver"], g1=m["depth_cm"]["gold_1g"], g01=m["depth_cm"]["gold_0p1g"], mass=m["mass_delta_g"])
        return m["runtime_boost_h"], m["depth_cm"]["coin_25mm_silver"], m["depth_cm"]["gold_0p1g"], m["mass_delta_g"]
    sampler = optuna.samplers.NSGAIISampler(seed=a.seed, population_size=80, constraints_func=lambda t: [float(t.user_attrs.get("nb", 99))])
    st = optuna.create_study(directions=["maximize", "maximize", "maximize", "minimize"], sampler=sampler)
    st.optimize(objective, n_trials=a.trials)
    feas = [t for t in st.best_trials if t.user_attrs.get("nb", 99) == 0]
    seen = set()
    try:
        with gzip.open(os.path.join(OUT, "rf2_variants_all.csv.gz"), "rt") as fh:
            rd = csv.DictReader(fh); seen = set("|".join(f"{ax['name']}={r[ax['name']]}" for ax in V.AXES) for r in rd)
    except Exception: pass
    eng = json.load(open(os.path.join(OUT, "rf2_variants.json"))); eb = eng["champions"]["score"]["no_break"]
    ebr = next((r for r in eng["rows_kept"] if r["id"] == eb), None)
    front = []
    for t in feas:
        cid = "|".join(f"{k}={v}" for k, v in t.params.items()); r = rec.get(cid, {})
        front.append(dict(id=cid, differs={k: v for k, v in t.params.items() if v != V.TODAY[k]}, boost_h=t.values[0], coin=t.values[1], g01=t.values[2], mass=t.values[3], new_vs_engine=cid not in seen))
    dom = []
    if ebr:
        e = (ebr["runtime_boost_h"], ebr["depth_cm"]["coin_25mm_silver"], ebr["depth_cm"]["gold_0p1g"], -ebr["mass_delta_g"])
        for f in front:
            v = (f["boost_h"], f["coin"], f["g01"], -f["mass"])
            if all(x >= y for x, y in zip(v, e)) and any(x > y for x, y in zip(v, e)): dom.append(f["id"])
    res = dict(status="MODELED Optuna NSGA-II search (independent of the engine's own search); broken rules are constraints", trials=a.trials, run_s=round(time.time() - t0, 1),
               n_distinct=len(rec), n_feasible_front=len(front), n_new_vs_engine=sum(f["new_vs_engine"] for f in front), engine_best_no_break=eb,
               dominating_engine_best=dom, front=sorted(front, key=lambda f: (-f["g01"], -f["boost_h"]))[:60])
    json.dump(res, open(os.path.join(OUT, "rf2_variant_optuna.json"), "w"), indent=1, default=float)
    print(f"{a.trials} trials, {len(rec)} distinct, feasible front {len(front)}, new vs engine {res['n_new_vs_engine']}, dominate engine best {len(dom)} in {res['run_s']} s")
    for f in res["front"][:6]: print(round(f["g01"], 1), round(f["coin"], 1), f["boost_h"], f["mass"], f["differs"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
