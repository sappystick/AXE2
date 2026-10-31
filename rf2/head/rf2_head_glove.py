#!/usr/bin/env python3
"""RF2 glove housing + internal head map (owner 2026-10-31). MODELED / tool-checked; nothing printed, moulded or built.

From the component data (the head SPEC of rf2_head.py variant BF with the 2026-10-31 owner decisions: bank-wound coil, PRX layer, MP2 fin; the built fin
boards' part bodies from out/<B>/<b>_check.json; the netlist footprint library for heights), this computes
  1. the ZONE MAP of the head: coil channel, HV island, analog, digital, hub, the 178 deg heel lead lane, the PRX lead lane and the metal keep-out next
     to the litz; every part gets its zone, its echo drift (rf2_zones.json metal echoes x the fin orientation factor of rf2_layout.json, 5 K step,
     criterion <= 0.5 x gate noise: rf2_system) and its HV clearance (envelope >= 3.0 mm to non-HV, rule 6 >= 1.0 mm to the flyback copper);
  2. the GLOVE HOUSING: four parts that hold every component with stated clearances:
       G_SHELL  skid + outer wall + stack pins + the masking rib that keeps the nickel shield coat's slit open (rule 5) [PETG, FDM]
       G_TRAY   one insert over QB: floor (bay + coil channel in one plate), channel inner wall with the litz lead notch, fin rails, hub with slots,
                sector walls, the HV epoxy ISLAND (walls at 166 / 190 deg, arcs at r 37.2 and r 102.6-103.4 so the epoxy stays >= 3.0 mm from the
                litz), gel TROUGHS around the three analog fins, the PRX lead lane from the feed hole to MP2, two sealed litz pass-through holes,
                the SH1 ground-wire and PRX feed holes, radial stiffening ribs in the digital sector [PETG, FDM]
       G_COMBS  the winding combs (0.30 mm teeth: resin SLA, below the FDM wall) [resin]
       G_LID    the light plate (rf2_head LID) + the cord gland boss with a strain-relief cross pin [PETG, FDM]
     plus the POTTING solids (HV island epoxy, analog gel troughs + lead lane, coil-channel syntactic foam) measured as the free volume of each cavity
     up to its stated fill level (fill port = funnel notch at one end, vent = weir notch at the fill level at the other end);
  3. a MOULDED variant of G_TRAY (1.0 deg draft on every wall parallel to the pull, z) to show what moulding changes.
Process today: printed PETG (FDM, 0.4 mm nozzle, 0.2 mm layers): vertical walls >= 0.8 mm (2 perimeters), horizontal plates >= 0.6 mm (3 layers);
combs resin SLA (>= 0.3 mm). Moulded variant: walls >= 0.8 mm, 1.0 deg draft (ASSUMED process rules, no moulder review).
Outputs (rf2/head/out_BF/glove/): G_<PART>.stl + .step, POT_<X>.stl, rf2_glove_cutaway.png, rf2_glove_exploded.png, rf2_glove_map.png, rf2_head_glove.json.
usage: python3 rf2/head/rf2_head_glove.py   (then rf2_head_glove_check.py)"""
import os, sys, json, math, time, itertools
import numpy as np
os.environ["RF2_VARIANT"] = "BF"
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..")); sys.path.insert(0, HERE)
import manifold3d as m3
import rf2_head as H
import rf2_netlist as NL
S = H.SPEC; pol = H.pol; cyl, ring, box, at = H.cyl, H.ring, H.box, H.at
OUT = os.path.join(H.OUT, "glove"); os.makedirs(OUT, exist_ok=True)
HEEL = H.HEEL
# ------------------------------------------------------------------------------------------------ design rules (stated; each becomes a numeric check)
PROC = dict(printed=dict(name="PETG FDM, 0.4 mm nozzle, 0.2 mm layers", wall_min=0.8, plate_min=0.6, draft_deg=0.0),
            moulded=dict(name="injection moulded PETG / PC (ASSUMED rules, no moulder review)", wall_min=0.8, plate_min=0.8, draft_deg=1.0),
            resin=dict(name="resin SLA", wall_min=0.3, plate_min=0.3, draft_deg=0.0))
T_W = 0.8                     # glove wall / rib thickness (printed min wall)
C_POT = 1.0                   # potting cavity: clearance from a fin's parts envelope to the cavity wall (>= 1.0 mm of potting over HV copper: rule 6 scale)
EPOXY_LITZ_MIN = 3.0          # MG 832TC epoxy kept >= 3.0 mm from the winding (rf2_head SPEC potting: eps 3.7, DF 0.1)
FILL_Z = 12.5                 # potting fill level (fin tops at 12.4: 0.1 mm cover over the board edge, 0.5 over the parts envelope at 12.0)
WALL_TOP = 12.6               # cup / trough / sector wall tops (0.5 mm under the display flex at 13.1)
HV_DEG = (165.0, 191.0)       # HV epoxy island between these radial walls (HV fins at 170 / 186, lead lane at 178): 5 deg = 3.7 mm lateral at the parts' inner end (r 42)
HV_R_IN = 37.2                # HV island inner arc (HV fins start at r 40)
LITZ_PASS_D = 2.0             # litz pass-through holes in the HV island's outer arc (litz 1.372 + FEP sleeve, ASSUMED 1.70 OD)
LITZ_SLEEVE_OD = 1.70
DENS = dict(PETG=1.27, resin=1.18, epoxy=1.15, gel=0.98, syntactic=0.70)   # g/cm3: PETG / resin / MG 832TC / silicone gel ASSUMED; syntactic foam 0.70 ASSUMED (K1 bubbles in silicone)
RIB = dict(t=T_W, h=2.0, r=(32.0, 100.0))
GLAND = dict(curl_d=6.5, pin_d=1.6, pin_z=13.4, what="cord flex (single-layer polyimide 0.15 mm, rf2_cordflex) C-curled across its width to 6.5 mm "
             "(curl radius 3.25 mm >= 6 x 0.15 mm IPC static, rf2_cordflex note) through the 8.0 mm gland bore; strain relief: a 1.6 mm PETG cross pin through the boss, "
             "the flex looped around it (SDC 2300 pin pattern, rf2_cordflex); the gland end potted in the HV island epoxy")
