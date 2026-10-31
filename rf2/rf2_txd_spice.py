#!/usr/bin/env python3
"""RF2 TXD schematic in SPICE (roadmap P1.1, 2026-10-31). MODELED (ngspice; ideal gate drive, switch models with the datasheet on-resistance).

Topology (chosen 2026-10-31, HANDOFF section 50): the coil (333 uH, R_coil from rf2_continuous) hangs from the bulk bus through the cord flex's TX strips
(round-trip resistance from rf2_cordflex). Q1 (Wolfspeed C3M0280090J, low side, 10 mohm Vishay WSL2512 shunt in its source) ramps the current. For the
flat-top a freewheel branch D_fw (US3M) + Q2 (a second C3M0280090J on its own UCC5350, floating at the bus) returns the coil current to the bus while Q1
is off, and Q1 holds the current with a hysteretic (bang-bang) loop on the COIL current (band +-dI/2), sensed as the sum of the Q1 shunt and a second 10 mohm
shunt in the freewheel branch (sensing at the bus would include Rd's current, which steps 64 mA at every Q1 edge and makes the loop chatter): a one-switch driver cannot hold a flat-top, because every
off-time would fly back to the clamp. At turn-off Q1 and Q2 open together: the coil flies back through D_cl (US3M) into the 460 V clamp node (the
regenerative clamp holds it; modelled as 460 V behind 0.2 ohm and 10 uF, ASSUMED); Rd 408 ohm and the node capacitance (368 pF + the cord flex) damp the tail.
Part values: C3M0280090J RDS(on) 416 mohm at 150 C + 10 % (rf2_continuous), 900 V, IDM 22 A; US3M VRRM 1000 V, IFSM 100 A (Nexperia), VF about 1.5-1.7 V at
3 A, trr 52-75 ns, Cd 23 pF (diode card fitted to those, ASSUMED shape); bulk 9 x Panasonic EEHZC1H101P (100 uF, 28 mohm, 1.6 A rms each); source 0.05 ohm
(pack + chassis wiring, ASSUMED). Cases: scan long pulse (8.06 A, 25.2 V nominal), boost long pulse (12.74 A, 21.0 V cut-off), scan short pulse.
Writes rf2/results/rf2_txd_spice.json.   usage: python3 rf2/rf2_txd_spice.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
import rf2_mp1v2_chain as CH, rf2_cordflex as CFX, rf2_continuous as CONT
from simcache import memo
L, RC, RD, VCL = 333e-6, CONT.R_COIL, 408.0, 460.0
RDS = 0.416 * 1.1; RSH = 0.010; RSRC = 0.05; CBULK, ESR = 9 * 100e-6, 0.028 / 9
C_NODE = 368e-12 + CFX.cps_c_pf_per_m() * CFX.segments({"REF3": (436, 786), "hinge": (790, 816)}, {"inner": 20.0, "mid": 170.0}, 550.0)["tx_length_m"] * 1e-12
DI = 0.08                                          # hysteresis band, A (sets the flat-top switching frequency)
T_FLAT = 300e-6
R_LOOP = RC + CFX.R_TX_LOOP + RDS + RSH

def t_ramp(i_set, vbus):
    x = i_set * R_LOOP / vbus
    return -(L / R_LOOP) * math.log(1 - x) if x < 1 else float("inf")

def netlist(i_set, vbus, t_en, t_stop):
    g = 100.0
    return f"""VB vin 0 DC {vbus}
