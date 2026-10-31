#!/usr/bin/env python3
"""RF2 continuous-boost ratings (2026-10-30, owner: the trigger may be held indefinitely; the only penalty is battery life). Every part in the transmit path is checked for
CONTINUOUS operation in the boost mode, and in the scan mode for comparison. MODELED: currents and energies follow from the coil model and the pulse timing (HANDOFF section 8,
rf2_wiring); ratings are the datasheet values already logged in docs/DATASHEET_LOG_ARX.md; ASSUMED items are marked and are where a rating cannot be checked yet.
Pulse train: 400 Hz; pulses alternate T1 (ramp to I) and T1 + 300 us (flat-top); turn-off into the 460 V clamp (fall time L I / V); critically damped by Rd 408 ohm across the coil.
Writes rf2/results/rf2_continuous.json.   usage: python3 rf2/rf2_continuous.py"""
import os, json, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "rf2", "results"); os.makedirs(OUT, exist_ok=True)
L, R_COIL, R_CABLE, VBUS, F, V_CLAMP, RD, T_FLAT = 333e-6, 0.601, 0.11, 25.2, 400.0, 460.0, 408.0, 300e-6   # VBUS 7 x 3.6 V nominal (was 26.0; 2026-10-31)
# R_COIL 0.601 ohm at 20 C (2026-10-30, rf2_wire_options): Rubadue 66/38 litz, 1056 CM over 18.3 m; was 0.53 (unsourced, CORRECTIONS)
import rf2_cordflex as _CFX
R_CABLE = _CFX.R_TX_LOOP                                   # 2026-10-31: the cord flex's TX strips out and back (was 0.11 ohm for the wire pair, CORRECTIONS)
MODES = {"scan": 8.06, "boost (trigger held, continuous)": 8.06 * math.sqrt(2.5)}
TA = 40.0                                                     # ambient for the ratings, C (ASSUMED: sun on a desert dig)
RDS_HOT, R_SHUNT = 0.416 * 1.1, 0.010
R_LOOP = R_COIL + R_CABLE + RDS_HOT + R_SHUNT                 # the ramp is resistance-limited (rf2_txd_spice: 139 us to 8.06 A at 25.2 V, not L I / V = 107 us)
def pulse_train(I):
    tau = L / R_LOOP; imax = VBUS / R_LOOP; T1 = -tau * math.log(1 - I / imax); tf = L * I / V_CLAMP
    tt = [T1 * k / 400 for k in range(401)]; ir = [imax * (1 - math.exp(-x / tau)) for x in tt]
    ramp_i2 = sum((ir[k] ** 2 + ir[k + 1] ** 2) / 2 * (tt[k + 1] - tt[k]) for k in range(400)); ramp_i = sum((ir[k] + ir[k + 1]) / 2 * (tt[k + 1] - tt[k]) for k in range(400))
    # mean of i^2 over time: the exponential ramp (exact), flat-top I^2 T on every second pulse, the linear fall I^2 tf / 3
    i2 = F * (ramp_i2 + 0.5 * I ** 2 * T_FLAT + (I ** 2 / 3) * tf); ia = F * (ramp_i + 0.5 * I * T_FLAT + 0.5 * I * tf)
    sw_i2 = F * (ramp_i2 + 0.5 * I ** 2 * T_FLAT * 0.30)        # the switch carries the ramp, and about 30 % of the flat-top (duty, rf2_txd_spice); the freewheel Q2 carries the rest
    on_frac = F * (T1 + 0.5 * T_FLAT)
    return dict(I_pk=I, T1_us=T1 * 1e6, ramp_i2_As=ramp_i2, fall_us=tf * 1e6, I_rms_coil=math.sqrt(i2), I_avg_coil=ia, I_rms_switch=math.sqrt(sw_i2), on_fraction=on_frac)
