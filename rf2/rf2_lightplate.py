#!/usr/bin/env python3
"""RF2 light plate (2026-10-30): the opaque lid with one conical well over each of the 522 LEDs, replacing the clear lid. MODELED.
Each well is a frustum from the LED (bottom d0, just clear of the 2.0 mm square emitter's 2.83 mm diagonal) up to the lid's top face (d1), through the
lid's thickness h. The wall carries a reflective liner; the well is filled flush with clear resin (seals the plate; a lens, no air gap). Monte Carlo of a
Lambertian 2 x 2 mm emitter in the well: exit efficiency and beam width against the top diameter, for the liner reflectance ASSUMED 0.90 (white TiO2 paint,
diffuse) and, as the bound, 0.98. The liner must NOT be metal (rule 5 / zone rules: a metal film near the coil is an echo target); a metallised liner would
need its own eddy study. Webs between wells and the printability limits are checked against the LED layout (rf2_ledgrid). Writes out/rf2_lightplate.json.
usage: python3 rf2/rf2_lightplate.py"""
import os, sys, json, math
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "rf2", "head"))
OUT = os.path.join(ROOT, "rf2", "head", "out")
D0, H_PLATE, MIN_WEB = 2.9, 1.5, 0.8          # bottom diameter (mm), plate thickness (lid thickness today), smallest printable web between wells (mm, ASSUMED resin/FDM limit)
def trace(d1, rho, n=60000, seed=1, h=H_PLATE, d0=D0):
    rng = np.random.default_rng(seed); r0, r1 = d0 / 2, d1 / 2; k = (r1 - r0) / h
    p = np.column_stack([rng.uniform(-1, 1, n), rng.uniform(-1, 1, n), np.zeros(n)])          # 2 x 2 mm emitter
    u1, u2 = rng.random(n), rng.random(n); st = np.sqrt(u1); ph = 2 * np.pi * u2
    d = np.column_stack([st * np.cos(ph), st * np.sin(ph), np.sqrt(1 - u1)])                  # cosine-weighted (Lambertian)
    alive = np.ones(n, bool); exited = np.zeros(n, bool); ang = np.full(n, np.nan)
    for _ in range(12):
        if not alive.any(): break
        P, D = p[alive], d[alive]
        # ray p + t d on the cone x^2 + y^2 = (r0 + k z)^2
        a = D[:, 0] ** 2 + D[:, 1] ** 2 - k * k * D[:, 2] ** 2
        b = 2 * (P[:, 0] * D[:, 0] + P[:, 1] * D[:, 1] - k * D[:, 2] * (r0 + k * P[:, 2]))
        c = P[:, 0] ** 2 + P[:, 1] ** 2 - (r0 + k * P[:, 2]) ** 2
        disc = np.maximum(b * b - 4 * a * c, 0); sq = np.sqrt(disc)
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (-b - sq) / (2 * a); t2 = (-b + sq) / (2 * a)
            tw = np.where(np.abs(a) < 1e-12, -c / b, np.where(t2 > 1e-9, t2, np.where(t1 > 1e-9, t1, np.inf)))
            tw = np.where(tw > 1e-9, tw, np.inf)
            tt = np.where(D[:, 2] > 0, (h - P[:, 2]) / D[:, 2], np.inf)                        # to the top plane
        hit_top = tt <= tw; idx = np.flatnonzero(alive)
        # exit through the top
        et = idx[hit_top]; X = P[hit_top] + D[hit_top] * tt[hit_top, None]
        okx = X[:, 0] ** 2 + X[:, 1] ** 2 <= r1 ** 2 + 1e-9
        exited[et[okx]] = True; ang[et[okx]] = np.degrees(np.arccos(np.clip(D[hit_top][okx, 2], -1, 1))); alive[et] = False
        # wall hit
        wi = idx[~hit_top]; Pw = P[~hit_top] + D[~hit_top] * tw[~hit_top, None]
        lost = rng.random(len(wi)) > rho; alive[wi[lost]] = False
        keep = ~lost; wi = wi[keep]; Pw = Pw[keep]
        ph2 = np.arctan2(Pw[:, 1], Pw[:, 0]); nrm = np.column_stack([-np.cos(ph2), -np.sin(ph2), np.full(len(wi), k)]); nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        # diffuse (Lambertian) reflection about the inward normal
        a1 = np.cross(nrm, np.array([0.0, 0.0, 1.0])); bad = np.linalg.norm(a1, axis=1) < 1e-6; a1[bad] = np.cross(nrm[bad], np.array([1.0, 0, 0])); a1 /= np.linalg.norm(a1, axis=1)[:, None]
        a2 = np.cross(nrm, a1); v1, v2 = rng.random(len(wi)), rng.random(len(wi)); s_, f_ = np.sqrt(v1), 2 * np.pi * v2
        p[wi] = Pw; d[wi] = a1 * (s_ * np.cos(f_))[:, None] + a2 * (s_ * np.sin(f_))[:, None] + nrm * np.sqrt(1 - v1)[:, None]
        alive[wi] = True
    eff = float(exited.mean()); a_ = ang[exited]
    return dict(exit_efficiency=round(eff, 3), median_half_angle_deg=round(float(np.median(a_)), 1), p90_half_angle_deg=round(float(np.percentile(a_, 90)), 1))
