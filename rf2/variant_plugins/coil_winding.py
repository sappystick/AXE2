#!/usr/bin/env python3
"""Variant plugin (rf2/rf2_variants.py): coil litz and winding pattern in the rim comb. MODELED; nothing adopted, nothing excluded.

Axes
  litz     the coil litz: today's Rubadue TXXL66/38FXXX-2 (triple FEP, 1000 V, OD 1.372 mm) and other catalog constructions from
           rf2/results/rf2_wire_options.json (Rubadue catalog, data/datasheets/Rubadue_insulated_litz_FEP_ETFE_TCA.pdf, DATASHEET_LOG RF2-DS-WIRE).
           The 600 V single / double FEP constructions are INCLUDED: each raises the safety row 'rule 6: insulation rating vs 630 V' with the
           catalog section rating (600 V). Nothing is dropped.
  winding  the turn order and the comb pitch: today's row-by-row fill (turn k in column k % 5, the slot order of rf2_lowL_options.SLOTS and of the
           rf2_head builder), column-first bank fill, column by column down-and-up (the order the rf2_head spec text describes), the owner's
           progressive order (rf2_taper: up every other groove, back down through the skipped ones, column by column), and a wider (2.00 mm,
           1.60 mm slots) and a narrower (1.67 mm, 0.20 mm teeth) comb pitch with today's row fill.

Model (per (N, p, litz, winding); the core coil axis sets N turns x p strands; every effect is RELATIVE to that wiring with today's litz and
today's winding, so today's options leave the engine's numbers untouched)
  geometry   columns r = 113.4 - pitch k (k 0..4), rows z = 4.49 + (OD - 1.372)/2 + (1.44 + OD - 1.372) m (m 0..5): the bottom wire sits on the
             floor and the stack keeps today's 0.068 mm allowance per row (ASSUMED as today's). Channel: inner wall r 104.6, top z 12.6, shield coat
             r 114.45 (rf2_head option B spec). Comb slot 1.47 mm (1.60 mm for the wide-pitch comb); fit rule OD <= slot - 0.05 (rf2_wire_options).
  L          Maxwell coaxial-circle sums over the slots used (as rf2_lowL_options.coil): L = sum M_ij / p^2, self term with the litz copper-equivalent
             radius; applied as a ratio to rf2_lowL_options.coil(N, p).L. Equal field at 300 mm: I scales by b_today(300) / b_new(300).
  R          DC: catalog copper area (rf2_wire_options R_coil_20C, lay factor 1.02) per metre x the slot path length + leads; ratio to today's.
             Strand skin factor 1 + (r/delta)^4 / 48 at 100 kHz is reported (it is < 1.001 for every option); bundle proximity loss NOT modelled.
  C_self     energy method on the turn-to-turn voltage map (flyback 460 V spread linearly over the N turns; parallel strands of one turn at the same
             potential): C = sum_pairs C_ij (dV_ij / V)^2 + sum_i C_i,gnd (V_i / V)^2. C_ij = clib.c_parallel_wires(s, a, 2.1) x 2 pi r: neighbours in
             the same row / column at the measured pitch, diagonals x 0.5 (screening, ASSUMED as rf2_taper); a = litz core radius; eps_r 2.1 (FEP, as
             asked; the channel epoxy would raise every C, ASSUMED linear). Ground: the outer column to the nickel shield coat (r 114.45, joined to
             SH1 ground) and the bottom row to a plane at z 3.2 (rf2_taper ASSUMPTION), each 2 pi eps / acosh(h / a) per metre. The winding direction
             (which end is cold) is chosen for the lower C.
  first gate delta = clib.pi_first_sample(L_new, C_node + dC, I_new, 460) - clib.pi_first_sample(L, C_node, I, 460), C_node =
             rf2_lowL_options.c_node(switch) (368 pF + cord flex [+ switch Coss]), dC = C_self(option) - C_self(today's litz and winding, same N x p).
  power      rf2_lowL_options.pulse() rerun with L_new, R_loop + dR, I_new, Rd re-tuned (408 ohm x sqrt(L / 333 uH)): delta P_tx added to the core's
             boost and scan power (pack Wh from ctx.packs); dissipative clamp: + 75 % of F x dE. Unreachable boost current -> rule row, I_rms^2 dR used.
  depth      ratio of the mono depth model (rf2_lowL_options.echo_mono / depth) at the new gate, field and current to the same model at the core's.
  mass       catalog-derived g/m (rf2_wire_options coil_wire_g / 18.27 m) x the wire length.
Rules appended (only when an option differs from today; today's machine stays the 1.0 reference): rule 6 insulation (safety), max turn-to-turn
voltage vs the litz rating (safety), litz OD vs comb slot, coil stack top vs channel top, inner column vs channel inner wall, comb tooth vs 0.30 mm
(as built; printability below it ASSUMED), boost current reachable through the loop resistance.

Run as a script: prints the per-option table for today's 26 x 1 machine and writes docs/WIRE_COUPONS.md (test coupons for each litz and each winding).
usage: python3 rf2/variant_plugins/coil_winding.py"""
import os, sys, re, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); RF2 = os.path.dirname(HERE); ROOT = os.path.dirname(RF2)
for _p in (os.path.join(ROOT, "concepts"), os.path.join(RF2, "head"), RF2):
    if _p not in sys.path: sys.path.insert(0, _p)
