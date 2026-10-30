#!/usr/bin/env python3
"""RF2 MP1 v2 front-end chain (2026-10-30): the whole signal path in ngspice with the TI LMH6629 and OPAx211 macro models (qualified against their datasheets by
rf2_opamp_qualify.py) and datasheet-anchored generic models for the IXTY08N100D2 limiter and the BAV199 clamp (no vendor SPICE model was reachable: Littelfuse and Nexperia
answered 403). MODELED. Topology (per coil leg X = A, B), as the MP1 v2 fin board:
  coil terminal -> IXTY08N100D2 (drain at the coil, source through Rsrc 22 ohm to the gate: a depletion current limiter) -> clamp node (BAV199: AGND / +5VA)
  -> Rin2 -> LMH6629 +IN (non-inverting, gain 10, COMP high: minimum stable gain 10; Rf from OUT, Rg to VBIAS); a 10 kohm bias resistor on +IN to VBIAS
  -> difference stage OPAx211 (1 kohm in, 2.4 kohm feedback / reference to VBIAS: gain 2.4) -> 100 ohm -> MONO_OUT.   Overall gain 24, as v1.
Convention: noise is the output noise divided by the gain with the coil terminals shorted (the preamp's own noise, both legs counted), quoted per sqrt(2) legs =
'per leg equivalent' as well, since the v1 figure (4.83 nV/rtHz from 1410 ohm) and the depth model's 1.7 nV are per leg.
Studied: Rin2 and the stage-1 feedback pair against noise, recovery after the 460 V turn-off (coil 333 uH, 8.06 A, 408 ohm / 500 pF damping, rf2_timing), and the peak current
into the LMH6629 input against its +-10 mA limit (TI SNOSB18I). Writes out/rf2_mp1v2_chain.json.   usage: python3 rf2/head/rf2_mp1v2_chain.py"""
import os, sys, json, math, subprocess, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
LMH = os.path.join(ROOT, "data/spice/LMH6629/LMH6629_TINA-TI_snom339.lib")
# The difference stage is a BEHAVIORAL OPA211 (TI OPA211 datasheet SBOS377L: GBW 80 MHz, en 1.1 nV/rtHz, rail-to-rail within 0.2 V assumed), not TI's macro model: the TI OPAx211 file
# (data/spice/OPAx211) converts to ngspice (spice_compat.py) but then shows a constant +2.85 V output offset, so it is not used until that is understood. The stage sits after the
# gain-10 stage, so its noise enters the input divided by 10. It has no anti-windup, so the overload RECOVERY is measured at the LMH6629 stage outputs (the subject of the study),
# not at this stand-in stage's output (a first version measured at the output and showed a 30 us 'recovery' that was this stage's own windup).
OPA = os.path.join(OUT, "bopa211.lib")
open(OPA, "w").write(""".SUBCKT OPAx211 INP INM VCC VEE OUT
Ren INP ip 73
Ed d 0 ip INM 1e5
Rp d p 1k
Cp p 0 199n
Bo OUT 0 v = max(v(VEE) + 0.2, min(v(VCC) - 0.2, v(p)))
.ENDS
""")
sys.path.insert(0, os.path.join(ROOT, "src")); from simcache import memo
KT4 = 4 * 1.380649e-23 * 300.15
# Depletion limiter candidates, datasheet-anchored level-1 models. VTO = middle of the VGS(off) range, ID0 = the minimum ID(on) at VGS 0 (VDS 25 V), RDS = the MAXIMUM RDS(on) (conservative
# for noise), Cds / Cgd = Coss / Crss at VDS 25 V held constant (pessimistic: the datasheet curves fall with VDS). Sources: IXYS DS100182C (08N100D2), DS98809F (01N100D),
# DS98861C (02N50D), DS100178E (08N50D2): the files in data/datasheets. BV is the BVDSX minimum; rule 6 asks 630 V parts on the coil flyback nets.
FETS = {
    "IXTY08N100D2": dict(VTO=-3.0, ID0=0.8, RDS=21.0, CDS=24e-12, CGD=6.5e-12, BV=1000),
    "IXTY01N100D": dict(VTO=-3.25, ID0=0.4, RDS=80.0, CDS=12e-12, CGD=2.0e-12, BV=1000),
    "IXTY02N50D": dict(VTO=-3.75, ID0=0.25, RDS=30.0, CDS=25e-12, CGD=5.0e-12, BV=500),
    "IXTY08N50D2": dict(VTO=-3.5, ID0=0.8, RDS=4.6, CDS=35e-12, CGD=11e-12, BV=500),
}
FET = FETS["IXTY08N100D2"]
def fet_card(tag, nd, g, s, fet="IXTY08N100D2"):
    F = FETS[fet]; KP = 2 * F["ID0"] / F["VTO"] ** 2; r_ch = 1.0 / (KP * abs(F["VTO"])); RD = max(0.0, F["RDS"] - r_ch)
    return (f"RDd{tag} {nd} dd{tag} {RD:.3f}\nM{tag} dd{tag} {g} {s} {s} NDEP L=1u W=1u\nCgd{tag} dd{tag} {g} {F['CGD']:.3e}\nCds{tag} dd{tag} {s} {F['CDS']:.3e}\n")
