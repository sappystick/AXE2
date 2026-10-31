#!/usr/bin/env python3
"""RF2 transmit drive design point: ONE source for the coil drive constants, the TX switch's datasheet values and the TXD position (owner decision
2026-10-31, adopted from docs/HEAD_BEST.md / HANDOFF section 55; HANDOFF section 56). Imported by rf2_continuous (ratings), rf2_cordflex (TX strip width
from the boost rms), rf2_txd_spice (ngspice), rf2_chassis / rf2_system (TXD pod position). This module exists so rf2_cordflex can size the TX strips from
the boost rms without a circular import (rf2_continuous needs the cord's loop resistance, the cord needs the coil rms).
MODELED: the pulse train follows HANDOFF section 8 (400 Hz; pulses alternate T1 and T1 + T_FLAT; linear fall L I / V_CLAMP).

Switch: onsemi NTBG080N120SC1 (EliteSiC M1, D2PAK-7L), data sheet Rev. 4 January 2023, data/datasheets/onsemi_NTBG080N120SC1.pdf (DATASHEET_LOG RF2-DS-ADOPT):
  VDSS 1200 V; ID 30 A (TC 25 C), 21 A (TC 100 C); IDM 110 A (TC 25 C, repetitive, limited by TJmax); TJ -55..175 C; EAS 171 mJ (IAS 18.5 A, L 1 mH,
  start TJ 25 C); RthJC 0.84 C/W max, RthJA 40 C/W max; RDS(on) 80 typ / 110 max mohm (VGS 20 V, ID 20 A, TJ 25 C), 121 mohm typ at TJ 150 C;
  Coss 79 pF typ (VDS 800 V, 1 MHz); EON 135 uJ, EOFF 46 uJ typ (VDS 800 V, ID 20 A, RG 4.7 ohm, inductive load); QG(tot) 56 nC.
  Hot RDS used here: 121 mohm (typ, 150 C) x 110 / 80 (the max / typ ratio at 25 C, ASSUMED to hold at 150 C) = 166 mohm.
usage: python3 rf2/rf2_drive.py   (prints the design point)"""
import math

# ---- coil and pulse (head-best design point: rf2/results/rf2_head_best.json coil_drive.head233.design)
L_COIL = 333e-6                 # H, the as-built rim mono (26 turns; the clean-sheet model gives 327.6 uH for the same comb: kept at the as-built 333)
R_COIL = 0.601                  # ohm at 20 C (rf2_wire_options: Rubadue 66/38 litz, 1056 CM over 18.3 m)
F_PULSE = 400.0                 # Hz
VBUS, V_CUTOFF, V_FULL = 25.2, 21.0, 29.4      # 7S P45B nominal, cut-off (3.0 V / cell), full (4.2 V / cell)
V_CLAMP = 477.0                 # V (was 460 until 2026-10-31)
RD = 408.0                      # ohm, damping across the coil (2 x Vishay PR03 806 ohm in parallel = 403 ohm built; 408 the modeled critical value)
T_FLAT = 318e-6                 # s (was 300 us)
I_SCAN = 8.94                   # A (was 8.06)
BOOST_K = 2.5                   # boost = scan x sqrt(2.5) (the energy ratio of the boost mode)
I_BOOST = I_SCAN * math.sqrt(BOOST_K)          # 14.14 A (was 12.74)
R_SHUNT = 0.010                 # Vishay WSL2512 10 mohm
FLAT_Q1_DUTY = 0.30             # Q1 share of the flat-top (hysteretic loop, rf2_txd_spice); the freewheel Q2 + D_fw carry the rest

# ---- TX switch (Q1 and Q2 the same part)
SWITCH = dict(part="onsemi NTBG080N120SC1", pdf="onsemi_NTBG080N120SC1.pdf", rev="Rev. 4, January 2023",
              vdss=1200.0, id25=30.0, id100=21.0, idm=110.0, tj_max=175.0, eas_J=171e-3, eas_ias=18.5,
              rthjc=0.84, rthja=40.0, rds25_typ=0.080, rds25_max=0.110, rds150_typ=0.121,
              coss_pF=79.0, eon_J=135e-6, eoff_J=46e-6, e_ref_V=800.0, e_ref_A=20.0, qg_nC=56.0,
              coss_extra_pF=79.0 - 20.0)   # node C above the C3M0280090J's (as rf2_lowL_options / rf2_cleansheet: ASSUMED effective Coss difference)
RDS_HOT = SWITCH["rds150_typ"] * SWITCH["rds25_max"] / SWITCH["rds25_typ"]     # 0.166 ohm (see the docstring; ASSUMED scaling)
PREV_SWITCH = dict(part="Wolfspeed C3M0280090J", vdss=900.0, idm=22.0, id100=7.0, rthjc=2.5, rds_hot=0.416 * 1.1)  # the record (until 2026-10-31)

def e_switch(i, v):
    """turn-on + turn-off energy at (i, v), scaled linearly in I and V from the datasheet point (ASSUMED linear)"""
    k = (i / SWITCH["e_ref_A"]) * (v / SWITCH["e_ref_V"]); return SWITCH["eon_J"] * k, SWITCH["eoff_J"] * k

# ---- TXD position (owner 2026-10-31): a pod on the shaft at s 400 mm from the yoke pivot (was inside the chassis at s 857)
TXD_S_MM = 400.0
TXD_POD_LEN_MM = 72.0           # the pod ends at the REF3 sleeve (s 436): 364-436 (rf2_chassis SPEC st TXD)

def r_loop(r_cable):
    return R_COIL + r_cable + RDS_HOT + R_SHUNT

def pulse_train(I, r_cable, L=L_COIL, vbus=VBUS, v_clamp=V_CLAMP, t_flat=T_FLAT, f=F_PULSE):
    """exponential (resistance-limited) ramp to I, flat-top on every second pulse, linear fall L I / V. -> the timing and the rms / mean currents"""
    R = r_loop(r_cable); tau = L / R; imax = vbus / R; T1 = -tau * math.log(1 - I / imax); tf = L * I / v_clamp
    tt = [T1 * k / 400 for k in range(401)]; ir = [imax * (1 - math.exp(-x / tau)) for x in tt]
    ramp_i2 = sum((ir[k] ** 2 + ir[k + 1] ** 2) / 2 * (tt[k + 1] - tt[k]) for k in range(400)); ramp_i = sum((ir[k] + ir[k + 1]) / 2 * (tt[k + 1] - tt[k]) for k in range(400))
    i2 = f * (ramp_i2 + 0.5 * I ** 2 * t_flat + (I ** 2 / 3) * tf); ia = f * (ramp_i + 0.5 * I * t_flat + 0.5 * I * tf)
    sw_i2 = f * (ramp_i2 + 0.5 * I ** 2 * t_flat * FLAT_Q1_DUTY)
    fw_i2 = f * (0.5 * I ** 2 * t_flat * (1 - FLAT_Q1_DUTY))
    return dict(I_pk=I, T1_us=T1 * 1e6, ramp_i2_As=ramp_i2, fall_us=tf * 1e6, I_rms_coil=math.sqrt(i2), I_avg_coil=ia, I_rms_switch=math.sqrt(sw_i2),
                I_rms_q2=math.sqrt(fw_i2), on_fraction=f * (T1 + 0.5 * t_flat))

if __name__ == "__main__":
    print(dict(I_scan=I_SCAN, I_boost=round(I_BOOST, 3), T_flat_us=T_FLAT * 1e6, V_clamp=V_CLAMP, switch=SWITCH["part"], RDS_hot=round(RDS_HOT, 4), TXD_s=TXD_S_MM))
