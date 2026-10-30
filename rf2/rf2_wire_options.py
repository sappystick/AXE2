#!/usr/bin/env python3
"""RF2 wire options from the owner's datasheets (2026-10-30): the coil litz and the TX pair in the coil cord. MODELED.

Sources (data/datasheets, DATASHEET_LOG RF2-DS-WIRE):
  Rubadue insulated litz catalog (single / double / triple FEP, ETFE, TCA3): construction tables parsed from the PDF (core OD, circular mils, strands,
    strand AWG, finished nominal OD, suggested frequency) and each section's voltage rating
  Pack RUPALIT litz: bare bundles (natural-silk wrapping only, no voltage rating): listed for copper area only
  FEP hook-up wire catalog: HE 18 silver-plated FEP (2.0 kV operating, OD 3.1 mm) and Li 6Y 0.5 mm2 (600 V / 900 V peak, OD 1.3-1.5 mm, 40 ohm/km)
  Radix FEP/FEP 200 C / 600 V jacketed cable: FQ18AT02A 2 x AWG18, OD 4.72 mm
Coil (rf2_head option B, variant BF): 26 turns, 5 rows x 6 columns wound column by column, comb slot 1.3 mm at 1.6 mm pitch for a 1.2 mm finished wire.
Rules applied: rule 6 (insulation >= 630 V on flyback nets; safety, reported, never relaxed here); fit (finished OD <= 1.25 mm in the 1.3 mm slot);
frequency (suggested band reaching >= 50 kHz, the turn-off spectrum); the system model's R_coil 0.53 ohm (rf2_continuous) is compared, not changed.
Writes rf2/results/rf2_wire_options.json.   usage: python3 rf2/rf2_wire_options.py"""
import os, sys, re, json, math
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); DS = os.path.join(ROOT, "data", "datasheets")
RHO20, ALPHA = 0.017241, 0.00393          # ohm mm2 / m, per K (annealed copper)
CM_MM2 = 5.067075e-4                      # 1 circular mil in mm2
LAY = 1.02                                 # litz lay-length factor on resistance (ASSUMED)
SLOT, FIT_OD = 1.3, 1.25                  # comb slot and the largest finished OD that seats in it (0.05 mm clearance, ASSUMED)
RULE6_V = 630.0; F_MIN_KHZ = 50.0
sys.path.insert(0, HERE); import rf2_continuous as CONT
R_MODEL = CONT.R_COIL                      # the system model's coil resistance (deltas below are against it)
PACK_FILL, JACKET = 0.65, 0.8              # round-bundle packing fraction and jacket wall per side (ASSUMED) for the cord OD estimate
CORD = dict(od=7.0, coil_od=17.0, bore=18.0)  # rf2_chassis cord spec and the inner profile bore
SEC_V = {("Triple", "FEP"): 1000.0, ("Triple", "ETFE"): 1000.0, ("Triple", "TCA"): 1000.0, ("Double", "FEP"): 600.0, ("Double", "ETFE"): 600.0, ("Single", "FEP"): 600.0, ("Single", "ETFE"): 600.0}
# triple ETFE / TCA3: UL 1500 V (electronic equipment), VDE 1000 V; the lower (VDE) value is used

def rubadue():
    d = pymupdf.open(os.path.join(DS, "Rubadue_insulated_litz_FEP_ETFE_TCA.pdf")); rows = []
    for p in d:
        t = p.get_text(); h = re.search(r"(Single|Double|Triple)\s*Insulated\s*(?:TCA3\s*)?Litz Wire\s*(FEP|ETFE)?", t.replace("\n", " "))
        if not h: continue
        kind = h.group(1); ins = "TCA" if "TCA3" in t else (h.group(2) or "ETFE")
        for m in re.finditer(r"((?:[A-Z]+XXL[\w/\-\.]+|TCA3 [\d/]+ LITZ)\(MWXX\))\n([\d\.]+)\n([\d\.]+)\n(\d+)\n(\d+)\n(\d+)\n([\d\.]+)\n([^\n]+)\n", t):
            hi = float(re.findall(r"[\d\.]+", m.group(8))[-1])                                           # every band in the catalog ends in kHz ('60hz-1 khz' -> 1)
            rows.append(dict(part=m.group(1), kind=kind, ins=ins, awg_eq=float(m.group(2)), core_mm=float(m.group(3)) * 25.4, cmil=int(m.group(4)), strands=int(m.group(5)),
                             strand_awg=int(m.group(6)), od_mm=round(float(m.group(7)) * 25.4, 3), f_band=m.group(8).strip(), f_hi_khz=hi, v_rating=SEC_V[(kind, ins)]))
    return rows

