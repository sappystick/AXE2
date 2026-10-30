#!/usr/bin/env python3
"""RF2 clean-sheet side experiment (2026-10-29): which transmit-coil formation, inside a 1-inch (25.4 mm) head of the existing diameter, gives the most
noise-limited depth and the best signature data with the dual-quadrupole receiver (RX-Q). MODELED; nothing here changes the baseline.

Physics reused from src/sim/sim_head1.py (same numbers, same functions, re-parametrised): RX-Q geometry and noise (1.7 nV/rtHz, null 3e-5), gold sphere
step-off response, gate schedule (golden-ratio gates from the first clean gate, 100 pulses), SNR 3 detection, lateral search grid, TX turn-off circuit
(damping chain, clamp diode, clamp capacitor / resistor), first clean gate from the nulled turn-off tail (> 100 nV), floor 6 us.

Fair comparison: every candidate gets the SAME energy per pulse as the baseline at boost (1/2 x 54 uH x (20 A)^2 = 10.8 mJ at 400 Hz) and the same
per-switch current (20 A), clamp, bus (26 V) and capacitors per switch. With the energy fixed, the field at depth depends on the winding geometry only,
through eta = B(per amp, all turns in series) / sqrt(L(all in series)); the series/parallel split only trades current against inductance, and the turn-off
time (about L I / V = 2E / (I V)) falls as the total switched current rises (more switches in parallel). So a candidate is: a winding window (which
turn sites are wound) + a number of switches n (total current 20 n A).

Coil model: circular turns (exact elliptic-integral fields and mutual inductances), litz 1.2 mm OD on a 1.6 mm dense grid (turn self-inductance
mu0 r (ln(8 r / a) - 1.75), a 0.6 mm), copper 0.57 mm2 per turn (baseline: 45 mohm for 53.8 m of litz in six parallel layers). Ferrite backing: an
ideal permeable plane above the winding by the image method (images of TX and RX loops): an UPPER BOUND (the hood v3 model reached +12.9-14.2 % at
200 mm). Quadrant set: four 90 deg pie windings on four switches; Z mode (all same sign) is the rim loop (radial legs cancel), X / Y modes (pairs
opposite) give horizontal fields, zero coupling to RX-Q by symmetry; a 1 % current mismatch between quadrants sets the matching spec.
Not modeled: ground (mineralisation), coil self-capacitance changes, litz AC resistance, eddy currents in the head, the pairs' own turn-off.
usage: python3 rf2/rf2_coil_search.py [--quick]"""
import os, sys, json, math, time
import numpy as np
from scipy.special import ellipk, ellipe
from scipy.integrate import solve_ivp
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
mu0 = 4e-7 * math.pi; QUICK = "--quick" in sys.argv
# ---------------------------------------------------------------- envelope (the only hard inputs) and fixed electrical limits
HEAD_R = 116.5e-3; H_1IN = 25.4e-3; WALL = 2.5e-3; R_OUT = HEAD_R - WALL - 0.6e-3     # outer shell wall, then the litz radius
Z_RX = 2.0e-3; Z_TX0 = 3.2e-3                                                        # RX-Q boards in the base (as sim_head1), TX window starts above them
TOP_STACK = 1.5e-3 + 1.0e-3 + 1.0e-3                                                 # lid + ferrite sheet + clearance over the winding (display is in the centre bay)
PITCH = 1.6e-3; A_WIRE = 0.6e-3; A_CU = 0.57e-6; RHO_CU = 1.72e-8
I_SW = 20.0; VBUS = 26.0; VK = 462.0; CL1 = 100e-9; RCL1 = 5e3; RON1 = 0.05; CN = 500e-12; VF = 1.2; F_BOOST = 400.0
L0, I0 = 54e-6, 20.0; E0 = 0.5 * L0 * I0 ** 2                                       # baseline energy per pulse (boost)
# ---------------------------------------------------------------- circular-loop physics
def loop_B(R, z0, P):
    """field (T per A) of a circular loop radius R at height z0, axis z, at points P (N x 3)"""
    x, y, z = P[:, 0], P[:, 1], P[:, 2] - z0; rho = np.hypot(x, y); q = (R + rho) ** 2 + z ** 2; m = 4 * R * rho / q
    K, E = ellipk(m), ellipe(m); den = (R - rho) ** 2 + z ** 2
    Bz = mu0 / (2 * np.pi) / np.sqrt(q) * (K + (R ** 2 - rho ** 2 - z ** 2) / den * E)
    with np.errstate(invalid="ignore", divide="ignore"):
        Br = np.where(rho > 1e-9, mu0 / (2 * np.pi) * z / (rho * np.sqrt(q)) * (-K + (R ** 2 + rho ** 2 + z ** 2) / den * E), 0.0)
        c, s = np.where(rho > 1e-9, x / rho, 0.0), np.where(rho > 1e-9, y / rho, 0.0)
    return np.c_[Br * c, Br * s, Bz]
