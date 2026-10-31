#!/usr/bin/env python3
"""Variant plugin 'boards' (2026-10-31): board placement, board stack / routing, front-end chips. MODELED; nothing adopted, nothing excluded.

Axes (option ids; * = today):
  preamp          MP1 v2 stage-1 amplifier: LMH6629* | OPA2211 | OPA1612 | INA849_G24 | INA849_G100 | OP470 | ADA4896_2 (UNVERIFIED) | LT6201 (UNVERIFIED)
  head_placement  where the front end sits: BF fins* | variant-B flat islands | BF fin + slotted etched can | head centre in a can |
                  control chassis | HV1 fin in the coil-lead plane (178 deg)
  board_stack     as built* (head boards 2 layers, QA/QB 4 layers, TXD+PWR one rigid-flex) | TXD+PWR 8-layer rigid-flex second source (FPCexpress) |
                  TXD and PWR split with an HV board-to-board connector | QA/QB copper 18 / 70 / 105 um
  + when the core axis rx == "hybrid": the second MP1-class receive channel (board area, parts, mass, its placement echo row).

Sources (every number): rf2/head/out/rf2_mp1v2_close.json (noise 2.211 nV/rtHz, worst settle 14.58 us, gate 16.43 us), rf2/head/out/rf2_mp1v2_chain.json (topology:
Rin2 100 ohm, Rf 240 / Rg 26.7, IXTY08N100D2 RDS 21 ohm max + Rsrc 22 ohm), DATASHEET_LOG rows for LMH6629 (SNOSB18I), OPA2211 (SBOS377L; IQ 3.6 mA typ per channel),
OPA1612 (SBOS450C), INA849 (SBOS945B), OP470 (ADI), rf2/results/rf2_zones.json (metal echoes and drift per K), rf2/results/rf2_flex_options.json (shield-can places),
rf2/results/rf2_layout.json (fin vs flat echo factors), rf2/results/rf2_mitigation.json (receive-board copper), rf2/head/out*/rf2_head_check.json (masses),
rf2/head/out/<B>/<b>_check.json and SB1R_RF2/sb1r_variant_check.json (routing, DRC, copper / eddy), docs/ICD.md I8 and docs/INTEGRATION_MATRIX.md (TXD+PWR stack).
Values read from a PDF in data/datasheets/ but NOT yet in DATASHEET_LOG are flagged 'PDF-only' (a gap to log): OPA1612 in 1.7 pA/rtHz, IQ 3.6 mA, GBW 40 MHz,
overload recovery 500 ns; OPA211 overload recovery 500 ns; INA849 IQ 6.2 mA.

Models (stated, MODELED):
  * Noise: quadrature substitution on the SPICE total (not a new SPICE run). N_new^2 = N_today^2 - T(LMH6629) + T(new), T = 2 legs x (en^2 + (in x R)^2) with
    R^2 = R_P^2 + R_N^2, R_P = Rin2 + Rsrc + RDS(max) = 143 ohm at +IN, R_N = Rf || Rg = 24 ohm at -IN (ASSUMED source impedances seen by the input current noise).
    An instrumentation amplifier replaces the leg pair: T = en_eff^2 + in^2 x 2 R_P^2, en_eff = hypot(en_in, en_out / G).
  * Depth: echo SNR ~ 1 / noise; the target echo falls as z^-6 in the far field (TX field z^-3 x RX coupling z^-3), so depth x (N_today / N_new)^(1/6) per target.
    (The repo's older scaling SNR^(1/5.1), PARTS_RF2, is given as a sensitivity in extra.) critic 2026-10-31: evaluate() now applies the
    engine's own mono depth model (depth_ratio(): threshold x N_new / N_today at this coil, current and gate); the 1/6 power stays in extra and
    in docs/BOARDS_COMPONENTS_MAP.md as the far-field reference. In hybrid mode the same ratio is applied to the combined depth (both
    channels use the same amplifier; the planar channel's coil Johnson noise dilutes the change, so this is an upper bound on the change there).
  * Settling: worst MP1 v2 settle 14.58 us (26-turn coil) x (gate / 16.43) (ASSUMED proportional to the coil tail) + the amplifier's overload recovery.
  * Supply: delta current x 5 V / 0.9 (the +5 V converter efficiency of rf2_continuous); parts on the TPS65131 +15 / -10 V rails: x 25 V / 0.8 (TPS65131
    efficiency 80 % ASSUMED). NOTE (finding): the core head budget still carries MP1 at 0.02 A (v1, HANDOFF section 7), not 2 x 15.5 mA LMH6629 + TPS65131.
  * Placement drift: drift for a 5 K step <= 0.5 x gate noise (rf2_system criterion). The IXTY08N100D2 TO-252 tab (rf2_zones: 1.87 x noise / K on a flat
    board) is scaled on a fin by rf2_layout's solid-plane echo factor (fin vs flat); a 3-D tab's own height is NOT modeled (HANDOFF section 26).
usage: python3 rf2/variant_plugins/boards.py   (writes docs/BOARDS_COMPONENTS_MAP.md)"""
import os, json, math, re, glob

HERE = os.path.dirname(os.path.abspath(__file__)); RF2 = os.path.dirname(HERE); ROOT = os.path.dirname(RF2)
HEAD_OUT = os.path.join(RF2, "head", "out"); RES = os.path.join(RF2, "results"); DS_DIR = os.path.join(ROOT, "data", "datasheets")
KT4 = 4 * 1.380649e-23 * 300.15
R_P, R_N = 100.0 + 22.0 + 21.0, 240.0 * 26.7 / (240.0 + 26.7)     # rf2_mp1v2_chain chosen: Rin2 100, Rsrc 22, IXTY08N100D2 RDS 21 (max); Rf 240 || Rg 26.7
V5, EFF5, V_TPS, EFF_TPS = 5.0, 0.9, 25.0, 0.8                      # +5 V rail, converter 90 % (rf2_continuous); TPS65131 +15/-10 V span; 80 % ASSUMED
DRIFT_STEP_K, DRIFT_LIMIT = 5.0, 0.5

