#!/usr/bin/env python3
"""RF2 system architecture, placement and harness (2026-10-30, owner: 'placing, building, mapping, which components where ... upstream, downstream, every effect on the
housing, where it sits, wired, compatibility ... no funky routes; smooth, clean, combined, structured'). MODELED: positions along the shaft, module boxes, cable ODs and
the shaft geometry are ASSUMED and marked; part ratings come from the logged datasheets (docs/DATASHEET_LOG_ARX.md). The head interior is built and checked
elsewhere (rf2_head.py, rf2_boards.py, rf2_construct.py); the handle pod in head/rf2_pod.py. This file owns what joins them.

ARCHITECTURE (four sealed modules on one shaft; each owns one job, so every interface is short and single-purpose):
  HEAD  sensing and display: coil, MP1, AB1A/B, CB1D (RP2354A, 2 x AD7389-4), LR1 522-LED display, TXJ / TXF fins (Rd), LSM6DSO + MMC5983MA, 2 x TMP117.
  TXD   (2026-10-31, owner decision, HANDOFF section 56: a POD on the outer profile's lower end at s 400 mm, rf2_chassis SPEC st TXD 364-436; it was inside
        the control chassis at s 857, and before that on the lower shaft at s 255-345 as described next) transmit only: Q1 / Q2 onsemi NTBG080N120SC1 (was
        Wolfspeed C3M0280090J), Q1 on an Ohmite D Series heat sink, 2 x UCC5350 isolated driver, US3M clamp diode, clamp film capacitor, 9 x EEHZC1H101P
        bulk bank, WSL2512 shunt, one TMP117 whose EEPROM-stored therm limit pulls TXSTAT (no bus to it). PLACED BY SEARCH on the lower shaft, s 255-345 mm
        from the gland (not at the shaft base, the 'neck' of the baseline): there the coil's field puts the heat sink and the nine aluminium cans at 4400-4900 x
        the gate noise, and a 5 K temperature drift moves that by about 100 x the noise. At s 300 the drift is 0.1 x the noise; the longer TX pair costs
        about 15 pF (+0.16 us on the first gate, first-order).
  POD   the hand: HB2 rigid-flex (top and bottom boards joined by a side flex around the shaft bore): RP2354A, piezo bridge (rf2_audio), 4 x KSC2 TE (power,
        trigger, two selector-cam switches: one switch part for every input, no magnet), 3 x SK9822 light ring, memory-LCD screen, RS-485 link to CB1D.
  PACK  all power: 7S1P Molicel P45B, BQ76952 (protection, gauge, the main DSG switch; the power button wakes it on TS2), SF-1206S fuse, LMR36520 +5V_AUX for
        the pod, the regenerative clamp return (hysteretic buck reusing NTBG080N120SC1 / UCC5350 / US3M; was C3M0280090J), MT60 charge port (keyed). Under the forearm, behind the pod.
  Removed by this architecture: the PM2 soft-latch power path (Si4401FDY, BZT52C15) and the LTC4365 (the BQ76952 DSG switch and the keyed MT60 cover their
  jobs); the AU1 class-D amplifier and speaker (rf2_audio); the UCC28780 (the regenerative return is a hysteretic buck built from parts already in the BOM).
One shaft bundle inside the tube, tapped at the TXD, REF3 and the pod; HV in its own FEP-jacketed twisted pairs; nothing crosses the coil.
Checks: rails and budgets, logic levels, I2C maps, HV ratings (rule 6), conductor ampacity / drop / fill, coil field and metal echo at every external module,
magnetic sources near REF3, thermal per module, battery runtime. Writes rf2/results/rf2_system.json and rf2/results/rf2_system_map.png.
usage: python3 rf2/rf2_system.py   (exit 1 if a check fails)"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
OUT = os.path.join(HERE, "results")
import rf2_continuous as CT
import rf2_drive as DRV
import rf2_zones as Z
HEEL = 178.0
import rf2_chassis as CHS                                                                                   # chassis v2 (SDC-style) positions
import rf2_upper as UPR                                                                                     # the shaft geometry has one source: rf2_upper.py
_RZ = np.array([[math.cos(math.radians(HEEL)), -math.sin(math.radians(HEEL)), 0], [math.sin(math.radians(HEEL)), math.cos(math.radians(HEEL)), 0], [0, 0, 1]])
TILT = UPR.SPEC["tilt_deg"]
def at(s, off=0.0, lat=0.0): return _RZ @ UPR.at(s, off, lat)                                             # mm, head frame (s from the yoke pivot)
GLAND = at(0.0); D = _RZ @ UPR.D; NRM = _RZ @ UPR.N
TUBE = dict(od=21.0, id=18.0, material="narrowest bore: the inner square profile 21 x 21, 18 x 18 bore (rf2_chassis slim set; area taken as an 18 mm circle, conservative); conductive but 0.6-1.2 m from the coil and no loop around the coil axis")
# ---------------------------------------------------------------- modules (s = distance along the shaft from the gland, mm; off = offset from the axis)
MODULES = {
    "HEAD": dict(s=(-30, 0), off=0, box=None, power_W=dict(scan=10.6, boost=10.6), note="built in rf2_head / rf2_boards; +5 V and LED loads from rf2_wiring"),
    "TXD": dict(s=tuple(CHS.SPEC["st"]["TXD"]), off=0, lat=CHS.pod_y(), box=(CHS.SPEC["st"]["TXD"][1] - CHS.SPEC["st"]["TXD"][0], CHS.SPEC["txd_pod"]["w"], CHS.SPEC["txd_pod"]["h"]),
                note="TX driver POD on the outer profile's lower end, beside the C2 cam collar (owner 2026-10-31; was inside the control chassis at s 812-902)"),
    "REF3": dict(s=tuple(CHS.SPEC["st"]["REF3"]), off=0, box=(350, 42, 36), note="3-axis reference in the rectangular outer profile (rf2_ref3 rect_sleeve)"),
    "POD": dict(s=tuple(CHS.SPEC["st"]["chassis"]), off=0, box=(360, 72, 47), note="control chassis with the inverted grip on top (rf2_chassis.py)"),
    "PACK": dict(s=tuple(CHS.SPEC["st"]["bay"]), off=-50, box=(160, 77, 54), note="battery cartridge under the chassis (rf2_chassis.py)"),
}
PARTS = [  # module, ref, part, rail, volts min/max operating, I2C address, datasheet file or status, metal / magnetic note
    ("TXD", "Q1", "onsemi NTBG080N120SC1 (TX switch)", "HV", (0, 1200), None, "onsemi_NTBG080N120SC1.pdf", "copper tab"),
    ("TXD", "Q2", "onsemi NTBG080N120SC1 (flat-top freewheel switch)", "HV", (0, 1200), None, "onsemi_NTBG080N120SC1.pdf", "copper tab"),
    ("TXD", "HS1", "Ohmite D Series TO-263 heat sink (Q1)", None, None, None, "Ohmite_D_Series_heatsink.pdf", "aluminium 30.9 x 14.2 x 12.7 mm"),
    ("TXD", "U1", "TI UCC5350 isolated gate driver (Q1)", "+5V/VCC2 15 V", (3.0, 33.0), None, "TI_UCC5350-Q1_SLUSE29G_2025-01.pdf", ""),
    ("TXD", "U1B", "TI UCC5350 isolated gate driver (Q2, floating at the bus)", "+5V/VCC2 15 V", (3.0, 33.0), None, "TI_UCC5350-Q1_SLUSE29G_2025-01.pdf", ""),
    ("TXD", "D1", "Nexperia US3M clamp diode", "HV", (0, 1000), None, "Nexperia_US3M_2025-01-20.pdf", ""),
    ("TXD", "D2", "Nexperia US3M freewheel diode", "HV", (0, 1000), None, "Nexperia_US3M_2025-01-20.pdf", ""),
    ("TXD", "C1", "clamp film capacitor >= 6.8 uF 630 V", "HV", (0, 630), None, "ASSUMED (part to choose)", "metallised film"),
    ("TXD", "CB1-9", "9 x Panasonic EEHZC1H101P bulk", "VIN", (0, 50), None, "logged (ZC series)", "9 aluminium cans 10 x 10.2 mm (ASSUMED size)"),
    ("TXD", "RS1-2", "2 x Vishay WSL2512 10 mohm shunt", "TX", None, None, "logged (WSL)", ""),
    ("TXD", "U2", "TI TMP117 (therm mode from EEPROM, ALERT -> TXSTAT)", "+3V3_N", (1.8, 5.5), "0x48 (own, unused bus)", "TI_TMP117_SNOSD82D_2022-09.pdf", ""),
    ("HEAD", "U10", "ST LSM6DSO IMU", "+3V3", (1.71, 3.6), "0x6A", "ST_LSM6DSO_DS12140_Rev3_2024-06.pdf", ""),
    ("HEAD", "U11", "MEMSIC MMC5983MA magnetometer", "+3V3", None, "0x30", "MEMSIC_MMC5983MA_RevA_2019.pdf", ""),
    ("HEAD", "U12", "TI TMP117 display-drift sensor", "+3V3", (1.8, 5.5), "0x48", "TI_TMP117_SNOSD82D_2022-09.pdf", "2 x 2 mm pad"),
    ("HEAD", "U13", "TI TMP117 coil-channel / HV-fin sensor", "+3V3", (1.8, 5.5), "0x49", "TI_TMP117_SNOSD82D_2022-09.pdf", "2 x 2 mm pad"),
    ("POD", "U20", "RP2354A MCU", "+3V3_P", None, None, "ASSUMED (as CB1D)", ""),
    ("POD", "U21", "TI TLV755P 3.3 V LDO", "+5V_AUX", (1.45, 5.5), None, "TI_TLV755P_SBVS320D_2024-09.pdf", ""),
    ("POD", "LS1", "Murata PKLCS1212E4001-R1 piezo", "bridge 5 V", (0, 12.5), None, "Murata_PKLCS1212E4001-R1_2026-10-30.pdf", "magnet-free"),
    ("POD", "U22-25", "4 x TI SN74AHCT1G125 (piezo bridge, LED data / clock)", "+5V_AUX", (4.5, 5.5), None, "TI_SN74AHCT1G125_SCLS378P_2024-03.pdf", ""),
    ("POD", "SW1-4", "4 x C&K KSC2 TE (power, trigger, selector A / B)", "+3V3_P", (1, 24), None, "CK_KSC2_TE_tactile.pdf", ""),
    ("POD", "LED1-3", "3 x SK9822-EC20 light ring", "+5V_AUX", None, None, "OPSCO_SK9822-EC20-000_RevA0.pdf", ""),
    ("POD", "DSP1", "1.28 in memory LCD (Sharp LS013B7DH03 class)", "+3V3_P", None, None, "ASSUMED (datasheet not on file)", ""),
    ("POD", "U26", "RS-485 transceiver (link to CB1D)", "+3V3_P", None, None, "ASSUMED (part to choose)", ""),
    ("POD", "U27", "TI TPD4E1B06 ESD on the link connector", "+3V3_P", (-5.5, 5.5), None, "TI_TPD4E1B06_SLVSBQ8E_2024-10.pdf", ""),
    ("PACK", "BT1", "7 x Molicel INR-21700-P45B (7S1P)", "VBAT", (2.5 * 7, 4.2 * 7), None, "Molicel_INR-21700-P45B_PDS_v1.2.pdf", "7 steel cans"),
    ("PACK", "U30", "TI BQ76952 monitor / protector", "VBAT", (4.7, 80), "0x08", "TI_BQ76952_SLUSE13B_2021-11.pdf", ""),
    ("PACK", "F1", "Bourns SF-1206S500-2 5 A slow fuse", "VBAT", (0, 32), None, "Bourns_SF-1206S.pdf", ""),
    ("PACK", "U31", "TI LMR36520 buck -> +5V_AUX", "VBAT", (4.2, 65), None, "TI_LMR36520_RevC.pdf", "shielded inductor (ferrite: allowed here)"),
    ("PACK", "Q30", "NTBG080N120SC1 regenerative buck switch (one switch part with the TXD)", "HV", (0, 1200), None, "onsemi_NTBG080N120SC1.pdf", ""),
    ("PACK", "U32", "UCC5350 regenerative buck driver", "+5V_AUX", (3.0, 33.0), None, "TI_UCC5350-Q1_SLUSE29G_2025-01.pdf", ""),
    ("PACK", "D30", "US3M regenerative freewheel diode", "HV", (0, 1000), None, "Nexperia_US3M_2025-01-20.pdf", ""),
    ("PACK", "J30", "Amass MT60 keyed charge port", "VBAT", (0, 500), None, "Amass_MT60_spec_V1.2.pdf", ""),
]
# ---------------------------------------------------------------- the shaft bundle: segment -> conductors (name, class, AWG, OD mm, current A rms boost, insulation V)
FEP18, FEP20, FEP24, STP26 = (18, 1.70), (20, 1.45), (24, 1.10), (26, 2.9)
OHM_PER_M = {18: 0.0210, 20: 0.0333, 24: 0.0842, 26: 0.134}                       # copper at 20 C (standard AWG tables)
def cond(name, cls, g, i, v=600): return dict(name=name, cls=cls, awg=g[0], od=g[1], i_rms=i, v_ins=v)
import rf2_cordflex as CFX                                                          # owner 2026-10-30: the coil cord is a long flex split at REF3T (HANDOFF 45)
_CJ = json.load(open(os.path.join(OUT, "rf2_continuous.json")))                     # rf2_continuous runs first (run.py dep)
_B = next(m for m in _CJ["modes"] if m["mode"].startswith("boost"))
P_BOOST = _B["battery"]["regenerative clamp (75 % recovery ASSUMED)"]["P_total_W"]; I_VIN = P_BOOST / 25.2      # battery power and current in continuous boost (was 28.3 W fixed)
I_FEED = _B["I_feed_A"]                                                              # TXD pod feed (cord VIN_T / GND_T), boost at cut-off
_I = {"TX_A": CFX.I_TX, "TX_B": CFX.I_TX, "VIN_H": 0.45, "GND_H": 0.45, "VIN_T": I_FEED, "GND_T": I_FEED, "HV_CLAMP": 0.03, "GND_CLAMP": 0.03}
def _flex(piece, with_ref):
    out = [dict(name=t["name"], cls=t["cls"], awg=None, od=None, area=t["area"], i_rms=_I.get(t["name"], 0.01), i_max=t["i_max"], v_ins=t["v_ins"],
                note="flex trace; HV coverlay rating UNVERIFIED (630 V is the requirement, vendor to confirm)") for t in CFX.traces(piece)]
    if with_ref: out += [dict(name=f"REF{a}+-", cls="analog", awg=None, od=None, area=1.35 * CFX.STACK_MM, i_rms=0.0, i_max=0.01, v_ins=None) for a in "XYZ"]
    return out
_ST = CHS.SPEC["st"]; _SP = DRV.TXD_S_MM
SEGMENTS = {   # TXD pod at s 400 (owner 2026-10-31): the TX strips run head -> pod only; the pod feed and the clamp return run pod <- hinge
    "S1 head - TXD pod (cord flex piece 1, rolling loop; TX strips tap off at the pod)": dict(len_m=_SP / 1000.0, conds=_flex("head-pod", with_ref=True)),
    "S1b TXD pod - REF3T (cord flex piece 1, no TX)": dict(len_m=(_ST["REF3"][0] - _SP) / 1000.0, conds=_flex("pod-REF3T", with_ref=True)),
    "S2 REF3T - hinge (cord flex piece 2, static: pod feed, clamp return)": dict(len_m=(_ST["hinge"][0] - _ST["REF3"][0]) / 1000.0, conds=_flex("piece2", with_ref=False)),
    "S3 hinge pass-through into the chassis": dict(len_m=0.06, conds=[cond("HV_CLAMP", "HV", FEP24, 0.03, 1000), cond("GND_CLAMP", "power", FEP24, 0.03),
        cond("VIN_T", "power", FEP18, I_FEED), cond("GND_T", "power", FEP18, I_FEED), cond("VIN_H", "power", FEP20, 0.45), cond("GND_H", "power", FEP20, 0.45), cond("DATA+-", "diff", (26, 1.9), 0.01)]),
}
AMPACITY = {18: 7.0, 20: 5.0, 24: 2.0, 26: 1.0}                                    # conservative bundle ampacity, A (ASSUMED, well under single-wire FEP ratings)
def main():
    res = dict(status="MODELED: positions, boxes, cable ODs and the shaft geometry ASSUMED; ratings from logged datasheets", checks={}, decisions=[], modules={}, harness={})
    c = res["checks"]
    res["decisions"] = [
        "Audio: magnet-free SMD piezo in bridge drive on HB2 (rf2_audio.py); tones 3.0-7.6 kHz, equalised; AU1 class-D + speaker removed",
        "Power switching: BQ76952 DSG high-side switch is the main switch; the power button wakes it on TS2 (falling edge, datasheet 7.x 'Wake on TS2'), the pod MCU "
        "turns it off over I2C after a 2 s hold; PM2 soft latch and LTC4365 removed (keyed MT60 prevents reverse charge)",
        "TX driver placement (owner 2026-10-31): a pod on the outer profile's lower end at s 400 (past the 375 mm echo distance); it was inside the control chassis (s 857). "
        "The echo is checked at the pod's nominal, min-use and max-use positions (it rides the telescope with REF3)",
        "Continuous boost thermal: the clamp energy (%.1f W boost) returns to the battery through the hysteretic buck on the PWR board in the chassis; the clamp node "
        "(%.0f V DC, about 30 mA) runs pod -> hinge in cord piece 2 (HV_CLAMP, rule-6 gaps). The pod keeps Q1 (%.2f W, vented heat sink, TJ %.0f C) and Q2 / diodes / shunts / drivers in its housing (rf2_continuous)"
        % (next(r["load"] for r in _B["rows"] if r["part"].startswith("clamp absorber")), DRV.V_CLAMP, _B["P_switch_W"], next(r["load"] for r in _B["rows"] if "Q1: junction" in r["part"])),
        "Pack: 7S1P Molicel P45B (113 Wh) under the forearm as the head's counterweight",
        "Inputs: one switch part (C&K KSC2 TE, IP67) for power, trigger and the two selector cams; no magnet in the pod (no offset at REF3 / the upper fluxgate)",
        "TXD temperature: TMP117 in therm mode with EEPROM-stored limits drives the TXSTAT fault line; the head backs the boost off (no I2C to the TXD)",
        "Link: RS-485 class pair (DATA+-) from CB1D to the pod; the head schedules LED frames and audio events on one clock and both play them a fixed 20 ms later "
        "(rf2_display3 coupling holds across the link)"]
    # ---- coil field and metal echoes at the external modules
    I_b = DRV.I_BOOST
    for m, d in MODULES.items():
        if d["box"] is None: continue
        s0, s1 = d["s"]; P = at((s0 + s1) / 2, d["off"], d.get("lat", 0.0)); near = min((at(s, d["off"]) for s in np.linspace(s0, s1, 9)), key=lambda q: np.linalg.norm(q[:2]) - 0)
        B = float(np.linalg.norm(Z.Bc(P)[0])) * I_b; Bn = max(float(np.linalg.norm(Z.Bc(at(s, d["off"], d.get("lat", 0.0)))[0])) * I_b for s in np.linspace(s0, s1, 9))
        res["modules"][m] = dict(centre_mm=[round(v, 1) for v in P], B_centre_uT_boost=round(B * 1e6, 2), B_max_uT_boost=round(Bn * 1e6, 2), box_mm=d["box"], note=d["note"])
    # metal echoes as single loops (rf2_zones.loop_echo; conservative for a block): fixed targets the offset / ground balance removes; the DRIFT must stay
    # under the gate noise: aluminium resistivity moves about 0.4 %/K, so a 5 K step moves the echo by 2 %
    def echo(P, r, w, t, sigma, axis=None):
        """axis None: |B|, the worst-case loop orientation (blocks such as the heat sink); axis given (head frame): a closed can wall links only the field along its
        axis (bulk-capacitor cans and cells are laid with their axes lateral, where the head's mirror symmetry makes that component small)"""
        B = Z.Bc(P)[0]; b = float(np.linalg.norm(B)) if axis is None else abs(float(B @ axis)); e, tau = Z.loop_echo(b * math.pi * r * r, r, w, 0, sigma, t); return e
    LAT = _RZ @ np.array([0.0, 1.0, 0.0])
    LAT_HS = CHS.pod_y() + CHS.SPEC["txd_pod"]["w"] / 2 - 11.0; LAT_CB = CHS.pod_y() - 10.0                      # heat sink and bulk cans in the pod (rf2_chassis electronics)
    def txd_echo(sx, lat_hs=LAT_HS, lat_cb=LAT_CB):
        return echo(at(sx, 0.0, lat_hs), 0.010, 0.0127, 0.003, Z.SIG_AL) + 9 * echo(at(sx, 0.0, lat_cb), 0.005, 0.010, 0.0003, Z.SIG_AL, LAT)       # heat sink + 9 bulk cans (sizes ASSUMED)
    search = [dict(s_mm=sx, B_uT_boost=round(float(np.linalg.norm(Z.Bc(at(sx, 0.0, LAT_HS))[0])) * I_b * 1e6, 1), echo_x_noise=round(txd_echo(sx) / Z.NOISE_GATE, 2),
                   drift5K_x_noise=round(txd_echo(sx) * 0.02 / Z.NOISE_GATE, 3)) for sx in (90, 200, 300, 330, 350, 375, 400, 590)]
    s_txd = DRV.TXD_S_MM; e_txd = txd_echo(s_txd)
    ext = CHS.SPEC["extend_max"]; s_min, s_max = s_txd - 100.0, s_txd + ext["inner"] + ext["mid"]          # the pod rides the outer profile: min use -100 mm, max +190 mm (rf2_chassis telescope)
    e_min, e_max = txd_echo(s_min), txd_echo(s_max)
    s_ok = next((float(sx) for sx in np.arange(250.0, 600.0, 1.0) if txd_echo(sx) * 0.02 <= 0.5 * Z.NOISE_GATE), None)
    ecell = 7 * echo(at(1130, -40), 0.0108, 0.070, 0.00025, 1.0e7, LAT)              # 7 x 21700 cans (21.55 x 70.15 mm)
    res["echoes"] = dict(txd_search=search, txd_at_s_mm=s_txd, txd_lateral_mm=dict(heat_sink=round(LAT_HS, 1), bulk_cans=round(LAT_CB, 1)), txd_echo_x_gate_noise=round(e_txd / Z.NOISE_GATE, 2), txd_drift5K_x_noise=round(e_txd * 0.02 / Z.NOISE_GATE, 3),
                         txd_min_use=dict(s_mm=s_min, drift5K_x_noise=round(e_min * 0.02 / Z.NOISE_GATE, 3)), txd_max_use=dict(s_mm=s_max, drift5K_x_noise=round(e_max * 0.02 / Z.NOISE_GATE, 3)),
                         txd_nearest_s_passing_mm=s_ok,
                         pack_cells_x_gate_noise=round(ecell / Z.NOISE_GATE, 5), criterion="drift for a 5 K step <= 0.5 x the gate noise; heat sink at worst-case orientation, cans with lateral axes")
    c["TXD metal echo drift (5 K) <= 0.5 x gate noise at its placed position"] = e_txd * 0.02 <= 0.5 * Z.NOISE_GATE
    c["TXD pod echo drift (5 K) <= 0.5 x gate noise at the shortest use length (pod rides the telescope, -100 mm)"] = e_min * 0.02 <= 0.5 * Z.NOISE_GATE
    c["at the baseline neck (s 90) the same parts would fail (> 1 x noise)"] = txd_echo(90) * 0.02 > Z.NOISE_GATE
    c["pack cells echo drift negligible (< 0.01 x noise)"] = ecell * 0.02 < 0.01 * Z.NOISE_GATE
    # the longer TX pair adds capacitance at the coil node; the critically damped tail scales with sqrt(C) (first-order; re-run rf2_timing with C_ext + pair)
    C_PAIR = CFX.cps_c_pf_per_m() * 1e-12; l_tx = CFX.TX_LEN_M; dC = C_PAIR * l_tx; tail = 16.3 - 5.8                     # TX strips head -> pod (rf2_cordflex)
    d_gate = tail * (math.sqrt(1 + dC / 500e-12) - 1); d_gate_base = tail * (math.sqrt(1 + C_PAIR * 0.09 / 500e-12) - 1)
    try: d_gate = max(v["shift_fixed_us"] for v in json.load(open(os.path.join(OUT, "rf2_timing_cord.json")))["cases"].values())      # the nonlinear simulation replaces the estimate
    except Exception: pass
    res["tx_pair"] = dict(length_m=l_tx, C_pF=round(dC * 1e12, 1), C_pF_per_m=round(C_PAIR * 1e12, 2), first_gate_shift_us=round(d_gate, 3), vs_baseline_neck_us=round(d_gate - d_gate_base, 3),
                          note="rf2_timing_cord (nonlinear) when its result is on file, else first-order: tail 10.5 us x (sqrt(1 + dC / 500 pF) - 1); strip capacitance from rf2_cordflex (eps_eff ASSUMED)")
    c["TX pair adds <= 0.6 us to the first gate (first-order)"] = d_gate <= 0.6
    # ---- magnetic and audio-frequency sources near REF3
    ref = at(600); pod = at(960, 19)                                                                   # nearest handle source: the piezo on HB2-M in the chassis (grip head
    r_ref = float(np.linalg.norm(pod - ref)) * 1e-3
    m_piezo = 0.0                                                                                      # piezo: no magnet, drive current about 7 mA in a < 1 cm2 loop on the board
    loop_m = 7.35e-3 * 1e-4; B_piezo = 1e-7 * 2 * loop_m / r_ref ** 3
    res["ref3_coupling"] = dict(distance_pod_to_REF3_mm=round(r_ref * 1e3), piezo_loop_field_pT=round(B_piezo * 1e12, 3), magnets_in_pod=0,
                                speaker_alternative_nT=round(1e-7 * 2 * (50 * math.pi * 0.006 ** 2 * 0.11) / r_ref ** 3 * 1e9, 2),
                                note="speaker alternative: a 50-turn, 12 mm voice coil at 0.11 A rms (0.1 W into 8 ohm), unshielded upper bound")
    c["no magnet in the pod; piezo audio field at REF3 < 10 pT (0.1 % of a 10 nT mains field, ASSUMED)"] = m_piezo == 0 and B_piezo < 10e-12
    # ---- harness: ampacity, voltage drop, fill, HV insulation
    tube_area = math.pi * (TUBE["id"] / 2) ** 2; hv_ok = True; amp_ok = True; fill = {}
    for sg, d in SEGMENTS.items():
        area = sum(x.get("area") or math.pi * (x["od"] / 2) ** 2 for x in d["conds"]); fill[sg] = round(area / tube_area, 3)
        for x in d["conds"]:
            amp_ok &= x["i_rms"] <= (x["i_max"] if x.get("i_max") is not None else AMPACITY[x["awg"]])
            if x["cls"] == "HV": hv_ok &= x["v_ins"] >= 630
    l_feed = (_ST["hinge"][0] - _SP) / 1000.0 + 0.06                                                          # pack -> TXD pod: chassis AWG18 0.15 m + cord VIN_T / GND_T hinge -> pod (+ 60 mm tap, ASSUMED)
    r_feed = 2 * (0.15 * OHM_PER_M[18] + 0.017241 * l_feed / (CFX.W_FEED * CFX.CU_2OZ_MM))
    drop = r_feed * I_FEED
    res["harness"] = dict(segments={k: [x["name"] for x in v["conds"]] for k, v in SEGMENTS.items()}, fill_fraction=fill, vin_drop_V_boost=round(drop, 3), feed_loop_R_ohm=round(r_feed, 3), feed_I_A=I_FEED,
                          vin_loss_W_boost=round(drop * I_VIN, 3), tube=TUBE,
                          route="one bundle inside the tube; taps leave through grommeted holes at the TXD (S1), REF3 (its 3 pairs) and the pod (DATA, and the pod-pack pairs); "
                                "HV pairs in their own FEP jackets, twisted with their return; LV and analog pairs in a separate sleeve")
    c["every HV conductor insulated >= 630 V (rule 6)"] = hv_ok
    c["every conductor inside its bundle ampacity"] = amp_ok
    c["tube fill <= 40 % per segment"] = max(fill.values()) <= 0.40
    c["VIN drop (pack -> TXD pod) under 2 % of 25.2 V in boost"] = drop <= 0.02 * 25.2
    # ---- rails, levels, addresses
    rails = {"+5V_AUX (LMR36520, 2 A)": dict(rating=2.0, loads={"pod MCU + LDO (ASSUMED 60 mA)": 0.06, "light ring 3 x SK9822 (firmware cap 20 mA each)": 0.06,
                                                                "piezo bridge": 0.0074, "AHCT x4": 0.004, "screen": 0.0002, "RS-485 (ASSUMED)": 0.01, "UCC5350 regen (ASSUMED)": 0.02})}
    for r in rails.values(): r["load"] = round(sum(r["loads"].values()), 4); r["margin"] = round(r["rating"] / r["load"], 1)
    res["rails"] = rails
    c["+5V_AUX loaded under 50 %"] = all(r["load"] <= 0.5 * r["rating"] for r in rails.values())
    vbat = (3.0 * 7, 4.2 * 7)                                                                         # BQ76952 under-voltage set at 3.0 V / cell (chosen), full 4.2 V
    on_vbat = [p for p in PARTS if p[3] in ("VBAT", "VIN") and p[4]]
    c["every VBAT / VIN part rated for 21.0-29.4 V"] = all(p[4][0] <= vbat[0] and p[4][1] >= vbat[1] for p in on_vbat)
    res["vbat_parts"] = {p[2]: p[4] for p in on_vbat}
    levels = dict(mcu_out_V=3.3, ahct_VIH=2.0, bq_i2c_max_V=5.5, tmp117_max_V=5.5, ksc2_min_V=1.0)
    c["logic levels compatible (3.3 V MCU -> AHCT VIH 2.0 V; I2C pull-ups 3.3 V within BQ76952 5.5 V)"] = levels["mcu_out_V"] >= levels["ahct_VIH"] and 3.3 <= levels["bq_i2c_max_V"] and levels["ksc2_min_V"] <= 3.3
    buses = {"head I2C (CB1D)": [p[5] for p in PARTS if p[0] == "HEAD" and p[5]], "pod I2C (HB2 <-> PACK)": [p[5] for p in PARTS if p[0] == "PACK" and p[5]]}
    c["I2C addresses unique per bus"] = all(len(v) == len(set(v)) for v in buses.values()); res["i2c"] = buses
    c["every HV-rail part >= 630 V (rule 6)"] = all(p[4][1] >= 630 for p in PARTS if p[3] == "HV")
    # ---- thermal and runtime
    boost = next(mm for mm in json.load(open(os.path.join(OUT, "rf2_continuous.json")))["modes"] if mm["mode"].startswith("boost"))
    tj = next(r["load"] for r in boost["rows"] if "junction" in r["part"]); p_clamp = next(r["load"] for r in boost["rows"] if r["part"].startswith("clamp absorber"))
    regen_eff = 0.90; p_pack = p_clamp * (1 - regen_eff) + 0.3 + 0.25                                 # buck loss (90 % ASSUMED) + LMR36520 + cell I2R (ASSUMED)
    pc = boost; I_pk = pc["I_pk"]; p_q1 = pc["P_switch_W"]; p_q2 = pc["P_q2_W"]
    p_dfw = DRV.F_PULSE * 0.5 * DRV.T_FLAT * (1 - DRV.FLAT_Q1_DUTY) * 1.2 * I_pk                     # freewheel US3M, about 1.2 V (rf2_continuous)
    p_dcl = next(r["load"] for r in pc["rows"] if r["part"].startswith("clamp diode US3M: average")) * 1.5   # clamp US3M, VF about 1.5 V
    p_sh = next(r["load"] for r in pc["rows"] if r["part"].startswith("current shunt")) + pc["I_rms_q2"] ** 2 * DRV.R_SHUNT
    p_in_pod = p_q2 + p_dfw + p_dcl + p_sh + 0.2                                                     # + 2 drivers, sense amplifier, TMP117 about 0.2 W (ASSUMED)
    tj_q2 = next(r["load"] for r in pc["rows"] if r["part"].startswith("freewheel switch Q2"))
    pod = CHS.SPEC["txd_pod"]; Lp = (_ST["TXD"][1] - _ST["TXD"][0]) / 1000.0; a_pod = 2 * (Lp * pod["w"] / 1e3 + Lp * pod["h"] / 1e3 + pod["w"] * pod["h"] / 1e6)
    rise_pod = p_in_pod / (8.0 * a_pod)
    res["thermal"] = dict(txd_switch_TJ_C=tj, txd_q2_TJ_C=tj_q2, txd_W=round(p_q1 + p_in_pod, 2), txd_pod_housing_W=round(p_in_pod, 2), txd_pod_surface_m2=round(a_pod, 5), txd_pod_surface_rise_K=round(rise_pod, 1),
                          pack_W_boost=round(p_pack, 2), split_W=dict(Q1_on_vented_heat_sink=p_q1, Q2=p_q2, D_freewheel=round(p_dfw, 3), D_clamp=round(p_dcl, 3), shunts=round(p_sh, 3), drivers_misc_ASSUMED=0.2),
                          note="TXD pod: Q1 on the Ohmite heat sink at a vented window (free air, as its 7 C/W rating); the rest heats the sealed pod housing (natural convection 8 W/m2K, ASSUMED); pack: regenerative buck losses at 90 % (ASSUMED), LMR36520 and cell I2R")
    c["TXD switch TJ under 125 C"] = tj <= 125.0
    c["TXD pod housing surface rise <= 15 K in continuous boost (natural convection, ASSUMED)"] = rise_pod <= 15.0
    area = 2 * (0.36 * 0.072 + 0.36 * 0.047 + 0.072 * 0.047); p_ch = p_pack; rise = p_ch / (8.0 * area)
    res["thermal"].update(chassis_W_boost=round(p_ch, 2), chassis_surface_rise_K=round(rise, 1), note2="chassis 360 x 72 x 47 mm, natural convection 8 W/m2K (ASSUMED); PWR (regenerative buck) and pack only: the TXD is in the pod")
    c["chassis surface rise <= 15 K in continuous boost (PWR + pack)"] = rise <= 15.0
    c["pack dissipation under 3 W in continuous boost"] = p_pack < 3.0
    wh = 7 * 16.2 * 0.9                                                                               # 7 x P45B 16.2 Wh typ (datasheet), 90 % usable (ASSUMED)
    bat = boost["battery"]; scan = next(mm for mm in json.load(open(os.path.join(OUT, "rf2_continuous.json")))["modes"] if mm["mode"] == "scan")["battery"]
    p_scan = scan["regenerative clamp (75 % recovery ASSUMED)"]["P_total_W"]; p_boost = bat["regenerative clamp (75 % recovery ASSUMED)"]["P_total_W"]
    res["runtime"] = dict(pack="7S1P Molicel P45B", rated_case="continuous boost (trigger held the whole time): the maximum use case (owner 2026-10-30)", usable_Wh=round(wh, 1), scan_h=round(wh / p_scan, 1), boost_continuous_h=round(wh / p_boost, 1),
                          cells_g=7 * 70, note="powers from rf2_continuous (regenerative clamp, 75 % recovery ASSUMED)")
    res["runtime"]["target_h"] = None                                                               # the 6 h target is RELAXED by the owner (2026-10-30): rf2_rules.py lists it every run
    c["runtime rated on continuous boost, from the chosen cell's datasheet energy"] = abs(wh - 7 * 16.2 * 0.9) < 1e-9 and p_boost > p_scan
    res["all_pass"] = all(c.values())
    json.dump(res, open(os.path.join(OUT, "rf2_system.json"), "w"), indent=1)
    figure(res)
    for k, v in c.items(): print(("  PASS " if v else "  FAIL ") + k)
    print(json.dumps(dict(modules={k: v["B_max_uT_boost"] for k, v in res["modules"].items()}, echoes=res["echoes"], runtime=res["runtime"], fill=res["harness"]["fill_fraction"]), indent=1))
    return res
def figure(res):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(15, 5.2)); u = lambda P: (-(P[0] - GLAND[0]) / math.sin(math.radians(TILT)) * 0 + np.dot(P - GLAND, D), np.dot(P - GLAND, NRM))
    ax.add_patch(plt.Rectangle((-240, -60), 230, 20, color="#999", alpha=0.4)); ax.text(-235, -75, "HEAD (coil, MP1, AB1A/B, CB1D, LR1, TXJ/TXF)", fontsize=8)
    ax.plot([0, 1250], [0, 0], color="#555", lw=6, solid_capstyle="butt", alpha=0.35); ax.text(1200, 8, "shaft tube", fontsize=8)
    cols = dict(TXD="#d62728", REF3="#9467bd", POD="#1f77b4", PACK="#2ca02c")
    for m, d in MODULES.items():
        if d["box"] is None: continue
        s0, s1 = d["s"]; h = d["box"][2]; y0 = d["off"] - h / 2
        ax.add_patch(plt.Rectangle((s0, y0), s1 - s0, h, fc=cols[m], alpha=0.35, ec=cols[m])); ax.text(s0, y0 + h + 6, m, color=cols[m], fontsize=10, weight="bold")
        parts = [p for p in PARTS if p[0] == m]
        for k, p in enumerate(parts[:9]):
            yy = (y0 + h + 22 + 9 * k) if m in ("POD", "REF3") else (y0 - 10 - 9 * k)
            ax.text(s0 + 2, yy, f"{p[1]} {p[2][:44]}", fontsize=6.2, color=cols[m])
    y = 4
    for sg, d in SEGMENTS.items():
        a, b = {"S1": (0, _ST["REF3"][0]), "S2": (_ST["REF3"][0], _ST["hinge"][0]), "S3": (_ST["hinge"][0], _ST["hinge"][1] + 40)}[sg[:2]]
        ax.annotate("", (b, y), (a, y), arrowprops=dict(arrowstyle="-", lw=2, color="#e377c2" if any(x["cls"] == "HV" for x in d["conds"]) else "#17becf")); ax.text(a, y + 3, sg.split(" (")[0], fontsize=6.5)
        y += 0
    ax.set_xlim(-250, 1260); ax.set_ylim(-150, 150); ax.set_aspect("equal"); ax.set_xlabel("distance along the shaft from the lid gland, mm (side view, shaft drawn straight)")
    ax.set_title("RF2 system map: four sealed modules on one shaft bundle (MODELED; positions ASSUMED). Pink = bundle with HV pair, cyan = LV only", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rf2_system_map.png"), dpi=130); plt.close(fig)
if __name__ == "__main__":
    sys.exit(0 if main()["all_pass"] else 1)
