#!/usr/bin/env python3
"""RF2 head v1 (2026-10-29): the clean-sheet 1-inch head as a parametric layout. One SPEC (every dimension, from the RF2 studies) and every printed part,
seat and envelope built with manifold3d (exact booleans, closed meshes). MODELED design; nothing ordered or built. The baseline is untouched.

Frame: mm; z up from the underside of the skid; azimuth CCW from +x; heel (shaft side) at 178 deg (repo convention).
Sectors: HV 156-198 deg (coil leads, TXJ, mono preamp MP1), ANALOG 89-156 deg (AB1A, AB1B: next to the QA / QB lead pads at 83-142 deg and to MP1's
output), DIGITAL the rest (CB1D tower at the centre). The shaft cable comes DOWN through the lid at the heel (r 92), never across the coil.
Seats: 3 PETG pins (Ø3.2, r 28 at 22.5 / 157.5 / 247.5 deg) through the board stack (the SB1R holes, Ø3.4); AB1 cradles (ledge + wall + snap lip, hinge
slot facing the centre); a CB1D tower (ledge, wall, snap lip, hinge slots); MP1 / TXJ trays (ledge + rim, HV slot and LV slot on opposite sides); the
LED display flex hangs on 6 lid bosses at r 110.8 (pins Ø1.8 through Ø2.0 board holes); clear PETG lid over the display (no windows); a cable gland boss in the lid at the heel.
Envelopes are board + parts-below + parts-above with edge keep-outs where ledges and lips grip (1.2 mm below, 0.4 mm above; component rule for layout).
Outputs (out/): RF2_<PART>.stl, rf2_head_spec.json.  usage: python3 rf2/head/rf2_head.py"""
import os, sys, json, math, struct
import numpy as np
import manifold3d as m3
VARIANT = os.environ.get("RF2_VARIANT") or next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--variant=")), "A")
# A = the 25.4 mm SPEC; B = 15.65 mm, option A's board islands lowered to one tier; BF = 15.65 mm clean-sheet: radial fin boards (rf2_layout.py)
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out" if VARIANT == "A" else "out_" + VARIANT); os.makedirs(OUT, exist_ok=True)
SEG = 256; HEEL = 178.0
def pol(r, deg): return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))
SPEC = dict(
    envelope=dict(R=116.5, H=25.4, note="owner: existing diameter, 1 inch height"),
    shell=dict(skid_t=1.2, wall_r=(114.5, 116.5), wall_z=(0.0, 23.9), lid_z=(23.9, 25.4), material="PETG (printed), no metal (rule 5)"),
    boards=dict(
        SH1=dict(z=(1.2, 1.6), r=114.0, what="split-ring electrostatic shield (rf2_shield_pcb.py): open rings + one radial spine, single-point ground"),
        QA=dict(z=(1.6, 2.4), r=114.0, what="SB1R-QA quadrupole receive board, copper unchanged; outline variant without the r 116 tab (does not fit a 2 mm wall)"),
        QB=dict(z=(2.4, 3.2), r=114.0, what="SB1R-QB (QA turned 45 deg), copper unchanged; same outline variant")),
    stack_pins=dict(r=28.0, deg=(157.5, 247.5), holes_deg=(22.5, 157.5, 247.5), d=3.2, hole_d=3.4, z=(1.2, 3.8),
                    what="2 PETG pins from the skid through SH1 / QA / QB (the SB1R NPTH holes); the 22.5 deg hole carries the shield's ground wire up (SH1 plated pad there)"),
    coil=dict(turns=26, columns_r=(113.4, 111.8, 110.2), litz_od=1.2, pitch=1.6, floor_z=(3.2, 3.8), row0_z=4.4, rows=9,
              L_uH=333, I_A=8.06, energy_mJ=10.8, what="rim mono: transmits and receives (rf2_receiver_combo / rf2_timing); critically damped"),
    channel=dict(inner_wall_r=(108.4, 109.4), z=(3.2, 18.8), lead_exit_deg=HEEL, lead_slot_w=6.0),
    bay=dict(r_max=108.0, z=(3.8, 21.6)),
    walls=dict(t=1.2, z=(3.8, 20.8), r=(42.0, 108.0), deg=(89.0, 156.0, 198.0),
               note="89: analog | digital, PETG loaded with carbonyl iron; 156: analog | HV; 198: HV | digital; 156 has an LV slot for MP1's output flex"),
    sectors=dict(hv=(156.0, 198.0), analog=(89.0, 156.0)),
    boards_inner=dict(   # board centre, size, board z, parts below / above (edge keep-outs 1.2 below, 0.4 above)
        AB1A=dict(kind="disc", c=pol(82.0, 106.0), r=20.0, z=(5.6, 7.2), below=1.0, above=3.0, hinge_deg=106.0 + 180.0,
                  what="RF1 AB1A analog section (D40, 6-layer rigid with the 2-layer flex core), routed in RF1: 0 open, KiCad DRC clean; mounted COMPONENT SIDE UP (its parts are on one side, 2.15 mm tall, measured on the RF1 mesh: they would hit the bay floor facing down)"),
        AB1B=dict(kind="disc", c=pol(82.0, 137.0), r=20.0, z=(5.6, 7.2), below=1.0, above=3.0, hinge_deg=137.0 + 180.0, what="RF1 AB1B analog section, routed in RF1"),
        CB1D=dict(kind="disc", c=(0.0, 0.0), r=39.0, z=(13.5, 15.1), below=2.0, above=4.4, what="RF1 CB1D section: RP2354A, LMR36015 buck, TLV755P (placed in RF1; route next)"),
        MP1=dict(kind="box", c=(-76.0, 14.0), size=(26.0, 18.0), z=(5.6, 7.2), below=1.0, above=3.4, what="NEW mono preamp: HV-tolerant input (630 V parts, >= 1.0 mm), output to AB1A"),
        TXJ=dict(kind="box", c=(-99.5, 3.4), size=(9.0, 15.0), z=(5.6, 7.2), below=1.0, above=4.8, what="NEW coil-lead terminal board: wire-hole pads (Wire_pads) for the coil leads and the shaft TX pair"),
        LED=dict(kind="flex", z=(22.85, 23.25), below=0.0, above=0.65,
                 what="LED display: FLEX section of the rigid-flex panel (0.2 mm polyimide on a 0.2 mm FR4 stiffener), 522 SK9822-EC20 in 13 rings from r 104 to the centre (rf2_ledgrid.py), clocked, dark during receive windows and power-gated when silent")),
    led_bosses=dict(n=6, r=110.8, deg0=30.0, boss_d=4.0, pin_d=1.8, hole_d=2.0),
    lid_light=dict(material="clear / natural PETG, printed solid (diffuser; transmission ASSUMED)", note="no holes over the LEDs: 522 windows would weaken the lid and the seal"),
    gland=dict(c=pol(92.0, HEEL), d=8.0, boss_d=12.0, boss_z=(21.6, 23.9), what="shaft cable enters DOWN through the lid at the heel into the HV sector"),
    potting=dict(analog="low-permittivity gel", hv="high-dielectric-strength epoxy", digital="syntactic silicone", display="conformal coat only", coil="epoxy in the channel"),
    ref_coil=dict(place="on the shaft, 0.6 m from the head", former="3 orthogonal windings, 100 mm, on a PETG frame", turns_per_axis=390, wire="0.20 mm enamelled copper",
                  requirement="area-turns = 3 x the mono per axis (rf2_emi.py)", noise="2.0 nV/rtHz, depth cost 1.4 %, copper 104 g (rf2_ref3.py; the earlier 620 x 0.15 mm on 80 mm gave 2.32 nV/rtHz and 1.8 %)"),
)
# boards defined in the system netlist (rf2_netlist.py) take their size and place from it: one source of truth
import rf2_netlist as _NL
for _k in ("MP1", "TXJ"):
    _b = _NL.BOARDS[_k]; SPEC["boards_inner"][_k]["c"] = tuple(_b["head"]["c"]); SPEC["boards_inner"][_k]["size"] = (_b["w"], _b["h"])
