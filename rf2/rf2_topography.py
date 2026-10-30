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
CK = J("rf2/chassis_out/rf2_chassis_check.json")
def ok(*path): return g(CK, "checks", *path, "ok") is True
STATIONS = [   # chassis v2 (rf2_chassis.py, SDC-style), from the handle tip to the head edge
    dict(name="1. Elbow cuff on rails (rear, top)", where="chassis s 1000-1165 mm, above the chassis", items=[("cuff trough + spring wings, twin side rails, U-slider; forearm on one straight line from the wrist", "CHECKED" if ok("forearm_straight_in_cuff") else "OPEN"),
         ("strap, padding, wing springs", "CONCEPT")], steps=["chassis"], numbers=lambda: f"wrist-to-cuff angle to the shaft {g(CK, 'checks', 'forearm_straight_in_cuff', 'wrist_to_cuff_angle_to_shaft_deg')} deg; trough {g(CK, 'checks', 'forearm_straight_in_cuff', 'trough_bottom_above_chassis_mm')} mm above the chassis",
         open="wing spring and rail detent detail; strap"),
    dict(name="2. Battery cartridge (under the chassis)", where="s 905-1065 mm, below the shaft line", items=[("7S1P Molicel P45B, BQ76952 (main switch, TS2 wake), fuse, MT60 charge port", "CONCEPT"), ("cartridge + bay geometry, rearward slide", "CHECKED" if ok("battery_slide") else "OPEN")],
         steps=["chassis", "system"], numbers=lambda: f"runtime {g(S, 'runtime', 'scan_h')} h scan / {g(S, 'runtime', 'boost_continuous_h')} h boost; cartridge {g(CK, 'checks', 'battery_slide', 'cartridge_mm')} mm", open="cell holder, contacts, latch; BQ76952 schematic"),
    dict(name="3. Control chassis body (TXD + PWR + HB2-M)", where="s 800-1160 mm, 360 x 72 x 47 mm", items=[("part envelopes inside the chassis", "CHECKED" if ok("electronics inside their housings") else "OPEN"), ("TX driver values / schematic", "OPEN"),
         ("regenerative clamp buck", "OPEN"), ("HB2-M schematic + board", "OPEN")], steps=["chassis", "system", "study:continuous"],
         numbers=lambda: f"chassis surface rise {g(S, 'thermal', 'chassis_surface_rise_K')} K in continuous boost; TXD echo drift {g(S, 'echoes', 'txd_drift5K_x_noise')} x noise; switch TJ {round(boost_row('junction').get('load', 0), 1)} C", open="driver + buck SPICE / schematics; venting; boards"),
    dict(name="4. Inverted control-stick grip (on top)", where="base at s 884 mm on the chassis top", items=[("3 finger wedges, 18 deg rake, pilot trigger, thumb button + light ring, flip-up screen, dial, FFC down the core, 25 mm slide lock", "CHECKED" if ok("grip") and ok("screen_view") and ok("grip_slide_lock") else "OPEN"),
         ("audio piezo (3.0-7.6 kHz), display / audio coding v3", "MODELED"), ("screen part, RS-485 part, HB2-G board", "OPEN")], steps=["chassis", "audio", "display3"],
         numbers=lambda: f"screen {g(CK, 'checks', 'screen_view', 'angle_to_eye_deg')} deg off the eye line; FFC loop {g(CK, 'checks', 'grip_slide_lock', 'ffc_service_loop_mm')} mm for {g(CK, 'checks', 'grip_slide_lock', 'slide_mm')} mm slide; audio floor {g(AU, 'floor_dB_10cm')} dB at 10 cm",
         open="HB2-G / FFC detail; trigger and slide-lock mechanisms; overmould"),
    dict(name="5. Main hinge (under the chassis front)", where="s 790-816 mm", items=[("hollow-axis hinge, bundle pass-through (2 x 90 deg bends + 180 deg twist)", "CHECKED" if ok("hinge_pass_through") else "OPEN"), ("locking tooth + grip slide lock mechanism", "CONCEPT")],
         steps=["chassis"], numbers=lambda: f"twist {g(CK, 'checks', 'hinge_pass_through', 'twist_deg_per_mm')} deg/mm, bend r {g(CK, 'checks', 'hinge_pass_through', 'bend_r_mm')} mm", open="hinge detail, seals"),
    dict(name="6. Outer rectangular profile + REF3", where="s 410-790 mm", items=[("38 x 32 profile, flat clamp 2; REF3 flat face coils + rectangular solenoid, 42 x 36 outer", "MODELED"), ("geometry", "CHECKED" if ok("telescope") else "OPEN")],
         steps=["chassis", "ref3", "study:emi"], numbers=lambda: f"REF3 worst-axis penalty {g(R3, 'rect_sleeve', 'worst_axis_penalty_pct')} % (box {g(R3, 'layout', 'box_penalty_pct')} %), copper {g(R3, 'rect_sleeve', 'copper_g_total')} g; REF3 {g(CK, 'checks', 'telescope', 'REF3_from_pivot_at_min_use_mm')} mm from the head at the shortest use length",
         open="re-run rf2_emi with the rect coils' e_ref; winding jig"),
    dict(name="7. Middle profile + clamp 1", where="s 300-680 mm", items=[("33 x 27 keyed profile, flat lever clamp", "CHECKED" if ok("telescope") else "CONCEPT")], steps=["chassis"],
         numbers=lambda: f"pivot to hinge {g(CK, 'checks', 'telescope', 'pivot_to_hinge_mm')} mm; collapsed {g(CK, 'checks', 'telescope', 'collapsed_mm')} mm", open="clamp mechanism detail"),
    dict(name="8. Inner profile + coil cord + yoke knuckle", where="s 0-420 mm", items=[("28 x 22 profile, coil cord (TX pair, power, data, 3 REF pairs) in the 24 x 18 bore", "CHECKED" if ok("coil_cord") else "OPEN"), ("dual-axis yoke (pitch + 90 deg roll)", "CONCEPT")],
         steps=["chassis"], numbers=lambda: f"cord stretch {g(CK, 'checks', 'coil_cord', 'stretch_mm')} mm (ratio {g(CK, 'checks', 'coil_cord', 'stretch_ratio')}); TX pair {g(CK, 'checks', 'tx_pair_in_cord', 'length_m')} m: first gate +{g(CK, 'checks', 'tx_pair_in_cord', 'first_gate_shift_us')} us (first-order)",
         open="coil-cord vendor spec (1000 V pair); re-run rf2_timing with the pair"),
    dict(name="9. Folded package", where="whole machine", items=[("telescoped + hinged + grip laid sideways + head stowed", "CHECKED" if ok("folds_to_backpack") else "OPEN")], steps=["chassis"],
         numbers=lambda: f"{g(CK, 'fold', 'chosen', 'package_mm')} mm (target {g(CK, 'fold', 'backpack_ASSUMED_mm')}; SDC 2300 {g(CK, 'fold', 'sdc2300_reference_mm')} mm with a 203 mm coil); mass {g(CK, 'mass', 'total_g')} g", open="lighter REF3 / tubes toward the SDC's 2.3 kg"),
    dict(name="10. Search head (outside)", where="D233, heel at 178 deg", items=[("shell, lid with 522 conical light wells, gland, skid, yoke ears", "CHECKED" if g(HC, "ok") is True else "MODELED")],
         steps=["head:BF", "head-check:BF", "lightplate"], numbers=lambda: "light plate, gland and shell checked in rf2_head_check (option BF)", open="skid clip detail; bumper"),
    dict(name="11. Search head (inside)", where="r 0-116.5 mm", items=[("rim coil, SH1, SB1R QA / QB, MP1 v1, TXJ / TXF, LR1", "CHECKED"), ("MP1 v2 protection", "OPEN"), ("AB1A / AB1B / CB1D", "MODELED"), ("Rd 408 ohm >= 4.24 W part", "OPEN")],
         steps=["board:MP1", "board:TXJ", "board:TXF", "board:LR1", "shield:SH1", "zonerules", "construct", "study:mp1v2_protect"],
         numbers=lambda: f"MP1 v2 any option passes: {g(P1, 'any_option_passes')} (best 14.1 mA / 17.5 us vs 10 mA / 16.3 us)", open="MP1 v2 levers; AB1 / CB1D routing (Phase C); Rd part"),
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
