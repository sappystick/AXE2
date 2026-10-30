#!/usr/bin/env python3
"""AXE2 study (owner 2026-10-30): the option-B rim coil (26 turns, 5 rows x 6 columns, rows stacked up the rim) with every turn following a WAVE
around the ring, and the wave phase advanced row by row going up (a stacked, Rodin-like twist). Same transmit = mono-receive chain as the best model.
MODELED; inductance by Neumann polylines (rf2_rodin, eps 0.465 mm calibrated to rf2_coil_search.L_turns), 10.8 mJ, MP1 v2 noise, gate from
rf2_timing.simulate (500 pF ASSUMED), gold spheres in air, SNR 3.

Turn k (row i, column j): theta around the ring,
  r(theta) = r_j - shift + Ar sin(n theta + i dphi),  z(theta) = z_i + Az sin(n theta + i dphi + psi)
  n = waves per circuit, dphi = phase advance per row (the twist), psi = 90 deg makes each turn a corkscrew (radial and vertical wave together).
All columns of a row wave in phase (nested, so the groove pitch is kept). A radial wave is shifted inward by Ar so the outermost turn stays inside the
shell wall (r 113.4); a vertical wave needs Az of free height: option B's window has 0.2 mm, so Az > 0.1 does not fit unless a row is dropped
('fits_window' says which).
usage: python3 rf2/rf2_wave.py -> rf2/results/rf2_wave.json, rf2/results/rf2_wave.png"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_rodin as RD, rf2_taper as TP
OUT = os.path.join(HERE, "results"); EPS = 0.465e-3
def wavy_coil(n=13, Ar=0.0, Az=0.0, dphi=0.0, psi=0.0, ds=1.5):
    S = TP.sites(*TP.SHAPES["rect 5 x 6"]); paths = []
    for (i, j) in S:
        r0, z0 = TP.geom((i, j)); r0 -= Ar
        N = int(2 * math.pi * r0 / ds * (1 + (n * max(Ar, Az) / r0) ** 2) ** 0.5) + 1; th = np.linspace(0, 2 * math.pi, N + 1)
        r = r0 + Ar * np.sin(n * th + i * dphi); z = z0 + Az * np.sin(n * th + i * dphi + psi)
        paths.append(np.c_[r * np.cos(th), r * np.sin(th), z] * 1e-3)
    return paths
CASES = [("flat turns (option B as today)", dict()),
         ("radial wave 0.8 mm, 13 waves, no twist", dict(Ar=0.8)),
         ("radial wave 0.8 mm, 13 waves, twist 72 deg / row", dict(Ar=0.8, dphi=2 * math.pi / 5)),
         ("radial wave 0.8 mm, 6 waves, twist 72 deg / row", dict(n=6, Ar=0.8, dphi=2 * math.pi / 5)),
         ("corkscrew 0.8 mm (radial + vertical, 90 deg), 13 waves, twist", dict(Ar=0.8, Az=0.8, psi=math.pi / 2, dphi=2 * math.pi / 5)),
         ("vertical wave 0.8 mm, 13 waves, twist", dict(Az=0.8, dphi=2 * math.pi / 5)),
         ("radial wave 3 mm, 13 waves, twist (does not fit)", dict(Ar=3.0, dphi=2 * math.pi / 5)),
         ("radial wave 3 mm, 13 waves, no twist (does not fit)", dict(Ar=3.0))]
if __name__ == "__main__":
    t0 = time.time(); os.makedirs(OUT, exist_ok=True); res = dict(status=__doc__.split("\n")[2], cases=[])
    for name, kw in CASES:
        paths = wavy_coil(**kw); L = RD.neumann(paths, EPS)
        fits = kw.get("Az", 0.0) <= 0.1 and 113.4 - kw.get("Ar", 0.0) * 2 - 5 * 1.6 >= 103.8 - 1e-9
        row = RD.evaluate(name, paths, L, dict(params={k: round(v, 3) for k, v in kw.items()}, fits_window=bool(fits)))
        # ripple of the field around the ring 20 mm below the coil (where the wave shows), and at 100 mm under the rim
        th = np.linspace(0, 2 * math.pi, 181)[:-1]; Bf = RD.Field(paths)
        for tag, zz in (("ripple_20mm_below_pct", -0.0115), ("ripple_100mm_below_pct", -0.0915)):
            P = np.c_[0.1086 * np.cos(th), 0.1086 * np.sin(th), np.full(len(th), zz)]; Bm = np.linalg.norm(Bf(P), axis=1)
            row[tag] = round(float(100 * (Bm.max() - Bm.min()) / Bm.mean()), 2)
        res["cases"].append(row); print(name, "ripple", row["ripple_20mm_below_pct"], row["ripple_100mm_below_pct"], "t", round(time.time() - t0), flush=True)
    b = res["cases"][0]
    for r in res["cases"]: r["depth_vs_flat_pct"] = {k: round(100 * (v / b["mono_depth_mm"][k] - 1), 1) for k, v in r["mono_depth_mm"].items()}
    res["seconds"] = round(time.time() - t0); json.dump(res, open(os.path.join(OUT, "rf2_wave.json"), "w"), indent=1, default=float)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(12, 4)); ax = fig.add_subplot(1, 2, 1, projection="3d")
    for p in wavy_coil(Ar=0.8, Az=0.8, psi=math.pi / 2, dphi=2 * math.pi / 5)[::6]:
        sel = p[: len(p) // 6] * 1e3; ax.plot(sel[:, 0], sel[:, 1], sel[:, 2], lw=0.8)
    ax.set_title("corkscrew wave, one column per row, 60 deg of the ring (each row twisted 72 deg)", fontsize=7); ax.set_box_aspect((2, 2, 0.6))
    ax2 = fig.add_subplot(1, 2, 2); names = [r["name"] for r in res["cases"]]; y = np.arange(len(names))
    ax2.barh(y, [r["depth_vs_flat_pct"]["1.0 g"] for r in res["cases"]], color=["#2e7d32" if r["fits_window"] else "#999" for r in res["cases"]])
    ax2.set_yticks(y); ax2.set_yticklabels(names, fontsize=6); ax2.axvline(0, color="k", lw=0.6); ax2.set_xlabel("1 g mono depth vs flat turns (%)")
    ax2.set_title("MODELED, 10.8 mJ, mono channel; grey = does not fit option B's window", fontsize=8)
    fig.savefig(os.path.join(OUT, "rf2_wave.png"), dpi=130, bbox_inches="tight"); print("done", res["seconds"])
