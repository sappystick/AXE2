#!/usr/bin/env python3
"""RF2 continuous-boost ratings (2026-10-30, owner: the trigger may be held indefinitely; the only penalty is battery life). Every part in the transmit path is checked for
CONTINUOUS operation in the boost mode, and in the scan mode for comparison. MODELED: currents and energies follow from the coil model and the pulse timing (HANDOFF section 8,
rf2_wiring); ratings are the datasheet values already logged in docs/DATASHEET_LOG_ARX.md; ASSUMED items are marked and are where a rating cannot be checked yet.
Design point (owner decision 2026-10-31, HANDOFF section 56; one source: rf2/rf2_drive.py): 8.94 A scan / 14.14 A boost, flat-top 318 us, clamp 477 V,
TX switches Q1 / Q2 onsemi NTBG080N120SC1 (was 8.06 / 12.74 A, 300 us, 460 V, Wolfspeed C3M0280090J). Pulse train: 400 Hz; pulses alternate T1 (ramp to I)
and T1 + T_FLAT (flat-top); turn-off into the clamp (fall time L I / V); critically damped by Rd 408 ohm across the coil. The TXD is a pod on the shaft at s 400
(rf2_chassis / rf2_system): the cord's TX strips run head -> pod only (rf2_cordflex).
Writes rf2/results/rf2_continuous.json.   usage: python3 rf2/rf2_continuous.py"""
import os, sys, json, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "rf2", "results"); os.makedirs(OUT, exist_ok=True)
import rf2_drive as DRV
L, R_COIL, VBUS, F, V_CLAMP, RD, T_FLAT = DRV.L_COIL, DRV.R_COIL, DRV.VBUS, DRV.F_PULSE, DRV.V_CLAMP, DRV.RD, DRV.T_FLAT   # VBUS 7 x 3.6 V nominal
# R_COIL 0.601 ohm at 20 C (2026-10-30, rf2_wire_options): Rubadue 66/38 litz, 1056 CM over 18.3 m; was 0.53 (unsourced, CORRECTIONS)
import rf2_cordflex as _CFX
R_CABLE = _CFX.R_TX_LOOP                                   # the cord flex's TX strips out and back, head -> TXD pod (2026-10-31: 0.145 ohm; was 0.280 head -> chassis)
MODES = {"scan": DRV.I_SCAN, "boost (trigger held, continuous)": DRV.I_BOOST}
TA = 40.0                                                     # ambient for the ratings, C (ASSUMED: sun on a desert dig)
SW = DRV.SWITCH
RDS_HOT, R_SHUNT = DRV.RDS_HOT, DRV.R_SHUNT                   # 166 mohm: NTBG080N120SC1 121 mohm typ at 150 C x 110 / 80 (max / typ, ASSUMED to hold hot)
R_LOOP = DRV.r_loop(R_CABLE)                                  # the ramp is resistance-limited (rf2_txd_spice)
F_PWM_MAX = 500e3                                             # flat-top hysteretic PWM, worst case (rf2_txd_spice with the NTBG: 192-471 kHz over the cases at the +-40 mA band; ASSUMED upper bound)
RTH_HS = 7.0                                                  # Ohmite D Series TO-263 (D2) extruded heat sink, natural convection at about 6 W: about 43 K case rise (READ from the
                                                              # heat-dissipation graph, data/datasheets/Ohmite_D_Series_heatsink.pdf); vented to outside air on the TXD pod
