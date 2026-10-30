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
def main_all():
    """levers 1-4; the closure uses lever 4 (high clamp rails + series isolation switch) when it passes"""
    res = main(); gate = res["first_gate_us"]; res["series_switch"] = []
    for lo, hi in ((-9.5, 14.5), (-4.5, 9.5)):
        for tc in (11.5, 12.0, 12.5):
            r = dict(rin2=100.0, rails=[lo, hi], noise_nV=res["runs"][0]["noise_nV"]); r.update(transient_series(100.0, lo, hi, tc))
            r["passes"] = bool(r["peak_lmh_input_mA"] < 10.0 and (r["settle_us"] or 99) < gate and r["peak_per_diode_mA"]["BAV199"] <= 500 and r["peak_per_diode_mA"]["BAT54"] <= 300
                               and (hi - lo) <= 0.8 * 30.0)                                       # BAT54 VRRM 30 V: rail-to-rail reverse voltage <= 80 %
            res["series_switch"].append(r)
    ok = [r for r in res["series_switch"] if r["passes"]]
    if ok:
        ch = min(ok, key=lambda r: r["settle_us"]); res["closed"] = True; res["chosen"] = dict(ch, lever="clamp rails +-12 V around VBIAS + series isolation switch (clamp node -> Rin2), closed at t_close")
        res["margin_us"] = round(gate - ch["settle_us"], 2)
        res["chosen_at_boost_12A74"] = [transient_series(100.0, ch["rails"][0], ch["rails"][1], tc, i_coil=12.74) for tc in (14.5, 15.5)]
        res["new_parts"] = ["analog switch rated for +-15 V signals, Ron <= ~5 ohm, low charge injection (part to choose; Ron 2 ohm and 2 pC ASSUMED)", "+-12 V clamp rails in the head (charge pump / LDO from +5 V, low impedance; part to choose)"]
        res["open"] = "parts for the switch and the +-12 V rails; the switch timing from CB1D (close 11.5 us after turn-off in scan, later in boost)"
    json.dump(res, open(os.path.join(OUT, "rf2_mp1v2_close.json"), "w"), indent=1); print("closed:", res["closed"], res.get("chosen"), res.get("chosen_at_boost_12A74"))
    return res

# ---- lever 3 (2026-10-30): INPUT BLANKING. The SPICE runs show the amplifier chain needs 3.2-3.9 us after the coil is quiet (rf2_timing assumes 2 us):
# the LMH6629 is driven into saturation through the whole flyback. A low-resistance analog switch from each amplifier input pin (ahead of the current
# sense) to VBIAS holds the input at bias while the coil flies back, and releases at t_rel (timed by CB1D, which already times the gates). The clamp
# current then flows into the switch, not the amplifier. Switch: Ron 2 ohm, Roff 1 Gohm (ASSUMED until a part is chosen); release charge injection
# 2.0 / 1.8 pC on legs A / B (ASSUMED; 10 % mismatch, the difference stage rejects the matched part).
def blank_variant(net, t_rel_us, ron, cinj):
    add = (f"Vbl blc 0 PWL(0 1 {t_rel_us}u 1 {t_rel_us + 0.02}u 0)\n.model SWBL SW(vt=0.5 vh=0.05 ron={ron} roff=1e9)\n"
           f"SblA pinA vb blc 0 SWBL\nSblB pinB vb blc 0 SWBL\nCinjA blc pinA {cinj[0]}p\nCinjB blc pinB {cinj[1]}p\n")
    return add + net
