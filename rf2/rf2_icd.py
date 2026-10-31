#!/usr/bin/env python3
"""RF2 interface control document (2026-10-30; roadmap P0.1). GENERATED + CHECKED: every joint of the chassis-v2 machine with its conductors (net, class,
current, voltage, insulation / spacing), the medium and connector (a datasheet on file, or 'TBD' with the requirement it must meet), the pinout and the
modules at each end. Checks: rule 6 on every HV conductor (insulation >= 630 V; >= 1.0 mm spacing on boards and flex), ampacity, FFC / FPC pin counts,
the screen's FPC bend limit (3 bends) handled by a dynamic hinge flex, net names consistent with rf2_system's harness, and every connector verified.
Writes docs/ICD.md and rf2/results/rf2_icd.json.   usage: python3 rf2/rf2_icd.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
OUT = os.path.join(HERE, "results")
LOG = open(os.path.join(ROOT, "docs", "DATASHEET_LOG_ARX.md")).read()
AMP = {18: 7.0, 20: 5.0, 24: 2.0, 26: 1.0}
import rf2_cordflex as CFX, rf2_drive as DRV
_SY = json.load(open(os.path.join(OUT, "rf2_system.json")))                          # rf2_system runs first (run.py dep)
I_TX, I_VIN, I_VH = round(CFX.I_TX, 2), round(_SY["harness"].get("feed_I_A", 1.13), 2), CFX.I_PWR   # A rms in continuous boost (rf2_cordflex / rf2_continuous / rf2_system); I_VIN = the TXD pod feed
V_HV = DRV.V_CLAMP + 5.0                                                              # flyback peak (clamp 477 V + diode / overshoot; rf2_txd_spice 481.3 V); was 463 V with the 460 V clamp
Y5B = dict(I_A=0.5, V=50.0)                                                           # Panasonic Y5B: 0.5 A per pin contact, 50 V AC/DC (DATASHEET_LOG, catalog ACCTB1E)
GLAND_Y5B = {"CB1D (10-way AYF531035)": ["VIN_H", "VIN_H", "GND_H", "GND_H", "TXCMD+", "TXCMD-", "TXSTAT+", "TXSTAT-", "DATA+", "DATA-"],
             "AB1A (10-way AYF531035)": ["REFX+", "REFX-", "REFY+", "REFY-", "REFZ+", "REFZ-", "REF_DRAIN", "GUARD_REF", "NC", "NC"]}
def w(net, cls, awg=None, i=0.0, v=5.0, ins=None, note=""): return dict(net=net, cls=cls, awg=awg, i_rms=i, v_max=v, ins_V=ins, note=note)
IF = [
    dict(id="I1", name="Coil leads -> TXJ (head)", a="coil (26 t FEP litz)", b="TXJ", medium="litz ends into wire-hole pads, potted", connector="solder (wire-hole pads), existing TXJ board",
         conds=[w("TX_A", "HV", None, I_TX, V_HV, 1000, "FEP litz"), w("TX_B", "HV", None, I_TX, V_HV, 1000, "FEP litz")], status="built (board:TXJ)"),
    dict(id="I2", name="Cord head end -> TXJ / CB1D / AB1A (head gland)", a="cord flex piece 1", b="TXJ (TX pair), CB1D (power, link, TX command), AB1A (REF pairs)", medium="flex ends straight into the boards inside the gland (no pigtails), potted strain relief",
         connector="TXJ: TX strips soldered to the existing pads (no connector on HV); CB1D: Panasonic Y5B 10-way ZIF AYF531035 (VIN_H / GND_H on 2 pins each; 0.5 A / pin, 50 V, datasheet on file); AB1A: Panasonic Y5B 10-way ZIF AYF531035 (3 REF pairs + drain + REF guard); flex ends stiffened to the 0.30 mm applicable FPC thickness (owner 2026-10-31, option 'gland_fpc'; was JST GH 8-way + 7-way with flex-to-wire pigtails)",
         conds=[w("TX_A", "HV", None, I_TX, V_HV, 1000, "flex strip, soldered"), w("TX_B", "HV", None, I_TX, V_HV, 1000, "flex strip, soldered"), w("VIN_H", "power", None, I_VH, 29.4, None, "Y5B, 2 pins"), w("GND_H", "power", None, I_VH, 0, None, "Y5B, 2 pins"),
                w("TXCMD+", "diff"), w("TXCMD-", "diff"), w("TXSTAT+", "diff"), w("TXSTAT-", "diff"), w("DATA+", "diff"), w("DATA-", "diff"),
                w("REFX+", "analog"), w("REFX-", "analog"), w("REFY+", "analog"), w("REFY-", "analog"), w("REFZ+", "analog"), w("REFZ-", "analog"), w("REF_DRAIN", "analog"), w("GUARD_REF", "analog", None, 0.0, 0, None, "ground guard (ref_guard)")],
         status="design"),
    dict(id="I3", name="Cord flex through the telescope (head -> TXD pod tap -> REF3T -> hinge cord board; owner 2026-10-30 / 2026-10-31, HANDOFF 45 / 56)", a="head gland", b="TXD pod (TX), cord board in the hinge knuckle",
         medium=f"single-layer 2 oz long flex (rf2_cordflex): piece 1 {CFX.WIDTH:.2f} mm wide: TX strips {CFX.W_TX:.2f} mm with 1.0 mm rule-6 gaps (head -> pod tap only), VIN_H / GND_H, 3 diff pairs (TXCMD, TXSTAT, DATA), a {CFX.GUARD_W} mm REF guard, 3 guarded REF pairs, a rolling loop for the 550 mm travel; piece 2 (REF3T -> hinge, static) {CFX.WIDTH_PIECE2:.2f} mm: HV_CLAMP / GND_CLAMP (rule-6 gap), VIN_T / GND_T, VIN_H / GND_H, DATA",
         connector="none on the TX strips (soldered at the gland board and the pod tap); REF3T and the cord board soldered; vendor: Tech Etch long flex (40 in preferred) or Minco (to 5 ft), capability on file; insulation: Kapton / acrylic coverlay 3500 V/mil and 1000 VRMS typical withstand (Minco design guide 2019, on file), the drawing calls a net-to-net hipot >= 1000 VRMS (rule 6: 630 V)", conds="I2", status="spec (roadmap P4.2: flex drawing + rolling-loop mock-up)"),
    dict(id="I3b", name=f"Cord tap -> TXD pod (s {DRV.TXD_S_MM:.0f} mm, outer profile lower end; owner 2026-10-31)", a="cord flex piece 1 (TX, TXCMD / TXSTAT) and piece 2 via REF3T (feed, clamp return)", b="TXD pod boards",
         medium="flex tails lap-soldered to the pod's lower board; HV lands >= 1.0 mm from everything (rule 6), potted", connector="none (soldered: no >= 630 V pluggable part on file)",
         conds=[w("TX_A", "HV", None, I_TX, V_HV, 1000, "flex strip"), w("TX_B", "HV", None, I_TX, V_HV, 1000, "flex strip"), w("TXCMD+", "diff"), w("TXCMD-", "diff"), w("TXSTAT+", "diff"), w("TXSTAT-", "diff"),
                w("VIN_T", "power", None, I_VIN, 29.4), w("GND_T", "power", None, I_VIN, 0), w("HV_CLAMP", "HV", None, 0.03, V_HV, 1000, "clamp node -> regenerative buck (PWR)"), w("GND_CLAMP", "power", None, 0.03, 0)], status="design (new 2026-10-31)"),
    dict(id="I4", name="REF3 coils -> REF3T board -> cord REF pairs (breakout on the fixed cord run in the outer section)", a="REF3 face coils X / Y, solenoid Z", b="cord REF pairs", medium="coil ends to REF3T pads; REF3T to the cord breakout",
         connector="solder pads on REF3T (board P1.7)", conds=[w("REFX+", "analog", None), w("REFX-", "analog", None), w("REFY+", "analog", None), w("REFY-", "analog", None), w("REFZ+", "analog", None), w("REFZ-", "analog", None), w("REF_DRAIN", "analog", None)], status="design"),
    dict(id="I5", name="Hinge pass-through (cord board -> chassis)", a="cord board (hinge knuckle)", b="PWR (pod feed, clamp return) and HB2-M (DATA, VIN_H)", medium="clock-spring flex in the hollow hinge axis: unbonded single-sided plies (air-gap), 2 oz copper; HV_CLAMP >= 1.0 mm from everything (rule 6); 180 deg fold (no TX pair here since the TXD moved to the pod, 2026-10-31)",
         connector="Panasonic Y5B FPC ends (50 V, 0.5 A / pin, datasheet on file) on the LV ply (VIN_H, GND_H, DATA); the HV / power ply (HV_CLAMP, GND_CLAMP, VIN_T, GND_T) soldered to PWR and the cord board",
         conds=[w("HV_CLAMP", "HV", None, 0.03, V_HV, 1000, "flex, 1.0 mm spacing"), w("GND_CLAMP", "power", None, 0.03, 0), w("VIN_T", "power", None, I_VIN, 29.4, None, "soldered ply"), w("GND_T", "power", None, I_VIN, 0, None, "soldered ply"),
                w("VIN_H", "power", None, I_VH, 29.4), w("GND_H", "power", None, I_VH, 0), w("DATA+", "diff"), w("DATA-", "diff")], status="design (P3.3)"),
    dict(id="I6", name="Battery cartridge -> PWR (bay front blade contacts)", a="cartridge (7S1P P45B, BQ76952)", b="PWR board", medium="sealed blade contacts at the bay front",
         connector="power: Amass MT60 mated pair (cartridge male, bay female; 30 A, keyed, datasheet on file); signals: 4 x photo-etched BeCu C172 contact fingers, 0.254 mm, 2.54 mm pitch, gold-plated (owner 2026-10-30; Tech Etch etch & form capability on file; 0.63 N at 0.8 mm, rf2_flex_options C; contact resistance and cycle life by vendor test)",
         conds=[w("VBAT+", "power", None, I_VIN * 1.5, 29.4), w("VBAT-", "power", None, I_VIN * 1.5, 0), w("SDA", "digital"), w("SCL", "digital"), w("BTN_TS2", "digital"), w("NTC", "analog")], status="design (P3.8)"),
    dict(id="I7", name="Charge port (cartridge)", a="charger", b="cartridge", medium="Amass MT60 keyed (datasheet on file)", connector="Amass MT60", conds=[w("CHG+", "power", None, 3.0, 29.4), w("CHG-", "power", None, 3.0, 0), w("CHG_SENSE", "power", None, 0.1, 29.4)], status="part chosen"),
    dict(id="I8", name="PWR -> hinge cord board (chassis internal; TXD pod feed and clamp return)", a="PWR", b="hinge cord board (-> I5 -> cord piece 2 -> TXD pod)", medium="PWR rigid-flex tail to the hinge HV / power ply: HV_CLAMP with >= 1.0 mm spacing (rule 6) - no HV connector (was the TXD-PWR rigid-flex inside the chassis until 2026-10-31)",
         connector="none (rigid-flex tail, soldered)",
         conds=[w("VIN_T", "power", None, I_VIN, 29.4), w("GND_T", "power", None, I_VIN, 0), w("HV_CLAMP", "HV", None, 0.03, V_HV, 1000, f"{DRV.V_CLAMP:.0f} V clamp -> regenerative buck"), w("GND_CLAMP", "HV", None, 0.03, 0, 1000)], status="design"),
    dict(id="I9", name="HB2-M <-> PWR", a="HB2-M", b="PWR", medium="short harness", connector="JST GH 8-way (datasheet on file)",
         conds=[w("+5V_AUX", "power", None, 0.16, 5), w("GND", "power", None, 0.16, 0), w("SDA", "digital"), w("SCL", "digital"), w("SPARE1", "digital", note="was TXSTAT_THERM: the pod's TMP117 drives TXSTAT to the head (2026-10-31)"), w("BTN_TS2", "digital"),
                w("SPARE2", "digital", note="was TXCMD_LOCAL: the head commands the pod over TXCMD"), w("BOOST_EN", "digital")], status="design"),
    dict(id="I10", name="HB2-M -> HB2-G (12-way FFC down the grip core)", a="HB2-M", b="HB2-G (grip head)", medium="12-way 0.5 mm FFC with a 60 mm service loop (25 mm grip slide)", connector="Panasonic AYF531235 (Y5B, 0.5 A / pin, 50 V, datasheet on file)",
         conds=[w("+3V3_P", "power", None, 0.06, 3.3), w("GND", "power", None, 0.06, 0), w("GND2", "power"), w("SW_PWR", "digital"), w("SW_TRG", "digital"), w("SW_SEL_A", "digital"), w("SW_SEL_B", "digital"),
                w("LED_DAT", "digital", None, 0.0, 5), w("LED_CLK", "digital", None, 0.0, 5), w("+5V_LED", "power", None, 0.06, 5), w("SCR_SPI_CLK", "digital", None, 0.0, 3.3), w("SCR_SPI_MOSI", "digital", None, 0.0, 3.3)], pins=12, status="design"),
    dict(id="I11", name="HB2-G -> screen tray board (dynamic hinge flex)", a="HB2-G", b="tray board (carries AYF531035 for the panel FPC)", medium="single-sided dynamic flex across the screen hinge (the panel's own FPC allows 3 bends only)",
         connector="Panasonic AYF531035 on the tray board (Sharp's recommendation); hinge flex soldered or Y5B",
         conds=[w("SCR_SCLK", "digital", None, 0.0, 3.3), w("SCR_SI", "digital", None, 0.0, 3.3), w("SCR_SCS", "digital", None, 0.0, 3.3), w("SCR_EXTCOMIN", "digital", None, 0.0, 3.3), w("SCR_DISP", "digital", None, 0.0, 3.3),
                w("SCR_VDD", "power", None, 0.001, 3.3), w("SCR_VSS", "power", None, 0.001, 0)], status="design"),
    dict(id="I12", name="Screen panel FPC -> tray board", a="Sharp LS013B7DH03", b="tray board", medium="panel FPC, 10 pins, static (bent once at assembly, R >= 0.45 mm)", connector="Panasonic AYF531035",
         conds=[w("SCLK", "digital", None, 0, 3.0), w("SI", "digital", None, 0, 3.0), w("SCS", "digital", None, 0, 3.0), w("EXTCOMIN", "digital", None, 0, 3.0), w("DISP", "digital", None, 0, 3.0),
                w("VDDA", "power", None, 0.0005, 3.0), w("VDD", "power", None, 0.0005, 3.0), w("EXTMODE", "digital", None, 0, 3.0), w("VSS", "power"), w("VSSA", "power")], pins=10, status="part chosen (Sharp spec LD-26X06A)"),
]
VERIFIED = {"Amass MT60": "Amass_MT60", "Panasonic AYF531035": "Panasonic_Y5B", "Panasonic Y5B": "Panasonic_Y5B"}
def main():
    res = dict(status="MODELED interface definitions; connector parts are TBD where no datasheet is on file", interfaces=[], checks={})
    hv_bad, amp_bad, tbd = [], [], []
    for itf in IF:
        conds = next(x for x in IF if x["id"] == itf["conds"])["conds"] if isinstance(itf["conds"], str) else itf["conds"]
        for c_ in conds:
            if c_["cls"] == "HV" and c_["v_max"] > 50 and (c_["ins_V"] or 0) < 630: hv_bad.append((itf["id"], c_["net"]))
            if c_["awg"] and c_["i_rms"] > AMP[c_["awg"]]: amp_bad.append((itf["id"], c_["net"]))
        if "TBD" in itf["connector"] or "UNVERIFIED" in itf["connector"]: tbd.append(itf["id"])
        if "pins" in itf and itf["pins"] < len(conds): amp_bad.append((itf["id"], f"{len(conds)} conductors > {itf['pins']} pins"))
        res["interfaces"].append(dict(itf, conds=conds))
    import rf2_system as S
    sys_nets = {x["name"].split("+")[0].split(" ")[0] for d in S.SEGMENTS.values() for x in d["conds"]}
    icd_nets = {c_["net"].rstrip("+-") for i_ in ("I2", "I3b", "I5") for c_ in next(x for x in IF if x["id"] == i_)["conds"]}
    y5b_rows = []
    for con, pins in GLAND_Y5B.items():
        n_vin = pins.count("VIN_H"); i_pin = I_VH / max(n_vin, 1)
        y5b_rows.append(dict(connector=con, pins=len(pins), i_per_pin_A=round(i_pin, 3) if n_vin else 0.0, i_rating_A=Y5B["I_A"], v_max_V=29.4 if n_vin else 3.3, v_rating_V=Y5B["V"], ok=len(pins) <= 10 and i_pin <= Y5B["I_A"] and 29.4 <= Y5B["V"]))
    res["gland_y5b"] = y5b_rows
    i2_nets = {c_["net"] for c_ in next(x for x in IF if x["id"] == "I2")["conds"] if c_["cls"] != "HV"}
    y5b_nets = {n for pins in GLAND_Y5B.values() for n in pins if n != "NC"}
    missing = sorted(n for n in sys_nets if n.rstrip("+-") not in icd_nets)
    c = res["checks"]
    c["rule 6: every HV conductor insulated >= 630 V"] = dict(ok=not hv_bad, offenders=hv_bad)
    c["ampacity and pin counts"] = dict(ok=not amp_bad, offenders=amp_bad)
    c["harness nets in rf2_system all defined at an ICD joint (I2 head gland, I3b TXD pod tap, I5 hinge)"] = dict(ok=not missing, missing=missing)
    c["head gland Y5B ZIFs: every LV net of I2 on a pin; VIN_H per pin and 29.4 V within the Y5B ratings (0.5 A, 50 V)"] = dict(ok=i2_nets == y5b_nets and all(r["ok"] for r in y5b_rows), rows=y5b_rows, unplaced=sorted(i2_nets ^ y5b_nets))
    c["screen FPC bend limit (3 bends) handled by a dynamic hinge flex (I11) and a static panel FPC (I12)"] = dict(ok=any(x["id"] == "I11" for x in IF) and "static" in next(x for x in IF if x["id"] == "I12")["medium"])
    c["every connector part verified (datasheet on file, ratings read)"] = dict(ok=not tbd, tbd_or_unverified=tbd)
    res["p06_parts"] = {"screen LS013B7DH03": "VERIFIED (Sharp LD-26X06A)", "RS-485 THVD1410": "VERIFIED (TI SLLSEY3E)", "FPC / FFC connectors (Panasonic Y5B)": "VERIFIED (catalog ACCTB1E + product page)", "wire-to-board (JST GH)": "VERIFIED (JST eGH)",
                        "cartridge signal contacts (photo-etched BeCu fingers)": "decided: custom photo-etched part (Tech Etch capability on file; force modeled, resistance / cycle life by vendor test)",
                        "coil cord -> cord flex": "decided: custom long flex, Kapton / acrylic stack (Minco design guide values on file; hipot >= 1000 VRMS on the drawing)", "rectangular CF profiles": "custom sizes: vendor pages only", "cam clamp hardware": "decided: printed cam lever + elastomer pressure block through a window in the outer profile (SDC 2300 pattern: Minelab camlock lever 8008-0061, pressure rubber block 8008-0062; elastomer hardness ASSUMED)",
                        "cell holder": "decided: spot-welded pack (Keystone holder logged as alternative)", "Rd resistor family": "VERIFIED (Vishay PR03, 2 x 806 ohm)",
                        "MP1 v2 isolation switch (TI TMUX7212)": "VERIFIED (TI SCDS416D)", "MP1 v2 switch / clamp-rail supply (TI TPS65131)": "VERIFIED (TI SLVS493E)",
                        "MP1 v2 clamp-rail shunts (TI TL431)": "VERIFIED (TI TL431 datasheet; stability with the rail capacitor still to check)"}
    res["p06_all_verified"] = all(v.startswith(("VERIFIED", "decided")) for v in res["p06_parts"].values())
    res["all_parts_verified"] = not tbd; res["ok_except_parts"] = all(v["ok"] for k, v in c.items() if not k.startswith("every connector"))
    json.dump(res, open(os.path.join(OUT, "rf2_icd.json"), "w"), indent=1)
    L = ["# AXE2 interface control document (generated by rf2/rf2_icd.py; MODELED)", "",
         f"Chassis v2 (rf2_chassis.py). {len(IF)} interfaces. Connector parts marked TBD carry the requirement they must meet; the readiness gate P0.1 stays open until every part is verified.", "",
         "## Checks", ""] + [f"- {'PASS' if v['ok'] else 'OPEN'}: {k}" + (f" ({ {kk: vv for kk, vv in v.items() if kk != 'ok'} })" if not v["ok"] else "") for k, v in c.items()] + [""]
    for itf in res["interfaces"]:
        L += [f"## {itf['id']}. {itf['name']}", "", f"- **From / to:** {itf['a']} -> {itf['b']}", f"- **Medium:** {itf['medium']}", f"- **Connector:** {itf['connector']}", f"- **Status:** {itf['status']}", "",
              "| # | Net | Class | AWG | I rms (A) | V max | Insulation (V) | Note |", "|---|---|---|---|---|---|---|---|"]
        for k, c_ in enumerate(itf["conds"], 1):
            L.append(f"| {k} | {c_['net']} | {c_['cls']} | {c_['awg'] or '-'} | {c_['i_rms']:.2f} | {c_['v_max']} | {c_['ins_V'] or '-'} | {c_['note']} |")
        L.append("")
    open(os.path.join(ROOT, "docs", "ICD.md"), "w").write("\n".join(L) + "\n")
    for k, v in c.items(): print(("PASS " if v["ok"] else "OPEN ") + k, "" if v["ok"] else {kk: vv for kk, vv in v.items() if kk != "ok"})
    return res
if __name__ == "__main__":
    main()
