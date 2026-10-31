#!/usr/bin/env python3
"""RF2 cord flex (owner decision 2026-10-30, HANDOFF section 45): the coil cord replaced by a long flex split at REF3T. One definition shared by
rf2_chassis (fit and rolling loop), rf2_system (harness), rf2_timing_cord (TX pair capacitance) and rf2_flex_options (study).
Construction: single conductive layer, 2 oz copper, Kapton base + 1 mil Kapton / acrylic coverlay (0.15 mm per layer, Minco design guide); trace widths
IPC-2221 (internal, 10 K rise); rule 6: 1.0 mm between the TX traces and from TX to everything else. Insulation: 3500 V/mil and 1000 VRMS typical
withstand (Minco design guide 2019); the drawing calls a net-to-net hipot >= 1000 VRMS.
Segment 1 (head -> REF3T) carries a rolling loop that stores half the telescope travel; segment 2 (REF3T -> hinge cord board) is static.
2026-10-31 (owner decision, HANDOFF section 56): the TXD is a pod on the shaft at s 400 (rf2_drive.TXD_S_MM), so the TX strips run head -> pod only and leave
piece 1 at the pod tap; TX strip width = IPC-2221 width at the BOOST rms of rf2_drive's design point (fixed point: width -> loop R -> rms), not a constant;
a 0.5 mm ground guard + 0.3 mm gap between the DATA pair and the REF group (variant option 'ref_guard'); piece 2 carries the pod feed (VIN_T / GND_T) and the
clamp return to the regenerative buck in the chassis (HV_CLAMP, rule-6 gaps) instead of the TX strips."""
import math, os, sys
from scipy.special import ellipk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_drive as DRV
EPS0 = 8.854e-12
OZ, STACK_MM, EPS_EFF = 2.0, 0.15, 1.6                 # copper oz; stack 0.15 mm per layer (Minco design guide); eps_eff of the TX strips ASSUMED (range 1.3-2.2)
HV_GAP = 1.0                                            # rule 6
I_PWR = 0.45                                            # A rms, head power VIN_H / GND_H (rf2_system)
I_FEED = 2.0                                            # A rms design allowance for the TXD pod feed VIN_T / GND_T (rf2_continuous checks the boost load against it)
I_CLAMP_RET = 0.05                                      # A, HV_CLAMP pair to the regenerative buck (about 20-30 mA in boost, rf2_continuous P_clamp / V_CLAMP)
GUARD_W, LV_GAP = 0.5, 0.3                              # REF guard trace (ASSUMED width, variant option 'ref_guard') and the LV gap
TE_LEN_PREF, TE_LEN_ADV = 40 * 25.4, 60 * 25.4          # Tech Etch long flex (brochure on file)
MINCO_LEN_MAX = 60 * 25.4                               # Minco: circuits up to 5 ft (design guide 2019); 1-2 layer panels 24 x 72 in (FC01)
# insulation (Minco design guide 2019): Kapton / modified acrylic 3500 V/mil, plain Kapton 3500-7000 V/mil; typical dielectric 1000 VRMS 60 Hz 30 s,
# 1 mA max leakage; withstanding test capability up to 6000 V; -65..105 C (acrylic), 150 C with the special adhesive
COVER_MIL = 1.0; COVER_V_PER_MIL = 2000.0; WITHSTAND_VRMS = 1000.0                # 1 mil Kapton coverlay (ASSUMED stack choice); 2000 V/mil = the AGED Kapton covercoat rating
# (Sierra Proto HV notebook 2004: 2000-3000 V/mil aged; Minco 3500 V/mil initial); FR4 aged about 300 V/mil (same notebook); sharp copper points arc at 1/3 the voltage of rounded ones
MIN_W_2OZ = 0.005 * 25.4                                # Minco minimum conductor width / space on 2 oz
LV_OZ = 0.5                                             # selective copper (owner sources 2026-10-30): 2 oz TX / power, 1/2 oz signal areas (Tech Etch contoured circuits; PICA 18 um adhesiveless)
MIN_W_HALF_OZ = 0.003 * 25.4                            # Minco artwork checklist: 0.003 in minimum on unplated 1/2 oz
CU_T_MM = {0.5: 0.0007 * 25.4, 1.0: 0.0014 * 25.4, 2.0: 0.0028 * 25.4}   # nomograph copper thicknesses (IPC-2223 reprint)
BEND_R = 40 * STACK_MM                                  # dynamic bend radius 40 x stack (ASSUMED; Minco: single layer >= 6 x (IPC), >= 10 x for reliability, single layer for dynamic)

