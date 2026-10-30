#!/usr/bin/env python3
"""RF2 battery pack options (2026-10-30, owner: 'a swappable custom pack that slides onto a rail like a cordless drill, under the chassis where the
cartridge is now; could it be a lighter option; is it feasible in any configuration'). MODELED.

What is compared (every option stays 7S so the 21-29.4 V bus, the BQ76952 7S BMS, TXD and the HV design are unchanged):
  A  baseline: 7S2P Molicel P30B cartridge sliding rearward INTO an enclosed bay (rf2_chassis BATTERY_BAY + BATTERY_CARTRIDGE)
  B  drill-style: the same cells; the bay is removed, the cartridge shell carries two T-rails + a latch and slides onto a dock under the chassis
  C  drill-style 7S1P Molicel P45B (21700)
  D  drill-style 7S1P LG M50T (21700)
  E  drill-style 7S RC LiPo soft pack (Gens Ace 5000 mAh 45C, vendor listing) inside a hard shell, with a BQ76952 board added (RC packs have none)
  F  drill-style 7S1P P30B, small, carried with a spare (fails the 6 h per-pack rule: owner decision)
Physics / budget used: scan and boost power from rf2_system (usable Wh / runtime h), the 6 h scan rule (rf2_system 'scan runtime >= 6 h'), 90 % usable
energy (ASSUMED, as rf2_system), the pack's lever arm about the hand from rf2_chassis (mass.lever_mm), cell values from datasheets on file (marked where
the source is weak). Shell / rail / latch / BMS masses are ASSUMED and marked. No bench test.
Writes rf2/results/rf2_pack_options.json.   usage: python3 rf2/rf2_pack_options.py"""
import os, sys, json, math
import trimesh
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results")
SYS = json.load(open(os.path.join(OUT, "rf2_system.json")))
CH = json.load(open(os.path.join(HERE, "chassis_out", "rf2_chassis_check.json")))
RHO_PETG = 1.27                       # g/cm3 (ASSUMED, PETG); printed parts at 100 % infill as the head budget does
USABLE = 0.90                         # as rf2_system (ASSUMED)
RULE_H = 6.0                          # rf2_system 'scan runtime >= 6 h'
CELLS = {   # name: (Wh typ, g max, d max mm, h max mm, max continuous discharge A at the coldest listed band, source)
    "Molicel P30B": (10.8, 47.0, 18.6, 65.2, 30.0, "data/datasheets/Molicel_INR-18650-P30B_PDS_v1.0.pdf (DATASHEET_LOG)"),
    "Molicel P45B": (16.2, 70.0, 21.55, 70.15, 45.0, "data/datasheets/Molicel_INR-21700-P45B_PDS_v1.2.pdf (min 15.5 Wh)"),
    "LG M50T": (18.2, 70.0, 21.44, 70.8, 2.425, "data/datasheets/LG_INR21700_M50T_spec_2018-07_rev0.pdf (rev 0 draft, values 'tentative'; min 17.6 Wh; 0.5 C below 10 C)"),
}
LIPO = dict(name="Gens Ace 5000 mAh 7S 45C", Wh=5.0 * 25.9, g=824.0, mm=(161.0, 46.0, 51.0),
            source="vendor listing https://www.gensace.de/gens-ace-5000mah-25-9v-45c-7s1p-lipo-battery-pack-with-xt90.html (UNVERIFIED: no datasheet)")
WALL = 3.0                            # cartridge wall (rf2_chassis cart_wall)
OVERHEAD_2P = 90.0                    # rf2_chassis cartridge overhead for 14 cells: shell + BQ76952 board + MT60 + strip (ASSUMED there)
RAIL_LATCH_G = 22.0                   # two T-rails + a printed spring latch on the pack (ASSUMED)
DOCK_G = 30.0                         # the dock under the chassis: rails, MT60 + pin block, catch (ASSUMED)
GASKET_G = 6.0                        # a face seal round the contacts (ASSUMED; the bay used to keep spray off)
LIPO_SHELL_EXTRA_G = 40.0             # a puncture-resistant shell + fish paper + swell gap for a soft pack (ASSUMED)
BMS_BOARD_G = 15.0                    # BQ76952 board added to a bare RC pack (ASSUMED)

