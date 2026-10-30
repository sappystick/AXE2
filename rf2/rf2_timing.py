#!/usr/bin/env python3
"""RF2 step 5 (2026-10-29): is every coil really "fully off" when the receivers listen? Turn-off timing of the rim mono (A), an idle second transmit
coil (B, the dual-TX option), and the receive channels. MODELED; circuit as src/sim/sim_head1.py / rf2_coil_search.turnoff (coil, parallel node capacitance
Cn and damping resistor Rd, clamp diode into a clamp capacitor with a bleed resistor, the switch's body diode), now for two magnetically coupled coils.

Method: the nonlinear part (any diode conducting) is integrated with Radau (tight tolerances); once every diode has stopped for good, the circuit is
linear and the tail is propagated EXACTLY with a matrix exponential, so voltages are resolved down to nanovolts (an ODE with absolute tolerances cannot
follow 460 V down to 100 nV). A gate is "clean" when the residual is below 100 nV in the channel (the sim_head1 rule).
  mono channel  : the rim coil's own terminal voltage (A is the mono receiver), plus the preamp's overload recovery (ASSUMED 2 us; not from a datasheet)
  QUAD channel  : null 3e-5 x (M_A dI_A/dt + M_B dI_B/dt) into an unnulled disc coil (sim_head1 rule)
Cases: A alone; A with an idle B (same winding sense: B's drain swings UP, its clamp diode stays off while its clamp capacitor holds more than the induced
voltage; opposite sense: B's drain swings DOWN past ground, its switch's body diode conducts and B carries current); B idle with a discharged clamp
(first pulses after switch-on); B disconnected by a bidirectional (back-to-back) switch, leaving only its damping. Damping: the baseline ratio
Rd = 330 ohm x sqrt(L / 54 uH) (underdamped, zeta about 0.5) and critical damping Rd = 0.5 sqrt(L / Cn).
Then the noise-limited / ground-balanced depths are recomputed with the computed first gate. Coil self-capacitance 500 pF is ASSUMED (sim_head1).
usage: python3 rf2/rf2_timing.py"""
import os, sys, json, math, time
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
import rf2_ground as G
VBUS, VF, RON, CN, RCL, CL = C.VBUS, C.VF, C.RON1, C.CN, C.RCL1, C.CL1
CLEAN = 1e-7; PREAMP_REC = 2e-6; NULL_Q = 3e-5; PERIOD = 1 / C.F_BOOST
A, B = G.COILS["A"], G.COILS["B"]
M_AB = float(sum(sa * sb * C.M_coax(ra, za, rb, zb) for ra, za, sa in A["T"] for rb, zb, sb in B["T"]))
MU_A = abs(C.M_paths_turns([p[::2] for p in C.MONO], A["T"])); MU_B = abs(C.M_paths_turns([p[::2] for p in C.MONO], B["T"]))
def rd(L, mode): return 330.0 * math.sqrt(L / 54e-6) if mode == "baseline ratio" else 0.5 * math.sqrt(L / CN)
def simulate(case, damping):
    """state: iA, iB, vA, vB, vcA, vcB (v = coil node voltage, drain = VBUS + v). A switches off at t = 0 carrying I_A; B idle."""
    LA, LB = A["L"], B["L"]; sgn = {"A alone": 0, "B idle, same sense": 1, "B idle, opposite sense": -1, "B idle, same sense, clamp discharged": 1, "B disconnected (back-to-back switch)": 1}[case]
    M = sgn * M_AB; Lm = np.array([[LA, M], [M, LB]]); Li = np.linalg.inv(Lm); RdA, RdB = rd(LA, damping), rd(LB, damping)
    vcA0 = 450.0; vcB0 = 0.0 if "discharged" in case else 450.0; bdis = "disconnected" in case or sgn == 0
    def diodes(y):
        iA, iB, vA, vB, vcA, vcB = y
        dA = max(0.0, vA - vcA - VF) / RON; bA = max(0.0, -(VBUS + VF) - vA) / RON
        dB = 0.0 if bdis else max(0.0, vB - vcB - VF) / RON; bB = 0.0 if bdis else max(0.0, -(VBUS + VF) - vB) / RON
        return dA, bA, dB, bB
    def rhs(t, y):
        iA, iB, vA, vB, vcA, vcB = y; dA, bA, dB, bB = diodes(y)
        di = Li @ np.array([-vA - A["R"] * iA, -vB - B["R"] * iB]) if sgn != 0 else np.array([(-vA - A["R"] * iA) / LA, (-vB - B["R"] * iB) / LB])
        return [di[0], di[1], (iA - vA / RdA - dA + bA) / CN, (iB - vB / RdB - dB + bB) / CN, (dA - vcA / RCL) / CL, (dB - vcB / RCL) / CL]
    span = 80e-6; te = np.linspace(0, span, 16001)
    s = solve_ivp(rhs, [0, span], [A["I"], 0.0, 0.0, 0.0, vcA0, vcB0], t_eval=te, method="Radau", rtol=1e-10, atol=[1e-9, 1e-9, 1e-7, 1e-7, 1e-6, 1e-6], max_step=5e-9)
    Y = s.y; on = np.array([any(d > 0 for d in diodes(Y[:, k])) for k in range(Y.shape[1])]); last_on = s.t[np.where(on)[0][-1]] if on.any() else 0.0
    peakB_I = float(np.max(np.abs(Y[1]))); vB_min, vB_max = float(Y[3].min()), float(Y[3].max())
    # exact linear tail from just after the last diode conduction (coil currents and node voltages; clamp capacitors decoupled)
    k0 = int(np.searchsorted(s.t, last_on + 0.2e-6)); t0 = s.t[k0]; x0 = Y[:4, k0]
    Am = np.zeros((4, 4))
    if sgn != 0: Am[0:2, 0:2] = -Li @ np.diag([A["R"], B["R"]]); Am[0:2, 2:4] = -Li
    else: Am[0, 0] = -A["R"] / LA; Am[1, 1] = -B["R"] / LB; Am[0, 2] = -1 / LA; Am[1, 3] = -1 / LB
    Am[2, 0] = 1 / CN; Am[2, 2] = -1 / (RdA * CN); Am[3, 1] = 1 / CN; Am[3, 3] = -1 / (RdB * CN)
    tt = t0 + np.concatenate([np.linspace(0, 60e-6, 6001), np.linspace(60e-6, PERIOD, 400)[1:]]); X = np.array([expm(Am * (t - t0)) @ x0 for t in tt])
    vA = X[:, 0 * 0 + 2]; diA = (Am @ X.T)[0]; diB = (Am @ X.T)[1]
    mono = np.abs(vA); quad = NULL_Q * np.abs(MU_A * diA + (MU_B * diB if sgn != 0 else 0.0))
    def clean_after(sig):
        bad = np.where(sig > CLEAN)[0]; return float(tt[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(tt) else (float(tt[0]) if not len(bad) else float("inf"))
    tzA = float(s.t[np.where(Y[0] <= 0)[0][0]]) if (Y[0] <= 0).any() else float("nan")
    return dict(case=case, damping=damping, Rd_A_ohm=round(RdA), Rd_B_ohm=round(RdB), t_zero_A_us=round(tzA * 1e6, 2), last_diode_us=round(last_on * 1e6, 2),
                B_peak_current_A=round(peakB_I, 3), B_node_V=[round(vB_min, 1), round(vB_max, 1)],
                mono_clean_us=round((clean_after(mono) + PREAMP_REC) * 1e6, 2), quad_clean_us=round(max(clean_after(quad), 6e-6) * 1e6, 2),
                mono_residual_at_period_V=float(f"{mono[-1]:.2e}"))
if __name__ == "__main__":
    t0 = time.time()
    res = dict(status="MODELED (RF2 step 5: turn-off timing; coil capacitance 500 pF and preamp recovery 2 us ASSUMED)", coils=dict(A_uH=round(A["L"] * 1e6), B_uH=round(B["L"] * 1e6),
               M_AB_uH=round(M_AB * 1e6, 2), k_AB=round(M_AB / math.sqrt(A["L"] * B["L"]), 3), I_A=round(A["I"], 2)), cases=[])
    for damping in ("baseline ratio", "critical"):
        for case in ("A alone", "B idle, same sense", "B idle, opposite sense", "B idle, same sense, clamp discharged", "B disconnected (back-to-back switch)"):
            r = simulate(case, damping); res["cases"].append(r); print(json.dumps(r), flush=True)
    # depth with the computed mono first gate (A alone, critical damping) vs the 15 us assumption: severe ground, multi-period balance
    tf = next(r["mono_clean_us"] for r in res["cases"] if r["case"] == "A alone" and r["damping"] == "critical") * 1e-6
    tab = G.ground_tables([("A", "A")]); res["depth_with_computed_gate"] = {}
    for label, gate in (("assumed 15 us", 15e-6), (f"computed {tf*1e6:.1f} us", tf)):
        G.GATES[:] = np.array([gate * 1.618 ** k for k in range(9)]); row = {}
        for gname in ("none", "severe 2e-4"):
            bl = [("A", 1, "A"), ("A", 2, "A")]; Rn, Rg, _ = G.build(bl, tab, G.CHI[gname]); row[gname] = {f"{g} g": G.depth(bl, Rn, Rg, g) for g in (1.0, 5.0)}
        res["depth_with_computed_gate"][label] = row; print(label, json.dumps(row), flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(C.OUT, "rf2_timing.json"), "w"), indent=1, default=float); print("done", res["seconds"])