def M_coax(R1, z1, R2, z2):
    k2 = 4 * R1 * R2 / ((R1 + R2) ** 2 + (z1 - z2) ** 2); k = np.sqrt(k2)
    return mu0 * np.sqrt(R1 * R2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))
def L_turns(T):
    """inductance of turns T = [(r, z, sign)] all in series"""
    r = np.array([t[0] for t in T]); z = np.array([t[1] for t in T]); s = np.array([t[2] for t in T], float)
    Lself = mu0 * r * (np.log(8 * r / A_WIRE) - 1.75)
    i, j = np.triu_indices(len(T), 1); M = M_coax(r[i], z[i], r[j], z[j])
    return float(np.sum(Lself) + 2 * np.sum(s[i] * s[j] * M))
def B_turns(T, P):
    out = np.zeros((len(P), 3))
    for r, z, s in T: out += s * loop_B(r, z, P)
    return out
def with_images(T, zf):
    """ideal permeable plane at zf above the winding: image of each turn at 2 zf - z, same current sense (upper bound)"""
    return T + [(r, 2 * zf - z, s) for r, z, s in T]
# ---------------------------------------------------------------- receiver (RX-Q) and target, as sim_head1.py
ts = np.linspace(0, 2 * np.pi, 60, endpoint=False)
def ring(r, cx, cy, sgn, z=Z_RX):
    x = r * np.cos(ts) + cx; y = r * np.sin(ts) + cy; l = np.c_[np.append(x, x[0]), np.append(y, y[0]), np.full(61, z * 1e3)] * 1e-3
    return l if sgn > 0 else l[::-1]
QUAD = [ring(r, cx, cy, sg) for (cx, cy, sg) in ((50, 50, 1), (-50, 50, -1), (-50, -50, 1), (50, -50, -1)) for r in np.linspace(15, 45, 6)]
MONO = [ring(r, 0, 0, 1) for r in np.linspace(20, 110, 18)]
def B_paths(paths, P, chunk=200):
    out = np.zeros((len(P), 3))
    for p in paths:
        d = np.diff(p, axis=0); m = (p[:-1] + p[1:]) / 2
        for a in range(0, len(P), chunk):
            q = P[a:a + chunk]; r = q[:, None, :] - m[None, :, :]; rn = np.sqrt((r ** 2).sum(2) + 1e-12)[:, :, None]
            out[a:a + chunk] += mu0 / (4 * np.pi) * np.sum(np.cross(d[None, :, :], r) / rn ** 3, axis=1)
    return out
def M_paths_turns(paths, T):
    """mutual inductance between circular turns T and polyline loops (flux of each path through... by Neumann on a discretised turn)"""
    tot = 0.0
    for r, z, s in T:
        c = np.c_[r * np.cos(ts), r * np.sin(ts), np.full(60, z)]; c = np.vstack([c, c[:1]]); da = np.diff(c, axis=0); ma = (c[:-1] + c[1:]) / 2
        for b in paths:
            db = np.diff(b, axis=0); mb = (b[:-1] + b[1:]) / 2; d = np.linalg.norm(ma[:, None, :] - mb[None, :, :], axis=2)
            tot += s * np.sum((da @ db.T) / d)
    return 1e-7 * tot