def model_text(fet="IXTY08N100D2", rs_clamp=2.0):
    """NDEP for the limiter and DPROT for the BAV199 clamp diodes: IS 3 pA, CJO 2 pF (Infineon CT 2 pF at 0 V); RS 2 ohm is about the typical forward drop, RS 4 ohm makes VF = 1.25 V at 150 mA,
    the Infineon maximum (IF = 150 mA: VF <= 1250 mV)"""
    F = FETS[fet]; return (".model NDEP NMOS(LEVEL=1 VTO=%.2f KP=%.5f LAMBDA=0.002 CGSO=0 CGDO=0)\n.model DPROT D(IS=3e-12 N=1.0 RS=%g CJO=2p)\n" % (F["VTO"], 2 * F["ID0"] / F["VTO"] ** 2, rs_clamp))
MODEL = model_text()
def leg(X, nc, rin2, rf, rg, rsrc=22.0, rbias=10e3, clamp2=True, fet="IXTY08N100D2"):
    return (fet_card(X, nc, f"g{X}", f"s{X}", fet) + f"Rsrc{X} s{X} g{X} {rsrc}\nRser{X} g{X} cl{X} 0.001\n"
            f"D{X}a 0 cl{X} DPROT\nD{X}b cl{X} vp DPROT\nCcl{X} cl{X} 0 3p\nRin2{X} cl{X} pin{X} {rin2}\n" + (f"D{X}c 0 pin{X} DPROT\nD{X}d pin{X} vp DPROT\n" if clamp2 else "") + f"Vm{X} pin{X} in{X} DC 0\nRb{X} in{X} vb 10k\n"
            f"Xl{X} in{X} fb{X} vp 0 o1{X} cmp LMH6629\nRf{X} o1{X} fb{X} {rf}\nRg{X} fb{X} vb {rg}\nRl{X} o1{X} vb 1k\n")
def netlist(rin2, rf, rg, source, rbias=10e3, clamp2=True, rsrc=22.0, fet="IXTY08N100D2", rs_clamp=2.0):
    s = f".include {LMH}\n.include {OPA}\n{model_text(fet, rs_clamp)}Vp vp 0 DC 5\nVb vb 0 DC 2.5\nVcmp cmp 0 DC 5\n"
    s += leg("A", "nca", rin2, rf, rg, rsrc=rsrc, clamp2=clamp2, fet=fet) + leg("B", "ncb", rin2, rf, rg, rsrc=rsrc, clamp2=clamp2, fet=fet)
    s += "R1 o1A m1 1k\nR2 m1 vb 2.4k\nR3 o1B m2 1k\nR4 m2 o2 2.4k\nXo m1 m2 vp 0 o2 OPAx211\nR10 o2 out 100\nRL out vb 10k\n"
    return s + source