def zero(v): return abs(v) < 1e-6
# ------------------------------------------------------------------------------------------------ helpers
def radial_wall(deg, r0, r1, t, z0, z1, draft=0.0):
    """a radial wall (plane through the axis) from r0 to r1; draft (deg): thicker at the bottom by 2 h tan(draft)"""
    h = z1 - z0
    if draft <= 0: return m3.Manifold.cube([r1 - r0, t, h], True).translate([(r0 + r1) / 2, 0, (z0 + z1) / 2]).rotate([0, 0, deg])
    return _radial_draft(deg, r0, r1, t, t + 2 * h * math.tan(math.radians(draft)), z0, z1)
def _radial_draft(deg, r0, r1, t, tb, z0, z1):
    a = m3.Manifold.cube([r1 - r0, tb, 0.01], True).translate([(r0 + r1) / 2, 0, z0 + 0.005])
    b = m3.Manifold.cube([r1 - r0, t, 0.01], True).translate([(r0 + r1) / 2, 0, z1 - 0.005])
    return m3.Manifold.batch_hull([a, b]).rotate([0, 0, deg])
def arc_wall(r_in, r_out, d0, d1, z0, z1, draft=0.0):
    """a wall along an arc (r_in..r_out) between azimuths d0..d1; drafted symmetric about its mid radius"""
    h = z1 - z0; e = h * math.tan(math.radians(draft)) if draft > 0 else 0.0
    prof = [(r_in - e, z0), (r_out + e, z0), (r_out, z1), (r_in, z1)]
    w = m3.CrossSection([prof]).revolve(256, d1 - d0)
    return w.rotate([0, 0, d0])
def sector_prism(d0, d1, r0, r1, z0, z1, n=96):
    pts = [(r1 * math.cos(math.radians(a)), r1 * math.sin(math.radians(a))) for a in np.linspace(d0, d1, n)] + \
          ([(0.0, 0.0)] if r0 <= 0 else [(r0 * math.cos(math.radians(a)), r0 * math.sin(math.radians(a))) for a in np.linspace(d1, d0, n)])   # CCW (outer arc first)
    return m3.CrossSection([pts]).extrude(z1 - z0).translate([0, 0, z0])
def fin_frame_box(deg, x0, x1, y0, y1, z0, z1):
    """a box in a fin's frame (x along the radius, y across the fin), rotated to azimuth deg"""
    return m3.Manifold.cube([x1 - x0, y1 - y0, z1 - z0], True).translate([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]).rotate([0, 0, deg])
def union(ms):
    ms = [m for m in ms if m is not None and not m.is_empty()]
    return m3.Manifold.batch_boolean(ms, m3.OpType.Add) if ms else m3.Manifold()
def write_stl(man, path): H.write_stl(man, path)
# ------------------------------------------------------------------------------------------------ measured part data from the built boards
def fin_side_envelopes():
    """per fin: the parts envelope on each face. Built fin boards (TXF, MP2): tallest part body from the netlist library (measured from the KiCad
    placement); unbuilt fins: the SPEC reservation (side 1.2 mm, ASSUMED)."""
    out = {}
    for k, v in S["boards_inner"].items():
        if v.get("kind") != "fin": continue
        b = v.get("board") or ("TXF" if k == "FIN_HV2" else None)
        src = "SPEC reservation (ASSUMED)"; hmax = None
        if b and b in NL.BOARDS:
            p = os.path.join(HERE, "out", b, f"{b.lower()}_check.json")
            if os.path.exists(p):
                d = json.load(open(p)); hmax = max(pp["body"][2] for pp in d.get("placement_in_head", [])) if d.get("placement_in_head") else None
                src = f"{b} built board (out/{b}/{b.lower()}_check.json): tallest body {hmax} mm"
        out[k] = dict(side=v["side"], board=b, tallest_part_mm=hmax, source=src, side_ok=(hmax is None or hmax <= v["side"] + 1e-9))
    return out
# ------------------------------------------------------------------------------------------------ the zone map
def zone_of(deg, r):
    a = deg % 360
    if r >= S["channel"]["inner_wall_r"][0]: return "coil channel"
    if r < S["hub"]["r"] + 1.0: return "hub (centre)"
    if HV_DEG[0] <= a <= HV_DEG[1]: return "HV island"
    if S["sectors"]["hv"][0] <= a <= S["sectors"]["hv"][1]: return "HV sector (unpotted margin)"
    if S["sectors"]["analog"][0] <= a <= S["sectors"]["analog"][1]: return "analog"
    return "digital"
def echo_tables():
    J = lambda n: json.load(open(os.path.join(ROOT, "rf2", "results", n)))
    zo, la = J("rf2_zones.json"), J("rf2_layout.json")
    fac = {(c["zone"], c["case"]): c["solid_plane_echo_vs_flat"] for c in la["cases"]}
    E = {e["object"]: e for e in zo["echoes"]}
    tab = next(e for e in zo["echoes"] if e["object"].startswith("IXTY08N100D2"))
    hatch = {w: next(e for e in zo["echoes"] if e["where"].startswith(w) and "border slit open" in e["object"]) for w in ("MP1", "TXJ", "AB1A", "CB1D")}
    led = next(e for e in zo["echoes"] if "PCB-holder" in e["object"])
    coat = next(e for e in zo["echoes"] if e["object"].startswith("MG 841AR"))
    return dict(f_hv=fac[("HV (next to the coil leads)", "radial fin, exact")], f_hv_tilt=fac[("HV (next to the coil leads)", "radial fin, 1 deg tilt about its radial axis")],
                f_an=fac[("analog", "radial fin, 1 deg tilt about its radial axis")], f_dig=fac[("digital", "radial fin, 1 deg tilt about its radial axis")],
                tab=tab, hatch=hatch, led=led, coat=coat, step_K=5.0, limit=0.5)
