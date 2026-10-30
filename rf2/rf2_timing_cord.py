#!/usr/bin/env python3
"""RF2 first gate with the TX pair in the coil cord (2026-10-30; roadmap P0.3). MODELED with rf2_timing.simulate (the full nonlinear turn-off + exact linear tail).
Chassis v2 puts the TX driver in the control chassis, so the TX pair runs the shaft in the coil cord (about 1.1 m at full extension). At the tail frequencies
(< 1 MHz) a 1 m pair is lumped: its capacitance adds to the coil node (the pair's inductance, about 0.7 uH, is negligible against 321 uH). Pair capacitance
50 pF/m ASSUMED (FEP twisted pair; the cord vendor sheet replaces it, roadmap P0.6). Cases: node C = the rf2_timing assumption (500 pF) and the RF2 estimate
368 pF (HANDOFF section 19), each without and with the pair; damping Rd FIXED at the no-cord critical value, and RE-TUNED to critical with the cord.
Writes rf2/results/rf2_timing_cord.json.   usage: python3 rf2/rf2_timing_cord.py"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rf2_timing as T
OUT = os.path.join(HERE, "results")
import rf2_cordflex as CFX, rf2_chassis as _CS                                   # owner 2026-10-30: the cord is a flex (HANDOFF 45)
_tel = (_CS.SPEC["st"]["hinge"][0] + _CS.SPEC["extend_max"]["inner"] + _CS.SPEC["extend_max"]["mid"]) - (_CS.SPEC["st"]["hinge"][0] - _CS.SPEC["collapse"]["inner"] - _CS.SPEC["collapse"]["mid"])
C_PAIR = CFX.cps_c_pf_per_m() * 1e-12; L_CORD = CFX.segments(_CS.SPEC["st"], _CS.SPEC["extend_max"], _tel)["tx_length_m"]
def run(cn, rd_fixed_cn=None):
    T.CN = cn
    orig = T.rd
    if rd_fixed_cn is not None: T.rd = lambda L, mode: 0.5 * math.sqrt(L / rd_fixed_cn)
    try: r = T.simulate("A alone", "critical")
    finally: T.rd = orig
    return dict(node_pF=round(cn * 1e12, 1), Rd_ohm=r["Rd_A_ohm"], first_gate_us=r["mono_clean_us"], last_diode_us=r["last_diode_us"])
def main():
    dC = C_PAIR * L_CORD; res = dict(status=f"MODELED; TX strips in the cord flex {C_PAIR * 1e12:.1f} pF/m over {L_CORD} m (coplanar strips, eps_eff ASSUMED; rf2_cordflex)", pair_pF=round(dC * 1e12, 1), cases={})
    for base in (500e-12, 368e-12):
        b = run(base); fx = run(base + dC, rd_fixed_cn=base); rt = run(base + dC)
        res["cases"][f"node {base*1e12:.0f} pF"] = dict(no_cord=b, cord_Rd_fixed=fx, cord_Rd_retuned=rt, shift_fixed_us=round(fx["first_gate_us"] - b["first_gate_us"], 2), shift_retuned_us=round(rt["first_gate_us"] - b["first_gate_us"], 2))
        print(json.dumps(res["cases"][f"node {base*1e12:.0f} pF"]), flush=True)
    worst = max(max(v["shift_fixed_us"], v["shift_retuned_us"]) for v in res["cases"].values())
    res["first_order_estimate_us"] = 0.562; res["worst_shift_us"] = worst
    res["recommendation"] = "re-tune Rd to critical with the cord in place (the TXF network value is set from this run)" if all(v["shift_retuned_us"] <= v["shift_fixed_us"] for v in res["cases"].values()) else "keep Rd at the no-cord value"
    json.dump(res, open(os.path.join(OUT, "rf2_timing_cord.json"), "w"), indent=1); print(json.dumps({k: res[k] for k in ("pair_pF", "worst_shift_us", "recommendation")}))
    return res
if __name__ == "__main__":
    main()