def _J(*p):
    f = os.path.join(*p)
    try: return json.load(open(f))
    except Exception: return None

# ------------------------------------------------------------------------------------------------ preamp candidates
# en nV/rtHz, inn pA/rtHz, iq_mA (package total for the parts used), rail ("5V" or "TPS"), rec_us overload recovery, gbw_MHz, supply range, src
PREAMPS = {
    "LMH6629": dict(desc="TI LMH6629 x 2 (one per leg, gain 10, COMP high), today", en=0.69, inn=2.6, iq_mA=2 * 15.5, rail="5V", rec_us=0.002, gbw_MHz=None, bw_note="chain BW 25.1 MHz (rf2_mp1v2_chain)",
                    vs=(2.7, 5.5), cm=(-0.3, 3.8), kind="opamp", status="VERIFIED", src="DATASHEET_LOG RF2-DS-MP1V2 (TI SNOSB18I, data/datasheets/TI_LMH6629_SNOSB18I_2014-12.pdf); overload recovery <= 2 ns (rf2_opamp_qualify.json)"),
    "OPA2211": dict(desc="TI OPA2211 dual (both legs in one package), the verified fallback", en=1.1, inn=1.7, iq_mA=2 * 3.6, rail="5V", rec_us=0.5, gbw_MHz=80.0, vs=(4.5, 36.0), cm=(2.0, 3.6), kind="opamp",
                    status="VERIFIED", src="DATASHEET_LOG (TI SBOS377L: en 1.1 nV at 1 kHz, In 1.7 pA, IQ 3.6 mA/ch, GBW 80 MHz G 100, CM (V-)+2..(V+)-1.4); overload recovery 500 ns G -10: PDF-only (data/datasheets/TI_OPA211_SBOS377L.pdf)"),
    "OPA1612": dict(desc="TI OPA1612 dual audio op-amp", en=1.1, inn=1.7, iq_mA=2 * 3.6, rail="5V", rec_us=0.5, gbw_MHz=40.0, vs=(4.5, 36.0), cm=(2.0, 3.0), kind="opamp",
                    status="VERIFIED (en, supply, CM in DATASHEET_LOG); in / IQ / GBW / recovery PDF-only", src="DATASHEET_LOG (TI SBOS450C: en 1.1 nV, 4.5-36 V, CM (V-)+2..(V+)-2); PDF-only: In 1.7 pA, IQ 3.6 mA/ch, GBW 40 MHz (G +1), recovery 500 ns"),
    "INA849_G24": dict(desc="TI INA849 in-amp replacing both legs + the difference stage, G 24 (today's chain gain), on the TPS65131 rails", en=1.0, en_out=45.0, G=24.0, inn=1.1, iq_mA=6.2,
                    rail="TPS", rec_us=0.4, gbw_MHz=None, bw_min_MHz=8.0, vs=(8.0, 36.0), cm=None, kind="inamp", status="VERIFIED (DATASHEET_LOG); IQ PDF-only",
                    src="DATASHEET_LOG (TI SBOS945B: eNI 1 nV, eNO 45 nV, in 1.1 pA, BW 8 MHz at G 100, settling 0.4 us 0.01 %, supply 8-36 V); IQ 6.2 mA PDF-only; recovery: settling used as proxy (ASSUMED)"),
    "INA849_G100": dict(desc="TI INA849 at G 100 (output noise / 100; the downstream gain and ADC range must change: not modeled)", en=1.0, en_out=45.0, G=100.0, inn=1.1, iq_mA=6.2,
                    rail="TPS", rec_us=0.4, gbw_MHz=None, bw_min_MHz=8.0, vs=(8.0, 36.0), cm=None, kind="inamp", status="VERIFIED (DATASHEET_LOG); IQ PDF-only", src="as INA849_G24"),
    "OP470": dict(desc="ADI OP470 quad (two channels used) on the TPS65131 rails", en=3.2, inn=0.4, iq_mA=9.0, rail="TPS", rec_us=None, gbw_MHz=6.0, vs=(9.0, 36.0), cm=None, kind="opamp",
                    status="VERIFIED (DATASHEET_LOG); overload recovery not on file", src="DATASHEET_LOG (ADI OP470: en 3.2 nV, in 0.4 pA, GBW 6 MHz AV 10, Icc 9 mA for four, +-4.5..+-18 V)"),
    "ADA4896_2": dict(desc="ADI ADA4896-2 dual: UNVERIFIED (no datasheet on file; ADI refused fetches)", en=None, status="UNVERIFIED", src="rf2/PARTS_RF2.md (product page only); data/datasheets: none"),
    "LT6201": dict(desc="ADI/LTC LT6201 dual: UNVERIFIED (third-party copies only)", en=None, status="UNVERIFIED", src="rf2/PARTS_RF2.md (third-party copy only); data/datasheets: none"),
}
TODAY_AMP = "LMH6629"

