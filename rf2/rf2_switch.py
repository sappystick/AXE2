#!/usr/bin/env python3
"""AXE2 stage 3: the transmit switch's output capacitance in the coil's decay tail. MODELED; values read from datasheet curves are marked READ.
In the tail the drain sits at about VBUS (26 V): the switch adds its Coss AT 26 V to the coil node, and the node capacitance with L sets how soon the
coil is quiet (rf2_timing.simulate, critical damping, 100 nV + 2 us preamp recovery). Superjunction MOSFETs have a Coss cliff right there.
  Infineon IPB65R095C7 (650 V CoolMOS C7, today's TX switch; data/datasheets): Coss 33 pF at 400 V; Co(er) 69 pF, Co(tr) 763 pF (0-400 V);
      Diagram 14: Coss about 400 pF at 26 V (READ; the curve falls from about 8 nF below 20 V to about 60 pF at 50 V).
  Wolfspeed C3M0280090J (900 V SiC, D2PAK-7; Rev. 04 12/2024, data/datasheets): Coss 26 pF at 600 V, Eoss 5.5 uJ; Fig. 17: Coss about 110 pF at 25 V (READ);
      RDS(on) 320 mohm typ (VGS 15 V, 7.5 A); ID 11 A (TC 25 C), 22 A pulsed; VGS -4 / +15 V.
  onsemi NTBG080N120SC1 (1200 V SiC, D2PAK-7L): 'typ. Coss 79 pF' (front page; curve not read).
Node = winding (132 pF, rf2_zones / rf2_taper, eps 2.5) + switch Coss(26 V) + leads, damping and preamp (50 pF, ASSUMED) [+ syntactic potting: winding 95 pF].
Reported per case: node pF, first gate, mono depth 0.1 / 1 / 20 g (option-B coil, 10.8 mJ, MP1 v2 noise, in air), and the earlier 500 pF assumption.
usage: python3 rf2/rf2_switch.py -> rf2/results/rf2_switch.json"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z, rf2_coil_search as C, rf2_rodin as RD, rf2_receiver_combo as RC
OUT = os.path.join(HERE, "results"); T = Z.T; L = Z.L; I = Z.I0; R = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU
CASES = [("earlier assumption: 500 pF node", 500e-12),
         ("IPB65R095C7 (Coss 400 pF at 26 V, READ) + winding 132 + 50", 582e-12),
         ("C3M0280090J SiC (Coss 110 pF at 25 V, READ) + winding 132 + 50", 292e-12),
         ("C3M0280090J + syntactic potting (winding 95 pF) + 50", 255e-12),
         ("bound: 60 pF switch (a GaN / low-Coss part, UNVERIFIED) + 95 + 30", 185e-12)]
if __name__ == "__main__":
    res = dict(status=__doc__.split("\n")[1], cases=[])
    Bf = lambda P: C.B_turns(T, P)
    for lab, cn in CASES:
        g = RD.gate_for(L, R, I, Cn=cn); d = {f"{m} g": RC.depth(Bf, I, g * 1e-6, m, Bf) for m in (0.1, 1.0, 20.0)}
        row = dict(case=lab, node_pF=round(cn * 1e12), first_gate_us=g, mono_depth_mm=d); res["cases"].append(row); print(json.dumps(row), flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_switch.json"), "w"), indent=1)