SIG, RHO_AU = 4.1e7, 19300.0; NOISE_Q, NULL_Q, NAVG = 1.7e-9, 3e-5, 100
DEPTHS = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]); LAT = np.array([-150, -100, -60, -30, 0, 30, 60, 100, 150]) * 1e-3
GRID = np.array([[x, y] for x in LAT for y in LAT])
def sphere_a(g): return (3 * g * 1e-3 / (4 * np.pi * RHO_AU)) ** (1 / 3)
def vt(t, a, K):
    tau = mu0 * SIG * a ** 2 / np.pi ** 2; n = np.arange(1, 40)[:, None]; return K / tau * np.sum(np.exp(-(n ** 2) * t[None, :] / tau), axis=0)
def snr_best(a, t_first, coup):
    """best gated SNR over the golden-ratio gates for one target position; coup = I_total x (Bt . Br)"""
    K = (2 * np.pi * a ** 3 / mu0) * (6 / np.pi ** 2) * coup; best = 0.0
    for k in range(9):
        tc = t_first * 1.618 ** k; Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 40)
        best = max(best, abs(vt(tt, a, K).mean()) / (NOISE_Q * math.sqrt(1 / (2 * Tg)) / math.sqrt(NAVG)))
    return best
_BR = {}
def Br_at(d, images_zf=None):
    key = (d, images_zf)
    if key not in _BR:
        P = np.c_[GRID[:, 0], GRID[:, 1], np.full(len(GRID), -d)]; paths = QUAD
        if images_zf is not None: paths = QUAD + [np.c_[p[:, 0], p[:, 1], 2 * images_zf - p[:, 2]] for p in QUAD]
        _BR[key] = B_paths(paths, P)
    return _BR[key]
def depth_mm(Bt_fn, I_tot, t_first, grams, zf=None):
    a = sphere_a(grams); sn = []
    for d in DEPTHS:
        P = np.c_[GRID[:, 0], GRID[:, 1], np.full(len(GRID), -d)]; c = I_tot * np.einsum("ij,ij->i", Bt_fn(P), Br_at(d, zf))
        sn.append(max(snr_best(a, t_first, ci) for ci in c))
    sn = np.array(sn)
    for k in range(len(DEPTHS) - 1):
        if sn[k] >= 3 and sn[k + 1] < 3:
            f = (math.log(sn[k]) - math.log(3)) / (math.log(sn[k]) - math.log(sn[k + 1])); return round((DEPTHS[k] + f * (DEPTHS[k + 1] - DEPTHS[k])) * 1000)
    return round(DEPTHS[-1] * 1000) if sn[-1] >= 3 else 0
# ---------------------------------------------------------------- turn-off (sim_head1 pulse(), parametrised; n switches = one equivalent stage)
def turnoff(L, Rc, n, I_tot, CL=None, f=F_BOOST):
    CLe, RCLe, Rone = n * CL1, RCL1 / n, RON1 / n; Rd = 330.0 * math.sqrt(L / L0)                    # same damping ratio as the baseline chain
    T = 1 / f; ton = L * I_tot / VBUS; vc0 = 0.0; span = max(60e-6, 12 * L * I_tot / VK)
    for _ in range(10):
        def rhs(t, y):
            i, vd, vc = y; iD = max(0.0, vd - vc - VF) / Rone
            return [(-vd - Rc * i) / L, (i - vd / Rd - iD) / CN, (iD - vc / RCLe) / CLe]
        te = np.linspace(0, span, 6000)
        s = solve_ivp(rhs, [0, span], [I_tot, 0.0, vc0], t_eval=te, method="Radau", rtol=1e-7, atol=[1e-6, 1e-4, 1e-4], max_step=span / 3000)
        t, i, vd, vc = s.t, s.y[0], s.y[1], s.y[2]; rest = T - span - ton; vc_end = vc[-1] * math.exp(-rest / (RCLe * CLe))
        if abs(vc_end - vc0) < 0.5: break
        vc0 = vc_end
    nz = np.where(i <= 0)[0]
    return dict(t=t, i=i, vd=vd, t_zero_us=float(t[nz[0]] * 1e6) if len(nz) else float("nan"), Vds_peak=float(vd.max() + VBUS), ton_us=ton * 1e6)