PLACES = {
    "BF_fins": dict(desc="variant BF radial fins: MP1 v2 on HV1 at 170 deg, TXJ/TXF on HV2 at 186 deg, analog A1-A3 100/122/144 deg, digital D1-D8 (today)",
                    where="MP1 v2 front end, HV1 fin 170 deg (variant BF)", src="HANDOFF section 26, rf2/head/out_BF/rf2_head_check.json"),
    "B_flat": dict(desc="variant B flat board islands (MP1 flat at (-72, 3), TXJ (-94.5, 0), CB1D on the AB1 tier)", where="MP1 flat board (zone MP1, centre (-76, 14) z 6.4; variant B)",
                    src="HANDOFF section 25, rf2_zones.json, rf2/head/out_B/rf2_head_check.json"),
    "fin_can": dict(desc="BF fin + a slotted photo-etched shield can over the front end (EMI screen for the TPS65131 / front end)", where="front end in a slotted can on the MP1 fin (r 95 mm, az 170 deg, z 12)",
                    src="rf2_flex_options.json B_shield_can"),
    "centre_can": dict(desc="front end moved to the head centre in a slotted etched can", where="front end in a slotted can at the head centre (r 30 mm, z 12)", src="rf2_flex_options.json B_shield_can"),
    "chassis": dict(desc="front end moved into the control chassis (~0.9 m up the shaft), receiving the coil over the cord-flex TX strips; closed shield can allowed there",
                    where="front end in the control chassis (s ~0.9 m, behind the heel)", src="rf2_flex_options.json B_shield_can (chassis place), rf2_cordflex R_TX_LOOP"),
    "hv1_lead_plane": dict(desc="HV1 fin moved into the coil-lead plane (178 deg) instead of 8 deg away", where="MP1 v2 front end, HV fin in the lead plane (178 deg)", src="rf2_layout.json HV 178 deg cases, rf2_zonerules spec_BF"),
}
TODAY_PLACE = "BF_fins"

STACKS = {
    "as_built": dict(desc="head boards 2 layers (MP1, TXJ, TXF, LR1, SH1), QA/QB 4 layers 35 um, TXD + PWR one rigid-flex (ICD I8, no HV connector) (today)", src="kicad_pcb layer tables, docs/ICD.md I8"),
    "txdpwr_8L_fpcx": dict(desc="TXD + PWR as an FPCexpress 8-layer rigid-flex (second source; PTH through rigid and flex)", src="docs/INTEGRATION_MATRIX.md, DATASHEET_LOG FPCexpress"),
    "txdpwr_split": dict(desc="TXD and PWR as two rigid boards joined by a board-to-board connector carrying HV_CLAMP (463 V)", src="docs/ICD.md I8 (the alternative the rigid-flex removes)"),
    "rx_18um": dict(desc="QA/QB receive boards in 18 um copper (flex receive boards, option C)", cu_um=18, src="rf2_mitigation.json receive_copper"),
    "rx_70um": dict(desc="QA/QB receive boards in 70 um copper", cu_um=70, src="rf2_mitigation.json receive_copper"),
    "rx_105um": dict(desc="QA/QB receive boards in 105 um copper", cu_um=105, src="rf2_mitigation.json receive_copper"),
}
TODAY_STACK = "as_built"

def _opt(d, key, today, pkey):
    return [dict(id=k, desc=v["desc"], source=v["src"], today=(k == today), p={pkey: k}) for k, v in d.items()]
AXES = [
    dict(name="preamp", help="MP1 v2 stage-1 amplifier (noise -> depth, recovery -> first gate, supply -> runtime)", options=_opt(PREAMPS, "preamp", TODAY_AMP, "bd_preamp")),
    dict(name="head_placement", help="where the front end (and a second receive channel) sits; echo drift vs 0.5 x gate noise at that location", options=_opt(PLACES, "place", TODAY_PLACE, "bd_place")),
    dict(name="board_stack", help="board layer stack / rigid-flex / receive-board copper; routing and DRC status as extras", options=_opt(STACKS, "stack", TODAY_STACK, "bd_stack")),
]

# ------------------------------------------------------------------------------------------------ models
def noise_nV(a, n0):
    """quadrature substitution on the SPICE total n0 (see module docstring)"""
    t = lambda en, inn: 2 * (en ** 2 + (inn * 1e-3) ** 2 * (R_P ** 2 + R_N ** 2))
    L = PREAMPS[TODAY_AMP]; rest = n0 ** 2 - t(L["en"], L["inn"])
    if a["kind"] == "inamp":
        en_eff = math.hypot(a["en"], a["en_out"] / a["G"]); new = en_eff ** 2 + (a["inn"] * 1e-3) ** 2 * 2 * R_P ** 2
    else:
        new = t(a["en"], a["inn"])
    return math.sqrt(rest + new), math.sqrt(max(rest, 0.0))

def depth_ratio(S, P, e, n_new, n_ref):
    """critic 2026-10-31: per-target depth ratio from the engine's own mono depth model (rf2_lowL_options.echo_mono / depth) with the detection
    threshold scaled by n_new / n_ref, at this combination's coil, scan current and mono first gate. The z^-6 far-field 1/6 power under-stated the
    change (the model's local exponent is 0.17 coin, 0.19 gold 1 g, 0.26-0.28 gold 0.1 g: the small targets sit in the coil's near field)."""
    import rf2_lowL_options as LO
    gate = e.get("gate_mono") or e.get("gate"); I = e.get("I_scan")
    if not gate or not I or n_new <= 0 or n_ref <= 0: return None
    k = (P["N"], P["p"], round(I, 4), round(gate, 4), round(n_new, 5), round(n_ref, 5)); C = S.setdefault("dcache", {})
    if k not in C:
        c = S.setdefault("coils", {}).get((P["N"], P["p"])) or S["coils"].setdefault((P["N"], P["p"]), LO.coil(P["N"], P["p"]))
        vth = LO.SNR * n_ref * 1e-9 * math.sqrt(LO.BW) / math.sqrt(LO.NAVG); out = {}
        for kk, tg in LO.TARGETS.items():
            f = lambda z, tg=tg: LO.echo_mono(c["b"](z), I, gate * 1e-6, tg)
            d0 = LO.depth(f, vth); d1 = LO.depth(f, vth * n_new / n_ref); out[kk] = d1 / d0 if d0 > 0 else (n_ref / n_new) ** (1 / 6)
        C[k] = out
    return C[k]