def apply_option_b(S):
    """option B (owner 2026-10-30; rf2_thin, rf2_zones, HANDOFF sections 17-24): CB1D lowered to the AB1 / MP1 / TXJ tier, the coil re-shaped to 5 rows
    x 6 columns under the display, head 15.65 mm. Materials chosen by the zone and potting studies."""
    zd = 13.1; DFLEX = 0.20; lid0 = round(zd + DFLEX + 0.65, 2)                           # owner 2026-10-30: ultra-thin display flex 0.20 mm (was 0.4; PICA), LEDs 0.65
    LID_T = 2.4                                                                           # light plate 2.4 mm (was 1.5): a 0.9 mm straight land under each cone removes the feather edge
    S["envelope"].update(H=round(lid0 + LID_T, 2), note="option B: single board tier; light plate 2.4 mm (2026-10-30, DFM)")   # at each well's bottom rim (rf2_print DFM, HANDOFF 40)
    S["shell"].update(wall_z=(0.0, lid0), lid_z=(lid0, round(lid0 + LID_T, 2)))
    S["coil"].update(columns_r=tuple(round(113.4 - 1.77 * k, 2) for k in range(5)), rows=6, row0_z=4.49, litz_od=1.37, pitch=1.77, row_pitch=1.44,   # owner 2026-10-30: Rubadue TXXL66/38F-2 triple FEP 1000 V; 5 columns (comb pitch 1.77) x 6 rows (stacked, 1.44) (HANDOFF 45)
                     what="rim mono, 6 rows x 5 columns (option B; was 5 x 6 at 1.6 mm), wound column by column down-and-up (owner's progressive order; about 195 V max between neighbours, 1000 V litz)")
    S["channel"].update(inner_wall_r=(103.8, 104.6), z=(3.2, 12.6))
    S["bay"].update(r_max=103.6, z=(3.8, zd))
    S["walls"].update(z=(3.8, 12.6), r=(42.0, 103.6))
    S["boards_inner"]["CB1D"].update(z=(6.6, 8.2), what=S["boards_inner"]["CB1D"]["what"] + "; option B: on the AB1 tier, parts below 2.0 / above 4.4")
    S["boards_inner"]["LED"].update(z=(zd, zd + DFLEX))
    S["boards_inner"]["MP1"].update(c=(-72.0, 3.0), what=S["boards_inner"]["MP1"]["what"] + "; option B: 3 mm inward (the 6-column channel wall is at r 103.8)")
    S["boards_inner"]["TXJ"].update(c=(-94.5, 0.0), what=S["boards_inner"]["TXJ"]["what"] + "; option B: at (-94.5, 0), between MP1 and the channel wall (r 103.8)")
    S["netlist_variant_note"] = "rf2_netlist.BOARDS MP1 / TXJ 'head' positions are option A's; the option-B board builds take MP1 (-72, 3) and TXJ (-94.5, 0) (stage 4)"
    S["gland"].update(boss_z=(12.6, lid0))
    S["materials"] = dict(
        coil_wire="Rubadue TXXL66/38F-2 triple-insulated FEP litz (owner 2026-10-30; DATASHEET_LOG RF2-DS-WIRE): 66 x AWG38, 1056 CM, finished OD 1.372 mm nominal, "
                  "FEP 155 C / 1000 V (catalog rating), 50-100 kHz; 0.601 ohm over 18.3 m (rf2_wire_options). Breakdown and exact OD: request the vendor specification sheet",
        coil_wire_od_mm=1.37, litz_g_per_m=6.9,
        sleeves="FEP on every wire in the head that leaves the coil's 1.37 mm litz: FEP-jacketed hookup wire for the shaft HV pair and the sense wires, FEP tubing over the litz lead pair "
                "to the TXJ board (same eps 2.1 and no creep; PTFE rejected: it creeps). Voltage rating of the finished wire is UNVERIFIED: must be >= 630 V (rule 6)",
        coating="Parylene (SCS ParyFree, falling back to Parylene C) on the analog and near-coil fins: moisture and leakage barrier with no magnetic or eddy effect",
        coil_potting="syntactic foam (K1 glass bubbles in silicone, eps about 1.75-1.9): coil capacitance 101 pF with FEP litz (rf2_qualify D)",
        status="MODELED / sourced from supplier notes; not bench-tested")
    S["lid_light"] = dict(type="light_plate", d_bottom=2.9, d_top=6.0, land=0.9, web_min_mm=0.8,
                          material="opaque matt black PETG plate, one conical well over each of the 522 LEDs (rf2_lightplate.py: exit efficiency 0.97 against 0.41 for a straight bore, liner reflectance ASSUMED 0.90); "
                                   "wall liner = white diffuse non-metal paint (TiO2); a metallised liner is banned (rule 5: metal near the coil); well filled flush with clear resin (seals the plate)",
                          note="replaces the clear lid of option A")
    S["coil_combs"] = dict(n=12, deg0=15.0, t=0.8, slot=1.47, what="printed winding combs (resin print): radial plates with one slot per groove column (1.47 mm slots for the 1.37 mm litz, 0.30 mm teeth), the turns laid from the top, column by column")
    S["shield_coat"] = dict(r=(114.45, 114.5), z=(1.2, lid0), slit_deg=HEEL + 6.0, slit_w=2.0, material="MG 841AR nickel coating, 25 um (1.6 ohm/sq): echo tau 1 ns (rf2_zones)",
                            what="electrostatic screen on the shell's inner face, joined to SH1 at the stack-pin ground; one 2 mm slit")
    S["potting"] = dict(coil="syntactic foam (resin + glass bubbles, eps about 1.8 UNVERIFIED): lowest winding capacitance (rf2_zones: gate 15.96 us)",
                        analog="low-permittivity silicone gel (stress-free, reworkable)", hv="MG 832TC epoxy (48 kV breakdown at 3.2 mm; kept >= 3 mm from the winding: eps 3.7, DF 0.1)",
                        digital="syntactic silicone", display="conformal coat only")
    S["zone_rules"] = ["no solid copper planes; hatched 1.0 / 0.25 mm with every border slit (rf2_zones: closed border up to 3300 x noise)",
                       "no aluminium electrolytic or other metal-can parts in the head: MLCC only (can echo 2e4-7.5e4 x noise)",
                       "nothing switches in the receive window; analog / TXJ loops < 0.1 cm2, edge-on where the field is vertical",
                       "IXTY08N100D2 tab edge-on to the field or a tab-less package (tab echo 2700 x noise, tau 19.8 us)"]
