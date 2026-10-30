#!/usr/bin/env python3
"""AXE2 study: how thin can the head be (owner 2026-10-30: thinner than 1 inch), using the flex fabrication data the owner supplied
(Wuerth CBT 'Design guide flex solutions' 06/25; FCT 'Flex Circuit Design Guide' 07/25) and the RF2 coil model. MODELED; ASSUMED values are marked.

Three explicit z-stacks (z up from the skid's underside; mm):
  A today        the rf2_head SPEC (HANDOFF section 3): rigid SH1 0.4 / QA 0.8 / QB 0.8, AB1 / MP1 / TXJ tier at 4.6-12.0, CB1D on a tower at 11.5-19.5,
                 display 21.6-23.9, lid 23.9-25.4; the coil (9 rows x 3 columns) at 3.8-17.8 in the rim channel.
  B single tier  CB1D moved down to the AB1 tier (they do not overlap in plan: CB1D r < 39, AB1 r 62-102, MP1 / TXJ at the rim side); the display
                 then sits 0.5 mm above the tallest island (TXJ, 4.8 mm above its board); the coil must fit under the display at the rim.
  C thin layers  B + SH1, QA, QB and the display as 2-layer adhesiveless flex (PURE.flex 2F: polyimide 50 um + coverlay 25 um x 2 + Cu 18 um x 2 =
                 about 0.14 mm; 0.15 used), islands with parts <= 3.0 mm above (AB1 class; TXJ lands lowered, ASSUMED) and the bay floor 0.6 mm.
Coil at equal energy per pulse (10.8 mJ): the 26 turns re-shaped into rows x columns that fit the rim window (columns inward from r 113.4 at
1.6 mm pitch, down to r 103.8: AB1 ends at r 102). Reported: the series inductance (C.L_turns), the current for 10.8 mJ, the axial field per pulse
at 100 / 200 mm, and the RF2 depth figure (C.evaluate: equal energy, RX-Q receiver, gold spheres). NOTE (correction 2026-10-30): 'depth_mm_equal_energy' below is rf2_coil_search.evaluate, i.e. the QUADRUPOLE (bearing) channel; the mono
(detection) depth of these options is in rf2/rf2_depth_levers.py. Not modeled here: the self-capacitance (sets the
first gate with L; study 2), the flex receive coils' 18 um copper (resistance x2 against 35 um: thermal noise of those channels x sqrt 2 if their
own resistance dominates; study 3).
usage: python3 rf2/rf2_thin.py  -> rf2/results/rf2_thin.json, rf2/results/rf2_thin.png"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C
OUT = os.path.join(HERE, "results"); E0 = 10.8e-3; PITCH = 1.6; COLS_R = [113.4 - PITCH * k for k in range(7)]
def stack(name, skid, rx, floor, island_bottom_gap, islands, tiers, disp, led, lid, clear=0.5):
    """z levels of one option; islands: [(name, below, board, above)]; tiers: 1 (all islands on one level) or 2 (CB1D on a tower)"""
    z_rx = skid + rx; z_floor = z_rx + floor; z_isl = z_floor + island_bottom_gap
    tops = {n: z_isl + b + t + a for n, b, t, a in islands}
    if tiers == 2: tops["CB1D"] = 19.5                                                  # today: on the tower (HANDOFF section 3)
    top_isl = max(tops.values())
    coil_top_min = z_floor + 0.6 + math.ceil(26 / 7) * PITCH                              # 26 turns need >= 4 rows (7 columns is the inward limit, r 103.8)
    z_disp = max(top_isl, coil_top_min) + clear if tiers == 1 else 22.85                 # today: the display flex at z 22.85 (SPEC; 21.6-22.85 is the boss gap)
    H = z_disp + disp + led + lid
    coil_window = (z_floor + 0.6, z_disp - clear)                                       # first row 0.6 above the floor (SPEC row0 = floor + 0.6)
    return dict(name=name, z_rx_top=round(z_rx, 2), z_floor=round(z_floor, 2), island_tops=tops, z_display=round(z_disp, 2), height_mm=round(H, 2),
                coil_window_z=[round(v, 2) for v in coil_window])
ISL_TODAY = [("AB1A/B", 1.0, 1.6, 3.0), ("MP1", 1.0, 1.6, 3.4), ("TXJ", 1.0, 1.6, 4.8)]
ISL_ONE = ISL_TODAY + [("CB1D", 2.0, 1.6, 4.4)]
ISL_LOW = [("AB1A/B", 1.0, 1.6, 3.0), ("MP1", 1.0, 1.6, 3.0), ("TXJ", 1.0, 1.6, 3.0), ("CB1D", 1.0, 1.6, 3.0)]
OPTIONS = [stack("A today (SPEC)", 1.2, 2.0, 0.6, 0.8, ISL_TODAY, 2, 0.4, 0.65, 1.5),
           stack("B single tier (CB1D lowered)", 1.2, 2.0, 0.6, 0.8, ISL_ONE, 1, 0.4, 0.65, 1.5),
           stack("C single tier + flex layers + low-profile parts", 1.2, 0.45, 0.6, 0.8, ISL_LOW, 1, 0.15, 0.65, 1.5)]
def coil_for(window, turns=26):
    rows = int((window[1] - window[0]) // PITCH)
    for r in range(min(rows, 9), 0, -1):
        cols = math.ceil(turns / r)
        if cols <= len(COLS_R):
            T = [(COLS_R[c] * 1e-3, (window[0] + PITCH * (k + 0.5)) * 1e-3, 1) for k in range(r) for c in range(cols)][:turns]
            return T, r, cols
    return None
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    res = dict(status="MODELED: z-stacks from the SPEC and the flex guides (+ ASSUMED part heights); coil at equal energy (10.8 mJ); depth by rf2_coil_search.evaluate",
               sources=["Wuerth Elektronik CBT, Design guide flex solutions, 06/25: polyimide 50 um, coverlay 25 um, Cu 12/18/35 um; PURE.flex / SLIM.flex > 100 um; "
                        "RIGID.flex >= 0.8 mm; bend radius >= 10 x thickness (1-2 layers), 20 x (4 layers); no ENIG at bends",
                        "FCT Flex Circuit Design Guide 07/25: bend ratio 10:1 single / double, 20:1 multilayer; UHDI 0.05 / 0.05 mm, laser via 0.08 mm; Cu 9-70 um"],
               options=[])
    base = None
    for o in OPTIONS:
        c = coil_for(o["coil_window_z"])
        if c is None: o["coil"] = "does not fit"; res["options"].append(o); continue
        T, rows, cols = c; Ls = C.L_turns(T); I = math.sqrt(2 * E0 / Ls)
        P = np.array([[0, 0, -0.1], [0, 0, -0.2]]); Bz = C.B_turns(T, P)[:, 2] * I * 1e6
        row, *_ = C.evaluate(o["name"], T, 1, masses=(1.0, 20.0))
        o["coil"] = dict(rows=rows, cols=cols, r_inner_mm=round(COLS_R[cols - 1], 1), z_rows=[round(T[0][1] * 1e3, 2), round(T[-1][1] * 1e3, 2)],
                         L_series_uH=round(Ls * 1e6, 1), I_for_10p8mJ_A=round(I, 2), Bz_uT_per_pulse_100_200mm=[round(float(v), 2) for v in Bz], depth_mm_equal_energy=row["depth_mm"])
        if base is None: base = o
        o["vs_today"] = dict(height_pct=round(100 * (o["height_mm"] / base["height_mm"] - 1), 1),
                             Bz_pct=[round(100 * (a / b - 1), 1) for a, b in zip(o["coil"]["Bz_uT_per_pulse_100_200mm"], base["coil"]["Bz_uT_per_pulse_100_200mm"])],
                             L_pct=round(100 * (o["coil"]["L_series_uH"] / base["coil"]["L_series_uH"] - 1), 1),
                             depth_pct={k: round(100 * (v / base["coil"]["depth_mm_equal_energy"][k] - 1), 1) for k, v in o["coil"]["depth_mm_equal_energy"].items()})
        res["options"].append(o); print(json.dumps(o), flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_thin.json"), "w"), indent=1)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.2)); y = 0
    for o in res["options"]:
        lv = [("skid", 0, 1.2, "#999"), ("RX / shield", 1.2, o["z_rx_top"], "#c9a227"), ("bay floor", o["z_rx_top"], o["z_floor"], "#bbb"),
              ("islands", o["z_floor"] + 0.8, max(o["island_tops"].values()), "#2e7d32"), ("display", o["z_display"], o["height_mm"] - 1.5, "#d35400"),
              ("lid", o["height_mm"] - 1.5, o["height_mm"], "#cfd8dc")]
        for n, a, b, col in lv: ax.barh(y, b - a, left=a, color=col, edgecolor="k", lw=0.3)
        if isinstance(o.get("coil"), dict): ax.barh(y + 0.32, o["coil"]["z_rows"][1] - o["coil"]["z_rows"][0] + 1.2, left=o["coil"]["z_rows"][0] - 0.6, height=0.2, color="#e67e22")
        ax.text(o["height_mm"] + 0.3, y, f"{o['name']}: {o['height_mm']} mm" + (f", coil {o['coil']['rows']}x{o['coil']['cols']}, 1 g {o['coil']['depth_mm_equal_energy']['1.0 g']} mm"
                                                                               if isinstance(o.get("coil"), dict) else ""), va="center", fontsize=7)
        y += 1
    ax.set_yticks([]); ax.set_xlabel("z (mm)"); ax.set_xlim(0, 45); ax.set_title("RF2 head thickness options (MODELED): z-stacks; orange bar = rim coil rows", loc="left", fontsize=9)
    fig.savefig(os.path.join(OUT, "rf2_thin.png"), dpi=130, bbox_inches="tight")
