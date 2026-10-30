#!/usr/bin/env python3
"""RF2 system netlist (Phase A1, 2026-10-29): the single source of truth for the RF2 head's new boards, their parts, pins, nets, placements, and the harness
conductors between board pads. rf2_boards.py builds the KiCad boards from it; rf2_parity.py checks every board and every conductor against it; rf2_render.py
places the part bodies from it. MODELED; part data are copied from the repo's libraries (provenance in each entry) or marked ASSUMED.

Boards defined here: MP1 (mono preamp v1), TXJ (coil-lead terminal board), LR1 (LED ring). SH1 is built by rf2_shield_pcb.py; QA / QB are the baseline SB1R
boards (outline variant by rf2_sb1r_variant.py); AB1A / AB1B / CB1D are RF1 boards whose RF2 rework is Phase C: their harness pads are declared here as
PENDING interfaces and are listed, not checked, until then.
usage: python3 rf2/head/rf2_netlist.py   (prints a summary and runs the netlist's own consistency check)"""
import math, json, os
# ------------------------------------------------------------------------------------------------ footprint library (pads: number, x, y, w, h, shape[, drill]; body w, l, h)
def two(dx, w, h): return [("1", -dx, 0, w, h, "roundrect"), ("2", dx, 0, w, h, "roundrect")]
def wire(drill, pad): return [("1", 0.0, 0.0, pad, pad, "circle", drill)]
LIB = {
    "R2512": dict(pads=two(3.1, 1.6, 3.4), body=(6.3, 3.2, 0.7), src="src/pcb/pw_design.py LIB R2512 (Vishay CRCW2512: Umax 500 V, 1 W; DATASHEET_LOG)"),
    "R0805": dict(pads=two(0.95, 1.0, 1.45), body=(2.0, 1.25, 0.6), src="afe_design C0805 pad pattern; body ASSUMED"),
    "C0805": dict(pads=two(0.95, 1.0, 1.45), body=(2.0, 1.25, 1.0), src="experiments/RF1_rigidflex afe_design LIB C0805"),
    "C0402": dict(pads=two(0.51, 0.54, 0.64), body=(1.0, 0.5, 0.5), src="afe_design LIB C0402"),
    "BAV199": dict(pads=[("1", -0.9375, -0.95, 1.475, 0.6, "roundrect"), ("2", -0.9375, 0.95, 1.475, 0.6, "roundrect"), ("3", 0.9375, 0, 1.475, 0.6, "roundrect")],
                   body=(2.9, 1.3, 1.1), src="afe_design LIB BAV199; pinning 1 A1, 2 K2, 3 K1+A2 (DATASHEET_LOG U-DS-BAV199)"),
    "OPA2211": dict(pads=[("1", -2.7, -1.905, 1.55, 0.6, "roundrect"), ("2", -2.7, -0.635, 1.55, 0.6, "roundrect"), ("3", -2.7, 0.635, 1.55, 0.6, "roundrect"), ("4", -2.7, 1.905, 1.55, 0.6, "roundrect"),
                         ("5", 2.7, 1.905, 1.55, 0.6, "roundrect"), ("6", 2.7, 0.635, 1.55, 0.6, "roundrect"), ("7", 2.7, -0.635, 1.55, 0.6, "roundrect"), ("8", 2.7, -1.905, 1.55, 0.6, "roundrect")],
                    body=(4.9, 3.9, 1.6), src="afe_design LIB OPA2211 SOIC-8 (TI SBOS377L); pins 1 OUT_A 2 -IN_A 3 +IN_A 4 V- 5 +IN_B 6 -IN_B 7 OUT_B 8 V+"),
    "SK9822EC20": dict(pads=[("1", -0.68, -0.86, 0.76, 0.46, "rect"), ("2", -0.68, 0.0, 0.76, 0.46, "rect"), ("3", -0.68, 0.86, 0.76, 0.46, "rect"),
                             ("4", 0.68, 0.86, 0.76, 0.46, "rect"), ("5", 0.68, 0.0, 0.76, 0.46, "rect"), ("6", 0.68, -0.86, 0.76, 0.46, "rect")],
                       body=(2.0, 2.0, 0.65), src="src/pcb/pw_design.py LIB SK9822EC20 (OPSCO SK9822-EC20-000 Rev. A/0): 1 SDO 2 GND 3 SDI 4 CKI 5 VDD 6 CKO"),
    "WIRE_LITZ": dict(pads=wire(1.5, 3.0), body=(3.0, 3.0, 0.05), src="wire-hole pad for the 1.2 mm litz end (repo rule: no plug-on joints); drill ASSUMED"),
    "WIRE_AWG18": dict(pads=wire(1.4, 2.8), body=(2.8, 2.8, 0.05), src="wire-hole pad for the shaft HV pair (AWG18 630 V wire, ASSUMED)"),
    "WIRE_SENSE": dict(pads=wire(0.9, 1.9), body=(1.9, 1.9, 0.05), src="wire-hole pad for a 0.5 mm sense wire"),
    "FLEX_LAND": dict(pads=[("1", 0.0, 0.0, 1.2, 0.5, "rect")], body=(1.2, 0.5, 0.05), src="hinge-flap solder land 1.2 x 0.5 mm (LR1 flap, hot-bar)"),
    "FLEX_PAD": dict(pads=[("1", 0.0, 0.0, 1.0, 2.0, "rect")], body=(1.0, 2.0, 0.05), src="flex-jumper solder land 1.0 x 2.0 mm (hot-bar / hand solder)"),
}
# ------------------------------------------------------------------------------------------------ boards
BOARDS = {}
def board(name, **kw): BOARDS[name] = dict(parts=[], **kw); return BOARDS[name]
def part(b, ref, typ, value, x, y, rot=0.0, side="top", note=""): BOARDS[b]["parts"].append(dict(ref=ref, type=typ, value=value, x=x, y=y, rot=rot, side=side, pins={}, note=note))
def net(b, name, *pins):
    for ref, pin in pins:
        p = next(q for q in BOARDS[b]["parts"] if q["ref"] == ref); assert pin not in p["pins"], (b, ref, pin); p["pins"][pin] = name