def first_gate(wf, M_mono_per_A):
    didt = np.abs(np.gradient(wf["i"], wf["t"])); emf = NULL_Q * M_mono_per_A * didt; bad = np.where(emf > 1e-7)[0]
    return max(wf["t"][bad[-1] + 1] if len(bad) else 0.0, 6e-6)
# ---------------------------------------------------------------- candidates
def sites(r_in, z0, z1, r_out=R_OUT):
    rs = np.arange(r_out, r_in - 1e-9, -PITCH); zs = np.arange(z0 + PITCH / 2, z1 - PITCH / 2 + 1e-9, PITCH)
    return [(float(r), float(z), 1) for z in zs for r in rs]
def baseline_turns():
    """the built coil as circular turns: six layers, 16 turns each (8 out + 8 back on rho^2 = R0^2 + (R1^2 - R0^2) t), layer pitch 4.4 mm from z 3.2"""
    R0, R1 = 62e-3, 109.6e-3; T = []
    for k in range(6):
        zl = Z_TX0 + k * 4.4e-3 + 1.8e-3
        for j in range(8):
            r = math.sqrt(R0 ** 2 + (R1 ** 2 - R0 ** 2) * (j + 0.5) / 8); T += [(r, zl - 0.65e-3, 1), (r, zl + 0.65e-3, 1)]
    return T
def evaluate(name, T, n_sw, zf=None, layers_parallel=None, masses=(0.1, 1.0, 20.0)):
    Tt = with_images(T, zf) if zf is not None else T
    if layers_parallel:                                               # the built coil: six identical layers in parallel on one switch
        L = L_turns(Tt) / layers_parallel ** 2; I_tot = I_SW * n_sw; Bfac = 1.0 / layers_parallel; k = layers_parallel
    else:                                                             # fixed energy E0 at the total switched current: L_eq = 2 E0 / I^2 = L_series / k^2
        I_tot = I_SW * n_sw; Ls = L_turns(Tt); L = 2 * E0 / I_tot ** 2; k = math.sqrt(Ls / L); Bfac = 1.0 / k
    R_series = RHO_CU * sum(2 * math.pi * r for r, z, s in T) / A_CU; Rc = R_series / k ** 2
    Bt = lambda P: Bfac * B_turns(Tt, P)                                # tesla per TERMINAL ampere
    M_mono = abs(M_paths_turns([p[::2] for p in MONO], Tt)) * Bfac
    wf = turnoff(L, Rc, n_sw, I_tot); tf = first_gate(wf, M_mono)
    ax = Bt(np.array([[0, 0, -0.1], [0, 0, -0.2], [0, 0, -0.3]]))[:, 2] * I_tot * 1e6
    m = Bfac * sum(s * math.pi * r ** 2 for r, z, s in T) * I_tot
    row = dict(name=name, turns=len(T), switches=n_sw, I_total_A=I_tot, L_uH=round(L * 1e6, 2), branches=round(k, 2), turns_per_branch=round(len(T) / k, 1),
               R_mohm=round(Rc * 1e3, 2), energy_mJ=round(0.5 * L * I_tot ** 2 * 1e3, 2), moment_Am2=round(m, 2), axis_uT_100_200_300=[round(float(v), 1) for v in ax],
               t_zero_us=round(wf["t_zero_us"], 2), Vds_peak_V=round(wf["Vds_peak"], 0), first_gate_us=round(tf * 1e6, 2), ferrite_bound=zf is not None,
               copper_loss_W=round(I_tot ** 2 * Rc * (L * I_tot / VBUS) / 3 * F_BOOST, 2))
    row["depth_mm"] = {f"{g} g": depth_mm(Bt, I_tot, tf, g, zf) for g in masses}
    print(name, row["depth_mm"], "gate", row["first_gate_us"], "L", row["L_uH"], "k", row["branches"], "m", row["moment_Am2"], flush=True)
    return row, Bt, I_tot, tf