SRC_AC = "Vsrc nca ncb AC 1\nVref ncb vb DC 0\n"
SRC_TR = ("* the coil carries 8.06 A (DC source + switch, so the DC operating point already holds it) and the switch opens at t = 0 into the damping and the 460 V clamp;\n"
          "* the coil, damping and clamp are referenced to VBIAS (the coil floats; the bias resistors set its DC level)\n"
          "Vdr nd vb DC -4.27\nRcoil nd sw 0.53\nS1 sw nc ctl vb SWM\nVctl ctl vb PULSE(1 0 0 1n 1n 1 1)\n.model SWM SW(vt=0.5 vh=0.1 ron=1m roff=1e12)\n"
          "L1 vb nc 333u\nRd nc vb 408\nCn nc vb 500p\nDcl nc ncl DCLAMP\nVcl ncl vb DC 460\n.model DCLAMP D(IS=1e-12 N=1.0 RS=0.05)\nVs1 nc nca DC 0\nVref ncb vb DC 0\n")
def ng(net, ctrl, timeout=900):
    d = tempfile.mkdtemp(); f = os.path.join(d, "c.cir"); o = os.path.join(d, "o.txt")
    open(f, "w").write("* mp1 v2 chain\n" + net + "\n.control\n" + ctrl.replace("{OUT}", o) + "\n.endc\n.end\n")
    r = subprocess.run(["ngspice", "-b", f], capture_output=True, text=True, errors="replace", timeout=timeout)
    if not os.path.exists(o): raise SystemExit("ngspice failed:\n" + (r.stdout + r.stderr)[-2000:])
    return np.loadtxt(o), r.stdout
@memo("spice.mp1v2.ac_noise", files=lambda *a, **k: [LMH, OPA], uses=[ng, netlist, leg, fet_card, model_text, MODEL, SRC_AC, SRC_TR, FETS], tools=["ngspice"])
def ac_noise(rin2, rf, rg, rsrc=22.0, clamp2=False, fet="IXTY08N100D2", rs_clamp=2.0):
    A, _ = ng(netlist(rin2, rf, rg, SRC_AC, clamp2=clamp2, rsrc=rsrc, fet=fet, rs_clamp=rs_clamp) + ".ac dec 20 1e3 1e8\n", "run\nwrdata {OUT} vdb(out)"); f, db = A[:, 0], A[:, 1]
    g0 = float(db[np.argmin(abs(f - 1e5))]); bw = float(f[np.where(db < g0 - 3)[0][0]]) if np.any(db < g0 - 3) else float("nan")
    N, _ = ng(netlist(rin2, rf, rg, SRC_AC, clamp2=clamp2, rsrc=rsrc, fet=fet, rs_clamp=rs_clamp) + ".noise v(out) Vsrc dec 20 1e3 1e7\n", "run\nsetplot noise1\nwrdata {OUT} inoise_spectrum"); nf, nv = N[:, 0], N[:, 1]
    at = lambda x: float(np.interp(math.log10(x), np.log10(nf), nv)) * 1e9
    band = (nf >= 1e4) & (nf <= 1e6); rms = math.sqrt(np.trapezoid(nv[band] ** 2, nf[band]))
    return dict(gain_dB=round(g0, 2), gain=round(10 ** (g0 / 20), 2), bw_3dB_MHz=round(bw / 1e6, 2), noise_diff_nV_100kHz=round(at(1e5), 3), noise_diff_nV_1MHz=round(at(1e6), 3),
                noise_per_leg_equiv_nV_100kHz=round(at(1e5) / math.sqrt(2), 3), rms_10k_1M_uV=round(rms * 1e6, 3))
