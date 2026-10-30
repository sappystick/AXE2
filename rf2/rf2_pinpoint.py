#!/usr/bin/env python3
"""RF2 step 6 (2026-10-29): trigger-held pinpoint. After a detection the user holds the trigger and makes one slow pass back over the spot (±250 mm).
The firmware switches to BOOST (2.5 x the energy per pulse: about 13 A in the rim mono, inside the 20 A switch rating, for a few seconds) and keeps
k times more pulses per 10 mm frame (pass k times slower). Ground keeps being tracked (the scan-mode tracker continues, guard window as in step 4).
MODELED; physics, detector and ground as rf2_ground_dsp.py (ASSUMED ground).

Readouts (scored against the truth):
  bearing  quadrupole axis at the frame where the quadrupole pair is strongest: 0.5 atan2(QB, QA) + 45 deg, compared with the true direction from the
           head centre to the target at that frame (mod 180: the quadrupole gives the axis, the side comes from the gyro / sweep direction)
  depth    peak quadrupole magnitude / peak mono magnitude along the pass (noise-bias corrected), against a noise-free calibration at 30 mm offset;
           the calibration spread over offsets 0 / 30 / 60 mm is the method's own error. Fallback when the quadrupole is weak: mono sweep width.
  size     mono peak amplitude at the estimated depth -> mass (sphere, mass ~ a^3)
  LIFT     a second slow pass with the head raised 50 mm (the LED tells the user when): the ratio of the two mono peaks depends on depth only, not on
           size; the mono has thousands of times the quadrupole's signal there, so this reaches where the quadrupole cannot (ground-limited by tilt)
usage: python3 rf2/rf2_pinpoint.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_ground as G
import rf2_ground_dsp as D
from rf2_ground import mu0, COILS
BOOST = 2.5; XS = np.arange(-0.25, 0.2501, 0.01)
SIG0, RN0 = D.SIG.copy(), D.RN.copy()
def set_noise(k, boost):
    """k x more pulses per frame and boost energy: the signal and the ground both scale with the current (sqrt of the energy), the noise does not,
    so in the scan units the noise falls by sqrt(k * boost)"""
    f = 1 / math.sqrt(k * boost); D.SIG = SIG0 * f; D.RN = RN0 * f ** 2
def calib():
    out = {}
    for yo in (0.0, 0.03, 0.06):
        rows = []
        for d in (0.05, 0.07, 0.09, 0.11, 0.13, 0.15, 0.17, 0.2, 0.25, 0.3):
            P = np.c_[-XS, np.full(len(XS), yo), np.full(len(XS), -(0.025 + d))]; Bt = G.Bfield("A", P)
            m = np.einsum("ij,ij->i", Bt, G.Bfield("A", P)); qa = np.einsum("ij,ij->i", Bt, G.Bfield("QA", P)); qb = np.einsum("ij,ij->i", Bt, G.Bfield("QB", P))
            rows.append((d, float(np.max(np.hypot(qa, qb)) / np.max(np.abs(m))), float(np.max(np.abs(m)))))
        out[yo] = rows
    return out
def readout(rows, cal):
    k = int(np.argmax([r[1] for r in rows])); tau = rows[k][2]; S = D.SB[int(np.argmin(np.abs(D.TAUS - tau)))]; A, V = [], []
    for r in rows:
        y, R = r[4], r[5]; Ri = np.linalg.inv(R); cov = np.linalg.inv(S.T @ Ri @ S); A.append(cov @ (S.T @ Ri @ y)); V.append(np.diag(cov))
    A, V = np.array(A), np.array(V)
    q2 = np.maximum(A[:, 1] ** 2 + A[:, 2] ** 2 - V[:, 1] - V[:, 2], 0); qs = np.sqrt(np.convolve(q2, np.ones(3) / 3, "same"))
    snrq = np.sqrt((A[:, 1] ** 2 / V[:, 1] + A[:, 2] ** 2 / V[:, 2])); m = np.convolve(np.abs(A[:, 0]), np.ones(3) / 3, "same")
    kq = int(np.argmax(qs)); out = dict(tau=tau, quad_snr=float(np.max(np.convolve(snrq, np.ones(3) / 3, "same"))), kq=kq)
    c = cal[0.03]; ds, rs, ms = np.array([x[0] for x in c]), np.array([x[1] for x in c]), np.array([x[2] for x in c])
    if out["quad_snr"] >= D.Q_SNR:
        ratio = qs[kq] / m.max(); out["depth"] = float(np.interp(ratio, rs[::-1], ds[::-1])); out["method"] = "quad / mono peak ratio"
        out["bearing"] = (math.degrees(0.5 * math.atan2(A[kq, 2], A[kq, 1])) + 45) % 180
    else:
        width = float(np.sum(m >= 0.5 * m.max()) * 0.01); wc = np.array([w for w in WCAL if w[0] >= 0.16])
        out["depth"] = float(np.interp(width, wc[:, 1], wc[:, 0])) if width > wc[0, 1] else None; out["method"] = "mono width" + ("" if out["depth"] else " (floor: <= 160 mm)")
        out["bearing"] = None
    d_use = out["depth"] if out["depth"] else 0.16
    a1 = (3e-3 / (4 * np.pi * 19300)) ** (1 / 3); k1 = (2 * np.pi * a1 ** 3 / mu0) * (6 / np.pi ** 2) * COILS["A"]["I"] * float(np.interp(d_use, ds, ms))
    out["mass"] = float(m.max() / k1); return out
LIFT = 0.05
def lift_cal():
    """noise-free mono peak along a pass (offset 30 mm) at head height 25 mm and 25 + LIFT mm, per depth below the ground: ratio (size-independent)"""
    out = []
    for d in (0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4):
        pk = []
        for h in (0.025, 0.025 + LIFT):
            P = np.c_[-XS, np.full(len(XS), 0.03), np.full(len(XS), -(h + d))]; pk.append(float(np.max(np.abs(np.einsum("ij,ij->i", G.Bfield("A", P), G.Bfield("A", P))))))
        out.append((d, pk[1] / pk[0], pk[0]))
    return out
def mono_peak(rows, tau=None):
    """mono peak amplitude along a pass; both lift passes must be fitted at the SAME decay constant (the amplitude scales with the assumed tau)"""
    k = int(np.argmax([r[1] for r in rows])); tau = tau or rows[k][2]; S = D.SB[int(np.argmin(np.abs(D.TAUS - tau)))]; m = []
    for r in rows:
        Ri = np.linalg.inv(r[5]); m.append(abs((np.linalg.inv(S.T @ Ri @ S) @ (S.T @ Ri @ r[4]))[0]))
    return float(np.max(np.convolve(m, np.ones(3) / 3, "same"))), tau
if __name__ == "__main__":
    t0 = time.time(); tab = G.ground_tables([("A", "A"), ("A", "QA"), ("A", "QB")]); cal = calib(); WCAL = D.width_curve()
    res = dict(status="MODELED (RF2 step 6: trigger-held pinpoint; ASSUMED ground)", boost=BOOST,
               ratio_calibration={str(int(yo * 1e3)) + " mm offset": [dict(depth_mm=round(d * 1e3), ratio=round(r, 4)) for d, r, m in rows] for yo, rows in cal.items()}, runs=[])
    # the method's own depth error from the unknown offset: invert each offset's noise-free ratio through the 30 mm curve
    c3 = cal[0.03]; ds3, rs3 = np.array([x[0] for x in c3]), np.array([x[1] for x in c3])
    res["offset_error_mm"] = {f"{int(yo*1e3)} mm": [round((float(np.interp(r, rs3[::-1], ds3[::-1])) - d) * 1e3) for d, r, m in rows] for yo, rows in cal.items()}
    D.XS_SWEEP = XS                                                     # the pinpoint pass: +-250 mm around the detection (a fresh 80-frame pump stands in for the scan tracker)
    cases = [(g, dict(g=m_, depth=d_), yo) for g in ("severe 2e-4", "moderate 2e-5") for (m_, d_) in ((1.0, 0.10), (1.0, 0.13), (1.0, 0.16), (5.0, 0.16), (5.0, 0.20)) for yo in (0.02, 0.05)]
    for gname, tgt, yo in cases:
        for k, boost in ((1, 1.0), (4, BOOST), (16, BOOST)):
            set_noise(k, boost); tg = dict(tgt, x=0.0, y=yo)
            rows = D.sweep(tab, G.CHI[gname], tg, seed=23)
            Ts = np.array([r[1] for r in rows]); det = bool(Ts.max() >= D.THR)
            out = dict(ground=gname, target=tgt, offset_mm=round(yo * 1e3), mode="scan pass" if k == 1 else f"pinpoint: boost x{boost}, {k} x slower", detected=det, peak_T=round(float(Ts.max()), 1))
            if det:
                ro = readout(rows, cal); xh = rows[ro["kq"]][0]
                true_brg = math.degrees(math.atan2(yo, 0.0 - xh)) % 180
                a = (3 * tgt["g"] * 1e-3 / (4 * np.pi * 19300)) ** (1 / 3)
                out.update(tau_us=round(ro["tau"] * 1e6, 1), true_tau_us=round(mu0 * 4.1e7 * a ** 2 / np.pi ** 2 * 1e6, 1), cls=D.klass(ro["tau"]), quad_snr=round(ro["quad_snr"], 1), depth_method=ro["method"],
                           depth_est_mm=round(ro["depth"] * 1e3) if ro["depth"] else "<= 160", depth_true_mm=round(tgt["depth"] * 1e3),
                           bearing_est_deg=round(ro["bearing"], 1) if ro["bearing"] is not None else None, bearing_true_deg=round(true_brg, 1) if ro["bearing"] is not None else None,
                           mass_est_g=round(ro["mass"], 2), mass_true_g=tgt["g"])
            res["runs"].append(out); print(json.dumps(out), flush=True)
    # lift test: the 16 x slower boost pass is repeated with the head raised LIFT; depth from the ratio of the two mono peaks, size from the low pass
    lc = lift_cal(); res["lift_calibration"] = [dict(depth_mm=round(d * 1e3), ratio=round(r, 4)) for d, r, p in lc]; res["lift_runs"] = []
    ld, lr, lp = np.array([c[0] for c in lc]), np.array([c[1] for c in lc]), np.array([c[2] for c in lc])
    a1 = (3e-3 / (4 * np.pi * 19300)) ** (1 / 3); k1u = (2 * np.pi * a1 ** 3 / mu0) * (6 / np.pi ** 2) * COILS["A"]["I"]
    for gname, tgt, yo in cases:
        set_noise(16, BOOST); tg = dict(tgt, x=0.0, y=yo)
        lo = D.sweep(tab, G.CHI[gname], tg, seed=23); hi = D.sweep(tab, G.CHI[gname], tg, seed=29, h0=0.025 + LIFT)
        p0, tau = mono_peak(lo); p1, _ = mono_peak(hi, tau); r = p1 / p0; d_est = float(np.interp(r, lr, ld))
        m_est = p0 / (k1u * float(np.interp(d_est, ld, lp)))
        out = dict(ground=gname, target=tgt, offset_mm=round(yo * 1e3), lift_mm=round(LIFT * 1e3), ratio=round(r, 4), depth_est_mm=round(d_est * 1e3), depth_true_mm=round(tgt["depth"] * 1e3),
                   mass_est_g=round(m_est, 2), mass_true_g=tgt["g"], tau_us=round(tau * 1e6, 1))
        res["lift_runs"].append(out); print("LIFT", json.dumps(out), flush=True)
    set_noise(1, 1.0); res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(G.OUT, "rf2_pinpoint.json"), "w"), indent=1, default=float); print("done", res["seconds"])