FIN_SEP = 3.0                                                                            # HV fins end this far from the LV hub board (rule 6 envelope margin)
def apply_option_bf(S):
    """option B, clean sheet (owner 2026-10-30: design the housing around the new boards): every electronics board is a RADIAL FIN standing in a plane
    through the head axis. The rim coil is axisymmetric, so its field has no azimuthal part: a fin's loops see no EMF and its copper no eddy current, and
    its own currents do not couple into the mono (rf2_layout.py: 1 deg of tilt leaves 0.096 mT against 5.5 mT on a flat board, solid-plane echo 3e-4 x).
    Fins are held in floor guide rails and hub slots (tilt < 1 deg). HV fins sit 8 deg either side of the coil-lead path (178 deg): the lead pair's own
    field drops to the background 4 deg away. Option B's coil, channel, combs, shield, receive boards, display and lid are kept."""
    apply_option_b(S)
    fin = lambda deg, zone, what, hv=False, r0=19.05: dict(kind="fin", deg=deg, r=(r0, 103.0), z=(4.0, 12.4), t=1.0, side=1.2, notch=(21.0, 11.0), zone=zone, hv=hv,
                                                          below=0.0, above=0.0, what=what)
    bi = {}
    bi["FIN_HV1"] = fin(170.0, "hv", "MP1 v2 function: HV limiter (IXTY08N100D2), clamps, LMH6629 preamp; LV output by flex through the 156 deg wall", True, 40.0)
    bi["FIN_HV2"] = fin(186.0, "hv", "TXJ function: coil-lead and shaft TX-pair termination (wire-hole pads), damping network", True, 40.0)
    for k, d in enumerate((100.0, 122.0, 144.0)): bi[f"FIN_A{k + 1}"] = fin(d, "analog", "AB1 function: receive channels (mono, QA, QB, REF3), gates / integrators, ADC")
    for k, d in enumerate((214.0, 245.0, 276.0, 307.0, 338.0, 9.0, 40.0, 71.0)):
        bi[f"FIN_D{k + 1}"] = fin(d, "digital", "CB1D function: RP2354A, clocks, LMR36520 + TPS22918 LED rail, LED data, power entry" if k < 6 else "CB1D function: sensors, audio / link, spare")
    bi["HUB_PCB"] = dict(kind="disc", c=(0.0, 0.0), r=20.5, z=(11.6, 12.4), below=0.0, above=0.5, what="LV hub: star (radial) interconnect of the LV fins by soldered flex tails; no ring traces (rule 5); 4 mm fill bore")
    bi["LED"] = S["boards_inner"]["LED"]; S["boards_inner"] = bi
    S["hub"] = dict(r=20.0, z=(3.8, 11.0), slot_depth=1.0, slot_w=1.1, bore_d=4.0, what="printed hub: radial slots for the LV fins' inner edges, a 4 mm bore to inject potting from the centre")
    S["fin_guides"] = dict(t=0.6, h=1.2, r=(24.0, 100.0), gap=1.1, what="paired floor rails either side of every fin (1.1 mm gap for a 1.0 mm board): tilt < 1 deg")
    S["bay_floor"] = dict(r=103.6, z=(3.2, 3.8), what="printed floor over QB carrying the fin rails")
    S["walls"].update(r=(21.0, 103.6), note="radial sector walls 89 / 156 / 198 deg (themselves radial planes); the 156 deg wall keeps the LV slot for the HV1 output flex")
    S["zone_rules"] = S["zone_rules"] + ["every board is a radial fin (field-free orientation); fins located by rails and hub slots to < 1 deg",
                                         "HV fins at 170 / 186 deg, >= 4 deg from the coil-lead path (178 deg); lead pair twisted / tight"]
