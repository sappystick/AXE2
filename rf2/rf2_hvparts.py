#!/usr/bin/env python3
"""RF2 owner-supplied HV parts comparison (2026-10-30). MODELED: loads from the continuous-boost pulse model (rf2_continuous.pulse_train); ratings are the datasheet values
logged in docs/DATASHEET_LOG_ARX.md section RF2-DS-HVPARTS (PDFs in data/datasheets). Values read off a graph are marked READ.
Roles checked:
  1. clamp diode (coil drain -> 460 V clamp capacitor): Nexperia US3M, Diodes US3M (today's part), Nexperia PNU650200AEJ-Q and PNU650300AEJ;
  2. TX switch: Microsemi ARF461A/B and ARF1510 against the Wolfspeed C3M0280090J; the same parts as the MP1 v2 limiter (needs a depletion-mode device);
  3. damping resistor Rd 408 ohm, >= 2x its 2.1 W boost load, >= 630 V: Vishay Techno TR;
  4. thermal-limit sensing (TI TMP117) and the regenerative clamp controller (TI UCC28780) are recorded as candidates with their constraints.
Writes rf2/results/rf2_hvparts.json; exits 1 if a check fails.   usage: python3 rf2/rf2_hvparts.py"""
import os, sys, json, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "rf2"))
import rf2_continuous as CT, rf2_drive as DRV
OUT = os.path.join(ROOT, "rf2", "results")
V_CLAMP, RULE6 = CT.V_CLAMP, 630.0
I_BOOST = CT.MODES["boost (trigger held, continuous)"]
TA_HEAD = CT.TA + 30.0                     # inside the potted head, as rf2_continuous (ASSUMED)
DIODES = {  # VRRM V, IF(AV) A, IFSM A (8.3 ms), trr max ns (0.5 A / 1 A / 0.25 A), Cd at ~430 V pF, Rth junction-ambient K/W, package, body mm
    "Nexperia US3M (2025-01-20)": dict(vrrm=1000, ifav=3.0, ifsm=100, trr_ns=75, cd_430_pF=7.0, rth_ja=135, pkg="SMC", body=(7.0, 6.1),
                                       note="product data sheet; Cd READ from Fig. 5 (about 7 pF above 400 V); Rth(j-sp) 15 K/W"),
    "Diodes US3M DS37228 rev 5-2 (today)": dict(vrrm=1000, ifav=3.0, ifsm=120, trr_ns=85, cd_430_pF=None, rth_ja=None, pkg="SMC", body=(7.0, 6.1),
                                               note="ADVANCED INFORMATION sheet; RthJT 26 C/W; Cd 25 pF at 4 V"),
    "Nexperia PNU650200AEJ-Q": dict(vrrm=650, ifav=20.0, ifsm=160, trr_ns=60, cd_430_pF=12.0, rth_ja=61, pkg="D2PAK R2P", body=(10.2, 15.4),
                                    note="Cd 10 pF at 400 V (table), about 12 pF at 430 V READ; Qrr 451-1221 nC at 20 A; body size ASSUMED (D2PAK class)"),
    "Nexperia PNU650300AEJ": dict(vrrm=650, ifav=30.0, ifsm=209, trr_ns=60, cd_430_pF=13.0, rth_ja=61, pkg="D2PAK R2P", body=(10.2, 15.4),
                                  note="Cd 13 pF at 400 V (table); Qrr 690-1788 nC at 30 A; body size ASSUMED (D2PAK class)"),
}
FETS = {  # mode, VDSS V, RDS(on) ohm (max at 25 C or VDS(on)/ID), ID A, IDM A, Coss pF at V
    "onsemi NTBG080N120SC1 (adopted 2026-10-31)": dict(mode="enhancement", vdss=1200, rds=0.110, rds_hot=DRV.RDS_HOT, id=30.0, idm=110.0, coss=(79, 800), hazard=None),
    "Wolfspeed C3M0280090J (until 2026-10-31)": dict(mode="enhancement", vdss=900, rds=0.36, rds_hot=0.416 * 1.1, id=11.0, idm=22.0, coss=(110, 25), hazard=None),
    "Microsemi ARF461A/B": dict(mode="enhancement", vdss=1000, rds=6.5 / 3.25, rds_hot=6.5 / 3.25 * 1.8, id=6.5, idm=None, coss=(175, 50), hazard=None),
    "Microsemi ARF1510": dict(mode="enhancement", vdss=1000, rds=7.5 / 3.25, rds_hot=7.5 / 3.25 * 1.8, id=8.0, idm=None, coss=(100, 200),
                              hazard="BeO ceramic (toxic dust; special disposal); four-switch H-bridge, flangeless 27 x 27 mm, clamped to a heat sink"),
}
TR = {"TR03C": (0.25, 800, 300, 3e6, 7.62, 5.33), "TR05D": (0.5, 4000, 500, 25e6, 12.7, 7.62), "TR10F": (1.0, 6500, 1e3, 16e6, 25.4, 8.89), "TR15G": (1.5, 12500, 1.5e3, 45e6, 38.1, 8.89),
      "TR20H": (2.0, 17500, 2e3, 64e6, 50.8, 8.89), "TR30J": (3.0, 25000, 3e3, 82e6, 76.2, 10.16)}   # P25 W, max working V, R range (100 ppm), length mm, height mm (body face)
