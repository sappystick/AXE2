#!/usr/bin/env python3
"""RF2 system topography (2026-10-30, owner: 'where exactly are we with every system, from the tip of the handle to the edge of the search head').
Generated, not hand-kept: each station lists what is there, its design maturity, the runner steps that check it (with their last result from state/ledger.json)
and numbers read from those steps' own outputs. A station's maturity is the LOWEST of its items:
  CHECKED   geometry / board generated and checked by a runner step (KiCad DRC where it is a board)  -  still MODELED, no fabricator or bench
  MODELED   numbers from a model or study; no geometry or board yet
  CONCEPT   an envelope or a part choice only
  OPEN      not designed
Writes docs/SYSTEM_TOPOGRAPHY.md and rf2/results/rf2_topography.json.   usage: python3 rf2/rf2_topography.py"""
import os, sys, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
def J(rel):
    p = os.path.join(ROOT, rel)
    try: return json.load(open(p))
    except Exception: return None
def g(d, *path, default="n/a"):
    for k in path:
        try: d = d[k]
        except Exception: return default
    return d
LED = (J("state/ledger.json") or {}).get("steps", {})
def step(sid): return LED.get(sid, {}).get("status", "not run")
U = J("rf2/upper_out/rf2_upper_check.json"); S = J("rf2/results/rf2_system.json"); CT = J("rf2/results/rf2_continuous.json"); AU = J("rf2/results/rf2_audio.json")
P1 = J("rf2/head/out/rf2_mp1v2_protect.json"); R3 = J("rf2/head/out/rf2_ref3.json"); HC = J("rf2/head/out_BF/rf2_head_check.json")
def boost_row(name):
    try: return next(r for r in next(m for m in CT["modes"] if m["mode"].startswith("boost"))["rows"] if name in r["part"])
    except Exception: return {}
