#!/usr/bin/env python3
"""RF2 head v1 wiring, power and pulse timing (2026-10-29): every connection (conductors, net class, path, length), the ADC channel map, the power tree
with a load budget, and the transmit / receive timing (PWM). Checked: endpoints exist, HV never on flex and only in the HV sector (RF1 fold rule F7, rule 6),
analog / LV paths through declared slots, AD7389-4 channel limits, regulator margins, shaft-cable conductor count. MODELED; loads ASSUMED (marked).
Outputs: out/rf2_wiring.json, out/rf2_wiring.png.  usage: python3 rf2/head/rf2_wiring.py"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_head as H
S = H.SPEC; BI = S["boards_inner"]; HEEL = H.HEEL
EXTERNAL = {"NECK": "neck module at the shaft base: TX driver (baseline PB1R topology, 630 V parts), clamp about 460 V, flat-top PWM current loop",
            "HANDLE": "handle: battery 7S, PM2 power switch / fuse, HB2 controls, AU1 audio (speaker)",
            "REF3": "3-axis reference coil on the shaft, 0.6 m from the head (EMI canceller input)"}
POS = {k: tuple(v["c"]) if "c" in v else (0.0, 0.0) for k, v in BI.items()}
POS.update(QA_PADS=(0.0, 33.0), QB_PADS=(-16.1, 16.1), SH1_GND=H.pol(28.0, 22.5), COIL_LEADS=H.pol(109.0, HEEL), GLAND=tuple(S["gland"]["c"]), LED=(0.0, 45.0))
def dist(a, b): return math.hypot(POS[a][0] - POS[b][0], POS[a][1] - POS[b][1])
# id, from, to, medium, net class, conductors, path (sectors / slots), note
CONN = [
    ("C01", "COIL_LEADS", "TXJ", "litz ends", "HV", ["TX_A", "TX_B"], ["coil channel lead slot 178", "hv"], "coil to wire-hole pads; potted in epoxy"),
    ("C02", "TXJ", "GLAND", "shaft cable, HV pair (630 V insulation, own jacket)", "HV", ["TX_A", "TX_B"], ["hv", "lid gland"], "to the NECK driver"),
    ("C03", "TXJ", "MP1", "2 short wires in the tray HV slots", "HV", ["COIL_SENSE", "COIL_RET"], ["hv"], "MP1 input side; >= 1.0 mm on both boards"),
    ("C04", "MP1", "AB1B", "2-layer flex jumper, hatched ground", "analog", ["MONO_OUT", "+5VA", "AGND"], ["hv", "wall 156 LV slot", "analog"], "MP1 output side only (low voltage after the protection)"),
    ("C05", "QA_PADS", "AB1A", "flex tail soldered to the SB1R pads", "analog", ["QA_P", "QA_N"], ["under tower", "tower slot 106", "analog"], "the quadrupole tails"),
    ("C06", "QB_PADS", "AB1B", "flex tail soldered to the SB1R pads", "analog", ["QB_P", "QB_N"], ["under tower", "tower slot 137", "analog"], ""),
    ("C07", "SH1_GND", "AB1A", "0.5 mm wire up the 22.5 deg stack hole", "analog", ["SHIELD"], ["stack hole 22.5", "under tower", "tower slot 106", "analog"], "single-point shield ground to AB1A AGND"),
    ("C08", "CB1D", "AB1A", "rigid-flex hinge (RF1 concept C)", "digital", ["SCLK", "CS", "SDO1", "SDO2", "+5V", "GND"], ["tower slot 106", "analog"], "ADC data, power in"),
    ("C09", "CB1D", "AB1B", "rigid-flex hinge", "digital", ["SCLK", "CS", "SDO1", "SDO2", "+5V", "GND"], ["tower slot 137", "analog"], ""),
    ("C10", "CB1D", "LED", "rigid-flex hinge flap (up)", "digital", ["+5V_LED", "+5V_LED", "GND", "GND"] + [f"C{c}_{k}0" for c in range(1, 5) for k in ("D", "K")], ["digital"],
     "LR1 display: 4 parallel SK9822-EC20 chains (rf2_ledgrid), one RP2354A PIO state machine each; dark during receive windows, power-gated when silent"),
    ("C11", "GLAND", "CB1D", "shaft cable, LV cores (separate sleeve, >= 10 mm from the HV pair)", "power/digital",
     ["VIN", "GND", "TXCMD_P", "TXCMD_N", "TXSTAT_P", "TXSTAT_N", "DATA_P", "DATA_N"], ["hv (sleeved, along the 198 wall)", "tower slot 186", "digital"], "power in, TX timing out, link to the handle"),
    ("C12", "GLAND", "AB1A", "shaft cable, 3 shielded twisted pairs", "analog", ["REFX_P", "REFX_N", "REFY_P", "REFY_N", "REFZ_P", "REFZ_N"], ["hv (sleeved)", "wall 156 LV slot", "analog (over AB1B, z 11-13)"], "from REF3 on the shaft"),
]
ADC = {"AB1A": ["QA", "REFX", "REFY", "REFZ"], "AB1B": ["QB", "MONO", "spare", "spare"]}
SHAFT = dict(hv_pair=["TX_A", "TX_B"], lv=[c for c in CONN if c[0] == "C11"][0][5], ref=[c for c in CONN if c[0] == "C12"][0][5])
POWER = dict(
    source="VIN about 24 V (7S pack 25.2 V nominal, switched and fused by PM2 in the handle) down the shaft",
    rails=[dict(rail="+5V", regulator="LMR36015 on CB1D (TI SNVSB49D: 4.2-60 V in, 1.5 A)", rating_A=1.5,
                loads_A={"AB1A analog (ASSUMED)": 0.04, "AB1B analog (ASSUMED)": 0.04, "MP1 (ASSUMED)": 0.02, "+3V3 LDO input": 0.09}),
           dict(rail="+5V_LED (display, own buck, power-gated)", regulator="LMR36520 on CB1D (TI Rev. C: 4.2-65 V in, 70 V transient, 2 A) + TPS22918 load switch "
                "(TI Rev. C: 1-5.5 V, 2 A continuous, 52 mohm); off whenever the display is dark (silent until a detection)", rating_A=2.0,
                loads_A={"522 x SK9822-EC20 static current (OPSCO Rev. A/0: IDD 1 mA typ)": 0.522, "lit LEDs, firmware brightness cap": 0.85}),
           dict(rail="+3V3", regulator="TLV755P on CB1D (500 mA)", rating_A=0.5, loads_A={"RP2354A + flash + misc (ASSUMED)": 0.08}),
           dict(rail="+3V3D (each AB1)", regulator="local TLV755P (RF1)", rating_A=0.5, loads_A={"AD7389-4 digital + logic (ASSUMED)": 0.01})],
    tx="the TX current never enters the head's electronics: NECK driver runs from VIN with its own bulk bank (baseline PB1R topology)")
L = S["coil"]["L_uH"] * 1e-6; I = S["coil"]["I_A"]; VB = 26.0; RC = 0.53; RCAB = 0.11
TIMING = dict(
    pulse_rate_Hz="400 nominal, chosen per site in 380-420 to sit off VLF stations (rf2_emi: fixed rate beats blind jitter); listen-only: 1 frame in 16 without pulses",
    scan=dict(I_A=I, T1_us=round(L * I / VB * 1e6, 1), T2_us=round(L * I / VB * 1e6 + 300, 1), order="T1 and T2 alternate pulse by pulse (multi-period ground balance, rf2_ground)"),
    flat_top_pwm=dict(where="NECK driver current loop", f_kHz="200 (ASSUMED)", duty=round(I * (RC + RCAB) / VB, 3), note="holds I during the 300 us flat-top; duty = I (R_coil + R_cable) / VBUS"),
    boost=dict(trigger="pinpoint (rf2_pinpoint)", energy_x=2.5, I_A=round(I * math.sqrt(2.5), 2), T1_us=round(L * I * math.sqrt(2.5) / VB * 1e6, 1), limit="a few seconds; FET 20 A rating"),
    turn_off=dict(clamp_V=460, damping="critical, Rd = 0.5 sqrt(L / C) = %.0f ohm (C 500 pF ASSUMED)" % (0.5 * math.sqrt(L / 500e-12)), first_gate_us=16.3),
    gates_us=[round(16.3 * 1.618 ** k, 1) for k in range(9)],
    led="LED stream only after the last gate and before the next pulse, dark during receive windows; 4 chains clocked in parallel at 8 MHz (SK9822-EC20 max 15 MHz)",
    adc="AD7389-4 on each AB1, SCLK >= 27.2 MHz (3 frames in the first gate, baseline fw timing)")
def checks():
    known = set(BI) | set(S["boards"]) | {"QA_PADS", "QB_PADS", "SH1_GND", "COIL_LEADS", "GLAND"} | set(EXTERNAL)
    ends_ok = all(c[1] in known and c[2] in known for c in CONN)
    hv = [c for c in CONN if c[4] == "HV"]
    hv_ok = all("flex" not in c[3] for c in hv) and all(all(p.startswith(("hv", "coil channel", "lid gland")) for p in c[6]) for c in hv)
    # every slot a path uses is probed in the real solids: a 2 mm cube at the slot must not intersect the part (the opening exists)
    import manifold3d as m3
    P = H.parts(); probe = lambda x, y, z: m3.Manifold.cube([2, 2, 2], True).translate([x, y, z])
    SLOT = {"tower slot 106": ("CB1D_TOWER", (*H.pol(39.9, 106.0), 9.0)), "tower slot 137": ("CB1D_TOWER", (*H.pol(39.9, 137.0), 9.0)),
            "tower slot 186": ("CB1D_TOWER", (*H.pol(39.9, 186.0), 9.0)), "wall 156 LV slot": ("BAY_WALLS", (*H.pol(74.0, 156.0), 10.0)),
            "coil channel lead slot 178": ("COIL_CHANNEL", (*H.pol(108.9, 178.0), 10.0)), "stack hole 22.5": ("BOARD_QB", (*H.pol(28.0, 22.5), 2.8)),
            "lid gland": ("LID", (*S["gland"]["c"], 24.6))}
    probes = {k: round((P[part] ^ probe(*xyz)).volume(), 4) for k, (part, xyz) in SLOT.items()}
    used = {p for c in CONN for p in c[6] if p.startswith(("tower slot", "wall", "stack hole", "coil channel", "lid gland"))}
    slot_ok = all(u in probes and probes[u] == 0.0 for u in used)
    adc_ok = all(len(v) <= 4 for v in ADC.values())
    pw = [dict(rail=r["rail"], load_A=round(sum(r["loads_A"].values()), 3), rating_A=r["rating_A"], margin=round(1 - sum(r["loads_A"].values()) / r["rating_A"], 2)) for r in POWER["rails"]]
    pw_ok = all(p["margin"] >= 0.3 for p in pw)
    # LED stream: the longest chain's frame (32-bit start, 32 bits per LED, N/2 end clocks) at 8 MHz must fit the quiet slot of the fastest pulse rate
    import rf2_ledgrid as LG
    n_max = max(LG.summary()["chain_lengths"]); f_clk = 8e6; t_led_us = (32 + 32 * n_max + math.ceil(n_max / 2)) / f_clk * 1e6
    quiet_us = 1e6 / 420 - TIMING["scan"]["T2_us"] - TIMING["gates_us"][-1] - 50.0
    led_ok = t_led_us < quiet_us
    lengths = {c[0]: round(dist(c[1], c[2]) * (1.3 if "flex" in c[3] or "hinge" in c[3] else 1.15) + 15, 0) for c in CONN if c[1] in POS and c[2] in POS}
    return dict(endpoints_exist=ends_ok, hv_not_on_flex_and_only_in_hv_sector=hv_ok, every_slot_open_in_the_solids=slot_ok, slot_probe_overlap_mm3=probes, adc_channels_within_4=adc_ok,
                power=pw, power_margin_ge_30pct=pw_ok, led_stream=dict(longest_chain=n_max, clock_MHz=8, frame_us=round(t_led_us, 1), quiet_slot_us=round(quiet_us, 1), fits=led_ok), shaft_cable=dict(hv=2, lv=len(SHAFT["lv"]), ref=len(SHAFT["ref"]), total=2 + len(SHAFT["lv"]) + len(SHAFT["ref"])),
                lengths_mm_estimate=lengths, ok=ends_ok and hv_ok and slot_ok and adc_ok and pw_ok and led_ok)
def figure(path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle, Wedge
    fig, ax = plt.subplots(figsize=(9, 9)); R = S["envelope"]["R"]
    ax.add_patch(Circle((0, 0), R, fc="#f6f6f6", ec="#333")); ax.add_patch(Circle((0, 0), 110.2, fc="none", ec="#b8620f", lw=2))
    ax.add_patch(Wedge((0, 0), 108, *S["sectors"]["hv"], fc="#f6d5d0", alpha=0.6)); ax.add_patch(Wedge((0, 0), 108, *S["sectors"]["analog"], fc="#d5e6f6", alpha=0.6))
    for k, v in BI.items():
        if v["kind"] == "disc": ax.add_patch(Circle(v["c"], v["r"], fc="#fff", ec="#444")); ax.text(*v["c"], k, ha="center", va="center", fontsize=8)
        elif v["kind"] == "box": ax.add_patch(Rectangle((v["c"][0] - v["size"][0] / 2, v["c"][1] - v["size"][1] / 2), *v["size"], fc="#fff", ec="#b03a2e")); ax.text(*v["c"], k, ha="center", va="center", fontsize=7)
    col = {"HV": "#c0392b", "analog": "#1f77b4", "digital": "#2e7d32", "power/digital": "#6a3d9a"}
    for c in CONN:
        if c[1] in POS and c[2] in POS:
            a, b = POS[c[1]], POS[c[2]]; ax.plot([a[0], b[0]], [a[1], b[1]], color=col[c[4]], lw=2.2 if c[4] == "HV" else 1.4, alpha=0.85)
            ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, c[0], fontsize=7, color=col[c[4]])
    for k in ("QA_PADS", "QB_PADS", "SH1_GND", "GLAND"): ax.plot(*POS[k], "ks", ms=4); ax.text(POS[k][0] + 2, POS[k][1] + 2, k, fontsize=7)
    ax.text(-115, -120, "red HV | blue analog | green digital | purple power + data\nC01-C12: see rf2_wiring.json and HANDOFF_RF2.md", fontsize=8)
    ax.set_xlim(-122, 122); ax.set_ylim(-125, 122); ax.set_aspect("equal"); ax.axis("off"); ax.set_title("RF2 head v1: connections (plan, MODELED)", loc="left", fontsize=10)
    plt.tight_layout(); plt.savefig(path, dpi=140)
if __name__ == "__main__":
    ck = checks(); res = dict(status="MODELED wiring / power / timing plan (loads ASSUMED where marked)", external=EXTERNAL,
                              connections=[dict(id=c[0], frm=c[1], to=c[2], medium=c[3], net_class=c[4], conductors=c[5], path=c[6], note=c[7]) for c in CONN],
                              adc_map=ADC, shaft_cable=SHAFT, power=POWER, timing=TIMING, checks=ck)
    json.dump(res, open(os.path.join(H.OUT, "rf2_wiring.json"), "w"), indent=1); figure(os.path.join(H.OUT, "rf2_wiring.png"))
    print(json.dumps(ck, indent=0)[:1500])