def ipc2221_width_mm(i_a, oz=OZ, d_t=10.0, internal=True):
    k = 0.024 if internal else 0.048; area_mil2 = (i_a / (k * d_t ** 0.44)) ** (1 / 0.725); return area_mil2 / (1.378 * oz) * 0.0254

def tx_length_m(s_txd=DRV.TXD_S_MM, ext_in=20.0, ext_mid=170.0, travel=550.0):
    """TX strips head -> TXD pod: the pod rides the outer profile with REF3T (rf2_chassis), so the strips take the rolling loop (half the travel) as segment 1
    does, + 60 mm head breakout and loop (ASSUMED, as segments()) + 40 mm pod tap (ASSUMED, as the REF3T joint). Defaults = rf2_chassis SPEC (checked there)."""
    return (s_txd + ext_in + ext_mid + travel / 2 + 60.0 + 40.0) / 1000.0
TX_LEN_M = tx_length_m()                                # 0.965 m (was 1.355 m head -> hinge while the TXD sat in the chassis); rf2_chassis checks it equals segments()
CU_2OZ_MM = 0.0028 * 25.4
def r_tx_loop(w_tx, length_m=TX_LEN_M): return 2 * 0.017241 * length_m / (w_tx * CU_2OZ_MM)      # ohm, out and back on the 2 oz strips (20 C)
def _size_tx():
    """fixed point: strip width -> loop resistance -> boost coil rms (rf2_drive.pulse_train, the rf2_continuous model) -> IPC-2221 width"""
    w = 2.35
    for _ in range(50):
        i = DRV.pulse_train(DRV.I_BOOST, r_tx_loop(w))["I_rms_coil"]; w2 = ipc2221_width_mm(i)
        if abs(w2 - w) < 1e-9: break
        w = w2
    return w2, i
W_TX, I_TX = _size_tx()                                 # 3.22 mm at 4.62 A rms (2026-10-31; was 2.35 mm from a hard-coded 3.67 A, CORRECTIONS)
W_PWR = max(ipc2221_width_mm(I_PWR), 0.3); W_FEED = max(ipc2221_width_mm(I_FEED), 0.3); W_CLAMP = 0.3
R_TX_LOOP = r_tx_loop(W_TX)
LANES = [("edge", 0.75), ("TX_A", W_TX), ("TX gap (rule 6)", HV_GAP), ("TX_B", W_TX), ("HV to LV gap (rule 6)", HV_GAP), ("VIN_H", W_PWR), ("gap", 0.3), ("GND_H", W_PWR), ("gap", 0.3)] + \
        [("TXCMD pair (2 x 0.15 / 0.15)", 0.45), ("gap", 0.3), ("TXSTAT pair (2 x 0.15 / 0.15)", 0.45), ("gap", 0.3), ("DATA pair (2 x 0.15 / 0.15)", 0.45)] + \
        [("guard gap", LV_GAP), ("GUARD_REF ground guard (ref_guard)", GUARD_W), ("guard gap", LV_GAP)] + \
        [(f"REF{a} pair with ground guards (0.15 / 0.15 + 2 x 0.3)", 1.35) for a in "XYZ"] + [("edge", 0.75)]
