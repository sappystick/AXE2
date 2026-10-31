#!/usr/bin/env python3
"""Independent-solver cross-checks of the AXE2 models (owner 2026-10-31: plug the open-source solver stack into the multi-agent framework). MODELED.

1. FastHenry (MIT / FastFieldSolvers, built from source by scripts/bootstrap.sh into /opt/solvers): 3D inductance and resistance of
   - the coil: the 26 turns of the comb (rf2_lowL_options SLOTS), each a 48-segment polygon, joined in series; litz as one square filament of
     the litz copper area (66 x 38 AWG; insulated strands -> no skin crowding inside the bundle, which is what litz is for); 1-100 kHz.
     Compared with the Maxwell / Neumann model (rf2_lowL_options) and the 333 uH design value.
   - the cord-flex TX strips: two 2 oz strips (rf2_cordflex W_TX, 1.0 mm gap) over TX_LEN_M, shorted at the head, 8 x 2 filaments per strip
     (skin + proximity); loop R(f) and L(f) compared with rf2_cordflex.R_TX_LOOP (DC).
2. SymPy: symbolic checks of formulas the models use: on-axis loop field from the Biot-Savart integral; far-field limit of the Maxwell mutual
   inductance (dipole); the critically damped settling relation (1 + s) e^-s used by clib.pi_first_sample; thin-wall regular-hexagon second
   moment 2.5 s^3 t (rf2_shaftlink / rf2_fold sections).
3. scikit-rf: the TX strip pair as a transmission line (L' from FastHenry, C' from rf2_cordflex.cps_c_pf_per_m) terminated in the coil
   (L, R) and the node capacitance; input-impedance self-resonance and the line's quarter-wave frequency, checked against the PI first gate.
Writes rf2/results/rf2_solver_xcheck.json.   usage: python3 rf2/rf2_solver_xcheck.py"""
import os, sys, json, math, subprocess, tempfile, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
FH = os.environ.get("FASTHENRY", "/opt/solvers/FastHenry2/bin/fasthenry")
SIGMA_CU_MM = 5.8e4                                   # S/mm (FastHenry .units mm takes sigma in 1/(ohm mm))

def run_fasthenry(text):
    d = tempfile.mkdtemp(prefix="fh_", dir=os.path.join(HERE, "results"))
    inp = os.path.join(d, "model.inp"); open(inp, "w").write(text)
    p = subprocess.run([FH, "model.inp"], cwd=d, capture_output=True, text=True, timeout=1800)
    zc = os.path.join(d, "Zc.mat"); txt = open(zc).read() if os.path.exists(zc) else ""
    res = []
    for m in re.finditer(r"frequency = ([0-9.eE+-]+)[^\n]*\n\s*([-0-9.eE+]+)\s*\+?\s*([-0-9.eE+]+)j", txt):
        f, R, X = float(m.group(1)), float(m.group(2)), float(m.group(3)); res.append(dict(f_Hz=f, R_ohm=R, L_uH=X / (2 * math.pi * f) * 1e6))
    for fn in os.listdir(d): os.remove(os.path.join(d, fn))      # files we just created in our own temp dir
    os.rmdir(d)
    if not res: raise RuntimeError("FastHenry produced no Zc.mat: " + p.stdout[-400:] + p.stderr[-400:])
    return res

def coil_inp(n_seg=48):
    import rf2_lowL_options as LO
    side = math.sqrt(66 * math.pi / 4 * 0.101 ** 2)               # mm, litz copper area as a square
    L = ["* AXE2 coil, 26 turns", ".units mm", f".default sigma={SIGMA_CU_MM}"]; nodes = []; k = 0
    for j in range(26):
        r, z = LO.SLOTS[j][0] * 1e3, LO.SLOTS[j][1] * 1e3
        for s in range(n_seg + 1 if j == 25 else n_seg):
            a = 2 * math.pi * s / n_seg; L.append(f"N{k} x={r * math.cos(a):.4f} y={r * math.sin(a):.4f} z={z:.4f}"); nodes.append(k); k += 1
    for i in range(len(nodes) - 1): L.append(f"E{i} N{i} N{i + 1} w={side:.4f} h={side:.4f} nhinc=1 nwinc=1")
    L += [f".external N0 N{nodes[-1]}", ".freq fmin=1e3 fmax=1e5 ndec=1", ".end"]
    return "\n".join(L) + "\n"