def amp_power_W(a):
    return a["iq_mA"] * 1e-3 * (V5 / EFF5 if a["rail"] == "5V" else V_TPS / EFF_TPS)

def prepare(ctx):
    S = {}
    try:
        import rf2_lowL_options as LO; n0 = LO.NOISE_nV; gate0 = LO.FIRST_GATE0
    except Exception:
        n0, gate0 = 2.211, 16.43
    mc = _J(HEAD_OUT, "rf2_mp1v2_close.json") or {}
    settle0 = (mc.get("parts_closure") or {}).get("worst_settle_us", 14.58); gate_mc = mc.get("first_gate_us", gate0)
    S.update(n0=n0, gate0=gate_mc, settle0=settle0)
    P0 = amp_power_W(PREAMPS[TODAY_AMP])
    amps = {}
    for k, a in PREAMPS.items():
        if a.get("en") is None: amps[k] = dict(unverified=True); continue
        n, floor = noise_nV(a, n0)
        bw = (a["gbw_MHz"] / 10.0) if a.get("gbw_MHz") else a.get("bw_min_MHz", 25.1)
        rail_v = V5 if a["rail"] == "5V" else V_TPS
        cm_head = None
        if a.get("cm"): cm_head = round(min(2.5 - a["cm"][0], a["cm"][1] - 2.5), 3)
        amps[k] = dict(noise=round(n, 3), floor=round(floor, 3), ratio6=(n0 / n) ** (1 / 6), ratio51=(n0 / n) ** (1 / 5.1), dP_W=amp_power_W(a) - P0,
                       bw_MHz=bw, rail_v=rail_v, cm_head=cm_head, rec=a.get("rec_us"))
    S["amps"] = amps
    # ---- placement drift rows (x gate noise for a 5 K step)
    zo = _J(RES, "rf2_zones.json") or {}; fo = _J(RES, "rf2_flex_options.json") or {}; la = _J(RES, "rf2_layout.json") or {}
    tab = next((e for e in zo.get("echoes", []) if e["object"].startswith("IXTY08N100D2")), None)
    tab_drift_flat = tab["drift_x_noise_per_K"] * DRIFT_STEP_K if tab else None                  # 1.87 / K x 5 K on a flat board
    fac = {(c["zone"], c["case"]): c["solid_plane_echo_vs_flat"] for c in la.get("cases", [])}
    f_hv_lead = fac.get(("HV (next to the coil leads)", "radial fin, exact"))                     # 0.00252 (fin in the lead plane)
    f_an_tilt = fac.get(("analog", "radial fin, 1 deg tilt about its radial axis"))               # 2.94e-4 (rails hold < 1 deg)
    cans = {k: v for k, v in (fo.get("B_shield_can") or {}).get("places", {}).items()}
    can = lambda key: next((v for k, v in cans.items() if k.startswith(key)), None)
    c_fin, c_cen, c_ch = can("front end near the rim"), can("head centre"), can("control chassis")
    mp1_hatch = next((e for e in zo.get("echoes", []) if e["object"].startswith("MP1 (mono preamp): hatched 1.0")), None)
    S["tab_drift_flat"], S["f_hv_lead"], S["f_an_tilt"] = tab_drift_flat, f_hv_lead, f_an_tilt
    pl = {}
    if tab_drift_flat is not None:
        pl["B_flat"] = [("front-end metal (IXTY08N100D2 TO-252 tab, flat board): echo drift (5 K) vs 0.5 x gate noise", tab_drift_flat, "rf2_zones.json")]
    if c_fin: pl["fin_can"] = [("slotted etched shield can: echo drift (5 K) vs 0.5 x gate noise", c_fin["slotted"]["drift5K_x_noise"], "rf2_flex_options.json")]
    if c_cen: pl["centre_can"] = [("slotted etched shield can: echo drift (5 K) vs 0.5 x gate noise", c_cen["slotted"]["drift5K_x_noise"], "rf2_flex_options.json")]
    if c_ch: pl["chassis"] = [("closed shield can in the chassis: echo drift (5 K) vs 0.5 x gate noise", c_ch["closed_can"]["drift5K_x_noise"], "rf2_flex_options.json")]
    if tab_drift_flat is not None and f_hv_lead is not None:
        pl["hv1_lead_plane"] = [("front-end metal (IXTY tab on a fin in the lead plane, flat drift x fin factor 0.00252; 3-D tab height not modeled): echo drift (5 K) vs 0.5 x gate noise",
                                 tab_drift_flat * f_hv_lead, "rf2_zones.json x rf2_layout.json")]
    S["place_rows"] = pl
    # second receive channel (hybrid): its board shares the front end's place; on the BF fins it goes on an analog fin (122 deg)
    sc = {}
    if tab_drift_flat is not None:
        sc["BF_fins"] = ("analog fin A2 (122 deg), second MP1-class channel", tab_drift_flat * (f_an_tilt or 0.0), "IXTY tab (MP1-class copy, ASSUMED) x analog fin 1 deg tilt factor")
        sc["B_flat"] = ("flat board next to MP1 (variant B), second MP1-class channel", tab_drift_flat, "IXTY tab on a flat board")
        sc["hv1_lead_plane"] = sc["BF_fins"]
    if c_fin: sc["fin_can"] = ("slotted can on the MP1 fin, second channel inside", c_fin["slotted"]["drift5K_x_noise"], "shield can")
    if c_cen: sc["centre_can"] = ("slotted can at the head centre, second channel inside", c_cen["slotted"]["drift5K_x_noise"], "shield can")
    if c_ch: sc["chassis"] = ("control chassis, second channel in the closed can", c_ch["closed_can"]["drift5K_x_noise"], "shield can")
    S["second_rows"] = sc
    S["mp1_hatch_drift5K"] = mp1_hatch["drift_x_noise_per_K"] * DRIFT_STEP_K if mp1_hatch else None
    # masses (head-check islands-only totals) and areas
    mB, mBF = [(_J(RF2, "head", d, "rf2_head_check.json") or {}).get("checks", {}).get("mass_g", {}).get("total_islands_only") for d in ("out_B", "out_BF")]
    S["dm_B_vs_BF"] = (mB - mBF) if (mB and mBF) else None
    try:
        import rf2_cordflex as CFX; S["R_tx_loop"] = CFX.R_TX_LOOP; S["TX_LEN_M"] = CFX.TX_LEN_M
    except Exception:
        S["R_tx_loop"], S["TX_LEN_M"] = None, 1.355
    mi = _J(RES, "rf2_mitigation.json") or {}; S["rx_cu"] = {r["copper_um"]: r for r in mi.get("receive_copper", [])}
    S["routing"] = board_status()
    S["cache"] = {}
    ctx.boards = S