LANES_PIECE2 = [("edge", 0.75), ("HV_CLAMP", W_CLAMP), ("HV gap (rule 6)", HV_GAP), ("GND_CLAMP", W_CLAMP), ("gap", LV_GAP), ("VIN_T (TXD pod feed)", W_FEED), ("gap", LV_GAP),
                ("GND_T", W_FEED), ("gap", LV_GAP), ("VIN_H", W_PWR), ("gap", LV_GAP), ("GND_H", W_PWR), ("gap", LV_GAP), ("DATA pair (2 x 0.15 / 0.15)", 0.45), ("edge", 0.75)]
WIDTH_PIECE2 = sum(w for _, w in LANES_PIECE2)
WIDTH = sum(w for _, w in LANES)

def segments(st, ext, travel):
    """st / ext: rf2_chassis SPEC 'st' and 'extend_max'; travel: pivot-to-hinge length change (rf2_chassis telescope)"""
    ref_near = st["REF3"][0]
    seg1 = ref_near + ext["inner"] + ext["mid"] + travel / 2 + 60.0              # + head breakout and loop (ASSUMED)
    seg2 = (st["hinge"][0] - ref_near) + 40.0
    tx = tx_length_m(DRV.TXD_S_MM, ext["inner"], ext["mid"], travel)                    # TX strips head -> TXD pod only (2026-10-31)
    return dict(seg1_dynamic_mm=round(seg1), seg2_static_mm=round(seg2), tx_length_m=round(tx, 3), one_piece_mm=round(seg1 + seg2 - 40), txd_s_mm=DRV.TXD_S_MM)

def cps_c_pf_per_m(w=W_TX, s=HV_GAP, eps_eff=EPS_EFF):
    k = s / (s + 2 * w); kp = math.sqrt(1 - k * k); return EPS0 * eps_eff * ellipk(kp ** 2) / ellipk(k ** 2) * 1e12

