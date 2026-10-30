#!/usr/bin/env python3
"""AXE2 study (owner 2026-10-30): a soft-ferrite hood over the rim coil (cap, U-channel open toward the ground, L) and coil formers shaped to go
with it, for option B (head 15.65 mm, display at z 13.1). MODELED; ASSUMED values are marked.

Method: axisymmetric magnetostatics in the flux function psi = r A_phi on a graded (r, z) grid (the ARX src/sim/hood_axi.py scheme, vectorised):
  -d/dr( 1/(mu r) dpsi/dr ) - d/dz( 1/(mu r) dpsi/dz ) = mu0 J_phi,  psi = 0 on the axis and the far boundary (4 m).
Only the ferrite's REACTION is taken from the grid: dpsi = psi(with ferrite) - psi(air), same grid and source, so the discretisation and the
truncated boundary cancel to first order. Coil field = exact Biot-Savart of the circular turns (rf2_coil_search) + reaction field;
inductance = L_turns (exact, air) + 2 pi sum_turns dpsi(turn) / I. Checks: (1) the air run against Biot-Savart; (2) a mu 1e5, 20 mm thick, 1.5 m
wide plate on top must reproduce the image-method value of rf2_rodin.image_L (548 uH for the option-B coil).
Ferrite (datasheets in data/datasheets/, DATASHEET_LOG RF2-DS-FERRITE): Ferroxcube 3C90 MnZn mu_i 2300, B 470 mT (25 C) / 380 mT (100 C),
rho 5 ohm m; 4A11 NiZn mu_i 850, B 340 / 230 mT, rho 1e5 ohm m; 4C65 NiZn mu_i 125. Flexible ferrite sheet mu' 150 is UNVERIFIED (no datasheet:
Wuerth WE-FSFS / TDK IFL downloads were refused). Tiles butted around the ring, fill 0.95 (ASSUMED): mu_eff = 0.95 mu + 0.05 (flux runs in the r-z
plane, parallel to the joints). DC, lossless: no frequency roll-off, no magnetic viscosity (a slow ferrite after-effect that PI receivers see;
no datasheet gives it: bench item). Saturation: the largest |B| in the ferrite at the peak current, against B(100 C).
Coil formers (26 turns, 1.6 mm grooves): rect 5 x 6 (option B), taper wide top (owner, both faces sloped), taper wide bottom, and 'low 4 x 7'
(the 'focus' former: the bundle pressed to the bottom and the outer wall, which frees 1.6 mm above it for a thicker cap inside today's height).
Hood geometry: cap above the bundle (0.2 mm former / insulation gap, ASSUMED), side walls 0.2 mm off the bundle, down to the bundle's bottom
('full') or its middle ('half'). Fit: cap top <= 13.1 (display); outer wall inside the 2.5 mm shell wall needs the wall thinned (flagged);
inner wall must stay outside AB1 (r >= 102.5).
Depth: mono channel, 10.8 mJ, MP1 v2 noise, 100 pulses, gate from rf2_timing.simulate with the new L (500 pF ASSUMED), gold spheres in air.
usage: python3 rf2/rf2_hood.py -> rf2/results/rf2_hood.json, rf2/results/rf2_hood.png"""
import os, sys, json, math, time
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl
from scipy.interpolate import RegularGridInterpolator
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C, rf2_receiver_combo as RC, rf2_rodin as RD, rf2_taper as TP
mu0 = C.mu0; OUT = os.path.join(HERE, "results"); E0 = 10.8e-3; MASSES = (0.1, 1.0, 5.0, 20.0); FILL = 0.95; Z_DISP = 13.1; H_B = 15.65
C.DEPTHS = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
MAT = {"3C90 MnZn": dict(mu=2300, Bsat_25=0.47, Bsat_100=0.38), "4A11 NiZn": dict(mu=850, Bsat_25=0.34, Bsat_100=0.23),
       "4C65 NiZn": dict(mu=125, Bsat_25=0.38, Bsat_100=0.34),
       "Fair-Rite 77 MnZn": dict(mu=2000, Bsat_25=0.51, Bsat_100=None), "Fair-Rite 61 NiZn": dict(mu=125, Bsat_25=0.25, Bsat_100=None), "flex sheet (UNVERIFIED mu 150)": dict(mu=150, Bsat_25=None, Bsat_100=None),
       "ideal (mu 1e5)": dict(mu=1e5, Bsat_25=None, Bsat_100=None)}
