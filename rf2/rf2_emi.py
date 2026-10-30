#!/usr/bin/env python3
"""RF2 step 9 (2026-10-29): external interference (EMI) and how to cancel it, for the rim-mono + quadrupole head. MODELED; interference amplitudes and
spectra are ASSUMED and swept (not measured); receive model as rf2_receiver_combo (noise 1.7 nV/rtHz, 100 pulses per frame at 400 Hz, gates from 16.3 us).

Interference reaches a receive coil as emf = -(N A) . dB/dt (uniform over the head for distant sources):
  mono   N A = sum of the rim coil's turn areas (vertical)                 quad  net N A = 0 by symmetry; a 0.1 % lobe imbalance (ASSUMED) leaks
  REF    3-axis reference coil on the shaft, 0.6 m from the head, N A = 3 x the mono's per axis (so its own noise adds little); an adaptive canceller
         fits its three weights on listen-only frames; the residual is the field difference between REF and head (a line source at 20 m: 3 %).
Sources: POWER LINE 50 Hz + odd/even harmonics to 3 kHz (amplitude 3 %/n of the fundamental), 0.05 uT (rural) and 1 uT (under a line), vertical
component; VLF station, horizontal field (ground wave) seen by the coil through a 3 deg head tilt, 1 nT at 20.000 kHz (an exact multiple of the 400 Hz
pulse rate: coherent, the worst case) and 10 nT at 19.8 kHz; ELECTRIC FENCE 1 pulse/s, 200 us, 10 us edges, 50 nT vertical at 20 m.
Methods: fixed pulse rate or jittered (+-5 % random per pulse, demodulated in step); detector "matched" (ignores interference) or "learned" (whitens with
the interference covariance measured on listen-only frames, which also removes slow offsets); REF canceller off / on; fence pulses blanked or not.
Also: the split-ring (MWO-style) electrostatic shield: eddy decay of a split trace vs a closed ring.
usage: python3 rf2/rf2_emi.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
import rf2_ground as G
RNG = np.random.default_rng(5); NP = 100; PRF = 400.0; TF = 16.3e-6; NFR = 400
GATES = np.array([TF * 1.618 ** k for k in range(9)]); GW = 0.5 * GATES
A = G.COILS["A"]; NA_MONO = float(sum(math.pi * r ** 2 for r, z, s in A["T"]))
def path_area(p): return 0.5 * float(np.sum(p[:-1, 0] * p[1:, 1] - p[1:, 0] * p[:-1, 1]))
QL = [sum(path_area(p) for p in C.QUAD[k * 6:(k + 1) * 6]) for k in range(4)]; NA_QUAD_IMB = 1e-3 * abs(QL[0])
SIG = np.array([C.NOISE_Q * math.sqrt(1 / (2 * g)) / math.sqrt(NP) for g in GW])
EN_REF = 1.9e-9; REF_GAIN = 3.0; RES_LINE = 0.03
def tone_gate(f, B0, phase, t0):
    """gate averages of emf = -NA dB/dt for B = B0 sin(2 pi f t + phase), per pulse starting at t0 (array): returns pulses x gates (per unit NA)"""
    t1 = t0[:, None] + GATES[None, :] - GW[None, :] / 2; t2 = t1 + GW[None, :]
    return -B0 * (np.sin(2 * np.pi * f * t2 + phase) - np.sin(2 * np.pi * f * t1 + phase)) / GW[None, :]
def fence_gate(t0, t_f, B0=50e-9, width=200e-6, edge=10e-6):
    """gate averages of -dB/dt for one trapezoid fence pulse starting at t_f (per unit NA): B rises over `edge`, holds, falls"""
    out = np.zeros((len(t0), len(GATES)))
    def B(t): return B0 * np.clip(np.minimum((t - t_f) / edge, (t_f + width - t) / edge), 0, 1)
    for i, tp in enumerate(t0):
        if tp + GATES[-1] + GW[-1] < t_f or tp > t_f + width: continue
        for g in range(len(GATES)):
            a = tp + GATES[g] - GW[g] / 2; b = a + GW[g]; out[i, g] = -(B(b) - B(a)) / GW[g]
    return out
def pulse_times(jitter):
    T = 1 / PRF; d = T * (1 + (RNG.uniform(-jitter, jitter, NP) if jitter else np.zeros(NP))); return np.concatenate([[0.0], np.cumsum(d)[:-1]])
def emi_frames(src, jitter, ref, blank):
    """per-frame interference (gates) after the chosen processing, for the mono and the quadrupole, NFR frames"""
    mono, quad = [], []
    for _ in range(NFR):
        t0 = pulse_times(jitter) + RNG.uniform(0, 1.0); phase = RNG.uniform(0, 2 * np.pi); e = np.zeros((NP, len(GATES))); keep = np.ones(NP, bool)
        if src["kind"] == "power line":
            for n in range(1, 61):
                b = src["B"] * (1.0 if n == 1 else 0.03 / n); e += tone_gate(50.0 * n, b, phase * n + RNG.uniform(0, 2 * np.pi) * (n > 1), t0)
        elif src["kind"] == "vlf":
            e = tone_gate(src["f"], src["B"] * math.sin(math.radians(3)), phase, t0)
        elif src["kind"] == "fence":
            tf_ = RNG.uniform(t0[0], t0[0] + 1.0)
            if tf_ < t0[-1] + 1 / PRF:
                e = fence_gate(t0, tf_)
                if blank: keep = np.abs(e).sum(axis=1) == 0            # REF / listen-only sees the fence pulse: drop those pulses
        res_factor = (RES_LINE if src["kind"] in ("power line", "fence") else 0.002) if ref else 1.0   # REF residual: gradient for near line sources, 0.2 % for a plane wave
        mono.append(NA_MONO * res_factor * e[keep].mean(axis=0)); quad.append(NA_QUAD_IMB * e[keep].mean(axis=0))
    return np.array(mono), np.array(quad)
def coupling_curve(rx):
    ds = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]); out = []
    for d in ds:
        P = np.c_[C.GRID[:, 0], C.GRID[:, 1], np.full(len(C.GRID), -d)]; out.append(float(np.max(np.abs(np.einsum("ij,ij->i", C.B_turns(A["T"], P), C.B_turns(A["T"], P) if rx == "mono" else C.B_paths(C.QUAD, P))))))
    return ds, np.array(out)
def depth_mm(ds, cp, Remi, sig, learned, grams=1.0, extra_noise=0.0):
    a = C.sphere_a(grams); tau = C.mu0 * 4.1e7 * a ** 2 / np.pi ** 2; n = np.arange(1, 40)[:, None]
    shape = np.array([np.mean(np.sum(np.exp(-(n ** 2) * np.linspace(g - w / 2, g + w / 2, 30)[None, :] / tau), axis=0) / tau) for g, w in zip(GATES, GW)])
    K = (2 * np.pi * a ** 3 / C.mu0) * (6 / np.pi ** 2) * A["I"]; Rn = np.diag((sig * math.sqrt(1 + extra_noise)) ** 2); R = Rn + Remi
    snr = []
    for c in cp:
        s = K * c * shape; snr.append(math.sqrt(s @ np.linalg.solve(R, s)) if learned else (s @ s) / math.sqrt(s @ R @ s))
    snr = np.array(snr)
    for k in range(len(ds) - 1):
        if snr[k] >= 3 and snr[k + 1] < 3:
            f = (math.log(snr[k]) - math.log(3)) / (math.log(snr[k]) - math.log(snr[k + 1])); return round((ds[k] + f * (ds[k + 1] - ds[k])) * 1000)
    return round(ds[-1] * 1000) if snr[-1] >= 3 else 0
def shield_check():
    """split-ring shield (one 3 mm trace, 35 um copper): in-trace eddy time constant vs a CLOSED ring of the same trace at r 100 mm"""
    w, t, sigma, r = 3e-3, 35e-6, 5.8e7, 0.1
    tau_split = C.mu0 * sigma * t * w / np.pi ** 2
    R = (1 / sigma) * 2 * np.pi * r / (w * t); L = C.mu0 * r * (math.log(8 * r / (w / 4)) - 2.0)
    tau_1mm = C.mu0 * sigma * t * 1e-3 / np.pi ** 2
    return dict(split_trace_eddy_tau_us=round(tau_split * 1e6, 3), split_1mm_trace_eddy_tau_us=round(tau_1mm * 1e6, 3), closed_ring_tau_us=round(L / R * 1e6, 2), closed_ring_R_ohm=round(R, 3),
                closed_ring_L_uH=round(L * 1e6, 3), decay_by_first_gate_3mm=float(f"{math.exp(-TF / tau_split):.1e}"),
                note="a closed ring decays in the receive window (6 us) and couples strongly to the coils; a split 3 mm trace's own eddies decay with about 0.8 us "
                     "(a 1 mm trace 0.26 us), down by e^-21 at the 16.3 us first gate (estimate: tau = mu0 sigma t w / pi^2)")
if __name__ == "__main__":
    t0 = time.time(); dsm, cpm = coupling_curve("mono"); dsq, cpq = coupling_curve("quad")
    SRC = {"none": None, "power line rural 0.05 uT": dict(kind="power line", B=0.05e-6), "power line under a line 1 uT": dict(kind="power line", B=1e-6),
           "VLF 1 nT at 20.000 kHz (coherent)": dict(kind="vlf", B=1e-9, f=20000.0), "VLF 10 nT at 19.8 kHz": dict(kind="vlf", B=10e-9, f=19800.0),
           "electric fence 50 nT at 20 m": dict(kind="fence")}
    METHODS = [("matched, fixed rate", 0.0, False, False, False), ("matched, jittered rate", 0.05, False, False, False), ("learned, fixed rate", 0.0, True, False, False), ("learned, jittered rate", 0.05, True, False, False),
               ("learned, jittered + REF canceller", 0.05, True, True, True)]
    res = dict(status="MODELED (RF2 step 9: EMI; ASSUMED interference levels)", NA_mono_m2=round(NA_MONO, 3), NA_quad_imbalance_m2=float(f"{NA_QUAD_IMB:.3g}"), depth_1g_mm={}, shield=shield_check())
    for sname, src in SRC.items():
        row = {}
        for mname, jit, learned, ref, blank in METHODS:
            if src is None: Rm = np.zeros((9, 9)); Rq = Rm
            else:
                m, q = emi_frames(src, jit, ref, blank); Rm = m.T @ m / len(m); Rq = q.T @ q / len(q)
            extra = ((EN_REF / REF_GAIN) / C.NOISE_Q) ** 2 if ref else 0.0      # the REF channel's own noise, scaled by the canceller weight
            row[mname] = dict(mono=depth_mm(dsm, cpm, Rm, SIG, learned, extra_noise=extra), quad=depth_mm(dsq, cpq, Rq, SIG, learned))
        res["depth_1g_mm"][sname] = row; print(sname, json.dumps(row), flush=True)
    res["seconds"] = round(time.time() - t0, 1); print("shield", res["shield"])
    json.dump(res, open(os.path.join(C.OUT, "rf2_emi.json"), "w"), indent=1, default=float); print("done", res["seconds"])
