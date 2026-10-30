#!/usr/bin/env python3
"""RF2 step 3 (2026-10-29): mineralised ground and how to cancel it. MODELED; same target / noise physics as rf2_receiver_combo.py.

Ground model (Born approximation, uniform magnetically viscous half-space below the head; ASSUMED parameters, swept):
  emf_g(t) = I chi_v / mu0 * G(h, tilt) * [t^-a - (t + T)^-a] * t0^(a-1),  G = integral over the ground of Bt . Br (per ampere each), T = on-time.
  chi_v = viscous susceptibility per unit ln(time): 0 / 2e-6 (mild) / 2e-5 (moderate) / 2e-4 (severe), ASSUMED from the order of magnitude of
  frequency-dependent susceptibility in magnetic soils (not verified here). Variation while sweeping (what a fixed balance cannot remove):
  head height h 15-45 mm, tilt |N(0, 3 deg)| in a random direction, decay exponent a = 1 +- 0.03, patchy amplitude x lognormal(0, 0.3).
Target: gold sphere step-off response with the finite on-time factor (1 - exp(-n^2 T / tau)) per mode. Pulses per decision: 100, split between modes.
Detector: optimal linear (whitened matched filter) over all data blocks: SINR = s' R^-1 s, R = noise + E[g g'] (ground second moment over the variation
samples); "raw" = matched filter for noise only (no ground model). Detection at SINR >= 9 (amplitude SNR 3, as before).
Heads: PROPOSED = rim mono (TX A, also the mono receiver) + QA / QB quadrupole boards; dual TX adds an inner coil B (r 50-60 mm); PWM = a current-
regulated flat-top that makes a second, longer on-time (multi-period). SDC 2300-class = 8 in mono with our electronics and multi-period balance.
usage: python3 rf2/rf2_ground.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
OUT = C.OUT; mu0 = C.mu0; NOISE = 1.7e-9; NP = 100; RNG = np.random.default_rng(7)
T_FLAT = 300e-6                                                       # PWM flat-top added for the long period
CHI = {"none": 0.0, "mild 2e-6": 2e-6, "moderate 2e-5": 2e-5, "severe 2e-4": 2e-4}
TF = 15e-6; GATES = np.array([TF * 1.618 ** k for k in range(9)])       # mono-class first gate (ASSUMED, as rf2_receiver_combo)
def mono_turns(r_out, n): return [(r_out - (j % 3) * C.PITCH, C.Z_TX0 + (j // 3) * C.PITCH, 1) for j in range(n)]
def coil_for_L(r_out, L_t=300e-6, rings=None):
    n = 6
    while C.L_turns(rings(n) if rings else mono_turns(r_out, n)) < L_t: n += 1
    return rings(n) if rings else mono_turns(r_out, n)
# ---------------------------------------------------------------- coils
TA = coil_for_L(C.R_OUT)                                               # proposed rim mono (TX and mono RX)
TB = coil_for_L(None, rings=lambda n: [(0.060 - (j % 3) * C.PITCH, C.Z_TX0 + (j // 3) * C.PITCH, 1) for j in range(n)])   # inner TX for the dual-TX option
TS = coil_for_L(0.1016 - 0.004)                                        # SDC 2300-class 8 in mono (ASSUMED internals)
def coil(T):
    L = C.L_turns(T); I = math.sqrt(2 * C.E0 / L); R = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU
    return dict(T=T, L=L, I=I, R=R, T1=L * I / C.VBUS)
COILS = {"A": coil(TA), "B": coil(TB), "S": coil(TS)}
QA = C.QUAD
QB = [np.c_[(p[:, 0] - p[:, 1]) / math.sqrt(2), (p[:, 0] + p[:, 1]) / math.sqrt(2), p[:, 2]] for p in C.QUAD]          # QB: QA turned 45 deg
def Bfield(name, P):
    if name in COILS: return C.B_turns(COILS[name]["T"], P)
    return C.B_paths({"QA": QA, "QB": QB}[name], P)
# ---------------------------------------------------------------- ground integrals G(h, tilt) by columns with cumulative z integrals
XY = np.concatenate([np.linspace(-0.6, -0.2, 6), np.arange(-0.18, 0.1801, 0.01), np.linspace(0.2, 0.6, 6)])
ZG = -np.geomspace(0.8, 0.002, 160)                                     # ascending z (deep -> shallow)
COLS = np.array([[x, y] for x in XY for y in XY]); W = np.gradient(XY); DA = np.array([wx * wy for wx in W for wy in W])
def ground_tables(pairs):
    P = np.array([[x, y, z] for x, y in COLS for z in ZG]); fields = {}
    for n in {p for pr in pairs for p in pr}:
        t0 = time.time(); fields[n] = Bfield(n, P); print("field", n, round(time.time() - t0, 1), "s", flush=True)
    tab = {}
    for tx, rx in pairs:
        f = np.einsum("ij,ij->i", fields[tx], fields[rx]).reshape(len(COLS), len(ZG))
        F = np.concatenate([np.zeros((len(COLS), 1)), np.cumsum(0.5 * (f[:, 1:] + f[:, :-1]) * np.diff(ZG)[None, :], axis=1)], axis=1)
        tab[(tx, rx)] = F
    return tab
def G_of(F, h, th, ph):
    zs = np.clip(-h + np.tan(th) * (COLS[:, 0] * math.cos(ph) + COLS[:, 1] * math.sin(ph)), ZG[0], ZG[-1])
    k = np.clip(np.searchsorted(ZG, zs) - 1, 0, len(ZG) - 2); w = (zs - ZG[k]) / (ZG[k + 1] - ZG[k])
    v = F[np.arange(len(COLS)), k] * (1 - w) + F[np.arange(len(COLS)), k + 1] * w
    return float(np.sum(v * DA))
# ---------------------------------------------------------------- data blocks: (tx, period, rx); gate responses
def gate_avg(fn):
    out = []
    for tc in GATES:
        Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 30); out.append(fn(tt).mean())
    return np.array(out)
def sphere_shape(a, T):
    tau = mu0 * 4.1e7 * a ** 2 / np.pi ** 2; n = np.arange(1, 40)[:, None]
    return gate_avg(lambda t: np.sum(np.exp(-(n ** 2) * t[None, :] / tau) * (1 - np.exp(-(n ** 2) * T / tau)), axis=0) / tau)
def ground_shape(a_exp, T, t0=1e-4): return gate_avg(lambda t: (t ** -a_exp - (t + T) ** -a_exp) * t0 ** (a_exp - 1))
def period(tx, p): c = COILS[tx]; return c["T1"] if p == 1 else c["T1"] + T_FLAT
SAMPLES = [dict(h=RNG.uniform(0.015, 0.045), th=abs(RNG.normal(0, math.radians(3))), ph=RNG.uniform(0, 2 * math.pi), a=RNG.normal(1, 0.03), s=RNG.lognormal(0, 0.3)) for _ in range(240)]
def build(blocks, tab, chi):
    modes = sorted({(tx, p) for tx, p, rx in blocks}); npm = NP / len(modes); nb = len(GATES)
    sig = np.concatenate([[NOISE * math.sqrt(1 / (2 * 0.5 * tc)) / math.sqrt(npm) for tc in GATES] for _ in blocks])
    Rn = np.diag(sig ** 2)
    Gs = []
    for smp in SAMPLES:
        g = []
        for tx, p, rx in blocks:
            I = COILS[tx]["I"]; G = G_of(tab[(tx, rx)], smp["h"], smp["th"], smp["ph"])
            g.append(I * chi * smp["s"] / mu0 * G * ground_shape(smp["a"], period(tx, p)))
        Gs.append(np.concatenate(g))
    Gs = np.array(Gs); Rg = Gs.T @ Gs / len(Gs)
    return Rn, Rg, Gs
TGT_LAT = np.array([[x, y] for x in (-0.1, -0.05, 0, 0.05, 0.1) for y in (-0.1, -0.05, 0, 0.05, 0.1)])
DEP = np.array([0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6])
_TF = {}
def tfield(name):
    if name not in _TF:
        P = np.array([[x, y, -d] for d in DEP for x, y in TGT_LAT]); _TF[name] = Bfield(name, P).reshape(len(DEP), len(TGT_LAT), 3)
    return _TF[name]
def depth(blocks, Rn, Rg, grams, raw=False):
    a = (3 * grams * 1e-3 / (4 * np.pi * 19300)) ** (1 / 3); R = Rn + Rg; Ri = np.linalg.pinv(R, rcond=1e-14, hermitian=True); best = []
    shapes = {(tx, p): sphere_shape(a, period(tx, p)) for tx, p, rx in blocks}
    for di in range(len(DEP)):
        cp = {(tx, rx): COILS[tx]["I"] * np.einsum("ij,ij->i", tfield(tx)[di], tfield(rx)[di]) for tx, p, rx in blocks}
        m = 0.0
        for k in range(len(TGT_LAT)):
            s = np.concatenate([(2 * np.pi * a ** 3 / mu0) * (6 / np.pi ** 2) * cp[(tx, rx)][k] * shapes[(tx, p)] for tx, p, rx in blocks])
            v = (s @ s) ** 2 / (s @ R @ s) if raw else float(s @ Ri @ s)
            m = max(m, v)
        best.append(m)
    best = np.array(best)
    for k in range(len(DEP) - 1):
        if best[k] >= 9 and best[k + 1] < 9:
            f = (math.log(best[k]) - math.log(9)) / (math.log(best[k]) - math.log(best[k + 1])); return round((DEP[k] + f * (DEP[k + 1] - DEP[k])) * 1000)
    return round(DEP[-1] * 1000) if best[-1] >= 9 else (0 if best[0] < 9 else round(DEP[0] * 1000))
DETECTORS = {
    "D1 mono, no ground balance":                     ([("A", 1, "A")], True),
    "D2 mono, time-domain balance (optimal gates)":   ([("A", 1, "A")], False),
    "D3 mono, multi-period (PWM flat-top) balance":   ([("A", 1, "A"), ("A", 2, "A")], False),
    "D4 quadrupole pair only, no balance":            ([("A", 1, "QA"), ("A", 1, "QB")], True),
    "D5 mono + QA + QB, space-time balance":          ([("A", 1, "A"), ("A", 1, "QA"), ("A", 1, "QB")], False),
    "D6 D5 + multi-period (PWM)":                     ([(tx, p, rx) for p in (1, 2) for tx, rx in (("A", "A"), ("A", "QA"), ("A", "QB"))], False),
    "D7 D6 + dual transmit (inner coil B)":           ([(tx, p, rx) for p in (1, 2) for tx in ("A", "B") for rx in ("A", "QA", "QB")], False),
    "SDC 2300-class 8 in mono, multi-period balance": ([("S", 1, "S"), ("S", 2, "S")], False)}
if __name__ == "__main__":
    t0 = time.time(); g_ = globals()
    pairs = sorted({(tx, rx) for bl, _ in DETECTORS.values() for tx, p, rx in bl})
    tab = ground_tables(pairs)
    Glevel = {f"{tx}->{rx}": dict(level_25mm=G_of(tab[(tx, rx)], 0.025, 0, 0), tilt3deg_25mm=G_of(tab[(tx, rx)], 0.025, math.radians(3), 0), h15=G_of(tab[(tx, rx)], 0.015, 0, 0), h45=G_of(tab[(tx, rx)], 0.045, 0, 0)) for tx, rx in pairs}
    res = dict(status="MODELED (RF2 step 3: ground; ASSUMED ground parameters, swept)", coils={k: dict(turns=len(v["T"]), L_uH=round(v["L"] * 1e6), I_A=round(v["I"], 2), T1_us=round(v["T1"] * 1e6, 1),
               R_ohm=round(v["R"], 3), flat_top_I2R_W_at_200Hz=round(v["I"] ** 2 * v["R"] * T_FLAT * 200, 2)) for k, v in COILS.items()},
               ground_G_T2m3_per_A2={k: {kk: float(f"{vv:.4g}") for kk, vv in v.items()} for k, v in Glevel.items()}, depth_mm={})
    print("G", json.dumps(res["ground_G_T2m3_per_A2"]), flush=True)
    for gname, chi in CHI.items():
        res["depth_mm"][gname] = {}
        for dn, (bl, raw) in DETECTORS.items():
            Rn, Rg, _ = build(bl, tab, chi)
            res["depth_mm"][gname][dn] = {f"{g} g": depth(bl, Rn, Rg, g, raw) for g in (1.0, 5.0)}
        print(gname, json.dumps(res["depth_mm"][gname]), flush=True)
    # ground-exponent tracking: the depth lost to ground comes from the exponent spread (a = 1 +- 0.03 across the sweep); a firmware tracker that follows a
    # locally narrows the spread the balance must cover. Severe ground, D3 (mono multi-period) and D6 (+ quadrupoles).
    keep = list(SAMPLES); res["exponent_tracking_severe"] = {}
    for sd in (0.03, 0.01, 0.003, 0.0):
        SAMPLES[:] = [dict(sm, a=1 + (sm["a"] - 1) * (sd / 0.03)) for sm in keep]
        row = {}
        for dn in ("D3 mono, multi-period (PWM flat-top) balance", "D6 D5 + multi-period (PWM)", "SDC 2300-class 8 in mono, multi-period balance"):
            bl, raw = DETECTORS[dn]; Rn, Rg, _ = build(bl, tab, CHI["severe 2e-4"]); row[dn] = {f"{g} g": depth(bl, Rn, Rg, g, raw) for g in (1.0, 5.0)}
        res["exponent_tracking_severe"][f"a spread {sd}"] = row; print("tracking", sd, json.dumps(row), flush=True)
    SAMPLES[:] = keep
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(OUT, "rf2_ground.json"), "w"), indent=1, default=float); print("done", res["seconds"])