def zone_map(P, sides):
    E = echo_tables(); K = E["step_K"]; rows = []
    hv_keys = [k for k, v in S["boards_inner"].items() if v.get("hv")]
    hvm = union([P["ENV_" + k] for k in hv_keys])
    def drift_row(name, deg, r, metal, drift, src, hv=False, solid=None, note="", zone=None):
        z = zone or zone_of(deg, r); row = dict(part=name, zone=z, deg=round(deg % 360, 1), r=round(r, 1), metal=metal, echo_drift_5K_x_noise=drift, drift_limit=E["limit"],
                                        drift_ok=drift <= E["limit"], drift_source=src, hv=hv, note=note)
        if solid is not None and not hv: row["gap_to_HV_envelopes_mm"] = round(float(solid.min_gap(hvm, 20.0)), 3); row["hv_envelope_ok"] = row["gap_to_HV_envelopes_mm"] >= 3.0
        rows.append(row)
    tilt = lambda zone: E["f_hv_tilt"] if zone.startswith("HV") else (E["f_an"] if zone == "analog" else E["f_dig"])
    for k, v in S["boards_inner"].items():
        if v.get("kind") == "fin":
            zname = zone_of(v["deg"], 60.0)
            if k == "FIN_HV1":
                d = E["tab"]["drift_x_noise_per_K"] * K * E["f_hv_tilt"]; m = "IXTY08N100D2 TO-252 tab (MP1 v2 function)"; src = "rf2_zones IXTY tab x rf2_layout HV fin 1 deg tilt factor"
            elif v.get("board") == "MP2":
                d = E["tab"]["drift_x_noise_per_K"] * K * E["f_an"]; m = "MP1 v1 parts (no tab; IXTY tab used as the upper bound, as the boards plugin)"; src = "rf2_zones IXTY tab x rf2_layout analog fin 1 deg tilt"
            else:
                w = "TXJ" if k == "FIN_HV2" else ("AB1A" if zname == "analog" else "CB1D"); e = E["hatch"][w]
                d = e["drift_x_noise_per_K"] * K * tilt(zname); m = "slit-hatched copper (rule 5 design), MLCC only"; src = f"rf2_zones {w} hatched slit-open x fin tilt factor"
            drift_row(k + (f" ({v['board']})" if v.get("board") else ""), v["deg"], (v["r"][0] + v["r"][1]) / 2, m, float(f"{d:.3g}"), src, hv=bool(v.get("hv")), solid=P["ENV_" + k],
                      note=sides[k]["source"])
        elif k == "HUB_PCB":
            e = E["hatch"]["CB1D"]; drift_row(k, 0.0, 0.0, "slit-hatched LV star, no ring traces", float(f"{e['drift_x_noise_per_K'] * K * E['f_dig']:.3g}"), "rf2_zones CB1D hatched x digital tilt (ASSUMED: flat disc at the centre, worst of the table)", solid=P["ENV_HUB_PCB"])
        elif k == "LED":
            drift_row("LED display flex (LR1)", 0.0, 60.0, "522 SK9822-EC20 PCB-holder packages", float(f"{E['led']['drift_x_noise_per_K'] * K:.3g}"), "rf2_zones display PCB-holder package (flat)", solid=P["ENV_LED"])
    drift_row("shield coat (MG 841AR, slit at %.0f deg)" % S["shield_coat"]["slit_deg"], S["shield_coat"]["slit_deg"], 114.5, "25 um nickel paint", float(E["coat"]["drift_x_noise_per_K"] * K), "rf2_zones MG 841AR closed band (upper bound)")
    drift_row("SH1 split-ring shield", 0.0, 60.0, "slit rings + spine (loop-free, rf2_shield_pcb)", 0.0, "rule 5 design: every ring slit (sh1_check topology loop_free)", zone="receive stack (z 1.2-3.3, under every sector)")
    drift_row("PRX planar RX (layer)", S["prx"]["feed"]["deg"], 95.0, "35 um spirals: open spiral, no closed loop", 0.0, "receive element itself (nulled to the TX: residual M %.2g uH)" % S["prx"]["M_residual_uH"], zone="receive stack (z 1.2-3.3, under every sector)")
    for b in ("QA", "QB"): drift_row(f"SB1R-{b} ({S['boards'][b]['copper_um']} um)", 0.0, 60.0, "receive spirals (unchanged copper)", 0.0, "receive element itself", zone="receive stack (z 1.2-3.3, under every sector)")
    drift_row("transmit litz (bank wound)", HEEL, 110.0, "26 turns FEP litz", 0.0, "the transmitter")
    return rows
