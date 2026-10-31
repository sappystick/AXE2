#!/usr/bin/env python3
"""RF2 cord flex (owner decision 2026-10-30, HANDOFF section 45): the coil cord replaced by a long flex split at REF3T. One definition shared by
rf2_chassis (fit and rolling loop), rf2_system (harness), rf2_timing_cord (TX pair capacitance) and rf2_flex_options (study).
Construction: single conductive layer, 2 oz copper, Kapton base + 1 mil Kapton / acrylic coverlay (0.15 mm per layer, Minco design guide); trace widths
IPC-2221 (internal, 10 K rise); rule 6: 1.0 mm between the TX traces and from TX to everything else. Insulation: 3500 V/mil and 1000 VRMS typical
withstand (Minco design guide 2019); the drawing calls a net-to-net hipot >= 1000 VRMS.
Segment 1 (head -> REF3T) carries a rolling loop that stores half the telescope travel; segment 2 (REF3T -> hinge cord board) is static."""
import math
from scipy.special import ellipk
EPS0 = 8.854e-12
OZ, STACK_MM, EPS_EFF = 2.0, 0.15, 1.6                 # copper oz; stack 0.15 mm per layer (Minco design guide); eps_eff of the TX strips ASSUMED (range 1.3-2.2)
HV_GAP = 1.0                                            # rule 6
I_TX, I_PWR = 3.67, 0.45                                # A rms in continuous boost (rf2_continuous / rf2_system)
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

W_TX = ipc2221_width_mm(I_TX); W_PWR = max(ipc2221_width_mm(I_PWR), 0.3)
TX_LEN_M = 1.355                                        # TX strip length head -> hinge incl. the rolling-loop slack (rf2_chassis cord_flex checks it equals segments())
R_TX_LOOP = 2 * 0.017241 * TX_LEN_M / (W_TX * 0.0028 * 25.4)   # ohm, out and back on the 2 oz strips (20 C)
LANES = [("edge", 0.75), ("TX_A", W_TX), ("TX gap (rule 6)", HV_GAP), ("TX_B", W_TX), ("HV to LV gap (rule 6)", HV_GAP), ("VIN_H", W_PWR), ("gap", 0.3), ("GND_H", W_PWR), ("gap", 0.3)] + \
        [("TXCMD pair (2 x 0.15 / 0.15)", 0.45), ("gap", 0.3), ("TXSTAT pair (2 x 0.15 / 0.15)", 0.45), ("gap", 0.3), ("DATA pair (2 x 0.15 / 0.15)", 0.45)] + [("guard gap", 0.3)] + \
        [(f"REF{a} pair with ground guards (0.15 / 0.15 + 2 x 0.3)", 1.35) for a in "XYZ"] + [("edge", 0.75)]
WIDTH = sum(w for _, w in LANES)

def segments(st, ext, travel):
    """st / ext: rf2_chassis SPEC 'st' and 'extend_max'; travel: pivot-to-hinge length change (rf2_chassis telescope)"""
    ref_near = st["REF3"][0]
    seg1 = ref_near + ext["inner"] + ext["mid"] + travel / 2 + 60.0              # + head breakout and loop (ASSUMED)
    seg2 = (st["hinge"][0] - ref_near) + 40.0
    return dict(seg1_dynamic_mm=round(seg1), seg2_static_mm=round(seg2), tx_length_m=round((seg1 + seg2) / 1000.0, 3), one_piece_mm=round(seg1 + seg2 - 40))

def cps_c_pf_per_m(w=W_TX, s=HV_GAP, eps_eff=EPS_EFF):
    k = s / (s + 2 * w); kp = math.sqrt(1 - k * k); return EPS0 * eps_eff * ellipk(kp ** 2) / ellipk(k ** 2) * 1e12

def traces():
    """the harness view for rf2_system: each trace with its current limit (IPC-2221 width at 10 K) and the flat area for the fill check"""
    t = STACK_MM
    return [dict(name="TX_A", cls="HV", w=W_TX, i_max=I_TX * 1.0, v_ins=630, area=W_TX * t), dict(name="TX_B", cls="HV", w=W_TX, i_max=I_TX, v_ins=630, area=W_TX * t),
            dict(name="VIN_H", cls="power", w=W_PWR, i_max=max(I_PWR, 0.6), v_ins=None, area=W_PWR * t), dict(name="GND_H", cls="power", w=W_PWR, i_max=max(I_PWR, 0.6), v_ins=None, area=W_PWR * t),
            dict(name="TXCMD+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t), dict(name="TXSTAT+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t),
            dict(name="DATA+-", cls="diff", w=0.15, i_max=0.1, v_ins=None, area=0.45 * t)]