def stl_g(name):
    m = trimesh.load(os.path.join(HERE, "chassis_out", name + ".stl")); return abs(m.volume) / 1000.0 * RHO_PETG

def main():
    rt = SYS["runtime"]; p_scan = rt["usable_Wh"] / rt["scan_h"]; p_boost = rt["usable_Wh"] / rt["boost_continuous_h"]
    lever = next(v for k, v in CH["mass"]["lever_mm"].items() if k.startswith("battery")) / 1000.0     # m, hand minus pack (negative: behind the hand)
    base_cart = next(v for k, v in CH["mass"]["items_g"].items() if k.startswith("battery")); m_tot0 = CH["mass"]["total_g"]; tq0 = CH["mass"]["torque_about_hand_Nm"]
    bay_g = stl_g("BATTERY_BAY")
    i_boost = p_boost / (7 * 3.0)                                                                   # A at the 21 V cut-off (worst case)
    opts = []
    def add(key, desc, wh_nom, pack_g, dims, removes_bay, n_p, cell=None, notes=()):
        wh_u = wh_nom * USABLE; dm = pack_g - base_cart + (DOCK_G + GASKET_G - bay_g if removes_bay else 0.0)
        r = dict(key=key, desc=desc, Wh_nominal=round(wh_nom, 1), Wh_usable=round(wh_u, 1), scan_h=round(wh_u / p_scan, 2), boost_h=round(wh_u / p_boost, 2),
                 meets_6h=wh_u / p_scan >= RULE_H, pack_g=round(pack_g), system_delta_g=round(dm), system_total_g=round(m_tot0 + dm),
                 torque_about_hand_Nm=round(tq0 + dm_pack_torque(pack_g - base_cart, lever), 2), pack_mm=[round(v, 1) for v in dims],
                 cell_current_boost_A=round(i_boost / n_p, 2), notes=list(notes))
        if cell: u = i_boost / n_p / CELLS[cell][4]; r["cell_current_frac_of_rating"] = round(u, 2); r["cell_current_ok"] = bool(u <= 1.0); r["cell_source"] = CELLS[cell][5]
        if cell and u > 0.5: r["notes"].append(f"boost at the 21 V cut-off uses {100 * u:.0f} % of the cell's continuous rating in its coldest band: inside the rating, little margin")
        opts.append(r); return r
    def box(cell, n_s, n_p, rows=1):
        wh, g, d, h, _, _ = CELLS[cell]; per_row = math.ceil(n_s * n_p / rows)
        return (per_row * d + 2 * WALL, h + 2 * WALL, rows * d + 4.0 + 2 * WALL)                       # along the shaft x lateral x height (+4 mm BMS / strip)
    def pack_mass(cell, n):
        return n * CELLS[cell][1] + OVERHEAD_2P * (0.55 + 0.45 * n / 14.0)                             # shell + strip scale with cell count, BMS / MT60 fixed (ASSUMED)
    add("A", "baseline: 7S2P P30B cartridge into an enclosed bay, rear slide", 14 * 10.8, base_cart, CH["checks"]["battery_slide"]["cartridge_mm"] if "checks" in CH else (136.2, 71.2, 47.2), False, 2, "Molicel P30B",
        ["the cartridge already slides out rearward with blind MT60 + spring-pin contacts (ICD I6)"])
    add("B", "drill-style rail pack, same 7S2P P30B (bay removed)", 14 * 10.8, base_cart + RAIL_LATCH_G, box("Molicel P30B", 7, 2, 2), True, 2, "Molicel P30B",
        [f"removes the {bay_g:.0f} g bay; adds rails / latch {RAIL_LATCH_G:.0f} g, dock {DOCK_G:.0f} g, face seal {GASKET_G:.0f} g (ASSUMED)"])
    for key, cell in (("C", "Molicel P45B"), ("D", "LG M50T")):
        for rows in (1, 2):
            add(key + str(rows), f"drill-style rail pack, 7S1P {cell}, {rows} row(s)", 7 * CELLS[cell][0], pack_mass(cell, 7) + RAIL_LATCH_G, box(cell, 7, 1, rows), True, 1, cell,
                ["1P: no parallel group to balance; the BQ76952 still balances the 7 cells"] + (["M50T spec is a 2018 rev 0 draft ('tentative'); get the current LG spec before buying"] if cell == "LG M50T" else []))
    lipo_g = LIPO["g"] + LIPO_SHELL_EXTRA_G + BMS_BOARD_G + RAIL_LATCH_G
    add("E", f"drill-style hard shell round a 7S RC LiPo ({LIPO['name']})", LIPO["Wh"], lipo_g, (LIPO["mm"][0] + 2 * WALL + 4, LIPO["mm"][1] + 2 * WALL + 4, LIPO["mm"][2] + 2 * WALL + 4), True, 1, None,
        [LIPO["source"], f"{LIPO['Wh'] / LIPO['g'] * 1000:.0f} Wh/kg bare vs {14 * 10.8 / (14 * 47) * 1000:.0f} (P30B) / {18.2 / 70 * 1000:.0f} (M50T) cells: heavier for the same energy",
         "no BMS in an RC pack (balance lead only): a BQ76952 board must be added; soft pouch needs puncture protection and a swell gap; 45C rating is unused (1.2 A draw)"])
    add("F", "drill-style small 7S1P P30B, carried with a spare", 7 * 10.8, pack_mass("Molicel P30B", 7) + RAIL_LATCH_G, box("Molicel P30B", 7, 1, 1), True, 1, "Molicel P30B",
        ["fails 6 h per pack; two packs give the baseline runtime; a swap restarts the detector unless a hold-up is added"])
    feas = [o for o in opts if o["key"] != "A" and o["meets_6h"] and o.get("cell_current_ok", True)]
    best = min(feas, key=lambda o: o["system_total_g"])
    res = dict(status="MODELED: cell values from datasheets on file (M50T from a rev 0 draft; the LiPo from a vendor listing, UNVERIFIED); shell, rail, latch, dock, seal and BMS masses ASSUMED; no bench test",
               p_scan_W=round(p_scan, 2), p_boost_W=round(p_boost, 2), boost_current_at_21V_A=round(i_boost, 2), pack_lever_mm=round(lever * 1000, 1), bay_g_from_stl=round(bay_g, 1),
               baseline_total_g=m_tot0, baseline_torque_Nm=tq0, options=opts, lightest_meeting_6h=best["key"],
               conclusion=dict(drill_rail_feasible=True, rc_lipo_lighter=bool(next(o for o in opts if o["key"] == "E")["system_total_g"] < m_tot0),
                               lightest=f"{best['key']}: {best['desc']}, {best['system_total_g']} g system ({best['system_delta_g']:+d} g), {best['scan_h']} h scan"))
    res["ok"] = bool(len(opts) == 8 and res["conclusion"]["drill_rail_feasible"])
    json.dump(res, open(os.path.join(OUT, "rf2_pack_options.json"), "w"), indent=1, default=float)
    for o in opts: print(o["key"], o["Wh_nominal"], o["scan_h"], o["meets_6h"], o["pack_g"], o["system_delta_g"], o["torque_about_hand_Nm"], o["pack_mm"], o.get("cell_current_ok"))
    print(res["conclusion"]); return res

def dm_pack_torque(dm_g, lever_m): return dm_g * 9.81e-3 * lever_m

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