# ------------------------------------------------------------------------------------------------ housing parts
def build(variant="printed"):
    """returns (housing parts, potting solids, features) for variant 'printed' (no draft) or 'moulded' (draft on the tray walls)"""
    t0 = time.time(); P = H.parts(); dr = PROC[variant]["draft_deg"]; bi = S["boards_inner"]; sh = S["shell"]; R = S["envelope"]["R"]
    zf0, zf1 = S["bay_floor"]["z"]; zc_top = S["channel"]["z"][1]; rcw0, rcw1 = S["channel"]["inner_wall_r"]; lid0 = sh["lid_z"][0]
    sp = S["stack_pins"]; F = {}                                                      # named features (for pocket clearances)
    # --- G_SHELL
    F["skid"] = cyl(R, 0, sh["skid_t"]); F["outer_wall"] = ring(sh["wall_r"][0], sh["wall_r"][1], 0, sh["wall_z"][1])
    F["stack_pins"] = union([at(cyl(sp["d"] / 2, sp["z"][0] - 0.01, sp["z"][1], 32), pol(sp["r"], d)) for d in sp["deg"]])
    sc = S["shield_coat"]; rib_w = sc["slit_w"]
    F["coat_mask_rib"] = m3.Manifold.cube([0.16, rib_w, sh["wall_z"][1] - sh["skid_t"]], True).translate([sh["wall_r"][0] - 0.07, 0, (sh["wall_z"][1] + sh["skid_t"]) / 2]).rotate([0, 0, sc["slit_deg"]])
    G = {}
    G["G_SHELL"] = union([F["skid"], F["outer_wall"], F["stack_pins"], F["coat_mask_rib"]])
    # --- G_TRAY
    fl = cyl(sh["wall_r"][0] - 0.2, zf0, zf1)
    for d in sp["deg"]: fl = fl - at(cyl(sp["d"] / 2 + 0.2, zf0 - 1, zf1 + 1, 32), pol(sp["r"], d))
    fl = fl - at(cyl(sp["hole_d"] / 2, zf0 - 1, zf1 + 1, 32), pol(sp["r"], 22.5))                   # SH1 ground wire up the 22.5 deg stack hole (was not cut in BAY_FLOOR)
    fl = fl - H.feed_hole(zf0 - 1, zf1 + 1)                                                          # PRX feed
    F["floor"] = fl
    lead_notch = m3.Manifold.cube([4, S["channel"]["lead_slot_w"], 30], True).translate([(rcw0 + rcw1) / 2, 0, 15 + zf1 + 1.0]).rotate([0, 0, HEEL])   # leads leave the coil over a 1 mm sill
    F["channel_wall"] = arc_wall(rcw0, rcw1, 0, 360, zf1, zc_top, dr) - lead_notch if dr > 0 else ring(rcw0, rcw1, zf1, zc_top) - lead_notch
    g = S["fin_guides"]; rails = []; fins = {k: v for k, v in bi.items() if v.get("kind") == "fin"}
    for k, v in fins.items():
        ra = (max(g["r"][0], v["r"][0] + 2.0), min(g["r"][1], v["r"][1] - 1.0))
        for sgn in (1, -1):
            rails.append(fin_frame_box(v["deg"], ra[0], ra[1], sgn * g["gap"] / 2, sgn * (g["gap"] / 2 + T_W), zf1, zf1 + g["h"]))
    F["fin_rails"] = union(rails)
    hb = S["hub"]; hub = cyl(hb["r"], zf1, hb["z"][1]) - cyl(hb["bore_d"] / 2, zf1 - 1, hb["z"][1] + 1, 32)
    for k, v in fins.items():
        if v["r"][0] < hb["r"]: hub = hub - box(hb["r"] - hb["slot_depth"] / 2, 0, hb["slot_depth"] + 0.02, hb["slot_w"], zf1 - 1, hb["z"][1] + 1).rotate([0, 0, v["deg"]])
    F["hub"] = hub
    w = S["walls"]; sw = []
    for d in w["deg"]:
        if HV_DEG[0] < d < HV_DEG[1]: continue
        sw.append(radial_wall(d, w["r"][0], w["r"][1], w["t"], zf1, WALL_TOP, dr))
    walls = union(sw) - H.slot_towards(pol(74.0, 156.0), 156.0 + 90, 10.0, 8.0, 12.0, 6) - H.slot_towards(pol(74.0, 156.0), 156.0 - 90, 10.0, 8.0, 12.0, 6)
    F["sector_walls"] = walls
    # HV island: radial walls at 166 / 190, inner arc, outer arc 3.0 mm from the litz, two litz pass-through holes
    turns = H.coil_turns(); litz_in = min(r for r, _ in turns) - S["coil"]["litz_od"] / 2
    r_ep = round(litz_in - EPOXY_LITZ_MIN - 0.05, 3)                                                # epoxy may reach this radius (0.05 mm for the 256-facet arc)
    hv_w = union([radial_wall(d, HV_R_IN, r_ep + T_W, T_W, zf1, WALL_TOP, dr) for d in HV_DEG] +
                 [arc_wall(HV_R_IN - T_W, HV_R_IN, HV_DEG[0], HV_DEG[1], zf1, WALL_TOP, dr), arc_wall(r_ep, r_ep + T_W, HV_DEG[0], HV_DEG[1], zf1, WALL_TOP, dr)])
    zp = 8.0; holes = [at(m3.Manifold.cylinder(4.0, LITZ_PASS_D / 2, LITZ_PASS_D / 2, 32, True).rotate([0, 90, 0]).translate([r_ep + T_W / 2, 0, zp]).rotate([0, 0, HEEL + s * 1.5]), (0, 0)) for s in (-1, 1)]
    F["hv_island_walls"] = hv_w - union(holes)
    # analog gel troughs: side walls from r 22 to the channel wall, an end wall at r 22 with the fin slot; fill / vent notches
    troughs, tr_inner = [], {}
    for k, v in fins.items():
        if v["zone"] != "analog": continue
        hw = v["t"] / 2 + v["side"] + C_POT; x0, x1 = 22.0 - T_W, rcw0 + 0.01
        side_walls = [fin_frame_box(v["deg"], x0, x1, s * hw, s * (hw + T_W), zf1, WALL_TOP) for s in (1, -1)]
        end = fin_frame_box(v["deg"], x0, x0 + T_W, -hw, hw, zf1, WALL_TOP) - fin_frame_box(v["deg"], x0 - 1, x0 + T_W + 1, -(v["t"] / 2 + 0.05), v["t"] / 2 + 0.05, zf1 - 1, WALL_TOP + 1)
        weir = fin_frame_box(v["deg"], x0 - 1, x0 + T_W + 1, v["t"] / 2 + 0.05 + 0.4, hw - 0.2, FILL_Z, WALL_TOP + 1)                         # vent / weir at the fill level
        funnel = fin_frame_box(v["deg"], x1 - 6.0, x1 - 2.0, hw - 0.5, hw + T_W + 0.5, WALL_TOP - 0.6, WALL_TOP + 1)                       # fill port notch (outer end)
        if dr > 0:                                                                                                                          # moulded: drafted side walls (hull of base / top slabs)
            e = (WALL_TOP - zf1) * math.tan(math.radians(dr))
            side_walls = [m3.Manifold.batch_hull([fin_frame_box(v["deg"], x0, x1, s * (hw - e), s * (hw + T_W + e), zf1, zf1 + 0.01), fin_frame_box(v["deg"], x0, x1, s * hw, s * (hw + T_W), WALL_TOP - 0.01, WALL_TOP)]) for s in (1, -1)]
        tw = union(side_walls + [end]) - weir - funnel
        F.setdefault("_trough_sides", []).extend(side_walls); F.setdefault("_trough_ends", []).append(end)
        troughs.append(tw); tr_inner[k] = (v["deg"], x0 + T_W, x1, hw)
    F["analog_troughs"] = union(troughs); F["analog_trough_sides"] = union(F.pop("_trough_sides")); F["analog_trough_end_slots"] = union(F.pop("_trough_ends"))
    # PRX lead lane: feed hole -> the A2 fin's +side trough wall at the board's input end (r 101.5)
    f = S["prx"]["feed"]; a2 = bi["FIN_A2"]; hw2 = tr_inner["FIN_A2"][3]
    u = np.array([math.cos(math.radians(a2["deg"])), math.sin(math.radians(a2["deg"]))]); vv = np.array([-u[1], u[0]])
    A = np.array(pol(f["r"], f["deg"])); Bp = 99.0 * u + (hw2 + T_W) * vv                                            # lane joins the trough wall at r 99 (inputs J1 / J2 at r 101.5)
    L = float(np.linalg.norm(Bp - A)); ang = math.degrees(math.atan2(*(Bp - A)[::-1])); LW = 2.0
    Bi = 99.0 * u + hw2 * vv; Li = float(np.linalg.norm(Bi - A)); angi = math.degrees(math.atan2(*(Bi - A)[::-1]))     # the lead runs on to the trough's inner face
    L, ang = Li, angi                                                                                                   # lane and lead share one axis (A -> trough inner face)
    lane_core = m3.Manifold.cube([L + 2.5, LW, WALL_TOP - zf1 + 2], True).translate([L / 2 - 1.0, 0, (zf1 + WALL_TOP) / 2]).rotate([0, 0, ang]).translate([A[0], A[1], 0])
    lane_out = m3.Manifold.cube([L + 2.5 + 2 * T_W, LW + 2 * T_W, WALL_TOP - zf1], True).translate([L / 2 - 1.0, 0, (zf1 + WALL_TOP) / 2]).rotate([0, 0, ang]).translate([A[0], A[1], 0])
    feed_box = at(cyl(f["hole_d"] / 2 + 0.6 + T_W, zf1, WALL_TOP, 48), tuple(A)) - at(cyl(f["hole_d"] / 2 + 0.6, zf1 - 1, WALL_TOP + 1, 48), tuple(A))
    trough_core = fin_frame_box(a2["deg"], tr_inner["FIN_A2"][1], tr_inner["FIN_A2"][2], -hw2, hw2, zf1 - 1, WALL_TOP + 1)
    lane = (lane_out + feed_box) - lane_core - at(cyl(f["hole_d"] / 2 + 0.6, zf1 - 1, WALL_TOP + 1, 48), tuple(A)) - trough_core
    F["prx_lane"] = lane
    port = m3.Manifold.cube([4.0, LW + 1.0, WALL_TOP - zf1 + 2], True).translate([L, 0, (zf1 + WALL_TOP) / 2]).rotate([0, 0, ang]).translate([A[0], A[1], 0])   # 3.0 mm port through the oblique trough wall
    F["prx_lane"] = lane = lane - port
    F["analog_troughs"] = F["analog_troughs"] - lane_core - port                                                       # opening where the lane meets the trough
    F["analog_trough_sides"] = F["analog_trough_sides"] - lane_core - port
    # stiffening ribs (digital sector, between the digital fins)
    dd = sorted(v["deg"] % 360 for v in fins.values() if v["zone"] == "digital"); ribs = []
    for a, b in zip(dd, dd[1:] + [dd[0] + 360]):
        mid = (a + b) / 2 % 360
        if b - a > 40 or zone_of(mid, 60) != "digital": continue
        ribs.append(radial_wall(mid, RIB["r"][0], RIB["r"][1], RIB["t"], zf1, zf1 + RIB["h"], dr))
    F["ribs"] = union(ribs)
    G["G_TRAY"] = union([F["floor"], F["channel_wall"], F["fin_rails"], F["hub"], F["sector_walls"], F["hv_island_walls"], F["analog_troughs"], F["prx_lane"], F["ribs"]])
    # --- G_COMBS (resin) and G_LID
    G["G_COMBS"] = P["COIL_COMBS"]
    gl = S["gland"]; pin = m3.Manifold.cylinder(gl["boss_d"] + 2, GLAND["pin_d"] / 2, GLAND["pin_d"] / 2, 24, True).rotate([90, 0, 0]).translate([0, 0, GLAND["pin_z"]]).rotate([0, 0, HEEL + 90]).translate([*gl["c"], 0])
    F["gland_pin_hole"] = pin
    G["G_LID"] = P["LID"] - pin
    G["G_GLAND_PIN"] = (m3.Manifold.cylinder(gl["boss_d"], GLAND["pin_d"] / 2 - 0.05, GLAND["pin_d"] / 2 - 0.05, 24, True).rotate([90, 0, 0]).translate([0, 0, GLAND["pin_z"]])
                        .rotate([0, 0, HEEL + 90]).translate([*gl["c"], 0])) - at(cyl(GLAND["curl_d"] / 2, 0, 30, 48), gl["c"])          # two stubs either side of the curled flex
    # --- components (what the glove holds)
    C = {k: P[k] for k in P if k.startswith(("BOARD_", "ENV_")) or k in ("LITZ", "SHIELD_COAT")}
    C["CORD_FLEX_CURL"] = at(cyl(GLAND["curl_d"] / 2, gl["boss_z"][0] - 2.0, sh["lid_z"][1] + 0.0, 48), gl["c"]) - at(cyl(GLAND["curl_d"] / 2 - 0.15, gl["boss_z"][0] - 3, sh["lid_z"][1] + 1, 48), gl["c"])
    C["CORD_FLEX_CURL"] = C["CORD_FLEX_CURL"] - box(gl["c"][0], gl["c"][1], 20, 20, GLAND["pin_z"] - GLAND["pin_d"] / 2 - 0.3, GLAND["pin_z"] + GLAND["pin_d"] / 2 + 0.3)   # the loop round the pin (not modeled): gap at the pin
    C["PRX_LEADS"] = m3.Manifold.cylinder(Li, 0.33, 0.33, 16).rotate([0, 90, 0]).translate([0, 0, zf1 + 0.4]).rotate([0, 0, angi]).translate([A[0], A[1], 0]) + \
                     at(cyl(0.33, S["boards"]["PRX"]["z"][1], zf1 + 0.73, 16), tuple(A))
    # --- potting solids: cavity up to the fill level minus every solid
    solids = union(list(G.values()) + list(C.values()))
    hv_cav = sector_prism(HV_DEG[0], HV_DEG[1], HV_R_IN, r_ep, zf1, FILL_Z)
    POT = {"POT_HV_EPOXY": hv_cav - solids}
    an = [fin_frame_box(dg, x0, x1, -hw, hw, zf1, FILL_Z) for dg, x0, x1, hw in tr_inner.values()]
    POT["POT_ANALOG_GEL"] = (union(an) + (lane_core ^ cyl(300, zf1, FILL_Z)) + at(cyl(f["hole_d"] / 2 + 0.6, zf1, FILL_Z, 48), tuple(A))) - solids
    chan = ring(rcw1, sc["r"][0], zf1, zc_top)
    POT["POT_COIL_FOAM"] = chan - solids
    info = dict(r_epoxy_max=r_ep, litz_inner_edge=round(litz_in, 3), lane=dict(from_xy=[round(float(x), 2) for x in A], to_xy=[round(float(x), 2) for x in Bp], length_mm=round(L, 1), width_mm=LW),
                troughs={k: dict(deg=d, r=[round(x0, 2), round(x1, 2)], half_width=round(hw, 2)) for k, (d, x0, x1, hw) in tr_inner.items()}, seconds=round(time.time() - t0, 1),
                litz_pass=dict(d=LITZ_PASS_D, z=zp, deg=[HEEL - 1.5, HEEL + 1.5], sleeve_od=LITZ_SLEEVE_OD, seal="RTV drop around each sleeve before potting (stated)"))
    return G, C, POT, F, P, info