def analyse(mode, I):
    p = pulse_train(I); r = dict(mode=mode, **{k: round(v, 4) for k, v in p.items()}); rows = []
    def row(part, load, rating, unit, ok, src, note=""):
        rows.append(dict(part=part, load=round(load, 3), rating=rating, unit=unit, margin=(round(rating / load, 2) if isinstance(rating, (int, float)) and load > 0 else None), ok=ok, source=src, note=note))
    E_store = 0.5 * L * I ** 2
    # coil (litz): I^2 R; the head is potted, so this is heat into the coil channel
    P_coil = p["I_rms_coil"] ** 2 * R_COIL
    row("coil, 26 turns FEP litz (I^2 R)", P_coil, None, "W", None, "R %.3f ohm (rf2_wire_options: Rubadue 66/38 litz)" % R_COIL, "no rating: a thermal limit. Surface rise of the whole head at h = 8 W/m2K over 0.097 m2 (natural convection, ASSUMED): %.1f K; the rise inside the foam-potted channel is NOT modeled" % (P_coil / (8 * 0.097)))
    # transmit switch C3M0280090J
    rds_hot = RDS_HOT                                          # 416 mohm typ at 150 C (datasheet) + 10 % (ASSUMED max at temperature)
    e_off = 2.4e-6 * (I / 7.5) * (V_CLAMP / 400.0)             # Eoff 2.4 uJ at 7.5 A / 400 V, scaled with I and V (ASSUMED linear)
    P_sw = p["I_rms_switch"] ** 2 * rds_hot + F * e_off
    row("TX switch Wolfspeed C3M0280090J: peak current", I, 22.0, "A (IDM)", I <= 22.0 * 0.8, "Rev 04: IDM 22 A", "80 % of the pulsed rating")
    row("TX switch: RMS current", p["I_rms_switch"], 7.0, "A (ID at TC 100 C)", p["I_rms_switch"] <= 7.0, "Rev 04: ID 7 A at TC 100 C")
    RTH_HS = 7.0                                               # Ohmite D Series TO-263 (D2) extruded heat sink, natural convection at about 6 W: about 43 K case rise (READ from the
                                                               # heat-dissipation graph, data/datasheets/Ohmite_D_Series_heatsink.pdf); was 5 C/W ASSUMED until 2026-10-30
    tj_pcb = TA + P_sw * 40.0; tj_hs = TA + P_sw * (2.5 + 0.5 + RTH_HS)
    row("TX switch: junction temperature", tj_hs, 150.0, "C (TJ max)", tj_hs <= 125.0, "Rev 04: RthJC 2.5 C/W, RthJA 40 C/W",
        "%.2f W; with the Ohmite D Series TO-263 heat sink (7 C/W natural convection, READ; aluminium: a fixed target at the neck, OPEN) TJ %.0f C; on bare PCB (RthJA 40) TJ %.0f C. Derated limit 125 C" % (P_sw, tj_hs, tj_pcb))
    # clamp diode US3M and the clamp absorber
    q = 0.5 * I * p["fall_us"] * 1e-6; i_avg_d = F * q
    row("clamp diode Diodes US3M: average current", i_avg_d, 3.0, "A (IO at TT 75 C)", i_avg_d <= 3.0 * 0.5, "DS37228 rev 5: IO 3 A, IFSM 120 A, 1000 V")
    row("clamp diode US3M: peak current", I, 120.0, "A (IFSM, 8.3 ms)", True, "DS37228", "each pulse is about %.0f us long at up to %.1f A; repetitive peak not given (ADVANCED INFORMATION sheet)" % (p["fall_us"], I))
    e_rd_clamp = V_CLAMP ** 2 / RD * p["fall_us"] * 1e-6; e_rd_on = VBUS ** 2 / RD * (p["T1_us"] * 1e-6 + 0.5 * T_FLAT)
    P_rd = F * (e_rd_clamp + e_rd_on)
    row("damping resistor Rd 408 ohm (across the coil)", P_rd, None, "W", None, "power from V^2 / R during the clamp and the on-time",
        "needs a >= %.1f W, >= 630 V resistor (rule 6) at %.0f C; it is on the HV fin in the potted head (thermal: OPEN)" % (2 * P_rd, TA + 30))
    P_clamp = F * max(0.0, E_store - e_rd_clamp)
    row("clamp absorber (TVS / zener stack or regenerative clamp)", P_clamp, None, "W", None, "0.5 L I^2 per pulse less the share Rd takes",
        "a dissipative 460 V clamp must sink %.1f W continuously; a regenerative clamp returns most of it to the bulk bank (recommended for continuous boost)" % P_clamp)
    # cable, PCB copper, shunt, bulk bank
    row("shaft HV pair (FEP AWG18, ASSUMED)", p["I_rms_coil"] ** 2 * R_CABLE, None, "W", None, "R 0.11 ohm both conductors (rf2_wiring)", "AWG18 carries well over 5 A continuously in free air; at %.2f A RMS it runs cool" % p["I_rms_coil"])
    def ipc2221_dT(i, width_mm, oz=1.0, k=0.048):
        area_mil2 = width_mm / 0.0254 * 1.378 * oz; return (i / (k * area_mil2 ** 0.725)) ** (1 / 0.44)
    dT_txf = ipc2221_dT(p["I_rms_coil"] / 2, 2.5)            # the bus is on both layers: half the current each
    row("TXF fin buses (2.5 mm, both layers, 1 oz ASSUMED)", dT_txf, 10.0, "K rise (IPC-2221)", dT_txf <= 10.0, "IPC-2221 external-layer formula", "RMS %.2f A per layer; peak %.1f A for under 0.5 ms" % (p["I_rms_coil"] / 2, I))
    P_sh = p["I_rms_switch"] ** 2 * 0.010
    row("current shunt Vishay WSL2512 10 mohm", P_sh, 1.0, "W at 70 C", P_sh <= 0.5, "WSL rev 23-Nov-2023", "50 % derating")
    i_cap = math.sqrt(max(p["I_rms_switch"] ** 2 - (F * (0.5 * I * p["T1_us"] * 1e-6 + 0.5 * I * T_FLAT)) ** 2, 0)) / 9
    row("bulk bank: 9 x Panasonic EEHZC1H101P, ripple per capacitor", i_cap, 1.6, "A rms (100 kHz, 105 C)", i_cap <= 1.6 * 0.7, "ZC series ZC-16", "70 % derating; the pulse frequency is 400 Hz, where the ripple rating is lower than at 100 kHz (frequency multiplier not read: OPEN)")
    # battery and fuse
    P_ohmic_on = F * (p["ramp_i2_As"] * (R_COIL + R_CABLE + rds_hot + R_SHUNT) + 0.5 * I ** 2 * T_FLAT * (R_COIL + R_CABLE + rds_hot + R_SHUNT)
                      + 0.5 * T_FLAT * 0.70 * 1.2 * I)          # freewheel: Q2 + shunt carry the current about 70 % of the flat-top, US3M drop about 1.2 V (rf2_txd_spice topology)
    P_tx_dissipative = F * E_store + P_ohmic_on + P_sw * 0.3 + P_rd * 0.1
    P_tx_regen = F * E_store * 0.25 + P_ohmic_on + P_sw * 0.3 + P_rd * 0.1   # regenerative clamp recovering about 75 % (ASSUMED)
    P_head = 5.0 * 0.54 / 0.9 + 5.0 * 1.372 / 0.9                           # +5 V rail budget and the LED rail at its cap, converter efficiency 90 % (rf2_wiring)
    for name, ptx in (("dissipative clamp", P_tx_dissipative), ("regenerative clamp (75 % recovery ASSUMED)", P_tx_regen)):
        pin = ptx + P_head; ib = pin / 25.2
        r.setdefault("battery", {})[name] = dict(P_tx_W=round(ptx, 2), P_head_W=round(P_head, 2), P_total_W=round(pin, 2), I_battery_A=round(ib, 2),
                                                  Wh_per_hour=round(pin, 1), runtime_h_per_100Wh=round(100.0 / pin, 2))
    r["rows"] = rows; r["fails"] = [x["part"] for x in rows if x["ok"] is False]; r["unrated"] = [x["part"] for x in rows if x["ok"] is None]
    return r