Rsrc vin bus {RSRC}
Cbk bus bk {CBULK}
Rbk bk 0 {ESR}
Rcab bus ct {CFX.R_TX_LOOP}
Vsense ct ca 0
Lc ca cb {L} IC=0
Rcl cb sw {RC}
Rd ct sw {RD}
Cn sw 0 {C_NODE}
S1 sw sq ctl1 0 SWQ1
Rsh sq 0 {RSH}
Dfw sw fw DUS3M
S2 fw fs ctl2 0 SWQ2
Rfs fs bus {RSH}
Dcl sw cl DUS3M
Ccl cl 0 10u IC={VCL}
Rcl2 cl vcl 0.2
Vcl vcl 0 DC {VCL}
Ven en 0 PWL(0 1 {t_en} 1 {t_en + 1e-9} 0)
Bc1 ctl1 0 V = v(en) * ({i_set} - i(Vsense)) * {g} - (1 - v(en)) * 10
Bc2 ctl2 0 V = v(en) * 10 - (1 - v(en)) * 10
.model SWQ1 SW(vt=0 vh={DI / 2 * g} ron={RDS} roff=1e9)
.model SWQ2 SW(vt=0 vh=1 ron={RDS} roff=1e9)
.model DUS3M D(IS=1e-9 N=2.2 RS=0.15 TT=50n CJO=23p BV=1000)
.options method=gear reltol=1e-3 abstol=1e-9 vntol=1e-5 itl4=200
.ic v(cl)={VCL} v(bus)={vbus} v(bk)=0
.tran 20n {t_stop} 0 50n uic
"""

@memo("spice.txd", files=lambda *a, **k: [], uses=[netlist, t_ramp], tools=["ngspice"])
def run(i_set, vbus, long_pulse):
    tr = t_ramp(i_set, vbus); t_en = tr + (T_FLAT if long_pulse else 0.0); t_stop = t_en + 40e-6
    vec = ["i(Vsense)", "v(sw)", "v(bus)", "v(fw)", "i(Vcl)", "v(sq)"]
    A, _ = CH.ng(netlist(i_set, vbus, t_en, t_stop), "run\nwrdata {OUT} " + " ".join(vec), timeout=1800)
    t = A[:, 0]; col = {v: A[:, 2 * k + 1] for k, v in enumerate(vec)}; i = col["i(Vsense)"]
    flat = (t > tr + 20e-6) & (t < t_en - 1e-6)
    on = col["v(sq)"] > 0.5 * RSH * i_set; edges = int(np.sum(np.diff(on[flat].astype(int)) == 1)) if flat.any() else 0
    after = t >= t_en; i_off = i[after]; t_off = t[after]
    fall = float(t_off[np.argmax(i_off < 0.01 * i_set)] - t_en) if np.any(i_off < 0.01 * i_set) else None
    pre = t < t_en
    e_clamp = float(np.trapezoid(col["i(Vcl)"] * VCL, t))                                   # energy delivered into the 460 V clamp node
    q1_i = np.where(on, i, 0.0)
    return dict(i_set_A=i_set, vbus_V=vbus, long=long_pulse, t_ramp_us=round(tr * 1e6, 1), t_off_us=round(t_en * 1e6, 1),
                i_peak_A=round(float(i[pre].max()), 3), flat_mean_A=round(float(i[flat].mean()), 3) if flat.any() else None,
                flat_ripple_pp_A=round(float(i[flat].max() - i[flat].min()), 3) if flat.any() else None,
                f_pwm_kHz=round(edges / ((t_en - tr - 21e-6) or 1) / 1e3, 1) if flat.any() else None,
                fall_us=round(fall * 1e6, 2) if fall is not None else None, fall_ideal_us=round(L * i_set / VCL * 1e6, 2),
                vds_q1_max_V=round(float(col["v(sw)"].max()), 1), vds_q2_max_V=round(float((col["v(fw)"] - col["v(bus)"]).max()), 1),
                bus_min_V=round(float(col["v(bus)"].min()), 2), bus_droop_V=round(vbus - float(col["v(bus)"].min()), 2),
                e_clamp_mJ=round(e_clamp * 1e3, 3), e_coil_mJ=round(0.5 * L * i_set ** 2 * 1e3, 3),
                q1_rms_pulse_A=round(float(np.sqrt(np.trapezoid(q1_i[pre] ** 2, t[pre]) / t_en)), 3))

def main():
    cases = dict(scan_long=run(8.06, 25.2, True), boost_long_cutoff=run(12.74, 21.0, True), scan_short=run(8.06, 25.2, False), boost_long_full=run(12.74, 29.4, True))
    lim = dict(vds_max_V=0.8 * 900, i_peak_max_A=22.0, d_ifsm_A=100.0)
    chk = {}
    for k, c in cases.items():
        chk[k] = dict(reaches_iset=c["i_peak_A"] >= 0.98 * c["i_set_A"], vds_q1_ok=c["vds_q1_max_V"] <= lim["vds_max_V"], vds_q2_ok=c["vds_q2_max_V"] <= lim["vds_max_V"],
                      peak_ok=c["i_peak_A"] <= lim["i_peak_max_A"], fall_close_to_ideal=c["fall_us"] is not None and c["fall_us"] <= 1.3 * c["fall_ideal_us"],
                      flat_regulated=(c["flat_mean_A"] is None) or abs(c["flat_mean_A"] - c["i_set_A"]) <= 0.02 * c["i_set_A"])
    res = dict(status="MODELED (ngspice): ideal gate drive; SiC as a switch with RDS(on) hot; US3M card fitted to its datasheet points (ASSUMED shape); clamp node held at 460 V (regenerative clamp ASSUMED ideal)",
               topology="Q1 low-side C3M0280090J + 10 mohm shunt; freewheel US3M + Q2 C3M0280090J (floating, own UCC5350) for the flat-top; hysteretic current loop +-%.0f mA; turn-off into the 460 V clamp through US3M; Rd 408 ohm" % (DI / 2 * 1e3),
               loop_R_ohm=dict(coil=RC, cord_flex_tx=round(CFX.R_TX_LOOP, 3), q1_hot=round(RDS, 3), shunt=RSH, total=round(R_LOOP, 3)), node_C_pF=round(C_NODE * 1e12, 1),
               limits=lim, cases=cases, checks=chk, ok=bool(all(all(v.values()) for v in chk.values())),
               new_parts=["second C3M0280090J (Q2, freewheel switch)", "second UCC5350 (floating at the bus, bootstrap or isolated supply)", "second US3M (D_fw)", "second 10 mohm WSL2512 shunt in the freewheel branch + a summing current-sense amplifier (part to choose)"])
    json.dump(res, open(os.path.join(OUT, "rf2_txd_spice.json"), "w"), indent=1)
    for k, c in cases.items(): print(k, json.dumps(c)); print("   ", chk[k])
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