# ------------------------------------------------------------------------------------------------ measurements
def min_feature(man, zs, tmax=4.0):
    """minimum wall: the largest t for which every connected piece of every horizontal slice survives an inward offset of t/2 (bisection)"""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    worst = (9e9, None)
    for z in zs:
        polys = man.slice(z).to_polygons()
        if not polys: continue
        rings = [Polygon(p) for p in polys if len(p) >= 3]
        g = None
        for r_ in sorted(rings, key=lambda q: -abs(q.area)):
            g = r_.buffer(0) if g is None else g.symmetric_difference(r_.buffer(0))
        if g is None or g.is_empty: continue
        pieces = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        for pc in pieces:
            if pc.area < 0.05: continue
            lo, hi = 0.0, tmax
            for _ in range(14):
                mid = (lo + hi) / 2; e = pc.buffer(-mid / 2, 8)
                ok = (not e.is_empty) and e.area > 1e-4
                lo, hi = (mid, hi) if ok else (lo, mid)
            if lo < worst[0]: worst = (lo, dict(z=round(z, 2), at=[round(pc.representative_point().x, 1), round(pc.representative_point().y, 1)]))
    return round(worst[0], 3), worst[1]
def step_from_stl(stl, step):
    """faceted STEP from the STL (sewn, coplanar facets merged: OCP StlAPI + UnifySameDomain)"""
    from OCP.StlAPI import StlAPI_Reader
    from OCP.TopoDS import TopoDS_Shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCP.TopoDS import TopoDS
    sh = TopoDS_Shape(); StlAPI_Reader().Read(sh, stl)
    try:
        u = ShapeUpgrade_UnifySameDomain(sh, True, True, False); u.Build(); sh = u.Shape()
    except Exception: pass
    w = STEPControl_Writer(); w.Transfer(sh, STEPControl_AsIs); w.Write(step); return os.path.getsize(step)