FIN = (32.0, 8.4)                            # TXF fin board w x h, mm (rf2_netlist "TXF"); the HV bus takes part of it, so the whole face is an upper bound
def tr_derate(ta):                           # Vishay TR derating: 100 % to 25 C, linear to 0 at 125 C (READ, page 3)
    return max(0.0, min(1.0, (125.0 - ta) / 100.0))
def main():
    p = CT.pulse_train(I_BOOST); checks = {}; res = dict(status="MODELED; ratings from the logged datasheets; READ values from graphs", boost_A=round(I_BOOST, 2))
    # 1. clamp diode
    q = 0.5 * I_BOOST * p["fall_us"] * 1e-6; i_avg = CT.F * q; vf_est = 2.5        # VF at the 12.7 A start of the clamp pulse (ASSUMED 2.5 V upper bound for the SMC parts)
    rows = []
    for n, d in DIODES.items():
        P = i_avg * vf_est; tj = TA_HEAD + P * d["rth_ja"] if d["rth_ja"] else None
        rows.append(dict(part=n, rule6=d["vrrm"] >= RULE6, margin_over_clamp=round(d["vrrm"] / V_CLAMP, 2), avg_current_mA=round(i_avg * 1e3, 1),
                         avg_vs_rating=round(i_avg / d["ifav"], 4), loss_W=round(P, 3), tj_C=round(tj, 1) if tj else None, cd_430_pF=d["cd_430_pF"],
                         area_mm2=round(d["body"][0] * d["body"][1], 1), note=d["note"]))
    res["clamp_diode"] = rows
    checks["US3M (Nexperia) passes rule 6 with >= 2x margin over the clamp"] = rows[0]["rule6"] and rows[0]["margin_over_clamp"] >= 2.0
    checks["PNU650 parts pass rule 6 but under 1.5x over the clamp"] = all(r["rule6"] and r["margin_over_clamp"] < 1.5 for r in rows[2:])
    checks["clamp diode average current under 2 % of the US3M rating"] = rows[0]["avg_vs_rating"] < 0.02
    checks["US3M junction rise under 15 K in continuous boost"] = rows[0]["tj_C"] - TA_HEAD < 15.0
    # 2. TX switch / limiter
    fr = []
    for n, f in FETS.items():
        P_cond = p["I_rms_switch"] ** 2 * f["rds_hot"]
        fr.append(dict(part=n, mode=f["mode"], vdss=f["vdss"], rule6=f["vdss"] >= RULE6, rds_ohm=round(f["rds"], 2), conduction_W_boost=round(P_cond, 2),
                       peak_A=round(I_BOOST, 2), peak_within_ID=I_BOOST <= (f["idm"] or f["id"]) * 0.8, coss_pF_at_V=f["coss"], usable_as_limiter=f["mode"] == "depletion",
                       hazard=f["hazard"]))
    res["tx_switch"] = fr
    res["tx_switch_note"] = "ARF RDS(on) from VDS(on) / ID at 3.25 A (typ / max); hot value x1.8 (ASSUMED, typical Si VDMOS at 125 C); no IDM in either ARF sheet: the continuous ID is used"
    arf = [r for r in fr if "ARF" in r["part"]]
    checks["ARF parts dissipate > 4x the adopted NTBG080N120SC1 in conduction"] = all(r["conduction_W_boost"] > 4 * fr[0]["conduction_W_boost"] for r in arf)
    checks["ARF parts cannot carry the boost peak within 80 % of their rating"] = not any(r["peak_within_ID"] for r in arf)
    checks["no ARF part can serve as the depletion limiter"] = not any(r["usable_as_limiter"] for r in arf)
    # 3. Rd with Vishay TR
    P_rd = CT.F * (V_CLAMP ** 2 / CT.RD * p["fall_us"] * 1e-6 + CT.VBUS ** 2 / CT.RD * (p["T1_us"] * 1e-6 + 0.5 * CT.T_FLAT)); need = 2 * P_rd
    opts = []
    for m, (p25, vmax, rlo, rhi, length, height) in TR.items():
        for n in range(1, 9):                # n in parallel, each n x 408 ohm
            r = n * CT.RD
            if rlo <= r <= rhi:
                pa = n * p25 * tr_derate(TA_HEAD); opts.append(dict(model=m, n_parallel=n, each_ohm=round(r), P_avail_W=round(pa, 2), need_W=round(need, 2),
                                                                     ok_power=pa >= need, ok_voltage=vmax >= RULE6, length_mm=length,
                                                                     face_mm2=round(n * length * height), fits_TXF_fin=length <= FIN[0] and n * length * height <= FIN[0] * FIN[1]))
    res["rd_vishay_TR"] = dict(P_rd_boost_W=round(P_rd, 2), derate_at_C=TA_HEAD, derate=round(tr_derate(TA_HEAD), 2), options=[o for o in opts if o["ok_power"]][:6],
                               any_fits=any(o["ok_power"] and o["ok_voltage"] and o["fits_TXF_fin"] for o in opts),
                               fit_elsewhere="high-value HV dividers / bleeders: cascode gate divider 2 x 10 Mohm (TR03C, 800 V, 230 V each: 5.3 mW), 460 V clamp-capacitor bleeder and sense divider")
    checks["no TR combination gives Rd >= 2x power and fits the 32 mm TXF fin"] = not res["rd_vishay_TR"]["any_fits"]
    # 4. candidates
    res["candidates"] = {
        "TI TMP117": "thermal-limit sensors for continuous boost (switch heat sink, HV fin / Rd, coil channel, battery) and the display drift sensor: +-0.1 C (-20..50 C), +-0.25 C to 125 C, "
                     "3.5 uA at 1 Hz, up to 4 per I2C bus (ADD0 to GND / V+ / SDA / SCL), ALERT with programmable limits; WSON 2 x 2 mm (small metal pad: count it in the echo budget if inside the coil)",
        "TI UCC28780": "regenerative clamp: an active-clamp flyback 460 V -> battery bus; stored coil energy %.1f W in boost (the clamp receives it less the Rd share, 8.9 W in rf2_continuous). VDD 12-34 V operating, 38 V abs max (7S pack 29.4 V full: OK); up to 1 MHz; "
                       "needs a transformer (ferrite: banned in the head, so the converter sits in the pod; 460 V DC up the shaft at about %.0f mA) and a >= 800 V primary switch "
                       "(NTBG080N120SC1, the TX switch part); its control loop regulates an output, a clamp must hold its input at the clamp voltage: OPEN design study" % (CT.F * (0.5 * CT.L * I_BOOST ** 2) - 0, CT.F * (0.5 * CT.L * I_BOOST ** 2) / V_CLAMP * 1e3)}
    res["checks"] = checks; res["all_pass"] = all(checks.values())
    json.dump(res, open(os.path.join(OUT, "rf2_hvparts.json"), "w"), indent=1)
    for r in rows: print(f"  diode {r['part'][:36]:<36} rule6 {r['rule6']}  x{r['margin_over_clamp']}  {r['avg_current_mA']} mA  {r['loss_W']} W  TJ {r['tj_C']}  Cd {r['cd_430_pF']} pF  {r['area_mm2']} mm2")
    for r in fr: print(f"  fet   {r['part'][:36]:<36} {r['mode']:<11} {r['vdss']} V  RDS {r['rds_ohm']}  {r['conduction_W_boost']} W  peak ok {r['peak_within_ID']}")
    print("  Rd:", json.dumps({k: v for k, v in res["rd_vishay_TR"].items() if k != "options"}), res["rd_vishay_TR"]["options"][:2])
    for k, v in checks.items(): print(("  PASS " if v else "  FAIL ") + k)
    return res
if __name__ == "__main__":
    sys.exit(0 if main()["all_pass"] else 1)
