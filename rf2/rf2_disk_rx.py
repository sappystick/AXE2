#!/usr/bin/env python3
"""RF2 step 8 (2026-10-29, owner idea): separate the jobs. The rim coil only transmits; a large DISC receive coil on the base board (inside the rim)
only receives, unnulled (no bucking). MODELED; same chain and fairness as rf2_receiver_combo / rf2_timing (energy per pulse 10.8 mJ, gold spheres,
noise-limited, no ground; the uniform-ground pickup is reported per channel).

Receive patterns (circular turns at z 2 mm, board traces 0.5 mm wide, 2 oz copper; self-capacitance 150 pF ASSUMED; critically damped):
  DISC      turns evenly spaced in radius, r 15-100 mm          SUNFLOWER  equal area per turn (r^2 linear, the Fermat rule of the repo's formers)
  OUTER     ring r 85-100 mm                                    INNER      r 15-60 mm
  each with 24 and 48 turns.
Noise per receive channel: preamp 1.7 nV/rtHz + the coil's resistance 4kTR + its damping resistor seen through the coil at 30 kHz (ASSUMED
representative of the gates). First gate per channel from the coupled turn-off (transmit coil with clamp and diodes, receive coil linear with its
damping), clean below 100 nV, plus 2 us preamp recovery (ASSUMED). The mono channel (the rim coil itself) is kept as a second channel; both channels
together combine SNR in quadrature (independent noise).
usage: python3 rf2/rf2_disk_rx.py"""
import os, sys, json, math, time
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
import rf2_ground as G
kT4 = 4 * 1.380649e-23 * 300; EN_PRE = 1.7e-9; CRX = 150e-12; F_N = 30e3; CLEAN = 1e-7; PREAMP_REC = 2e-6
TRACE_A = 0.5e-3 * 70e-6
A = G.COILS["A"]
def rx_pattern(kind, n):
    if kind == "DISC": rs = np.linspace(0.015, 0.100, n)
    elif kind == "SUNFLOWER": rs = np.sqrt(np.linspace(0.015 ** 2, 0.100 ** 2, n))
    elif kind == "OUTER": rs = np.linspace(0.085, 0.100, n)
    else: rs = np.linspace(0.015, 0.060, n)
    return [(float(r), C.Z_RX, 1) for r in rs]
def noise_of(L, R):
    Rd = 0.5 * math.sqrt(L / CRX); w = 2 * math.pi * F_N * L
    return math.sqrt(EN_PRE ** 2 + kT4 * R + kT4 * Rd * (w / math.hypot(Rd, w)) ** 2), Rd
def first_gates(Lb, Rb, Rdb, M):
    """coupled turn-off: A switches off at I_A through its clamp; B (receive) is linear with Rd and C. Returns the clean times of A's and B's voltages."""
    LA = A["L"]; Lm = np.array([[LA, M], [M, Lb]]); Li = np.linalg.inv(Lm); RdA = 0.5 * math.sqrt(LA / C.CN)
    def dA(y): return max(0.0, y[2] - y[4] - C.VF) / C.RON1
    def rhs(t, y):
        iA, iB, vA, vB, vc = y; d = dA(y); di = Li @ np.array([-vA - A["R"] * iA, -vB - Rb * iB])
        return [di[0], di[1], (iA - vA / RdA - d) / C.CN, (iB - vB / Rdb) / CRX, (d - vc / C.RCL1) / C.CL1]
    s = solve_ivp(rhs, [0, 40e-6], [A["I"], 0, 0, 0, 450.0], t_eval=np.linspace(0, 40e-6, 8001), method="Radau", rtol=1e-10, atol=[1e-9, 1e-9, 1e-7, 1e-7, 1e-6], max_step=5e-9)
    on = np.array([dA(s.y[:, k]) > 0 for k in range(s.y.shape[1])]); last = s.t[np.where(on)[0][-1]] if on.any() else 0.0
    k0 = int(np.searchsorted(s.t, last + 0.2e-6)); t0, x0 = s.t[k0], s.y[:4, k0]
    Am = np.zeros((4, 4)); Am[0:2, 0:2] = -Li @ np.diag([A["R"], Rb]); Am[0:2, 2:4] = -Li; Am[2, 0] = 1 / C.CN; Am[2, 2] = -1 / (RdA * C.CN); Am[3, 1] = 1 / CRX; Am[3, 3] = -1 / (Rdb * CRX)
    tt = t0 + np.linspace(0, 80e-6, 8001); X = np.array([expm(Am * (t - t0)) @ x0 for t in tt])
    def clean(v): b = np.where(np.abs(v) > CLEAN)[0]; return float(tt[b[-1] + 1]) if len(b) else float(tt[0])
    peakB = float(np.max(np.abs(s.y[3])))
    return clean(X[:, 2]) + PREAMP_REC, clean(X[:, 3]) + PREAMP_REC, peakB