# ---------------------------------------------------------------- quadrant set (signature modes)
def quad_paths(T, gap=1.0e-3, r_hub=12e-3, npts=24):
    """four 90 deg pie windings: each turn = outer arc at r (from the window), radial legs to the hub, inner arc at the hub; returns paths per quadrant"""
    Q = [[], [], [], []]
    for r, z, s in T:
        for q in range(4):
            a0 = q * np.pi / 2 + gap / r; a1 = (q + 1) * np.pi / 2 - gap / r; th = np.linspace(a0, a1, npts); thi = np.linspace(a1, a0, 6)
            outer = np.c_[r * np.cos(th), r * np.sin(th)]; inner = np.c_[r_hub * np.cos(thi), r_hub * np.sin(thi)]
            p = np.vstack([outer, inner, outer[:1]]); Q[q].append(np.c_[p, np.full(len(p), z)])
    return Q
if __name__ == "__main__":
    t0 = time.time(); rows = []
    # 1. validation: the built coil through this chain (sim_head1: 7.96 A m2 at 20 A, 24.56 uT/A at 100 mm, QUAD first gate 7.29 us, 1 g 136 mm)
    base, *_ = evaluate("BASELINE built coil (6 layers parallel, 25.6 mm tall: does not fit 1 in)", baseline_turns(), 1, layers_parallel=6)
    rows.append(base)
    z_top = H_1IN - TOP_STACK                                                  # top of the TX window in the 1-inch head
    # 2. 1-inch windows: inner radius sweep (rim bundle -> spread spiral), full height, one switch
    r_ins = [100e-3, 90e-3, 75e-3, 62e-3] if not QUICK else [90e-3, 62e-3]
    for r_in in r_ins:
        row, *_ = evaluate(f"1in window r {r_in*1e3:.0f}-{R_OUT*1e3:.1f} mm, z {Z_TX0*1e3:.1f}-{z_top*1e3:.1f}, 1 switch", sites(r_in, Z_TX0, z_top), 1); rows.append(row)
    best = max(rows[1:], key=lambda r: r["depth_mm"]["1.0 g"]); rb = float(best["name"].split("r ")[1].split("-")[0]) * 1e-3
    T = sites(rb, Z_TX0, z_top)
    # 3. more switches (same energy, faster turn-off): 2 and 4
    for n in (2, 4):
        row, *_ = evaluate(f"1in window r {rb*1e3:.0f}-{R_OUT*1e3:.1f} mm, {n} switches (quadrant-ready if 4)", T, n); rows.append(row)
    # 4. ideal ferrite backing (upper bound) on the best window, 4 switches
    rowf, Btf, Itf, tff = evaluate(f"1in window r {rb*1e3:.0f}-{R_OUT*1e3:.1f} mm, 4 switches + ideal ferrite plane (BOUND)", T, 4, zf=z_top + 0.5e-3); rows.append(rowf)
    # 5. quadrant signature modes on the 4-switch window. The quadrant set in Z mode (all same sign) is the rim coil (radial legs cancel), so each turn
    #    carries the rim coil's per-turn current; a coarser turn subset (Biot-Savart) carries the same ampere-turns. X mode = (+ - - +): horizontal field.
    four = next(r for r in rows if r["switches"] == 4 and not r["ferrite_bound"])
    Tq = T[::3] if not QUICK else T[::6]; Q = quad_paths(Tq)
    I_turn = four["I_total_A"] / four["branches"] * len(T) / len(Tq); tf4 = four["first_gate_us"] * 1e-6
    def mode_Bt(signs):
        paths = [pp if signs[q] > 0 else pp[::-1] for q in range(4) for pp in Q[q]]
        return lambda P: B_paths(paths, P)
    z_d = {f"{g} g": depth_mm(mode_Bt((1, 1, 1, 1)), I_turn, tf4, g) for g in (1.0,)}
    x_d = {f"{g} g": depth_mm(mode_Bt((1, -1, -1, 1)), I_turn, tf4, g) for g in (0.1, 1.0, 20.0)}
    def M_quadrant_to_quadRX(qi):
        tot = 0.0
        for a_ in Q[qi]:
            da = np.diff(a_, axis=0); ma = (a_[:-1] + a_[1:]) / 2
            for b_ in QUAD:
                bb = b_[::2]; db = np.diff(bb, axis=0); mb = (bb[:-1] + bb[1:]) / 2; d = np.linalg.norm(ma[:, None, :] - mb[None, :, :], axis=2); tot += np.sum((da @ db.T) / d)
        return 1e-7 * tot
    Mq0 = M_quadrant_to_quadRX(0)                                               # per ampere in each modeled turn of one quadrant
    dIdt_turn = I_turn / (four["t_zero_us"] * 1e-6)
    sig = dict(quadrant_Z_mode_depth_mm=z_d, rim_coil_4sw_depth_mm=four["depth_mm"], quadrant_X_mode_depth_mm=x_d, quadrant_turns_modeled=len(Tq) * 4,
               mismatch_1pct_leak_mV=round(0.01 * abs(Mq0) * dIdt_turn * 1e3, 2), M_one_quadrant_to_RXQ_nH_per_turnA=round(Mq0 * 1e9, 3),
               note="Z mode should match the rim coil (check). X / Y modes: horizontal field, zero RX-Q coupling by symmetry; the leak row is what a 1 % current mismatch in one quadrant puts into RX-Q at turn-off (baseline aligned leak 0.01 mV, QA at 0.5 mm offset 0.13 mV)")
    print("signature", sig, flush=True)
    # 6. sensitivity: the 4-switch rim coil reaches the receiver-recovery floor (6 us, sim_head1 assumption): what an earlier first gate buys
    I4 = four["I_total_A"]; k4 = four["branches"]; Bt4 = lambda P: B_turns(T, P) / k4
    gate_sens = {f"{g_us} us": {f"{m} g": depth_mm(Bt4, I4, g_us * 1e-6, m) for m in (0.05, 0.1, 1.0)} for g_us in (6, 4, 3, 2)}
    print("gate sensitivity", gate_sens, flush=True)
    res = dict(gate_sensitivity_4sw=gate_sens, status="MODELED (RF2 clean-sheet side experiment; same physics as src/sim/sim_head1.py; not the sign-off)", envelope=dict(head_R_mm=HEAD_R * 1e3, height_mm=H_1IN * 1e3,
               tx_window_z_mm=[Z_TX0 * 1e3, round(z_top * 1e3, 2)], r_out_mm=round(R_OUT * 1e3, 2), pitch_mm=PITCH * 1e3), fairness=dict(energy_per_pulse_mJ=round(E0 * 1e3, 2), switch_current_A=I_SW, clamp_V=VK),
               rows=rows, signature=sig, seconds=round(time.time() - t0, 1),
               validation=dict(sim_head1=dict(moment_Am2=7.96, axis_uT_per_A_100mm=24.56, first_gate_us_QUAD_C0G=7.29, depth_mm_QUAD_C0G={"0.1 g": 91, "1.0 g": 136, "20.0 g": 189}),
                               this_chain=dict(moment_Am2=base["moment_Am2"], axis_uT_100mm=round(base["axis_uT_100_200_300"][0] / 20, 2), first_gate_us=base["first_gate_us"], depth_mm=base["depth_mm"])))
    json.dump(res, open(os.path.join(OUT, "rf2_coil_search.json"), "w"), indent=1, default=float); print("done", round(time.time() - t0, 1), "s")
