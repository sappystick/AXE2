#!/usr/bin/env python3
"""RF2 MP1 input protection, ngspice comparison (2026-10-29). MODELED with GENERIC device models: part parameters marked ASSUMED are distributor / search
figures NOT yet verified against the manufacturer datasheet (rule 7); the result decides the topology, not the part.
Circuit: the rim mono coil (333 uH, 0.53 ohm) carrying 8.06 A is switched off at t = 0 into a 460 V clamp (diode + 460 V source) with critical damping
(408 ohm, 500 pF, rf2_timing.py). The coil node feeds the preamp input through:
  v1  3 x 470 ohm (1.41 kohm) -> two clamp diodes to 0 V / 5 V (BAV199-class: IS 3 pA ASSUMED generic) -> preamp input (10 pF)
  v2  depletion-mode HV MOSFET current limiter (VTO -2.5 V, RDS(on) about 42 ohm, BV 700 V: DN2470-class, ASSUMED) with gate tied to the far end of a 22 ohm
      source resistor -> the same clamps -> preamp input
Measured: peak clamp current, energy into the protection per pulse, the time the preamp input needs to come within 1 mV of rest after turn-off, and the
small-signal series resistance (thermal noise 4kTR) the signal sees once the protection has released.
usage: python3 rf2/head/rf2_mp1_spice.py   -> out/rf2_mp1_spice.json"""
import os, json, math, subprocess, tempfile
import numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
COMMON = """
* coil, damping and clamp (switch modeled as the coil current released at t = 0)
L1 0 nc 333u IC=8.06
RL nc ncs 1e-6
Rcoil ncs 0 1e9
Rd nc 0 408
Cn nc 0 500p
Dcl nc ncl DCLAMP
Vcl ncl 0 DC 460
.model DCLAMP D(IS=1e-12 N=1.0 RS=0.05)
.model DPROT D(IS=3e-12 N=1.0 RS=2 CJO=2p)
Vp5 p5 0 DC 5
* clamps at the preamp input
D1 0 xd1 DPROT
Vd1 xd1 inp DC 0
Vd2 inp xd2 DC 0
D2 xd2 p5 DPROT
Cin inp 0 10p
Rin inp 0 1e7
"""
V1 = "Rs1 nc a1 470\nRs2 a1 a2 470\nRs3 a2 inp 470\n"
V2 = """* depletion-mode MOSFET current limiter (generic level-1 model, ASSUMED parameters): drain at the coil, source through 22 ohm, gate at the far end
M1 nc g s s NDEP L=1u W=1u
Rsrc s g 22
Rser g inp 0.001
.model NDEP NMOS(LEVEL=1 VTO=-2.5 KP=9.5e-3 LAMBDA=0.002 CGSO=0 CGDO=0)
"""
def run(name, body):
    net = f"* {name}\n{COMMON}{body}\n.options reltol=1e-5 abstol=1e-12 vntol=1e-7 method=gear\n.tran 2n 120u 0 2n uic\n.control\nrun\nwrdata {{OUT}} v(nc) v(inp) i(Vd1) i(Vd2) i(Vcl)\n.endc\n.end\n"
    d = tempfile.mkdtemp(); out = os.path.join(d, "o.txt"); f = os.path.join(d, "c.cir"); open(f, "w").write(net.replace("{OUT}", out))
    r = subprocess.run(["ngspice", "-b", f], capture_output=True, text=True, timeout=600)
    if not os.path.exists(out): raise SystemExit(f"ngspice failed for {name}:\n" + (r.stdout + r.stderr)[-1500:])
    A = np.loadtxt(out); t = A[:, 0]; vnc = A[:, 1]; vin = A[:, 3]; id1 = A[:, 5]; id2 = A[:, 7]
    iprot = np.abs(id1) + np.abs(id2); E = float(np.trapezoid(np.abs(vnc - vin) * iprot, t)) if hasattr(np, "trapezoid") else 0.0
    rest = vin[-1]; bad = np.where(np.abs(vin - rest) > 1e-3)[0]; t_rec = float(t[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(t) else float("nan")
    return dict(peak_coil_V=round(float(vnc.max()), 1), peak_clamp_mA=round(float(iprot.max()) * 1e3, 1), energy_per_pulse_uJ=round(E * 1e6, 2),
                preamp_input_within_1mV_after_us=round(t_rec * 1e6, 2), ngspice_rc=r.returncode)
def small_signal_R(body, vbias=0.0):
    """series resistance at rest: inject 1 uA at the preamp input with the coil node held at 0 V (AC short)"""
    net = f"* R\nVnc nc 0 DC 0\nVp5 p5 0 DC 5\n.model DPROT D(IS=3e-12 N=1.0 RS=2 CJO=2p)\nD1 0 inp DPROT\nD2 inp p5 DPROT\n{body}\nIinj 0 inp DC 1u\n.op\n.control\nrun\nprint v(inp)\n.endc\n.end\n"
    d = tempfile.mkdtemp(); f = os.path.join(d, "r.cir"); open(f, "w").write(net); r = subprocess.run(["ngspice", "-b", f], capture_output=True, text=True, timeout=120)
    v = [l for l in r.stdout.splitlines() if "v(inp)" in l.lower() and "=" in l]
    return float(v[-1].split("=")[-1]) / 1e-6 if v else None
if __name__ == "__main__":
    kT4 = 4 * 1.380649e-23 * 300; res = dict(status="MODELED with generic ngspice models; device parameters ASSUMED (not datasheet-verified)")
    for name, body in (("v1 resistor 3 x 470 ohm", V1), ("v2 depletion MOSFET limiter", V2)):
        r = run(name, body); R = small_signal_R(body); r["series_R_ohm"] = round(R, 1) if R else None
        r["thermal_noise_nV_rtHz"] = round(math.sqrt(kT4 * R) * 1e9, 2) if R else None
        res[name] = r; print(name, r, flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_mp1_spice.json"), "w"), indent=1)