import numpy as np
import clib as K
import rf2_lowL_options as LO

WIRE = json.load(open(os.path.join(RF2, "results", "rf2_wire_options.json")))
CAND = {c["part"]: c for c in WIRE["candidates"]}
STUDY_LEN_M = WIRE["coil"]["length_m"]                       # 18.27 m: the length rf2_wire_options' masses and resistances are for
TODAY_LITZ = "TXXL66/38FXXX-2(MWXX)"; OD0 = CAND[TODAY_LITZ]["od_mm"]
EPS_FEP = 2.1; VFLY = LO.VCL; RULE6_V = 630.0
NCOL, NROW = 5, 6; R_OUT, ROW0, ROWP0 = 113.4, 4.49, 1.44
SHIELD_R, Z_GND, WALL_R, CHAN_TOP = 114.45, 3.2, 104.6, 12.6  # rf2_head option B spec: shield coat, receive-stack plane (rf2_taper ASSUMED), channel
TOOTH_MIN = 0.30; FIT_CLEAR = 0.05; SLOT0 = 1.47; PITCH0 = 1.77
DIAG_W = 0.5

def _litz(part, desc):
    c = CAND[part]
    return dict(id=re.sub(r"(\d)([FT])X+-", r"\1\2-", part.split("(")[0]), desc=desc, today=(part == TODAY_LITZ),
                source=f"Rubadue catalog (data/datasheets/Rubadue_insulated_litz_FEP_ETFE_TCA.pdf, DATASHEET_LOG RF2-DS-WIRE) via rf2_wire_options.json: {c['kind']} {c['ins']} {c['v_rating']:.0f} V, OD {c['od_mm']} mm, {c['cmil']} CM, {c['strands']} x AWG{c['strand_awg']}, {c['f_band']}",
                p=dict(cw_litz=part))

LITZ_OPTS = [
    _litz(TODAY_LITZ, "Rubadue TXXL66/38F-2 triple FEP 1000 V, OD 1.372 (today)"),
    _litz("TXXL66/38FXXX-3(MWXX)", "TXXL66/38F-3 triple FEP 1000 V, thicker wall OD 1.524 (needs the wide-slot comb)"),
    _litz("TXXL108/40FXXX-2(MWXX)", "TXXL108/40F-2 triple FEP 1000 V, finer strands (100-200 kHz), OD 1.473"),
    _litz("TXXL230/44FXXX-2(MWXX)", "TXXL230/44F-2 triple FEP 1000 V, 44 AWG strands (400-850 kHz), OD 1.435"),
    _litz("TXXL35/38TXXX-2(MWXX)", "TXXL35/38T-2 triple ETFE (VDE 1000 V), thin OD 1.082, 560 CM"),
    _litz("DXXL66/38FXX-2(MWXX)", "DXXL66/38F-2 double FEP 600 V, OD 1.27 (rule 6 BLOCKED)"),
    _litz("SXXL100/38FX-2(MWXX)", "SXXL100/38F-2 single FEP 600 V, OD 1.417, 1600 CM: 0.396 ohm (rule 6 BLOCKED)"),
    _litz("SXXL66/38FX-2(MWXX)", "SXXL66/38F-2 single FEP 600 V, OD 1.168 (rule 6 BLOCKED)"),
]
WIND = {"row": dict(order="row", pitch=PITCH0, slot=SLOT0), "bank": dict(order="bank", pitch=PITCH0, slot=SLOT0),
        "colzz": dict(order="colzz", pitch=PITCH0, slot=SLOT0), "prog": dict(order="prog", pitch=PITCH0, slot=SLOT0),
        "wide2.0": dict(order="row", pitch=2.00, slot=1.60), "narrow1.67": dict(order="row", pitch=1.67, slot=SLOT0)}
