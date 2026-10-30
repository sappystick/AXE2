#!/usr/bin/env python3
"""RF2 cord flex (owner decision 2026-10-30, HANDOFF section 45): the coil cord replaced by a long flex split at REF3T. One definition shared by
rf2_chassis (fit and rolling loop), rf2_system (harness), rf2_timing_cord (TX pair capacitance) and rf2_flex_options (study).
Construction: single conductive layer, 2 oz copper, polyimide base + coverlay (about 0.1 mm total stack, ASSUMED); trace widths IPC-2221 (internal,
10 K rise); rule 6: 1.0 mm between the TX traces and from TX to everything else. Coverlay voltage rating: UNVERIFIED (vendor to confirm >= 630 V).
Segment 1 (head -> REF3T) carries a rolling loop that stores half the telescope travel; segment 2 (REF3T -> hinge cord board) is static."""
import math
from scipy.special import ellipk
EPS0 = 8.854e-12
OZ, STACK_MM, EPS_EFF = 2.0, 0.10, 1.6                 # copper oz, total stack, effective permittivity of the TX strips (ASSUMED; range 1.3-2.2)
HV_GAP = 1.0                                            # rule 6
I_TX, I_PWR = 3.67, 0.45                                # A rms in continuous boost (rf2_continuous / rf2_system)
TE_LEN_PREF, TE_LEN_ADV = 40 * 25.4, 60 * 25.4          # Tech Etch long flex (brochure on file)
BEND_R = 40 * STACK_MM                                  # dynamic bend radius 40 x stack (ASSUMED rule of thumb)

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
