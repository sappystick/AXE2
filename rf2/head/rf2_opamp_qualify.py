#!/usr/bin/env python3
"""RF2 op-amp macro-model qualification (2026-10-30), after TI AN-1516 "SPICE Universal Test Circuits" (owner-supplied PDF): a model is only used once it reproduces the
datasheet. Benches in ngspice for the TI LMH6629 model (data/spice/LMH6629/LMH6629_TINA-TI_snom339.lib, TI snom339, header "datasheet SNOSB18E"; the repo datasheet is
SNOSB18I, so each figure is compared with SNOSB18I's typical column, quoted below). MODELED: this shows the model matches the datasheet's typical values, not that a part does.
  gain / bandwidth (AV 10, COMP high), open-loop gain and phase (loop-break), voltage noise en, current noise in, slew rate and rise time (2 V step), overload recovery
  (VIN 1 Vpp), input bias current, offset, supply current, DC CMRR and PSRR.
5 V single supply, VCM 2.5 V, RL 100 ohm to 2.5 V, WSON-8 pins +IN 4, -IN 3, V+ 8, V- 5, OUT 7, COMP 6 (the model's pin order). Writes out/rf2_opamp_qualify.json.
usage: python3 rf2/head/rf2_opamp_qualify.py"""
import os, sys, json, math, subprocess, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LIB = os.path.join(ROOT, "data", "spice", "LMH6629", "LMH6629_TINA-TI_snom339.lib"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "src")); from simcache import memo
KT4 = 4 * 1.380649e-23 * 300.15
def ng(netlist, ctrl):
    d = tempfile.mkdtemp(); f = os.path.join(d, "c.cir"); o = os.path.join(d, "o.txt")
    open(f, "w").write(netlist.replace("{LIB}", LIB).replace("{OUT}", o) + "\n.control\n" + ctrl.replace("{OUT}", o) + "\n.endc\n.end\n")
    r = subprocess.run(["ngspice", "-b", f], capture_output=True, text=True, timeout=600)
    if not os.path.exists(o): raise SystemExit("ngspice failed:\n" + (r.stdout + r.stderr)[-1500:])
    return np.loadtxt(o), r.stdout