# ---- MP1: mono preamp v1 (board 30 x 20 mm, 2 layers, 1.6 mm). Coil terminals -> 3 x 470 ohm CRCW2512 per leg (each <= 500 V; peak clamp current
#      460 V / 1.41 kohm = 0.33 A < BAV199 IFRM 0.5 A) -> BAV199 clamps to AGND / +5VA -> OPA2211 A difference amplifier (gain 10, ASSUMED: Phase E tunes it)
#      referenced to VBIAS (OPA2211 B buffers a 10k / 10k divider) -> 100 ohm isolation -> flex lands. HV nets: COIL_A, COIL_B, HA1, HA2, HB1, HB2.
board("MP1", w=26.0, h=36.0, layers=2, thickness=1.6, kind="rect", hv_nets=["COIL_A", "COIL_B", "HA1", "HA2", "HB1", "HB2"],
      head=dict(c=(-75.0, 3.0), z_bottom=5.6), note="mono preamp v1: resistor-protected input; series 1.41 kohm adds about 4.8 nV/rtHz (depth penalty, see HANDOFF)")
part("MP1", "J1", "WIRE_SENSE", "COIL_A", -11.0, 14.0); part("MP1", "J2", "WIRE_SENSE", "COIL_B", -11.0, -14.0)
for i, (y, rot) in enumerate(((14.0, 0), (9.4, 180), (4.8, 0))):        # snake: RA1 L->R, RA2 R->L, RA3 L->R (each link is a short jump at one end)
    part("MP1", f"RA{i+1}", "R2512", "470R CRCW2512", -4.2, y, rot); part("MP1", f"RB{i+1}", "R2512", "470R CRCW2512", -4.2, -y, rot)
