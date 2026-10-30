#!/usr/bin/env python3
"""RF2 step 4 (2026-10-29): a firmware-style ground-tracking detector, run on simulated sweeps over mineralised ground. MODELED; reference algorithm
for the head DSP (Python, to be ported to C like fw/ from src/sim/dsp_ref.py). Physics from rf2_ground.py (same coils, ground and target models).

Per frame (one head position, 10 mm of travel, 100 pulses split between the two PWM periods):
  y = [mono T1 | mono T2 | QA (T1 + T2 averaged) | QB (T1 + T2 averaged)] gates  (4 x 9 = 36 numbers; every pulse is received by every coil: the
      quadrupole channels average both periods, which keeps the dimension the tracker must learn small)
  1. ground subspace tracker: EWMA second moment of target-free frames (lambda 0.92), ground covariance = its top-k eigenvectors (k = 3) above the
     known electronic noise; started by a 40-frame "ground pump" (coil bobbed over the ground at switch-on, like a commercial quick-balance).
  2. detector: GLRT over unknown amplitudes per receive channel and a bank of decay constants (12 taus, 10-400 us): T = y' R^-1 S (S' R^-1 S)^-1 S' R^-1 y
     (chi-square, 3 degrees of freedom under ground + noise); silent below the threshold (chi-square 3 dof at a false-alarm rate of 1e-5 per frame: 25.9).
  3. readout: tau at the peak frame -> type class (dsp_ref.py edges 10 / 40 / 200 / 700 us); every frame re-fitted at that tau (amplitude and its
     variance per channel). If the quadrupole pair has signal (amplitude SNR >= 3 in some frame): bearing axis = 0.5 atan2(QB, QA) + 45 deg (calibrated)
     and depth from |quad| / |mono|. Otherwise (deeper than the quadrupole's own range) depth from the WIDTH of the mono response along the sweep
     (half-maximum width, calibrated on noise-free sweeps). Size from the mono peak amplitude at that depth (mass ~ a^3 for a sphere).
  4. output map: LED pixel at the bearing (side from the gyro, not simulated), colour by class, brightness by T; audio tone by class, volume by T.
Learning uses a guard window (frames near any rising signal are not learned). Sweep: x -0.4 .. 0.4 m, target at x 0, y 30 mm; head height 25 mm + smooth noise (sd 8 mm), tilt smooth (sd 2 deg), ground exponent 1 + smooth (sd 0.03),
patchy amplitude x exp(0.3 smooth). usage: python3 rf2/rf2_ground_dsp.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_ground as G
from rf2_ground import mu0, COILS, GATES, NOISE
BLOCKS = [("A", 1, "A"), ("A", 2, "A"), ("A", 12, "QA"), ("A", 12, "QB")]; RXCOL = {"A": 0, "QA": 1, "QB": 2}
NPM = G.NP / 2; NG = len(GATES); THR = 25.9; LAM = 0.97; KEEP = 2.0; LOCK = 25; GUARD = 12; Q_SNR = 5.0
TAUS = np.geomspace(10e-6, 400e-6, 12)
BLOCK_GROUPS = [list(range(0, 2 * 9)), list(range(2 * 9, 4 * 9))]      # mono T1 + T2 | QA + QB (ground tracked per receiver)
SIG = np.concatenate([[NOISE * math.sqrt(1 / (2 * 0.5 * tc)) / math.sqrt(G.NP if p == 12 else NPM) for tc in GATES] for tx, p, rx in BLOCKS]); RN = np.diag(SIG ** 2)
def per(tx, p): return [G.period(tx, 1), G.period(tx, 2)] if p == 12 else [G.period(tx, p)]
def smooth(rng, n, corr=12):
    w = rng.normal(size=n + 4 * corr); k = np.exp(-0.5 * (np.arange(-2 * corr, 2 * corr + 1) / corr) ** 2); v = np.convolve(w, k / np.sqrt(np.sum(k ** 2)), "valid")[:n]
    return v
def tau_shape(tau, T):
    n = np.arange(1, 40)[:, None]
    return G.gate_avg(lambda t: np.sum(np.exp(-(n ** 2) * t[None, :] / tau) * (1 - np.exp(-(n ** 2) * T / tau)), axis=0) / tau)
def S_for(tau):
    S = np.zeros((len(BLOCKS) * NG, 3))
    for b, (tx, p, rx) in enumerate(BLOCKS): S[b * NG:(b + 1) * NG, RXCOL[rx]] = np.mean([tau_shape(tau, T) for T in per(tx, p)], axis=0)
    return S
SB = [S_for(t) for t in TAUS]
def frame_signal(tab, xh, h, th, ph, a_exp, chi, tgt):
    y = []
    for tx, p, rx in BLOCKS:
        I = COILS[tx]["I"]; Gv = G.G_of(tab[(tx, rx)], h, th, ph); y.append(I * chi / mu0 * Gv * np.mean([G.ground_shape(a_exp, T) for T in per(tx, p)], axis=0))
    y = np.concatenate(y)
    if tgt:
        P = np.array([[tgt["x"] - xh, tgt["y"], -(h + tgt["depth"])]]); a = (3 * tgt["g"] * 1e-3 / (4 * np.pi * 19300)) ** (1 / 3)
        Bt = G.Bfield("A", P); amp = {rx: (2 * np.pi * a ** 3 / mu0) * (6 / np.pi ** 2) * COILS["A"]["I"] * float(Bt[0] @ G.Bfield(rx, P)[0]) for rx in ("A", "QA", "QB")}
        tau = mu0 * 4.1e7 * a ** 2 / np.pi ** 2
        y = y + np.concatenate([amp[rx] * np.mean([tau_shape(tau, T) for T in per(tx, p)], axis=0) for tx, p, rx in BLOCKS])
    return y
class Tracker:
    """ground subspace: EWMA second moment of accepted (target-free) frames, top-k eigenvectors kept; R = noise + low-rank ground"""
    def __init__(self): self.M = None
    def update(self, y):
        o = np.outer(y, y); self.M = o if self.M is None else LAM * self.M + (1 - LAM) * o
    def R(self):
        """keep every eigen-direction of the tracked second moment that stands KEEP x above the known electronic noise in that direction (the ground
        occupies about 7 such directions in severe ground: rf2_ground eigen check); x 1.5 margin for drift between updates"""
        R = RN.copy(); self.k = 0
        for blk in BLOCK_GROUPS:                                       # per receiver: the mono's huge ground must not leak estimation error into the quadrupole
            ix = np.ix_(blk, blk); w, V = np.linalg.eigh(self.M[ix]); nv = np.einsum("ij,ij->j", V, RN[ix] @ V); keep = w > KEEP * nv
            self.k += int(keep.sum()); R[ix] += (V[:, keep] * (w[keep] - nv[keep])) @ V[:, keep].T * 1.5
        return R
def glrt(y, R):
    Ri = np.linalg.inv(R); best = (0.0, None, None)
    for t, S in zip(TAUS, SB):
        A = S.T @ Ri @ S; b = S.T @ Ri @ y; amp = np.linalg.solve(A, b); T = float(b @ amp)
        if T > best[0]: best = (T, t, amp)
    return best
CLASS = [(10e-6, "foil / tiny"), (40e-6, "small gold"), (200e-6, "medium gold"), (700e-6, "large gold / coin"), (1e9, "iron / very large")]
def klass(tau): return next(n for e, n in CLASS if tau < e)
def output_map(T, tau, bearing_deg):
    """LED / audio mapping (silent below threshold)"""
    if T < THR: return dict(led=None, audio=None)
    cls = klass(tau); col = {"foil / tiny": "white", "small gold": "yellow", "medium gold": "orange", "large gold / coin": "red", "iron / very large": "blue"}[cls]
    lvl = min(1.0, math.log10(T / THR + 1)); return dict(led=dict(pixel_deg=round(bearing_deg) % 180, colour=col, brightness=round(lvl, 2)), audio=dict(tone=cls, volume=round(lvl, 2)))
res_k = []
XS_SWEEP = np.arange(-0.4, 0.4001, 0.01)                              # head positions of one pass (rf2_pinpoint.py sets a shorter, slower pass)
def sweep(tab, chi, tgt, seed, tracker=None, pump=True, adapt=True, h0=0.025, h_sd=0.008):
    rng = np.random.default_rng(seed); xs = XS_SWEEP; n = len(xs)
    h = h0 + h_sd * smooth(rng, n); th = np.radians(2) * np.abs(smooth(rng, n)); ph = np.pi * smooth(rng, n, 30); ae = 1 + 0.03 * smooth(rng, n, 30); sc = np.exp(0.3 * smooth(rng, n, 20))
    h = np.clip(h, h0 - 0.013, h0 + 0.025)
    trk = tracker or Tracker()
    if pump:                                                         # 80 target-free frames: coil bobbed 12-50 mm and rocked +-4 deg over the ground
        for k in range(80):
            hp = 0.031 + 0.019 * math.sin(k / 3); trk.update(frame_signal(tab, 0, hp, abs(rng.normal(0, math.radians(2.5))), rng.uniform(0, 6.28), 1 + 0.03 * rng.normal(), chi * np.exp(0.3 * rng.normal()), None) + SIG * rng.normal(size=len(SIG)))
    rows = []; run = 0
    for i, xh in enumerate(xs):
        y = frame_signal(tab, xh, h[i], th[i], ph[i], ae[i], chi * sc[i], tgt) + SIG * rng.normal(size=len(SIG))
        T, tau, amp = glrt(y, trk.R())
        rows.append((xh, T, tau, amp, y, trk.R())); run = run + 1 if T >= THR else 0
        # guard window: a frame is learned GUARD frames late, and only if no frame within GUARD of it rose above half the threshold (keeps the weak flanks
        # of a target out of the ground estimate); a signal lasting longer than any target pass (LOCK frames = 250 mm) is ground and is learned anyway
        j = i - GUARD
        if adapt and j >= 0:
            win = [r[1] for r in rows[max(0, j - GUARD):i + 1]]
            if max(win) < 0.5 * THR or run > LOCK: trk.update(rows[j][4])
    res_k.append(trk.k)
    return rows
def width_curve():
    """noise-free mono response along a sweep line (target y 30 mm): half-maximum width per depth"""
    out = []
    for d in (0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
        xs = np.arange(-0.4, 0.4001, 0.01); P = np.c_[-xs, np.full(len(xs), 0.03), np.full(len(xs), -(0.025 + d))]
        m = np.abs(np.einsum("ij,ij->i", G.Bfield("A", P), G.Bfield("A", P))); out.append((d, float(np.sum(m >= 0.5 * m.max()) * 0.01)))
    return out
def readout(rows):
    """per-frame re-fit at the peak tau; quadrupole readouts only where the quadrupole has signal"""
    k = int(np.argmax([r[1] for r in rows])); tau = rows[k][2]; S = SB[int(np.argmin(np.abs(TAUS - tau)))]; A, SNRq = [], []
    for xh, T, _, _, y, R in rows:
        Ri = np.linalg.inv(R); F = S.T @ Ri @ S; cov = np.linalg.inv(F); a = cov @ (S.T @ Ri @ y); A.append(a)
        SNRq.append(math.sqrt(a[1] ** 2 / cov[1, 1] + a[2] ** 2 / cov[2, 2]))
    A = np.array(A); m = np.convolve(np.abs(A[:, 0]), np.ones(3) / 3, "same"); kq = int(np.argmax(SNRq))
    return dict(tau=tau, k=k, mono=A[:, 0], mono_s=m, quad_snr=SNRq[kq], kq=kq, aq=A[kq])
def depth_curve(tab):
    """noise-free calibration: |quad| / |mono| at the mono peak of a level sweep over clean ground, per depth (y offset 30 mm)"""
    out = []
    for d in (0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4):
        best = None
        for xh in np.arange(-0.15, 0.1501, 0.01):
            P = np.array([[0 - xh, 0.03, -(0.025 + d)]]); Bt = G.Bfield("A", P)[0]
            m, qa, qb = (float(Bt @ G.Bfield(rx, P)[0]) for rx in ("A", "QA", "QB"))
            if best is None or abs(m) > best[0]: best = (abs(m), math.hypot(qa, qb) / abs(m))
        out.append((d, best[1], best[0]))
    return out
if __name__ == "__main__":
    t0 = time.time(); tab = G.ground_tables([("A", "A"), ("A", "QA"), ("A", "QB")])
    cal = depth_curve(tab); wcal = width_curve(); res = dict(width_calibration=[dict(depth_mm=round(d * 1e3), width_mm=round(w * 1e3)) for d, w in wcal], status="MODELED (RF2 step 4: firmware-style ground tracking on simulated sweeps; ASSUMED ground)", threshold=THR,
                                       depth_calibration=[dict(depth_mm=round(d * 1e3), quad_over_mono=round(r, 4)) for d, r, m in cal], runs=[])
    def est_depth(r):
        ds, rs = np.array([c[0] for c in cal]), np.array([c[1] for c in cal]); o = np.argsort(rs)
        return float(np.interp(r, rs[o], ds[o]))
    def est_mass(amp_mono, d):
        a1 = (3 * 1e-3 / (4 * np.pi * 19300)) ** (1 / 3); m1 = np.interp(d, [c[0] for c in cal], [c[2] for c in cal])
        k1 = (2 * np.pi * a1 ** 3 / mu0) * (6 / np.pi ** 2) * COILS["A"]["I"] * m1
        return abs(amp_mono) / k1
    cases = [("severe 2e-4", None), ("severe 2e-4", dict(g=1.0, depth=0.10)), ("severe 2e-4", dict(g=1.0, depth=0.15)), ("severe 2e-4", dict(g=1.0, depth=0.20)), ("severe 2e-4", dict(g=5.0, depth=0.25)),
             ("severe 2e-4", dict(g=20.0, depth=0.30)), ("moderate 2e-5", None), ("moderate 2e-5", dict(g=1.0, depth=0.10)), ("moderate 2e-5", dict(g=1.0, depth=0.20)), ("moderate 2e-5", dict(g=5.0, depth=0.28))]
    for gname, tgt in cases:
        for mode in ("tracking", "fixed balance"):
            tg = dict(tgt, x=0.0, y=0.03) if tgt else None
            rows = sweep(tab, G.CHI[gname], tg, seed=11, adapt=(mode == "tracking"))
            Ts = np.array([r[1] for r in rows]); k = int(np.argmax(Ts)); xh, T, tau = rows[k][:3]
            det = T >= THR
            out = dict(ground=gname, target=tgt, detector=mode, ground_dirs_tracked=res_k[-1], detected=bool(det), false_alarm_frames=int(np.sum(Ts >= THR)) if not tgt else None, peak_T=round(T, 1), peak_x_mm=round(xh * 1e3))
            if det:
                ro = readout(rows); mpk = float(ro["mono_s"].max()); width = float(np.sum(ro["mono_s"] >= 0.5 * mpk) * 0.01)
                if ro["quad_snr"] >= Q_SNR:                      # max over ~80 frames of a 2-channel SNR reaches about 3.3 on noise alone
                    aq = ro["aq"]; brg = (math.degrees(0.5 * math.atan2(aq[2], aq[1])) + 45) % 180; d_est = est_depth(math.hypot(aq[1], aq[2]) / abs(aq[0])); how = "quad / mono ratio"
                else:
                    brg = None; wc = np.array([w for w in wcal if w[0] >= 0.16]); how = "mono sweep width"
                    d_est = float(np.interp(width, wc[:, 1], wc[:, 0])) if width > wc[0, 1] else 0.16; how += "" if width > wc[0, 1] else " (width at the coil-size floor: depth <= 160 mm)"
                out.update(tau_us=round(tau * 1e6, 1), cls=klass(tau), quad_snr=round(ro["quad_snr"], 1), bearing_axis_deg=round(brg, 1) if brg is not None else "beyond quadrupole range",
                           depth_method=how, depth_est_mm=round(d_est * 1e3), mono_width_mm=round(width * 1e3), output=output_map(T, tau, brg if brg is not None else 90.0))
                if "floor" in how: out.update(depth_est_mm="<= 160", mass_upper_bound_g=round(est_mass(mpk, d_est), 2))   # shallower than 160 mm means a smaller target for the same signal
                else: out.update(mass_est_g=round(est_mass(mpk, d_est), 2))
            if tgt: out["true_tau_us"] = round(mu0 * 4.1e7 * ((3 * tgt["g"] * 1e-3 / (4 * np.pi * 19300)) ** (1 / 3)) ** 2 / np.pi ** 2 * 1e6, 1)
            res["runs"].append(out); print(json.dumps(out), flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(G.OUT, "rf2_ground_dsp.json"), "w"), indent=1, default=float); print("done", res["seconds"])
