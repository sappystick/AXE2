#!/usr/bin/env python3
"""Variant plugin: wiring and connections (cord-flex lane order, connectors, the REF3T splice). MODELED; nothing adopted, nothing excluded.

Axes (params prefixed wiring_; exactly one option per axis is today's machine, which this plugin leaves unchanged):
  cord_lanes   lane order of the cord flex (rf2_cordflex.LANES is today's). Each layout is built here from the rf2_cordflex constants (W_TX, W_PWR,
               HV_GAP, 0.3 mm LV gaps, 0.15 / 0.15 pairs, 1.35 mm guarded REF lanes); today's layout is asserted to add up to CFX.WIDTH.
               Measured from the layout: width (-> the core 'cord-flex width vs bore less 2' row on the telescope), the rule-6 gaps TX_A-TX_B and
               TX -> nearest other copper (safety rows), stack (-> rolling-loop / clock-spring rows).
               Coupling model (stated): the rf2_hex_section 2D finite-volume Laplace solver (fv_solve, validated -1.26 % on a coax) on the same
               coplanar-reference geometry it uses (strip bottom 2.0 mm over a ground plane, grounded box 10 mm clear, polyimide eps_r 3.4 ASSUMED,
               traces as 0.05 mm bands; power traces and REF guards at AC ground) gives C(TX -> REF), C(DATA -> REF) and the TX self-capacitance;
               the magnetic TX -> REF coupling is the free-space filament formula M' = mu0/2pi ln(d13 d24 / d14 d23) (rf2_hex_section.m_pair).
               The core's REF pickup (ref_crosstalk_mV, from rf2_hex_section's coplanar M) is scaled by M(option) / M(today). The TX self-capacitance
               change moves the first gate by the rf2_timing_cord sensitivity (worst_shift_us / pair_pF, linear, first order). Coupling is solved at
               today's W_TX (2.35 mm) for every coil / copper option (ratios are weakly W-dependent; the core uses a fixed M as well).
  connectors   head-gland and hinge connectors. Ratings ONLY from docs/DATASHEET_LOG_ARX.md rows whose PDF is in data/datasheets (checked at
               prepare(); a missing PDF or log text makes the option's 'datasheet on file' row fail). Masses of connectors are not in the
               datasheets: ASSUMED values, marked.
  splice       the REF3T joint of the two cord-flex pieces: soldered split (today), one-piece flex (length vs Tech Etch 40 in preferred and
               Minco 5 ft / Tech Etch 60 in advanced, rf2_flex_options), LV through a Panasonic Y5B ZIF pair with the TX strips lap-soldered,
               ACF bond (no ACF datasheet on file: rows fail as 'not shown').
Run as a script: writes docs/FLEX_COUPONS.md (cord-flex test coupons with modelled expected values and pass limits) and prints the lane table.
usage: python3 rf2/variant_plugins/wiring.py      test in the engine: python3 rf2/rf2_variants.py --plugin-test wiring"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RF2 = os.path.dirname(HERE); ROOT = os.path.dirname(RF2)
for _p in (RF2, os.path.join(RF2, "head")):
    if _p not in sys.path: sys.path.insert(0, _p)
import rf2_cordflex as CFX

OUT = os.path.join(RF2, "results"); DS = os.path.join(ROOT, "data", "datasheets")
LV_GAP, PAIR_W, REF_W, EDGE = 0.3, 0.45, 1.35, 0.75             # rf2_cordflex.LANES
GUARD_W = 0.5                                                   # extra ground-guard trace width (ASSUMED: 1/2 oz, wide enough to stitch at the ends)
L2_HATCH_OVER = 0.3                                             # layer-2 REF: hatch overhang each side of the REF group (ASSUMED)
STACK_L2 = 0.095                                                # second copper layer adds 0.095 mm (the rf2_variants assumption for tx2)
HATCH_FILL = 0.5                                                # hatched ground copper fill (ASSUMED; hatched planes per eddy rule 5)
RHO_PI_G_MM3, PI_T = 1.42e-3, 0.075                             # rf2_flex_options mass formula (polyimide 1.42 g/cm3 x 0.075 mm per mm of width)
CU_G_MM3, CU_HALF_OZ = 8.96e-3, CFX.CU_T_MM[0.5]
JOINT_OVERLAP_MM = 40.0                                         # rf2_cordflex.segments: one-piece = seg1 + seg2 - 40 (the REF3T lap)
I_PIN_VIN = CFX.I_PWR                                           # VIN_H / GND_H 0.45 A rms (rf2_cordflex / ICD I2)
V_TX, V_VIN = 463.0, 29.4                                       # ICD I2 V max (flyback clamp), pack 7S full
FLEX_CYCLES_ASSUMED = 1.0e5                                     # dynamic coupon target: 10 extensions / session x 2 / week x 52 x 10 y ~ 1e4, x 10 margin (ASSUMED)

# ---------------------------------------------------------------- connectors (ratings exactly as logged; mass ASSUMED)
CONN = {
    "JST_GH": dict(part="JST GH 1.25 mm wire-to-board", pdf="JST_GH_wire-to-board_eGH.pdf", log="current 1.0 A AC/DC (AWG #26); voltage 50 V AC/DC",
                   I_A=1.0, V=50.0, cycles=None, mass_g=0.4, mass_src="ASSUMED 0.4 g per mated 7-8 way pair (not in the eGH catalog)"),
    "Y5B": dict(part="Panasonic Y5B 0.5 mm FPC / FFC (AYF531035 10-way, AYF531235 12-way)", pdf="Panasonic_Y5B_Y5BW_ACCTB1E_2023-09.pdf",
                log="rated current 0.5 A per pin contact (holding contacts excluded); **rated voltage 50 V AC/DC**", I_A=0.5, V=50.0, cycles=20, fpc_t_mm=0.30,
                mass_g=0.15, mass_src="ASSUMED 0.15 g per connector (not in catalog ACCTB1E)"),
    "MT60": dict(part="Amass MT60 mated pair (3 contacts)", pdf="Amass_MT60_spec_V1.2.pdf", log="contact resistance 0.45 mohm, DC 500 V, 30 A rated, 60 A momentary",
                 I_A=30.0, V=500.0, cycles=1000, mass_g=5.0, mass_src="ASSUMED 5 g per mated pair incl. 12 AWG cups and pigtails (body 27.5 x 12.5 mm read; mass not in the sheet)"),
}
PIGTAIL_G = 0.6                                                 # ASSUMED: 8 x AWG26 x 60 mm pigtail from the flex lands to a JST GH housing
GAPS_NO_DATASHEET = ["Mill-Max 0906 spring pins (cartridge signal contacts): official PDF not obtained, ratings UNVERIFIED (DATASHEET_LOG)",
                     "photo-etched BeCu C172 dock fingers: custom part, Tech Etch capability only; no current / voltage / contact-resistance / cycle rating (vendor test)",
                     "ACF (anisotropic conductive film) for a flex-to-flex bond: no datasheet on file (current per bond, voltage, peel strength)",
                     "a >= 630 V, >= 4.2 A two-contact pluggable connector for the TX pair: none on file (MT60 500 V, JST GH 50 V, Y5B 50 V)"]

# ---------------------------------------------------------------- axes
AXES = [
    dict(name="cord_lanes", help="cord-flex lane order (rf2_cordflex.LANES; coupling from the rf2_hex_section 2D solver)", options=[
        dict(id="today", desc="edge | TX_A | 1.0 | TX_B | 1.0 | VIN_H GND_H | digital pairs (0.3 gaps) | 0.3 | REF X/Y/Z guarded | edge (today)", source="rf2_cordflex.LANES", today=True, p=dict(wiring_lanes="today")),
        dict(id="ref_guard", desc="today + a 0.5 mm ground guard trace (and 0.3 gap) between the DATA pair and the REF group (+0.8 mm)", source="ASSUMED guard width; rf2_hex_section solver", p=dict(wiring_lanes="ref_guard")),
        dict(id="pwr_guard", desc="digital pairs next to the HV gap, VIN_H / GND_H moved between the digital pairs and REF (AC-ground guard, same width)", source="rf2_cordflex widths; rf2_hex_section solver", p=dict(wiring_lanes="pwr_guard")),
        dict(id="hv_lv_guard", desc="a 0.5 mm ground guard trace 1.0 mm from TX_B (rule 6 to the guard), 0.3 mm to VIN_H (+0.8 mm)", source="ASSUMED guard width; rf2_hex_section solver", p=dict(wiring_lanes="hv_lv_guard")),
        dict(id="ref_layer2", desc="REF pairs on a second copper layer under a hatched ground on layer 1 (no coplanar guards; 2-layer flex, +0.095 mm stack)", source="ASSUMED stack (rf2_variants tx2 value); Minco: single layer for dynamic flexing", p=dict(wiring_lanes="ref_layer2"))]),
    dict(name="connectors", help="head-gland / hinge connectors (ICD I2, I5); ratings from DATASHEET_LOG only", options=[
        dict(id="today", desc="TX soldered everywhere; head gland CB1D JST GH 8-way + AB1A JST GH 7-way via flex-to-wire pigtails; hinge LV plies Y5B (today)", source="ICD I2 / I5; JST eGH, Panasonic ACCTB1E", today=True, p=dict(wiring_conn="today")),
        dict(id="gland_fpc", desc="cord flex plugs straight into Panasonic Y5B ZIFs on CB1D (10-way, VIN / GND on 2 pins each) and AB1A (10-way); no pigtails, TX still soldered", source="Panasonic ACCTB1E (DATASHEET_LOG)", p=dict(wiring_conn="gland_fpc")),
        dict(id="cord_mt60", desc="serviceable cord: TX pair through an Amass MT60 mated pair at the hinge cord board (unplugs without desoldering); LV as today", source="Amass MT60 V1.2 (DATASHEET_LOG)", p=dict(wiring_conn="cord_mt60"))]),
    dict(name="splice", help="REF3T joint of the two cord-flex pieces (rf2_flex_options A)", options=[
        dict(id="today", desc="split at REF3T, both pieces lap-soldered on the REF3T board (today)", source="rf2_cordflex / CORD_FLEX_SPEC", today=True, p=dict(wiring_splice="today")),
        dict(id="one_piece", desc="one-piece cord flex head -> hinge (no REF3T joint; REF3 coils land on a tab)", source="rf2_flex_options A: Tech Etch 40 / 60 in, Minco 5 ft", p=dict(wiring_splice="one_piece")),
        dict(id="zif_lv", desc="split at REF3T: LV nets through 2 x Panasonic Y5B 12-way ZIF, TX strips lap-soldered", source="Panasonic ACCTB1E", p=dict(wiring_splice="zif_lv")),
        dict(id="acf", desc="split at REF3T, pieces bonded with ACF (all nets incl. TX)", source="no ACF datasheet on file", p=dict(wiring_splice="acf"))]),
]
TODAY_P = dict(wiring_lanes="today", wiring_conn="today", wiring_splice="today")

# ---------------------------------------------------------------- lane layouts
def layout(opt, w_tx=CFX.W_TX, data="copper"):
    """-> list of (x0, x1, net, role, layer) for copper (role 'sig' / 'gnd'), total width mm. Built from the rf2_cordflex constants."""
    segs, x = [], [0.0]
    def gap(w): x[0] += w
    def cu(net, w, role, layer=1): segs.append((x[0], x[0] + w, net, role, layer)); x[0] += w
    def pair(n, layer=1): cu(n + "+", 0.15, "sig", layer); gap(0.15); cu(n + "-", 0.15, "sig", layer)
    def ref_guarded(a): cu(f"G{a}a", 0.3, "gnd"); gap(0.15); cu(f"REF{a}+", 0.15, "sig"); gap(0.15); cu(f"REF{a}-", 0.15, "sig"); gap(0.15); cu(f"G{a}b", 0.3, "gnd")
    def pwr(): cu("VIN_H", CFX.W_PWR, "gnd"); gap(LV_GAP); cu("GND_H", CFX.W_PWR, "gnd")
    def dig():
        if data != "copper": return                                                     # POF: pairs and their inner gaps removed (= the core's DIG_W 1.95 mm)
        pair("TXCMD"); gap(LV_GAP); pair("TXSTAT"); gap(LV_GAP); pair("DATA")
    gap(EDGE); cu("TX_A", w_tx, "sig"); gap(CFX.HV_GAP); cu("TX_B", w_tx, "sig"); gap(CFX.HV_GAP)
    if opt == "hv_lv_guard": cu("GUARD_HV", GUARD_W, "gnd"); gap(LV_GAP)
    if opt == "pwr_guard":
        dig(); gap(LV_GAP); pwr(); gap(LV_GAP)
    else:
        pwr(); gap(LV_GAP); dig(); gap(LV_GAP)
    if opt == "ref_guard": cu("GUARD_REF", GUARD_W, "gnd"); gap(LV_GAP)
    if opt == "ref_layer2":
        x0 = x[0]; wh = 2 * L2_HATCH_OVER + 3 * PAIR_W + 2 * LV_GAP; cu("HATCH", wh, "gnd")
        xr = [x0 + L2_HATCH_OVER]
        for a in "XYZ":
            segs.append((xr[0], xr[0] + 0.15, f"REF{a}+", "sig", 2)); segs.append((xr[0] + 0.3, xr[0] + 0.45, f"REF{a}-", "sig", 2)); xr[0] += PAIR_W + LV_GAP
    else:
        for a in "XYZ": ref_guarded(a)
    gap(EDGE)
    return segs, x[0]

def hv_gaps(segs):
    """measured rule-6 gaps on the same layer: TX_A-TX_B and TX -> nearest other copper"""
    tx = {s[2]: s for s in segs if s[2] in ("TX_A", "TX_B")}; a, b = tx["TX_A"], tx["TX_B"]
    tt = b[0] - a[1]
    others = [s for s in segs if s[2] not in ("TX_A", "TX_B") and s[4] == 1]
    lv = min(min(abs(s[0] - t[1]) if s[0] >= t[1] else abs(t[0] - s[1]) for t in (a, b)) for s in others)
    return round(tt, 3), round(lv, 3)

def solve_coupling(opt, data="copper"):
    """2D finite-volume solve (rf2_hex_section.fv_solve) of one layout on the coplanar-reference geometry; free-space filament M"""
    import rf2_hex_section as HS
    segs, W = layout(opt, CFX.W_TX, data); h = HS.H; y0 = 2.0
    two = any(s[4] == 2 for s in segs); st = 0.30 if two else HS.STRIP_T
    band = {1: (0.20, 0.25) if two else (HS.TR_V0, HS.TR_V1), 2: (HS.TR_V0, HS.TR_V1)}
    sig = [s[2] for s in segs if s[3] == "sig"]
    xs = np.arange(-int(10 / h), int((W + 10) / h) + 1) * h; ys = np.arange(0, int(12 / h) + 1) * h; X, Y = np.meshgrid(xs, ys)
    kind = np.where((Y <= 1e-9) | (Y >= ys[-1] - 1e-9) | (X <= xs[0] + 1e-9) | (X >= xs[-1] - 1e-9), -1, 0)
    xm_x, ym_x = (X[:, :-1] + X[:, 1:]) / 2, Y[:, :-1]; xm_y, ym_y = X[:-1, :], (Y[:-1, :] + Y[1:, :]) / 2
    ex = np.where((xm_x >= 0) & (xm_x <= W) & (ym_x >= y0) & (ym_x <= y0 + st), HS.EPS_PI, 1.0)
    ey = np.where((xm_y >= 0) & (xm_y <= W) & (ym_y >= y0) & (ym_y <= y0 + st), HS.EPS_PI, 1.0); cen = {}
    for a, b, net, role, layer in segs:
        v0, v1 = band[layer]
        msk = (X >= a - 1e-9) & (X <= b + 1e-9) & (Y >= y0 + v0 - h / 2) & (Y <= y0 + v1 + h / 2)
        kind[msk] = -1 if role == "gnd" else sig.index(net) + 1; cen[net] = ((a + b) / 2, y0 + (v0 + v1) / 2)
    C, _ = HS.fv_solve(kind, ex, ey, len(sig)); C = C * 1e12; ix = {n: i for i, n in enumerate(sig)}
    refs = [n for n in sig if n.startswith("REF")]; digs = [n for n in sig if n.split("+")[0].split("-")[0] in ("TXCMD", "TXSTAT", "DATA")]
    c_tx = max(-C[ix[t], ix[r]] for t in ("TX_A", "TX_B") for r in refs)
    c_da = max([0.0] + [-C[ix[d], ix[r]] for d in digs for r in refs])
    Ms = {a: HS.m_pair(cen["TX_A"], cen["TX_B"], cen[f"REF{a}+"], cen[f"REF{a}-"]) * 1e9 for a in "XYZ"}
    return dict(width_mm=round(W, 3), C_tx_ref_pF_per_m=round(float(max(c_tx, 0.0)), 5), C_data_ref_pF_per_m=round(float(c_da), 5),
                C_TXA_self_pF_per_m=round(float(C[ix["TX_A"], ix["TX_A"]]), 3), C_TXB_self_pF_per_m=round(float(C[ix["TX_B"], ix["TX_B"]]), 3),
                C_TXA_TXB_pF_per_m=round(float(-C[ix["TX_A"], ix["TX_B"]]), 3), M_tx_ref_nH_per_m=round(float(max(Ms.values(), key=abs)), 4),
                M_by_axis_nH_per_m={k: round(v, 4) for k, v in Ms.items()}, layers=2 if two else 1)

# ---------------------------------------------------------------- prepare / helpers
class _NS: pass

def prepare(ctx):
    W = _NS(); ctx.wiring = W
    W.flex = json.load(open(os.path.join(OUT, "rf2_flex_options.json")))["A_cord_to_flex"]
    tc = json.load(open(os.path.join(OUT, "rf2_timing_cord.json"))); W.gate_us_per_pF = tc["worst_shift_us"] / tc["pair_pF"]
    W.hexM = (getattr(ctx, "hex", None) or {}).get("coplanar_reference", {}).get("M_tx_ref_nH_per_m")
    log = open(os.path.join(ROOT, "docs", "DATASHEET_LOG_ARX.md")).read()
    W.conn_ok = {k: bool(os.path.exists(os.path.join(DS, c["pdf"])) and c["log"] in log) for k, c in CONN.items()}
    segs, w0 = layout("today"); W.width_check = dict(layout_today_mm=round(w0, 3), cordflex_WIDTH_mm=round(CFX.WIDTH, 3), ok=abs(w0 - CFX.WIDTH) < 1e-6)
    W.geo = {}
    for o in AXES[0]["options"]:
        for d in ("copper", "POF"):
            s, w = layout(o["p"]["wiring_lanes"], CFX.W_TX, d); tt, lv = hv_gaps(s)
            W.geo[(o["id"], d)] = dict(width_mm=w, tx_tx_mm=tt, tx_lv_mm=lv, layers=2 if any(x[4] == 2 for x in s) else 1)
    W.cpl = {}; W.cache = {}

def coupling(W, opt, data):
    k = (opt, data)
    if k not in W.cpl: W.cpl[k] = solve_coupling(opt, data)
    return W.cpl[k]

def _rule(m, name, v, lim, sense, where, kind="target"):
    m["rules"].append(dict(rule=name, value=round(float(v), 4), limit=round(float(lim), 4), sense=sense, ok=bool(v <= lim if sense == "<=" else v >= lim), where=where, kind=kind))

def _set_core_row(m, name, value, tag):
    for r in m["rules"]:
        if r["rule"] == name: r["value"] = round(float(value), 3); r["where"] = f"{r['where']} ({tag})"; return True
    return False

def _irms2(e):
    """boost TX rms^2 from the core model (P_flex_boost / R_flex); scan scaled by P_tx_scan / P_tx_boost (ASSUMED proportional)"""
    i2b = e["P_flex_boost_W"] / e["R_flex"]; return i2b, i2b * e["P_tx_scan_W"] / e["P_tx_boost_W"]

def _add_loss(ctx, P, m, dR):
    if abs(dR) < 1e-12: return
    i2b, i2s = _irms2(m["_e"]); wh = ctx.packs[P["pack"]]["Wh_usable"]
    Pb = m["P_boost_W"] + i2b * dR; Ps = wh / m["runtime_scan_h"] + i2s * dR
    m["P_boost_W"] = round(Pb, 2); m["runtime_boost_h"] = round(wh / Pb, 2); m["runtime_scan_h"] = round(wh / Ps, 2)

def _stack(P, extra=0.0): return 0.15 + (0.035 if P["oz"] == 3 else 0.0) + (0.095 if P["tx2"] else 0.0) + extra

# ---------------------------------------------------------------- evaluate
def evaluate(ctx, P, m):
    lane, conn, spl = P.get("wiring_lanes", "today"), P.get("wiring_conn", "today"), P.get("wiring_splice", "today")
    if lane == "today" and conn == "today" and spl == "today": return
    W = ctx.wiring; e = m["_e"]; tele = P["shaft"].startswith("telescope"); data = "copper" if P["data"] == "copper" else "POF"
    L_mm = m["L_tx_m"] * 1000.0; mass = 0.0; parts = 0; dR = 0.0; X = m["extra"]
    i_rms_b = math.sqrt(_irms2(e)[0]); X["wiring_I_tx_rms_boost_A"] = round(i_rms_b, 2)
    # ---- cord lanes
    if lane != "today":
        g0, g = W.geo[("today", data)], W.geo[(lane, data)]; dw = g["width_mm"] - g0["width_mm"]; where = f"cord flex lanes '{lane}' " + ("(pieces 1 and 2)" if tele else "(shaft strips + hinge clock springs)")
        _rule(m, "rule 6: TX_A-TX_B gap >= 1.0 mm", g["tx_tx_mm"], CFX.HV_GAP, ">=", where, "safety")
        _rule(m, "rule 6: TX to nearest other copper >= 1.0 mm", g["tx_lv_mm"], CFX.HV_GAP, ">=", where, "safety")
        if abs(dw) > 1e-9:
            m["flex_width_mm"] = round(m["flex_width_mm"] + dw, 2)
            if tele: _set_core_row(m, "cord-flex width vs bore less 2", m["flex_width_mm"], f"lanes {lane}")
        add_l2 = g["layers"] == 2 and not P["tx2"]
        if g["layers"] == 2:
            st = _stack(P, STACK_L2 if add_l2 else 0.0); X["wiring_stack_mm"] = round(st, 3)
            if tele: _set_core_row(m, "rolling loop: 2 x 40 x stack vs bore less 4", 2 * 40 * st, f"lanes {lane}")
            else: _set_core_row(m, "flex clock-spring bend: 40 x stack vs drum radius", 40 * st, f"lanes {lane}")
            if add_l2: _rule(m, "conductive layers in the dynamic flex vs 1 (Minco: single layer for dynamic flexing)", 2, 1, "<=",
                             "cord flex piece 1 rolling loop" if tele else "fold-hinge clock springs")
            mass += (g0["width_mm"] + dw) * STACK_L2 * L_mm * RHO_PI_G_MM3 * (1.0 if add_l2 else 0.0)
            mass += (2 * L2_HATCH_OVER + 3 * PAIR_W + 2 * LV_GAP) * CU_HALF_OZ * HATCH_FILL * L_mm * CU_G_MM3
        mass += dw * PI_T * L_mm * RHO_PI_G_MM3 + (GUARD_W * CU_HALF_OZ * L_mm * CU_G_MM3 if "guard" in lane and lane != "pwr_guard" else 0.0)
        X["wiring_flex_width_delta_mm"] = round(dw, 2)
        if tele:
            c0, c = coupling(W, "today", data), coupling(W, lane, data)
            X["ref_pickup_pF_per_m"] = c["C_tx_ref_pF_per_m"]; X["data_ref_pF_per_m"] = c["C_data_ref_pF_per_m"]; X["M_tx_ref_nH_per_m"] = c["M_tx_ref_nH_per_m"]
            X["ref_pickup_vs_today"] = round(c["C_tx_ref_pF_per_m"] / c0["C_tx_ref_pF_per_m"], 3) if c0["C_tx_ref_pF_per_m"] > 0 else None
            if m.get("ref_crosstalk_mV") is not None and c0["M_tx_ref_nH_per_m"]:
                m["ref_crosstalk_mV"] = round(m["ref_crosstalk_mV"] * abs(c["M_tx_ref_nH_per_m"] / c0["M_tx_ref_nH_per_m"]), 2)
            dC = max(c["C_TXA_self_pF_per_m"] - c0["C_TXA_self_pF_per_m"], c["C_TXB_self_pF_per_m"] - c0["C_TXB_self_pF_per_m"]) * m["L_tx_m"]
            X["wiring_tx_node_dC_pF"] = round(dC, 2)
            if m.get("first_gate_us") is not None and abs(dC) > 1e-6: m["first_gate_us"] = round(m["first_gate_us"] + W.gate_us_per_pF * dC, 2)
        else:
            X["wiring_lanes_note"] = "fold shaft: groups sit on separate inner faces (rf2_hex_section); lane-order coupling not applied"
    # ---- connectors
    if conn == "gland_fpc":
        y = CONN["Y5B"]; where = "head gland CB1D / AB1A (ICD I2)"
        _rule(m, "Y5B datasheet on file (ratings read)", int(W.conn_ok["Y5B"]), 1, ">=", where)
        _rule(m, "Y5B current per pin: VIN_H on 2 pins vs 0.5 A", I_PIN_VIN / 2, y["I_A"], "<=", where)
        _rule(m, "Y5B voltage: VIN_H vs 50 V rated", V_VIN, y["V"], "<=", where, "safety")
        mass += 2 * y["mass_g"] - 2 * CONN["JST_GH"]["mass_g"] - 2 * PIGTAIL_G; parts -= 2
        X["wiring_gland_note"] = "flex ends stiffened to the 0.30 mm applicable FPC thickness; 20 mating cycles: assembly only (gland potted)"
    elif conn == "cord_mt60":
        c = CONN["MT60"]; where = "hinge cord board, TX pair (ICD I5)"
        _rule(m, "MT60 datasheet on file (ratings read)", int(W.conn_ok["MT60"]), 1, ">=", where)
        _rule(m, "rule 6: TX contact voltage rating vs 630 V (MT60 DC 500 V)", c["V"], 630.0, ">=", where, "safety")
        _rule(m, "MT60 current: TX rms in boost vs 30 A rated", i_rms_b, c["I_A"], "<=", where)
        mass += c["mass_g"]; parts += 1; dR += 2 * 0.45e-3                                      # 2 contacts x 0.45 mohm (MT60 sheet)
    # ---- splice
    if spl == "one_piece":
        f = W.flex; one = L_mm - JOINT_OVERLAP_MM; where = "cord flex, one piece head -> hinge (no REF3T joint)"
        _rule(m, "one-piece flex length vs Tech Etch 40 in preferred", one, f["te_limit_mm"]["preferred"], "<=", where)
        _rule(m, "one-piece flex length vs Minco 5 ft / Tech Etch 60 in advanced", one, min(f["minco"]["len_max_mm"], f["te_limit_mm"]["advanced"]), "<=", where)
        X["wiring_one_piece_mm"] = round(one)
        mass -= JOINT_OVERLAP_MM * (m["flex_width_mm"] * PI_T * RHO_PI_G_MM3 + 2 * CFX.W_TX * CFX.CU_T_MM[2.0] * CU_G_MM3)
        dR -= e["R_flex"] * JOINT_OVERLAP_MM / L_mm
    elif spl == "zif_lv":
        y = CONN["Y5B"]; where = "REF3T joint (ICD I3), LV nets"
        _rule(m, "Y5B datasheet on file (ratings read)", int(W.conn_ok["Y5B"]), 1, ">=", where)
        _rule(m, "Y5B current per pin: VIN_H on 2 pins vs 0.5 A", I_PIN_VIN / 2, y["I_A"], "<=", where)
        _rule(m, "Y5B voltage: VIN_H vs 50 V rated", V_VIN, y["V"], "<=", where, "safety")
        mass += 2 * y["mass_g"]; parts += 2
        X["wiring_splice_note"] = "TX strips stay lap-soldered (Y5B 50 V: never on the TX pair); 20 mating cycles: replaces piece 1 a few times"
    elif spl == "acf":
        where = "REF3T joint (ICD I3), ACF bond"
        _rule(m, "ACF datasheet on file (current per bond, voltage, peel)", 0, 1, ">=", where)
        _rule(m, "rule 6: ACF bond on TX_A / TX_B: shown insulation rating vs 630 V (none on file)", 0.0, 630.0, ">=", where, "safety")
        X["wiring_splice_note"] = "ACF ratings not on file: every rating row fails as 'not shown'"
    if mass: m["mass_delta_g"] = int(round(m["mass_delta_g"] + mass))
    if parts: m["added_parts"] = int(m["added_parts"] + parts)
    _add_loss(ctx, P, m, dR)
    X["wiring_mass_delta_g"] = round(mass, 2)

# ---------------------------------------------------------------- coupons (docs/FLEX_COUPONS.md)
def write_coupons(path=None):
    import rf2_lowL_options as LO
    ctx = _NS(); ctx.hex = json.load(open(os.path.join(OUT, "rf2_hex_section.json"))); prepare(ctx); W = ctx.wiring
    mo, _ = LO.evaluate(26, 1, "C3M0280090J", False, False, tx2=False, flex_scale=1.0)
    i_b = math.sqrt(mo["P_flex_boost_W"] / mo["R_flex"]); f = W.flex
    rho = 0.017241                                                                         # ohm mm2 / m, copper 20 C (rf2_cordflex)
    t2 = CFX.CU_T_MM[2.0]; Lc = 0.5; R_c = rho * Lc / (CFX.W_TX * t2)
    dT = lambda i: 10.0 * (i / CFX.I_TX) ** (1 / 0.44)                                     # IPC-2221: I = k dT^0.44 A^0.725 -> dT scales as I^(1/0.44) at fixed area
    v_hipot = 2 * 630.0; cov_aged = CFX.COVER_MIL * CFX.COVER_V_PER_MIL; cov_init = CFX.COVER_MIL * 3500.0
    st = {"today 2 oz": 0.15, "3 oz TX (flex_cu)": 0.185, "2 copper layers (tx2 / ref_layer2)": 0.245}
    cp = {o["id"]: coupling(W, o["id"], "copper") for o in AXES[0]["options"]}
    c0 = cp["today"]; Lk = 0.30; f_m = 100e3
    v_m = lambda M: 2 * math.pi * f_m * M * 1e-9 * Lk * 1.0 * 1e3                          # mV for 1 A rms at 100 kHz over the coupon
    hexM = W.hexM
    L = ["# AXE2 cord flex: test coupons (generated by rf2/variant_plugins/wiring.py; MODELED expected values, no coupon built or tested)", "",
         "Coupons to order on the same panel as the cord flex (same copper, coverlay and adhesive lot), so the vendor's process is tested, not a generic material. "
         "Every expected value below is from the repo's models; every pass limit names its source. Rule 6 (>= 1.0 mm, 630 V parts) and the flex-life rows are safety-relevant: "
         "a failed coupon blocks the flex, it never relaxes the rule.", "",
         f"Inputs: W_TX {CFX.W_TX:.2f} mm at 2 oz ({t2:.4f} mm), TX gap {CFX.HV_GAP} mm, stack {CFX.STACK_MM} mm per layer, TX length {CFX.TX_LEN_M} m, loop R {CFX.R_TX_LOOP:.3f} ohm (rf2_cordflex); "
         f"TX rms in continuous boost: {CFX.I_TX} A (ICD / rf2_continuous) and {i_b:.2f} A from the rf2_lowL_options model (P_flex_boost {mo['P_flex_boost_W']} W / R_flex {mo['R_flex']} ohm); "
         f"flyback {V_TX:.0f} V peak (ICD I2).", "",
         "## C1. TX strip resistance and ampacity", "",
         f"- **Coupon:** one TX strip {CFX.W_TX:.2f} mm x {Lc*1000:.0f} mm, 2 oz, coverlaid both sides, 4-wire Kelvin lands at the ends; a second strip on the 3 oz option if that is quoted.",
         f"- **Expected:** R(20 C) = rho L / (w t) = {R_c*1e3:.1f} mohm (rho 0.017241 ohm mm2/m, nominal 2 oz = 0.0028 in, IPC-2223 nomograph thickness); the full TX loop scales to {CFX.R_TX_LOOP*1e3:.0f} mohm.",
         f"- **Pass (resistance):** {R_c*1e3*0.85:.1f}-{R_c*1e3*1.15:.1f} mohm (+-15 %: copper thickness / etch tolerance ASSUMED; the vendor's IPC-6013 class tolerance replaces it). A high value lowers runtime: the core model takes "
         f"R_flex {mo['R_flex']} ohm -> P_flex {mo['P_flex_boost_W']} W in boost.",
         f"- **Ampacity:** DC {CFX.I_TX} A, flat in still air at 25 C, thermocouple / IR at mid-length after 15 min. Expected rise 10 K (the IPC-2221 internal-trace basis of the width); "
         f"at the model's {i_b:.2f} A the same law gives {dT(i_b):.1f} K. **Pass:** rise <= 10 K at {CFX.I_TX} A and <= 20 K at {i_b:.2f} A (ASSUMED limits; acrylic adhesive rated -65..105 C, Minco).",
         f"- **Note:** the ICD's {CFX.I_TX} A and the model's {i_b:.2f} A disagree by {100*(i_b/CFX.I_TX-1):.0f} %; the coupon at {i_b:.2f} A covers both.", "",
         "## C2. Rule-6 gap hipot (TX_A - TX_B and TX - LV)", "",
         f"- **Coupon:** two interdigitated 2 oz combs, gap {CFX.HV_GAP} mm, 2 x 100 mm of facing edge, rounded ends (no sharp copper: Sierra HV notebook, a point arcs at 1/3 the voltage), coverlaid as the cord; "
         "plus the same comb with a 0.5 mm guard trace at 1.0 mm (lane option hv_lv_guard).",
         f"- **Basis:** 2 x 630 V = {v_hipot:.0f} V (the rule-6 part rating, doubled); the cord drawing also calls 1000 VRMS 60 Hz 30 s ({1000*math.sqrt(2):.0f} V peak, Minco typical withstand).",
         f"- **Expected:** field across the gap {v_hipot/CFX.HV_GAP/1000:.2f} kV/mm at {v_hipot:.0f} V DC; working field {V_TX/CFX.HV_GAP/1000:.2f} kV/mm. No breakdown expected (Minco: Kapton / acrylic 3500 V/mil through the film; the gap is a surface path under coverlay).",
         f"- **Pass:** {v_hipot:.0f} V DC 60 s and 1000 VRMS 30 s, leakage <= 1 mA (Minco test limit), no flashover; insulation resistance >= 100 MOhm at 500 V DC before and after (Minco minimum). "
         "Repeat after C4 cycling and after 85 C / 85 % RH 168 h (ASSUMED conditioning).", "",
         "## C3. Coverlay breakdown", "",
         f"- **Coupon:** 2 oz strip {CFX.W_TX:.2f} mm under 1 mil Kapton / acrylic coverlay; electrode: conductive foil or saline pad over the coverlay (the CF tube wall is the real counter-electrode).",
         f"- **Expected:** breakdown >= {cov_aged:.0f} V (1 mil x 2000 V/mil AGED, Sierra notebook) and about {cov_init:.0f} V initial (3500 V/mil, Minco); "
         f"margin over the {V_TX:.0f} V flyback {cov_aged/V_TX:.1f}x aged.",
         f"- **Pass:** no breakdown at {v_hipot:.0f} V DC 60 s; ramp-to-failure median >= {cov_aged:.0f} V on 5 samples (ASSUMED sample count). A lower result fails rule 6 for the flex against the shaft wall.", "",
         "## C4. Dynamic flex life", "",
         "- **Coupon:** full-width cord-flex section (every lane, TX strips daisy-chained with the LV traces for continuity monitoring), 300 mm long.",
         f"- **Rolling loop (piece 1):** radius 40 x stack, stroke {f['travel_mm']/2:.0f} mm (half the {f['travel_mm']:.0f} mm telescope travel), U-loop tester. "
         + "; ".join(f"{k}: R {40*v:.1f} mm" for k, v in st.items()) + "; outer-fibre strain <= stack / 2R = 1/80 = 1.25 % for every stack (by construction of the 40 x rule).",
         f"- **Fold-hinge clock spring:** drum radius {17.0:.0f} mm (rf2_variants DRUM_R), 180 deg wrap, strain <= " + ", ".join(f"{100*v/(2*17.0):.2f} % ({k})" for k, v in st.items()) + ".",
         f"- **Target:** {FLEX_CYCLES_ASSUMED:.0e} cycles (ASSUMED: about 1e4 telescope / fold cycles in 10 years x 10 margin; the cycle count is still to be agreed with the owner).",
         "- **Pass:** no open (continuous monitoring, > 1 us dropout counts), TX strip resistance change <= 10 %, then C2 hipot passes. Minco: single conductive layer for dynamic flexing; "
         "IPC >= 6 x / Minco >= 10 x thickness; the 40 x used here is ASSUMED. Two-layer stacks (tx2, ref_layer2) are outside Minco's dynamic guidance: test them, or do not adopt them.", "",
         "## C5. TX -> REF coupling (and the TX pair capacitance)", "",
         f"- **Coupon:** {Lk*1000:.0f} mm of the cord-flex lane layout over a ground plane at 2.0 mm (the solver geometry), one coupon per lane option quoted.",
         f"- **Measure:** (a) C(TX_A-TX_B) and C(TX-REF) with an LCR meter (guarded), (b) M(TX loop -> REF pair): drive 1 A rms at {f_m/1e3:.0f} kHz in the TX loop, read the REF pair open-circuit voltage V = 2 pi f M I l.",
         f"- **Expected (2D finite-volume solve, rf2_hex_section.fv_solve; free-space filament M):** TX pair {CFX.cps_c_pf_per_m():.1f} pF/m from the coplanar-strip formula (rf2_cordflex, eps_eff 1.6 ASSUMED) "
         f"-> {CFX.cps_c_pf_per_m()*Lk:.1f} pF on the coupon; rf2_hex_section's coplanar reference M {hexM} nH/m.", "",
         "| Lane option | Width mm | TX-REF pF/m | DATA-REF pF/m | C(TX_A-TX_B) pF/m (solver) | M TX->REF nH/m | REF V for 1 A, 100 kHz, 0.3 m (mV) |", "|---|---|---|---|---|---|---|"]
    for k, c in cp.items():
        L.append(f"| {k} | {c['width_mm']:.2f} | {c['C_tx_ref_pF_per_m']:.4f} | {c['C_data_ref_pF_per_m']:.4f} | {c['C_TXA_TXB_pF_per_m']:.2f} | {c['M_tx_ref_nH_per_m']:.3f} | {v_m(abs(c['M_tx_ref_nH_per_m'])):.3f} |")
    L += ["", "- Solver notes: TX-REF is the largest of TX_A and TX_B to any REF trace (rf2_hex_section reports TX_A only: 0.0177 pF/m for its layout with 0.15 mm inter-pair gaps); "
          "the solver's C(TX_A-TX_B) is the mutual term over a ground plane, not the isolated-pair formula; ref_layer2 is modelled with a 0.30 mm dielectric (both layers), which raises the TX "
          "capacitances by itself (part of its +2 pF/m is a model artifact).",
          f"- **Pass:** C(TX pair) within +-30 % of the formula (eps_eff range 1.3-2.2 gives {f['tx_capacitance'][0]['C_pF_per_m']}-{f['tx_capacitance'][2]['C_pF_per_m']} pF/m, rf2_flex_options); "
          "M and C(TX-REF) <= 1.5 x the solver value (ASSUMED; the REF pickup budget in rf2_variants scales with M). A higher C(TX pair) moves the first gate by "
          f"{W.gate_us_per_pF:.4f} us/pF (rf2_timing_cord worst shift / pair pF, linear).", "",
          "## Coupon list for the panel", "",
          "| # | Coupon | Size | Qty (ASSUMED) |", "|---|---|---|---|",
          f"| C1 | TX strip R / ampacity | {CFX.W_TX:.2f} x {Lc*1000:.0f} mm | 3 |", "| C2 | comb hipot 1.0 mm (+ guard variant) | 2 x 100 mm facing | 5 + 5 |",
          f"| C3 | coverlay breakdown | {CFX.W_TX:.2f} x 50 mm | 5 |", "| C4 | dynamic flex life (full width) | 300 mm | 3 per radius |", "| C5 | coupling (per lane option) | 300 mm | 2 |", "",
          "Gaps: no coupon or vendor data yet; coverlay / adhesive voltage rating and polyimide eps are vendor values to obtain (rf2_flex_options 'open'); cycle target to be agreed."]
    path = path or os.path.join(ROOT, "docs", "FLEX_COUPONS.md"); open(path, "w").write("\n".join(L) + "\n")
    return dict(path=path, couplings=cp, I_boost_rms=i_b)

if __name__ == "__main__":
    t0 = time.time(); r = write_coupons()
    print(r["path"], f"{time.time() - t0:.1f} s; I_tx_rms_boost {r['I_boost_rms']:.2f} A")
    for k, c in r["couplings"].items(): print(k, c)