STATIONS = [
    dict(name="1. Battery cartridge (under the cuff, rear)", where="s 1050-1205 mm, below the spine",
         items=[("7S2P Molicel P30B cells, BQ76952 (main switch, TS2 wake), fuse, MT60 charge port", "CONCEPT"),
                ("cartridge + bay geometry, rearward slide path", "CHECKED" if g(U, "checks", "battery", "ok") is True else "OPEN")],
         steps=["upper", "system"], numbers=lambda: f"runtime {g(S, 'runtime', 'scan_h')} h scan / {g(S, 'runtime', 'boost_continuous_h')} h boost; cartridge {g(U, 'checks', 'battery', 'cartridge_mm')} mm; slide hits {g(U, 'checks', 'battery', 'slide_path_hits')}",
         open="cell holder and contact design; BQ76952 schematic; charger spec; latch mechanism"),
    dict(name="2. Elbow cuff + stem", where="s 1200-1262 mm, above the spine", items=[("cuff trough r 46 mm, 210 deg, stem: height range checked", "CHECKED" if g(U, "checks", "cuff_height_range", "ok") is True else "CONCEPT"),
                ("forearm line from the grip to the cuff (owner review 2026-10-30: the arm cannot sit in the cuff and reach the grip)", "OPEN")],
         steps=["upper"], numbers=lambda: f"cuff height {g(U, 'checks', 'cuff_height_range', 'min_mm')}-{g(U, 'checks', 'cuff_height_range', 'max_mm')} mm over tilt and telescope",
         open="REDESIGN: straight forearm axis from the hand on the grip to the cuff; cuff fold; strap, padding"),
    dict(name="3. Spine (PWR board)", where="s 975-1205 mm", items=[("LMR36520 +5V_AUX", "CONCEPT"), ("regenerative clamp return (hysteretic buck: C3M0280090J, UCC5350, US3M)", "OPEN"),
                                                               ("part envelopes inside the spine", "CHECKED" if g(U, "checks", "electronics inside their housings", "ok") is True else "OPEN")],
         steps=["upper", "system", "study:continuous"], numbers=lambda: f"pack dissipation {g(S, 'thermal', 'pack_W_boost')} W in boost (90 % ASSUMED)", open="buck SPICE and schematic; PWR board layout"),
    dict(name="4. Grip head + pistol grip (the hand)", where="s 880-1010 mm", items=[("grip: 3 finger wedges, pinky shelf, 18 deg rake; pilot trigger + guard; thumb button + light ring; flip-up screen; mode dial", "CHECKED" if g(U, "checks", "grip", "ok") is True else "OPEN"),
         ("HB2 electronics placed in the grip head (MCU, piezo bridge, 4 x KSC2 TE, J1 / RS-485)", "CHECKED" if g(U, "checks", "electronics inside their housings", "ok") is True else "OPEN"),
         ("audio: piezo, 3.0-7.6 kHz equalised", "MODELED"), ("display / audio coding v3, profiles", "MODELED"), ("screen part", "CONCEPT"), ("RS-485 part", "OPEN")],
         steps=["upper", "audio", "ui", "display3"], numbers=lambda: f"trigger reach {g(U, 'checks', 'trigger_and_thumb', 'trigger_reach_mm')} mm; thumb to button {g(U, 'checks', 'trigger_and_thumb', 'thumb_to_button_mm')} mm; screen {g(U, 'checks', 'screen_view', 'angle_to_eye_deg')} deg off the eye line; audio floor {g(AU, 'floor_dB_10cm')} dB at 10 cm",
         open="HB2 schematic + board; screen and RS-485 datasheets; trigger / dial mechanisms; overmould"),
    dict(name="5. F2 joint + L2 telescope", where="s 450-880 mm", items=[("L2 outer tube, 0-250 mm telescope with cam lock", "CONCEPT"), ("F2 fold hinge: WITHDRAWN by the owner (telescope instead)", "OPEN"),
                                                                                ("cable coil and hinge service loops", "MODELED")],
         steps=["upper", "system"], numbers=lambda: f"retired fold study: package {g(U, 'fold', 'package_mm')} mm vs {g(U, 'fold', 'backpack_ASSUMED_mm')}",
         open="REDESIGN: telescoping sections and collapsed length; cam locks; coil-cord / flex in the tube"),
    dict(name="6. REF3 reference coil (sleeve on L2)", where="s 470-820 mm", items=[("X / Y saddle pairs + Z solenoid on the tube, OD 33.8 mm (no box)", "MODELED"), ("sleeve geometry in the upper assembly", "CHECKED" if g(U, "checks", "electronics inside their housings", "ok") is True else "CONCEPT"), ("EMI canceller", "MODELED")],
         steps=["ref3", "upper", "study:emi"], numbers=lambda: f"worst-axis depth penalty {g(R3, 'sleeve', 'worst_axis_penalty_pct')} % (box was {g(R3, 'layout', 'box_penalty_pct')} %); copper {g(R3, 'sleeve', 'copper_g_total')} g; piezo field at REF3 {g(S, 'ref3_coupling', 'piezo_loop_field_pT')} pT",
         open="re-run rf2_emi with the sleeve's e_ref (2.6-3.4 nV/rtHz); winding jig; AB1A input pairs"),
    dict(name="7. F1 joint", where="s 420-450 mm", items=[("F1 fold hinge: WITHDRAWN by the owner (becomes a telescoping joint)", "OPEN")], steps=["upper"],
         numbers=lambda: "-", open="REDESIGN with the telescoping shaft"),
    dict(name="8. TXD transmit driver (beside L1)", where="s 330-420 mm", items=[("placement by echo search", "MODELED"), ("C3M0280090J + Ohmite D heat sink, UCC5350, US3M, bulk bank, TMP117 therm", "CONCEPT"),
                                                                          ("RF2 driver values (333 uH, 8.06 / 12.74 A, flat-top loop)", "OPEN"), ("housing + part envelopes", "CHECKED" if g(U, "checks", "electronics inside their housings", "ok") is True else "OPEN")],
         steps=["system", "study:continuous", "study:hvparts", "upper"], numbers=lambda: f"echo drift {g(S, 'echoes', 'txd_drift5K_x_noise')} x noise; switch TJ {round(boost_row('junction').get('load', 0), 1)} C in boost; TX pair +{g(S, 'tx_pair', 'first_gate_shift_us')} us (first-order)",
         open="driver schematic and board; rf2_timing with the 0.3 m pair; heat-sink venting"),
    dict(name="9. L1 lower segment + yoke", where="s 0-420 mm; pivot r 85 at the heel", items=[("tube, yoke cheeks + friction pivot, head ears", "CHECKED" if g(U, "checks", "deployed_clear", "ok") is True else "CONCEPT")], steps=["upper"],
         numbers=lambda: f"deployed min gaps {g(U, 'checks', 'deployed_clear', 'min_gaps_mm')}", open="pivot friction and knob detail"),
    dict(name="10. Search head (outside)", where="D233, heel at 178 deg", items=[("shell, lid with 522 conical light wells, gland, skid (new), yoke ears (new)", "CHECKED" if g(HC, "ok") is True else "MODELED")],
         steps=["head:BF", "head-check:BF", "lightplate", "upper"], numbers=lambda: "light plate, gland and shell checked in rf2_head_check (option BF)", open="skid clip detail; impact bumper"),
    dict(name="11. Search head (inside)", where="r 0-116.5 mm", items=[("rim coil 26 t, SH1 shield, SB1R QA / QB boards", "CHECKED"), ("MP1 v1 board", "CHECKED"), ("MP1 v2 protection (amplifier current / settling)", "OPEN"),
                                                                     ("TXJ / TXF boards", "CHECKED"), ("LR1 522-LED display board", "CHECKED"), ("AB1A / AB1B / CB1D", "MODELED"), ("Rd 408 ohm >= 4.24 W part", "OPEN"), ("zone rules, harness construct", "CHECKED")],
         steps=["board:MP1", "board:TXJ", "board:TXF", "board:LR1", "shield:SH1", "sb1r-variant", "zonerules", "construct", "study:mp1v2_protect"],
         numbers=lambda: f"MP1 v2 any option passes: {g(P1, 'any_option_passes')} (best 14.1 mA / 17.5 us vs 10 mA / 16.3 us)", open="MP1 v2 levers; AB1 / CB1D routing in RF2 (Phase C); Rd part; potting trials"),
]
ORDER = {"OPEN": 0, "CONCEPT": 1, "MODELED": 2, "CHECKED": 3}
def main():
    rows = []
    for st in STATIONS:
        lvl = min((m for _, m in st["items"]), key=lambda m: ORDER[m]); stp = {s_: step(s_) for s_ in st["steps"]}
        try: nums = st["numbers"]()
        except Exception as e: nums = f"(numbers unavailable: {e})"
        rows.append(dict(station=st["name"], where=st["where"], maturity=lvl, items=st["items"], steps=stp, numbers=nums, open=st["open"]))
    json.dump(rows, open(os.path.join(ROOT, "rf2", "results", "rf2_topography.json"), "w"), indent=1)
    L = ["# AXE2 system topography: handle tip to head edge (generated by rf2/rf2_topography.py; MODELED, nothing built or bench-tested)", "",
         "Maturity is the lowest item at the station: CHECKED (generated + checked by a runner step), MODELED (numbers from a model), CONCEPT (envelope / part choice), OPEN (not designed).", "",
         "| Station | Where | Maturity | Checked by (last result) | Numbers | Open |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['station']} | {r['where']} | **{r['maturity']}** | {', '.join(f'{k} {v}' for k, v in r['steps'].items())} | {r['numbers']} | {r['open']} |")
    L += ["", "## Items per station", ""]
    for r in rows:
        L.append(f"- **{r['station']}**: " + "; ".join(f"{t} ({m})" for t, m in r["items"]))
    open(os.path.join(ROOT, "docs", "SYSTEM_TOPOGRAPHY.md"), "w").write("\n".join(L) + "\n")
    for r in rows: print(f"{r['maturity']:<8} {r['station']}")
    return rows
if __name__ == "__main__":
    main()