def strips_inp():
    import rf2_cordflex as CFX
    w, t, g, Lm = CFX.W_TX, 0.0028 * 25.4, CFX.HV_GAP, CFX.TX_LEN_M * 1e3
    y = w / 2 + g / 2
    L = ["* cord-flex TX strips", ".units mm", f".default sigma={SIGMA_CU_MM}",
         f"NA0 x=0 y={y} z=0", f"NA1 x={Lm} y={y} z=0", f"NB0 x=0 y={-y} z=0", f"NB1 x={Lm} y={-y} z=0",
         f"EA NA0 NA1 w={w} h={t} nwinc=8 nhinc=2", f"EB NB0 NB1 w={w} h={t} nwinc=8 nhinc=2", ".equiv NA1 NB1", ".external NA0 NB0", ".freq fmin=1e3 fmax=1e5 ndec=1", ".end"]
    return "\n".join(L) + "\n", Lm / 1e3

def sympy_checks():
    import sympy as sp
    out = {}
    mu, I, R, z, phi = sp.symbols("mu I R z phi", positive=True)
    # 1. on-axis Bz of a loop: dB_z = mu I /(4 pi) R^2 dphi / (R^2 + z^2)^(3/2)
    Bz = sp.integrate(mu * I / (4 * sp.pi) * R ** 2 / (R ** 2 + z ** 2) ** sp.Rational(3, 2), (phi, 0, 2 * sp.pi))
    out["loop_on_axis"] = bool(sp.simplify(Bz - mu * I * R ** 2 / (2 * (R ** 2 + z ** 2) ** sp.Rational(3, 2))) == 0)
    # 2. far-field Maxwell M -> mu pi R1^2 R2^2 / (2 d^3): numeric check with clib at d >> R
    sys.path.insert(0, os.path.join(ROOT, "concepts")); import clib as K
    R1, R2, d = 0.1, 0.08, 5.0; M = K.maxwell_M(R1, R2, d); Md = K.MU0 * math.pi * R1 ** 2 * R2 ** 2 / (2 * d ** 3)
    out["maxwell_far_field_rel"] = round(abs(M / Md - 1), 5)
    # 3. critically damped tail: v(t) = V0 (1 + t/tau) e^(-t/tau) solves v'' + 2 v'/tau + v/tau^2 = 0 with v'(0) = 0
    t, tau, V0 = sp.symbols("t tau V0", positive=True); v = V0 * (1 + t / tau) * sp.exp(-t / tau)
    out["critical_damping"] = bool(sp.simplify(sp.diff(v, t, 2) + 2 / tau * sp.diff(v, t) + v / tau ** 2) == 0 and sp.simplify(sp.diff(v, t).subs(t, 0)) == 0)
    # 4. thin regular hexagon (flats horizontal), side s, wall t: I = 2 (s t (sqrt3/2 s)^2) + 4 t s (h^2/12 + ybar^2), h = sqrt3/2 s, ybar = sqrt3/4 s
    s_, t_ = sp.symbols("s t_", positive=True); h = sp.sqrt(3) / 2 * s_
    Ihex = 2 * s_ * t_ * h ** 2 + 4 * t_ * s_ * (h ** 2 / 12 + (h / 2) ** 2)
    out["hex_thin_wall_I"] = str(sp.simplify(Ihex)); out["hex_thin_wall_ok"] = bool(sp.simplify(Ihex - sp.Rational(5, 2) * s_ ** 3 * t_) == 0)
    out["ok"] = out["loop_on_axis"] and out["maxwell_far_field_rel"] < 0.01 and out["critical_damping"] and out["hex_thin_wall_ok"]
    return out

def line_check(Lp_H_per_m, length_m, L_coil, R_coil, C_node):
    import skrf as rf
    import rf2_cordflex as CFX
    Cp = CFX.cps_c_pf_per_m() * 1e-12; Z0 = math.sqrt(Lp_H_per_m / Cp); v = 1 / math.sqrt(Lp_H_per_m * Cp); td = length_m / v
    freq = rf.Frequency(10, 20000, 4000, "kHz"); w = 2 * np.pi * freq.f
    beta = w / v; gl = 1j * beta * length_m
    ZL = (R_coil + 1j * w * L_coil) / (1 + 1j * w * C_node * (R_coil + 1j * w * L_coil))
    Zin = Z0 * (ZL + Z0 * np.tanh(gl)) / (Z0 + ZL * np.tanh(gl))
    med = rf.media.DefinedGammaZ0(frequency=freq, z0=Z0, gamma=1j * beta)          # same line as an skrf network (S-parameters on file)
    ntw = med.line(length_m, "m", name="TX strips"); s21_ph = float(np.angle(ntw.s[0, 1, 0]))
    mag = np.abs(Zin); i_pk = int(np.argmax(mag))
    return dict(Z0_ohm=round(Z0, 1), delay_ns=round(td * 1e9, 2), quarter_wave_MHz=round(1 / (4 * td) / 1e6, 1), Zin_peak_kHz=round(freq.f[i_pk] / 1e3, 1),
                Zin_peak_ohm=round(float(mag[i_pk])), lumped_SRF_kHz=round(1 / (2 * math.pi * math.sqrt(L_coil * C_node)) / 1e3, 1), skrf_s21_phase_at_10kHz=round(s21_ph, 6))

