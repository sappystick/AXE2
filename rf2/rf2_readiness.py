#!/usr/bin/env python3
"""RF2 prototype-readiness tracker (2026-10-30, owner: 'what needs to be designed next ... designed, wired, routed, fitted to the housing cavities, checked
upstream and downstream ... exactly what needs to be done to be ready to mold, print and prototype'). GENERATED: each deliverable has dependencies and a
GATE (a runner step that must pass, or output files that must exist); its status is computed, not typed. 'Ready to prototype' here means every gate is green
in this repository: MODELED and tool-checked, with no fabricator review and no bench test (rule 3).
Phases: 0 freeze interfaces and close the simulations that can still change boards; 1 schematics + SPICE; 2 boards placed, routed, DRC'd and fitted back
into their cavities; 3 housings and mechanisms for print / mould; 4 harness, winding, potting, BOM, assembly; 5 readiness review and bench plan.
Writes docs/PROTOTYPE_ROADMAP.md and rf2/results/rf2_readiness.json.   usage: python3 rf2/rf2_readiness.py"""
import os, json, glob
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LED = (json.load(open(os.path.join(ROOT, "state", "ledger.json"))) if os.path.exists(os.path.join(ROOT, "state", "ledger.json")) else {}).get("steps", {})
def step_ok(s): return LED.get(s, {}).get("status") == "pass"
def files(*pats): return all(glob.glob(os.path.join(ROOT, p)) for p in pats)
# id, phase, deliverable, depends on, gate (("step", id) | ("files", [globs]) | ("none", why)), what 'done' means
D = [
    # ---- phase 0: interfaces + the simulations that can still move boards
    ("P0.1", 0, "Interface control document: every joint (gland, coil cord, hinge pass-through, grip FFC, cartridge contacts, REF3 termination) with conductors, connector part, pinout, voltage class",
     [], ("json", "rf2/results/rf2_icd.json", "all_parts_verified"), "one table per interface (docs/ICD.md, generated); every connector part verified"),
    ("P0.2", 0, "System netlist extended to every RF2 board and harness wire (TXD, PWR, HB2-M, HB2-G, BMS, REF3T, AB1A/B, CB1D, MP1 v2) with parity", ["P0.1"],
     ("files", ["rf2/results/rf2_netlist_coverage.json"]), "coverage report lists every board above with nets; rf2_parity passes against built boards and harness"),
    ("P0.3", 0, "First gate with the 1.1 m TX pair in the coil cord (rf2_timing, node C + pair, damping at the coil)", [], ("files", ["rf2/results/rf2_timing_cord.json"]), "exact gate shift replaces the +0.56 us first-order estimate"),
    ("P0.4", 0, "EMI canceller with the rectangular REF3 (e_ref 2.5-3.4 nV/rtHz) (rf2_emi)", [], ("files", ["rf2/results/rf2_emi_rect.json"]), "depth with canceller re-computed"),
    ("P0.5", 0, "MP1 v2 protection closed: amplifier input < 10 mA and settling < first gate (levers: Rin2 150-220 ohm, 3.3 V clamp rail, gate timing)", ["P0.3"],
     ("json", "rf2/head/out/rf2_mp1v2_close.json", "closed"), "one option passes every limit in SPICE"),
    ("P0.6", 0, "Missing datasheets on file and logged: memory LCD (LS013B7DH03 class), RS-485 transceiver, FFC / FPC connectors, coil-cord cable, rectangular CF profiles, cam-clamp hardware, cell holder, battery contacts, Rd resistor family (630 V, >= 4.24 W total)",
     [], ("json", "rf2/results/rf2_icd.json", "p06_all_verified"), "each part VERIFIED in DATASHEET_LOG (status list in rf2_icd.json p06_parts)"),
    # ---- phase 1: schematics + SPICE (each lands in rf2_netlist, ratings checked continuous + rule 6)
    ("P1.1", 1, "TXD schematic: C3M0280090J + UCC5350, flat-top PWM current loop (333 uH, 8.06 / 12.74 A), US3M clamp + film cap, bulk bank, shunt + current sense, TMP117 therm -> TXSTAT",
     ["P0.1", "P0.3"], ("files", ["rf2/results/rf2_txd_spice.json"]), "SPICE: current loop, turn-off, clamp, ratings in continuous boost"),
    ("P1.2", 1, "PWR schematic: LMR36520 +5V_AUX, hysteretic regenerative buck 460 V -> VBAT (C3M + UCC5350 + US3M + L), cartridge contacts", ["P0.1", "P1.1"],
     ("files", ["rf2/results/rf2_pwr_spice.json"]), "SPICE: regulation of the clamp at 460 V, efficiency, start-up, fault"),
    ("P1.3", 1, "MP1 v2 schematic (the closed option)", ["P0.5"], ("step", "board:MP1V2"), "netlist entry"),
    ("P1.4", 1, "HB2-M schematic: RP2354A, TLV755P, piezo bridge (2 x AHCT + 680 ohm), RS-485 + TPD4E1B06, I2C to BQ76952, FFC + cord connectors", ["P0.1", "P0.6"], ("step", "board:HB2M"), "netlist entry, logic levels checked"),
    ("P1.5", 1, "HB2-G schematic: 4 x KSC2 TE, 3 x SK9822 + AHCT, screen FPC, FFC", ["P0.1", "P0.6"], ("step", "board:HB2G"), "netlist entry"),
    ("P1.6", 1, "BMS schematic (cartridge): BQ76952 7S, sense resistor, CHG / DSG FETs, fuse, thermistors, TS2 wake from the power button, MT60", ["P0.1", "P0.6"], ("step", "board:BMS"), "BQ76952 settings table; protections"),
    ("P1.7", 1, "REF3 termination board: 3 coil pairs -> 3 STP pairs, ESD, cover fixing", ["P0.1"], ("step", "board:REF3T"), "netlist entry"),
    ("P1.8", 1, "CB1D RF2 schematic update (RS-485 link, TXCMD / TXSTAT to the chassis, TMP117 x2, IMU, magnetometer)", ["P0.1"], ("step", "board:CB1D"), "netlist entry"),
    ("P1.9", 1, "Rd damping network on TXF: 408 ohm from series / parallel 630 V parts, >= 4.24 W at 70 C", ["P0.6"], ("files", ["rf2/results/rf2_rd_network.json"]), "part chosen and logged; TXF re-routed"),
    # ---- phase 2: boards placed, routed, DRC'd, fitted back into their cavities
    ("P2.1", 2, "TXD board in the chassis front cavity: outline from rf2_chassis, HV clearance 1.0 mm, heat-sink + vent alignment", ["P1.1"], ("step", "board:TXD"), "KiCad DRC 0; fit check in chassis"),
    ("P2.2", 2, "PWR board in the chassis spine cavity", ["P1.2"], ("step", "board:PWR"), "KiCad DRC 0; fit check"),
    ("P2.3", 2, "HB2-M board under the grip base", ["P1.4"], ("step", "board:HB2M"), "KiCad DRC 0; fit check"),
    ("P2.4", 2, "HB2-G board in the grip head + FFC length from the grip core route", ["P1.5"], ("step", "board:HB2G"), "KiCad DRC 0; fit check"),
    ("P2.5", 2, "BMS board on the cells in the cartridge", ["P1.6"], ("step", "board:BMS"), "KiCad DRC 0; fit check"),
    ("P2.6", 2, "MP1 v2 board in the head tray", ["P1.3"], ("step", "board:MP1V2"), "DRC 0; copper / eddy check; fit"),
    ("P2.7", 2, "AB1A / AB1B / CB1D routed for RF2 (Phase C) and fitted", ["P1.8"], ("step", "board:CB1D"), "DRC 0; eddy rule; fit"),
    ("P2.8", 2, "Board-into-housing fit for every board: STEP of the routed board placed in the assembly; containment, clearance, connector access", ["P2.1", "P2.2", "P2.3", "P2.4", "P2.5", "P2.6", "P2.7"],
     ("files", ["rf2/chassis_out/rf2_board_fit.json"]), "every board inside its cavity with >= 0.5 mm clearance"),
    # ---- phase 3: housings and mechanisms for print / mould
    ("P3.1", 3, "Chassis shell halves: parting line, bosses + heat-set inserts matching board holes, standoffs, cable channels, vents, gasket groove", ["P2.8"], ("files", ["rf2/chassis_out/print/CHASSIS_*.stl"]), "DFM: wall >= 1.6 mm, overhang / draft, fastener access"),
    ("P3.2", 3, "Grip shell halves + overmould, FFC core, trigger pivot + return spring + switch actuator, screen cassette hinge / detent / latch, dial cam, slide-lock carriage", ["P2.4"],
     ("files", ["rf2/chassis_out/print/GRIP_*.stl"]), "kinematic sweeps clear; switch travel stack-up"),
    ("P3.3", 3, "Main hinge with hollow axis, locking tooth and the slide-lock pawl", ["P3.1"], ("files", ["rf2/chassis_out/print/HINGE_*.stl"]), "180 deg sweep clear; bundle bend / twist in the bore"),
    ("P3.4", 3, "Rectangular profiles (vendor sizes), flat lever clamps, keyed slide pads, end stops", ["P0.6"], ("files", ["rf2/chassis_out/print/CLAMP_*.stl"]), "overlap at full extension, clamp force (ASSUMED until tested)"),
    ("P3.5", 3, "REF3 face-coil formers, solenoid layer, cover", ["P1.7"], ("files", ["rf2/chassis_out/print/REF3_*.stl"]), "winding fits the 42.4 x 36.4 envelope"),
    ("P3.6", 3, "Yoke dual-axis knuckle (pitch friction + roll detents) and head ears for the 28 x 22 profile", [], ("json", "rf2/results/rf2_print.json", "P3.6_ok"), "DFM pass; working pitch -25..+45 free; storage path (pitch, then roll) clear"),
    ("P3.7", 3, "Cuff, wings + springs, rails, slider, strap slots", [], ("json", "rf2/results/rf2_print.json", "P3.7_ok"), "DFM pass; slide sweep clear"),
    ("P3.8", 3, "Battery cartridge shell: cell holder, nickel-strip layout, latch, seal, contacts", ["P2.5"], ("files", ["rf2/chassis_out/print/CART_*.stl"]), "slide path clear (done for the envelope)"),
    ("P3.9", 3, "Head exterior for print: skid clips, bumper, ears; head interior trays already generated", [], ("json", "rf2/results/rf2_print.json", "P3.9_ok"), "DFM pass on skid, bumper, shell and lid"),
    # ---- phase 4: harness, winding, potting, BOM, assembly
    ("P4.1", 4, "Harness drawings with lengths from the 3-D routes (cord, hinge pass-through, grip FFC, head harness)", ["P0.2", "P3.3"], ("files", ["docs/HARNESS.md"]), "every wire end, length, sleeve, voltage class"),
    ("P4.2", 4, "Coil-cord specification (1000 V pair + power + STP pairs, coil OD 17 mm, stretch 4.4:1)", ["P0.1"], ("files", ["docs/COIL_CORD_SPEC.md"]), "vendor quote-able spec"),
    ("P4.3", 4, "Winding specs: rim coil (exists), REF3 face coils + solenoid", ["P3.5"], ("files", ["docs/REF3_WINDING.md"]), "turns, layers, wire, terminations"),
    ("P4.4", 4, "Potting and sealing process (syntactic foam / silicone / 832TC zones; O-rings; vents)", ["P3.1"], ("files", ["docs/POTTING_SEALING.md"]), "materials logged, volumes from the models"),
    ("P4.5", 4, "BOM with sources, EOL flags (Murata piezo) and alternates", ["P1.1", "P1.2", "P1.4", "P1.5", "P1.6"], ("files", ["docs/BOM.csv"]), "every line VERIFIED or marked"),
    ("P4.6", 4, "Assembly sequence (exploded STEP + order + torque / adhesive notes)", ["P3.1", "P3.2", "P4.1"], ("files", ["docs/ASSEMBLY.md"]), "each step reachable in the model"),
    # ---- phase 5: review
    ("P5.1", 5, "All runner steps green, every board with vendor-capability DRC rules, print files with orientation", ["P2.8", "P3.1", "P4.5"], ("step", "readiness-review"), "tool-checked, MODELED"),
    ("P5.2", 5, "Bench plan: bring-up, HV safety, first-gate measurement, EMI + REF3 calibration, ground balance, depth tests", ["P5.1"], ("files", ["docs/BENCH_PLAN.md"]), "test list with pass criteria"),
]
DONE_ALREADY = ["head shells / trays / coil channel (head:BF)", "TXJ, TXF, MP1 v1, LR1, SH1, SB1R QA / QB boards (DRC 0)", "light plate", "chassis v2 envelope + electronics envelopes + fold (chassis)",
                "system budgets / harness / thermal (system)", "audio path (audio)", "display + audio coding v3", "REF3 rect sizing (ref3)", "continuous-boost ratings"]
