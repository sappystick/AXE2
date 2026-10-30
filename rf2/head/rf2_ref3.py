#!/usr/bin/env python3
"""RF2 Phase B: REF3 reference coil (the EMI canceller's input, rf2_emi.py) sized from the noise it adds (2026-10-29). MODELED.
The canceller subtracts w x REF from the mono; with REF area-turns = g x the mono's, w = 1 / g and the REF channel's own noise e_ref enters the mono as
e_ref / g. Depth follows SNR^(1/5.1) (sim_head1 scaling), so the penalty is (1 + (e_ref / g / e_mono)^2)^(-1 / 10.2).
e_ref = sqrt(e_preamp^2 + 4 k T R_coil) with e_preamp = e_mono = 1.7 nV/rtHz; R_coil = rho x wire length / wire area; air-core square-ish former (one per axis,
3 orthogonal), copper density 8.96. The study in rf2_emi.py ASSUMED e_ref = 1.9 nV/rtHz at g = 3.
usage: python3 rf2/head/rf2_ref3.py"""
import os, sys, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rf2_ground as G
kT4 = 4 * 1.380649e-23 * 300; RHO = 1.72e-8; E_MONO = 1.7e-9
NA_MONO = sum(math.pi * r ** 2 for r, z, s in G.COILS["A"]["T"])
rows = []
for g in (1.0, 2.0, 3.0):
    for d in (0.06, 0.08, 0.10, 0.12):                       # former diameter (each axis a circular winding of this diameter)
        for wd in (0.15, 0.20, 0.25, 0.32):                  # wire diameter, mm
            A = math.pi * (d / 2) ** 2; N = g * NA_MONO / A; L = N * math.pi * d; aw = math.pi * (wd * 1e-3 / 2) ** 2; R = RHO * L / aw
            e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g / E_MONO) ** 2) ** (-1 / 10.2) - 1
            mass = 3 * L * aw * 8960 * 1e3
            rows.append(dict(gain=g, former_mm=round(d * 1e3), wire_mm=wd, turns_per_axis=round(N), wire_m_per_axis=round(L, 1), R_ohm=round(R, 1),
                             e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g_3axes=round(mass, 1)))
ok = [r for r in rows if r["depth_penalty_pct"] >= -1.5 and r["former_mm"] <= 100]
best = min(ok, key=lambda r: (r["copper_g_3axes"], r["former_mm"])) if ok else None
res = dict(status="MODELED (RF2 REF3 sizing)", NA_mono_m2=round(NA_MONO, 3), rule="depth penalty <= 1.5 %, former <= 100 mm, then least copper", chosen=best, options=rows,
           emi_study_assumption=dict(gain=3, e_ref_nV=1.9))
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "rf2_ref3.json"), "w"), indent=1)
print("chosen", best)
for r in rows:
    if r["gain"] == 3 and r["former_mm"] in (80, 100): print(r)