def main():
    import rf2_ledgrid as LG
    from scipy.spatial import cKDTree
    P = np.array([(e["x"], e["y"]) for e in LG.layout()["leds"]]); dd, _ = cKDTree(P).query(P, k=2); pitch = float(dd[:, 1].min())
    res = dict(status="MODELED (liner reflectance and printable web ASSUMED; no optical bench)", leds=len(P), min_led_pitch_mm=round(pitch, 3), plate_t_mm=H_PLATE, d_bottom_mm=D0, sweep=[])
    flat = trace(D0, 0.0, h=H_PLATE)                                                         # a straight 2.9 mm bore with an absorbing wall (no cone, no liner)
    res["straight_bore_absorbing_wall"] = flat
    for d1 in (3.5, 4.5, 5.5, 6.0, 6.5, 7.0):
        web = pitch - d1; row = dict(d_top_mm=d1, cone_half_angle_deg=round(math.degrees(math.atan((d1 - D0) / 2 / H_PLATE)), 1), web_mm=round(web, 2), web_ok=web >= MIN_WEB)
        for rho in (0.90, 0.98): row[f"rho_{rho}"] = trace(d1, rho)
        res["sweep"].append(row); print(row, flush=True)
    ok = [r for r in res["sweep"] if r["web_ok"]]
    best = max(ok, key=lambda r: r["rho_0.9"]["exit_efficiency"])                           # the widest well the web allows gives the most light; a wider mouth also gives a wider beam
    res["chosen"] = dict(d_top_mm=6.0, reason=f"a 2.0 mm web between wells (2.5 x the 0.8 mm printable minimum) keeps the plate stiff, and the exit efficiency is within {100 * (best['rho_0.9']['exit_efficiency'] - next(r for r in res['sweep'] if r['d_top_mm'] == 6.0)['rho_0.9']['exit_efficiency']):.1f} points of the widest well swept (d {best['d_top_mm']} mm, web {best['web_mm']} mm)")
    c = next(r for r in res["sweep"] if r["d_top_mm"] == 6.0)
    res["ok"] = bool(len(P) == 522 and c["web_ok"] and c["rho_0.9"]["exit_efficiency"] > flat["exit_efficiency"] * 2 and pitch - 6.0 >= 2 * MIN_WEB)
    json.dump(res, open(os.path.join(OUT, "rf2_lightplate.json"), "w"), indent=1); print(json.dumps({k: res[k] for k in ("straight_bore_absorbing_wall", "chosen", "ok")}, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