def snr_curve(Bt, I, tf, grams, Br, en):
    a = C.sphere_a(grams); out = []
    for d in C.DEPTHS:
        P = np.c_[C.GRID[:, 0], C.GRID[:, 1], np.full(len(C.GRID), -d)]; cp = I * np.einsum("ij,ij->i", Bt(P), Br(P)); best = np.zeros(len(cp))
        K = (2 * np.pi * a ** 3 / C.mu0) * (6 / np.pi ** 2) * cp
        for kk in range(9):
            tc = tf * 1.618 ** kk; Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 40); shape = C.vt(tt, a, 1.0).mean()
            best = np.maximum(best, np.abs(K * shape) / (en * math.sqrt(1 / (2 * Tg)) / math.sqrt(C.NAVG)))
        out.append(best)                                                  # per lateral position, best gate
    return np.array(out)                                                  # depths x positions
def depth_from(sn):
    s = sn.max(axis=1)
    for k in range(len(C.DEPTHS) - 1):
        if s[k] >= 3 and s[k + 1] < 3:
            f = (math.log(s[k]) - math.log(3)) / (math.log(s[k]) - math.log(s[k + 1])); return round((C.DEPTHS[k] + f * (C.DEPTHS[k + 1] - C.DEPTHS[k])) * 1000)
    return round(C.DEPTHS[-1] * 1000) if s[-1] >= 3 else 0
def ground_rel(Bt, Br):
    xs = np.linspace(-0.6, 0.6, 41); zs = -(np.geomspace(0.01, 0.6, 28)) - 0.025; dz = np.abs(np.gradient(zs)); tot = 0.0
    for z, w in zip(zs, dz):
        P = np.array([[x, y, z] for x in xs for y in xs]); tot += float(np.sum(np.einsum("ij,ij->i", Bt(P), Br(P)))) * (xs[1] - xs[0]) ** 2 * w
    P = np.c_[C.GRID[:, 0], C.GRID[:, 1], np.full(len(C.GRID), -0.15)]; tgt = float(np.max(np.abs(np.einsum("ij,ij->i", Bt(P), Br(P)))))
    return abs(tot) / tgt
if __name__ == "__main__":
    t0 = time.time(); TA = A["T"]; Bt = lambda P: C.B_turns(TA, P); I = A["I"]; res = dict(status="MODELED (RF2 step 8: separate disc receiver; ASSUMED rx capacitance 150 pF, preamp recovery 2 us)", rows=[])
    en_m, rd_m = noise_of(A["L"], A["R"])
    g_mono = ground_rel(Bt, Bt)
    for kind in ("DISC", "SUNFLOWER", "OUTER", "INNER"):
        for n in (24, 48):
            T = rx_pattern(kind, n); Lb = C.L_turns(T); Rb = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / TRACE_A; en, Rdb = noise_of(Lb, Rb)
            M = float(sum(C.M_coax(ra, za, rb, zb) for ra, za, sa in TA for rb, zb, sb in T))
            tA, tB, pkB = first_gates(Lb, Rb, Rdb, M)
            Br = lambda P, T=T: C.B_turns(T, P)
            snB = snr_curve(Bt, I, tB, 1.0, Br, en); snA = snr_curve(Bt, I, tA, 1.0, Bt, en_m)
            row = dict(pattern=kind, turns=n, L_uH=round(Lb * 1e6), R_ohm=round(Rb, 1), k_to_tx=round(M / math.sqrt(A["L"] * Lb), 3), rx_flyback_peak_V=round(pkB, 1),
                       noise_nV=round(en * 1e9, 2), first_gate_rx_us=round(tB * 1e6, 1), first_gate_mono_us=round(tA * 1e6, 1),
                       depth_1g_mm=dict(disc_rx=depth_from(snB), mono=depth_from(snA), both=depth_from(np.sqrt(snA ** 2 + snB ** 2))),
                       ground_rel_mono=1.0, ground_rel_rx=round(ground_rel(Bt, Br) / g_mono, 2))
            for g in (5.0, 20.0):
                sB = snr_curve(Bt, I, tB, g, Br, en); sA = snr_curve(Bt, I, tA, g, Bt, en_m); row[f"depth_{int(g)}g_mm"] = dict(disc_rx=depth_from(sB), mono=depth_from(sA), both=depth_from(np.sqrt(sA ** 2 + sB ** 2)))
            res["rows"].append(row); print(json.dumps(row), flush=True)
    res["mono_noise_nV"] = round(en_m * 1e9, 2); res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(C.OUT, "rf2_disk_rx.json"), "w"), indent=1, default=float); print("done", res["seconds"])