# ------------------------------------------------------------------------------------------------ evaluate
def _rule(m, name, v, lim, sense, where, kind="target"):
    ok = (v <= lim) if sense == "<=" else (v >= lim)
    m["rules"].append(dict(rule=name, value=round(float(v), 6), limit=round(float(lim), 6), sense=sense, ok=bool(ok), where=where, kind=kind))

def evaluate(ctx, P, m):
    S = ctx.boards; amp, place, stack = P.get("bd_preamp", TODAY_AMP), P.get("bd_place", TODAY_PLACE), P.get("bd_stack", TODAY_STACK)
    hybrid = P.get("rx") == "hybrid"
    if amp == TODAY_AMP and place == TODAY_PLACE and stack == TODAY_STACK and not hybrid:
        return                                                                      # today's machine: m unchanged
    where_fe = PLACES[place]["where"]; e = m.get("_e", {}); ch = 2 if hybrid else 1
    # ---------------- preamp
    if amp != TODAY_AMP:
        A = S["amps"][amp]; a = PREAMPS[amp]
        if A.get("unverified"):
            _rule(m, f"preamp {amp}: datasheet on file in data/datasheets (UNVERIFIED part; effects not modeled)", 0, 1, ">=", where_fe)
            m["extra"]["bd_preamp_status"] = "UNVERIFIED: no datasheet on file, no numbers used"
        else:
            dr = depth_ratio(S, P, e, A["noise"], S["n0"]) or {k: A["ratio6"] for k in m["depth_cm"]}     # critic 2026-10-31: engine depth model, not the 1/6 power
            m["depth_cm"] = {k: round(v * dr.get(k, A["ratio6"]), 1) for k, v in m["depth_cm"].items()}
            dP = A["dP_W"] * ch
            wh = ctx.packs[P["pack"]]["Wh_usable"] if hasattr(ctx, "packs") and P.get("pack") in getattr(ctx, "packs", {}) else m["runtime_boost_h"] * m["P_boost_W"]
            Pb = m["P_boost_W"] + dP; Ps = wh / m["runtime_scan_h"] + dP
            m["P_boost_W"] = round(Pb, 2); m["runtime_boost_h"] = round(wh / Pb, 2); m["runtime_scan_h"] = round(wh / Ps, 2)
            # critic 2026-10-31: the absolute 1.7 nV/rtHz row was added for alternative amplifiers only, while today's LMH6629 (2.211) fails it too and
            # no option can meet it (resistor / FET / second-stage floor 1.911 nV/rtHz without any amplifier). It excluded every alternative from the
            # no-break set for a target the whole machine fails. The target stays reported once for the machine (rf2_rules mp1.noise, FAIL); the
            # option's value against it is kept here as an extra, and its depth effect is in depth_cm.
            m["extra"]["bd_noise_vs_1p7_target_pct"] = round(100 * (A["noise"] / 1.7 - 1), 1)
            gate_mono = e.get("gate_mono") or m["first_gate_us"]
            if A["rec"] is not None:
                settle = S["settle0"] * gate_mono / S["gate0"] + A["rec"]
                _rule(m, "MP1 worst settle (scaled to the coil tail) + amplifier overload recovery vs the first gate", settle, gate_mono, "<=", where_fe)
                if settle > gate_mono and not hybrid:
                    m["first_gate_us"] = round(settle, 2); m["extra"]["bd_gate_pushed_by_amp"] = "first gate moved to the amplifier settle; depth NOT re-evaluated for the later gate"
            else:
                _rule(m, f"{amp}: overload recovery on file (needed for the settle vs first-gate check)", 0, 1, ">=", where_fe)
            _rule(m, f"{amp}: stage-1 closed-loop bandwidth (GBW / 10, or the in-amp BW at G <= 100) vs the depth model's 1 MHz noise bandwidth", A["bw_MHz"], 1.0, ">=", where_fe)
            _rule(m, f"{amp}: rail ({A['rail_v']:g} V) vs the part's minimum supply", A["rail_v"], a["vs"][0], ">=", where_fe, "safety")
            _rule(m, f"{amp}: rail ({A['rail_v']:g} V) vs the part's maximum supply", A["rail_v"], a["vs"][1], "<=", where_fe, "safety")
            if A["cm_head"] is not None:
                _rule(m, f"{amp}: input common-mode headroom at VBIAS 2.5 V on 5 V", A["cm_head"], 0.0, ">=", where_fe)
            if a["rail"] == "TPS":
                m["extra"]["bd_amp_on_tps65131"] = "runs from the TPS65131 +15 / -10 V rails: its load share, output level shift to the 5 V ADC and input CM range are NOT modeled"
            m["extra"].update(bd_noise_nV=A["noise"], bd_noise_floor_without_amp_nV=A["floor"], bd_depth_scale_1_6=round(A["ratio6"], 4), bd_depth_scale_model={k: round(v, 4) for k, v in dr.items()}, bd_depth_scale_alt_1_5p1=round(A["ratio51"], 4),
                              bd_amp_dP_W=round(dP, 3), bd_amp_status=a["status"])
    # ---------------- placement
    if place != TODAY_PLACE:
        for name, v, src in S["place_rows"].get(place, []):
            _rule(m, name, v, DRIFT_LIMIT, "<=", where_fe)
        if place == "B_flat" and S["dm_B_vs_BF"] is not None:
            m["mass_delta_g"] = int(round(m["mass_delta_g"] + S["dm_B_vs_BF"]))
            m["extra"]["bd_B_flat_board_area"] = "flat islands AB1A+AB1B 25 cm2, CB1D 48, MP1+TXJ 11.3 (BF fins: 32 / 85 / 16 cm2; HANDOFF section 26)"
        if place == "hv1_lead_plane":
            _rule(m, "HV fin separation from the coil-lead path vs the 4 deg spec limit", 0.0, 4.0, ">=", where_fe)
            m["extra"]["bd_lead_plane_B_mT"] = 4.4994
        if place == "chassis":
            R = (S["R_tx_loop"] or 0.0) * m.get("L_tx_m", S["TX_LEN_M"]) / S["TX_LEN_M"] * (2.0 / P.get("oz", 2))
            jn = math.sqrt(KT4 * R) * 1e9; base = S["amps"].get(amp, {}).get("noise") or S["n0"]
            nn = math.hypot(base, jn); r6 = (base / nn) ** (1 / 6)
            dr = depth_ratio(S, P, e, nn, base) or {k: r6 for k in m["depth_cm"]}                           # critic 2026-10-31: engine depth model, not the 1/6 power
            m["depth_cm"] = {k: round(v * dr.get(k, r6), 1) for k, v in m["depth_cm"].items()}
            m["extra"].update(bd_noise_with_cord_strips_nV=round(nn, 3),bd_cord_strip_R_ohm=round(R, 3), bd_cord_strip_johnson_nV=round(jn, 3),
                              bd_chassis_not_modeled="pickup on the 1.36 m unscreened receive path (the TX strips), flyback common-mode at the chassis, REF crosstalk into the receive signal")
        if place in ("fin_can", "centre_can"):
            m["extra"]["bd_can_note"] = "can 12 x 12 x 3 mm, 0.254 mm (Tech Etch); EMI benefit not quantified; mass not counted"
    # ---------------- stack
    if stack != TODAY_STACK:
        rt = S["routing"]
        m["extra"]["bd_routed_head_boards"] = ", ".join(f"{b['board']} {b['layers']}L open {b['unconnected']} DRC {b['drc_errors']}" for b in rt if b.get("layers"))
        if stack == "txdpwr_8L_fpcx":
            m["extra"]["bd_stack_note"] = "same function as today's rigid-flex; second source only (FPCexpress to 8 layers); TXD/PWR boards not yet designed (no numbers)"
        elif stack == "txdpwr_split":
            m["added_parts"] = int(m["added_parts"] + 1)
            _rule(m, "TXD-PWR HV_CLAMP (463 V) board-to-board connector: part with a >= 630 V rating on file (rule 6)", 0.0, 630.0, ">=", "control chassis, TXD-PWR joint", "safety")
            m["extra"]["bd_stack_note"] = "connector mass / part not on file"
        elif stack.startswith("rx_"):
            cu = STACKS[stack]["cu_um"]; r = S["rx_cu"].get(cu)
            if r:
                m["extra"]["bd_bearing_channel_depth_pct"] = r["depth_change_pct_vs_35um"]; m["extra"]["bd_qa_qb_R_ohm"] = r["R_ohm"]
            dm = 2 * 16900 * 0.8 * (cu - 35) * 1e-3 * 8.96 / 1000.0                      # QA + QB, 16.9 m x 0.8 mm traces (rf2_head_check), Cu 8.96 g/cm3
            m["mass_delta_g"] = int(round(m["mass_delta_g"] + dm)); m["extra"]["bd_qa_qb_copper_dm_g"] = round(dm, 1)
            if cu == 18: m["extra"]["bd_stack_note"] = "flex receive boards: FR4 -> polyimide mass change not on file (copper only counted)"
    # ---------------- second receive channel (core rx = hybrid)
    if hybrid:
        row = S["second_rows"].get(place)
        if row:
            _rule(m, f"second receive channel metal ({row[2]}): echo drift (5 K) vs 0.5 x gate noise", row[1], DRIFT_LIMIT, "<=", row[0])
        m["mass_delta_g"] = int(round(m["mass_delta_g"] + 8))                         # MP1 island 8 g ASSUMED (rf2_head_check electronics islands)
        m["extra"].update(bd_rx2_board="second MP1-class board: 26 x 36 mm = 9.4 cm2 as MP1 v1 (or an 8.0 cm2 HV-class fin, HANDOFF 26); 24 parts (MP1 v1 netlist; the v2 BOM is not built); 8 g ASSUMED; power 0.35 W already in rf2_lowL hybrid")