def lid_step(step):
    """the light plate as a B-rep (cadquery): plate, bosses, gland boss, the 522 conical wells and the pin hole. Exact surfaces: a compact STEP"""
    import cadquery as cq
    sh = S["shell"]; R = S["envelope"]["R"]; z0, z1 = sh["lid_z"]; ll = S["lid_light"]; lb = S["led_bosses"]; L = S["boards_inner"]["LED"]; gl = S["gland"]
    lid = cq.Workplane("XY").workplane(offset=z0).circle(R).extrude(z1 - z0)
    for p in H.boss_positions():
        lid = lid.union(cq.Workplane("XY").workplane(offset=L["z"][1]).center(*p).circle(lb["boss_d"] / 2).extrude(z0 - L["z"][1] + 0.01))
        lid = lid.union(cq.Workplane("XY").workplane(offset=L["z"][0]).center(*p).circle(lb["pin_d"] / 2).extrude(L["z"][1] - L["z"][0] + 0.01))
    lid = lid.union(cq.Workplane("XY").workplane(offset=gl["boss_z"][0]).center(*gl["c"]).circle(gl["boss_d"] / 2).extrude(z0 - gl["boss_z"][0] + 0.01))
    lid = lid.cut(cq.Workplane("XY").workplane(offset=gl["boss_z"][0] - 1).center(*gl["c"]).circle(gl["d"] / 2).extrude(z1 - gl["boss_z"][0] + 2))
    land = ll.get("land", 0.0); hw = z1 - z0 - land
    cone = cq.Solid.makeCone(ll["d_bottom"] / 2, ll["d_top"] / 2 + (ll["d_top"] - ll["d_bottom"]) / 2 / hw * 0.2, hw + 0.2, cq.Vector(0, 0, z0 + land))
    bore = cq.Solid.makeCylinder(ll["d_bottom"] / 2, land + 0.4, cq.Vector(0, 0, z0 - 0.2))
    tool = cone.fuse(bore)
    tools = [tool.translate(cq.Vector(x, y, 0)) for x, y in H.led_positions()]
    lid = lid.cut(cq.Workplane("XY").add(cq.Compound.makeCompound(tools)))
    c = gl["c"]; dx, dy = math.cos(math.radians(HEEL + 90)), math.sin(math.radians(HEEL + 90))
    pin = cq.Solid.makeCylinder(GLAND["pin_d"] / 2, gl["boss_d"] + 2, cq.Vector(c[0] - dx * (gl["boss_d"] / 2 + 1), c[1] - dy * (gl["boss_d"] / 2 + 1), GLAND["pin_z"]), cq.Vector(dx, dy, 0))
    lid = lid.cut(cq.Workplane("XY").add(pin))
    cq.exporters.export(lid, step); return os.path.getsize(step)
