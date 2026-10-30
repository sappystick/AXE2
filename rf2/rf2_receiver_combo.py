#!/usr/bin/env python3
"""RF2 step 2 (2026-10-29): the receiver for the 1-inch rim-coil head, a light transmit winding, a head mass estimate, and an SDC 2300-class mono coil
modeled in the same chain. Targets 1 g and up (owner: below 1 g need not be detected). MODELED; physics and fairness rules as rf2_coil_search.py.

Receivers (each about 24 turns, all read by the same preamp noise 1.7 nV/rtHz, RS 100 ohm, as sim_head1's improved channel):
  QUAD  the built dual rotated quadrupole (one board; null 3e-5)          X8  figure-8, the earlier receiver (null 2.5e-4)
  CN    concentric nulled: receive turns inside the transmit rim plus an opposing bucking winding sized so the TX coupling is zero (null 2.5e-4 ASSUMED,
        like X8: a mechanical null)                                       QUAD + CN  both boards, two channels: depth from CN, bearing / pinpoint from QUAD
SDC 2300-class: Minelab publishes an 8 in round mono coil (hardwired), Multi Period Fast PI, 2.3-2.4 kg without batteries, 4 x C cells, about 7 h, no
  discrimination / depth readout / pinpoint (detectorprospector.com review spec table; dealer listings). It does NOT publish coil turns, current, timing
  or noise. Modeled here as: 8 in mono (TX = RX), L 300 uH (ASSUMED typical PI mono), the SAME energy per pulse and preamp noise as ours, first gate
  swept 8-15 us (ASSUMED; MPF timing unpublished). It compares coil architecture at equal electronics, not the real SDC.
usage: python3 rf2/rf2_receiver_combo.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
OUT = C.OUT; NOISE = 1.7e-9; MASSES = (1.0, 5.0, 20.0)
def ring_set(rs, sgn=1, z=C.Z_RX): return [(float(r), z, sgn) for r in rs]
def M_turns(A, B):
    return float(sum(sa * sb * C.M_coax(ra, za, rb, zb) for ra, za, sa in A for rb, zb, sb in B))
def snr_best(a, t_first, coup):
    K = (2 * np.pi * a ** 3 / C.mu0) * (6 / np.pi ** 2) * coup; best = 0.0
    for k in range(9):
        tc = t_first * 1.618 ** k; Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 40)
        best = max(best, abs(C.vt(tt, a, K).mean()) / (NOISE * math.sqrt(1 / (2 * Tg)) / math.sqrt(C.NAVG)))
    return best
def depth(Bt, I, tf, grams, Br_fn):
    a = C.sphere_a(grams); sn = []
    for d in C.DEPTHS:
        P = np.c_[C.GRID[:, 0], C.GRID[:, 1], np.full(len(C.GRID), -d)]; cp = I * np.einsum("ij,ij->i", Bt(P), Br_fn(P))
        sn.append(max(snr_best(a, tf, c) for c in cp))
    sn = np.array(sn)
    for k in range(len(C.DEPTHS) - 1):
        if sn[k] >= 3 and sn[k + 1] < 3:
            f = (math.log(sn[k]) - math.log(3)) / (math.log(sn[k]) - math.log(sn[k + 1])); return round((C.DEPTHS[k] + f * (C.DEPTHS[k + 1] - C.DEPTHS[k])) * 1000)
    return round(C.DEPTHS[-1] * 1000) if sn[-1] >= 3 else 0
def peak_coupling(Bt, Br_fn, d):
    P = np.c_[C.GRID[:, 0], C.GRID[:, 1], np.full(len(C.GRID), -d)]; return float(np.max(np.abs(np.einsum("ij,ij->i", Bt(P), Br_fn(P)))))
def tx(T, n_sw):
    I = C.I_SW * n_sw; Ls = C.L_turns(T); L = 2 * C.E0 / I ** 2; k = math.sqrt(Ls / L); Rc = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU / k ** 2
    wf = C.turnoff(L, Rc, n_sw, I); Mu = abs(C.M_paths_turns([p[::2] for p in C.MONO], T)) / k
    return dict(T=T, I=I, k=k, L=L, wf=wf, M_unnulled=Mu, Bt=lambda P, T=T, k=k: C.B_turns(T, P) / k)
def gate(t, null):
    didt = np.abs(np.gradient(t["wf"]["i"], t["wf"]["t"])); bad = np.where(null * t["M_unnulled"] * didt > 1e-7)[0]
    return max(t["wf"]["t"][bad[-1] + 1] if len(bad) else 0.0, 6e-6)
if __name__ == "__main__":
    t0 = time.time(); res = dict(status="MODELED (RF2 step 2; same physics as sim_head1 / rf2_coil_search; not the sign-off)")
    ztop = C.H_1IN - C.TOP_STACK
    # 1. light transmit winding: depth at fixed energy depends on B / sqrt(L) only, so a small rim bundle keeps the depth with far less copper
    full = C.sites(0.100, C.Z_TX0, ztop)
    light = [(r, z, 1) for r in (C.R_OUT, C.R_OUT - C.PITCH, C.R_OUT - 2 * C.PITCH) for z in np.arange(C.Z_TX0 + 0.8e-3, C.Z_TX0 + 0.8e-3 + 8 * C.PITCH - 1e-9, C.PITCH)]   # 3 x 8 = 24 turns
    TXF, TXL = tx(full, 4), tx(light, 4)
    qbr = lambda P: C.B_paths(C.QUAD, P)
    x8 = [C.ring(r, 55, 0, 1) for r in np.linspace(20, 52, 12)] + [C.ring(r, -55, 0, -1) for r in np.linspace(20, 52, 12)]; x8br = lambda P: C.B_paths(x8, P)
    tfq_f, tfq_l = gate(TXF, 3e-5), gate(TXL, 3e-5)
    lit = sum(2 * math.pi * r for r, z, s in light); fl = sum(2 * math.pi * r for r, z, s in full)
    res["tx_light_vs_full"] = dict(full=dict(turns=len(full), litz_m=round(fl, 1), depth_mm={f"{g} g": depth(TXF["Bt"], TXF["I"], tfq_f, g, qbr) for g in MASSES}),
                                   light=dict(turns=len(light), litz_m=round(lit, 1), branches=round(TXL["k"], 2), L_uH=round(TXL["L"] * 1e6, 2), t_zero_us=round(TXL["wf"]["t_zero_us"], 2),
                                              depth_mm={f"{g} g": depth(TXL["Bt"], TXL["I"], tfq_l, g, qbr) for g in MASSES}))
    print("tx", res["tx_light_vs_full"], flush=True)
    T = TXL
    # 2. concentric nulled receiver: 24 receive turns on r_a..r_b, bucking turns at r_c with a (real) turn count that zeroes M(TX, RX); search r_a, r_b, r_c
    best = None
    # a buildable bucking winding: the turns must fit as board traces (0.3 mm pitch, 4 layers) in a 6 mm band at its radius: 4 x 6 / 0.3 = 80 turns max;
    # 30 is the conservative cap used here (an unconstrained search picked 1239 turns at r 12 mm, which cannot be laid out and whose capacitance and
    # resistance noise this model does not include). The chosen design needs 26.
    WMAX = 30.0
    for ra, rb, nr in ((50e-3, 80e-3, 12), (60e-3, 92e-3, 12), (70e-3, 92e-3, 12), (70e-3, 95e-3, 16), (80e-3, 95e-3, 8), (80e-3, 95e-3, 12)):
            for rc in (40e-3, 45e-3, 50e-3, 55e-3, 60e-3, 65e-3):
                if rc >= ra - 5e-3: continue
                R = ring_set(np.linspace(ra, rb, nr)); w = M_turns(T["T"], R) / M_turns(T["T"], ring_set([rc]))      # bucking turns
                if w > WMAX: continue
                Rn = R + [(rc, C.Z_RX, -w)]
                br = lambda P, Rn=Rn: sum(s * C.loop_B(r, z, P) for r, z, s in Rn)
                pc = peak_coupling(T["Bt"], br, 0.2)
                if best is None or pc > best[0]: best = (pc, ra, rb, rc, w, Rn, br, nr)
    pc, ra, rb, rc, w, Rn, cnbr, nr = best
    res["concentric_design"] = dict(receive_r_mm=[round(ra * 1e3), round(rb * 1e3)], receive_turns=nr, bucking_r_mm=round(rc * 1e3), bucking_turns=round(w, 1),
                                    residual_M_nH=round(sum(s * sum(C.M_coax(r, z, rt, zt) for rt, zt, st in T["T"]) for r, z, s in Rn) / T["k"] * 1e9, 3))
    tf_cn = gate(T, 2.5e-4); tf_x8 = gate(T, 2.5e-4)
    rx = {"QUAD (built quadrupole)": (qbr, tfq_l), "X8 (figure-8)": (x8br, tf_x8), "CN (concentric nulled)": (cnbr, tf_cn)}
    res["receivers"] = {}
    for nm, (br, tf) in rx.items():
        res["receivers"][nm] = dict(first_gate_us=round(tf * 1e6, 2), depth_mm={f"{g} g": depth(T["Bt"], T["I"], tf, g, br) for g in MASSES}); print(nm, res["receivers"][nm], flush=True)
    res["receivers"]["QUAD + CN (two channels)"] = dict(depth_mm={k: max(res["receivers"]["QUAD (built quadrupole)"]["depth_mm"][k], res["receivers"]["CN (concentric nulled)"]["depth_mm"][k]) for k in res["receivers"]["CN (concentric nulled)"]["depth_mm"]},
                                                         note="detection on the deeper channel; bearing and pinpoint from QUAD where its SNR >= 3")
    # 3. depth readout from the channel ratio: QUAD and CN see the same target (same a^3, same decay), so their peak-signal ratio depends on depth only
    ds = [0.05, 0.1, 0.15, 0.2, 0.3]
    ratio = [peak_coupling(T["Bt"], qbr, d) / peak_coupling(T["Bt"], cnbr, d) for d in ds]
    res["depth_from_ratio"] = dict(depth_mm=[round(d * 1e3) for d in ds], quad_over_cn=[round(x, 4) for x in ratio], monotonic=bool(all(np.diff(ratio) < 0) or all(np.diff(ratio) > 0)),
                                   note="peak over the sweep grid for each channel; independent of target size for a sphere; real targets add orientation spread")
    print("ratio", res["depth_from_ratio"], flush=True)
    # 3b. ground coupling: a uniform magnetically viscous half-space (susceptibility chi, no target) answers with chi x integral of Bt . Br over the ground
    #     (Born approximation). Its size relative to a target's peak coupling ranks how hard each receiver must work on ground (lower = better rejection).
    xs = np.linspace(-0.6, 0.6, 41); zs = -(np.geomspace(0.01, 0.6, 28))
    def ground_G(Bt, Br, h):
        tot = 0.0; zz = zs - h; dz = np.abs(np.gradient(zz)); dA = (xs[1] - xs[0]) ** 2
        for z, w_ in zip(zz, dz):
            P = np.array([[x, y, z] for x in xs for y in xs]); tot += float(np.sum(np.einsum("ij,ij->i", Bt(P), Br(P)))) * dA * w_
        return tot
    def mono_br(Tm): return lambda P: C.B_turns(Tm, P)
    gres = {}
    for nm, br in (("QUAD (built quadrupole)", qbr), ("X8 (figure-8)", x8br), ("CN (concentric nulled)", cnbr)):
        tgt = peak_coupling(T["Bt"], br, 0.15)
        gres[nm] = {f"h {int(h*1e3)} mm": abs(ground_G(T["Bt"], br, h)) / tgt for h in (0.01, 0.03)}
    q0 = gres["CN (concentric nulled)"]
    res["ground_coupling_rel"] = {k: {kk: (float(f"{vv / q0[kk]:.2e}") if vv / q0[kk] < 1e-3 else round(vv / q0[kk], 3)) for kk, vv in v.items()} for k, v in gres.items()}
    res["ground_coupling_note"] = ("|integral of Bt . Br over a uniform half-space below clearance h| divided by the target's peak coupling at 150 mm, relative to CN = 1; "
                                   "QUAD and X8 cancel a uniform half-space by symmetry (their values are numerical residue); uniform ground only (no hot rocks, no "
                                   "layering, no tilt or coil height change while sweeping, which break the symmetry); a large value means ground, not noise, limits depth "
                                   "unless ground balance removes it")
    print("ground", res["ground_coupling_rel"], flush=True)
    # 4. SDC 2300-class mono (8 in) and a mono of our diameter, equal energy and preamp noise; first gate swept (ASSUMED)
    def mono(r_out, nturns, Lt=300e-6):
        Tm = [(r_out - (j % 3) * C.PITCH, C.Z_TX0 + (j // 3) * C.PITCH, 1) for j in range(nturns)]
        return Tm
    for nm, r_out in (("SDC 2300-class 8 in mono (ASSUMED internals)", 0.1016 - 0.004), ("mono, our diameter", C.R_OUT)):
        n = 12
        while C.L_turns(mono(r_out, n)) < 300e-6: n += 1
        Tm = mono(r_out, n); Lm = C.L_turns(Tm); Im = math.sqrt(2 * C.E0 / Lm); Bm = lambda P, Tm=Tm: C.B_turns(Tm, P)
        res.setdefault("mono", {})[nm] = dict(turns=n, L_uH=round(Lm * 1e6), I_A=round(Im, 2), depth_mm_by_gate={f"{g_us} us": {f"{g} g": depth(Bm, Im, g_us * 1e-6, g, Bm) for g in MASSES} for g_us in (8, 10, 12, 15)})
        tgt = peak_coupling(Bm, Bm, 0.15); res["mono"][nm]["ground_coupling_rel_CN"] = {f"h {int(h*1e3)} mm": round(abs(ground_G(Bm, Bm, h)) / tgt / q0[f"h {int(h*1e3)} mm"], 2) for h in (0.01, 0.03)}
        print(nm, res["mono"][nm], flush=True)
    # 4b. MONO + QUAD: the rim winding as a classic mono (TX = RX, about 300 uH, one switch) for depth, plus the QUAD board for bearing / pinpoint and the
    #     depth-ratio readout. QUAD stays nulled to the transmit coil whatever else the coil does.
    n = 12
    while C.L_turns(mono(C.R_OUT, n)) < 300e-6: n += 1
    Tm = mono(C.R_OUT, n); Lm = C.L_turns(Tm); Im = math.sqrt(2 * C.E0 / Lm); Bm = lambda P, Tm=Tm: C.B_turns(Tm, P)
    Rm = C.RHO_CU * sum(2 * math.pi * r for r, z, s in Tm) / C.A_CU; wfm = C.turnoff(Lm, Rm, 1, Im)
    Tmd = dict(wf=wfm, M_unnulled=abs(C.M_paths_turns([p[::2] for p in C.MONO], Tm))); tq = gate(Tmd, 3e-5)
    rq = [peak_coupling(Bm, qbr, d) / peak_coupling(Bm, Bm, d) for d in ds]
    res["mono_plus_quad"] = dict(mono_turns=n, L_uH=round(Lm * 1e6), I_A=round(Im, 2), t_zero_us=round(wfm["t_zero_us"], 2), quad_first_gate_us=round(tq * 1e6, 2),
                                 quad_depth_mm={f"{g} g": depth(Bm, Im, tq, g, qbr) for g in MASSES},
                                 mono_depth_mm_by_gate=res["mono"]["mono, our diameter"]["depth_mm_by_gate"],
                                 depth_ratio=dict(depth_mm=[round(d * 1e3) for d in ds], quad_over_mono=[round(x, 4) for x in rq], monotonic=bool(all(np.diff(rq) < 0) or all(np.diff(rq) > 0))))
    print("mono+quad", res["mono_plus_quad"], flush=True)
    # 5. head mass estimate (component estimates, MODELED; baseline head 2.22 kg from the repo's estimate)
    litz_g_per_m = 6.0                                                 # 0.57 mm2 copper (5.1 g/m) + serving
    cn_turns_len = sum(2 * math.pi * r for r, z, s in Rn[:-1]) + abs(w) * 2 * math.pi * rc
    parts = {"transmit litz (24 turns, light rim winding)": lit * litz_g_per_m,
             "rim coil channel + bonding (PETG, 12 x 14 mm hollow ring)": 45.0,
             "receive board(s): QUAD + CN as one 4-layer 0.4 mm board, D228 (FR4 1850 kg/m3 + copper)": math.pi * 0.114 ** 2 * 0.4e-3 * 1850 * 1e3 + 12.0,
             "compute bay rigid-flex (AB1 + CB1D sections + hinges) incl. parts": 45.0,
             "LED ring board + light pipes": 20.0,
             "shell: skid + lid (PETG 1.2 mm) + side wall (1.5 mm)": (2 * math.pi * 0.1165 ** 2 * 1.2e-3 + 2 * math.pi * 0.1165 * 0.0254 * 1.5e-3) * 1270 * 1e3,
             "internal ribs and bay walls (PETG, carbonyl-iron wall where needed)": 45.0,
             "potting (gel, compute bay only, 25 cm3)": 25.0,
             "yoke / cable gland / hardware": 40.0}
    res["head_mass_g"] = dict(parts={k: round(v) for k, v in parts.items()}, total=round(sum(parts.values())), baseline_head_estimate_g=2220,
                              optional_ferrite_sheet_g=round(math.pi * (0.116 ** 2 - 0.052 ** 2) * 0.3e-3 * 3200 * 1e3), note="estimates, not weighed; ferrite sheet (0.3 mm polymer-bonded) optional, gain unverified")
    print("mass", res["head_mass_g"]["total"], flush=True)
    res["sdc2300_published"] = dict(coil="8 in round mono, hardwired", technology="Multi Period Fast pulse induction", weight_kg="2.3-2.4 without batteries (5.7 lb with NiMH)",
                                    batteries="4 x C cells (alkaline / NiMH), about 7 h", features="no discrimination, no depth readout, no pinpoint mode; LED indicator + audio; waterproof 3 m; folds to 400 mm",
                                    not_published="coil turns, inductance, current, pulse timing, noise, depth",
                                    sources=["https://www.detectorprospector.com/magazine/steves-reviews/minelab-sdc-2300-waterproof-gold-nugget-detector/", "https://www.metaldetectingworld.com/551-1-minelabsdc2300.html"])
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(OUT, "rf2_receiver_combo.json"), "w"), indent=1, default=float); print("done", res["seconds"])