def main():
    res = dict(status="MODELED: loads from the pulse timing; ratings from logged datasheets; heat sinks, the clamp absorber, the head's internal thermal path and the battery pack are OPEN",
               ambient_C=TA, modes=[analyse(m, i) for m, i in MODES.items()])
    b = next(m for m in res["modes"] if m["mode"].startswith("boost"))
    res["verdict"] = dict(boost_fails=b["fails"], boost_unrated=b["unrated"], note="continuous boost is feasible for the rated parts listed as ok; the unrated items need a thermal design (heat sink, regenerative clamp, Rd power rating) before 'indefinite' can be claimed")
    json.dump(res, open(os.path.join(OUT, "rf2_continuous.json"), "w"), indent=1)
    for m in res["modes"]:
        print(f"== {m['mode']}: I {m['I_pk']:.2f} A, T1 {m['T1_us']:.0f} us, fall {m['fall_us']:.1f} us, coil RMS {m['I_rms_coil']:.2f} A, switch RMS {m['I_rms_switch']:.2f} A")
        for x in m["rows"]: print(f"   {'OK  ' if x['ok'] else ('FAIL' if x['ok'] is False else '----')} {x['part'][:58]:<58} {x['load']:>8} {x['unit']:<20} {x['note'][:90]}")
        for k, v in m["battery"].items(): print(f"   battery, {k}: {v}")
    return res
if __name__ == "__main__":
    main()
