#!/usr/bin/env python3
"""AXE2: qualification of the owner-supplied datasheets (DATASHEET_LOG RF2-DS-OWNER2) against the design, as numbers. MODELED; ASSUMED marked.
  A. Syntactic potting around the coil. Bubble permittivity 1.2-2.0 (3M, by density; linear in density between K1 0.125 and iM30K 0.60 g/cc is
     ASSUMED); composite by the Lichtenecker rule ln eps = phi ln eps_b + (1 - phi) ln eps_m (ASSUMED mixing law); matrices: MG 832TC epoxy 3.7
     (datasheet, 1 MHz) and silicone 3.1 (SCS table, lower end at 1 MHz). Winding capacitance (rf2_taper energy method) -> node (winding + SiC
     Coss 110 pF at 26 V + 50 pF ASSUMED) -> first gate (rf2_timing) -> mono depth.
  B. Quadrupole (bearing) channel with the INA849: 1.0 nV/rtHz + board thermal noise (10.4 ohm, 35 um) + 1.1 pA/rtHz x 10.4 ohm, against the
     1.7 nV/rtHz used so far; depth by rf2_coil_search.evaluate (the quadrupole channel) on the option-B coil.
  C. BAT15-03W anti-parallel clamp at the LMH6629 input: IF max 110 mA limits Rin2 from the 6.55 V clamp node: Rin2 >= (6.55 - VF) / 0.110;
     the mono noise for that Rin2 (quadrature from the decided 1.7 nV/rtHz at Rin2 = 100 ohm) and the mono depth.
usage: python3 rf2/rf2_qualify.py -> rf2/results/rf2_qualify.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z, rf2_coil_search as C, rf2_rodin as RD, rf2_receiver_combo as RC, rf2_taper as TP, rf2_depth_levers as DL
OUT = os.path.join(HERE, "results"); kB, TK = 1.380649e-23, 300.0
T, L, I = Z.T, Z.L, Z.I0; Rw = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU; Bf = lambda P: C.B_turns(T, P)
def eps_bubble(rho): return 1.2 + 0.8 * (rho - 0.125) / (0.60 - 0.125)
if __name__ == "__main__":
    res = dict(status=__doc__.split("\n")[1], potting=[], quad=[], clamp={})
    seq = TP.order(TP.sites(*TP.SHAPES["rect 5 x 6"]), "layered")
    for grade, rho in (("K1", 0.125), ("S22", 0.22), ("iM30K", 0.60)):
        for mat, em in (("832TC epoxy", 3.7), ("silicone", 3.1)):
            for phi in (0.4, 0.6):
                eb = eps_bubble(rho); e = math.exp(phi * math.log(eb) + (1 - phi) * math.log(em)); TP.EPS_R = e; Cw, _ = TP.self_cap(seq)
                g = RD.gate_for(L, Rw, I, Cn=Cw + 160e-12); d = {f"{m} g": RC.depth(Bf, I, g * 1e-6, m, Bf) for m in (0.1, 1.0)}
                row = dict(bubbles=grade, eps_bubble=round(eb, 2), matrix=mat, phi=phi, eps_composite=round(e, 2), C_winding_pF=round(Cw * 1e12, 1),
                           first_gate_us=g, mono_depth_mm=d); res["potting"].append(row); print(json.dumps(row), flush=True)
    TP.EPS_R = 2.5
    # B. quadrupole channel
    Rb = 10.44; e_ina = math.sqrt(1.0e-9 ** 2 + 4 * kB * TK * Rb + (1.1e-12 * Rb) ** 2)
    for lab, nq in (("1.7 nV/rtHz (used so far)", 1.7e-9), (f"INA849: {e_ina*1e9:.2f} nV/rtHz", e_ina)):
        C.NOISE_Q = nq; row, *_ = C.evaluate(lab, T, 1, masses=(1.0, 20.0)); res["quad"].append(dict(case=lab, noise_nV=round(nq * 1e9, 3), quad_depth_mm=row["depth_mm"]))
    C.NOISE_Q = 1.7e-9
    # C. BAT15 clamp
    vn, rmin = 6.55, (6.55 - 0.32) / 0.110; r2 = 68.0; base2 = 1.7e-9 ** 2 - 4 * kB * TK * 100.0; n68 = math.sqrt(base2 + 4 * kB * TK * r2)
    shot = math.sqrt(2 * 1.602e-19 * 5e-6) * (r2 + 22 + 0.55)
    d68, _, _ = DL.mono_depth(T, 16.33, noise=math.hypot(n68, shot)) if hasattr(DL, "mono_depth") else (None, 0, 0)
    res["clamp"] = dict(Rin2_min_ohm=round(rmin, 1), Rin2_chosen_ohm=r2, peak_clamp_current_mA=round((vn - 0.32) / r2 * 1e3, 1), IF_max_mA=110,
                        mono_noise_nV=round(math.hypot(n68, shot) * 1e9, 3), leakage_shot_noise_bound_nV=round(shot * 1e9, 3), input_capacitance_pF=0.56,
                        mono_depth_mm_at_16p3us=d68, note="anti-parallel pair across the LMH6629 inputs; the BAV199 rail clamps stay (BAT15 VR max 4 V)")
    print(json.dumps(res["clamp"]), flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_qualify.json"), "w"), indent=1); print("done")
