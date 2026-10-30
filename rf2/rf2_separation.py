#!/usr/bin/env python3
"""RF2 multi-target separation (2026-10-30, owner: two pieces of gold close together at different depths - can the firmware tell them apart, and how is it shown?). MODELED.
Two independent handles, both available in the design:
  1. DECAY TIME (one pulse, full waveform): the AD7389-4 records the whole decay every 0.5 us from 13.5 us (rf2_decaylib grid); the sum of two targets is a sum of decays.
     A non-negative least-squares fit over a grid of 80 decay constants (3 us - 3 ms) finds the components; two targets are 'resolved' when two peaks come back within 30 %
     of the true decay constants, each by a different component (within half the log-spacing of the pair). Monte Carlo: 30 noise draws per case. The weaker target's first-sample amplitude over the noise sets the SNR.
  2. POSITION (the sweep): as the head passes, each target's mono response follows |B|^2 of the rim coil at its depth (transmit and receive on the same coil); the gyro gives the
     head position at every pulse (rf2_ui / STAGE3_PARTS). Two targets are resolved when the summed response has two maxima with a dip of at least 10 % between them.
     The minimum lateral separation is found for several depth / size pairs. The rim coil is a single loop of radius 111 mm (its mean winding radius); the quadrupole bearing
     channels, which separate targets on opposite sides of the head even closer, are not modeled here.
The firmware combines both: a target list (position, depth from the response width and the amplitude ratio, decay class, confidence) drives rf2_display.py (one blob per target).
Writes rf2/results/rf2_separation.json.   usage: python3 rf2/rf2_separation.py"""
import os, json, math
import numpy as np
from scipy.optimize import nnls
from scipy.special import ellipk, ellipe
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "rf2", "results"); os.makedirs(OUT, exist_ok=True)
T = np.arange(13.5e-6, 513e-6, 0.5e-6); TAUS = np.logspace(math.log10(3e-6), math.log10(3e-3), 80); BASIS = np.exp(-T[:, None] / TAUS[None, :])
def decompose(v):
    w, _ = nnls(BASIS, v); pk = [i for i in range(1, len(w) - 1) if w[i] > w[i - 1] and w[i] >= w[i + 1] and w[i] > 0.02 * w.max()]
    if w[0] > w[1] and w[0] > 0.02 * w.max(): pk = [0] + pk
    # merge each peak's neighbourhood into one component (weighted log-mean)
    comps = []
    for i in pk:
        lo, hi = max(0, i - 3), min(len(w), i + 4); ww = w[lo:hi]; comps.append(float(np.exp(np.sum(ww * np.log(TAUS[lo:hi])) / ww.sum())))
    return comps
def decompose_bic(v, sig):
    """model selection: fit one and two decays (non-negative amplitudes, decay constants 3 us - 3 ms) and keep two only if the Bayesian information criterion improves by
    more than 10 (strong evidence); starting points from the NNLS components. Returns the decay constants kept."""
    from scipy.optimize import least_squares
    n = len(v); best = {}
    seeds = decompose(v) or [30e-6]
    def fit(k, init):
        x0 = np.concatenate([np.log(np.clip(init, 3.1e-6, 2.9e-3)), np.clip(np.log(np.full(k, max(v[0], 1e-12) / k)), -39, 19)])
        f = lambda p: (np.exp(-T[:, None] / np.exp(p[:k])[None, :]) @ np.exp(p[k:]) - v) / sig
        r = least_squares(f, x0, bounds=(np.concatenate([np.full(k, math.log(3e-6)), np.full(k, -40)]), np.concatenate([np.full(k, math.log(3e-3)), np.full(k, 20)])))
        return float(np.sum(r.fun ** 2)), list(np.exp(r.x[:k]))
    c1, t1 = fit(1, [seeds[0]]); c2, t2 = fit(2, (seeds + [seeds[0] * 3])[:2] if len(seeds) >= 2 else [seeds[0] / 2, seeds[0] * 2])
    bic1 = c1 + 2 * math.log(n); bic2 = c2 + 4 * math.log(n)
    return t2 if bic1 - bic2 > 10 else t1
def decay_case(tau1, tau2, snr_weak, a_ratio=1.0, n=30, seed=0, method="nnls"):
    rng = np.random.default_rng(seed); ok = 0
    for _ in range(n):
        a2 = 1.0; a1 = a_ratio; sig = a2 * math.exp(-T[0] / tau2) / snr_weak
        v = a1 * np.exp(-T / tau1) + a2 * np.exp(-T / tau2) + rng.normal(0, sig, len(T)); c = decompose(v) if method == "nnls" else decompose_bic(v, sig)
        tol = 0.5 * math.log(max(tau1, tau2) / min(tau1, tau2)) if tau1 != tau2 else 0.3              # half the log-spacing: one component cannot match both
        m1 = [x for x in c if abs(math.log(x / tau1)) < tol]; m2 = [x for x in c if abs(math.log(x / tau2)) < tol]
        if tau1 == tau2: ok += len(c) >= 2                                                               # single-target case: count false splits
        elif m1 and m2 and set(m1).isdisjoint(m2): ok += 1
    return ok / n
