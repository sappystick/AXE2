#!/usr/bin/env python3
"""AXE2 study, part 3 (owner 2026-10-30): the Fair-Rite materials, and what beats the option-B rim coil if the footprint may grow. MODELED.
  A. Fair-Rite 77 (MnZn, mu_i 2000, 510 mT at 5 Oe, 1 ohm m) and 61 (NiZn, mu_i 125, 250 mT at 15 Oe, 1e6 ohm m) (owner-supplied web datasheets,
     data/datasheets/FairRite_*_material_webpage.pdf) in the key layers of rf2_hood_wide: full-face disc 0.5 / 2.0 mm, plate to r 300.
  B. A ferrite BRIM: the option-B coil (D233 head) with a 2 mm Fair-Rite 77 annulus reaching beyond the head (r 100-170, r 100-230). The head then grows
     to the brim's diameter.
  C. The plain alternative for the same growth: a larger head with the same 5 x 6 rim coil moved out to the new rim (r_out = D/2 - 3.1 mm), turns cut so
     that L stays about 323 uH (same driver, same gate), no ferrite. D 233 / 260 / 290 / 340 / 400 mm.
  D. Both: the D340 coil plus a 2 mm Fair-Rite 77 disc over its whole face (run in a sub-process with the fine grid moved to r 140-175).
Same solver, checks and depth chain as rf2_hood.py (mono channel, 10.8 mJ, MP1 v2 noise, gate per L, gold in air). Not modeled: ferrite viscosity /
loss, the heavier head's swing and the larger coil's larger ground signal (ground and EMI pick-up grow with the loop area).
usage: python3 rf2/rf2_hood_size.py -> rf2/results/rf2_hood_size.json"""
import os, sys, json, math, time, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_hood as H, rf2_coil_search as C
OUT = H.OUT; COILS = {}; _coil = H.coil
H.coil = lambda nm: COILS[nm] if nm in COILS else _coil(nm)
def rim_coil(D, n):
    rout = D / 2 - 3.1; S = sorted((i, j) for i in range(5) for j in range(6))[:n]
    return [((rout - 1.6 * j) * 1e-3, (5.2 + 1.6 * i) * 1e-3, 1) for i, j in S]
def coil_for_L(D, L0=323.4e-6):
    best = min(range(10, 31), key=lambda n: abs(C.L_turns(rim_coil(D, n)) - L0)); return best, rim_coil(D, best)
if __name__ == "__main__" and "--d340" in sys.argv:
    n, T = coil_for_L(340); COILS["D340"] = T; rows = []
    rows.append(H.run(f"D340 head, rim coil {n} turns, no ferrite (fine grid at the coil)", "D340", None, 0, "Fair-Rite 77 MnZn", extra=dict(head_D_mm=340, turns=n)))
    rows.append(H.run(f"D340 head, rim coil {n} turns + 2 mm Fair-Rite 77 disc r 0-170", "D340", "wide", 0, "Fair-Rite 77 MnZn", boxes=[(0.0, 170.0, 12.6, 14.6)],
                      extra=dict(head_D_mm=340, turns=n, head_mm=H.H_B + 1.5)))
    json.dump(rows, open(os.path.join(OUT, "rf2_hood_size_d340.json"), "w"), indent=1, default=float); sys.exit(0)
if __name__ == "__main__":
    t0 = time.time(); res = dict(status=__doc__.split("\n")[1], materials=[], brim=[], head_size=[], combined=[])
    for mat in ("Fair-Rite 77 MnZn", "Fair-Rite 61 NiZn"):
        for lab, boxes in (("disc r 0-114, 0.5 mm (fits option B)", [(0.0, 114.0, 12.6, 13.1)]), ("disc r 0-114, 2.0 mm", [(0.0, 114.0, 12.6, 14.6)]),
                           ("plate r 0-300, 2.0 mm (outside the head)", [(0.0, 300.0, 12.6, 14.6)])):
            res["materials"].append(H.run(f"{mat}: {lab}", "rect 5 x 6", "wide", 0, mat, boxes=boxes, extra=dict(head_D_mm=233 if "300" not in lab else 600)))
    for r1 in (170, 230):
        res["brim"].append(H.run(f"D233 coil + 2 mm Fair-Rite 77 brim r 100-{r1} (head D{2 * r1})", "rect 5 x 6", "wide", 0, "Fair-Rite 77 MnZn",
                                 boxes=[(100.0, r1, 12.6, 14.6)], extra=dict(head_D_mm=2 * r1)))
    for D in (233, 260, 290, 340, 400):
        n, T = coil_for_L(D); COILS[f"D{D}"] = T; Ls = C.L_turns(T); I = math.sqrt(2 * H.E0 / Ls); Rw = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU
        g = H.RD.gate_for(Ls, Rw, I); Bf = lambda P, T=T: C.B_turns(T, P)
        d = {f"{m} g": H.RC.depth(Bf, I, g * 1e-6, m, Bf) for m in H.MASSES}
        row = dict(case=f"D{D} head, rim coil r_out {D / 2 - 3.1:.1f} mm, {n} turns", head_D_mm=D, turns=n, L_uH=round(Ls * 1e6, 1), I_A=round(I, 2), first_gate_us=g,
                   wire_m=round(sum(2 * math.pi * r for r, z, s in T), 2), mono_depth_mm=d); res["head_size"].append(row); print(json.dumps(row), flush=True)
    env = dict(os.environ, HOOD_FINE_R="0.140,0.175"); subprocess.run([sys.executable, os.path.abspath(__file__), "--d340"], env=env, check=True)
    res["combined"] = json.load(open(os.path.join(OUT, "rf2_hood_size_d340.json"))); os.remove(os.path.join(OUT, "rf2_hood_size_d340.json"))
    base = res["head_size"][0]
    for grp in ("materials", "brim", "head_size", "combined"):
        for r in res[grp]: r["depth_vs_optionB_pct"] = {k: round(100 * (v / base["mono_depth_mm"][k] - 1), 1) for k, v in r["mono_depth_mm"].items()}
    res["seconds"] = round(time.time() - t0); json.dump(res, open(os.path.join(OUT, "rf2_hood_size.json"), "w"), indent=1, default=float); print("done", res["seconds"])