# ------------------------------------------------------------------------------------------------ renders
def render(G, C, POT, path_cut, path_exp, path_map, zrows):
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    import pyvista as pv
    def pvm(man):
        mm = man.to_mesh(); V = np.asarray(mm.vert_properties)[:, :3]; Fc = np.asarray(mm.tri_verts)
        return pv.PolyData(V, np.hstack([np.full((len(Fc), 1), 3), Fc]).ravel())
    col = dict(G_SHELL="#b0bec5", G_TRAY="#8d6e63", G_COMBS="#4e342e", G_LID="#37474f", G_GLAND_PIN="#ffca28", LITZ="#e67e22", BOARD_SH1="#c9a227", BOARD_PRX="#ab47bc",
               BOARD_QA="#2e7d32", BOARD_QB="#43a047", SHIELD_COAT="#212121", ENV_LED="#26c6da", CORD_FLEX_CURL="#fdd835", PRX_LEADS="#d500f9",
               POT_HV_EPOXY="#e53935", POT_ANALOG_GEL="#42a5f5", POT_COIL_FOAM="#fff59d")
    def c_of(k):
        if k in col: return col[k]
        if k.startswith("ENV_FIN_HV"): return "#c62828"
        if k == "ENV_FIN_A2": return "#7b1fa2"
        if k.startswith("ENV_FIN_A"): return "#1565c0"
        if k.startswith("ENV_"): return "#00897b"
        return "#90a4ae"
    # cut-away: remove the quadrant 90..225 deg (looking into the HV island, the analog troughs and the PRX feed) above z 0
    cutter = sector_prism(95.0, 215.0, 0.0, 130.0, -1, 30)
    pl = pv.Plotter(off_screen=True, window_size=(2600, 1800), lighting="three lights"); pl.set_background("#f6f7f9")
    allp = {**{k: v for k, v in G.items()}, **C, **POT}
    for k, m in allp.items():
        if k in ("G_LID", "ENV_LED"): m = m - sector_prism(60.0, 240.0, 0, 130, -1, 30)
        elif k in ("G_SHELL", "SHIELD_COAT", "POT_COIL_FOAM", "LITZ", "G_COMBS", "BOARD_SH1", "BOARD_PRX", "BOARD_QA", "BOARD_QB"): m = m - cutter
        if m.is_empty(): continue
        pl.add_mesh(pvm(m), color=c_of(k), opacity=0.55 if k.startswith("POT_") else 1.0, smooth_shading=False, specular=0.2, ambient=0.2)
    pl.camera.position = (-260, 300, 190); pl.camera.focal_point = (-40, 40, 6); pl.camera.up = (0, 0, 1); pl.camera.view_angle = 30
    pl.enable_anti_aliasing("ssaa")
    pl.add_text("AXE2 RF2 head, glove housing (variant BF + bank coil + PRX + MP2), cut-away 95-215 deg: HV epoxy island (red), analog gel troughs (blue), "
                "coil foam (yellow), MP2 fin (purple), PRX layer (violet). MODELED", position="lower_left", font_size=9, color="#1d2733")
    pl.screenshot(path_cut); pl.close()
    # exploded
    pl = pv.Plotter(off_screen=True, window_size=(2000, 2400), lighting="three lights"); pl.set_background("#f6f7f9")
    dz = dict(G_SHELL=0, BOARD_SH1=12, BOARD_PRX=24, BOARD_QA=36, BOARD_QB=48, G_TRAY=66, G_COMBS=86, LITZ=86, SHIELD_COAT=0, POT_COIL_FOAM=104, POT_HV_EPOXY=122, POT_ANALOG_GEL=122,
              ENV_LED=150, G_LID=172, G_GLAND_PIN=190, CORD_FLEX_CURL=190, PRX_LEADS=60, ENV_HUB_PCB=104)
    for k, m in allp.items():
        z = dz.get(k, 104)
        if m.is_empty(): continue
        pl.add_mesh(pvm(m.translate([0, 0, z])), color=c_of(k), opacity=0.7 if k.startswith("POT_") else 1.0, smooth_shading=False, specular=0.2, ambient=0.2)
    pl.camera.position = (-420, 520, 460); pl.camera.focal_point = (0, 0, 95); pl.camera.up = (0, 0, 1); pl.camera.view_angle = 30
    pl.enable_anti_aliasing("ssaa")
    pl.add_text("glove housing, exploded (z offsets): shell, SH1, PRX, QA, QB, tray, combs + litz, fins / hub, potting, display, lid, gland pin. MODELED", position="lower_left", font_size=9, color="#1d2733")
    pl.screenshot(path_exp); pl.close()
    # plan-view zone map (matplotlib)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge, Circle
    fig, ax = plt.subplots(figsize=(13, 13))
    zc = {"coil channel": "#ffe0b2", "HV island": "#ffcdd2", "HV sector (unpotted margin)": "#fce4ec", "analog": "#bbdefb", "digital": "#c8e6c9", "hub (centre)": "#e0e0e0"}
    ax.add_patch(Wedge((0, 0), 103.8, 0, 360, width=103.8 - 21, color=zc["digital"]))
    ax.add_patch(Wedge((0, 0), 103.8, *S["sectors"]["analog"], width=103.8 - 21, color=zc["analog"]))
    ax.add_patch(Wedge((0, 0), 103.8, *S["sectors"]["hv"], width=103.8 - 21, color=zc["HV sector (unpotted margin)"]))
    ax.add_patch(Wedge((0, 0), 103.8, *HV_DEG, width=103.8 - HV_R_IN, color=zc["HV island"]))
    ax.add_patch(Wedge((0, 0), 114.5, 0, 360, width=114.5 - 103.8, color=zc["coil channel"])); ax.add_patch(Circle((0, 0), 21, color=zc["hub (centre)"]))
    for k, m in {**G, **C, **POT}.items():
        if k in ("G_LID", "G_SHELL", "BOARD_SH1", "BOARD_QA", "BOARD_QB", "BOARD_PRX", "ENV_LED", "SHIELD_COAT"): continue
        from matplotlib.path import Path
        from matplotlib.patches import PathPatch
        polys = [np.asarray(p) for p in m.slice(8.0).to_polygons() if len(p) >= 3]
        if not polys: continue
        verts = np.vstack([np.vstack([p, p[:1]]) for p in polys]); codes = np.concatenate([[Path.MOVETO] + [Path.LINETO] * (len(p) - 1) + [Path.CLOSEPOLY] for p in polys])
        ax.add_patch(PathPatch(Path(verts, codes), fc=c_of(k), ec="none", alpha=0.45 if k.startswith("POT_") else 0.95))   # compound path: holes stay open (nonzero winding)
    f = S["prx"]["feed"]; fx, fy = pol(f["r"], f["deg"]); ax.plot(fx, fy, "o", color="#d500f9", ms=7); ax.text(fx + 3, fy, "PRX feed", fontsize=8, color="#6a1b9a")
    for r in (S["prx"]["main_r_mm"] + S["prx"]["buck_r_mm"]): ax.add_patch(Circle((0, 0), r, fill=False, ls=":", lw=0.6, color="#8e24aa"))
    for row in zrows:
        if row["r"] > 0 and row["part"].startswith("FIN"):
            x, y = pol(64.0, row["deg"]); ax.text(x, y, row["part"].replace("FIN_", ""), fontsize=7, ha="center", rotation=row["deg"] if abs(row["deg"] - 180) > 90 else row["deg"] - 180)
    for name, c in zc.items(): ax.plot([], [], "s", color=c, ms=12, label=name)
    ax.legend(loc="upper right", fontsize=8); ax.set_aspect("equal"); ax.set_xlim(-118, 118); ax.set_ylim(-118, 118)
    ax.set_title("RF2 head zone map (plan, cut at z 8.0): zones, glove walls, potting (translucent), PRX spirals (dotted), heel at 178 deg. MODELED", fontsize=9)
    fig.savefig(path_map, dpi=110, bbox_inches="tight"); plt.close(fig)