HEAD = ".include {LIB}\nVp vp 0 DC 5\nVcm vcm 0 DC 2.5\nVc comp 0 DC 5\n"                          # COMP high: minimum stable gain 10
def cross(x, y, level, rising=True):
    s = np.sign(y - level); i = np.where((s[:-1] <= 0) & (s[1:] > 0) if rising else (s[:-1] >= 0) & (s[1:] < 0))[0]
    if not len(i): return float("nan")
    i = i[0]; return float(x[i] + (level - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
@memo("spice.qualify.ac", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_ac():
    A, _ = ng(HEAD + "Vin in 0 DC 2.5 AC 1\nXu in fb vp 0 out comp LMH6629\nRf out fb 240\nRg fb vcm 26.7\nRl out vcm 100\n.ac dec 40 1e4 3e9\n", "run\nwrdata {OUT} vdb(out) vp(out)")
    f, db = A[:, 0], A[:, 1]; g0 = float(db[0]); bw = cross(f, db, g0 - 3.0, rising=False); pk = float(db.max() - g0)
    return dict(gain_dB=round(g0, 2), bw_3dB_MHz=round(bw / 1e6, 0), peaking_dB=round(pk, 2))
@memo("spice.qualify.aol", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_aol():
    # loop-break: a 1 GH inductor closes the loop at DC, a 1 GF capacitor injects the AC at the inverting input; AOL = -v(out) / v(fb)
    A, _ = ng(HEAD + "Xu vcm fb vp 0 out comp LMH6629\nL1 out fb 1e9\nCi fb inj 1e9\nVin inj 0 DC 0 AC 1\nRl out vcm 100\n.ac dec 40 10 3e9\n", "run\nwrdata {OUT} vdb(out) vp(out) vdb(fb) vp(fb)")
    f = A[:, 0]; gdb = A[:, 1] - A[:, 5]                                                    # columns: f, vdb(out), f, vp(out), f, vdb(fb), f, vp(fb)
    ph = np.degrees(np.unwrap(A[:, 3] - A[:, 7])) - 180.0; ph = ph - 360.0 * round(float(ph[0]) / 360.0)      # vp() is in radians; out / fb = -AOL, so subtract the 180 deg of the inversion
    f20 = cross(f, gdb, 20.0, rising=False); i1g = int(np.argmin(np.abs(f - 1e9)))
    return dict(aol_dc_dB=round(float(gdb[0]), 1), f_at_20dB_MHz=round(f20 / 1e6, 0), phase_at_1GHz_deg=round(float(ph[i1g]), 0))
@memo("spice.qualify.noise", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_noise():
    n = []
    for rs, rf, rg, tag in ((0.0, 45.0, 5.0, "en"), (2000.0, 45.0, 5.0, "in")):
        net = HEAD + f"Vin ni 0 DC 2.5 AC 1\nRs ni in {max(rs, 1e-3)}\nXu in fb vp 0 out comp LMH6629\nRf out fb {rf}\nRg fb vcm {rg}\nRl out vcm 100\n.noise v(out) Vin dec 20 100 1e8\n"
        A, _ = ng(net, "run\nsetplot noise1\nwrdata {OUT} onoise_spectrum"); f, v = A[:, 0], A[:, 1]
        G = 1 + rf / rg; rp = rf * rg / (rf + rg); at = lambda x: float(np.interp(math.log10(x), np.log10(f), v))
        out = {}
        for fq in (1e6, 200.0):
            vin2 = (at(fq) / G) ** 2                                                         # input-referred (the gain 10 AC path): includes the resistors
            out[fq] = vin2
        if tag == "en":
            e = {fq: math.sqrt(max(out[fq] - KT4 * rp, 0)) * 1e9 for fq in out}; n.append(("en", e))
        else:
            e0 = {fq: n[0][1][fq] * 1e-9 for fq in out}
            i = {fq: math.sqrt(max(out[fq] - e0[fq] ** 2 - KT4 * (rs + rp) , 0)) / rs * 1e12 for fq in out}; n.append(("in", i))
    return dict(en_1MHz_nV=round(n[0][1][1e6], 3), en_200Hz_nV=round(n[0][1][200.0], 2), in_1MHz_pA=round(n[1][1][1e6], 2))
@memo("spice.qualify.step", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_step():
    net = HEAD + "Vin in 0 PULSE(2.5 2.7 5n 20p 20p 100n 200n)\nXu in fb vp 0 out comp LMH6629\nRf out fb 240\nRg fb vcm 26.7\nRl out vcm 100\n.tran 2p 40n\n"
    A, _ = ng(net, "run\nwrdata {OUT} v(out)"); t, v = A[:, 0], A[:, 1]; v0, v1 = float(v[np.argmin(np.abs(t - 4e-9))]), float(v[np.argmin(np.abs(t - 35e-9))])
    t10 = cross(t, v, v0 + 0.1 * (v1 - v0)); t90 = cross(t, v, v0 + 0.9 * (v1 - v0))
    return dict(step_V=round(v1 - v0, 2), rise_10_90_ns=round((t90 - t10) * 1e9, 3), slew_V_us=round(0.8 * (v1 - v0) / (t90 - t10) / 1e6, 0))
@memo("spice.qualify.overload", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_overload():
    def run(vin):
        net = HEAD + f"Vin in 0 PULSE(2.5 {2.5 + vin} 5n 50p 50p 20n 200n)\nXu in fb vp 0 out comp LMH6629\nRf out fb 240\nRg fb vcm 26.7\nRl out vcm 100\n.tran 2p 60n\n"
        A, _ = ng(net, "run\nwrdata {OUT} v(out) v(in)"); t, v, vi = A[:, 0], A[:, 1], A[:, 3]; tf = cross(t, vi, 2.5 + vin / 2, rising=False)
        return t, v, tf
    t1, v1, tf1 = run(0.1)                                                                  # linear: 1.0 V of output
    t2, v2, tf2 = run(0.5)                                                                  # input 0.5 V: the output saturates (gain 10 -> 5 V of drive)
    lvl = 2.5 + 0.4; a = cross(t1, v1, lvl, rising=False) - tf1; b = cross(t2, v2, lvl, rising=False) - tf2
    return dict(sat_output_V=round(float(v2.max()), 2), extra_recovery_ns=round((b - a) * 1e9, 2))
@memo("spice.qualify.dc", files=lambda: [LIB], uses=[ng, HEAD, cross], tools=["ngspice"])
def bench_dc():
    def op(vcm=2.5, vsup=5.0, rs=9.0):
        net = f".include {{LIB}}\nVp vp 0 DC {vsup}\nVcm vcm 0 DC {vcm}\nVc comp 0 DC {vsup}\nVin in0 0 DC {vcm}\nRs in0 in {rs}\nXu in fb vp 0 out comp LMH6629\nRf out fb 90\nRg fb vcm 10\n.op\n"
        A, so = ng(net, "run\nprint v(out) v(in) i(Vp)\nwrdata {OUT} v(out)")
        return float(A[1] if A.ndim == 1 else A[0, 1]), so
    vo, so = op(); ip = [l for l in so.splitlines() if "i(vp)" in l.lower() and "=" in l]; iq = abs(float(ip[-1].split("=")[-1])) * 1e3 if ip else float("nan")
    vos = (vo - 2.5) / 10.0 * 1e6
    vo_c, _ = op(vcm=1.5); vo_p, _ = op(vsup=5.5)
    cmrr = -20 * math.log10(abs(((vo_c - 1.5) - (vo - 2.5)) / 10.0) / 1.0 + 1e-15); psrr = -20 * math.log10(abs(((vo_p - 2.5) - (vo - 2.5)) / 10.0) / 0.5 + 1e-15)
    ib = None
    net = ".include {LIB}\nVp vp 0 DC 5\nVcm vcm 0 DC 2.5\nVc comp 0 DC 5\nVin in0 0 DC 2.5\nRs in0 in 10k\nXu in fb vp 0 out comp LMH6629\nRf out fb 90\nRg fb vcm 10\n.op\n"
    A, so = ng(net, "run\nprint v(in0) - v(in)\nwrdata {OUT} v(in0)-v(in)"); dv = float(A[1] if A.ndim == 1 else A[0, 1]); ib = abs(dv) / 10e3 * 1e6
    return dict(vos_uV=round(vos, 0), iq_mA=round(iq, 1), ib_uA=round(ib, 1), cmrr_dc_dB=round(cmrr, 0), psrr_dc_dB=round(psrr, 0))
# typical datasheet values (TI SNOSB18I, repo data/datasheets/TI_LMH6629_SNOSB18I_2014-12.pdf, 5 V table) with the tolerance each comparison allows
SPEC = [("bw_3dB_MHz", "ac", 900.0, 0.15, "SSBW AV 10 WSON-8, VO 200 mVpp"), ("peaking_dB", "ac", 0.0, 1.0, "peaking 0 dB (absolute +-1 dB: the Rf here is 240 ohm)"),
        ("aol_dc_dB", "aol", 78.5, 0.03, "AVOL (model header 78.5 dB; datasheet min 72 over temperature)"), ("f_at_20dB_MHz", "aol", 400.0, 0.25, "open loop gain = 20 dB at about 400 MHz (the model header itself quotes 470 for the model)"),
        ("phase_at_1GHz_deg", "aol", -142.0, 0.10, "open loop phase at 1 GHz, COMP high: -142 deg (model header -140)"),
        ("en_1MHz_nV", "noise", 0.69, 0.10, "input voltage noise 0.69 nV/rtHz"), ("in_1MHz_pA", "noise", 2.6, 0.20, "input current noise 2.6 pA/rtHz"),
        ("slew_V_us", "step", 1600.0, 0.30, "slew rate AV 10, 2 V step"), ("rise_10_90_ns", "step", 0.90, 0.40, "rise time 0.90 ns (WSON-8)"),
        ("extra_recovery_ns", "ovl", 2.0, 0.0, "overload recovery <= 2 ns (VIN 1 Vpp)"),
        ("ib_uA", "dc", 15.0, 0.20, "input bias current 15 uA at 27 C (model header; datasheet typ in its table 6)"), ("vos_uV", "dc", 780.0, 0.0, "offset: |Vos| <= the +-780 uV maximum at 25 C (typ +-150)"),
        ("iq_mA", "dc", 15.5, 0.08, "typical supply current 15.5 mA"), ("cmrr_dc_dB", "dc", 87.0, 0.10, "CMRR 87 dB (model header; datasheet min 70)")]
# not compared: DC PSRR (the model rolls PSRR off from a 660 kHz zero, so a DC number says nothing about the 71 dB header figure) and anything the datasheet gives only as a graph
REGISTRY = os.path.join(ROOT, "state", "qualified_models.json")
def register(lib, part, res):
    """record that this exact model file passed (or failed) this bench: consumers call model_qualified(lib) and refuse a model that changed or never passed"""
    import hashlib
    reg = json.load(open(REGISTRY)) if os.path.exists(REGISTRY) else {}
    reg[os.path.relpath(lib, ROOT)] = dict(part=part, model_sha256=hashlib.sha256(open(lib, "rb").read()).hexdigest()[:16], bench_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16],
                                            ok=bool(res["ok"]), rows_passed=sum(r["ok"] for r in res["rows"]), rows=len(res["rows"]), source="TI AN-1516 benches vs the datasheet's typical column")
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True); json.dump(reg, open(REGISTRY, "w"), indent=1, sort_keys=True)
def model_qualified(lib):
    """True only if the registry holds a passing entry for this exact file content and the current bench"""
    import hashlib
    reg = json.load(open(REGISTRY)) if os.path.exists(REGISTRY) else {}; e = reg.get(os.path.relpath(lib, ROOT))
    return bool(e and e["ok"] and e["model_sha256"] == hashlib.sha256(open(lib, "rb").read()).hexdigest()[:16] and e["bench_sha256"] == hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16])
def evaluate():
    """run every bench and compare with the datasheet: the result dict, with no side effects (the self-test swaps LIB to show a wrong model FAILS)"""
    res = dict(status="MODELED: model vs the datasheet's typical column (TI AN-1516 method); not a part measurement", model=os.path.relpath(LIB, ROOT)); R = {}
    errors = {}
    for k, fn in (("ac", bench_ac), ("aol", bench_aol), ("noise", bench_noise), ("step", bench_step), ("ovl", bench_overload), ("dc", bench_dc)):
        try: R[k] = fn()
        except (SystemExit, Exception) as e: R[k] = {}; errors[k] = str(e)[-200:]               # a model the simulator cannot run through a bench has failed that bench
    res["measured"] = R; res["bench_errors"] = errors; rows = []
    for name, grp, ref, tol, note in SPEC:
        v = R[grp].get(name)
        if v is None: rows.append(dict(name=name, model=None, datasheet=ref, tol=tol, ok=False, note=note + " [bench did not run]")); continue
        if name in ("extra_recovery_ns", "vos_uV"): ok = abs(v) <= ref                         # limits, not typicals
        elif name == "peaking_dB": ok = abs(v - ref) <= tol                                   # absolute dB
        elif name == "phase_at_1GHz_deg": ok = abs(v - ref) <= tol * abs(ref)
        else: ok = abs(v - ref) <= tol * ref
        rows.append(dict(name=name, model=v, datasheet=ref, tol=tol, ok=bool(ok), note=note))
    res["rows"] = rows; res["ok"] = all(r["ok"] for r in rows); return res
def main():
    res = evaluate(); register(LIB, "LMH6629", res)
    json.dump(res, open(os.path.join(OUT, "rf2_opamp_qualify.json"), "w"), indent=1)
    for r in res["rows"]: print(("PASS " if r["ok"] else "FAIL "), r["name"], r["model"], "vs", r["datasheet"], "|", r["note"])
    return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