def json_flag(path, key):
    try: return json.load(open(os.path.join(ROOT, path))).get(key) is True
    except Exception: return False
def status(d):
    kind = d[4][0]
    if kind == "json": return "DONE" if json_flag(d[4][1], d[4][2]) else "TODO"
    if kind == "step": return "DONE" if step_ok(d[4][1]) else "TODO"
    if kind == "files": return "DONE" if files(*d[4][1]) else "TODO"
    return "TODO"
def main():
    rows = [dict(id=d[0], phase=d[1], item=d[2], deps=d[3], gate=d[4], done_means=d[5], status=status(d)) for d in D]
    st = {r["id"]: r["status"] for r in rows}
    for r in rows: r["ready_to_start"] = r["status"] == "TODO" and all(st.get(x) == "DONE" for x in r["deps"])
    # critical path: longest dependency chain (by count) to P5.2
    memo = {}
    def depth(i):
        if i in memo: return memo[i]
        r = next(x for x in rows if x["id"] == i); memo[i] = 1 + max([depth(x) for x in r["deps"]] or [0]); return memo[i]
    def chain(i):
        r = next(x for x in rows if x["id"] == i)
        return ([i] if not r["deps"] else chain(max(r["deps"], key=depth)) + [i])
    crit = chain("P5.2")
    json.dump(dict(rows=rows, critical_path=crit, done_already=DONE_ALREADY), open(os.path.join(ROOT, "rf2", "results", "rf2_readiness.json"), "w"), indent=1)
    names = {0: "Phase 0: freeze interfaces, close the simulations that can still change boards", 1: "Phase 1: schematics + SPICE", 2: "Phase 2: boards placed, routed, DRC'd, fitted into their cavities",
             3: "Phase 3: housings + mechanisms for print / mould", 4: "Phase 4: harness, winding, potting, BOM, assembly", 5: "Phase 5: readiness review + bench plan"}
    L = ["# AXE2 prototype roadmap (generated by rf2/rf2_readiness.py)", "",
         "'Ready to prototype' = every gate below green in this repository. That is MODELED and tool-checked: no fabricator review, no bench test (rule 3).", "",
         f"**Done: {sum(r['status'] == 'DONE' for r in rows)} of {len(rows)}. Ready to start now: {', '.join(r['id'] for r in rows if r['ready_to_start'])}.**", "",
         "**Critical path:** " + " -> ".join(crit), "", "Already in place: " + "; ".join(DONE_ALREADY) + ".", ""]
    for ph in range(6):
        L += [f"## {names[ph]}", "", "| ID | Deliverable | Needs | Gate | Done means | Status |", "|---|---|---|---|---|---|"]
        for r in rows:
            if r["phase"] != ph: continue
            g = r["gate"]; gs = f"step `{g[1]}`" if g[0] == "step" else (f"`{g[1]}` {g[2]} = true" if g[0] == "json" else "files " + ", ".join(f"`{x}`" for x in g[1]))
            L.append(f"| {r['id']} | {r['item']} | {', '.join(r['deps']) or '-'} | {gs} | {r['done_means']} | {'**' + r['status'] + '**' + (' (start now)' if r['ready_to_start'] else '')} |")
        L.append("")
    open(os.path.join(ROOT, "docs", "PROTOTYPE_ROADMAP.md"), "w").write("\n".join(L) + "\n")
    print(f"{sum(r['status'] == 'DONE' for r in rows)}/{len(rows)} done; start now: {[r['id'] for r in rows if r['ready_to_start']]}"); print("critical path:", " -> ".join(crit))
    return rows
if __name__ == "__main__":
    main()
