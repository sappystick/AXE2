#!/usr/bin/env python3
"""AXE2: a passive ferrous channel, a fluxgate GRADIOMETER (one sensor in the head, one 0.6 m up the shaft), read between TX pulses. MODELED;
ASSUMED values are marked. Iron in the Earth's field carries an induced moment m = V chi_eff B_E / mu0; gold has none. What limits it in a
swinging head is not sensor noise but how well the two sensors cancel the 50 uT Earth field as the head rotates (axis misalignment and gain
mismatch after calibration): that residual moves at the sweep rate, in the same band as a target.
Targets (steel, mu >> 1, chi_eff from the demagnetising factor of an ellipsoid): 3 g compact lump (sphere, chi_eff 3); 50 x 3 mm nail (2.8 g)
along / across the field; 100 g lump. Earth field 50 uT, inclination 60 deg (ASSUMED mid-latitude). Target directly under the head centre;
lower sensor at the hub (z 8 mm above the skid underside), upper sensor 600 mm above it.
Sensor noise 10 pT/rtHz (ASSUMED, typical of a good miniature fluxgate: UNVERIFIED, no datasheet on disk), bandwidth 10 Hz.
Detection: |gradient field| >= 3 x (sqrt(2) x sensor noise + B_E x residual mismatch). Residual mismatch 1e-3 / 1e-4 / 1e-5 (uncalibrated /
calibrated / carefully calibrated). Also: the TX field at the head sensor (it must be read in the quiet window).
usage: python3 rf2/rf2_fluxgate.py -> rf2/results/rf2_fluxgate.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z
OUT = os.path.join(HERE, "results"); mu0 = 4e-7 * math.pi; BE = 50e-6; INC = math.radians(60); RHO = 7850.0
def demag_prolate(a):                                   # long axis demagnetising factor, aspect a > 1
    e = math.sqrt(1 - 1 / a ** 2); return (1 - e ** 2) / e ** 3 * (math.atanh(e) - e)
def moment(kind):
    if kind == "3 g lump (sphere)": V = 3e-3 / RHO; return V * 3.0 * BE / mu0, V
    if kind == "100 g lump (sphere)": V = 100e-3 / RHO; return V * 3.0 * BE / mu0, V
    a = 50 / 3; V = math.pi * (1.5e-3) ** 2 * 50e-3; Nl = demag_prolate(a); Nt = (1 - Nl) / 2
    return (V * (1 / Nl) * BE / mu0 if "along" in kind else V * (1 / Nt) * BE / mu0), V
def dipole_B(m_vec, r_vec):
    r = np.linalg.norm(r_vec); u = r_vec / r; return mu0 / (4 * math.pi) * (3 * u * np.dot(m_vec, u) - m_vec) / r ** 3
if __name__ == "__main__":
    bdir = np.array([math.cos(INC), 0.0, -math.sin(INC)]); res = dict(status=__doc__.split("\n")[1], targets=[], tx_at_sensor_mT=None)
    noise = 10e-12 * math.sqrt(10.0) * math.sqrt(2)
    for kind in ("3 g lump (sphere)", "nail 50 x 3 mm along the field", "nail 50 x 3 mm across the field", "100 g lump (sphere)"):
        m, V = moment(kind); mv = m * bdir; rows = {}
        for mis in (1e-3, 1e-4, 1e-5):
            floor = noise + BE * mis; rng = 0
            for d in np.arange(0.02, 3.0, 0.005):
                lo = np.array([0, 0, 0.008 + d]); hi = lo + np.array([0, 0, 0.6]); g = np.linalg.norm(dipole_B(mv, lo) - dipole_B(mv, hi))
                if g >= 3 * floor: rng = d
            rows[f"mismatch {mis:g}"] = dict(floor_nT=round(floor * 1e9, 3), range_mm=round(rng * 1000))
        B100 = np.linalg.norm(dipole_B(mv, np.array([0, 0, 0.108])))
        row = dict(target=kind, mass_g=round(V * RHO * 1000, 1), moment_Am2=float(f"{m:.3g}"), field_at_100mm_nT=round(B100 * 1e9, 2), detection=rows)
        res["targets"].append(row); print(json.dumps(row), flush=True)
    res["tx_at_sensor_mT"] = round(float(np.linalg.norm(Z.Bc((0, 0, 8.0))[0])) * Z.I0 * 1e3, 3)
    res["notes"] = ["the head sensor sees about 1.2 mT at each TX pulse: far above a fluxgate's range (typically +-100 uT, UNVERIFIED); it must recover before "
                    "the quiet-window reading (bench: recovery time)", "its permalloy core is itself a small magnetic and conductive target for the mono (bench: "
                    "mono residual with and without the sensor in place)", "residual mismatch is set by calibration (rotate the head in a clean area; 12-parameter fit "
                    "per sensor: offsets, gains, non-orthogonality) and by temperature"]
    json.dump(res, open(os.path.join(OUT, "rf2_fluxgate.json"), "w"), indent=1); print("TX at sensor mT", res["tx_at_sensor_mT"])