def loop_B2(x, z, a=0.111):
    """|B|^2 of a 1 A circular loop of radius a (axis z) at radial offset x and depth z below the loop plane (relative units)"""
    rho = np.maximum(np.abs(x), 1e-9); m = 4 * a * rho / ((a + rho) ** 2 + z ** 2); K, E = ellipk(m), ellipe(m); d = np.sqrt((a + rho) ** 2 + z ** 2)
    Bz = (K + (a ** 2 - rho ** 2 - z ** 2) / ((a - rho) ** 2 + z ** 2) * E) / d
    Br = (z / rho) * (-K + (a ** 2 + rho ** 2 + z ** 2) / ((a - rho) ** 2 + z ** 2) * E) / d
    return Bz ** 2 + Br ** 2
def resolved(sep, z1, z2, A1, A2):
    x = np.linspace(-0.6, 0.6 + sep, 2401); r = A1 * loop_B2(x, z1) + A2 * loop_B2(x - sep, z2)
    pk = [i for i in range(1, len(r) - 1) if r[i] > r[i - 1] and r[i] >= r[i + 1]]
    pk = sorted(pk, key=lambda i: -r[i])[:2]
    if len(pk) < 2: return False
    i, j = sorted(pk); dip = r[i:j + 1].min(); return dip <= 0.9 * min(r[i], r[j])
def min_sep(z1, z2, A1, A2):
    for s in np.arange(0.01, 0.8, 0.005):
        if resolved(s, z1, z2, A1, A2) and all(resolved(s2, z1, z2, A1, A2) for s2 in (s + 0.01, s + 0.02)): return round(float(s) * 1000, 0)
    return None
def main():
    res = dict(status="MODELED: exponential decays and a single-loop |B|^2 response; no ground, no quadrupole channels; target strength A taken proportional to the mass of the same metal (ASSUMED)")
    rows = []
    for ratio in (1.3, 1.6, 2.0, 3.0, 5.0):
        for snr in (10, 30, 100, 300):
            rows.append(dict(tau_ratio=ratio, snr_weaker=snr, p_resolved=decay_case(30e-6, 30e-6 * ratio, snr, seed=int(ratio * 100 + snr))))
    res["decay_time"] = rows
    res["false_split_single_target"] = {str(snr): decay_case(30e-6, 30e-6, snr, seed=7 + snr) for snr in (10, 30, 100, 300)}
    rows_b = [dict(tau_ratio=ratio, snr_weaker=snr, p_resolved=decay_case(30e-6, 30e-6 * ratio, snr, seed=int(ratio * 100 + snr), method="bic"))
              for ratio in (1.3, 1.6, 2.0, 3.0, 5.0) for snr in (10, 30, 100, 300)]
    res["decay_time_with_model_selection"] = rows_b
    res["false_split_single_target_with_model_selection"] = {str(snr): decay_case(30e-6, 30e-6, snr, seed=7 + snr, method="bic") for snr in (10, 30, 100, 300)}
    pairs = [("two 1 g gold, both 100 mm", 0.10, 0.10, 1.0, 1.0), ("1 g at 100 mm + 1 g at 200 mm", 0.10, 0.20, 1.0, 1.0), ("0.5 g at 80 mm + 5 g at 220 mm", 0.08, 0.22, 0.5, 5.0),
             ("two 5 g, both 250 mm", 0.25, 0.25, 5.0, 5.0), ("1 g at 50 mm + 1 g at 150 mm", 0.05, 0.15, 1.0, 1.0)]
    res["position"] = [dict(case=n, min_separation_mm=min_sep(z1, z2, a1, a2)) for n, z1, z2, a1, a2 in pairs]
    def need(snr):
        ok = [r["tau_ratio"] for r in rows if r["snr_weaker"] == snr and r["p_resolved"] >= 0.8]; return min(ok) if ok else None
    def need_b(snr):
        ok = [r["tau_ratio"] for r in rows_b if r["snr_weaker"] == snr and r["p_resolved"] >= 0.8]; return min(ok) if ok else None
    res["summary"] = dict(decay_ratio_needed_for_80pct={str(s): need(s) for s in (10, 30, 100, 300)}, with_model_selection={str(s): need_b(s) for s in (10, 30, 100, 300)},
                          false_split_nnls=res["false_split_single_target"], false_split_model_selection=res["false_split_single_target_with_model_selection"],
                          note="same metal and size give the same decay: those can only be split by position; different sizes / metals differ in decay and can be split in one pulse when the ratio and SNR allow")
    json.dump(res, open(os.path.join(OUT, "rf2_separation.json"), "w"), indent=1); print(json.dumps(res["summary"], indent=1)); print(json.dumps(res["position"], indent=1))
    for r in rows: print(r)
    return res
if __name__ == "__main__":
    main()