# ------------------------------------------------------------------------------------------------ main
def main():
    t0 = time.time(); sides = fin_side_envelopes()
    G, C, POT, F, P, info = build("printed")
    for k, m in {**G, **POT}.items(): write_stl(m, os.path.join(OUT, f"{k}.stl"))
    zrows = zone_map(P, sides)
    steps = {}
    for k in ("G_SHELL", "G_TRAY", "G_COMBS", "G_GLAND_PIN"):
        steps[k] = round(step_from_stl(os.path.join(OUT, f"{k}.stl"), os.path.join(OUT, f"{k}.step")) / 1e6, 2)
    try: steps["G_LID"] = round(lid_step(os.path.join(OUT, "G_LID.step")) / 1e6, 2)
    except Exception as e: steps["G_LID"] = f"B-rep export failed: {str(e)[:120]}"
    GM, _, POTM, FM, _, infoM = build("moulded")
    write_stl(GM["G_TRAY"], os.path.join(OUT, "G_TRAY_MOULDED.stl"))
    render(G, C, POT, os.path.join(OUT, "rf2_glove_cutaway.png"), os.path.join(OUT, "rf2_glove_exploded.png"), os.path.join(OUT, "rf2_glove_map.png"), zrows)
    json.dump(dict(status="MODELED glove housing geometry (rf2_head_glove.py); checks in rf2_head_glove_check.py", info=info, info_moulded=infoM, step_MB=steps, fin_sides=sides,
                   zone_map=zrows, process=PROC, seconds=round(time.time() - t0, 1)), open(os.path.join(OUT, "rf2_head_glove_geom.json"), "w"), indent=1)
    return G, C, POT, F, P, info, GM, POTM, FM, zrows, sides, steps
if __name__ == "__main__":
    r = main(); print("glove geometry written", OUT, "STEP MB", r[-1])