RTH_CS = 0.5                                                  # case -> heat sink interface (ASSUMED)
V_FILM, V_PR03, V_US3M = 630.0, 750.0, 1000.0                 # clamp film capacitor (630 V class, part to choose: ASSUMED), Vishay PR03 Umax (DATASHEET_LOG), US3M VRRM (Nexperia)
def pulse_train(I): return DRV.pulse_train(I, R_CABLE)
def analyse(mode, I):
    p = pulse_train(I); r = dict(mode=mode, **{k: round(v, 4) for k, v in p.items()}); rows = []
    def row(part, load, rating, unit, ok, src, note=""):
        rows.append(dict(part=part, load=round(load, 3), rating=rating, unit=unit, margin=(round(rating / load, 2) if isinstance(rating, (int, float)) and load > 0 else None), ok=ok, source=src, note=note))
    E_store = 0.5 * L * I ** 2
    # coil (litz): I^2 R; the head is potted, so this is heat into the coil channel
    P_coil = p["I_rms_coil"] ** 2 * R_COIL
    row("coil, 26 turns FEP litz (I^2 R)", P_coil, None, "W", None, "R %.3f ohm (rf2_wire_options: Rubadue 66/38 litz)" % R_COIL, "no rating: a thermal limit. Surface rise of the whole head at h = 8 W/m2K over 0.097 m2 (natural convection, ASSUMED): %.1f K; the rise inside the foam-potted channel is NOT modeled" % (P_coil / (8 * 0.097)))
    # transmit switch Q1 onsemi NTBG080N120SC1 (Rev. 4, 2023-01)
    eon_off = DRV.e_switch(I, V_CLAMP)[1]                      # turn-off into the clamp: EOFF 46 uJ at 800 V / 20 A, scaled linearly (ASSUMED)
    eon_b, eoff_b = DRV.e_switch(I, DRV.V_FULL)                # flat-top PWM edges at the bus (worst: full pack), both edges
    P_pwm = F * 0.5 * F_PWM_MAX * T_FLAT * FLAT_EDGES_FRAC * (eon_b + eoff_b)
    P_sw = p["I_rms_switch"] ** 2 * RDS_HOT + F * eon_off + P_pwm
    row(f"TX switch Q1 {SW['part']}: peak current", I, SW["idm"], "A (IDM)", I <= SW["idm"] * 0.8, f"{SW['rev']}: IDM 110 A (TC 25 C, repetitive)", "80 % of the pulsed rating")
    row("TX switch Q1: RMS current", p["I_rms_switch"], SW["id100"], "A (ID at TC 100 C)", p["I_rms_switch"] <= SW["id100"], f"{SW['rev']}: ID 21 A at TC 100 C")
    tj_pcb = TA + P_sw * SW["rthja"]; tj_hs = TA + P_sw * (SW["rthjc"] + RTH_CS + RTH_HS)
    row("TX switch Q1: junction temperature", tj_hs, SW["tj_max"], "C (TJ max)", tj_hs <= 125.0, f"{SW['rev']}: RthJC 0.84 C/W, RthJA 40 C/W, TJ max 175 C",
        "%.2f W (conduction %.2f at RDS %.0f mohm hot, turn-off %.3f, flat-top PWM %.3f); with the Ohmite D Series TO-263 heat sink (7 C/W natural convection, READ) TJ %.0f C; on bare PCB (RthJA 40) TJ %.0f C. Derated limit 125 C"
        % (P_sw, p["I_rms_switch"] ** 2 * RDS_HOT, RDS_HOT * 1e3, F * eon_off, P_pwm, tj_hs, tj_pcb))
    vds = V_CLAMP + 1.7                                        # clamp + US3M VF max (Nexperia 1.7 V at 3 A)
    row("TX switches Q1 / Q2: peak VDS (clamp + diode drop)", vds, 0.8 * SW["vdss"], "V (80 % of VDSS 1200 V)", vds <= 0.8 * SW["vdss"], f"{SW['rev']}: VDSS 1200 V", "rule 6: >= 630 V part")
    row("TX switch Q1: stored energy if the clamp opens (single avalanche)", E_store * 1e3, SW["eas_J"] * 1e3, "mJ (EAS, start TJ 25 C)", E_store <= SW["eas_J"] and I <= SW["eas_ias"],
        f"{SW['rev']}: EAS 171 mJ (IAS 18.5 A, L 1 mH)", "fault case only (a clamp diode open); not a repetitive rating")
    P_q2 = p["I_rms_q2"] ** 2 * RDS_HOT; tj_q2 = TA + P_q2 * SW["rthja"]
    row("freewheel switch Q2 (NTBG080N120SC1, PCB, no heat sink): junction temperature", tj_q2, SW["tj_max"], "C (TJ max)", tj_q2 <= 125.0, f"{SW['rev']}: RthJA 40 C/W",
        "%.2f W conduction (RMS %.2f A over the freewheel share of the flat-top); derated limit 125 C" % (P_q2, p["I_rms_q2"]))
    r["P_switch_W"] = round(P_sw, 3); r["P_q2_W"] = round(P_q2, 3)
    # clamp diode US3M and the clamp absorber
    q = 0.5 * I * p["fall_us"] * 1e-6; i_avg_d = F * q
    row("clamp diode US3M: average current", i_avg_d, 3.0, "A (IO at TT 75 C)", i_avg_d <= 3.0 * 0.5, "DS37228 rev 5: IO 3 A, IFSM 120 A, 1000 V")
    row("clamp diode US3M: peak current", I, 120.0, "A (IFSM, 8.3 ms)", True, "DS37228", "each pulse is about %.0f us long at up to %.1f A; repetitive peak not given (ADVANCED INFORMATION sheet)" % (p["fall_us"], I))
    row("clamp diode US3M: reverse voltage at the clamp", V_CLAMP, 0.8 * V_US3M, "V (80 % of VRRM 1000 V)", V_CLAMP <= 0.8 * V_US3M, "Nexperia US3M 2025-01-20: VRRM 1000 V", "rule 6: >= 630 V part")
    row("clamp film capacitor (630 V class, part to choose): clamp voltage", V_CLAMP, 0.8 * V_FILM, "V (80 % of 630 V, ASSUMED derating)", V_CLAMP <= 0.8 * V_FILM, "630 V class (part to choose; rule 6)", "ASSUMED rating until a part is chosen")
    row("Rd: 2 x Vishay PR03 806 ohm in parallel, voltage per part", V_CLAMP, V_PR03, "V (Umax AC/DC)", V_CLAMP <= V_PR03, "Vishay PR01/02/03 doc 28729 (2025-07-08): Umax 750 V", "each part sees the full clamp voltage; rule 6: >= 630 V")
    e_rd_clamp = V_CLAMP ** 2 / RD * p["fall_us"] * 1e-6; e_rd_on = VBUS ** 2 / RD * (p["T1_us"] * 1e-6 + 0.5 * T_FLAT)
    P_rd = F * (e_rd_clamp + e_rd_on)
    row("damping resistor Rd 408 ohm (across the coil)", P_rd, None, "W", None, "power from V^2 / R during the clamp and the on-time",
        "needs a >= %.1f W, >= 630 V resistor (rule 6) at %.0f C; it is on the HV fin in the potted head (thermal: OPEN)" % (2 * P_rd, TA + 30))
    P_clamp = F * max(0.0, E_store - e_rd_clamp)
    row("clamp absorber (TVS / zener stack or regenerative clamp)", P_clamp, None, "W", None, "0.5 L I^2 per pulse less the share Rd takes",
        "a dissipative %.0f V clamp must sink %.1f W continuously; a regenerative clamp returns most of it to the bulk bank (recommended for continuous boost)" % (V_CLAMP, P_clamp))
    # cable, PCB copper, shunt, bulk bank
    row("cord flex TX strips head -> TXD pod (I^2 R)", p["I_rms_coil"] ** 2 * R_CABLE, None, "W", None, "R %.3f ohm both strips (rf2_cordflex: %.2f mm x %.3f m, 2 oz)" % (R_CABLE, _CFX.W_TX, _CFX.TX_LEN_M),
        "spread over %.2f m of strip pair; width set by IPC-2221 at this rms (rf2_cordflex)" % _CFX.TX_LEN_M)
    def ipc2221_dT(i, width_mm, oz=1.0, k=0.048):
        area_mil2 = width_mm / 0.0254 * 1.378 * oz; return (i / (k * area_mil2 ** 0.725)) ** (1 / 0.44)
    dT_txf = ipc2221_dT(p["I_rms_coil"] / 2, 2.5)            # the bus is on both layers: half the current each
    row("TXF fin buses (2.5 mm, both layers, 1 oz ASSUMED)", dT_txf, 10.0, "K rise (IPC-2221)", dT_txf <= 10.0, "IPC-2221 external-layer formula", "RMS %.2f A per layer; peak %.1f A for under 0.5 ms" % (p["I_rms_coil"] / 2, I))
    P_sh = p["I_rms_switch"] ** 2 * 0.010
    row("current shunt Vishay WSL2512 10 mohm", P_sh, 1.0, "W at 70 C", P_sh <= 0.5, "WSL rev 23-Nov-2023", "50 % derating")
    i_cap = math.sqrt(max(p["I_rms_switch"] ** 2 - (F * (0.5 * I * p["T1_us"] * 1e-6 + 0.5 * I * T_FLAT)) ** 2, 0)) / 9
    row("bulk bank: 9 x Panasonic EEHZC1H101P, ripple per capacitor", i_cap, 1.6, "A rms (100 kHz, 105 C)", i_cap <= 1.6 * 0.7, "ZC series ZC-16", "70 % derating; the pulse frequency is 400 Hz, where the ripple rating is lower than at 100 kHz (frequency multiplier not read: OPEN)")
    # battery and fuse
    P_ohmic_on = F * (p["ramp_i2_As"] * R_LOOP + 0.5 * I ** 2 * T_FLAT * R_LOOP
                      + 0.5 * T_FLAT * (1 - DRV.FLAT_Q1_DUTY) * 1.2 * I)   # freewheel: Q2 + shunt carry the current over the rest of the flat-top, US3M drop about 1.2 V (rf2_txd_spice topology)
    P_tx_dissipative = F * E_store + P_ohmic_on + P_sw * 0.3 + P_rd * 0.1
    P_tx_regen = F * E_store * 0.25 + P_ohmic_on + P_sw * 0.3 + P_rd * 0.1   # regenerative clamp recovering about 75 % (ASSUMED)
    P_head = 5.0 * 0.54 / 0.9 + 5.0 * 1.372 / 0.9                           # +5 V rail budget and the LED rail at its cap, converter efficiency 90 % (rf2_wiring)
    for name, ptx in (("dissipative clamp", P_tx_dissipative), ("regenerative clamp (75 % recovery ASSUMED)", P_tx_regen)):
        pin = ptx + P_head; ib = pin / 25.2
        r.setdefault("battery", {})[name] = dict(P_tx_W=round(ptx, 2), P_head_W=round(P_head, 2), P_total_W=round(pin, 2), I_battery_A=round(ib, 2),
                                                  Wh_per_hour=round(pin, 1), runtime_h_per_100Wh=round(100.0 / pin, 2))
    # the TXD pod feed (cord piece 2 VIN_T / GND_T): the pod's own bulk bank smooths the 400 Hz pulses; rms = mean x 1.1 (ASSUMED), at the pack cut-off
    i_feed = P_tx_regen / DRV.V_CUTOFF * 1.1
    row("cord flex VIN_T / GND_T (TXD pod feed) vs its design current", i_feed, _CFX.I_FEED, "A rms (IPC-2221 width basis)", i_feed <= _CFX.I_FEED, "rf2_cordflex I_FEED (W %.2f mm, 2 oz)" % _CFX.W_FEED,
        "P_tx %.1f W (regenerative clamp) at %.1f V cut-off, x 1.1 ripple (ASSUMED)" % (P_tx_regen, DRV.V_CUTOFF))
    r["I_feed_A"] = round(i_feed, 3)
    r["rows"] = rows; r["fails"] = [x["part"] for x in rows if x["ok"] is False]; r["unrated"] = [x["part"] for x in rows if x["ok"] is None]
    return r