def axis(fine_lo, fine_hi, h, lo, hi, ratio=1.05):
    x = list(np.arange(fine_lo, fine_hi + h / 2, h)); d = h
    while x[-1] < hi: d *= ratio; x.append(x[-1] + d)
    d = h; y = [x[0]]
    while y[-1] > lo: d *= ratio; y.append(y[-1] - d)
    return np.unique(np.r_[y[1:], x])
FINE_R = [float(v) for v in os.environ.get("HOOD_FINE_R", "0.090,0.125").split(",")]          # fine-grid radial band (m); move it for larger coils
R = axis(FINE_R[0], FINE_R[1], 0.2e-3, 0.0, 4.0); R = np.unique(np.r_[0.0, R[R > 1e-6]]); Z = axis(0.0, 0.026, 0.2e-3, -4.0, 4.0)
NR, NZ = len(R), len(Z); dr, dz = np.diff(R), np.diff(Z); rc, zcen = (R[1:] + R[:-1]) / 2, (Z[1:] + Z[:-1]) / 2
II, JJ = np.meshgrid(np.arange(1, NR - 1), np.arange(1, NZ - 1), indexing="ij"); IDX = -np.ones((NR, NZ), int); IDX[1:-1, 1:-1] = np.arange(II.size).reshape(II.shape)
def solve(mu_cell, turns, I):
    k = 1.0 / mu_cell / rc[:, None]; i, j = II.ravel(), JJ.ravel(); n = IDX[i, j]
    cE = (k[i, j - 1] * dz[j - 1] / 2 + k[i, j] * dz[j] / 2) / dr[i]; cW = (k[i - 1, j - 1] * dz[j - 1] / 2 + k[i - 1, j] * dz[j] / 2) / dr[i - 1]
    cN = (k[i - 1, j] * dr[i - 1] / 2 + k[i, j] * dr[i] / 2) / dz[j]; cS = (k[i - 1, j - 1] * dr[i - 1] / 2 + k[i, j - 1] * dr[i] / 2) / dz[j - 1]
    rows, cols, vals = [n], [n], [cE + cW + cN + cS]
    for c, (a, b) in ((cE, (i + 1, j)), (cW, (i - 1, j)), (cN, (i, j + 1)), (cS, (i, j - 1))):
        m = IDX[a, b]; ok = m >= 0; rows.append(n[ok]); cols.append(m[ok]); vals.append(-c[ok])
    A = sp.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(II.size,) * 2); b = np.zeros(II.size)
    for r0, z0, s in turns:
        a = np.searchsorted(R, r0) - 1; c = np.searchsorted(Z, z0) - 1; tr = (r0 - R[a]) / dr[a]; tz = (z0 - Z[c]) / dz[c]
        for (p, q), w in (((a, c), (1 - tr) * (1 - tz)), ((a + 1, c), tr * (1 - tz)), ((a, c + 1), (1 - tr) * tz), ((a + 1, c + 1), tr * tz)):
            if IDX[p, q] >= 0: b[IDX[p, q]] += mu0 * I * s * w
    psi = np.zeros((NR, NZ)); psi[1:-1, 1:-1] = spl.spsolve(A, b).reshape(II.shape); return psi
def cells(boxes, mu):
    """boxes [(r0, r1, z0, z1)] in mm -> cell permeability (fill-homogenised)"""
    m = np.ones((NR - 1, NZ - 1)); me = FILL * mu + (1 - FILL)
    for r0, r1, z0, z1 in boxes: m[np.ix_((rc > r0 * 1e-3) & (rc < r1 * 1e-3), (zcen > z0 * 1e-3) & (zcen < z1 * 1e-3))] = me
    return m
