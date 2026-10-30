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
CU_T_MM = {0.5: 0.0007 * 25.4, 1.0: 0.0014 * 25.4, 2.0: 0.0028 * 25.4}   # nomograph copper thicknesses (IPC-2223 reprint)
BEND_R = 40 * STACK_MM                                  # dynamic bend radius 40 x stack (ASSUMED; Minco: single layer >= 6 x (IPC), >= 10 x for reliability, single layer for dynamic)

def ipc2221_width_mm(i_a, oz=OZ, d_t=10.0, internal=True):
    k = 0.024 if internal else 0.048; area_mil2 = (i_a / (k * d_t ** 0.44)) ** (1 / 0.725); return area_mil2 / (1.378 * oz) * 0.0254

W_TX = ipc2221_width_mm(I_TX); W_PWR = max(ipc2221_width_mm(I_PWR), 0.3)
LANES = [("edge", 0.75), ("TX_A", W_TX), ("TX gap (rule 6)", HV_GAP), ("TX_B", W_TX), ("HV to LV gap (rule 6)", HV_GAP), ("VIN_H", W_PWR), ("gap", 0.3), ("GND_H", W_PWR), ("gap", 0.3)] + \
        [(f"{n} pair (2 x 0.15 / 0.15)", 0.45) for n in ("TXCMD", "TXSTAT", "DATA")] + [("gap", 0.3) for _ in range(2)] + [("guard gap", 0.3)] + \
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
