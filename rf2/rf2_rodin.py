#!/usr/bin/env python3
"""AXE2 study (owner 2026-10-30): a Rodin-style toroidal former as the transmit (and mono receive) coil, and a Halbach magnet shell over it. MODELED;
ASSUMED values are marked. The owner's upload rodin_core_HIGH.stl was not a mesh (279-byte gzip of a 515-byte STL-viewer settings JSON), so the former is
parametric here; a real export can be checked against it later.

Former (torus, elliptic tube; z up from the skid underside, mm):
  RIM   fits option B's rim window r 103.8-113.4, z 4.4-12.6: major radius 108.6, tube radius 4.0, centre z 8.5 (same footprint as today's coil)
  FLAT  a pancake torus over the whole face r 20-113 (major 66.5, radial semi-axis 46.5, vertical 4.0): the classic fat-Rodin proportion squeezed
        into 8 mm; it collides with the AB1 / MP1 / TXJ / CB1D islands (geometry only, to test the physics)
Windings: two helices on the tube, opposite handedness (cross-diagonal one way and the other), winding A in a shallow groove (tube radius 3.5),
winding B in a deeper groove (2.5). Each makes Q = 13 toroidal circuits and P poloidal turns (RIM P = 350, FLAT P = 27: about 45 deg to the tube axis),
in series. Two series connections:
  toroidal-aiding   A (P, Q) + B (-P, Q): the poloidal currents cancel, the 2 x 13 toroidal circuits add (an effective 26-turn loop)
  poloidal-aiding   A (P, Q) + B (P, -Q): the toroidal circuits cancel, the 2 x P poloidal turns add (a closed toroid: field confined to the tube)
Compared with the 26-turn rim mono of option B (rect 5 x 6) at equal energy (10.8 mJ), mono channel, MP1 v2 noise, gate from rf2_timing.simulate
(500 pF node ASSUMED for every coil: the Rodin's crossovers would add capacitance, not modeled), gold spheres in air.
Inductance: Neumann double integral over the polylines with the kernel 1 / sqrt(d^2 + eps^2); eps is calibrated so that the rect 5 x 6 coil, as
polylines, matches rf2_coil_search.L_turns.

Halbach shell (magpylib): a half-cylinder of 5 square N42 bars (3 x 3 mm, Br 1.3 T ASSUMED typical) on a 6 mm radius around the top half of the
tube, 180 positions around the ring, magnetisation rotated as a Halbach cylinder so the field inside points down. Reported: the static field at the
coil, at the receive boards, and in the ground. Its effect on the PULSED field is through its permeability only: NdFeB recoil mu_r 1.05 (ASSUMED
typical), image weight (mu-1)/(mu+1); the same image model with weight 1 is the ideal soft-ferrite cap (upper bound). Eddy currents in the magnets
(rho 1.5 uOhm m ASSUMED typical): sphere-equivalent decay into the mono at the first gate, against the noise.
usage: python3 rf2/rf2_rodin.py -> rf2/results/rf2_rodin.json, rf2/results/rf2_rodin.png"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C, rf2_receiver_combo as RC, rf2_timing as TM, rf2_taper as TP
mu0 = C.mu0; OUT = os.path.join(HERE, "results"); E0 = 10.8e-3; MASSES = (0.1, 1.0, 5.0, 20.0); Q = 13
C.DEPTHS = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
FORMERS = {"RIM": dict(R0=108.6, ar=4.0, az=4.0, z0=8.5, P=350), "FLAT": dict(R0=66.5, ar=46.5, az=4.0, z0=8.5, P=27)}
GROOVE = {"A": 3.5 / 4.0, "B": 2.5 / 4.0}                                   # groove depth as a fraction of the tube: A shallow, B deep
def rodin(f, groove, p, q, ds=1.5):
    s = GROOVE[groove]; ar, az = f["ar"] * s, f["az"] * s
    Lpath = math.hypot(abs(p) * 2 * math.pi * math.sqrt((ar ** 2 + az ** 2) / 2), abs(q) * 2 * math.pi * f["R0"]); n = int(Lpath / ds)
    t = np.linspace(0, 1, n + 1); th = 2 * math.pi * q * t; ph = 2 * math.pi * p * t; rr = f["R0"] + ar * np.cos(ph)
    return np.c_[rr * np.cos(th), rr * np.sin(th), f["z0"] + az * np.sin(ph)] * 1e-3
def turn_polys(T, ds=1.5):
    out = []
    for r, z, s in T:
        n = int(2 * math.pi * r * 1e3 / ds); a = np.linspace(0, 2 * math.pi, n + 1); out.append(np.c_[r * np.cos(a), r * np.sin(a), np.full(n + 1, z)])
    return out
def neumann(paths, eps, chunk=400):
    d = np.vstack([np.diff(p, axis=0) for p in paths]).astype(np.float32); m = np.vstack([(p[:-1] + p[1:]) / 2 for p in paths]).astype(np.float32); tot = 0.0
    for a in range(0, len(d), chunk):
        r2 = ((m[a:a + chunk, None, :] - m[None, :, :]) ** 2).sum(2) + np.float32(eps ** 2)
        tot += float(np.sum((d[a:a + chunk] @ d.T) / np.sqrt(r2), dtype=np.float64))
    return 1e-7 * tot
def length(paths): return float(sum(np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in paths))
class Field:
    """B per ampere of a set of polylines, cached by point set (the depth grid is reused for every mass)"""
    def __init__(self, paths): self.paths, self.cache = paths, {}
    def __call__(self, P):
        k = P.tobytes()
        if k not in self.cache: self.cache[k] = C.B_paths(self.paths, P, chunk=100)
        return self.cache[k]
def image_L(T, zf, k):
    """inductance of real turns T below a permeable half-space at zf (image weight k): L0 + k * sum M(real i, image j). Counting the images as extra
    turns (L_turns(T + images)) double-counts them: that gives (1 + k^2) L0 + 2 k M."""
    r = np.array([t[0] for t in T]); z = np.array([t[1] for t in T]); i, j = np.meshgrid(range(len(T)), range(len(T)))
    return C.L_turns(T) + k * float(np.sum(C.M_coax(r[i], z[i], r[j], 2 * zf - z[j])))
def gate_for(L, R, I, Cn=500e-12):
    TM.A = dict(T=None, L=L, I=I, R=R); TM.CN = Cn; return TM.simulate("A alone", "critical")["mono_clean_us"]
def evaluate(name, paths, L, extra=None):
    I = math.sqrt(2 * E0 / L); R = C.RHO_CU * length(paths) / C.A_CU; Bf = Field(paths); g = gate_for(L, R, I)
    d = {f"{m} g": RC.depth(Bf, I, g * 1e-6, m, Bf) for m in MASSES}
    pts = np.array([[0, 0, 8.5e-3], [0, 0, -0.1], [0, 0, -0.3], [0.1086, 0, 8.5e-3 + 1e-4], [0.1086, 0, -0.1]]); B = Bf(pts) * I * 1e6
    row = dict(name=name, L_uH=round(L * 1e6, 1), I_A=round(I, 2), wire_m=round(length(paths), 2), R_ohm=round(R, 3), first_gate_us=g,
               B_uT=dict(head_centre=round(float(np.linalg.norm(B[0])), 1), axis_100mm=round(float(np.linalg.norm(B[1])), 2), axis_300mm=round(float(np.linalg.norm(B[2])), 3),
                         inside_tube=round(float(np.linalg.norm(B[3])), 0), under_rim_100mm=round(float(np.linalg.norm(B[4])), 2)),
               mono_depth_mm=d, **(extra or {}))
    print(json.dumps(row), flush=True); return row
def halbach(sense):
    import magpylib as magpy
    mags = []; Br = 1.3; Rs = 6.0; f = FORMERS["RIM"]
    for k in range(180):
        th = 2 * math.pi * k / 180
        for j in range(5):
            al = math.pi * j / 4                                                  # 0..180 deg over the top half of the tube (in the r-z plane)
            r, z = f["R0"] + Rs * math.cos(al), f["z0"] + Rs * math.sin(al)
            mang = sense * 2 * al + math.pi / 2                                   # Halbach cylinder rotation (two senses tried; the one aiming down is kept)
            mr, mz = math.cos(mang), math.sin(mang)
            mags.append(magpy.magnet.Cuboid(polarization=(Br * mr, 0, Br * mz), dimension=(3e-3, 3e-3, 3e-3), position=(r * 1e-3, 0, z * 1e-3)).rotate_from_angax(math.degrees(th), "z", anchor=0))
    return magpy.Collection(*mags)
def magnet_eddy(T, I, gate_us, cube_mm, n_blocks):
    """sphere-equivalent eddy decay of n_blocks NdFeB cubes on the shell, into the mono, mean over the first gate (as RC.snr_best)"""
    a = (3 * (cube_mm * 1e-3) ** 3 / (4 * math.pi)) ** (1 / 3); sig = 1 / 1.5e-6; tau = mu0 * sig * a ** 2 / math.pi ** 2
    f = FORMERS["RIM"]; P = np.array([[(f["R0"] + 6 * math.cos(al)) * 1e-3, 0, (f["z0"] + 6 * math.sin(al)) * 1e-3] for al in np.linspace(0, math.pi, 5)])
    B = C.B_turns(T, P); coup = I * np.einsum("ij,ij->i", B, B) * n_blocks / 5
    K = (2 * math.pi * a ** 3 / mu0) * (6 / math.pi ** 2) * coup.sum(); tc = gate_us * 1e-6; Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 40)
    n = np.arange(1, 40)[:, None]; v = float(np.mean(K / tau * np.sum(np.exp(-(n ** 2) * tt[None, :] / tau), axis=0)))
    noise = RC.NOISE * math.sqrt(1 / (2 * Tg)) / math.sqrt(C.NAVG)
    return dict(cube_mm=cube_mm, blocks=n_blocks, tau_us=round(tau * 1e6, 3), V_at_first_gate=float(f"{v:.3g}"), noise_V=float(f"{noise:.3g}"), ratio_to_noise=float(f"{v / noise:.3g}"))
if __name__ == "__main__":
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    res = dict(status=__doc__.split("\n")[1], upload="rodin_core_HIGH.stl: gzip of an STL-viewer settings JSON (515 bytes), no geometry", coils=[], focusing=[], halbach={})
    # reference coil and the inductance calibration
    S = TP.sites(*TP.SHAPES["rect 5 x 6"]); TR = [(TP.geom(s)[0] * 1e-3, TP.geom(s)[1] * 1e-3, 1) for s in S]; Lref = C.L_turns(TR); polys = turn_polys(TR)
    lo, hi = 0.05e-3, 1.2e-3
    for _ in range(20):
        mid = (lo + hi) / 2
        if neumann(polys, mid) > Lref: lo = mid
        else: hi = mid
    EPS = (lo + hi) / 2; res["neumann_eps_mm"] = round(EPS * 1e3, 3); print("eps", EPS, "L check", neumann(polys, EPS), Lref, flush=True)
    res["coils"].append(evaluate("rim mono, rect 5 x 6 (option B)", polys, Lref))
    # Rodin formers
    for fname, f in FORMERS.items():
        for conn, (pB, qB) in (("toroidal-aiding", (-f["P"], Q)), ("poloidal-aiding", (f["P"], -Q))):
            paths = [rodin(f, "A", f["P"], Q), rodin(f, "B", pB, qB)]; L = neumann(paths, EPS)
            res["coils"].append(evaluate(f"Rodin {fname}, {conn}", paths, L, dict(former=f, P=f["P"], Q=Q, segments=sum(len(p) for p in paths))))
            print("t", round(time.time() - t0), flush=True)
    # focusing: ideal ferrite cap and NdFeB shell, as weighted images of the rect coil in a plane at the window top (z 13.1)
    Iref = math.sqrt(2 * E0 / Lref); gref = res["coils"][0]["first_gate_us"]
    for label, k in (("no cap", 0.0), ("NdFeB shell (mu_r 1.05): image weight 0.024", (1.05 - 1) / (1.05 + 1)), ("ideal soft-ferrite cap (upper bound)", 1.0)):
        Ti = TR + ([(r, 2 * 13.1e-3 - z, k) for r, z, s in TR] if k else []); L = image_L(TR, 13.1e-3, k); I = math.sqrt(2 * E0 / L)
        d = {f"{m} g": RC.depth(lambda P, Ti=Ti: C.B_turns(Ti, P), I, gref * 1e-6, m, lambda P, Ti=Ti: C.B_turns(Ti, P)) for m in MASSES}
        row = dict(case=label, image_weight=round(k, 4), L_uH=round(L * 1e6, 1), I_A=round(I, 2), mono_depth_mm=d); res["focusing"].append(row); print(json.dumps(row), flush=True)
    # Halbach shell: static field
    best = None
    for sense in (1, -1):
        col = halbach(sense); Bc = np.reshape(col.getB(np.array([[0.1086, 0, -0.005]])), -1)
        if best is None or Bc[2] < best[1]: best = (sense, Bc[2], col)
    col = best[2]; f = FORMERS["RIM"]
    probes = {"tube centre (coil)": (f["R0"], 8.5), "receive boards under the coil (z 2)": (f["R0"], 2.0), "receive boards mid-face (r 50, z 2)": (50, 2.0),
              "ground 0 mm below the rim (z 0)": (f["R0"], 0.0), "50 mm below the rim": (f["R0"], -50), "100 mm below the rim": (f["R0"], -100), "100 mm below the centre": (0, -100)}
    res["halbach"]["static_field_mT"] = {k: round(float(np.linalg.norm(np.reshape(col.getB(np.array([[r * 1e-3, 0, z * 1e-3]])), -1))) * 1e3, 4) for k, (r, z) in probes.items()}
    res["halbach"]["sense"] = best[0]; res["halbach"]["blocks"] = 900; res["halbach"]["mass_g_NdFeB_7.5"] = round(900 * 27e-3 * 7.5, 0)
    res["halbach"]["eddy_into_mono"] = [magnet_eddy(TR, Iref, gref, c, int(900 * (3 / c))) for c in (3, 5, 10)]
    res["halbach"]["height_needed_mm"] = "shell top at z 8.5 + 6 + 1.5 = 16.0, above option B's display level (13.1): the head grows to about 19-20 mm"
    print(json.dumps(res["halbach"]), flush=True)
    res["seconds"] = round(time.time() - t0); json.dump(res, open(os.path.join(OUT, "rf2_rodin.json"), "w"), indent=1, default=float)
    # figure: winding paths (part) and field maps in the r-z plane
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.2))
    f = FORMERS["RIM"]; pa, pb = rodin(f, "A", f["P"], Q), rodin(f, "B", -f["P"], Q); sel = slice(0, 1400)
    ax = axs[0]; ax.plot(pa[sel, 0] * 1e3, pa[sel, 1] * 1e3, lw=0.6, label="A (shallow)"); ax.plot(pb[sel, 0] * 1e3, pb[sel, 1] * 1e3, lw=0.6, label="B (deep, opposite hand)")
    ax.set_aspect("equal"); ax.legend(fontsize=6); ax.set_title("RIM Rodin: the first 2 m of each winding (plan)", fontsize=8)
    rr = np.linspace(-0.13, 0.13, 53); zz = np.linspace(-0.12, 0.03, 31); G = np.array([[x, 0, z] for z in zz for x in rr])
    for ax, nm in zip(axs[1:], ("rim mono, rect 5 x 6 (option B)", "Rodin RIM, poloidal-aiding")):
        row = next(c for c in res["coils"] if c["name"] == nm)
        paths = polys if "mono" in nm else [rodin(f, "A", f["P"], Q), rodin(f, "B", f["P"], -Q)]
        B = C.B_paths(paths, G, chunk=60) * row["I_A"]; Bm = np.linalg.norm(B, axis=1).reshape(len(zz), len(rr))
        im = ax.pcolormesh(rr * 1e3, zz * 1e3, np.log10(Bm * 1e6 + 1e-3), vmin=-1, vmax=4, shading="auto"); fig.colorbar(im, ax=ax, label="log10 |B| (uT)")
        ax.set_title(f"{nm}: |B| at {row['I_A']} A (10.8 mJ)", fontsize=8); ax.set_xlabel("x (mm)"); ax.set_aspect("equal")
    fig.savefig(os.path.join(OUT, "rf2_rodin.png"), dpi=130, bbox_inches="tight"); print("done", res["seconds"], "s")