def traces(piece="head-pod"):
    """the harness view for rf2_system: each trace with its current limit (IPC-2221 width at 10 K) and the flat area for the fill check.
    piece 'head-pod': piece 1 up to the TXD pod tap (TX strips, TX command / status); 'pod-REF3T': piece 1 past the tap; 'piece2': REF3T -> hinge"""
    t = STACK_MM
    tx = [dict(name="TX_A", cls="HV", w=W_TX, i_max=I_TX * 1.0, v_ins=630, area=W_TX * t), dict(name="TX_B", cls="HV", w=W_TX, i_max=I_TX, v_ins=630, area=W_TX * t)]
    pwr = [dict(name="VIN_H", cls="power", w=W_PWR, i_max=max(I_PWR, 0.6), v_ins=None, area=W_PWR * t), dict(name="GND_H", cls="power", w=W_PWR, i_max=max(I_PWR, 0.6), v_ins=None, area=W_PWR * t)]
    cmd = [dict(name="TXCMD+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t), dict(name="TXSTAT+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t)]
    data = [dict(name="DATA+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t)]
    guard = [dict(name="GUARD_REF", cls="analog", w=GUARD_W, i_max=0.01, v_ins=None, area=GUARD_W * t)]
    if piece == "head-pod": return tx + pwr + cmd + data + guard
    if piece == "pod-REF3T": return pwr + data + guard
    return [dict(name="HV_CLAMP", cls="HV", w=W_CLAMP, i_max=I_CLAMP_RET, v_ins=630, area=W_CLAMP * t), dict(name="GND_CLAMP", cls="power", w=W_CLAMP, i_max=I_CLAMP_RET, v_ins=None, area=W_CLAMP * t),
            dict(name="VIN_T", cls="power", w=W_FEED, i_max=I_FEED, v_ins=None, area=W_FEED * t), dict(name="GND_T", cls="power", w=W_FEED, i_max=I_FEED, v_ins=None, area=W_FEED * t)] + pwr + data

def lane_gaps(lanes=None):
    """measured rule-6 gaps: every gap lane next to an HV trace (TX_A / TX_B / HV_CLAMP) -> min width, and the edge distances"""
    lanes = lanes or LANES; hv = ("TX_A", "TX_B", "HV_CLAMP"); g = []
    for k, (n, w) in enumerate(lanes):
        if n.split(" ")[0] in hv:
            for j in (k - 1, k + 1):
                if 0 <= j < len(lanes) and lanes[j][0] != "edge": g.append(lanes[j][1])
    return dict(min_hv_gap_mm=min(g) if g else None, n_hv_gaps=len(g))

def write_spec(path=None):
    """docs/CORD_FLEX_SPEC.md: the vendor-quotable drawing notes (roadmap P4.2), generated from this module and the chassis telescope"""
    import os, sys, json
    here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
    import rf2_chassis as CS
    st, ext = CS.SPEC["st"], CS.SPEC["extend_max"]; travel = (st["hinge"][0] + ext["inner"] + ext["mid"]) - (st["hinge"][0] - CS.SPEC["collapse"]["inner"] - CS.SPEC["collapse"]["mid"])
    sg = segments(st, ext, travel); bore = min(CS.SPEC["tubes"]["inner"]) - 2 * CS.SPEC["wall"]
    L = ["# AXE2 cord flex: specification for quotation (generated by rf2/rf2_cordflex.py; MODELED design, not a released drawing)", "",
         "## 1. Function", f"Carries the coil transmit pair from the search head to the TXD pod on the shaft (s {DRV.TXD_S_MM:.0f} mm), and head power, three RS-485-class differential pairs, three guarded analog reference pairs and (piece 2) the pod feed and clamp return between the head, the pod, REF3T and the hinge of the control chassis, through the 2-stage carbon telescope. Replaces a coiled cable.", "",
         "## 2. Construction",
         f"- Single conductive layer, Kapton polyimide base, **1 mil Kapton / acrylic coverlay** both sides; about {STACK_MM} mm per layer.",
         f"- **Selective copper:** {OZ:g} oz (0.0028 in) on TX_A, TX_B, VIN_H, GND_H (piece 1) and VIN_T, GND_T, VIN_H, GND_H, HV_CLAMP, GND_CLAMP (piece 2); {LV_OZ:g} oz on the signal and reference areas (contoured / selective plating). Rolled-annealed copper preferred (dynamic loop).",
         f"- Piece 1 width **{WIDTH:.2f} mm** against the {bore:.1f} mm inner bore less 2 mm = {bore - 2:.1f} mm: " + ("fits." if WIDTH <= bore - 2.0 else f"**does NOT fit ({WIDTH - (bore - 2):+.2f} mm; rule row 'cord-flex width vs bore less 2' BLOCKED / FAIL in docs/RULE_NEAR_MISSES.md: owner decision open)**."),
         f"- Piece 2 width **{WIDTH_PIECE2:.2f} mm** (no TX strips past the pod). Lanes, edge to edge, piece 1:", ""]
    L += ["| Lane | Width mm |", "|---|---|"] + [f"| {n} | {w:.2f} |" for n, w in LANES] + ["", "Piece 2 (REF3T -> hinge):", "", "| Lane | Width mm |", "|---|---|"] + [f"| {n} | {w:.2f} |" for n, w in LANES_PIECE2] + [""]
    L += ["## 3. Pieces and lengths",
          f"- **Piece 1 (dynamic):** head gland -> REF3T board, **{sg['seg1_dynamic_mm']} mm**, with a rolling loop storing half of the {travel:.0f} mm telescope travel; loop bend radius {BEND_R:.1f} mm (40 x stack; IPC single layer >= 6 x). The TX strips and the TXCMD / TXSTAT pairs end at the **TXD pod tap** (s {DRV.TXD_S_MM:.0f} mm, {sg['tx_length_m'] * 1000:.0f} mm of TX strip from the head incl. the loop); the rest continues to REF3T.",
          f"- **Piece 2 (static):** REF3T -> hinge cord board, **{sg['seg2_static_mm']} mm**.",
          f"- Both inside the 40 in (1016 mm) preferred length of Tech Etch long flex; one-piece ({sg['one_piece_mm']} mm) only on a 5 ft (Minco) / 60 in (Tech Etch advanced) process.", "",
          "## 4. Electrical requirements",
          f"- **High voltage (project rule 6):** TX_A / TX_B (piece 1, head -> pod) carry the coil flyback, {DRV.V_CLAMP:.0f} V peak (clamp); HV_CLAMP (piece 2) carries the clamp node DC to the regenerative buck. Spacing >= {HV_GAP} mm HV-HV and HV-to-everything (measured minimum {lane_gaps()['min_hv_gap_mm']} / {lane_gaps(LANES_PIECE2)['min_hv_gap_mm']} mm). **Net-to-net hipot >= {WITHSTAND_VRMS:.0f} VRMS, 60 Hz, 30 s, <= 1 mA** (Minco typical; Kapton aged rating 2000-3000 V/mil, Sierra HV notebook). No sharp copper corners on TX (round all bends and pad ends).",
          f"- **Current:** TX {I_TX:.2f} A rms (continuous boost at {DRV.I_BOOST:.2f} A peak, {DRV.T_FLAT * 1e6:.0f} us flat-top; rf2_drive / rf2_continuous), traces {W_TX:.2f} mm at {OZ:g} oz for a 10 K rise (IPC-2221 internal); loop resistance about {R_TX_LOOP:.3f} ohm out and back over {TX_LEN_M} m. VIN_H / GND_H {I_PWR} A, {W_PWR:.2f} mm. VIN_T / GND_T (pod feed, piece 2) {I_FEED} A design, {W_FEED:.2f} mm. HV_CLAMP / GND_CLAMP {W_CLAMP} mm.",
          f"- **Capacitance:** TX strip pair about {cps_c_pf_per_m():.1f} pF/m (coplanar strips, eps_eff {EPS_EFF} ASSUMED): the vendor to report the measured value (it sets the first gate, rf2_timing_cord).",
          f"- **Reference pairs:** 0.15 / 0.15 mm pairs with 0.3 mm ground guards each side; guards tied at REF3T only. A {GUARD_W} mm ground guard trace ({LV_GAP} mm gaps) separates the DATA pair from the REF group (owner 2026-10-31, variant option 'ref_guard').", "",
          "## 5. Terminations",
          "- TX strips: solder lands only (no connector on the TX strips): head gland board (TXJ) and the TXD pod tap. LV nets at the head gland: Panasonic Y5B 0.5 mm ZIFs on CB1D (10-way, VIN_H / GND_H on 2 pins each) and AB1A (10-way), flex ends stiffened to 0.30 mm (owner 2026-10-31, option 'gland_fpc'). REF3T board (joint of pieces 1 and 2) and the hinge cord board: solder lands.",
          "- Strain relief: a pin through a loop of the flex at the gland boss (SDC 2300 coil-cable pin pattern); stiffeners (polyimide) under the land areas.", "",
          "## 6. Environment and test",
          "- -20 to +60 C use (acrylic adhesive rated -65 to 105 C); field moisture (potted gland ends).",
          "- Tests: continuity, insulation resistance, the hipot above, dynamic flex life on the rolling loop (cycles to be agreed; telescoping several times per session), measured TX capacitance.", "",
          "## 7. Open with the vendor",
          "- Exact stack (adhesive vs adhesiveless), selective-copper process, RA copper in the loop, flex-life data at the 6 mm loop radius, price for 2 pieces vs 1."]
    path = path or os.path.join(os.path.dirname(here), "docs", "CORD_FLEX_SPEC.md"); open(path, "w").write("\n".join(L) + "\n")
    return dict(path=path, width_mm=round(WIDTH, 2), segments=sg, ok=True)

if __name__ == "__main__":
    print(write_spec())