def write_spec(path=None):
    """docs/CORD_FLEX_SPEC.md: the vendor-quotable drawing notes (roadmap P4.2), generated from this module and the chassis telescope"""
    import os, sys, json
    here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
    import rf2_chassis as CS
    st, ext = CS.SPEC["st"], CS.SPEC["extend_max"]; travel = (st["hinge"][0] + ext["inner"] + ext["mid"]) - (st["hinge"][0] - CS.SPEC["collapse"]["inner"] - CS.SPEC["collapse"]["mid"])
    sg = segments(st, ext, travel); bore = min(CS.SPEC["tubes"]["inner"]) - 2 * CS.SPEC["wall"]
    L = ["# AXE2 cord flex: specification for quotation (generated by rf2/rf2_cordflex.py; MODELED design, not a released drawing)", "",
         "## 1. Function", "Carries the coil transmit pair, head power, three RS-485-class differential pairs and three guarded analog reference pairs from the search head to the hinge of the control chassis, through the 2-stage carbon telescope. Replaces a coiled cable.", "",
         "## 2. Construction",
         f"- Single conductive layer, Kapton polyimide base, **1 mil Kapton / acrylic coverlay** both sides; about {STACK_MM} mm per layer.",
         f"- **Selective copper:** {OZ:g} oz (0.0028 in) on TX_A, TX_B, VIN_H, GND_H; {LV_OZ:g} oz on the signal and reference areas (contoured / selective plating). Rolled-annealed copper preferred (dynamic loop).",
         f"- Width **{WIDTH:.1f} mm** (fits the {bore:.1f} mm bore with 2 mm clearance). Lanes, edge to edge:", ""]
    L += ["| Lane | Width mm |", "|---|---|"] + [f"| {n} | {w:.2f} |" for n, w in LANES] + [""]
    L += ["## 3. Pieces and lengths",
          f"- **Piece 1 (dynamic):** head gland -> REF3T board, **{sg['seg1_dynamic_mm']} mm**, with a rolling loop storing half of the {travel:.0f} mm telescope travel; loop bend radius {BEND_R:.1f} mm (40 x stack; IPC single layer >= 6 x).",
          f"- **Piece 2 (static):** REF3T -> hinge cord board, **{sg['seg2_static_mm']} mm**.",
          f"- Both inside the 40 in (1016 mm) preferred length of Tech Etch long flex; one-piece ({sg['one_piece_mm']} mm) only on a 5 ft (Minco) / 60 in (Tech Etch advanced) process.", "",
          "## 4. Electrical requirements",
          f"- **High voltage (project rule 6):** TX_A / TX_B carry the coil flyback, 460 V peak (clamp). Spacing >= {HV_GAP} mm TX-TX and TX-to-everything. **Net-to-net hipot >= {WITHSTAND_VRMS:.0f} VRMS, 60 Hz, 30 s, <= 1 mA** (Minco typical; Kapton aged rating 2000-3000 V/mil, Sierra HV notebook). No sharp copper corners on TX (round all bends and pad ends).",
          f"- **Current:** TX 3.67 A rms (continuous boost), traces {W_TX:.2f} mm at {OZ:g} oz for a 10 K rise (IPC-2221 internal); loop resistance about {R_TX_LOOP:.2f} ohm out and back over {TX_LEN_M} m. VIN_H / GND_H 0.45 A, {W_PWR:.2f} mm.",
          f"- **Capacitance:** TX strip pair about {cps_c_pf_per_m():.1f} pF/m (coplanar strips, eps_eff {EPS_EFF} ASSUMED): the vendor to report the measured value (it sets the first gate, rf2_timing_cord).",
          "- **Reference pairs:** 0.15 / 0.15 mm pairs with 0.3 mm ground guards each side; guards tied at REF3T only.", "",
          "## 5. Terminations",
          "- Solder lands only (no connector on the TX strips): head gland board, REF3T board (joint of pieces 1 and 2), hinge cord board.",
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