if VARIANT == "B": apply_option_b(SPEC)
if VARIANT == "BF": apply_option_bf(SPEC)
# ------------------------------------------------------------------------------------------------ primitives
def cyl(r, z0, z1, seg=SEG): return m3.Manifold.cylinder(z1 - z0, r, r, seg).translate([0, 0, z0])
def ring(r0, r1, z0, z1): return cyl(r1, z0, z1) - cyl(r0, z0 - 0.1, z1 + 0.1)
def box(cx, cy, sx, sy, z0, z1): return m3.Manifold.cube([sx, sy, z1 - z0], True).translate([cx, cy, (z0 + z1) / 2])
def at(man, c): return man.translate([c[0], c[1], 0])
def radial_wall(deg, r0, r1, t, z0, z1): return m3.Manifold.cube([r1 - r0, t, z1 - z0], True).translate([(r0 + r1) / 2, 0, (z0 + z1) / 2]).rotate([0, 0, deg])
def slot_towards(c, deg, w, z0, z1, L=12.0):
    """a slot of width w cut from the point c outward along direction deg (for hinge / lead exits)"""
    return m3.Manifold.cube([L, w, z1 - z0], True).translate([L / 2, 0, (z0 + z1) / 2]).rotate([0, 0, deg]).translate([c[0], c[1], 0])