# ------------------------------------------------------------------------------------------------ board status / map doc
CHIPS = {   # chip -> (boards, aliases to find the datasheet file / log row)
    "OPA2211": ("MP1 v1 (built)", ["OPA211", "OPA2211"]), "BAV199": ("MP1 v1, MP1 v2", ["BAV199"]), "SK9822-EC20": ("LR1", ["SK9822"]),
    "LMH6629": ("MP1 v2 (SPICE, not built)", ["LMH6629"]), "IXTY08N100D2": ("MP1 v2 (SPICE, not built)", ["IXTY08N100D2", "08N100D2"]),
    "TMUX7212": ("MP1 v2 (SPICE, not built)", ["TMUX7212", "TMUX721"]), "TPS65131": ("MP1 v2 (SPICE, not built)", ["TPS6513"]),
    "BAT54": ("MP1 v2 (SPICE, not built)", ["BAT54"]), "INA849": ("candidate QA/QB/REF3 inputs", ["INA849"]),
    "C3M0280090J": ("TXD (chassis, not built)", ["C3M0280090J", "C3M0280090"]), "NTBG080N120SC1": ("TXD option", ["NTBG080N120SC1", "NTBG080"]),
    "LMR36015": ("CB1D (+5 V, Phase C)", ["LMR36015", "LMR3601"]), "LMR36520": ("+5V_LED buck for the display", ["LMR36520"]), "TLV755P": ("CB1D / AB1 LDO (Phase C)", ["TLV755", "TLV755P"]),
    "ADA4896-2": ("MP1 candidate", ["ADA4896"]), "LT6201": ("MP1 candidate", ["LT6201", "LT6200"]),
}
def ds_status(aliases):
    files = []
    for d in (DS_DIR, os.path.join(ROOT, "data", "seed", "datasheets")):
        if os.path.isdir(d): files += [f for f in os.listdir(d) if any(a.lower() in f.lower() for a in aliases)]
    try: log = open(os.path.join(ROOT, "docs", "DATASHEET_LOG_ARX.md")).read()
    except Exception: log = ""
    logged = any(a in log for a in aliases)
    return files, logged