WIND_OPTS = [
    dict(id="row", desc="row by row, turn k in column k % 5 (today: rf2_lowL_options.SLOTS / rf2_head builder)", source="rf2_lowL_options, rf2_head", today=True, p=dict(cw_winding="row")),
    dict(id="bank", desc="column-first bank fill: each column bottom -> top, crossover down to the next column", source="MODELED here", p=dict(cw_winding="bank")),
    dict(id="colzz", desc="column by column down-and-up (boustrophedon; the order the rf2_head spec text and HANDOFF 45 describe, ~195 V)", source="rf2_head spec text, HANDOFF 45", p=dict(cw_winding="colzz")),
    dict(id="prog", desc="owner's progressive order (rf2_taper): per column up every other groove, back down through the skipped ones", source="rf2_taper, HANDOFF 19", p=dict(cw_winding="prog")),
    dict(id="wide2.0", desc="row fill on a 2.00 mm comb pitch with 1.60 mm slots / 0.40 mm teeth (fits the channel: inner column edge vs r 104.6)", source="MODELED here; channel from rf2_head", p=dict(cw_winding="wide2.0")),
    dict(id="narrow1.67", desc="row fill on a 1.67 mm pitch (1.47 mm slots, 0.20 mm teeth: below the 0.30 mm as built)", source="MODELED here", p=dict(cw_winding="narrow1.67")),
]
AXES = [dict(name="litz", help="coil litz construction (Rubadue catalog; coil_winding plugin)", options=LITZ_OPTS),
        dict(name="winding", help="coil turn order and comb pitch (coil_winding plugin)", options=WIND_OPTS)]

# ---------------------------------------------------------------- geometry and physics
def strand_d_mm(awg): return 0.127 * 92 ** ((36 - awg) / 39.0)
def a_eq_m(c): return math.sqrt(c["strands"]) * strand_d_mm(c["strand_awg"]) / 2 * 1e-3      # copper-equivalent radius (as LO.A_STRAND)

def grid(od, pitch, r_out=R_OUT):
    z0 = ROW0 + (od - OD0) / 2; rp = ROWP0 + (od - OD0)
    return {(c, m): (r_out - pitch * c, z0 + rp * m) for c in range(NCOL) for m in range(NROW)}, rp