class Reaction:
    def __init__(self, dpsi):
        gr, gz = np.gradient(dpsi, R, Z, edge_order=2); self.fr = RegularGridInterpolator((R, Z), gr); self.fz = RegularGridInterpolator((R, Z), gz); self.f = RegularGridInterpolator((R, Z), dpsi)
    def B(self, P):
        r = np.hypot(P[:, 0], P[:, 1]); rr = np.maximum(r, 1e-3); q = np.c_[rr, P[:, 2]]; Bz = self.fr(q) / rr; Br = -self.fz(q) / rr
        c, s = np.where(r > 1e-9, P[:, 0] / np.maximum(r, 1e-12), 0), np.where(r > 1e-9, P[:, 1] / np.maximum(r, 1e-12), 0); return np.c_[Br * c, Br * s, Bz]
def Bmax_ferrite(psi, mu_cell, I):
    g_r = np.diff(psi, axis=0)[:, :-1] / dr[:, None]; g_z = np.diff(psi, axis=1)[:-1, :] / dz[None, :]
    B = np.hypot(g_r, g_z) / rc[:, None]; m = mu_cell > 1.5; return float(B[m].max()) if m.any() else 0.0
def coil(name):
    S = TP.sites(*TP.SHAPES[name]) if name in TP.SHAPES else [(i, j) for i in range(4) for j in range(7)][:26]
    return [(TP.geom(s)[0] * 1e-3, TP.geom(s)[1] * 1e-3, 1) for s in S]
def hood(T, kind, t, walls="full", gap=0.2):
    r = [x[0] * 1e3 for x in T]; z = [x[1] * 1e3 for x in T]; ri, ro, zb, zt = min(r) - 0.6, max(r) + 0.6, min(z) - 0.6, max(z) + 0.6
    cap = (ri - (gap + t if kind == "U" else 0), ro + (gap + t if kind in ("U", "L") else 0), zt + gap, zt + gap + t); boxes = [cap] if kind else []
    zw = zb if walls == "full" else (zb + zt) / 2
    if kind in ("U", "L"): boxes.append((ro + gap, ro + gap + t, zw, zt + gap + t))
    if kind == "U": boxes.append((ri - gap - t, ri - gap, zw, zt + gap + t))
    fit = dict(cap_top_mm=round(cap[3], 2), head_mm=round(H_B + max(0.0, cap[3] - Z_DISP), 2), inner_wall_r_mm=round(ri - gap - t, 2) if kind == "U" else None,
               outer_wall_r_mm=round(ro + gap + t, 2) if kind in ("U", "L") else None)
    fit["fits_option_B"] = bool(cap[3] <= Z_DISP + 1e-9 and (kind != "U" or ri - gap - t >= 102.5) and (kind not in ("U", "L") or ro + gap + t <= 114.0 + 1e-9))
    fit["fits_if_shell_wall_thinned"] = bool(cap[3] <= Z_DISP + 1e-9 and (kind != "U" or ri - gap - t >= 102.5) and (kind not in ("U", "L") or ro + gap + t <= 115.0 + 1e-9))
    return boxes, fit