def _layers(pcb):
    try:
        t = open(pcb).read(200000); i = t.find("(layers"); return len(re.findall(r'\(\d+ "[^"]*\.Cu" (?:signal|power|mixed|jumper)', t[i:i + 4000]))
    except Exception: return None

def board_status():
    out = []
    for b in ("MP1", "TXJ", "TXF", "LR1"):
        c = _J(HEAD_OUT, b, f"{b.lower()}_check.json")
        if not c: out.append(dict(board=b, missing=True)); continue
        out.append(dict(board=b, layers=_layers(os.path.join(HEAD_OUT, b, f"PF233-RF2-{b}.kicad_pcb")), unconnected=c["route"]["unconnected_after"], tracks=c["route"]["tracks"], vias=c["route"]["vias"],
                        mode=c["route"]["mode"], strategies="; ".join(f"{s['name']} (open {s['open']}, DRC {s['drc_errors']})" for s in c["route"]["strategies"]),
                        drc_errors=c["kicad_drc"]["errors"], drc_unconnected=c["kicad_drc"]["unconnected"], hv_min=c["copper"]["min_hv_clearance_mm"], clr_min=c["copper"]["min_clearance_mm"],
                        loops=len(c["copper"]["loops_around_axis"]), parity=c["parity"]["ok"], fin_deg=next((p.get("fin_deg") for p in c.get("placement_in_head", []) if p.get("fin_deg") is not None), None),
                        place=(lambda P: (round(sum(p["x"] for p in P) / len(P), 1), round(sum(p["y"] for p in P) / len(P), 1), P[0]["z"]) if P else None)(c.get("placement_in_head", [])), ok=c["ok"]))
    s = _J(HEAD_OUT, "SH1", "sh1_check.json")
    if s: out.append(dict(board="SH1", layers=_layers(os.path.join(HEAD_OUT, "SH1", "PF233-RF2-SH1.kicad_pcb")), unconnected=s["kicad_unconnected"], drc_errors=s["kicad_drc_errors"], drc_unconnected=s["kicad_unconnected"],
                          mode="generated (rf2_shield_pcb.py)", strategies="-", hv_min=None, clr_min=None, loops=0 if s["topology"]["loop_free"] else 1, parity=None, fin_deg=None, place=(0.0, 0.0, None),
                          eddy_tau_us=s["topology"]["eddy_tau_us"], ok=s.get("ok", True)))
    q = _J(HEAD_OUT, "SB1R_RF2", "sb1r_variant_check.json")
    if q:
        for b in ("QA", "QB"):
            k = q["kicad_drc"]["boards"].get(f"SB1R-{b}", {})
            out.append(dict(board=f"SB1R-{b}", layers=_layers(os.path.join(HEAD_OUT, "SB1R_RF2", f"SB1R-{b}-RF2.kicad_pcb")), unconnected=k.get("unconnected"), drc_errors=len(k.get("errors", {})),
                            drc_unconnected=k.get("unconnected"), mode="baseline SB1R copper, outline r 114 mm (rf2_sb1r_variant)", strategies="-", hv_min=None, clr_min=None, loops=None, parity=q["copper_identical"]["ok"],
                            fin_deg=None, place=(0.0, 0.0, None), ok=q["ok"]))
    return out