def led_positions():
    import rf2_ledgrid as LG
    return [(e["x"], e["y"]) for e in LG.layout()["leds"]]
def led_sites():
    """(x, y, rot, size_x, size_y) of every part on the display flex: LEDs 2 x 2, capacitors 1.0 x 0.5 (courtyard-sized boxes: 2.2 x 2.2, 1.2 x 0.7)"""
    import rf2_ledgrid as LG
    out = []
    for e in LG.layout()["leds"]: out += [(e["x"], e["y"], e["rot"], 2.2, 2.2), (e["cx"], e["cy"], e["crot"], 1.2, 0.7)]
    return out
def boss_positions():
    b = SPEC["led_bosses"]; return [pol(b["r"], b["deg0"] + 360 * k / b["n"]) for k in range(b["n"])]
# ------------------------------------------------------------------------------------------------ envelopes (what the boards occupy)
def envelope(k):
    v = SPEC["boards_inner"][k]; z0, z1 = v["z"]; KB, KA = 1.2, 0.4
    if v["kind"] == "disc":
        e = at(cyl(v["r"], z0, z1, 128), v["c"])
        if v["below"] > 0: e = e + at(cyl(v["r"] - KB, z0 - v["below"], z0, 128), v["c"])               # zero-height solids are invalid manifolds
        if v["above"] > 0: e = e + at(cyl(v["r"] - KA, z1, z1 + v["above"], 128), v["c"])
    elif v["kind"] == "box":
        sx, sy = v["size"]; cx, cy = v["c"]
        e = box(cx, cy, sx, sy, z0, z1) + box(cx, cy, sx - 2 * KB, sy - 2 * KB, z0 - v["below"], z0) + box(cx, cy, sx - 2 * KA, sy - 2 * KA, z1, z1 + v["above"])
    elif v["kind"] == "fin":                                                                    # radial fin: board slab (notched at the top inner corner) + parts on both faces
        r0, r1 = v["r"]; z0, z1 = v["z"]; t = v["t"]; sd = v["side"]; nr, nz = v["notch"]
        b = box((r0 + r1) / 2, 0, r1 - r0, t, z0, nz) + box((max(r0, nr) + r1) / 2, 0, r1 - max(r0, nr), t, nz, z1)
        pr0 = max(r0, nr) + 2.0; pz0, pz1 = z0 + 1.2, z1 - 0.4
        for sgn in (1, -1): b = b + box((pr0 + r1 - 2.0) / 2, sgn * (t / 2 + sd / 2), r1 - 2.0 - pr0, sd, pz0, pz1)
        e = b.rotate([0, 0, v["deg"]])
    else:                                                                                       # LED display flex: its real outline (rf2_ledgrid) + part sites on top
        import rf2_ledgrid as LG
        o = LG.outline(); cs = m3.CrossSection([list(o.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in o.interiors], m3.FillRule.EvenOdd)
        e = m3.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])
        for x, y, rot, sx, sy in led_sites(): e = e + m3.Manifold.cube([sx, sy, v["above"]], True).rotate([0, 0, rot]).translate([x, y, z1 + v["above"] / 2])
        for p in boss_positions(): e = e - at(cyl(SPEC["led_bosses"]["hole_d"] / 2, z0 - 1, z1 + 1, 32), p)
    return e