@memo("spice.mp1v2.close.blank", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES + [blank_variant], tools=["ngspice"])
def transient_blank(rin2, lo, hi, t_rel_us, ron=2.0, cinj=(2.0, 1.8), i_coil=8.06):
    src = C.SRC_TR.replace("Vdr nd vb DC -4.27", f"Vdr nd vb DC {-i_coil * 0.53:.4f}")
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)", "i(VsuA0)", "i(VsuA1)", "v(out)"]
    net = blank_variant(variant(PR.netlist(FET, PR.CLAMPS[CLAMP], src), rin2, lo, hi), t_rel_us, ron, cinj)
    A, _ = C.ng(net + ".save " + " ".join(vec) + "\n.options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n", "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}; d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    vo = col["v(out)"]; rest_o = float(vo[-1]); bad_o = np.where(np.abs(vo - rest_o) > 24e-3)[0]
    return dict(t_rel_us=t_rel_us, peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2),
                settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None,
                settle_out_us=round(float(t[bad_o[-1] + 1]) * 1e6, 2) if len(bad_o) and bad_o[-1] + 1 < len(t) else None,
                peak_per_diode_mA=dict(BAV199=round(float(np.abs(col["i(VsuA0)"]).max()) * 1e3 / 2, 1), BAT54=round(float(np.abs(col["i(VsuA1)"]).max()) * 1e3 / 2, 1)))
# ---- lever 4 (2026-10-30): SERIES ISOLATION SWITCH. Diagnosis (rf2_mp1v2_close diagnostics, HANDOFF section 40): the slow settling is the COIL tail, not the
# amplifier: the input path (limiter channel + Rsrc + Rin2 into the saturated amplifier's input diodes, or a shunt blanking switch) loads the coil node in its
# tail and overdamps it (front end disconnected: coil 1 mV at 11.5 us; with it: 18.3 us). A series switch between the clamp node and Rin2, OPEN through the
# flyback and closed at t_close, leaves the limiter output floating in the tail (no load on the coil) and keeps the amplifier out of saturation; the clamps
# stay on the limiter side and catch the flyback charge. Switch Ron 2 ohm, Roff 1 Gohm, release injection 2.0 / 1.8 pC (ASSUMED until a part is chosen).
def series_variant(net, t_close_us, ron, cinj):
    net = re.sub(r"^Rin2([AB]) (cl[AB]) (pin[AB]) (\S+)$", lambda m: f"Sse{m.group(1)} {m.group(2)} mid{m.group(1)} sec 0 SWSE\nRin2{m.group(1)} mid{m.group(1)} {m.group(3)} {m.group(4)}", net, flags=re.M)
    add = (f"Vsec sec 0 PWL(0 0 {t_close_us}u 0 {t_close_us + 0.02}u 1)\n.model SWSE SW(vt=0.5 vh=0.05 ron={ron} roff=1e9)\n"
           f"CsiA sec midA {cinj[0]}p\nCsiB sec midB {cinj[1]}p\n")
    return add + net
@memo("spice.mp1v2.close.series", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES + [series_variant], tools=["ngspice"])
def transient_series(rin2, lo, hi, t_close_us, ron=2.0, cinj=(2.0, 1.8), i_coil=8.06):
    src = C.SRC_TR.replace("Vdr nd vb DC -4.27", f"Vdr nd vb DC {-i_coil * 0.53:.4f}")
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)", "i(VsuA0)", "i(VsuA1)", "v(out)"]
    net = series_variant(variant(PR.netlist(FET, PR.CLAMPS[CLAMP], src), rin2, lo, hi), t_close_us, ron, cinj)
    A, _ = C.ng(net + ".save " + " ".join(vec) + "\n.options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n", "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}; d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    nc = col["v(nc)"]; bad_c = np.where(np.abs(nc - nc[-1]) > 1e-3)[0]
    return dict(t_close_us=t_close_us, peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2),
                settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None,
                coil_1mV_us=round(float(t[bad_c[-1] + 1]) * 1e6, 2) if len(bad_c) else 0.0,
                peak_per_diode_mA=dict(BAV199=round(float(np.abs(col["i(VsuA0)"]).max()) * 1e3 / 2, 1), BAT54=round(float(np.abs(col["i(VsuA1)"]).max()) * 1e3 / 2, 1)))

if __name__ == "__main__":
    main_all()