def coil_length_m():
    co = json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_spec.json")))["coil"]; rs = co["columns_r"]; n = co["turns"]; rows = co["rows"]
    return sum(2 * math.pi * rs[min(k // rows, len(rs) - 1)] for k in range(n)) / 1000.0 + 0.30, co        # + 0.30 m leads to TXJ (ASSUMED)

def main():
    L_m, co = coil_length_m(); cont = json.load(open(os.path.join(OUT, "rf2_continuous.json")))
    modes = {m["mode"].split()[0]: m for m in cont["modes"]}
    i_scan, i_boost = modes["scan"]["I_rms_coil"], next(m for k, m in modes.items() if k.startswith("boost"))["I_rms_coil"]
    sy = json.load(open(os.path.join(OUT, "rf2_system.json")))["runtime"]; wh = sy["usable_Wh"]; p_boost = wh / sy["boost_continuous_h"]; p_scan = wh / sy["scan_h"]
    cands = []
    for r in rubadue():
        a = r["cmil"] * CM_MM2; R = RHO20 * LAY * L_m / a
        r.update(cu_mm2=round(a, 4), R_coil_20C=round(R, 3), R_coil_60C=round(R * (1 + ALPHA * 40), 3), fits_comb=r["od_mm"] <= FIT_OD, freq_ok=r["f_hi_khz"] >= F_MIN_KHZ,
                 rule6_ok=r["v_rating"] >= RULE6_V, rule6_short_pct=round(100 * max(0.0, 1 - r["v_rating"] / RULE6_V), 1))
        r["P_coil_scan_W"] = round(i_scan ** 2 * R, 2); r["P_coil_boost_W"] = round(i_boost ** 2 * R, 2)
        dP_b = i_boost ** 2 * (R - R_MODEL); dP_s = i_scan ** 2 * (R - R_MODEL)
        r["boost_h"] = round(wh / (p_boost + dP_b), 2); r["scan_h"] = round(wh / (p_scan + dP_s), 2)
        cu_g = a * L_m * 8.96; ins_g = (math.pi / 4) * (r["od_mm"] ** 2 - r["core_mm"] ** 2) * L_m * 2.15
        r["coil_wire_g"] = round(cu_g / 0.85 + ins_g, 1)                                              # copper / 0.85 for enamel + bunching (ASSUMED) + jacket
        cands.append(r)
    usable = [c for c in cands if c["fits_comb"] and c["freq_ok"]]
    ok_now = [c for c in usable if c["rule6_ok"]]
    best_now = min(ok_now, key=lambda c: c["R_coil_20C"]) if ok_now else None
    blocked = sorted([c for c in usable if not c["rule6_ok"] and c["rule6_short_pct"] <= 10.0], key=lambda c: c["R_coil_20C"])
    # path (c): a wider comb for a thicker triple-insulated (1000 V) litz that brings R back near the model
    wider = sorted([c for c in cands if c["rule6_ok"] and c["freq_ok"] and not c["fits_comb"] and c["od_mm"] <= 1.6], key=lambda c: (abs(c["R_coil_20C"] - R_MODEL), c["od_mm"]))
    pc = wider[0] if wider else None
    if pc:
        pitch = round(pc["od_mm"] + 0.4, 2); slot = round(pc["od_mm"] + 0.08, 2)                     # 0.3 mm teeth + clearance, as the 1.2 mm design (1.6 pitch, 1.3 slot)
        pc = dict(pc, comb_slot_mm=slot, comb_pitch_mm=pitch, channel_growth_mm=dict(radial=round(6 * (pitch - co["pitch"]), 2), height=round(5 * (pitch - co["pitch"]), 2)))
    # cord TX pair
    i_tx = 3.67; L_pair = 2 * 1.1                                                                       # boost RMS (rf2_system), out and back in the 1.1 m cord
    tx = [dict(name="HE 18 silver-plated FEP (AWG18, 7 x 0.40)", od_mm=3.1, v_rating=2000.0, v_peak=None, ohm_per_km=round(RHO20 / 0.93 * 1000 * 0.95, 1), source="FEP hook-up catalog (resistance from 0.93 mm2, silver-plated: ASSUMED)"),
          dict(name="Li 6Y 0.5 mm2 FEP (27 x 0.15 tinned)", od_mm=1.5, v_rating=600.0, v_peak=900.0, ohm_per_km=40.0, source="FEP hook-up catalog: 600 V operating / 900 V peak, 0.25 mm wall, -100..200 C"),
          dict(name="Radix FQ18AT02A FEP/FEP 2 x AWG18 jacketed", od_mm=4.72, v_rating=600.0, v_peak=None, ohm_per_km=round(RHO20 / 0.823 * 1000, 1), pair_in_one=True, source="Radix FEP/FEP 200 C / 600 V"),
          dict(name="model now: FEP AWG18 1000 V (ASSUMED, no vendor)", od_mm=1.70, v_rating=1000.0, v_peak=None, ohm_per_km=round(RHO20 / 0.823 * 1000, 1), source="rf2_system FEP18 (ASSUMED)")]
    tube_a = math.pi * 9.0 ** 2; base_area = 0.142 * tube_a - 2 * math.pi * (1.70 / 2) ** 2          # S1 fill without the model's TX pair
    for t in tx:
        a_pair = math.pi * (t["od_mm"] / 2) ** 2 * (1 if t.get("pair_in_one") else 2)
        t.update(rule6_ok=t["v_rating"] >= RULE6_V, rule6_short_pct=round(100 * max(0.0, 1 - t["v_rating"] / RULE6_V), 1), flyback_peak_V=460.0,
                 s1_fill=round((base_area + a_pair) / tube_a, 3), fill_ok=(base_area + a_pair) / tube_a <= 0.40, R_pair_ohm=round(t["ohm_per_km"] * L_pair / 1000, 3),
                 P_pair_boost_W=round(i_tx ** 2 * t["ohm_per_km"] * L_pair / 1000, 2))
    # coil-cord packing: the S1 conductor set of rf2_system with each TX option; a coiled cord needs coil OD = coil ID + 2 x cable OD <= the bore
    import rf2_system as SYS
    s1 = next(v for k, v in SYS.SEGMENTS.items() if k.startswith("S1"))["conds"]
    def cord_od(conds): a = sum(math.pi * (c["od"] / 2) ** 2 for c in conds); return math.sqrt(a / PACK_FILL * 4 / math.pi) + 2 * JACKET
    others = [c for c in s1 if not c["name"].startswith("TX_")]
    for t in tx:
        tx_c = [dict(od=t["od_mm"])] if t.get("pair_in_one") else [dict(od=t["od_mm"])] * 2
        od = cord_od(others + tx_c); t["cord_od_mm"] = round(od, 2); t["coil_id_mm_at_17"] = round(CORD["coil_od"] - 2 * od, 2)
    ref = [c for c in others if c["name"].startswith("REF")]; dig = [c for c in others if c["cls"] == "diff"]
    li = next(t for t in tx if t["name"].startswith("Li 6Y")); tx_li = [dict(od=li["od_mm"])] * 2
    variants = {"all conductors (rf2_system S1)": others + [dict(od=1.70)] * 2,
                "REF3 digitised at REF3T (3 STP pairs off the cord)": [c for c in others if c not in ref] + [dict(od=1.70)] * 2,
                "REF3 digitised + one RS-485 pair for TXCMD / TXSTAT / DATA": [c for c in others if c not in ref and c not in dig] + dig[:1] + [dict(od=1.70)] * 2,
                "REF3 digitised + one RS-485 pair, Li 6Y TX pair": [c for c in others if c not in ref and c not in dig] + dig[:1] + tx_li}
    cord = {k: dict(cord_od_mm=round(cord_od(v), 2), coil_id_mm_at_17=round(CORD["coil_od"] - 2 * cord_od(v), 2), fits_spec_7mm=cord_od(v) <= CORD["od"],
                    over_spec_pct=round(100 * (cord_od(v) / CORD["od"] - 1), 1)) for k, v in variants.items()}
    res = dict(status="MODELED: wire data from the owner's catalogs (Rubadue tables parsed); lay factor, lead length, fit clearance and masses ASSUMED; resistance at 20 C (60 C also listed)",
               coil=dict(length_m=round(L_m, 2), turns=co["turns"], rows=co["rows"], columns=len(co["columns_r"]), comb_slot_mm=SLOT, fit_od_mm=FIT_OD, R_model_ohm=R_MODEL,
                         I_rms_scan=i_scan, I_rms_boost=i_boost, cu_needed_for_model_mm2=round(RHO20 * LAY * L_m / R_MODEL, 3)),
               n_constructions=len(cands), fits_and_freq=len(usable),
               coil_best_rule6_ok_in_comb=best_now, coil_blocked_by_rule6_within_10pct=blocked[:5], coil_wider_comb_option=pc,
               rupalit_note="RUPALIT bundles are bare litz with natural-silk wrapping (no voltage rating): usable only as the core of a vendor FEP extrusion; not a coil option on their own",
               tx_pair=tx, cord_packing=dict(spec=CORD, packing_fraction=PACK_FILL, jacket_mm=JACKET, variants=cord), candidates=cands)
    res["findings"] = [
        f"the model's {R_MODEL} ohm needs {res['coil']['cu_needed_for_model_mm2']} mm2 of copper over {L_m:.1f} m; no catalog litz that seats in the 1.3 mm comb and is rated >= 630 V has that much",
        (f"best that fits and meets rule 6: {best_now['part']} ({best_now['ins']} x3, {best_now['v_rating']:.0f} V, OD {best_now['od_mm']} mm): {best_now['R_coil_20C']} ohm, "
         f"coil {best_now['P_coil_boost_W']} W in boost, boost runtime {best_now['boost_h']} h (model {sy['boost_continuous_h']} h)") if best_now else "no construction fits and meets rule 6",
        (f"a wider comb (slot {pc['comb_slot_mm']} / pitch {pc['comb_pitch_mm']} mm) takes {pc['part']} ({pc['v_rating']:.0f} V, OD {pc['od_mm']} mm): {pc['R_coil_20C']} ohm, "
         f"boost runtime {pc['boost_h']} h; coil channel grows {pc['channel_growth_mm']['radial']} mm radially, {pc['channel_growth_mm']['height']} mm in height (re-run L and the field)") if pc else "",
        f"coil cord: the S1 conductor set needs a {cord['all conductors (rf2_system S1)']['cord_od_mm']} mm cable against the 7.0 mm spec (coil ID at 17 mm OD would be {cord['all conductors (rf2_system S1)']['coil_id_mm_at_17']} mm: not coilable in the 18 mm bore); digitising REF3 at REF3T and one RS-485 pair brings it to {cord['REF3 digitised + one RS-485 pair for TXCMD / TXSTAT / DATA']['cord_od_mm']} mm",
        "cord TX pair: HE 18 (2 kV) is the only verified option above 630 V but at 3.1 mm OD; Li 6Y (600 V operating / 900 V peak, 1.5 mm) and the Radix pair (600 V) are blocked by rule 6 by 4.8 %"]
    res["ok"] = bool(cands and usable)
    json.dump(res, open(os.path.join(OUT, "rf2_wire_options.json"), "w"), indent=1)
    for f in res["findings"]: print("-", f)
    for t in tx: print(t["name"], t["rule6_ok"], t["s1_fill"], t["R_pair_ohm"])
    for c in blocked[:3]: print("blocked:", c["part"], c["od_mm"], c["R_coil_20C"], c["boost_h"])
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