def sequence(order, n):
    """the first n slots in winding order, as (column, row); column 0 outermost, row 0 on the floor"""
    if order == "row": return [(k % NCOL, k // NCOL) for k in range(n)]
    seq = []; c = 0
    while len(seq) < n:
        rows = list(range(min(NROW, n - len(seq))))
        if order == "bank": rr = rows
        elif order == "colzz": rr = rows if c % 2 == 0 else rows[::-1]
        elif order == "prog": rr = rows[0::2] + rows[1::2][::-1]
        else: raise KeyError(order)
        seq += [(c, m) for m in rr]; c += 1                          # a partly filled column uses its lowest rows (the wires rest on the floor)
    return seq

def b_axis(pos, p, z):
    return sum(K.MU0 * r ** 2 / (2 * (r ** 2 + (z + zs) ** 2) ** 1.5) for r, zs in pos) / p

def winding_model(N, p, part, wid, r_out=R_OUT, ground=True):
    c = CAND[part]; w = WIND[wid]; od = c["od_mm"]
    G, rp = grid(od, w["pitch"], r_out); seq = sequence(w["order"], N * p)
    pos = [(G[s][0] * 1e-3, G[s][1] * 1e-3) for s in seq]
    a_l = a_eq_m(c); L = 0.0
    for i, (ri, zi) in enumerate(pos):
        L += K.MU0 * ri * (math.log(8 * ri / a_l) - 1.75)
        for j in range(i + 1, len(pos)): L += 2 * K.maxwell_M(ri, pos[j][0], abs(zi - pos[j][1]))
    L /= p ** 2
    length = sum(2 * math.pi * r for r, _ in pos) + LO.LEAD_M * p
    R = c["R_coil_20C"] / STUDY_LEN_M * length / p ** 2
    turn = {s: k // p for k, s in enumerate(seq)}; a = c["core_mm"] / 2 * 1e-3
    def caps(rev):
        frac = {s: ((N - t - 0.5) if rev else (t + 0.5)) / N for s, t in turn.items()}
        Cw = 0.0; dmax = 0; dorth = 0; Cg = 0.0
        for i, s1 in enumerate(seq):
            for s2 in seq[i + 1:]:
                dc, dm = abs(s1[0] - s2[0]), abs(s1[1] - s2[1])
                if max(dc, dm) != 1: continue
                (r1, z1), (r2, z2) = G[s1], G[s2]; d = math.hypot(r1 - r2, z1 - z2) * 1e-3
                cij = (DIAG_W if dc + dm == 2 else 1.0) * K.c_parallel_wires(d, a, EPS_FEP) * 2 * math.pi * (r1 + r2) / 2 * 1e-3
                dt = abs(turn[s1] - turn[s2]); Cw += cij * (dt / N) ** 2; dmax = max(dmax, dt)
                if dc + dm == 1: dorth = max(dorth, dt)
            r1, z1 = G[s1]
            if s1[0] == 0 and ground: Cg += 2 * math.pi * K.EPS0 * EPS_FEP / math.acosh((SHIELD_R - R_OUT + r_out - r1) * 1e-3 / a) * 2 * math.pi * r1 * 1e-3 * frac[s1] ** 2
            if s1[1] == 0 and ground: Cg += 2 * math.pi * K.EPS0 * EPS_FEP / math.acosh((z1 - Z_GND) * 1e-3 / a) * 2 * math.pi * r1 * 1e-3 * frac[s1] ** 2
        return Cw + Cg, Cw, Cg, dmax, dorth
    best = min((caps(False), caps(True)), key=lambda x: x[0])
    used = set(seq); top = max(G[s][1] for s in used) + od / 2; inner = min(G[s][0] for s in used) - od / 2
    delta = K.skin_depth(1.72e-8, 100e3); rs = strand_d_mm(c["strand_awg"]) / 2 * 1e-3
    return dict(L=L, R=R, length_m=length, C=best[0], C_tt=best[1], C_gnd=best[2], dt_max=best[3], V_tt_max=best[3] * VFLY / N, V_tt_orth=best[4] * VFLY / N,
                b300=b_axis(pos, p, 0.30), pos=pos, top_z=top, inner_r=inner, od=od, slot=w["slot"], tooth=w["pitch"] - w["slot"],
                ac_factor_100k=1 + (rs / delta) ** 4 / 48, mass_g=c["coil_wire_g"] / STUDY_LEN_M * length)

# ---------------------------------------------------------------- engine interface
def prepare(ctx):
    ctx.coil_winding = dict(geo={}, elec={})

def _geo(ctx, N, p, part, wid):
    k = (N, p, part, wid); g = ctx.coil_winding["geo"]
    if k not in g:
        refs = ctx.coil_winding.setdefault("ref", {})
        if (N, p) not in refs: refs[(N, p)] = winding_model(N, p, TODAY_LITZ, "row")
        ref = refs[(N, p)]
        new = winding_model(N, p, part, wid); core = LO.coil(N, p)
        g[k] = dict(new=new, ref=ref, L_core=core["L"], b_core=core["b"], L_new=core["L"] * new["L"] / ref["L"], R_core=core["R"], R_new=core["R"] * new["R"] / ref["R"],
                    I_ratio=ref["b300"] / new["b300"], dC=new["C"] - ref["C"], b_new=lambda z, pos=new["pos"], p=p: b_axis(pos, p, z))
    return g[k]

def _rule(m, name, v, lim, sense, where, kind):
    ok = v <= lim if sense == "<=" else v >= lim
    m["rules"].append(dict(rule=name, value=round(v, 3), limit=round(lim, 3), sense=sense, ok=bool(ok), where=where, kind=kind))

def _vth(): return LO.SNR * LO.NOISE_nV * 1e-9 * math.sqrt(LO.BW) / math.sqrt(LO.NAVG)

def evaluate(ctx, P, m):
    part, wid = P.get("cw_litz", TODAY_LITZ), P.get("cw_winding", "row")
    if part == TODAY_LITZ and wid == "row": return                      # today's litz and winding: the engine's numbers stay as they are
    if not hasattr(ctx, "coil_winding"): prepare(ctx)
    e = m["_e"]; N, p, sw = P["N"], P["p"], P["sw"]; g = _geo(ctx, N, p, part, wid); new = g["new"]; c = CAND[part]
    ek = (N, p, part, wid, sw, e["R_loop"], e["I_scan"], e["I_boost"], e.get("gate"))
    E = ctx.coil_winding["elec"]
    if ek not in E:
        s = LO.SW[sw]; Cn = LO.c_node(sw); L0, L1 = g["L_core"], g["L_new"]; I0, Ib0 = e["I_scan"], e["I_boost"]; I1, Ib1 = I0 * g["I_ratio"], Ib0 * g["I_ratio"]
        dR = g["R_new"] - g["R_core"]
        fs0 = K.pi_first_sample(L0, Cn, I0, VFLY); fs1 = K.pi_first_sample(L1, Cn + g["dC"], I1, VFLY); dgate = fs1["first_sample_us"] - fs0["first_sample_us"]
        Rd0, Rd1 = 408.0 * math.sqrt(L0 / 333e-6), 408.0 * math.sqrt(L1 / 333e-6)
        out = dict(dgate=dgate, dR=dR, reach=True, Cn=Cn)
        for mode, Ia, Ib in (("scan", I0, I1), ("boost", Ib0, Ib1)):
            p0 = LO.pulse(L0, e["R_loop"], Ia, s["rds"], s["e_off"], Rd0); p1 = LO.pulse(L1, e["R_loop"] + dR, Ib, s["rds"], s["e_off"], Rd1)
            if p0 and p1: out["dP_" + mode] = p1["P_tx"] - p0["P_tx"]; out["dE_" + mode] = (p1["E_mJ"] - p0["E_mJ"]) * 1e-3
            else:
                out["dP_" + mode] = (p0["I_rms_coil"] if p0 else 0.2865 * Ia) ** 2 * dR; out["dE_" + mode] = 0.5 * (L1 * Ib ** 2 - L0 * Ia ** 2); out["reach"] = out["reach"] and bool(p1)
        out["I_boost_new"] = Ib1; out["I_reach_max"] = LO.VBUS / (e["R_loop"] + dR)
        g0 = e.get("gate") or m["first_gate_us"]; vth = _vth(); dep = {}
        if g0:
            for kk, tg in LO.TARGETS.items():
                d0 = LO.depth(lambda z: LO.echo_mono(g["b_core"](z), I0, g0 * 1e-6, tg), vth)
                d1 = LO.depth(lambda z: LO.echo_mono(g["b_new"](z), I1, (g0 + dgate) * 1e-6, tg), vth)
                dep[kk] = d1 / d0 if d0 > 0 else 1.0
        out["depth_ratio"] = dep; E[ek] = out
    o = E[ek]
    if m.get("first_gate_us") is not None: m["first_gate_us"] = round(m["first_gate_us"] + o["dgate"], 2)
    if o["depth_ratio"] and isinstance(m.get("depth_cm"), dict):
        m["depth_cm"] = {k: round(v * o["depth_ratio"].get(k, 1.0), 1) for k, v in m["depth_cm"].items()}
    wh = ctx.packs[P["pack"]]["Wh_usable"] if hasattr(ctx, "packs") and P.get("pack") in getattr(ctx, "packs", {}) else m["runtime_boost_h"] * m["P_boost_W"]
    dPb, dPs = o["dP_boost"], o["dP_scan"]
    if P.get("clamp") == "dissip": dPb += 0.75 * LO.F * o["dE_scan"] * 2.5; dPs += 0.75 * LO.F * o["dE_scan"]
    Pb = wh / m["runtime_boost_h"] + dPb; Ps = wh / m["runtime_scan_h"] + dPs
    m["P_boost_W"] = round(m["P_boost_W"] + dPb, 2); m["runtime_boost_h"] = round(wh / Pb, 2); m["runtime_scan_h"] = round(wh / Ps, 2)
    m["mass_delta_g"] = int(round(m["mass_delta_g"] + new["mass_g"] - g["ref"]["mass_g"]))
    where = f"coil litz {part} / winding {wid}"
    _rule(m, "rule 6: insulation rating vs 630 V (coil litz, catalog section rating)", c["v_rating"], RULE6_V, ">=", f"coil litz {part}", "safety")
    _rule(m, "coil max turn-to-turn voltage at the 460 V flyback vs litz rating", new["V_tt_max"], c["v_rating"], "<=", where, "safety")
    _rule(m, "litz OD vs comb slot (OD <= slot - 0.05)", new["od"], new["slot"] - FIT_CLEAR, "<=", f"coil comb ({wid})", "target")
    _rule(m, "coil stack top vs channel top z 12.6", new["top_z"], CHAN_TOP, "<=", f"coil channel ({wid})", "target")
    _rule(m, "coil inner column edge vs channel inner wall r 104.6", new["inner_r"], WALL_R, ">=", f"coil channel ({wid})", "target")
    if WIND[wid]["pitch"] != PITCH0: _rule(m, "comb tooth vs 0.30 mm (as built; printability below it ASSUMED)", new["tooth"], TOOTH_MIN, ">=", f"coil comb ({wid})", "target")
    if o["dR"] > 0 or not o["reach"]: _rule(m, "TX boost current vs VBUS / R_loop (reachable)", o["I_boost_new"], o["I_reach_max"], "<=", where, "target")
    x = m["extra"]
    x.update(C_self_pF=round(new["C"] * 1e12, 1), C_self_today_pF=round(g["ref"]["C"] * 1e12, 1), C_node_pF=round(float(o["Cn"] + g["dC"]) * 1e12, 1), R_coil_ohm=round(g["R_new"], 3),
             L_uH=round(float(g["L_new"]) * 1e6, 1), L_uH_change_pct=round(float(100 * (g["L_new"] / g["L_core"] - 1)), 2), gate_delta_us=round(float(o["dgate"]), 3),
             V_turn_turn_max=round(new["V_tt_max"], 1), V_turn_turn_touching=round(new["V_tt_orth"], 1), litz_v_rating=c["v_rating"], litz_od_mm=new["od"])

# ---------------------------------------------------------------- report and coupon spec (script mode)
def table(N=26, p=1, sw="C3M0280090J"):
    """per-option effects on the given wiring with everything else at today's value (litz options with today's winding, winding options with today's litz)"""
    class _C: pass
    ctx = _C(); prepare(ctx); e, _ = LO.evaluate(N, p, sw, False, False); e = dict(e, gate=e["first_gate_us"]); rows = []
    for ax, opts in (("litz", LITZ_OPTS), ("winding", WIND_OPTS)):
        for op in opts:
            P = dict(N=N, p=p, sw=sw, cw_litz=TODAY_LITZ, cw_winding="row", clamp="regen"); P.update(op["p"])
            m = dict(_e=e, extra={}, first_gate_us=e["first_gate_us"], depth_cm=dict(e["depth_cm"]), runtime_boost_h=e["runtime_boost_h"], runtime_scan_h=e["runtime_scan_h"],
                     P_boost_W=round(LO.WH / e["runtime_boost_h"], 2), mass_delta_g=0, rules=[])
            ctx.packs = {"x": dict(Wh_usable=LO.WH)}; P["pack"] = "x"
            evaluate(ctx, P, m); g = _geo(ctx, N, p, P["cw_litz"], P["cw_winding"])
            rows.append(dict(axis=ax, id=op["id"], today=op.get("today", False), C_self_pF=round(g["new"]["C"] * 1e12, 1), C_tt_pF=round(g["new"]["C_tt"] * 1e12, 1), C_gnd_pF=round(g["new"]["C_gnd"] * 1e12, 1),
                             L_uH=round(g["L_new"] * 1e6, 1), dL_pct=round(100 * (g["L_new"] / g["L_core"] - 1), 2), R_ohm=round(g["R_new"], 3), V_tt=round(g["new"]["V_tt_max"]), V_orth=round(g["new"]["V_tt_orth"]),
                             gate=m["first_gate_us"], dgate=round(m["first_gate_us"] - e["first_gate_us"], 2), boost_h=m["runtime_boost_h"], dboost=round(m["runtime_boost_h"] - e["runtime_boost_h"], 2),
                             scan_h=m["runtime_scan_h"], mass=m["mass_delta_g"], depth=m["depth_cm"], breaks=[f"{r['rule']} ({r['value']} vs {r['limit']})" for r in m["rules"] if not r["ok"]],
                             ac=round(g["new"]["ac_factor_100k"], 5)))
    return rows, e

def coupon_doc():
    rows, e = table()
    L = ["# Wire and winding test coupons (generated by rf2/variant_plugins/coil_winding.py; MODELED expectations)", "",
         "Status: MODELED. No coupon has been made or measured. Expected values come from the Rubadue catalog (data/datasheets/Rubadue_insulated_litz_FEP_ETFE_TCA.pdf, "
         "DATASHEET_LOG RF2-DS-WIRE: circular mils, strands, finished OD, section voltage rating) through rf2/rf2_wire_options.py, and from the plugin's geometry model. "
         "Pass limits marked ASSUMED are proposals for the owner, not vendor tolerances (the catalog says 'request specification sheet' for breakdown).", "",
         "Rule 6 (coil flyback nets: 630 V parts) is applied to the CATALOG rating. A 600 V construction that passes the coupon hipot stays BLOCKED until the owner decides; "
         "the coupon only gives the owner the measured margin.", "",
         "## 1. Litz coupons (one set per construction)", "",
         "Per construction: (a) a 1.000 m straight length, both ends stripped 10 mm, strands tinned in a solder pot (FEP does not strip in solder: strip mechanically first), "
         "4-wire Kelvin clips 900 mm apart for DC R; (b) a 2-turn loop on a printed ring at r 110 mm (stacked at the comb row pitch) for L / AC R / Q; (c) two 0.5 m pieces twisted "
         "together (twisted-pair, 12 twists per 100 mm, ASSUMED after the magnet-wire twisted-pair method) for turn-to-turn breakdown; (d) a 0.5 m piece wound 3 turns on a mandrel "
         "of 5 x OD (ASSUMED lead-exit bend) then hipot again.", "",
         "Measurements and limits:",
         "- DC R at 20 C (correct with alpha 0.00393 / K): expected rho20 x 1.02 lay / catalog area; pass within +-5 % (ASSUMED: strand diameter tolerance).",
         "- Hipot conductor to a foil wrap / water bath: 2 x 630 V = 1260 V DC for 60 s (the rule-6 basis), leakage <= 1 mA (ASSUMED); then raised in 100 V steps to 2 x catalog rating, record the first failure.",
         "- Turn-to-turn on the twisted pair: ramp 500 V/s to breakdown, 5 samples; pass if the lowest is >= 2 x the worst modelled turn-to-turn voltage of the chosen winding AND >= 920 V (2 x the 460 V flyback, both walls in series) (ASSUMED limits).",
         "- AC R and Q on the 2-turn loop at 10, 50, 100 kHz (LCR meter, series mode): expected R_ac / R_dc from the strand skin factor 1 + (r/delta)^4/48 (below); the bundle proximity effect is NOT modelled, so pass if R_ac(100 kHz) / R_dc <= 1.20 (ASSUMED) and record it.",
         "- OD with a micrometer at 10 points: within catalog nominal +-0.05 mm (ASSUMED), and <= comb slot - 0.05 mm to seat (slot 1.47 mm today; 1.60 mm in the wide-slot comb option).",
         "- Bend: after (d), no insulation crack under 10x loupe and the hipot passes again.", "",
         "| Construction | Insulation / catalog rating | Rule 6 | OD mm (fits 1.47 slot) | Cu mm2 | DC R 1 m coupon, 20 C (ohm) | 2-turn loop L uH | Q at 10 / 50 / 100 kHz | Strand AC factor 100 kHz | Coil R 26 turns (ohm) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for op in LITZ_OPTS:
        c = CAND[op["p"]["cw_litz"]]; rpm = c["R_coil_20C"] / STUDY_LEN_M
        od = c["od_mm"]; rp = ROWP0 + (od - OD0); r1, r2 = 0.110, 0.110; a_l = a_eq_m(c)
        Ll = sum(K.MU0 * r1 * (math.log(8 * r1 / a_l) - 1.75) for _ in range(2)) + 2 * K.maxwell_M(r1, r2, rp * 1e-3)
        Rl = rpm * 2 * 2 * math.pi * 0.110; rs = strand_d_mm(c["strand_awg"]) / 2 * 1e-3
        q = [2 * math.pi * f * Ll / (Rl * (1 + (rs / K.skin_depth(1.72e-8, f)) ** 4 / 48)) for f in (10e3, 50e3, 100e3)]
        L.append(f"| {op['p']['cw_litz']}{' (today)' if op['today'] else ''} | {c['kind']} {c['ins']}, {c['v_rating']:.0f} V | {'ok' if c['v_rating'] >= RULE6_V else 'BLOCKED (' + str(c['rule6_short_pct']) + ' % short)'} | "
                 f"{od} ({'yes' if od <= SLOT0 - FIT_CLEAR else 'no'}) | {c['cu_mm2']} | {rpm:.4f} (pass {rpm * 0.95:.4f}-{rpm * 1.05:.4f}) | {Ll * 1e6:.2f} | {q[0]:.1f} / {q[1]:.1f} / {q[2]:.1f} | "
                 f"{1 + (rs / K.skin_depth(1.72e-8, 100e3)) ** 4 / 48:.6f} | {c['R_coil_20C']} |")
    # winding coupons
    RC = 50.0
    L += ["", "## 2. Winding coupons (capacitance and turn-to-turn map)", "",
          "(a) **Pair-capacitance comb section** (validates the model input C_ij): a straight 300 mm printed comb section (6 combs, 0.8 mm plates at today's 57.6 mm spacing), "
          "30 straight 340 mm pieces of the litz laid in the 5 x 6 slots, ends free. Measure at 10 kHz (LCR, guarded) the capacitance of each neighbour pair (vertical, radial, diagonal) "
          "with all other pieces grounded, each outer-column piece to a grounded copper foil at the shield-coat position (1.05 mm outside the outer column centre), and each bottom-row "
          "piece to a grounded plate at z 3.2. Test it dry and again potted in the channel epoxy (the model uses eps_r 2.1, FEP only: the potted ratio gives the real eps_eff). "
          "Expected (eps 2.1, 0.300 m): " + ", ".join(
              f"vertical {K.c_parallel_wires(ROWP0 * 1e-3, CAND[TODAY_LITZ]['core_mm'] / 2e3, EPS_FEP) * 0.3e12:.1f} pF, radial {K.c_parallel_wires(PITCH0 * 1e-3, CAND[TODAY_LITZ]['core_mm'] / 2e3, EPS_FEP) * 0.3e12:.1f} pF, "
              f"diagonal x 0.5 {DIAG_W * K.c_parallel_wires(math.hypot(ROWP0, PITCH0) * 1e-3, CAND[TODAY_LITZ]['core_mm'] / 2e3, EPS_FEP) * 0.3e12:.1f} pF, "
              f"to shield foil {2 * math.pi * K.EPS0 * EPS_FEP / math.acosh((SHIELD_R - R_OUT) / (CAND[TODAY_LITZ]['core_mm'] / 2)) * 0.3e12:.1f} pF, "
              f"to the z 3.2 plate {2 * math.pi * K.EPS0 * EPS_FEP / math.acosh((ROW0 - Z_GND) / (CAND[TODAY_LITZ]['core_mm'] / 2)) * 0.3e12:.1f} pF".split("|")) +
          " (today's litz). Pass: each within +-30 % of the model dry (ASSUMED); the potted / dry ratio is recorded and fed back as eps_eff.", "",
          f"(b) **Ring coupons, one per winding pattern** (validates the voltage-map energy method): a printed full ring with today's comb cross-section (5 columns x 6 rows, "
          f"outer column at r {RC:.0f} mm) wound with 26 turns of today's litz in each pattern ({26 * 2 * math.pi * RC / 1000 * 1.0 + 0.3:.1f} m of litz per coupon), with and without ground: a grounded copper-foil band "
          "1.05 mm outside the outer column centre (the shield coat) plus a grounded plate 1.29 mm below the bottom-row centre (the z 3.2 plane). Measure L at 10 kHz and the first self-resonance f_SRF with an impedance analyser; C_self = 1 / ((2 pi f_SRF)^2 L) less the fixture C "
          "(measure the open fixture). Hipot between the coil ends and the foil at 1260 V DC. Pass: C_self within +-30 % of the model (ASSUMED) and the RANKING of the patterns as modelled.", "",
          "| Pattern | Max turn-to-turn at 460 V (26 turns) | Full coil (r 113.4): C_self pF (turn-turn + ground) | Ring coupon r 50: L uH | C_self pF with ground / without | f_SRF MHz with ground / without |",
          "|---|---|---|---|---|---|"]
    for op in WIND_OPTS:
        wid = op["id"]; full = winding_model(26, 1, TODAY_LITZ, wid)
        cf = winding_model(26, 1, TODAY_LITZ, wid, r_out=RC, ground=True); cn = winding_model(26, 1, TODAY_LITZ, wid, r_out=RC, ground=False)
        srf = lambda w: 1 / (2 * math.pi * math.sqrt(w["L"] * w["C"])) / 1e6
        L.append(f"| {wid}{' (today)' if op.get('today') else ''}: {op['desc']} | {full['V_tt_max']:.0f} V ({full['dt_max']} turns; row / column neighbours {full['V_tt_orth']:.0f} V) | {full['C'] * 1e12:.1f} ({full['C_tt'] * 1e12:.1f} + {full['C_gnd'] * 1e12:.1f}) | "
                 f"{cf['L'] * 1e6:.1f} | {cf['C'] * 1e12:.1f} / {cn['C'] * 1e12:.1f} | {srf(cf):.2f} / {srf(cn):.2f} |")
    L += ["", "## 3. Modelled effect of each option on today's machine (26 x 1, C3M, everything else today)", "",
          f"Today: first gate {e['first_gate_us']} us, boost {e['runtime_boost_h']} h, scan {e['runtime_scan_h']} h (rf2_lowL_options); node C {LO.c_node('C3M0280090J') * 1e12:.1f} pF = 368 pF + cord flex. "
          "The modelled winding C_self today is listed for comparison: the timing chain's 368 pF was derived as the capacitance OUTSIDE the winding (HANDOFF 19), "
          "so only the change dC is added to the node.", "",
          "| Axis | Option | C_self pF | L uH (change) | R_coil ohm | Max turn-turn V (row / column neighbours) | Gate us (delta) | Boost h (delta) | Scan h | Mass delta g | Depth coin / 1 g / 0.1 g cm | Rules broken |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        d = r["depth"]
        L.append(f"| {r['axis']} | {r['id']}{' (today)' if r['today'] else ''} | {r['C_self_pF']} | {r['L_uH']} ({r['dL_pct']:+.2f} %) | {r['R_ohm']} | {r['V_tt']} ({r['V_orth']}) | {r['gate']} ({r['dgate']:+.2f}) | "
                 f"{r['boost_h']} ({r['dboost']:+.2f}) | {r['scan_h']} | {r['mass']:+d} | {d['coin_25mm_silver']} / {d['gold_1g']} / {d['gold_0p1g']} | {'; '.join(r['breaks']) or '-'} |")
    L += ["", "## Assumptions and limits", "",
          "- Linear voltage along the winding at the 460 V clamp (low-frequency energy method); distributed / transmission-line effects, litz strand-to-strand capacitance and the "
          "potting epoxy's permittivity are not modelled (eps_r 2.1 everywhere: the real C is higher, roughly in proportion to eps_eff).",
          "- Diagonal neighbours count x 0.5 (screening, as rf2_taper); ground: the shield coat (r 114.45, joined to SH1) and a plane at z 3.2 (rf2_taper ASSUMPTION).",
          "- Row pitch = OD + today's 0.068 mm stacking allowance; the bottom wire sits on the floor; the outer column stays at r 113.4.",
          "- Parallel strands share current equally and sit at the same potential (rf2_lowL_options ASSUMPTION).",
          "- Resistances at 20 C as rf2_wire_options (lay factor 1.02 ASSUMED); masses from its catalog-derived g/m (enamel / bunching factor ASSUMED).",
          "- The rf2_head spec text says the coil is wound 'column by column down-and-up' (~195 V), while the slot order in rf2_lowL_options / the rf2_head builder is row by row; "
          "the variant engine's today is the row order. The 'colzz' option is the documented order."]
    open(os.path.join(ROOT, "docs", "WIRE_COUPONS.md"), "w").write("\n".join(L) + "\n")
    return rows

if __name__ == "__main__":
    rows = coupon_doc()
    for r in rows: print(r["axis"], r["id"], "C", r["C_self_pF"], "L", r["L_uH"], r["dL_pct"], "R", r["R_ohm"], "Vtt", r["V_tt"], "gate", r["gate"], r["dgate"], "boost", r["boost_h"], r["dboost"], "mass", r["mass"], r["depth"], r["breaks"])
    print("wrote docs/WIRE_COUPONS.md")
