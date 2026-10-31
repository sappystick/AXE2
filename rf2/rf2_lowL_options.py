#!/usr/bin/env python3
"""RF2 low-inductance TX and planar nulled RX options (owner 2026-10-31, from the concept boards). MODELED; an options study, nothing adopted.

What it does: re-wires the AXE2 coil comb (5 columns x 6 rows = 30 litz slots, Rubadue TXXL66/38F-2) as N turns of p strands in parallel
(N x p <= 30: the same copper, lower inductance), sets the current for the same field at 300 mm as today's 26 turns at 8.06 A, and runs
each option through the AXE2 power model (the rf2_continuous pulse train and regenerative-clamp budget), the switch ratings, the cord-flex
TX strip width (IPC-2221, rf2_cordflex), the PI tail (critically damped, calibrated to MP1 v2's 16.43 us first gate) and a target-echo
depth model. Then the same TX options with a separate planar polyimide RX nulled to the TX (a single-layer receive spiral at the rim and a
counter-wound bucking spiral on layer 2, radius solved for zero mutual inductance).

Model: coaxial circles (Maxwell mutual inductance, exact), round-wire self inductance mu0 R (ln(8R/a) - 7/4) with the litz copper-equivalent
radius; equal current sharing between parallel strands (transposed bundle, ASSUMED). Target echo of a small eddy loop (concepts/clib.eddy_echo);
noise MP1 v2 2.211 nV/rtHz (+ RX coil Johnson), 1 MHz, 1000-pulse average, SNR 5 (ASSUMED): absolute depths are optimistic, the CHANGE is the result.
Switches: Wolfspeed C3M0280090J (900 V, IDM 22 A, 0.416 ohm hot + 10 %), onsemi NTBG080N120SC1 (1200 V, IDM 110 A, RDS(on) 110 mohm max at 25 C,
Coss 79 pF; hot factor 1.6 ASSUMED). Writes rf2/results/rf2_lowL_options.json.   usage: python3 rf2/rf2_lowL_options.py"""
import os, sys, json, math
import numpy as np
from scipy.optimize import brentq
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
sys.path[:0] = [HERE, os.path.join(HERE, "head"), os.path.join(ROOT, "concepts")]
import clib as K
import rf2_cordflex as CFX, rf2_continuous as CONT
MU0 = K.MU0
COLS = [113.4 - 1.77 * k for k in range(5)]; ROW0, ROWP = 4.49, 1.44
SLOTS = [(COLS[j % 5] * 1e-3, (ROW0 + (j // 5) * ROWP) * 1e-3) for j in range(30)]
A_STRAND = math.sqrt(66 * (0.101e-3) ** 2 / 4)                 # 66 x 38 AWG copper-equivalent radius
R_PER_M = 0.601 / 18.3                                         # rf2_wire_options: 0.601 ohm over 18.3 m (incl. leads)
LEAD_M = 18.3 - sum(2 * math.pi * SLOTS[j][0] for j in range(26))
I_SCAN0, BOOST = 8.06, math.sqrt(2.5)
F, T_FLAT, VCL, VBUS, P_HEAD, WH = CONT.F, CONT.T_FLAT, CONT.V_CLAMP, CONT.VBUS, 5.0 * 0.54 / 0.9 + 5.0 * 1.372 / 0.9, 102.1
FIRST_GATE0 = 16.43
NOISE_nV, BW, NAVG, SNR = 2.211, 1e6, 1000, 5.0
DEPTHS = np.geomspace(0.03, 1.5, 90)
SW = {"C3M0280090J": dict(rds=0.416 * 1.1, idm=22.0, vds=900, coss_extra_pF=0.0, e_off=2.4e-6),
      "NTBG080N120SC1": dict(rds=0.110 * 1.6, idm=110.0, vds=1200, coss_extra_pF=79.0 - 20.0, e_off=2.4e-6 * 1.5)}
TARGETS = dict(coin_25mm_silver=dict(r=8e-3, w=8e-3, t=2e-3, sigma=6.1e7, area=math.pi * 12.5e-3 ** 2),
               gold_1g=dict(r=2e-3, w=2e-3, t=2e-3, sigma=4.1e7, area=math.pi * 2e-3 ** 2),
               gold_0p1g=dict(r=0.8e-3, w=0.8e-3, t=0.5e-3, sigma=4.1e7, area=math.pi * 1.2e-3 ** 2))

def m_matrix():
    n = len(SLOTS); M = np.zeros((n, n))
    for i, (ri, zi) in enumerate(SLOTS):
        M[i, i] = MU0 * ri * (math.log(8 * ri / A_STRAND) - 1.75)
        for j in range(i + 1, n):
            rj, zj = SLOTS[j]; M[i, j] = M[j, i] = K.maxwell_M(ri, rj, abs(zi - zj))
    return M
M30 = m_matrix()

def b_axis(slots, p, z):                                       # Bz per amp on the axis at depth z below the skid
    return sum(MU0 * r ** 2 / (2 * (r ** 2 + (z + zs) ** 2) ** 1.5) for r, zs in slots) / p

def coil(N, p):
    S = list(range(N * p)); L = float(M30[np.ix_(S, S)].sum()) / p ** 2
    R = R_PER_M * (sum(2 * math.pi * SLOTS[j][0] for j in S) + LEAD_M * p) / p ** 2
    return dict(N=N, p=p, slots=S, L=L, R=R, b=lambda z, S=S, p=p: b_axis([SLOTS[j] for j in S], p, z))

def pulse(L, R_loop, I, rds, e_off, Rd):
    tau = L / R_loop; imax = VBUS / R_loop
    if I >= imax * 0.999: return None
    T1 = -tau * math.log(1 - I / imax); tf = L * I / VCL; tt = np.linspace(0, T1, 401); ir = imax * (1 - np.exp(-tt / tau))
    ramp_i2 = float(np.trapezoid(ir ** 2, tt)); ramp_i = float(np.trapezoid(ir, tt))
    i2 = F * (ramp_i2 + 0.5 * I ** 2 * T_FLAT + I ** 2 / 3 * tf); sw_i2 = F * (ramp_i2 + 0.5 * I ** 2 * T_FLAT * 0.30)
    E = 0.5 * L * I ** 2; P_sw = sw_i2 * rds + F * e_off * (I / 7.5) * (VCL / 400.0)
    e_rd = VCL ** 2 / Rd * tf + VBUS ** 2 / Rd * (T1 + 0.5 * T_FLAT); P_rd = F * e_rd
    P_ohm = F * (ramp_i2 * R_loop + 0.5 * I ** 2 * T_FLAT * R_loop + 0.5 * T_FLAT * 0.70 * 1.2 * I)
    P_tx = F * E * 0.25 + P_ohm + P_sw * 0.3 + P_rd * 0.1
    return dict(T1_us=T1 * 1e6, fall_us=tf * 1e6, I_rms_coil=math.sqrt(i2), I_rms_sw=math.sqrt(sw_i2), P_sw=P_sw, P_rd=P_rd, P_tx=P_tx, E_mJ=E * 1e3)

def echo_mono(b_t, I, t, tg):
    v, tau = K.eddy_echo(b_t * tg["area"], tg["r"], tg["w"], tg["t"], tg["sigma"], I, t); return v
def echo_sep(b_t, b_r, I, t, tg):
    Lo = MU0 * tg["r"] * (math.log(8 * tg["r"] / (0.2235 * (tg["w"] + tg["t"]))) - 2); Ro = 2 * math.pi * tg["r"] / (tg["sigma"] * tg["w"] * tg["t"]); tau = Lo / Ro
    return (b_t * tg["area"] * I / Lo) * (b_r * tg["area"]) / tau * math.exp(-t / tau)

def depth(fn, vth):
    # speed 2026-10-31: evaluate all depths in one numpy call when fn accepts an array (echo_mono / echo_sep do); else the scalar loop
    try:
        v = np.asarray(fn(DEPTHS), dtype=float)
        if v.shape != DEPTHS.shape: raise TypeError
    except (TypeError, ValueError):
        v = np.array([fn(z) for z in DEPTHS])
    if v[0] < vth: return 0.0
    return float(np.exp(np.interp(math.log(vth), np.log(v[::-1]), np.log(DEPTHS[::-1]))))

def c_node(sw):
    import rf2_txd_spice as TS
    return TS.C_NODE + SW[sw]["coss_extra_pF"] * 1e-12

# ------------------------------------------------ planar nulled RX
RX_Z = 1.65e-3                                                 # on a 0.1 mm PI layer between SH1 (z 1.2-1.6) and QA (moved up 0.1 mm: rule 12)
RX_PITCH, RX_W, RX_T, RX_NM = 0.5e-3, 0.25e-3, 70e-6, 20
def _m_turn_table(c, z):
    """mutual inductance (per RX turn) between the TX option and a coaxial RX circle of radius r at height z: vectorised Maxwell, on a 0.05 mm grid"""
    from scipy.special import ellipk, ellipe
    r = np.arange(0.010, 0.11301, 0.00005); m = np.zeros_like(r)
    for j in c["slots"]:
        R2, zj = SLOTS[j]; d = abs(zj - z); k2 = 4 * r * R2 / ((r + R2) ** 2 + d ** 2); k = np.sqrt(k2)
        m += MU0 * np.sqrt(r * R2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))
    return r, m / c["p"]

def rx_design(c, nm=None, pitch=None, w=None):
    global RX_NM, RX_PITCH, RX_W
    RX_NM, RX_PITCH, RX_W = nm or 20, pitch or 0.5e-3, w or 0.25e-3
    """main receive spiral (layer 1, RX_NM turns) inside the TX; bucking turns counter-wound on layer 2 right under the TX wire, where a turn couples
    strongly for little area. Searches the main spiral's outer radius for the largest target response at 300 mm with an exact null (bucking radius solved)."""
    tabs = {z: _m_turn_table(c, z) for z in (RX_Z, RX_Z + 0.1e-3, RX_Z + 0.2e-3)}
    def m_tx(radii, z): r, m = tabs[round(z, 7)] if round(z, 7) in tabs else tabs[min(tabs, key=lambda q: abs(q - z))]; return float(np.sum(np.interp(radii, r, m)))
    bz = lambda loops, z: sum(sg * MU0 * rr ** 2 / (2 * (rr ** 2 + (z + zz) ** 2) ** 1.5) for rr, zz, sg in loops)
    best = None
    for r_mo in np.arange(0.040, 0.0981, 0.002):
        main = [r_mo - k * RX_PITCH for k in range(RX_NM)]; Mm = m_tx(main, RX_Z)
        for n_b in range(1, 30):
            f = lambda rb: Mm - m_tx([rb - k * RX_PITCH for k in range(n_b)], RX_Z + 0.1e-3)
            lo = max(r_mo + 1e-3, 0.012) + (n_b - 1) * RX_PITCH
            if lo < 0.1125 and f(lo) * f(0.1125) < 0:
                rb = brentq(f, lo, 0.1125); buck = [rb - k * RX_PITCH for k in range(n_b)]
                loops = [(r, RX_Z, +1) for r in main] + [(r, RX_Z + 0.1e-3, -1) for r in buck]
                sc = abs(bz(loops, 0.30))
                if best is None or sc > best[0]: best = (sc, main, buck, n_b, rb, Mm)
                break
    _, main, buck, n_b, rb, Mm = best
    d_z = abs(m_tx(main, RX_Z + 0.1e-3) - m_tx(buck, RX_Z + 0.2e-3))          # whole RX 0.1 mm further from the coil
    d_r = abs(Mm - m_tx([r + 0.1e-3 for r in buck], RX_Z + 0.1e-3))           # bucking spiral 0.1 mm larger
    loops = [(r, RX_Z, +1) for r in main] + [(r, RX_Z + 0.1e-3, -1) for r in buck]
    Lrx = 0.0
    for i, (ri, zi, si) in enumerate(loops):
        for k, (rk, zk, sk) in enumerate(loops):
            Lrx += si * sk * (MU0 * ri * (math.log(8 * ri / (RX_W / 4 + RX_T / 2)) - 1.75) if i == k else K.maxwell_M(ri, rk, abs(zi - zk) + 1e-9))
    length = sum(2 * math.pi * r for r, _, _ in loops); Rrx = length * 1.72e-8 / (RX_W * RX_T)
    c_pair = CFX.cps_c_pf_per_m(RX_W * 1e3, (RX_PITCH - RX_W) * 1e3, 2.0) * 1e-12 * 2 * math.pi * 0.105
    Crx = c_pair / (RX_NM - 1) + 20e-12                       # chain estimate + preamp input 20 pF (ASSUMED)
    b = lambda z: abs(bz(loops, z))
    return dict(main_turns=RX_NM, main_r_mm=[round(main[0] * 1e3, 2), round(main[-1] * 1e3, 2)], buck_turns=n_b, buck_r_mm=[round(rb * 1e3, 2), round(buck[-1] * 1e3, 2)],
                b300_vs_tx_coil_per_turn=round(bz(loops, 0.30) / (c["b"](0.30) * c["p"] / len(c["slots"])), 2),
                M_main_uH=round(Mm * 1e6, 3), null_ratio_dz_0p1mm=round(d_z / Mm, 5), null_ratio_dr_0p1mm=round(d_r / Mm, 5),
                L_uH=round(Lrx * 1e6, 1), R_ohm=round(Rrx, 2), C_pF=round(Crx * 1e12, 1), tau_rx_ns=round(math.sqrt(Lrx * Crx) * 1e9, 1),
                johnson_nV=round(K.johnson_noise_nV(Rrx), 2), _b=b, _Mres=max(d_z, d_r), _Mm=Mm, _tau=math.sqrt(Lrx * Crx))

def evaluate(N, p, sw, sep_rx=False, txd_near=False, rx_cfg=(20, 0.5e-3, 0.25e-3), tx2=False, flex_scale=None):
    c = coil(N, p); b300 = c["b"](0.30); base_b300 = coil(26, 1)["b"](0.30)
    I = I_SCAN0 * base_b300 / b300; Ib = I * BOOST; s = SW[sw]
    w_tx = max(CFX.W_TX, CFX.ipc2221_width_mm(CFX.I_TX * Ib / (I_SCAN0 * BOOST)))
    r_flex = CFX.R_TX_LOOP * CFX.W_TX / w_tx * (flex_scale if flex_scale is not None else (400.0 / 857.0 if txd_near else 1.0))
    width = CFX.WIDTH + 2 * ((w_tx / 2 if tx2 else w_tx) - CFX.W_TX)            # tx2: each TX strip doubled on both copper layers (2-layer cord flex)
    Rd = 408.0 * math.sqrt(c["L"] / 333e-6)
    R_loop = c["R"] + r_flex + s["rds"] + 0.010
    ps, pb = pulse(c["L"], R_loop, I, s["rds"], s["e_off"], Rd), pulse(c["L"], R_loop, Ib, s["rds"], s["e_off"], Rd)
    Cn = c_node(sw); fs = K.pi_first_sample(c["L"], Cn, I, VCL); base_fs = K.pi_first_sample(333e-6, c_node("C3M0280090J"), I_SCAN0, VCL)
    gate = fs["first_sample_us"] + (FIRST_GATE0 - base_fs["first_sample_us"])
    out = dict(N=N, p=p, switch=sw, sep_rx=(f'{rx_cfg[0]} turns, {rx_cfg[1]*1e3:.2f} mm pitch, {rx_cfg[2]*1e3:.2f} mm traces' if sep_rx else False), txd_at_400mm=txd_near, tx_strips_2layer=tx2, L_uH=round(c["L"] * 1e6, 1), R_coil=round(c["R"], 3), I_scan=round(I, 2), I_boost=round(Ib, 2),
               R_flex=round(r_flex, 3), W_TX_mm=round(w_tx, 2), flex_width_mm=round(width, 2), Rd_ohm=round(Rd), R_loop=round(R_loop, 3),
               idm_frac=round(Ib / s["idm"], 3), reachable=bool(ps and pb))
    if not (ps and pb):
        out["why_not"] = f"boost current {Ib:.1f} A is above VBUS / R_loop = {VBUS / R_loop:.1f} A"; return out, None
    tj = 40.0 + pb["P_sw"] * (2.5 + 0.5 + 7.0)
    rx = None; vn = NOISE_nV
    if sep_rx:
        rx = rx_design(c, *rx_cfg); vn = math.hypot(NOISE_nV, rx["johnson_nV"])
        v_res = rx["_Mres"] * VCL / c["L"]                     # residual RX voltage during the flyback
        s_tx = brentq(lambda x: (1 + x) * math.exp(-x) - 1e-6 / max(v_res, 1.01e-6), 1e-6, 200.0)
        s_rx = brentq(lambda x: (1 + x) * math.exp(-x) - 1e-6 / max(v_res, 1.01e-6), 1e-6, 200.0)
        gate_sep = fs["fall_us"] + fs["tau_us"] * s_tx + rx["_tau"] * 1e6 * s_rx + (FIRST_GATE0 - base_fs["first_sample_us"]) * 0.0
        out.update(rx={k: v for k, v in rx.items() if not k.startswith("_")}, V_rx_residual_flyback_V=round(v_res, 3))
        gate = max(gate_sep, fs["fall_us"] + 0.5)
    vth = SNR * vn * 1e-9 * math.sqrt(BW) / math.sqrt(NAVG); t = gate * 1e-6
    dep = {}
    for k, tg in TARGETS.items():
        if sep_rx: dep[k] = round(depth(lambda z: echo_sep(c["b"](z), rx["_b"](z), I, t, tg), vth) * 100, 1)
        else: dep[k] = round(depth(lambda z: echo_mono(c["b"](z), I, t, tg), vth) * 100, 1)
    out.update(ramp_us_scan=round(ps["T1_us"], 1), ramp_us_boost=round(pb["T1_us"], 1), first_gate_us=round(gate, 2), fall_us=round(fs["fall_us"], 2),
               P_tx_scan_W=round(ps["P_tx"], 2), P_tx_boost_W=round(pb["P_tx"], 2), runtime_scan_h=round(WH / (ps["P_tx"] + P_HEAD), 2), runtime_boost_h=round(WH / (pb["P_tx"] + P_HEAD), 2),
               P_coil_boost_W=round(pb["I_rms_coil"] ** 2 * c["R"], 2), P_flex_boost_W=round(pb["I_rms_coil"] ** 2 * r_flex, 2), P_switch_boost_W=round(pb["P_sw"], 2), Tj_switch_boost_C=round(tj, 1),
               P_Rd_boost_W=round(pb["P_rd"], 2), E_pulse_mJ=round(ps["E_mJ"], 2), depth_cm=dep, noise_nV=round(vn, 2))
    return out, c

P_RX2_W = 0.35                                                  # second MP1-class receive channel for the planar RX (ASSUMED budget)
def hybrid(N, p, sw, txd_near=False, tx2=False, rx_cfg=(40, 0.3e-3, 0.15e-3), flex_scale=None):
    """the rim coil keeps receiving (mono channel, its own first gate) AND the planar nulled RX feeds a second preamp from its earlier gate;
    independent noise, so the two SNRs add in quadrature (optimal weighting): SNR = sqrt(SNR_mono^2 + SNR_planar^2); detection at SNR 5"""
    mo, c = evaluate(N, p, sw, False, txd_near, tx2=tx2, flex_scale=flex_scale); ro, _ = evaluate(N, p, sw, True, txd_near, rx_cfg, tx2, flex_scale)
    if "depth_cm" not in mo or "depth_cm" not in ro: return dict(N=N, p=p, switch=sw, mode="hybrid", reachable=False)
    rx = rx_design(c, *rx_cfg); I = mo["I_scan"]
    sm = NOISE_nV * 1e-9 * math.sqrt(BW) / math.sqrt(NAVG); sr = ro["noise_nV"] * 1e-9 * math.sqrt(BW) / math.sqrt(NAVG)
    tm, tr = mo["first_gate_us"] * 1e-6, ro["first_gate_us"] * 1e-6
    dep = {}
    for k, tg in TARGETS.items():
        snr = lambda z: math.hypot(echo_mono(c["b"](z), I, tm, tg) / sm, echo_sep(c["b"](z), rx["_b"](z), I, tr, tg) / sr)
        dep[k] = round(depth(snr, SNR) * 100, 1)
    P_s = WH / mo["runtime_scan_h"] + P_RX2_W; P_b = WH / mo["runtime_boost_h"] + P_RX2_W
    out = dict(N=N, p=p, switch=sw, mode="hybrid (rim coil + planar nulled RX)", rx=ro["sep_rx"], txd_at_400mm=txd_near, tx_strips_2layer=tx2, L_uH=mo["L_uH"], I_boost=mo["I_boost"],
               gate_mono_us=mo["first_gate_us"], gate_planar_us=ro["first_gate_us"], depth_cm=dep, depth_mono_only_cm=mo["depth_cm"], depth_planar_only_cm=ro["depth_cm"],
               runtime_scan_h=round(WH / P_s, 2), runtime_boost_h=round(WH / P_b, 2), flex_width_mm=mo["flex_width_mm"], Tj_switch_boost_C=mo["Tj_switch_boost_C"],
               extra=f"second receive channel ({P_RX2_W} W ASSUMED), 0.1 mm PI layer above SH1 (QA / QB move up 0.1 mm)", reachable=True)
    out["rule_rows"] = [r for r in mo.get("rule_rows", [])]
    return out

def main():
    base, _ = evaluate(26, 1, "C3M0280090J")
    opts = [base, evaluate(26, 1, "NTBG080N120SC1")[0], evaluate(26, 1, "C3M0280090J", txd_near=True)[0], evaluate(26, 1, "NTBG080N120SC1", txd_near=True)[0]]
    for N, p in ((15, 2), (10, 3), (7, 4), (6, 5), (5, 6)):
        for sw in ("C3M0280090J", "NTBG080N120SC1"):
            o, _ = evaluate(N, p, sw); opts.append(o)
    for N, p in ((15, 2), (10, 3)):
        opts.append(evaluate(N, p, "NTBG080N120SC1", tx2=True)[0]); opts.append(evaluate(N, p, "NTBG080N120SC1", tx2=True, txd_near=True)[0])
    for N, p in ((26, 1), (15, 2), (10, 3), (7, 4)):
        sw = "C3M0280090J" if N >= 15 else "NTBG080N120SC1"
        o, _ = evaluate(N, p, sw, sep_rx=True); opts.append(o)
        o, _ = evaluate(N, p, sw, sep_rx=True, rx_cfg=(40, 0.3e-3, 0.15e-3)); opts.append(o)
        o, _ = evaluate(N, p, sw, sep_rx=True, txd_near=True, rx_cfg=(40, 0.3e-3, 0.15e-3)); opts.append(o)
    for o in opts:
        if "depth_cm" in o:
            o["vs_base"] = dict(first_gate_us=round(o["first_gate_us"] - base["first_gate_us"], 2), runtime_boost_h=round(o["runtime_boost_h"] - base["runtime_boost_h"], 2),
                                depth_pct={k: round(100 * (o["depth_cm"][k] / base["depth_cm"][k] - 1), 1) for k in TARGETS})
        o["rule_rows"] = [dict(rule="switch peak vs 80 % IDM", value=o["I_boost"], limit=round(0.8 * SW[o["switch"]]["idm"], 1), ok=o["I_boost"] <= 0.8 * SW[o["switch"]]["idm"]),
                          dict(rule="cord-flex width vs 16 mm (18 mm bore less 2)", value=o["flex_width_mm"], limit=16.0, ok=o["flex_width_mm"] <= 16.0),
                          dict(rule="rule 6: switch VDS >= 630 V at the 460 V clamp", value=SW[o["switch"]]["vds"], limit=630, ok=SW[o["switch"]]["vds"] >= 630)]
        if "Tj_switch_boost_C" in o: o["rule_rows"].append(dict(rule="TX switch TJ in boost vs 125 C", value=o["Tj_switch_boost_C"], limit=125.0, ok=o["Tj_switch_boost_C"] <= 125.0))
    hyb = []
    for args in ((26, 1, "C3M0280090J"), (26, 1, "NTBG080N120SC1"), (26, 1, "NTBG080N120SC1", True), (15, 2, "NTBG080N120SC1", False, True), (15, 2, "NTBG080N120SC1", True, True), (10, 3, "NTBG080N120SC1", True, True)):
        h = hybrid(*args)
        if h.get("reachable"):
            h["rule_rows"] = [dict(rule="switch peak vs 80 % IDM", value=h["I_boost"], limit=round(0.8 * SW[h["switch"]]["idm"], 1), ok=h["I_boost"] <= 0.8 * SW[h["switch"]]["idm"]),
                              dict(rule="cord-flex width vs 16 mm (18 mm bore less 2)", value=h["flex_width_mm"], limit=16.0, ok=h["flex_width_mm"] <= 16.0),
                              dict(rule="TX switch TJ in boost vs 125 C", value=h["Tj_switch_boost_C"], limit=125.0, ok=h["Tj_switch_boost_C"] <= 125.0)]
            h["vs_base"] = {k: round(100 * (h["depth_cm"][k] / base["depth_cm"][k] - 1), 1) for k in TARGETS}
        hyb.append(h); print("hybrid", args, h.get("gate_planar_us"), h.get("depth_cm"), h.get("runtime_boost_h"))
    ok_cal = abs(base["runtime_scan_h"] - 5.18) < 0.3 and abs(base["L_uH"] - 333) / 333 < 0.05
    good = [o for o in opts if "depth_cm" in o and all(r["ok"] for r in o["rule_rows"])]
    best = max(good, key=lambda o: (o["depth_cm"]["gold_0p1g"], o["runtime_boost_h"]))
    res = dict(status="MODELED options study (owner 2026-10-31): nothing adopted; equal field at 300 mm; regenerative clamp 75 % (ASSUMED as in rf2_continuous)",
               calibration=dict(base_L_uH=base["L_uH"], design_L_uH=333, base_runtime_scan_h=base["runtime_scan_h"], rf2_continuous_scan_h=5.18, ok=ok_cal),
               noise_basis=f"MP1 v2 {NOISE_nV} nV/rtHz, {BW / 1e6:.0f} MHz, {NAVG}-pulse average, SNR {SNR}", options=opts, hybrid=hyb, best_passing=best,
               ok=bool(ok_cal))
    json.dump(res, open(os.path.join(OUT, "rf2_lowL_options.json"), "w"), indent=1, default=float)
    for o in opts:
        print(o["N"], o["p"], o["switch"][:4], "RX" if o["sep_rx"] else "mono", "TXD400" if o["txd_at_400mm"] else "", "TX2L" if o["tx_strips_2layer"] else "", o["L_uH"], o["I_boost"], o.get("first_gate_us"), o.get("runtime_boost_h"), o.get("depth_cm"), o["flex_width_mm"], o.get("Tj_switch_boost_C"), o.get("why_not", ""))
    print("calibration", res["calibration"]); print("best", best["N"], best["p"], best["switch"], best["sep_rx"], best["txd_at_400mm"])
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