FLAT_EDGES_FRAC = 1.0                                         # every PWM cycle has one turn-on and one turn-off edge (both counted in e_switch's sum)
def main():
    res = dict(status="MODELED: loads from the pulse timing; ratings from logged datasheets; heat sinks, the clamp absorber, the head's internal thermal path and the battery pack are OPEN",
               design_point=dict(I_scan_A=DRV.I_SCAN, I_boost_A=round(DRV.I_BOOST, 3), T_flat_us=round(T_FLAT * 1e6), V_clamp_V=V_CLAMP, switch=SW["part"], RDS_hot_ohm=round(RDS_HOT, 4),
                                 R_tx_loop_ohm=round(R_CABLE, 4), txd_s_mm=DRV.TXD_S_MM, source="rf2/rf2_drive.py (owner decision 2026-10-31)"),
               ambient_C=TA, modes=[analyse(m, i) for m, i in MODES.items()])
    b = next(m for m in res["modes"] if m["mode"].startswith("boost"))
    res["cordflex_consistent"] = abs(b["I_rms_coil"] - _CFX.I_TX) < 1e-3                       # the cord's TX strips were sized at this rms
    res["verdict"] = dict(boost_fails=b["fails"], boost_unrated=b["unrated"], note="continuous boost is feasible for the rated parts listed as ok; the unrated items need a thermal design (heat sink, regenerative clamp, Rd power rating) before 'indefinite' can be claimed")
    json.dump(res, open(os.path.join(OUT, "rf2_continuous.json"), "w"), indent=1)
    for m in res["modes"]:
        print(f"== {m['mode']}: I {m['I_pk']:.2f} A, T1 {m['T1_us']:.0f} us, fall {m['fall_us']:.1f} us, coil RMS {m['I_rms_coil']:.2f} A, switch RMS {m['I_rms_switch']:.2f} A")
        for x in m["rows"]: print(f"   {'OK  ' if x['ok'] else ('FAIL' if x['ok'] is False else '----')} {x['part'][:58]:<58} {x['load']:>8} {x['unit']:<20} {x['note'][:90]}")
        for k, v in m["battery"].items(): print(f"   battery, {k}: {v}")
    print("cord flex sized at this boost rms:", res["cordflex_consistent"])
    return res
if __name__ == "__main__":
    main()
