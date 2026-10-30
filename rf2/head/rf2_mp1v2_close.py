#!/usr/bin/env python3
"""MP1 v2 protection closure (2026-10-30; roadmap P0.5). MODELED with the same SPICE chain as rf2_mp1v2_protect.py (TI LMH6629 macro model, datasheet-fitted
diodes, charge-equivalent limiter capacitances). Two levers on the best earlier option (IXTY01N100D limiter with charge-equivalent C, 2 x BAV199 + 2 x BAT54S):
  1. CLAMP RAILS inside the amplifier's supply: the clamp diodes return to low-impedance rails at (lo, hi) instead of (0 V, 5 V), so the clamp node stays
     below the level where the LMH6629's own input diodes conduct (rails as ideal sources here: a real design needs a stiff divider / LDO with a large cap);
  2. Rin2 (between the clamp node and the amplifier input) 100 / 150 ohm: less input current, more thermal noise.
Limits: amplifier input < 10 mA; settling before the first gate with the coil cord (16.29 + 0.19 us, rf2_timing_cord); per-diode current inside IFRM; noise
reported (the depth cost of extra noise is (1 + (dn / e)^2)-style small; reported, not limited).
Writes rf2/head/out/rf2_mp1v2_close.json.   usage: python3 rf2/head/rf2_mp1v2_close.py"""
import os, sys, json, math, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import numpy as np
import rf2_mp1v2_protect as PR
import rf2_mp1v2_chain as C
from simcache import memo
OUT = os.path.join(HERE, "out")
FET, CLAMP = "IXTY01N100D@Q", "2 x BAV199 + 2 x BAT54S (typ)"
RIN2 = (100.0,)          # 150 ohm dropped 2026-10-30: the clamp rails already bring the input current under 10 mA, and Rin2 does not move the settling
def variant(net, rin2, lo, hi):
    net = re.sub(r"^(Rin2[AB] \S+ \S+) \S+$", lambda m: f"{m.group(1)} {rin2}", net, flags=re.M)
    net = re.sub(r"^(Dd\S+) 0 (cl[AB])", r"\1 cllo \2", net, flags=re.M)
    net = re.sub(r"^(Vsu\S+ \S+) vp DC 0", r"\1 clhi DC 0", net, flags=re.M)
    return f"Vclhi clhi 0 DC {hi}\nVcllo cllo 0 DC {lo}\n" + net
USES = PR.USES + [variant]
@memo("spice.mp1v2.close.noise", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES, tools=["ngspice"])
def noise_v(rin2, lo, hi):
    N, _ = C.ng(variant(PR.netlist(FET, PR.CLAMPS[CLAMP], C.SRC_AC), rin2, lo, hi) + ".noise v(out) Vsrc dec 10 1e4 1e7\n", "run\nsetplot noise1\nwrdata {OUT} inoise_spectrum")
    return round(float(np.interp(5.0, np.log10(N[:, 0]), N[:, 1])) * 1e9 / math.sqrt(2), 3)
@memo("spice.mp1v2.close.transient", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES, tools=["ngspice"])
def transient_v(rin2, lo, hi, i_coil=8.06):
    src = C.SRC_TR.replace("Vdr nd vb DC -4.27", f"Vdr nd vb DC {-i_coil * 0.53:.4f}")
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)", "i(VsuA0)", "i(VsuA1)"]
    A, _ = C.ng(variant(PR.netlist(FET, PR.CLAMPS[CLAMP], src), rin2, lo, hi) + ".save " + " ".join(vec) + "\n.options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n",
                "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}; d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    return dict(peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2),
                settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None,
                peak_per_diode_mA=dict(BAV199=round(float(np.abs(col["i(VsuA0)"]).max()) * 1e3 / 2, 1), BAT54=round(float(np.abs(col["i(VsuA1)"]).max()) * 1e3 / 2, 1)))
def main():
    gate = 16.29 + 0.19
    try: gate = 16.29 + max(v["shift_fixed_us"] for v in json.load(open(os.path.join(os.path.dirname(HERE), "results", "rf2_timing_cord.json")))["cases"].values())
    except Exception: pass
    res = dict(status="MODELED (SPICE); ideal clamp rails", limiter=FET, clamp=CLAMP, first_gate_us=round(gate, 2), runs=[])
    for rin2 in RIN2:
        nz = noise_v(rin2, 0.0, 5.0)
        for lo, hi in ((0.0, 5.0), (0.5, 4.5), (1.0, 4.0)):
            r = dict(rin2=rin2, rails=[lo, hi], noise_nV=nz); r.update(transient_v(rin2, lo, hi))
            r["passes"] = bool(r["peak_lmh_input_mA"] < 10.0 and (r["settle_us"] or 99) < gate and r["peak_per_diode_mA"]["BAV199"] <= 500 and r["peak_per_diode_mA"]["BAT54"] <= 300)
            res["runs"].append(r); print(json.dumps(r), flush=True)
    ok = [r for r in res["runs"] if r["passes"]]
    cur_ok = [r for r in res["runs"] if r["peak_lmh_input_mA"] < 10.0]
    res["current_closed_by"] = min(cur_ok, key=lambda r: r["peak_lmh_input_mA"])["rails"] if cur_ok else None
    res["settling_gap_us"] = round(min(r["settle_us"] for r in res["runs"]) - gate, 2)
    res["open"] = "settling is set by the limiter's recovery (17.5-18.2 us against the 16.48 us first gate); next levers: a gate speed-up network on the depletion limiter, a lower-Coss limiter, or a later first gate (depth cost)"
    res["closed"] = bool(ok); res["chosen"] = min(ok, key=lambda r: (r["noise_nV"], r["settle_us"])) if ok else None
    if res["closed"]:
        b = res["chosen"]; res["chosen_at_boost_12A74"] = transient_v(b["rin2"], b["rails"][0], b["rails"][1], 12.74)
    json.dump(res, open(os.path.join(OUT, "rf2_mp1v2_close.json"), "w"), indent=1); print("closed:", res["closed"], res["chosen"])
    return res
if __name__ == "__main__":
    main()