def main():
    import rf2_lowL_options as LO, rf2_cordflex as CFX, rf2_txd_spice as TS
    res = dict(status="MODELED cross-checks with independent solvers (FastHenry 3D PEEC, SymPy, scikit-rf)")
    coil = run_fasthenry(coil_inp()); res["coil_fasthenry"] = coil
    c0 = LO.coil(26, 1); res["coil_models"] = dict(neumann_maxwell_uH=round(c0["L"] * 1e6, 1), design_uH=333.0, R_model_ohm=round(c0["R"], 3))
    L_fh = coil[0]["L_uH"]
    res["coil_check"] = dict(L_fasthenry_uH=round(L_fh, 1), vs_maxwell_pct=round(100 * (L_fh / (c0["L"] * 1e6) - 1), 2), vs_design_pct=round(100 * (L_fh / 333.0 - 1), 2),
                             R_1kHz_ohm=round(coil[0]["R_ohm"], 3), R_100kHz_ohm=round(coil[-1]["R_ohm"], 3), ok=abs(L_fh / 333.0 - 1) <= 0.05)
    inp, Lm = strips_inp(); st = run_fasthenry(inp); res["strips_fasthenry"] = st
    res["strips_check"] = dict(R_dc_model_ohm=round(CFX.R_TX_LOOP, 4), R_1kHz_fh=round(st[0]["R_ohm"], 4), R_100kHz_fh=round(st[-1]["R_ohm"], 4), L_loop_uH=round(st[0]["L_uH"], 3),
                               L_per_m_nH=round(st[0]["L_uH"] / Lm * 1e3, 1), ok=abs(st[0]["R_ohm"] / CFX.R_TX_LOOP - 1) <= 0.10)
    res["sympy"] = sympy_checks()
    res["line"] = line_check(st[0]["L_uH"] * 1e-6 / Lm, Lm, L_fh * 1e-6, coil[0]["R_ohm"], TS.C_NODE)
    res["line"]["ok"] = res["line"]["quarter_wave_MHz"] > 10 * res["line"]["lumped_SRF_kHz"] / 1e3
    res["ok"] = bool(res["coil_check"]["ok"] and res["strips_check"]["ok"] and res["sympy"]["ok"] and res["line"]["ok"])
    res["findings"] = [f"coil L: FastHenry {L_fh:.1f} uH vs Maxwell {c0['L'] * 1e6:.1f} uH ({res['coil_check']['vs_maxwell_pct']:+.1f} %) vs design 333 uH ({res['coil_check']['vs_design_pct']:+.1f} %)",
                       f"coil R: {coil[0]['R_ohm']:.3f} ohm at 1 kHz (FastHenry, copper only, no leads) vs 0.601 ohm (catalog over 18.3 m incl. leads)",
                       f"TX strips: R {st[0]['R_ohm']:.4f} ohm at 1 kHz, {st[-1]['R_ohm']:.4f} ohm at 100 kHz (skin / proximity) vs {CFX.R_TX_LOOP:.4f} ohm DC model; loop L {st[0]['L_uH']:.3f} uH",
                       f"line: Z0 {res['line']['Z0_ohm']} ohm, delay {res['line']['delay_ns']} ns, quarter-wave {res['line']['quarter_wave_MHz']} MHz vs the coil + node self-resonance {res['line']['lumped_SRF_kHz']} kHz: the cord acts as a lumped element at PI frequencies",
                       f"SymPy: {{k: v for k, v in res['sympy'].items() if k != 'hex_thin_wall_I'}}".format() if False else f"SymPy: loop on-axis {res['sympy']['loop_on_axis']}, Maxwell far field rel {res['sympy']['maxwell_far_field_rel']}, critical damping {res['sympy']['critical_damping']}, hex I = {res['sympy']['hex_thin_wall_I']} ({res['sympy']['hex_thin_wall_ok']})"]
    json.dump(res, open(os.path.join(OUT, "rf2_solver_xcheck.json"), "w"), indent=1, default=float)
    for f in res["findings"]: print(f)
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
