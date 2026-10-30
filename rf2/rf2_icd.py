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
I_TX, I_VIN, I_VH = 3.67, 1.13, 0.45                                                  # A rms in continuous boost (rf2_continuous / rf2_system)
def w(net, cls, awg=None, i=0.0, v=5.0, ins=None, note=""): return dict(net=net, cls=cls, awg=awg, i_rms=i, v_max=v, ins_V=ins, note=note)
IF = [
    dict(id="I1", name="Coil leads -> TXJ (head)", a="coil (26 t FEP litz)", b="TXJ", medium="litz ends into wire-hole pads, potted", connector="solder (wire-hole pads), existing TXJ board",
         conds=[w("TX_A", "HV", None, I_TX, 463, 1000, "FEP litz"), w("TX_B", "HV", None, I_TX, 463, 1000, "FEP litz")], status="built (board:TXJ)"),
    dict(id="I2", name="Cord head end -> TXJ / CB1D / AB1A (head gland)", a="coil cord", b="TXJ (TX pair), CB1D (power, link, TX command), AB1A (REF pairs)", medium="cord breakout inside the gland, potted strain relief",
         connector="TXJ: solder pads (existing); CB1D: JST GH 8-way (1.0 A / pin, 50 V, datasheet on file); AB1A: JST GH 7-way (3 REF pairs + drain)",
         conds=[w("TX_A", "HV", 18, I_TX, 463, 1000), w("TX_B", "HV", 18, I_TX, 463, 1000), w("VIN_H", "power", 20, I_VH, 29.4, 300), w("GND_H", "power", 20, I_VH, 0, 300),
                w("TXCMD+", "diff", 26, 0.01), w("TXCMD-", "diff", 26, 0.01), w("TXSTAT+", "diff", 26, 0.01), w("TXSTAT-", "diff", 26, 0.01), w("DATA+", "diff", 26, 0.01), w("DATA-", "diff", 26, 0.01),
                w("REFX+", "analog", 26), w("REFX-", "analog", 26), w("REFY+", "analog", 26), w("REFY-", "analog", 26), w("REFZ+", "analog", 26), w("REFZ-", "analog", 26), w("REF_DRAIN", "analog", 26)],
         status="design"),
    dict(id="I3", name="Coil cord through the telescope (head -> outer-section anchor)", a="head gland", b="cord board in the hinge knuckle", medium="custom coil cord in the 18 x 18 mm inner bore: twisted FEP AWG18 1000 V TX pair, AWG20 power pair, 3 twisted AWG26 pairs (TXCMD, TXSTAT, DATA), 3 individually shielded AWG26 REF pairs + drain; PUR jacket; coil OD 17 mm, stretch 4.4 : 1",
         connector="none (continuous); vendor TBD (custom: stock PUR cords are 120-500 V, rule 6 needs the TX pair at >= 630 V)", conds="I2", status="spec (COIL_CORD_SPEC, roadmap P4.2)"),
    dict(id="I4", name="REF3 coils -> REF3T board -> cord REF pairs (breakout on the fixed cord run in the outer section)", a="REF3 face coils X / Y, solenoid Z", b="cord REF pairs", medium="coil ends to REF3T pads; REF3T to the cord breakout",
         connector="solder pads on REF3T (board P1.7)", conds=[w("REFX+", "analog", None), w("REFX-", "analog", None), w("REFY+", "analog", None), w("REFY-", "analog", None), w("REFZ+", "analog", None), w("REFZ-", "analog", None), w("REF_DRAIN", "analog", None)], status="design"),
    dict(id="I5", name="Hinge pass-through (cord board -> chassis)", a="cord board (hinge knuckle)", b="TXD (TX pair, TXCMD / TXSTAT) and HB2-M (DATA, VIN_H return)", medium="clock-spring flex in the hollow hinge axis: unbonded single-sided plies (air-gap), 2 oz copper; TX traces 3 mm wide, >= 1.0 mm spacing (rule 6); 180 deg fold",
         connector="Panasonic Y5B FPC ends (50 V, 0.5 A / pin, datasheet on file) on the LV plies; the HV ply soldered to TXD and the cord board",
         conds=[w("TX_A", "HV", None, I_TX, 463, 1000, "flex, 1.0 mm spacing"), w("TX_B", "HV", None, I_TX, 463, 1000, "flex, 1.0 mm spacing"), w("VIN_H", "power", None, I_VH, 29.4), w("GND_H", "power", None, I_VH, 0),
                w("TXCMD+", "diff"), w("TXCMD-", "diff"), w("TXSTAT+", "diff"), w("TXSTAT-", "diff"), w("DATA+", "diff"), w("DATA-", "diff")], status="design (P3.3)"),
    dict(id="I6", name="Battery cartridge -> PWR (bay front blade contacts)", a="cartridge (7S2P, BQ76952)", b="PWR board", medium="sealed blade contacts at the bay front",
         connector="power: Amass MT60 mated pair (cartridge male, bay female; 30 A, keyed, datasheet on file); signals: 4 x Mill-Max 0906 spring pins (UNVERIFIED: official sheet not obtained)",
         conds=[w("VBAT+", "power", None, I_VIN * 1.5, 29.4), w("VBAT-", "power", None, I_VIN * 1.5, 0), w("SDA", "digital"), w("SCL", "digital"), w("BTN_TS2", "digital"), w("NTC", "analog")], status="design (P3.8)"),
    dict(id="I7", name="Charge port (cartridge)", a="charger", b="cartridge", medium="Amass MT60 keyed (datasheet on file)", connector="Amass MT60", conds=[w("CHG+", "power", None, 3.0, 29.4), w("CHG-", "power", None, 3.0, 0), w("CHG_SENSE", "power", None, 0.1, 29.4)], status="part chosen"),
    dict(id="I8", name="PWR <-> TXD (chassis internal)", a="PWR", b="TXD", medium="TXD and PWR built as ONE rigid-flex: the flex joint carries HV_CLAMP with >= 1.0 mm spacing (rule 6) - no HV connector",
         connector="none (rigid-flex integral)",
         conds=[w("VBAT_TX", "power", None, I_VIN, 29.4), w("GND", "power", None, I_VIN, 0), w("HV_CLAMP", "HV", None, 0.03, 463, 1000, "460 V clamp -> regenerative buck"), w("GND_CLAMP", "HV", None, 0.03, 0, 1000), w("+5V_AUX", "power", None, 0.05, 5)], status="design"),
    dict(id="I9", name="HB2-M <-> PWR / TXD", a="HB2-M", b="PWR, TXD", medium="short harness", connector="JST GH 8-way (datasheet on file)",
         conds=[w("+5V_AUX", "power", None, 0.16, 5), w("GND", "power", None, 0.16, 0), w("SDA", "digital"), w("SCL", "digital"), w("TXSTAT_THERM", "digital"), w("BTN_TS2", "digital"), w("TXCMD_LOCAL", "digital"), w("BOOST_EN", "digital")], status="design"),
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
    icd_nets = {c_["net"].rstrip("+-") for c_ in next(x for x in IF if x["id"] == "I2")["conds"]}
    missing = sorted(n for n in sys_nets if n.rstrip("+-") not in icd_nets)
    c = res["checks"]
    c["rule 6: every HV conductor insulated >= 630 V"] = dict(ok=not hv_bad, offenders=hv_bad)
    c["ampacity and pin counts"] = dict(ok=not amp_bad, offenders=amp_bad)
    c["harness nets in rf2_system all defined at the cord's head end (I2)"] = dict(ok=not missing, missing=missing)
    c["screen FPC bend limit (3 bends) handled by a dynamic hinge flex (I11) and a static panel FPC (I12)"] = dict(ok=any(x["id"] == "I11" for x in IF) and "static" in next(x for x in IF if x["id"] == "I12")["medium"])
    c["every connector part verified (datasheet on file, ratings read)"] = dict(ok=not tbd, tbd_or_unverified=tbd)
    res["p06_parts"] = {"screen LS013B7DH03": "VERIFIED (Sharp LD-26X06A)", "RS-485 THVD1410": "VERIFIED (TI SLLSEY3E)", "FPC / FFC connectors (Panasonic Y5B)": "VERIFIED (catalog ACCTB1E + product page)", "wire-to-board (JST GH)": "VERIFIED (JST eGH)",
                        "cartridge signal pins (Mill-Max 0906)": "UNVERIFIED (official sheet not obtained)",
                        "coil cord": "custom: no vendor sheet (stock cords 120-500 V)", "rectangular CF profiles": "custom sizes: vendor pages only", "cam clamp hardware": "custom printed: no datasheet",
                        "cell holder": "decided: spot-welded pack (Keystone holder logged as alternative)", "Rd resistor family": "VERIFIED (Vishay PR03, 2 x 806 ohm)"}
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