part("MP1", "D1", "BAV199", "BAV199", 2.4, 4.4); part("MP1", "D2", "BAV199", "BAV199", 2.4, -4.4)
part("MP1", "U1", "OPA2211", "OPA2211AIDR", 7.0, 0.0)
for ref, x, y, rot in (("R4", 1.4, 1.3, 0), ("R6", 1.4, -1.3, 0), ("R5", 11.0, 3.5, 0), ("R7", 11.0, -3.5, 0), ("R8", 7.0, 7.0, 0), ("R9", 7.0, 9.8, 0), ("R10", 7.0, -15.0, 0)):
    part("MP1", ref, "R0805", {"R4": "1k", "R5": "24k", "R6": "1k", "R7": "24k", "R8": "10k", "R9": "10k", "R10": "100R"}[ref], x, y, rot)
part("MP1", "C1", "C0805", "100n", 7.0, 12.6); part("MP1", "C2", "C0805", "10u", 7.0, -6.8); part("MP1", "C3", "C0805", "100n", 7.0, -9.6)
part("MP1", "J3", "FLEX_PAD", "MONO_OUT", 11.8, -15.5); part("MP1", "J4", "FLEX_PAD", "+5VA", 11.8, -12.5); part("MP1", "J5", "FLEX_PAD", "AGND", 11.8, -9.5)
net("MP1", "COIL_A", ("J1", "1"), ("RA1", "1")); net("MP1", "HA1", ("RA1", "2"), ("RA2", "1")); net("MP1", "HA2", ("RA2", "2"), ("RA3", "1"))
net("MP1", "INP", ("RA3", "2"), ("D1", "3"), ("R4", "1"))
net("MP1", "COIL_B", ("J2", "1"), ("RB1", "1")); net("MP1", "HB1", ("RB1", "2"), ("RB2", "1")); net("MP1", "HB2", ("RB2", "2"), ("RB3", "1"))
net("MP1", "INN", ("RB3", "2"), ("D2", "3"), ("R6", "1"))
net("MP1", "AGND", ("D1", "1"), ("D2", "1"), ("U1", "4"), ("R9", "2"), ("C1", "2"), ("C2", "2"), ("J5", "1"), ("C3", "2"))
net("MP1", "+5VA", ("D1", "2"), ("D2", "2"), ("U1", "8"), ("R8", "1"), ("C2", "1"), ("J4", "1"), ("C3", "1"))
net("MP1", "PLUS_A", ("R4", "2"), ("U1", "3"), ("R5", "1")); net("MP1", "VBIAS", ("R5", "2"), ("U1", "6"), ("U1", "7"))
net("MP1", "MINUS_A", ("R6", "2"), ("U1", "2"), ("R7", "1")); net("MP1", "OUT_A", ("R7", "2"), ("U1", "1"), ("R10", "1"))
net("MP1", "VDIV", ("R8", "2"), ("R9", "1"), ("U1", "5"), ("C1", "1")); net("MP1", "MONO_OUT", ("R10", "2"), ("J3", "1"))
# ---- TXJ: coil-lead terminal board (12 x 16 mm, 2 layers, 2 oz). Column A and column B, 1.0 mm+ HV clearance between them, 2.5 mm tracks (8 A pulses).
board("TXJ", w=12.0, h=16.0, layers=2, thickness=1.6, kind="rect", hv_nets=["TX_A", "TX_B"], wide={"TX_A": 2.5, "TX_B": 2.5},
      head=dict(c=(-99.5, 3.4), z_bottom=5.6), note="wire-hole pads only (repo rule: no plug-on joints inside the head)")
for col, nm, x in (("A", "TX_A", -3.2), ("B", "TX_B", 3.2)):
    part("TXJ", f"JC{col}", "WIRE_LITZ", f"coil {col}", x, 5.0); part("TXJ", f"JK{col}", "WIRE_AWG18", f"cable {col}", x, -0.6); part("TXJ", f"JS{col}", "WIRE_SENSE", f"sense {col}", x, -5.0)          # -5.0: the 2.5 mm track's end cap keeps 1.0 mm to the 0.5 mm edge keep-out
    net("TXJ", nm, (f"JC{col}", "1"), (f"JK{col}", "1"), (f"JS{col}", "1"))