# ------------------------------------------------------------------------------------------------ printed parts
def parts():
    S = SPEC; P = {}; sh = S["shell"]; R = S["envelope"]["R"]; bi = S["boards_inner"]
    # shell: skid + wall + stack pins
    lower = cyl(R, 0, sh["skid_t"]) + ring(sh["wall_r"][0], sh["wall_r"][1], 0, sh["wall_z"][1])
    sp = S["stack_pins"]
    for d in sp["deg"]: lower = lower + at(cyl(sp["d"] / 2, sp["z"][0] - 0.01, sp["z"][1], 32), pol(sp["r"], d))
    P["SHELL_LOWER"] = lower
    # lid: clear PETG (the display shines through; no windows), display bosses + pins at the rim holes, cable gland boss and hole
    lid = cyl(R, *sh["lid_z"]); lb = S["led_bosses"]; L = bi["LED"]
    for p in boss_positions():
        lid = lid + at(cyl(lb["boss_d"] / 2, L["z"][1], sh["lid_z"][0] + 0.01, 32), p) + at(cyl(lb["pin_d"] / 2, L["z"][0], L["z"][1] + 0.01, 32), p)
    g = S["gland"]; lid = lid + at(cyl(g["boss_d"] / 2, g["boss_z"][0], sh["lid_z"][0] + 0.01, 64), g["c"]) - at(cyl(g["d"] / 2, g["boss_z"][0] - 1, sh["lid_z"][1] + 1, 64), g["c"])
    ll = S["lid_light"]
    if ll.get("type") == "light_plate":                                                         # conical wells through the lid over every LED
        z0w, z1w = sh["lid_z"]; land = ll.get("land", 0.0); hw = z1w - z0w - land; r0w, r1w = ll["d_bottom"] / 2, ll["d_top"] / 2; kw = (r1w - r0w) / hw; e = 0.2
        cone = m3.Manifold.cylinder(hw + e, r0w, r1w + kw * e, 48).translate([0, 0, z0w + land])                  # cone above the land
        if land > 0: cone = cone + m3.Manifold.cylinder(land + 2 * e, r0w, r0w, 48).translate([0, 0, z0w - e])     # straight land at the bottom
        lid = lid - m3.Manifold.compose([cone.translate([x, y, 0]) for x, y in led_positions()])
    P["LID"] = lid
    # coil channel: inner wall + floor, lead slot at the heel
    ch = S["channel"]; co = S["coil"]
    chan = ring(ch["inner_wall_r"][0], ch["inner_wall_r"][1], ch["z"][0], ch["z"][1]) + ring(ch["inner_wall_r"][0], sh["wall_r"][0] - 0.2, co["floor_z"][0], co["floor_z"][1])
    P["COIL_CHANNEL"] = chan - m3.Manifold.cube([12, ch["lead_slot_w"], 30], True).translate([109.0, 0, 15]).rotate([0, 0, ch["lead_exit_deg"]])
    fins = {k: v for k, v in bi.items() if v.get("kind") == "fin"}
    # bay walls with the LV slot in the 156 deg wall (MP1 output flex to AB1A) and a cable slot in the 198 deg wall for the LV cores to CB1D
    w = S["walls"]; walls = None
    for d in w["deg"]:
        x = radial_wall(d, w["r"][0], w["r"][1], w["t"], *w["z"]); walls = x if walls is None else walls + x
    walls = walls - slot_towards(pol(74.0, 156.0), 156.0 + 90, 10.0, 8.0, 12.0, 6) - slot_towards(pol(74.0, 156.0), 156.0 - 90, 10.0, 8.0, 12.0, 6)
    P["BAY_WALLS"] = walls
    if fins:                                                                                # clean-sheet seats: floor, rails, hub
        fl = cyl(S["bay_floor"]["r"], *S["bay_floor"]["z"])
        for d in sp["deg"]: fl = fl - at(cyl(sp["d"] / 2 + 0.2, sp["z"][0] - 1, sp["z"][1] + 1, 32), pol(sp["r"], d))
        P["BAY_FLOOR"] = fl; g = S["fin_guides"]; hb = S["hub"]; rails = None; hub = cyl(hb["r"], *hb["z"]) - cyl(hb["bore_d"] / 2, hb["z"][0] - 1, hb["z"][1] + 1, 32)
        for k, v in fins.items():
            ra = (max(g["r"][0], v["r"][0] + 2.0), g["r"][1])
            for sgn in (1, -1):
                x = box((ra[0] + ra[1]) / 2, sgn * (g["gap"] / 2 + g["t"] / 2), ra[1] - ra[0], g["t"], S["bay_floor"]["z"][1], S["bay_floor"]["z"][1] + g["h"]).rotate([0, 0, v["deg"]])
                rails = x if rails is None else rails + x
            if v["r"][0] < hb["r"]: hub = hub - box(hb["r"] - hb["slot_depth"] / 2, 0, hb["slot_depth"] + 0.02, hb["slot_w"], hb["z"][0] - 1, hb["z"][1] + 1).rotate([0, 0, v["deg"]])
        P["FIN_RAILS"] = rails; P["HUB"] = hub
    # AB1 cradles: ledge (under the 1.2 mm edge keep-out), wall, snap lip; hinge slot towards the centre
    for k in ("AB1A", "AB1B"):
        if k not in bi: continue
        v = bi[k]; z0, z1 = v["z"]; c = v["c"]; r = v["r"]; zb = S["bay"]["z"][0]
        cr = at(ring(r + 0.3, r + 1.5, zb, z1 + 0.8, ), c) + at(ring(r - 1.2, r + 0.3, zb, z0), c) + at(ring(r - 0.4 + 0.05, r + 0.3, z1 + 0.2, z1 + 0.8), c)
        P["CRADLE_" + k] = cr - slot_towards(c, v["hinge_deg"], 10.0, zb - 1, z1 + 2, 30)
    # CB1D tower: ledge, wall, snap lip; slots towards AB1A / AB1B / MP1 (hinges come down) and towards the gland (LV cores)
    v = bi.get("CB1D", bi.get("HUB_PCB")); z0, z1 = v["z"]; r = v["r"]; zb = S["bay"]["z"][0]
    tw = ring(r + 0.3, r + 1.5, zb, z1 + 0.9) + ring(r - 1.2, r + 0.3, zb, z0) + ring(r - 0.4 + 0.05, r + 0.3, z1 + 0.2, z1 + 0.9)
    for d in (106.0, 137.0, 170.0, HEEL + 8):
        tw = tw - slot_towards((0, 0), d, 10.0, zb - 1, z1 + 2, 60)
    if "CB1D" in bi: P["CB1D_TOWER"] = tw
    # MP1 / TXJ trays: ledge under the board edge, rim; HV slot on the coil side, LV slot on the other
    for k, hv_deg, lv_deg in (("MP1", 180.0, 0.0), ("TXJ", 180.0, 0.0)):
        if k not in bi: continue
        v = bi[k]; sx, sy = v["size"]; cx, cy = v["c"]; z0, z1 = v["z"]; zb = S["bay"]["z"][0]
        rim = box(cx, cy, sx + 3.0, sy + 3.0, zb, z1 + 0.8) - box(cx, cy, sx + 0.6, sy + 0.6, zb - 1, z1 + 1)
        ledge = box(cx, cy, sx + 0.6, sy + 0.6, zb, z0) - box(cx, cy, sx - 2.4, sy - 2.4, zb - 1, z0 + 1)
        tray = rim + ledge - slot_towards((cx, cy), hv_deg, 8.0, zb - 1, z1 + 2, 20) - slot_towards((cx, cy), lv_deg, 8.0, zb - 1, z1 + 2, 20)
        P["TRAY_" + k] = tray
    # boards (as solids with the stack-pin holes) and envelopes
    for k, b in S["boards"].items():
        s = cyl(b["r"], *b["z"])
        for d in sp["holes_deg"]: s = s - at(cyl(sp["hole_d"] / 2, b["z"][0] - 1, b["z"][1] + 1, 32), pol(sp["r"], d))
        P["BOARD_" + k] = s
    for k in bi: P["ENV_" + k] = envelope(k)
    # litz (26 turns) for fit and mass
    litz = None; nc = len(co["columns_r"])
    for j in range(co["turns"]):
        t = m3.CrossSection.circle(co["litz_od"] / 2, 24).translate([co["columns_r"][j % nc], co["row0_z"] + (j // nc) * co.get("row_pitch", co["pitch"])]).revolve(SEG)
        litz = t if litz is None else litz + t
    P["LITZ"] = litz
    if "coil_combs" in S:                                                                   # option B: winding combs in the channel (open-topped slots)
        cb = S["coil_combs"]; r0, r1 = S["channel"]["inner_wall_r"][1], S["shell"]["wall_r"][0] - 0.2; z0, z1 = co["floor_z"][1], S["channel"]["z"][1]
        plate = m3.Manifold.cube([r1 - r0, cb["t"], z1 - z0], True).translate([(r0 + r1) / 2, 0, (z0 + z1) / 2])
        for rc in co["columns_r"]: plate = plate - m3.Manifold.cube([cb["slot"], cb["t"] + 1, z1 - z0 + 1], True).translate([rc, 0, (z0 + z1) / 2])
        combs = None
        for k in range(cb["n"]):
            d = cb["deg0"] + 360.0 * k / cb["n"]
            if abs(((d - S["channel"]["lead_exit_deg"]) + 180) % 360 - 180) < 8: continue          # keep the lead slot free
            x = plate.rotate([0, 0, d]); combs = x if combs is None else combs + x
        P["COIL_COMBS"] = combs
    if "shield_coat" in S:
        sc = S["shield_coat"]; P["SHIELD_COAT"] = ring(sc["r"][0], sc["r"][1], *sc["z"]) - m3.Manifold.cube([6, sc["slit_w"], 40], True).translate([115.0, 0, 10]).rotate([0, 0, sc["slit_deg"]])
    f = None
    for rot in ([0, 0, 0], [90, 0, 0], [0, 90, 0]):
        x = ring(46, 50, -4, 4).rotate(rot); f = x if f is None else f + x          # 100 mm windings (rf2_ref3.py)
    P["REF3_FORMER"] = f.translate([0, 0, 600])                        # 0.6 m up the shaft line (schematic position)
    return P
def write_stl(man, path):
    mesh = man.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    with open(path, "wb") as f:
        f.write(b"RF2 head v1".ljust(80, b" ")); f.write(struct.pack("<I", len(F)))
        for a, b, c in F:
            n = np.cross(V[b] - V[a], V[c] - V[a]); nn = np.linalg.norm(n); n = n / nn if nn else n
            f.write(struct.pack("<12fH", *n, *V[a], *V[b], *V[c], 0))
if __name__ == "__main__":
    P = parts()
    for name in os.listdir(OUT):
        if name.startswith("RF2_") and name.endswith(".stl") and name[4:-4] not in P: os.remove(os.path.join(OUT, name))   # parts renamed this version (generated files only)
    for k, v in P.items(): write_stl(v, os.path.join(OUT, f"RF2_{k}.stl"))
    json.dump(SPEC, open(os.path.join(OUT, "rf2_head_spec.json"), "w"), indent=1)
    print({k: round(v.volume() / 1000, 2) for k, v in P.items()})