@memo("spice.mp1v2.transient", files=lambda *a, **k: [LMH, OPA], uses=[ng, netlist, leg, fet_card, model_text, MODEL, SRC_AC, SRC_TR, FETS], tools=["ngspice"])
def transient(rin2, rf, rg, tstop=120e-6, clamp2=False, rsrc=22.0, fet="IXTY08N100D2", rs_clamp=2.0):
    net = netlist(rin2, rf, rg, SRC_TR, clamp2=clamp2, rsrc=rsrc, fet=fet, rs_clamp=rs_clamp) + f".options reltol=1e-4 abstol=1e-12 vntol=1e-7 method=gear\n.tran 2n {tstop} 0 2n\n"
    A, so = ng(net, "run\nwrdata {OUT} v(out) v(clA) i(VmA) v(nc) i(Vcl) v(inA) v(o1A) v(o1B)", timeout=3000)
    t, vo, vcl, imA, vnc, icl, vin, o1a, o1b = A[:, 0], A[:, 1], A[:, 3], A[:, 5], A[:, 7], A[:, 9], A[:, 11], A[:, 13], A[:, 15]
    # stage 1 has gain 10: 10 mV = 1 mV at the coil terminals
    d1 = o1a - o1b; rest = float(d1[-1]); bad = np.where(np.abs(d1 - rest) > 10e-3)[0]; t_rec = float(t[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(t) else float("nan")
    return dict(peak_coil_V=round(float(vnc.max()), 1), peak_clamp_node_V=round(float(vcl.max()), 2), min_clamp_node_V=round(float(vcl.min()), 2), peak_lmh_input_mA=round(float(np.abs(imA).max()) * 1e3, 2),
                stage1_diff_rest_V=round(rest, 3), recovery_to_1mV_input_referred_us=round(t_rec * 1e6, 2), recovery_measured_at="LMH6629 stage outputs (differential / 10)", peak_out_V=round(float(vo.max()), 2), min_out_V=round(float(vo.min()), 2))
@memo("spice.mp1v2.v1_noise", files=lambda *a, **k: [LMH, OPA], uses=[ng, netlist, leg, fet_card, model_text, MODEL, SRC_AC, SRC_TR, FETS], tools=["ngspice"])
def v1_noise():
    """the v1 chain for the same convention: 3 x 470 ohm per leg into BAV199 clamps, OPA2211 difference amplifier (1 kohm / 24 kohm bias, gain 24), source shorted"""
    net = (f".include {OPA}\n{MODEL}Vp vp 0 DC 5\nVb vb 0 DC 2.5\nVsrc nca ncb AC 1\nVref ncb vb DC 0\n"
           "RA1 nca a1 1410\nRB1 ncb b1 1410\nR4 a1 pa 1k\nR6 b1 pb 1k\nR5 pa vb 24k\nR7 pb o 24k\nXo pa pb vp 0 o OPAx211\nR10 o out 100\nRL out vb 10k\n")
    # the v1 amplifier is one OPA2211 half: +IN biased by R5 (24 k) to VBIAS, -IN with 24 k feedback; the +/- legs are the two coil terminals
    net = (f".include {OPA}\n{MODEL}Vp vp 0 DC 5\nVb vb 0 DC 2.5\nVsrc nca ncb AC 1\nVref ncb vb DC 0\nRA1 nca a1 1410\nRB1 ncb b1 1410\nR4 a1 pp 1k\nR6 b1 pm 1k\n"
           "R5 pp vb 24k\nR7 pm o 24k\nXo pp pm vp 0 o OPAx211\nR10 o out 100\nRL out vb 10k\n")
    N, _ = ng(net + ".noise v(out) Vsrc dec 20 1e3 1e7\n", "run\nsetplot noise1\nwrdata {OUT} inoise_spectrum"); nf, nv = N[:, 0], N[:, 1]
    A, _ = ng(net + ".ac dec 20 1e3 1e8\n", "run\nwrdata {OUT} vdb(out)"); g0 = float(A[np.argmin(abs(A[:, 0] - 1e5)), 1])
    return dict(gain_dB=round(g0, 2), noise_diff_nV_100kHz=round(float(np.interp(5.0, np.log10(nf), nv)) * 1e9, 3))
def main():
    res = dict(status="MODELED: TI macro models (datasheet-qualified); FET and clamp are datasheet-anchored generics; not a measurement", convention="noise = output noise / gain with the coil terminals shorted; "
               "'per leg equivalent' divides the differential figure by sqrt(2)", options=[])
    for rin2 in (47.0, 68.0, 100.0):
        for rf, rg in ((240.0, 26.7), (90.0, 10.0)):
            r = ac_noise(rin2, rf, rg); r.update(Rin2_ohm=rin2, Rf_ohm=rf, Rg_ohm=rg); res["options"].append(r); print(r, flush=True)
    res["v1_reference"] = v1_noise(); print("v1", res["v1_reference"], flush=True)
    res["chosen"] = dict(Rin2_ohm=100.0, Rf_ohm=240.0, Rg_ohm=26.7, reason="Rin2 100 ohm with a second BAV199 clamp pair on the LMH6629 input keeps the amplifier input current inside its +-10 mA rating (transient options below); Rf 240 / Rg 26.7 keeps the load on each stage-1 output at 267 ohm")
    res["transient_options"] = []
    for rin2, c2 in ((100.0, False), (100.0, True), (68.0, True)):
        t_ = transient(rin2, 240.0, 26.7, clamp2=c2); t_.update(Rin2_ohm=rin2, second_clamp_at_amp_input=c2); res["transient_options"].append(t_); print("transient", t_, flush=True)
    tr = next(t for t in res["transient_options"] if t["Rin2_ohm"] == 100.0 and t["second_clamp_at_amp_input"]); res["transient_chosen"] = tr
    ch = next(o for o in res["options"] if o["Rin2_ohm"] == 100.0 and o["Rf_ohm"] == 240.0)
    res["limiter_candidates"] = []
    for fet, rs in (("IXTY08N100D2", 2.0), ("IXTY01N100D", 2.0), ("IXTY02N50D", 2.0), ("IXTY08N50D2", 2.0), ("IXTY08N100D2", 4.0), ("IXTY01N100D", 4.0)):
        n_ = ac_noise(100.0, 240.0, 26.7, fet=fet, rs_clamp=rs); t_ = transient(100.0, 240.0, 26.7, fet=fet, rs_clamp=rs)
        row = dict(fet=fet, BV_V=FETS[fet]["BV"], rule6_630V_ok=FETS[fet]["BV"] >= 630, RDS_max_ohm=FETS[fet]["RDS"], Coss_pF=FETS[fet]["CDS"] * 1e12, Crss_pF=FETS[fet]["CGD"] * 1e12, clamp_RS_ohm=rs,
                   noise_per_leg_nV=n_["noise_per_leg_equiv_nV_100kHz"], peak_clamp_node_V=t_["peak_clamp_node_V"], peak_lmh_input_mA=t_["peak_lmh_input_mA"], settle_us=t_["recovery_to_1mV_input_referred_us"])
        res["limiter_candidates"].append(row); print("candidate", row, flush=True)
    import rf2_opamp_qualify as Q
    res["checks"] = dict(lmh6629_model_qualified=Q.model_qualified(LMH), gain_is_24=abs(ch["gain"] - 24.0) < 1.5, bandwidth_over_10MHz=ch["bw_3dB_MHz"] > 10.0,
                         noise_better_than_v1=ch["noise_per_leg_equiv_nV_100kHz"] < res["v1_reference"]["noise_diff_nV_100kHz"] / math.sqrt(2),
                         lmh_input_current_inside_10mA=tr["peak_lmh_input_mA"] < 10.0, recovers_inside_first_gate=tr["recovery_to_1mV_input_referred_us"] < 16.3,
                         clamp_node_inside_rails_plus_diode=tr["peak_clamp_node_V"] < 5.0 + 1.0 and tr["min_clamp_node_V"] > -1.0)
    res["ok"] = all(res["checks"].values())
    res["open_findings"] = [k for k, v in res["checks"].items() if not v]
    res["verdict"] = ("MP1 v2 as chosen (IXTY08N100D2, Rsrc 22, Rin2 100, LMH6629 gain 10) is NOT yet a closed design: " + ", ".join(res["open_findings"])) if res["open_findings"] else "all checks pass"
    json.dump(res, open(os.path.join(OUT, "rf2_mp1v2_chain.json"), "w"), indent=1); print(json.dumps(res["checks"], indent=1)); return res
if __name__ == "__main__":
    r = main(); print(r["verdict"]); sys.exit(0)                     # the study ran; the verdict (open findings) is in the JSON and the runner reports it
