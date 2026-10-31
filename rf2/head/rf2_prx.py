#!/usr/bin/env python3
"""RF2 planar nulled receive layer PRX (owner decision 2026-10-31: hybrid receive adopted). MODELED geometry; nothing built, no artwork yet.

What it is: a 2-layer polyimide flex in the z 1.60-1.70 slot between SH1 (z 1.2-1.6) and QA (moved up 0.1 mm to z 1.7-2.5). Layer 1 (bottom copper)
carries the MAIN receive spiral inside the rim coil (40 turns, 0.15 mm traces at 0.30 mm pitch, outer turn r 88.0 mm: rf2_lowL_options.json hybrid
design); layer 2 (top copper) carries the BUCKING spiral counter-wound right under the TX litz, where a turn couples strongly to the TX for little area.
The bucking radius is solved here for ZERO mutual inductance to the TX coil AS WOUND (bank fill, the owner's 2026-10-31 order, at the built z), so the
receive spiral sees no flyback EMF to first order. Spirals are modeled as concentric circles (as rf2_lowL_options does); the TX turns as coaxial circles.

Stack (ASSUMED, to fit the owner's 0.1 mm slot): 25 um adhesiveless polyimide core + 2 x 35 um copper = 0.095 mm, no coverlay (bonded with the stack's
adhesive film between SH1 and QA). NOTE: rf2_lowL_options models the RX copper as 70 um; 70 um per side cannot fit a 0.1 mm layer, so the trace
resistance here is computed with 35 um (rule 4: docs/CORRECTIONS.md row).
Leads: the spiral ends meet two pads at a feed point (r 72, 135 deg) that lies in the copper-free window of QA AND QB (searched in rf2_head_glove /
the SB1R geometry); a twisted 2-wire FEP lead rises through a 3.4 mm NPTH feed hole in QA / QB / the bay floor to the MP2 fin (122 deg).
Radial run from the spiral ends to the feed: layer-1 trace out, layer-2 trace back on the same azimuth (broadside pair: no loop area, rule 5: no closed loop).
usage: python3 rf2/head/rf2_prx.py   (prints the design)"""
import math, json
import numpy as np
from scipy.special import ellipk, ellipe
from scipy.optimize import brentq
MU0 = 4e-7 * math.pi
CU_T, PI_T = 0.035, 0.025                                     # mm (ASSUMED stack, see above)
Z0 = 1.60                                                     # PRX slot bottom (SH1 top)
Z_L1, Z_L2 = Z0 + CU_T / 2, Z0 + CU_T + PI_T + CU_T / 2       # copper centre heights: 1.6175 / 1.6775
MAIN = dict(turns=40, pitch=0.30, w=0.15, r_out=88.0)        # rf2/results/rf2_lowL_options.json hybrid rx '40 turns, 0.30 mm pitch, 0.15 mm traces', main_r_mm [88.0, 76.3]
BUCK = dict(turns=16, pitch=0.30, w=0.15)                     # same count and pitch as the lowL design (16 turns); the radius is solved below
FEED = dict(r=72.0, deg=135.0, hole_d=3.4, pad_d=1.6)         # QA / QB copper-free window (clearance measured in rf2_head_glove)
R_OUT_PI = 112.0                                              # PI outline radius (SH1 r 114; 0.5 mm wall bore beyond)
def M(R1, R2, d):
    k2 = 4 * R1 * R2 / ((R1 + R2) ** 2 + d ** 2); k = math.sqrt(k2)
    return MU0 * math.sqrt(R1 * R2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))
def m_set(radii_mm, z_mm, tx):
    """mutual inductance (H) of coaxial circles radii_mm at z_mm with the TX turns tx = [(r, z) mm]"""
    return sum(M(r * 1e-3, R * 1e-3, abs(z_mm - Z) * 1e-3) for r in radii_mm for R, Z in tx)
def main_radii(): return [MAIN["r_out"] - k * MAIN["pitch"] for k in range(MAIN["turns"])]
def design(tx):
    """solve the bucking spiral's outer radius for zero M to the TX turns tx [(r, z) mm]; returns the PRX geometry and its null sensitivity"""
    rm = main_radii(); Mm = m_set(rm, Z_L1, tx)
    buck = lambda rb: [rb - k * BUCK["pitch"] for k in range(BUCK["turns"])]
    f = lambda rb: Mm - m_set(buck(rb), Z_L2, tx)
    lo, hi = max(R for R, _ in tx) - 12.0, R_OUT_PI - 0.5
    grid = np.linspace(lo, hi, 60); vals = [f(x) for x in grid]
    root = next(brentq(f, a, b, xtol=1e-6) for a, b, fa, fb in zip(grid[:-1], grid[1:], vals[:-1], vals[1:]) if fa * fb < 0)
    rb = buck(root)
    d_z = abs(m_set(rm, Z_L1 + 0.1, tx) - m_set(rb, Z_L2 + 0.1, tx)) / Mm          # whole PRX 0.1 mm higher
    d_r = abs(Mm - m_set([r + 0.1 for r in rb], Z_L2, tx)) / Mm                       # bucking spiral 0.1 mm larger
    length = sum(2 * math.pi * r for r in rm + rb) * 1e-3
    R_ohm = length * 1.72e-8 / (MAIN["w"] * 1e-3 * CU_T * 1e-3)
    johnson = math.sqrt(4 * 1.380649e-23 * 300 * R_ohm) * 1e9
    return dict(main_turns=MAIN["turns"], main_r_mm=[round(rm[0], 3), round(rm[-1], 3)], main_z_mm=round(Z_L1, 4), buck_turns=BUCK["turns"],
                buck_r_mm=[round(rb[0], 3), round(rb[-1], 3)], buck_z_mm=round(Z_L2, 4), pitch_mm=MAIN["pitch"], trace_mm=MAIN["w"], copper_um=CU_T * 1e3,
                M_main_uH=round(Mm * 1e6, 3), M_residual_uH=round((Mm - m_set(rb, Z_L2, tx)) * 1e6, 6), null_ratio_dz_0p1mm=round(d_z, 5), null_ratio_dr_0p1mm=round(d_r, 5),
                length_m=round(length, 3), R_ohm=round(R_ohm, 1), johnson_nV=round(johnson, 2), pi_r_out_mm=R_OUT_PI, feed=FEED,
                stack="25 um PI + 2 x 35 um Cu = 0.095 mm (ASSUMED; vendor stack UNVERIFIED)", z=(Z0, round(Z0 + 0.1, 2)))
if __name__ == "__main__":
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("RF2_VARIANT", "BF"); import rf2_head as H
    print(json.dumps(H.SPEC["prx"], indent=1))
