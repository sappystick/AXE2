#!/usr/bin/env python3
"""RF2 MP1 v2 input protection options (2026-10-30), on the chain of rf2_mp1v2_chain.py (TI LMH6629 macro model, behavioral OPA211 second stage, both coil legs, the coil released
at 8.06 A into the 460 V clamp). MODELED. Three questions, in the owner's order:
  1. CLAMP: one BAV199, two BAV199 in parallel, a BAV199 plus a BAT54S Schottky pair, two BAT54S. Diodes are fitted to their datasheet forward-voltage tables:
       BAV199 max  (Nexperia v.3 / Infineon 2007, identical maxima 0.9 / 1.0 / 1.1 / 1.25 V at 1 / 10 / 50 / 150 mA): IS 5.67e-14, N 1.474, RS 1.06 ohm, CJO 2 pF
       BAT54 max   (Diodes DS11005 rev 34-2: 0.24 / 0.32 / 0.40 / 0.50 / 0.80 V at 0.1 / 1 / 10 / 30 / 100 mA): IS 7.21e-9, N 0.996, RS 3.75 ohm
       BAT54 typ   (onsemi BAT54LT1/D rev 18: 0.22 / 0.29 / 0.35 / 0.41 / 0.52 V): IS 2.22e-8, N 1.021, RS 1.15 ohm
       BAT54 CJO from CT 10 pF max / 7.6 pF typ at 1 V (VJ 0.35, M 0.5 ASSUMED). Both tables stop at 100-150 mA: at the 0.4 A spike every fit is an EXTRAPOLATION.
  2. CASCODE: two IXTY08N50D2 (500 V each, RDS(on) <= 4.6 ohm) in series; the upper gate on a 10 Mohm / 10 Mohm divider from the coil to AGND with 47 pF / 47 pF across it, so each
     device holds about half the flyback. Cgs = Ciss - Crss (301 pF) is added on both devices (the level-1 model has none). The per-device peak VDS is reported (balance check).
  3. Coss(V): the datasheet capacitance curves (read off the graphs by eye, about +-15 %, curves end at 40 V) are integrated to the device's peak VDS, with a power law fitted on
     20-40 V beyond 40 V (an EXTRAPOLATION). The charge-equivalent capacitance C_Q = Q(V) / V replaces the 25 V value, which overstates the charge at 460 V.
Per option: noise (per leg equivalent, coil shorted), clamp-node peak, LMH6629 input peak (rating 10 mA, TI SNOSB18I), settling of the stage-1 outputs to 1 mV at the coil (first
gate 16.3 us), and the peak current per clamp diode against its rating (BAV199 IFRM 500 mA Nexperia; BAT54 IFRM 300 mA Diodes). Writes out/rf2_mp1v2_protect.json.
usage: python3 rf2/head/rf2_mp1v2_protect.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..")); sys.path[:0] = [HERE, os.path.join(ROOT, "src")]
import rf2_mp1v2_chain as C
from simcache import memo
OUT = C.OUT
DIODES = {"BAV199_MAX": "IS=5.672e-14 N=1.474 RS=1.059 CJO=2p", "BAT54_MAX": "IS=7.208e-9 N=0.996 RS=3.748 CJO=19.6p VJ=0.35 M=0.5",
          "BAT54_TYP": "IS=2.218e-8 N=1.021 RS=1.154 CJO=14.9p VJ=0.35 M=0.5", "BAV199_GEN": "IS=3e-12 N=1.0 RS=2 CJO=2p"}
RATING_MA = {"BAV199_MAX": 500.0, "BAV199_GEN": 500.0, "BAT54_MAX": 300.0, "BAT54_TYP": 300.0}      # repetitive peak forward current per diode
# capacitance curves read off the datasheet graphs (V, pF); beyond 40 V a power law fitted on the 20-40 V points
CURVES = {
    "IXTY08N100D2": dict(coss=[(0, 700), (1, 450), (2, 300), (5, 250), (6, 200), (7, 80), (8, 50), (10, 40), (15, 33), (20, 28), (25, 24), (30, 22), (40, 19)],
                         crss=[(0, 330), (3, 250), (5, 230), (6, 120), (7, 25), (8, 15), (10, 12), (15, 9), (20, 7.5), (25, 6.5), (40, 5.3)]),
    "IXTY01N100D": dict(coss=[(0, 180), (2, 140), (5, 120), (6, 90), (8, 40), (10, 25), (12, 19), (15, 15), (20, 13.5), (25, 12), (30, 11.5), (40, 10)],
                        crss=[(0, 110), (5, 80), (7, 30), (8, 10), (10, 5), (12, 3.5), (15, 2.8), (20, 2.4), (25, 2.1), (40, 1.8)]),
    "IXTY08N50D2": dict(coss=[(0, 800), (5, 200), (10, 120), (15, 100), (18, 50), (20, 40), (25, 37), (30, 33), (35, 30), (40, 28)],
                        crss=[(0, 300), (5, 150), (10, 100), (15, 70), (17, 20), (20, 12), (25, 11), (30, 10), (40, 8.5)]),
}
def charge_equiv_pF(points, v):
    """C_Q = Q(v) / v from the curve: trapezoids to 40 V, then C(V) = C40 (V / 40)^-k with k fitted on 20-40 V"""
    P = np.array(points, float); V, Cp = P[:, 0], P[:, 1]; vv = min(v, V[-1]); m = V <= vv
    q = float(np.trapezoid(np.append(Cp[m], np.interp(vv, V, Cp)), np.append(V[m], vv)))
    if v > V[-1]:
        c20 = float(np.interp(20.0, V, Cp)); c40 = Cp[-1]; k = math.log(c20 / c40) / math.log(2.0)
        q += c40 * 40.0 ** k / (1 - k) * (v ** (1 - k) - 40.0 ** (1 - k))
    return q / v
def fets():
    F = dict(C.FETS)
    for name, vds in (("IXTY08N100D2", 455.0), ("IXTY01N100D", 455.0)):
        F[name + "@Q"] = dict(F[name], CDS=charge_equiv_pF(CURVES[name]["coss"], vds) * 1e-12, CGD=charge_equiv_pF(CURVES[name]["crss"], vds) * 1e-12)
    F["IXTY08N50D2@Q230"] = dict(F["IXTY08N50D2"], CDS=charge_equiv_pF(CURVES["IXTY08N50D2"]["coss"], 230.0) * 1e-12, CGD=charge_equiv_pF(CURVES["IXTY08N50D2"]["crss"], 230.0) * 1e-12, CGS=301e-12)
    return F
FX = fets()
def fet_lines(tag, nd, g, s, fet):
    f = FX[fet]; KP = 2 * f["ID0"] / f["VTO"] ** 2; r_ch = 1.0 / (KP * abs(f["VTO"])); RD = max(0.0, f["RDS"] - r_ch); mn = "N" + tag
    out = (f".model {mn} NMOS(LEVEL=1 VTO={f['VTO']:.2f} KP={KP:.5f} LAMBDA=0.002 CGSO=0 CGDO=0)\nRDd{tag} {nd} dd{tag} {RD:.3f}\nM{tag} dd{tag} {g} {s} {s} {mn} L=1u W=1u\n"
           f"Cgd{tag} dd{tag} {g} {f['CGD']:.3e}\nCds{tag} dd{tag} {s} {f['CDS']:.3e}\n")
    return out + (f"Cgs{tag} {g} {s} {f['CGS']:.3e}\n" if f.get("CGS") else "")
def leg(X, nc, fet, clamp, rin2=100.0, rf=240.0, rg=26.7, rsrc=22.0):
    s = ""
    if fet.startswith("CASCODE:"):                              # upper device: drain at the coil, source at the middle node; gate on the divider from the coil to AGND
        dev = fet.split(":", 1)[1]
        s += fet_lines(X + "u", nc, f"g2{X}", f"nm{X}", dev) + f"Rdv1{X} {nc} g2{X} 10Meg\nRdv2{X} g2{X} 0 10Meg\nCdv1{X} {nc} g2{X} 47p\nCdv2{X} g2{X} 0 47p\n"
        s += fet_lines(X + "l", f"nm{X}", f"g{X}", f"s{X}", dev)
    else: s += fet_lines(X, nc, f"g{X}", f"s{X}", fet)
    s += f"Rsrc{X} s{X} g{X} {rsrc}\nRser{X} g{X} cl{X} 0.001\nCcl{X} cl{X} 0 3p\n"
    for k, (model, n) in enumerate(clamp):                       # each diode type: n devices, a 0 V sense source in the upward (to +5VA) group of leg A
        for j in range(n):
            s += f"Dd{X}{k}{j} 0 cl{X} {model}\nDu{X}{k}{j} cl{X} su{X}{k} {model}\n"
        s += f"Vsu{X}{k} su{X}{k} vp DC 0\n"
    s += (f"Rin2{X} cl{X} pin{X} {rin2}\nVm{X} pin{X} in{X} DC 0\nRb{X} in{X} vb 10k\nXl{X} in{X} fb{X} vp 0 o1{X} cmp LMH6629\nRf{X} o1{X} fb{X} {rf}\nRg{X} fb{X} vb {rg}\nRl{X} o1{X} vb 1k\n")
    return s
def netlist(fet, clamp, source):
    models = "".join(f".model {m} D({DIODES[m]})\n" for m in sorted({m for m, _ in clamp}))
    s = f".include {C.LMH}\n.include {C.OPA}\n{models}Vp vp 0 DC 5\nVb vb 0 DC 2.5\nVcmp cmp 0 DC 5\n" + leg("A", "nca", fet, clamp) + leg("B", "ncb", fet, clamp)
    return s + "R1 o1A m1 1k\nR2 m1 vb 2.4k\nR3 o1B m2 1k\nR4 m2 o2 2.4k\nXo m1 m2 vp 0 o2 OPAx211\nR10 o2 out 100\nRL out vb 10k\n" + source
USES = [leg, netlist, fet_lines, DIODES, CURVES, charge_equiv_pF, C.ng, C.SRC_AC, C.SRC_TR, C.FETS]
@memo("spice.protect.noise", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES, tools=["ngspice"])
def noise(fet, clamp):
    N, _ = C.ng(netlist(fet, clamp, C.SRC_AC) + ".noise v(out) Vsrc dec 10 1e4 1e7\n", "run\nsetplot noise1\nwrdata {OUT} inoise_spectrum")
    return round(float(np.interp(5.0, np.log10(N[:, 0]), N[:, 1])) * 1e9 / math.sqrt(2), 3)
@memo("spice.protect.transient", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES, tools=["ngspice"])
def transient(fet, clamp):
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)"] + [f"i(VsuA{k})" for k in range(len(clamp))] + (["v(nmA)", "v(sA)"] if fet.startswith("CASCODE:") else [])
    save = ".save " + " ".join(v.replace("i(", "i(").replace("v(", "v(") for v in vec) + "\n"       # store only what is measured (the full node set took > 1.5 GB and > 10 min per run)
    A, _ = C.ng(netlist(fet, clamp, C.SRC_TR) + save + ".options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n", "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}
    d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    r = dict(peak_coil_V=round(float(col["v(nc)"].max()), 1), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2), peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2),
             settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None,
             peak_per_diode_mA={f"{m} x{n}": round(float(np.abs(col[f'i(VsuA{k})']).max()) * 1e3 / n, 1) for k, (m, n) in enumerate(clamp)})
    if fet.startswith("CASCODE:"):
        r["peak_vds_upper_V"] = round(float((col["v(nc)"] - col["v(nmA)"]).max()), 1); r["peak_vds_lower_V"] = round(float((col["v(nmA)"] - col["v(sA)"]).max()), 1)
    return r
CLAMPS = {"1 x BAV199 (generic, as the chain study)": [("BAV199_GEN", 1)], "1 x BAV199": [("BAV199_MAX", 1)], "2 x BAV199": [("BAV199_MAX", 2)], "BAV199 + BAT54S (max)": [("BAV199_MAX", 1), ("BAT54_MAX", 1)],
          "BAV199 + BAT54S (typ)": [("BAV199_MAX", 1), ("BAT54_TYP", 1)], "2 x BAT54S (max)": [("BAT54_MAX", 2)], "2 x BAV199 + 2 x BAT54S (typ)": [("BAV199_MAX", 2), ("BAT54_TYP", 2)]}
RUNS = [("0. accuracy check against the chain study (reltol 1e-4, all nodes saved)", "IXTY01N100D", "1 x BAV199 (generic, as the chain study)"), ("0. accuracy check against the chain study (reltol 1e-4, all nodes saved)", "IXTY08N100D2", "1 x BAV199 (generic, as the chain study)")] + [("1. clamp", "IXTY01N100D", c) for c in CLAMPS if "generic" not in c] + [("1. clamp", "IXTY08N100D2", "1 x BAV199"), ("1. clamp", "IXTY08N100D2", "2 x BAV199 + 2 x BAT54S (typ)"),
        ("3. Coss(V) charge-equivalent", "IXTY08N100D2@Q", "1 x BAV199"), ("3. Coss(V) charge-equivalent", "IXTY01N100D@Q", "1 x BAV199"),
        ("3. Coss(V) charge-equivalent", "IXTY01N100D@Q", "2 x BAV199 + 2 x BAT54S (typ)"),
        ("2. cascode", "CASCODE:IXTY08N50D2@Q230", "1 x BAV199"), ("2. cascode", "CASCODE:IXTY08N50D2@Q230", "2 x BAV199 + 2 x BAT54S (typ)")]
def main():
    res = dict(status="MODELED: TI LMH6629 macro model; limiters and diodes are datasheet-anchored generics; capacitance curves read by eye; diode fits extrapolated past their tables",
               charge_equivalent_pF={k: dict(Coss=round(v["CDS"] * 1e12, 2), Crss=round(v["CGD"] * 1e12, 2)) for k, v in FX.items() if "@" in k}, runs=[])
    print("charge-equivalent C:", res["charge_equivalent_pF"], flush=True)
    for q, fet, cl in RUNS:
        clamp = CLAMPS[cl]; r = dict(question=q, limiter=fet, clamp=cl, noise_per_leg_nV=noise(fet, clamp)); r.update(transient(fet, clamp))
        rat = {k: v <= RATING_MA[k.split(" x")[0]] for k, v in r["peak_per_diode_mA"].items()}; r["diodes_inside_IFRM"] = all(rat.values())
        r["passes"] = bool(r["peak_lmh_input_mA"] < 10.0 and (r["settle_us"] or 99) < 16.3 and r["diodes_inside_IFRM"] and (not fet.startswith("CASCODE") or max(r["peak_vds_upper_V"], r["peak_vds_lower_V"]) <= 400.0))
        res["runs"].append(r); print(json.dumps(r), flush=True)
    ref = {c["fet"]: c for c in json.load(open(os.path.join(OUT, "rf2_mp1v2_chain.json")))["limiter_candidates"] if c["clamp_RS_ohm"] == 2.0}
    acc = []
    for r in res["runs"]:
        if r["question"].startswith("0.") and r["limiter"] in ref:
            c = ref[r["limiter"]]; acc.append(dict(limiter=r["limiter"], lmh_mA=(r["peak_lmh_input_mA"], c["peak_lmh_input_mA"]), clamp_node_V=(r["peak_clamp_node_V"], c["peak_clamp_node_V"]),
                                                  settle_us=(r["settle_us"], c["settle_us"]), noise_nV=(r["noise_per_leg_nV"], c["noise_per_leg_nV"])))
    res["accuracy_check"] = dict(pairs_fast_vs_reference=acc, max_rel_diff=round(max(abs(a - b) / abs(b) for x in acc for a, b in (x["lmh_mA"], x["clamp_node_V"], x["settle_us"], x["noise_nV"])), 4) if acc else None)
    res["accuracy_check"]["ok"] = res["accuracy_check"]["max_rel_diff"] is not None and res["accuracy_check"]["max_rel_diff"] < 0.03
    res["any_option_passes"] = any(r["passes"] for r in res["runs"] if not r["question"].startswith("0."))
    json.dump(res, open(os.path.join(OUT, "rf2_mp1v2_protect.json"), "w"), indent=1); return res
# ---- boost current (owner 2026-10-30: the trigger may be held indefinitely): the same turn-off at the boost peak current. The DC drive of SRC_TR sets the coil current.
@memo("spice.protect.transient_at_current", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES, tools=["ngspice"])
def transient_at(fet, clamp, i_coil):
    src = C.SRC_TR.replace("Vdr nd vb DC -4.27", f"Vdr nd vb DC {-i_coil * 0.53:.4f}")
    assert src != C.SRC_TR or abs(i_coil - 8.06) < 0.01
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)"]
    A, _ = C.ng(netlist(fet, clamp, src) + ".save " + " ".join(vec) + "\n.options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n", "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}; d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    return dict(i_coil_A=i_coil, peak_coil_V=round(float(col["v(nc)"].max()), 1), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2), peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2),
                settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None)
def boost_check():
    rows = []
    for fet, cl in (("IXTY08N100D2", "1 x BAV199"), ("IXTY01N100D@Q", "2 x BAV199 + 2 x BAT54S (typ)")):
        for i in (8.06, 12.74): r = transient_at(fet, CLAMPS[cl], i); r.update(limiter=fet, clamp=cl); rows.append(r)
    return rows
# ---- clamp reverse recovery (2026-10-30, Nexperia BAV199 1 April 2023 sheet): the same turn-off with stored charge in the BAV199s (TT variants above); the BAT54S Schottkys
# store none (trr <= 5 ns). Question: does recovery of the clamp diodes push the settling past the 16.3 us first gate?
# TT from trr ~ TT ln(1 + IF/IR) with IF = IR = 10 mA (the datasheet test): TT = trr / ln 2 (ASSUMED conversion, charge-control model). The fits in DIODES have no stored charge.
# Nexperia BAV199 (1 April 2023 and v.3): trr 0.8 typ / 3 max us; Infineon 2007: 0.6 typ / 1.5 max us. TT is added to the BAV199 card only (BAT54 Schottky: trr <= 5 ns).
TT_US = {"none": 0.0, "Nexperia typ (trr 0.8 us)": 0.8 / math.log(2), "Infineon max (trr 1.5 us)": 1.5 / math.log(2), "Nexperia max (trr 3 us)": 3.0 / math.log(2)}
@memo("spice.protect.transient_recovery", files=lambda *a, **k: [C.LMH, C.OPA], uses=USES + [TT_US], tools=["ngspice"])
def transient_rec(fet, clamp, tt_us, i_coil=8.06):
    net = netlist(fet, clamp, C.SRC_TR.replace("Vdr nd vb DC -4.27", f"Vdr nd vb DC {-i_coil * 0.53:.4f}"))
    card = f".model BAV199_MAX D({DIODES['BAV199_MAX']})"; assert card in net
    net = net.replace(card, f".model BAV199_MAX D({DIODES['BAV199_MAX']} TT={tt_us:.4f}u)")
    vec = ["v(clA)", "i(VmA)", "v(o1A)", "v(o1B)", "v(nc)", "i(VsuA0)"]
    A, _ = C.ng(net + ".save " + " ".join(vec) + "\n.options reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear\n.tran 5n 120u 0 5n\n", "run\nwrdata {OUT} " + " ".join(vec), timeout=3000)
    t = A[:, 0]; col = {v: A[:, 2 * i + 1] for i, v in enumerate(vec)}; d1 = col["v(o1A)"] - col["v(o1B)"]; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]
    iu = col["i(VsuA0)"]; rev = iu[t > 12e-6]
    return dict(tt_us=round(tt_us, 3), peak_lmh_input_mA=round(float(np.abs(col["i(VmA)"]).max()) * 1e3, 2), peak_clamp_node_V=round(float(col["v(clA)"].max()), 2),
                settle_us=round(float(t[bad[-1] + 1]) * 1e6, 2) if len(bad) and bad[-1] + 1 < len(t) else None,
                peak_reverse_recovery_mA=round(float(max(0.0, -rev.min())) * 1e3, 3) if len(rev) else None)
def recovery_check():
    rows = []
    for fet, cl in (("IXTY08N100D2", "1 x BAV199"), ("IXTY01N100D@Q", "2 x BAV199 + 2 x BAT54S (typ)")):
        for name, tt in TT_US.items():
            r = transient_rec(fet, CLAMPS[cl], tt); r.update(limiter=fet, clamp=cl, recovery=name); rows.append(r); print(json.dumps(r), flush=True)
    return rows
def main_all():
    res = main(); res["boost_12A74"] = boost_check(); res["clamp_recovery"] = recovery_check()
    json.dump(res, open(os.path.join(OUT, "rf2_mp1v2_protect.json"), "w"), indent=1)
    for r in res["boost_12A74"] + res["clamp_recovery"]: print(json.dumps(r), flush=True)
    return res
if __name__ == "__main__":
    main_all(); sys.exit(0)