def write_map():
    S = type("C", (), {})(); prepare(S); B = S.boards
    zr = _J(HEAD_OUT, "rf2_zonerules.json") or {}; zc = zr.get("checks", {}).get("copper", {}); zo = _J(RES, "rf2_zones.json") or {}
    echo = {}
    for e in zo.get("echoes", []):
        if "hatched 1.0" in e["object"]: echo[e["where"].split(" ")[0]] = e
    L = ["# Boards and components map (generated by rf2/variant_plugins/boards.py; MODELED / tool-checked)", "",
         "No fabricator DRC, no CAM review, no bench test. Sources: rf2/head/out/<B>/<b>_check.json, SB1R_RF2/sb1r_variant_check.json, the .kicad_pcb layer tables, "
         "rf2/head/out/rf2_zonerules.json, rf2/results/rf2_zones.json, rf2/head/rf2_netlist.py, data/datasheets/ and docs/DATASHEET_LOG_ARX.md.", "",
         "## Built boards (routed copper on file)", "",
         "| Board | Layers | Routed (open) | Route mode / strategies | KiCad DRC errors / unconnected | Min clearance / HV clearance (mm) | Eddy loops around axis (rule 5) | Zone-rule copper | Parity | Placement in head |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for b in B["routing"]:
        if b.get("missing"): L.append(f"| {b['board']} | - | check JSON missing | | | | | | | |"); continue
        z = zc.get(b["board"]); zs = ("ok, loops over 0.1 cm2: none" if z and z.get("ok") else ("FAIL" if z else "not checked (reported only)" if b["board"] == "LR1" else "-"))
        hv = f"{b['clr_min']} / {b['hv_min'] if b['hv_min'] is not None else 'no HV nets'}" if b.get("clr_min") is not None else "-"
        if b["board"] == "MP1": hv += " (rule 6 >= 1.0)"
        if b["board"] in ("TXJ", "TXF"): hv += " (rule 6 >= 1.0)"
        pl = b.get("place"); pls = (f"fin at {b['fin_deg']} deg" if b.get("fin_deg") is not None else (f"centroid ({pl[0]}, {pl[1]}) z {pl[2]}" if pl and pl[2] is not None else "axis-centred disc"))
        loops = ("0" if b.get("loops") == 0 else (str(b.get("loops")) if b.get("loops") is not None else "- (baseline copper)"))
        if b.get("eddy_tau_us") is not None: loops += f"; split rings, eddy tau {b['eddy_tau_us']} us"
        L.append(f"| {b['board']} | {b.get('layers')} | {'yes' if b.get('unconnected') == 0 else 'NO'} ({b.get('unconnected')}) | {b.get('mode')}; {b.get('strategies')} | {b.get('drc_errors')} / {b.get('drc_unconnected')} | {hv} | {loops} | {zs} | {b.get('parity')} | {pls} |")
    L += ["", "Notes: MP1 on file is **MP1 v1** (OPA2211 + 3 x 470 ohm CRCW2512 per leg, 26 x 36 mm); MP1 v2 (LMH6629 / IXTY08N100D2 / TMUX7212 / TPS65131 / BAT54 / BAV199) "
          "is closed in SPICE only (rf2_mp1v2_close.json) and waits for its fin board (HV1, 170 deg). TXF is TXJ's function as the first fin board (186 deg). "
          "LR1 copper is reported only by the zone rules (display flex). TXD, PWR, HB2-M / HB2-G (chassis) and the RF2 rework of AB1A / AB1B / CB1D (Phase C) have no board yet.", "",
          "## Echo / drift at each board's zone (rf2_zones.json, slit-hatched plane: the rule-5 design)", "", "| Zone | Echo at the first gate (x gate noise) | Drift (x noise / K) | Worst metal there |", "|---|---|---|---|"]
    worst = {"MP1": "IXTY08N100D2 TO-252 tab: 2710 x noise, 1.87 / K flat (stand it edge-on / fin)", "TXJ": "-", "CB1D": "no solid planes, no cans (zone rules)", "AB1A": "electrolytic can banned (MLCC only)", "AB1B": "as AB1A"}
    for k, e in echo.items():
        L.append(f"| {e['where']} | {e['x_gate_noise']:.3g} | {e['drift_x_noise_per_K']:.3g} | {worst.get(k, '-')} |")
    L += ["", "## Key chips and datasheet-on-file status", "", "| Chip | Where | Datasheet in data/datasheets (or seed) | In DATASHEET_LOG |", "|---|---|---|---|"]
    gaps = []
    for chip, (where, al) in CHIPS.items():
        f, lg = ds_status(al)
        if not f: gaps.append(chip)
        L.append(f"| {chip} | {where} | {', '.join(sorted(set(f))[:3]) or '**none (gap)**'} | {'yes' if lg else 'no'} |")
    L += ["", f"Gaps (no datasheet file found): {', '.join(gaps) or 'none'}.", "",
          "## Front-end amplifier options (variant axis `preamp`)", "",
          f"Noise by quadrature substitution on the SPICE total {B['n0']} nV/rtHz (R_P {R_P:.0f} ohm, R_N {R_N:.1f} ohm ASSUMED); depth x (N_today / N_new)^(1/6). "
          f"Resistor / FET / second-stage floor without any amplifier: {B['amps'][TODAY_AMP]['floor']} nV/rtHz, already above the 1.7 nV target.", "",
          "| Option | Status | Noise nV/rtHz | Depth scale | Amp supply delta W | Overload recovery us | Source |", "|---|---|---|---|---|---|---|"]
    for k, a in PREAMPS.items():
        A = B["amps"][k]
        if A.get("unverified"): L.append(f"| {k} | {a['status']} | - | - | - | - | {a['src']} |"); continue
        L.append(f"| {k} | {a['status']} | {A['noise']} | {A['ratio6']:.4f} | {A['dP_W']:+.3f} | {A['rec'] if A['rec'] is not None else 'not on file'} | {a['src']} |")
    L += ["", "## Placement echo rows (variant axis `head_placement`)", "", "| Placement | Rule row | Value (x gate noise) | Limit |", "|---|---|---|---|"]
    for k, v in PLACES.items():
        rows = B["place_rows"].get(k, [])
        if not rows: L.append(f"| {k} ({'today' if k == TODAY_PLACE else ''}) | no new row (today's checks) | - | - |")
        for name, val, src in rows: L.append(f"| {k} | {name} | {val:.4g} | <= 0.5 |")
    open(os.path.join(ROOT, "docs", "BOARDS_COMPONENTS_MAP.md"), "w").write("\n".join(L) + "\n")
    return L

if __name__ == "__main__":
    import sys; sys.path[:0] = [RF2, os.path.join(RF2, "head")]
    for l in write_map(): print(l)
