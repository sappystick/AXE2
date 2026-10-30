#!/usr/bin/env python3
"""RF2 independent field cross-check (2026-10-30): the rim mono coil of rf2_head.SPEC (26 turns in 3 columns x 9 rows) evaluated twice, with the repo's
elliptic-integral loop field (rf2_coil_search.loop_B, the code behind every RF2 depth number) and with magpylib 6 (an independent analytic library,
requirements-rf2.txt). Points: on the axis and off the axis down to 500 mm below the head, where the depth numbers come from. The check passes when the
two agree to 1e-6 relative; it validates the field code, not the depth model (target response, noise and ground stay MODELED as in the studies).
usage: python3 rf2/head/rf2_field_xcheck.py   -> out/rf2_field_xcheck.json"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import magpylib as magpy
import rf2_head as H, rf2_coil_search as C
def rim_turns():
    c = H.SPEC["coil"]; sites = [(r, c["row0_z"] + k * c.get("row_pitch", c["pitch"])) for k in range(c["rows"]) for r in c["columns_r"]]
    return [(r * 1e-3, z * 1e-3) for r, z in sites[:c["turns"]]]
if __name__ == "__main__":
    T = rim_turns(); P = np.array([[x, 0.0, -d] for d in (0.02, 0.05, 0.1, 0.2, 0.3, 0.5) for x in (0.0, 0.05, 0.1, 0.15, 0.25)])
    Brepo = sum(C.loop_B(r, z, P) for r, z in T)
    coll = magpy.Collection(*[magpy.current.Circle(current=1.0, diameter=2 * r, position=(0, 0, z)) for r, z in T])
    Bmp = coll.getB(P)
    rel = np.linalg.norm(Brepo - Bmp, axis=1) / np.linalg.norm(Bmp, axis=1)
    res = dict(status="MODELED field code cross-check (two independent analytic implementations); not a measurement", turns=len(T),
               points=len(P), max_rel_diff=float(rel.max()), Bz_axis_uT_per_A={f"{-p[2]*1e3:.0f} mm": round(float(Bmp[i, 2]) * 1e6, 4) for i, p in enumerate(P) if p[0] == 0},
               ok=bool(rel.max() < 1e-6))
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True); json.dump(res, open(os.path.join(HERE, "out", "rf2_field_xcheck.json"), "w"), indent=1)
    print(json.dumps(res, indent=1)); sys.exit(0 if res["ok"] else 1)
