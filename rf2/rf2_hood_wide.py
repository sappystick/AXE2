#!/usr/bin/env python3
"""AXE2 study, part 2 of the ferrite hood (rf2_hood.py found that ferrite wrapped closely around the bundle raises L without adding far field).
Here the ferrite is a WIDE layer over the head (the image-plane mechanism that the 'ideal plate' check confirmed): a full-face disc or an annulus,
3C90 tiles (fill 0.95 ASSUMED), above the coil and the islands (option B: island tops and coil top <= 12.6, display at 13.1, so 0.5 mm fits with no
clearance; thicker layers raise the head by the excess). Each layer is also run with the turn count cut until L returns to about the option-B
value (323 uH), so the first gate stays early (fewer turns: the last turns of the 5 x 6 fill, top row first, are removed).
Same solver, checks and depth chain as rf2_hood.py. MODELED; the ferrite is DC and lossless (no viscosity), and the effect on the quadrupole receive
boards under the ferrite is not modeled.
usage: python3 rf2/rf2_hood_wide.py -> rf2/results/rf2_hood_wide.json"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_hood as H, rf2_coil_search as C, rf2_taper as TP
OUT = H.OUT
LAYERS = [("disc r 0-114, 0.5 mm (fits option B)", [(0.0, 114.0, 12.6, 13.1)]), ("disc r 0-114, 1.0 mm", [(0.0, 114.0, 12.6, 13.6)]),
          ("disc r 0-114, 2.0 mm", [(0.0, 114.0, 12.6, 14.6)]), ("annulus r 60-114, 1.0 mm", [(60.0, 114.0, 12.6, 13.6)]),
          ("annulus r 85-114, 1.0 mm", [(85.0, 114.0, 12.6, 13.6)])]
def coil_n(n):
    S = sorted(TP.sites(*TP.SHAPES["rect 5 x 6"]))[:n]; return [(TP.geom(s)[0] * 1e-3, TP.geom(s)[1] * 1e-3, 1) for s in S]
if __name__ == "__main__":
    t0 = time.time(); res = dict(status=__doc__.split("\n")[1], cases=[])
    for lab, boxes in LAYERS:
        top = max(b[3] for b in boxes); extra = dict(head_mm=round(H.H_B + max(0.0, top - H.Z_DISP), 2), fits_option_B=top <= H.Z_DISP + 1e-9, turns=26)
        res["cases"].append(H.run(lab + ", 26 turns", "rect 5 x 6", "wide", 0, "3C90 MnZn", boxes=boxes, extra=extra))
        mu_c = H.cells(boxes, 2300); n = 26
        while n > 12:                                                   # fewest-turn change that brings L back to about 323 uH
            T = coil_n(n - 1); air = H.solve(np.ones((H.NR - 1, H.NZ - 1)), T, 1.0); re = H.Reaction(H.solve(mu_c, T, 1.0) - air)
            L = C.L_turns(T) + 2 * math.pi * float(sum(re.f([[r, z]])[0] for r, z, s in T))
            n -= 1
            if L <= 330e-6: break
        name = f"rect 5 x 6 first {n}"; T = coil_n(n); H._AIR.pop(name, None)
        H.TP.SHAPES.pop(name, None); C_ = H.coil
        H.coil = lambda nm, n=n, C_=C_: coil_n(n) if nm == name else C_(nm)
        res["cases"].append(H.run(f"{lab}, {n} turns (L back to about 323 uH)", name, "wide", 0, "3C90 MnZn", boxes=boxes, extra=dict(extra, turns=n)))
        H.coil = C_; print("t", round(time.time() - t0), flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_hood_wide.json"), "w"), indent=1, default=float); print("done", round(time.time() - t0))