# ---- TXF: TXJ's function as a RADIAL FIN (option B clean sheet, variant BF; Stage 4b). The coil is axisymmetric, so a board standing in a plane through the axis
#      sees no azimuthal field: its loops get no EMF and its copper no eddy current (rf2_layout.py). The fin slot is 8.4 mm tall (z 4.0-12.4) and 1.0 mm thick, so
#      TXJ's two columns become two groups end to end along the fin's radial axis (x outward, fin centre at r 86, so the rim end is r 102): each group is
#      litz / cable / sense in a line on a 2.5 mm track at mid-height (8 A pulses). The groups are 3.5 mm apart (rule 6 asks >= 1.0 mm). Each group has its sense
#      pad at the gap for B and at the far end for A; the coil (litz) pad is at x = -3.0 for A and +13.5 for B (the lead pair reaches the fin from the rim at 178 deg).
board("TXF", w=32.0, h=8.4, layers=2, thickness=1.0, kind="rect", hv_nets=["TX_A", "TX_B"], wide={"TX_A": 2.5, "TX_B": 2.5},
      head=dict(c=(0.0, -1000.0), z_bottom=4.0, fin=dict(deg=186.0, r_center=86.0, z0=4.0)),
      bus=[("TX_A", [(-3.0, 0.0), (-13.5, 0.0)], 2.5), ("TX_B", [(3.0, 0.0), (13.5, 0.0)], 2.5)],
      note="fin board, wire-hole pads only (repo rule: no plug-on joints inside the head); replaces TXJ in variant BF")
for col, nm, xs in (("A", "TX_A", (-3.0, -8.0, -13.5)), ("B", "TX_B", (13.5, 8.0, 3.0))):
    part("TXF", f"JC{col}", "WIRE_LITZ", f"coil {col}", xs[0], 0.0); part("TXF", f"JK{col}", "WIRE_AWG18", f"cable {col}", xs[1], 0.0); part("TXF", f"JS{col}", "WIRE_SENSE", f"sense {col}", xs[2], 0.0)
    net("TXF", nm, (f"JC{col}", "1"), (f"JK{col}", "1"), (f"JS{col}", "1"))
# ---- LR1: dense LED display flex (owner 2026-10-30: rings from the rim to the centre + a centre cluster, about 540 LEDs on an 8 mm grid; built: see
#      rf2_ledgrid.py, the single source of its layout, nets and copper). 2-layer polyimide flex (0.2 mm with coverlay) on a 0.2 mm FR4 stiffener, vendor
#      rules 0.10 / 0.10 mm; SK9822-EC20 + 100 nF 0402 per LED; 4 serial chains; open B.Cu buses and spokes (rule 5); hinge flap above CB1D (12 lands);
#      notch around the lid's gland boss; 6 rim holes for the lid bosses. Routed by rf2_ledgrid.copper() (deterministic template, no autorouter).
import rf2_ledgrid as LG
board("LR1", kind="poly", r_out=LG.R_OUT, layers=2, thickness=0.4, hv_nets=[], holes=LG.HOLES, rules="0.1,0.1,0.45,0.2", floor=0.1,
      tech="flex 2L polyimide 0.2 mm + FR4 stiffener 0.2 mm (vendor 0.10 / 0.10 mm; via 0.45 / 0.2 ASSUMED)",
      head=dict(c=(0.0, 0.0), z_bottom=22.85), note="LEDs under a clear PETG lid (diffuser); dark during receive windows and when silent (power-gated)")
BOARDS["LR1"]["template"] = "led_grid"
_LG = LG.layout(); _PINS, _LANDS = LG.nets_and_lands()
for e in _LG["leds"]:
    part("LR1", e["ref"], "SK9822EC20", "SK9822-EC20", e["x"], e["y"], e["rot"]); part("LR1", e["cap"], "C0402", "100n", e["cx"], e["cy"], e["crot"])
for ref, nm, xl, yl in _LANDS:
    x, y = LG.to_g(xl, yl); part("LR1", ref, "FLEX_LAND", nm, x, y, LG.HEEL)