_AIR = {}
def run(label, former, kind, t, mat, walls="full", boxes=None, extra=None):
    T = coil(former); Ls = C.L_turns(T); I0 = 1.0
    if former not in _AIR: _AIR[former] = solve(np.ones((NR - 1, NZ - 1)), T, I0)
    fit = {}
    if boxes is None: boxes, fit = hood(T, kind, t, walls) if kind else ([], dict(head_mm=H_B, fits_option_B=True))
    mu_c = cells(boxes, MAT[mat]["mu"]) if boxes else np.ones((NR - 1, NZ - 1)); psi = solve(mu_c, T, I0) if boxes else _AIR[former]
    re = Reaction(psi - _AIR[former]); dL = 2 * math.pi * float(sum(re.f([[r, z]])[0] for r, z, s in T)) / I0; L = Ls + dL; I = math.sqrt(2 * E0 / L)
    Bt = lambda P, T=T, re=re: C.B_turns(T, P) + re.B(P); Rw = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU; g = RD.gate_for(L, Rw, I)
    cache = {}
    def Bf(P):
        k = P.tobytes()
        if k not in cache: cache[k] = Bt(P)
        return cache[k]
    d = {f"{m} g": RC.depth(Bf, I, g * 1e-6, m, Bf) for m in MASSES}
    Bm = Bmax_ferrite(psi, mu_c, I0) * I if boxes else 0.0; vol = sum((b[1] - b[0]) * (b[3] - b[2]) * 2 * math.pi * (b[0] + b[1]) / 2 for b in boxes) * 1e-9
    row = dict(case=label, former=former, hood=kind or "none", t_mm=t, walls=walls if kind in ("U", "L") else None, material=mat if boxes else None, L_uH=round(L * 1e6, 1),
               I_A=round(I, 2), first_gate_us=g, axis_uT_100_300=[round(float(v), 2) for v in Bf(np.array([[0, 0, -0.1], [0, 0, -0.3]]))[:, 2] * I * 1e6],
               B_max_ferrite_mT=round(Bm * 1e3, 1), mass_g=round(vol * 4800 * 1e3 * FILL, 1), mono_depth_mm=d, **fit, **(extra or {}))
    sat = MAT[mat]["Bsat_100"] if boxes else None; row["saturation_margin_100C"] = round(sat / Bm, 2) if sat and Bm else None
    print(json.dumps(row), flush=True); return row
