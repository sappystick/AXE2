#!/usr/bin/env python3
"""RF2 telescope wall options vs a commercial carbon shaft (2026-10-30, owner sources). MODELED.

Sources: Steve's Detector Rods Garrett AT / ACE two-piece carbon shaft (middle 19.75 in + lower 20 in, combined 5.5 oz / 156 g, 3K twill, injection-moulded
nylon cam lock; data/datasheets/Steves_Garrett_two_piece_CF_shaft.pdf); Rock West octagonal tubing (3k 2x2 twill, standard modulus, OD 1.922-2.130 in,
wall 0.076-0.100 in, 70 in max); Minelab SDC 2300 shaft parts list (camlock lever 8008-0061, pressure rubber block 8008-0062, coil-cable strain-relief
pin 4308-0031, shaft-to-hinge cap screw 0703-0204).
Model: the three keyed rectangular profiles of rf2_chassis (21 / 26 / 31 mm, corner radius ignored), extended to the full 980 mm pivot-to-hinge length
with 100 mm overlaps, as a cantilever from the hinge carrying the head (rf2_head_check mass) at the tip plus the tubes' own weight; the overlap takes
the smaller section (conservative). E = 50 GPa and density 1.55 g/cm3 for 3K twill carbon / epoxy are ASSUMED (no modulus in the sources).
Writes rf2/results/rf2_shaft_options.json.   usage: python3 rf2/rf2_shaft_options.py"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); sys.path.insert(0, HERE)
E_CF, RHO_CF = 50e3, 1.55e-3                     # N/mm2, g/mm3 (ASSUMED)
GARRETT = dict(len_mm=(19.75 + 20.0) * 25.4, mass_g=156.0)
OCTO_OD_MM = [round(v * 25.4, 1) for v in (2.130, 2.098, 1.922, 1.922)]

def I_rect(w, h, t): return (w * h ** 3 - (w - 2 * t) * (h - 2 * t) ** 3) / 12.0
def A_rect(w, h, t): return w * h - (w - 2 * t) * (h - 2 * t)

def deflection(wall, tubes, L=980.0, ov=100.0, P_tip_N=0.0):
    sec = [("outer", tubes["outer"][0]), ("mid", tubes["mid"][0]), ("inner", tubes["inner"][0])]
    seg = (L + 2 * ov) / 3.0; x = np.linspace(0, L, 2001)
    def size_at(xx):
        i = min(int(xx // (seg - ov)), 2) if xx < L else 2
        return sec[i][1]
    W = np.array([size_at(v) for v in x]); EI = E_CF * np.array([I_rect(w, w, wall) for w in W]); q = RHO_CF * np.array([A_rect(w, w, wall) for w in W]) * 9.81e-3   # N/mm
    shear = np.array([np.trapezoid(q[i:], x[i:]) for i in range(len(x))]) + P_tip_N
    M = np.array([np.trapezoid(shear[i:], x[i:]) for i in range(len(x))])               # moment at x from the load beyond it
    curv = M / EI; slope = np.concatenate([[0], np.cumsum((curv[1:] + curv[:-1]) / 2 * np.diff(x))])
    defl = np.concatenate([[0], np.cumsum((slope[1:] + slope[:-1]) / 2 * np.diff(x))])
    mass = sum(RHO_CF * A_rect(w, w, wall) * 380.0 for _, w in sec)
    return float(defl[-1]), float(mass)

def main():
    import rf2_chassis as CS
    tubes = CS.SPEC["tubes"]; wall0 = CS.SPEC["wall"]
    hc = json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_check.json")))
    m_head = hc["checks"]["mass_g"]["total_islands_only"]                                   # head with island potting (rf2_head_check)
    P = (m_head + 40.0) * 9.81e-3                                                          # head + yoke (40 g ASSUMED)
    rows = []
    for wall in (1.5, 1.2, 1.0, 0.8):
        d, m = deflection(wall, tubes, P_tip_N=P); rows.append(dict(wall_mm=wall, tubes_g=round(m), tip_sag_mm=round(d, 2)))
    base = next(r for r in rows if r["wall_mm"] == wall0)
    for r in rows: r["delta_g"] = r["tubes_g"] - base["tubes_g"]; r["sag_ratio"] = round(r["tip_sag_mm"] / base["tip_sag_mm"], 2)
    garrett_g_per_m = GARRETT["mass_g"] / GARRETT["len_mm"] * 1000
    ours_g_per_m = base["tubes_g"] / 1.14
    res = dict(status="MODELED: E 50 GPa and density 1.55 g/cm3 ASSUMED; rectangular sections without corner radii; static sag under the head only (no swing loads)",
               head_plus_yoke_g=round(m_head + 40), current_wall_mm=wall0, walls=rows,
               benchmark=dict(garrett_two_piece_g=GARRETT["mass_g"], garrett_len_mm=round(GARRETT["len_mm"]), garrett_g_per_m=round(garrett_g_per_m), ours_g_per_m=round(ours_g_per_m),
                              note="the Garrett figure includes a nylon cam lock but its tube diameter is not given; ours is three nested keyed profiles (the overlaps double the section)"),
               octagonal=dict(od_mm=OCTO_OD_MM, fits=False, note="Rock West octagonal stock is 48.8-54.1 mm OD: larger than the 31 mm outer profile; no stock octagonal in the 21-31 mm range in the listing"),
               clamp=dict(pattern="SDC 2300: camlock lever (8008-0061) pressing a rubber pressure block (8008-0062) onto the inner section; coil-cable strain-relief pin (4308-0031)",
                          adopt="printed cam lever + elastomer pressure block through a window in the outer profile (P3.4); a strain-relief pin through a loop of the cord flex at the gland"))
    w12 = next(r for r in rows if r["wall_mm"] == 1.2)
    res["findings"] = [f"walls 1.5 -> 1.2 mm: tubes {base['tubes_g']} -> {w12['tubes_g']} g ({w12['delta_g']:+d} g), static tip sag {base['tip_sag_mm']} -> {w12['tip_sag_mm']} mm",
                       f"ours {res['benchmark']['ours_g_per_m']} g/m of nested profile vs the Garrett two-piece {res['benchmark']['garrett_g_per_m']} g/m (with its cam lock)"]
    res["ok"] = True
    json.dump(res, open(os.path.join(OUT, "rf2_shaft_options.json"), "w"), indent=1)
    for f in res["findings"]: print("-", f)
    for r in rows: print(r)
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