_byn = {}
for (ref, pin), nm in _PINS.items(): _byn.setdefault(nm, []).append((ref, pin))
for ref, nm, _, _ in _LANDS: _byn.setdefault(nm, []).append((ref, "1"))
for nm, pins in _byn.items(): net("LR1", nm, *pins)
# ------------------------------------------------------------------------------------------------ harness: conductors between board pads (board.ref.pin), net names must agree
HARNESS = [
    ("C01a", "COIL.A", "TXJ.JCA.1", "TX_A", "litz end"), ("C01b", "COIL.B", "TXJ.JCB.1", "TX_B", "litz end"),
    ("C02a", "TXJ.JKA.1", "NECK.TX_A", "TX_A", "shaft HV pair"), ("C02b", "TXJ.JKB.1", "NECK.TX_B", "TX_B", "shaft HV pair"),
    ("C03a", "TXJ.JSA.1", "MP1.J1.1", "TX_A|COIL_A", "sense wire"), ("C03b", "TXJ.JSB.1", "MP1.J2.1", "TX_B|COIL_B", "sense wire"),
    ("C04a", "MP1.J3.1", "AB1B.MONO_IN", "MONO_OUT|MONO_IN", "flex jumper"), ("C04b", "MP1.J4.1", "AB1B.+5VA", "+5VA", "flex jumper"), ("C04c", "MP1.J5.1", "AB1B.AGND", "AGND", "flex jumper"),
    *[(f"C10{chr(97 + k)}", f"CB1D.LED{k + 1}", f"LR1.{ref}.1", nm, "hinge flap") for k, (ref, nm, _, _) in enumerate(LG.nets_and_lands()[1])],
    ("C07", "SH1.H1.1", "AB1A.AGND", "SHIELD|AGND", "0.5 mm wire, single-point shield ground"),
]
PENDING = {"AB1A", "AB1B", "CB1D", "NECK", "COIL"}                       # boards not yet in this netlist (Phase C) or not boards (COIL, NECK)
def pad_net(spec):
    """'BOARD.REF.PIN' -> net name on that board (None if the board is PENDING / external)"""
    b, ref, pin = (spec.split(".") + [None, None])[:3]
    if b not in BOARDS: return None
    p = next((q for q in BOARDS[b]["parts"] if q["ref"] == ref), None)
    return None if p is None else p["pins"].get(pin, "UNCONNECTED")
def check():
    errs = []
    for b, B in BOARDS.items():
        refs = [p["ref"] for p in B["parts"]]
        if len(refs) != len(set(refs)): errs.append(f"{b}: duplicate refs")
        for p in B["parts"]:
            pads = {q[0] for q in LIB[p["type"]]["pads"]}
            if set(p["pins"]) - pads: errs.append(f"{b}.{p['ref']}: pins not in footprint {set(p['pins']) - pads}")
            if pads - set(p["pins"]): errs.append(f"{b}.{p['ref']}: unconnected pads {sorted(pads - set(p['pins']))}")
        nets = {}
        for p in B["parts"]:
            for pin, n in p["pins"].items(): nets.setdefault(n, []).append(f"{p['ref']}.{pin}")
        chain_ends = {f"C{c}_{k}{len(seq)}" for c, seq in enumerate(LG.layout()["chains"], 1) for k in ("D", "K")} if b == "LR1" else set()
        single = [n for n, v in nets.items() if len(v) < 2 and n not in chain_ends]          # the last LED's SDO / CKO of each chain are open by design
        if single: errs.append(f"{b}: single-pin nets {single}")
    checked, pending = [], []
    for cid, a, z, nm, _ in HARNESS:
        na, nz = pad_net(a), pad_net(z); names = nm.split("|")
        if na is None or nz is None: pending.append(cid); continue
        if na not in names or nz not in names: errs.append(f"{cid}: {a} is {na}, {z} is {nz}, expected {nm}")
        checked.append(cid)
    for cid, a, z, nm, _ in HARNESS:                                   # the end on a defined board must still match even if the other end is pending
        for e in (a, z):
            n = pad_net(e)
            if n is not None and n not in nm.split("|"): errs.append(f"{cid}: {e} is {n}, expected {nm}")
    return dict(ok=not errs, errors=errs, harness_checked=checked, harness_pending_phase_c=pending,
                parts={b: len(B["parts"]) for b, B in BOARDS.items()}, nets={b: len({n for p in B["parts"] for n in p["pins"].values()}) for b, B in BOARDS.items()})
if __name__ == "__main__":
    print(json.dumps(check(), indent=1))