if __name__ == "__main__":
    t0 = time.time(); os.makedirs(OUT, exist_ok=True); print("grid", NR, "x", NZ, flush=True)
    res = dict(status=__doc__.split("\n")[1], grid=[NR, NZ], validation={}, cases=[])
    T = coil("rect 5 x 6"); air = solve(np.ones((NR - 1, NZ - 1)), T, 1.0); _AIR["rect 5 x 6"] = air
    P = np.array([[0, 0, -d] for d in (0.05, 0.1, 0.3, 0.6)]); gr = np.gradient(air, R, Z, edge_order=2)[0]; f = RegularGridInterpolator((R, Z), gr)
    Bz_grid = [float(f([[1e-3, p[2]]])[0] / 1e-3) for p in P]; Bz_bs = C.B_turns(T, P)[:, 2]
    res["validation"]["air_grid_vs_biot_savart_pct"] = {f"{int(-p[2]*1e3)} mm": round(100 * (a / b - 1), 2) for p, a, b in zip(P, Bz_grid, Bz_bs)}
    print("air check", res["validation"], flush=True)
    v = run("CHECK: ideal plate mu 1e5, 20 mm thick, r 0-1500 at z 13.1 (image method: 548.2 uH, 231 / 410 / 523 / 629 mm)", "rect 5 x 6", "plate", 20, "ideal (mu 1e5)",
            boxes=[(0.0, 1500.0, 13.1, 33.1)])
    res["validation"]["ideal_plate"] = v
    plan = [("option B coil, no hood", "rect 5 x 6", None, 0, "3C90 MnZn"),
            ("cap 0.5 mm 3C90", "rect 5 x 6", "cap", 0.5, "3C90 MnZn"), ("cap 0.5 mm flex sheet", "rect 5 x 6", "cap", 0.5, "flex sheet (UNVERIFIED mu 150)"),
            ("cap 1.0 mm 3C90", "rect 5 x 6", "cap", 1.0, "3C90 MnZn"), ("cap 2.0 mm 3C90", "rect 5 x 6", "cap", 2.0, "3C90 MnZn"),
            ("L 1.0 mm 3C90 (cap + outer wall)", "rect 5 x 6", "L", 1.0, "3C90 MnZn"),
            ("U 0.5 mm 3C90, full walls", "rect 5 x 6", "U", 0.5, "3C90 MnZn"), ("U 1.0 mm 3C90, full walls", "rect 5 x 6", "U", 1.0, "3C90 MnZn"),
            ("U 1.0 mm 3C90, half walls", "rect 5 x 6", "U", 1.0, "3C90 MnZn", "half"), ("U 2.0 mm 3C90, full walls", "rect 5 x 6", "U", 2.0, "3C90 MnZn"),
            ("U 1.0 mm 4A11 NiZn, full walls", "rect 5 x 6", "U", 1.0, "4A11 NiZn"), ("U 1.0 mm 4C65 NiZn, full walls", "rect 5 x 6", "U", 1.0, "4C65 NiZn"),
            ("owner taper (wide top), no hood", "taper, wide top (owner), both faces sloped", None, 0, "3C90 MnZn"),
            ("owner taper (wide top) + U 1.0 3C90", "taper, wide top (owner), both faces sloped", "U", 1.0, "3C90 MnZn"),
            ("taper wide bottom + U 1.0 3C90", "taper, wide bottom, outer wall flush", "U", 1.0, "3C90 MnZn"),
            ("focus former low 4 x 7, no hood", "low 4 x 7", None, 0, "3C90 MnZn"),
            ("focus former low 4 x 7 + cap 2.0 3C90", "low 4 x 7", "cap", 2.0, "3C90 MnZn"),
            ("focus former low 4 x 7 + U 0.5 3C90 (cap 2.0 would need walls outside the window)", "low 4 x 7", "U", 0.5, "3C90 MnZn"),
            ("focus former low 4 x 7 + L 1.0 3C90", "low 4 x 7", "L", 1.0, "3C90 MnZn")]
    for p in plan:
        res["cases"].append(run(p[0], p[1], p[2], p[3], p[4], p[5] if len(p) > 5 else "full")); print("t", round(time.time() - t0), flush=True)
    base = res["cases"][0]
    for r in res["cases"]: r["depth_vs_optionB_pct"] = {k: round(100 * (v / base["mono_depth_mm"][k] - 1), 1) for k, v in r["mono_depth_mm"].items()}
    res["seconds"] = round(time.time() - t0); json.dump(res, open(os.path.join(OUT, "rf2_hood.json"), "w"), indent=1, default=float)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw=dict(width_ratios=[1, 1, 1.4]))
    for ax, (lab, kind, t) in zip(axs[:2], (("no hood", None, 0), ("U 1.0 mm 3C90, full walls", "U", 1.0))):
        boxes = hood(T, kind, t)[0] if kind else []; mu_c = cells(boxes, 2300) if boxes else np.ones((NR - 1, NZ - 1)); psi = solve(mu_c, T, 1.0)
        sr, sz = (R > 0.085) & (R < 0.125), (Z > -0.012) & (Z < 0.022); ax.contour(R[sr] * 1e3, Z[sz] * 1e3, psi[np.ix_(sr, sz)].T, 40, linewidths=0.6)
        for b in boxes: ax.add_patch(plt.Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], color="#555", alpha=0.6))
        for r, z, s in T: ax.add_patch(plt.Circle((r * 1e3, z * 1e3), 0.6, color="#d35400"))
        ax.axhline(Z_DISP, color="#999", lw=0.6, ls="--"); ax.set_aspect("equal"); ax.set_title(f"field lines (psi contours), {lab}", fontsize=8); ax.set_xlabel("r (mm)"); ax.set_ylabel("z (mm)")
    ax = axs[2]; rows = res["cases"]; y = np.arange(len(rows))
    ax.barh(y, [r["depth_vs_optionB_pct"]["1.0 g"] for r in rows], color=["#2e7d32" if r.get("fits_option_B") else ("#f9a825" if r.get("fits_if_shell_wall_thinned") else "#999") for r in rows])
    ax.set_yticks(y); ax.set_yticklabels([r["case"][:60] for r in rows], fontsize=6); ax.axvline(0, color="k", lw=0.6); ax.invert_yaxis()
    ax.set_xlabel("1 g mono depth vs option B (%)"); ax.set_title("MODELED (DC, lossless ferrite); green fits option B, amber needs a thinner shell wall, grey taller head", fontsize=7)
    fig.savefig(os.path.join(OUT, "rf2_hood.png"), dpi=130, bbox_inches="tight"); print("done", res["seconds"])
