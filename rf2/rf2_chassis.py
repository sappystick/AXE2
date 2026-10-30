#!/usr/bin/env python3
"""RF2 chassis v2: hinged telescopic chassis after the Minelab SDC 2300 pattern, with an INVERTED (top-mounted) control-stick grip (2026-10-30, owner). MODELED.
Every dimension is ASSUMED unless a datasheet is named. The SDC 2300 description the owner supplied is a REFERENCE for the mechanism (not a data source).
What maps over from the SDC pattern, and what changes in ours:
  - One CONTROL CHASSIS carries all electronics: the TX driver (moved off the shaft, as the SDC keeps its electronics in the box), the PWR board (regenerative
    return), HB2-M (MCU, piezo bridge, RS-485) and the battery cartridge underneath. This removes the TXD box from the shaft and the HV return pair up the shaft;
    the TX pair now runs head -> chassis in the coil cord (about 1 m: first-gate cost checked here).
  - MAIN HINGE under the chassis front: the shaft swings 180 deg back; the bundle passes through the hinge's hollow axis (two 90 deg bends + a 180 deg twist
    along the axial run). The GRIP slides 25 mm forward on a rail to lock the hinge (the SDC handle-lock), its FFC takes the slide in a service loop.
  - TELESCOPE: three nested carbon tubes (outer 28 / 25.4 on the hinge with the REF3 sleeve, middle 25 / 22.4, inner 22 / 19.6 with the yoke), two cam locks;
    the bundle is a coil cord inside the inner bore that stretches with the extension.
  - ARMREST GLIDE: the cuff rides twin rails on the chassis top; its two wings fold flat for storage.
  - YOKE KNUCKLE: pitch about the yoke pivot plus a 90 deg roll about the shaft for storage.
  - INVERTED GRIP (owner): a control stick standing on the chassis top in front of the cuff: pinky at its base, 3 finger wedges facing the head, raked 18 deg
    forward at the top, the pilot trigger under the grip head (index finger), the thumb button on top with its light ring, the flip-up screen behind the button,
    the dial on the thumb side; an FFC runs down the hollow grip to HB2-M. The forearm then lies on one straight line from the wrist to the cuff, above the
    chassis, and the battery is on the opposite (lower) side of the shaft.
Writes rf2/chassis_out/*.stl, rf2_chassis.step, rf2_chassis_check.json, rf2_chassis_views.png.   usage: python3 rf2/rf2_chassis.py"""
import os, sys, json, math, itertools, time
import numpy as np
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rf2_upper as U                                                          # frame, placement, sampling, timing and cache helpers (one source)
from rf2_upper import at, shaft_frame, place, rot_about, compose, apply, rbox, trsf, I3, P0, D, N, Y, LID_TOP, phase, TIMINGS, memo, samples
OUT = os.path.join(HERE, "chassis_out"); os.makedirs(OUT, exist_ok=True)
REF3 = json.load(open(os.path.join(HERE, "head", "out", "rf2_ref3.json")))["rect_sleeve"]            # rectangular profile layout (owner 2026-10-30)
SPEC = dict(tubes=dict(outer=(31.0, 31.0), mid=(26.0, 26.0), inner=(21.0, 21.0)), wall=1.5, corner_r=4.0, key=(3.0, 1.5),   # slim set (rf2_slim option A)                       # nested rectangular carbon profiles W x H (keyed telescope)
            st=dict(yoke=(0, 40), inner=(40, 420), C1=(300, 322), mid=(300, 680), C2=(410, 432), outer=(410, 790), REF3=(436, 786), hinge=(790, 816),
                    chassis=(800, 1160), TXD=(812, 902), bay=(905, 1065), rails=(1000, 1165)),
            collapse=dict(inner=255.0, mid=105.0), extend_max=dict(inner=20.0, mid=170.0), overlap_min=100.0,
            chassis=dict(n=(-15.0, 16.0), w=62.0, fillet=9.0),                                                          # slim chassis, boards on one level (rf2_slim)
            grip=dict(base_s=884.0, base_n=21.0, rake_deg=18.0, length=112.0, sections=[(0, 27, 21), (8, 22, 18.5), (40, 23.5, 19.5), (75, 23, 19.5), (112, 21, 18)],
                      grooves=[(20.0, 10.0, 3.0), (44.0, 10.5, 3.2), (68.0, 10.5, 3.2)], head=(44.0, 38.0, 30.0), slide=25.0, ffc_loop=60.0),
            trigger=dict(len=28.0, w=11.0, t=6.0, reach=70.0), button=dict(cap_d=12.0, ring_d=17.0, h=3.0), screen=dict(len=30.0, w=32.0, t=6.0, open_deg=60.0),
            dial=dict(d=15.0, t=6.0), cuff=dict(r_in=42.0, t=4.0, len=62.0, centre_s=1150.0, wing_deg=55.0, slide=70.0), forearm_r=40.0,
            rails=dict(d=8.0, y=35.0, n=0.0), cells=dict(d=18.6, l=65.2, n_s=7, n_p=2), cart_wall=3.0, bay_wall=2.5, bay_clear=0.6,
            ref3_outer=tuple(REF3["outer_mm"]), ref3_len=REF3["length_mm"], C_pair_pF_per_m=50.0, bend_min=10.0, twist_max_deg_per_mm=10.0, cord=dict(od=7.0, coil_od=17.0, stretch_max=4.0),
            eye=dict(above=600.0, behind=250.0), backpack=(520.0, 320.0, 210.0), sdc_folded=(400.0, 216.0), fold_gap=2.0)
def rrect(W, H, r): return cq.Workplane("XY").rect(H, W).extrude(1.0).edges("|Z").fillet(min(r, W / 2 - 0.1, H / 2 - 0.1)).faces(">Z").wires().toPending()
def rprof(W, H, s0, s1, wall=None, r=None, n=0.0, keys=False):
    """rectangular profile along the shaft: W lateral (Y), H along N; rounded corners; hollow by `wall`; keys=True cuts the keyway track (3 x 1.5 mm) along
    each side face: it carries the slide pads (keyed telescope, no twist) and seats the cord anchors and the clamp shoes"""
    wall = SPEC["wall"] if wall is None else wall; r = SPEC["corner_r"] if r is None else r; L = s1 - s0
    o = cq.Workplane("XY").rect(H, W).extrude(L).edges("|Z").fillet(min(r, H / 2 - 0.2, W / 2 - 0.2))
    i = cq.Workplane("XY").rect(H - 2 * wall, W - 2 * wall).extrude(L + 2).translate((0, 0, -1)).edges("|Z").fillet(max(0.5, min(r - wall, (H - 2 * wall) / 2 - 0.2, (W - 2 * wall) / 2 - 0.2)))
    o = o.cut(i)
    if keys:
        kw, kd = SPEC["key"]
        for sg in (1, -1): o = o.cut(cq.Workplane("XY").box(kw, 2 * kd, L + 2).translate((0, sg * W / 2, L / 2)))
    return shaft_frame(o.val(), s0, n)
def tube(W, H, s0, s1): return rprof(W, H, s0, s1)
def g_axis():
    rk = math.radians(SPEC["grip"]["rake_deg"]); up = math.cos(rk) * N - math.sin(rk) * D; front = -math.cos(rk) * D - math.sin(rk) * N      # base -> top; finger side (toward the head)
    return up, front
def build():
    s = SPEC; st = s["st"]; P = {}
    up_parts, _ = U.build()                                                        # reuse the head exterior from rf2_upper (skid, ears, envelope)
    for k in ("HEAD_SKID", "HEAD_EAR_L", "HEAD_EAR_R", "HEAD_ENVELOPE"): P[k] = ("HEAD", up_parts[k][1], up_parts[k][2])
    to, tm, ti = s["tubes"]["outer"], s["tubes"]["mid"], s["tubes"]["inner"]
    for sg in (1, -1):
        link = cq.Workplane("XY").box(18, 5, 30).translate((0, sg * 24.5, 15)).union(cq.Workplane("XZ").circle(9.0).extrude(2.5, both=True).translate((0, sg * 24.5, 0)))
        P[f"YOKE_CHEEK_{'L' if sg > 0 else 'R'}"] = ("LOW", shaft_frame(link.val(), 0.0), "yoke link: rounded r 9 end on the pivot (clears the lid 12 mm below at every pitch), up to the swivel")
    P["YOKE_SWIVEL"] = ("LOW", rprof(ti[0] + 10, ti[1] + 10, 18.0, st["yoke"][1] + 8, wall=5.0), "roll swivel collar (90 deg detents) on the inner profile")
    P["INNER_TUBE"] = ("LOW", rprof(*ti, *st["inner"], keys=True), "inner square carbon profile 21 x 21, 1.5 mm wall, keyway tracks (coil cord in the 18 x 18 bore)")
    P["MID_TUBE"] = ("MID", rprof(*tm, *st["mid"], keys=True), "middle profile 26 x 26, keyway tracks")
    P["CAMLOCK_1"] = ("MID", rprof(tm[0] + 7, tm[1] + 7, *st["C1"], wall=3.6), "flat lever clamp 1 (inner in middle)")
    P["OUTER_TUBE"] = ("UPT", tube(*to, *st["outer"]), "outer profile 31 x 31 on the hinge")
    P["CAMLOCK_2"] = ("UPT", rprof(s["ref3_outer"][0] + 4, s["ref3_outer"][1] + 4, *st["C2"], wall=(s["ref3_outer"][0] + 4 - to[0]) / 2), "flat lever clamp 2 (middle in outer)")
    ro = s["ref3_outer"]
    P["REF3_SLEEVE"] = ("UPT", rprof(ro[0], ro[1], *st["REF3"], wall=(ro[0] - to[0]) / 2 + 0.01, r=s["corner_r"] + 2),
                        f"REF3 in the outer profile: flat face-coil pairs (X, Y) + rectangular solenoid (Z) under a 1 mm cover, {ro[0]} x {ro[1]} mm (rf2_ref3 rect_sleeve)")
    h0, h1 = st["hinge"]
    P["HINGE_SHAFT_KNUCKLE"] = ("UPT", shaft_frame(rbox(30, 44, h1 - h0 - 1, 6).translate((-4, 0, (h1 - h0 - 1) / 2)), h0), "hinge knuckle on the outer tube (hollow axis carries the bundle)")
    c = s["chassis"]; c0, c1 = st["chassis"]
    body = rbox(c["n"][1] - c["n"][0], c["w"], c1 - c0, c["fillet"]).translate(((c["n"][0] + c["n"][1]) / 2, 0, (c1 - c0) / 2))
    P["CHASSIS"] = ("CH", shaft_frame(body, c0), "control chassis: TXD (front, vented), PWR board, HB2-M; battery bay below; rails and cuff above")
    P["HINGE_CHASSIS_LUGS"] = ("CH", shaft_frame(rbox(26, c["w"] - 6, 22, 5).translate((c["n"][0] - 8, 0, 11)), c0 - 4), "hinge lugs under the chassis front")
    # battery bay + cartridge under the chassis
    ce = s["cells"]; cw = s["cart_wall"]; Lc = ce["n_s"] * ce["d"] + 2 * cw; Wc = ce["l"] + 2 * cw; Hc = ce["n_p"] * ce["d"] + 4.0 + 2 * cw
    bw, bc = s["bay_wall"], s["bay_clear"]; b0, b1 = st["bay"]; Lb = Lc + 2 * bc + bw; Wb = Wc + 2 * bc + 2 * bw; Hb = Hc + 2 * bc + 2 * bw; n_bay = c["n"][0] + 1.0 - Hb / 2
    bay = rbox(Hb, Wb, Lb, 4.0).cut(cq.Workplane("XY").box(Hc + 2 * bc, Wc + 2 * bc, Lb).translate((0, 0, bw)).val())
    P["BATTERY_BAY"] = ("CH", shaft_frame(bay.translate((0, 0, Lb / 2)), b1 - Lb, n_bay), "battery bay under the chassis, open at the rear")
    P["BATTERY_CARTRIDGE"] = ("CH", shaft_frame(rbox(Hc, Wc, Lc, 3.0).translate((0, 0, Lc / 2)), b1 - Lc - bc, n_bay), "7S2P cartridge (BQ76952, MT60); slides out rearward")
    # inverted grip: loft along 'up', finger wedges on the front face
    gp = s["grip"]; up, front = g_axis(); base = at(gp["base_s"], gp["base_n"])
    w = cq.Workplane("XY")
    for k, (z, a, b) in enumerate(gp["sections"]): w = (w.ellipse(a, b) if k == 0 else w.workplane(offset=z - gp["sections"][k - 1][0]).ellipse(a, b))
    grip = w.loft(combine=True)
    for z, r, dep in gp["grooves"]:
        a_here = float(np.interp(z, [q[0] for q in gp["sections"]], [q[1] for q in gp["sections"]]))
        grip = grip.cut(cq.Workplane("XZ").circle(r).extrude(30, both=True).translate((a_here + r - dep, 0, z)))
    grip_solid = place(grip.val(), front, Y, up, base)
    grip = grip.cut(cq.Workplane("XY").circle(5.0).extrude(gp["length"] + 2).translate((0, 0, -1)))          # hollow core for the FFC
    P["GRIP"] = ("CH", place(grip.val(), front, Y, up, base), "inverted control-stick grip: 3 finger wedges toward the head, palm swell, FFC core; overmoulded TPE")
    hx, hy, hz = gp["head"]; top = base + up * gp["length"]
    ghead = rbox(hx, hy, hz, 8.0).translate((-4.0, 0, hz / 2))                      # local x = front, z = up
    P["GRIP_HEAD"] = ("CH", place(ghead, front, Y, up, top), "grip head: HB2-G (button, trigger switch, LEDs, dial switches, screen connector)")
    tg = s["trigger"]
    trig = cq.Workplane("XZ").moveTo(0, 0).threePointArc((5.0, -tg["len"] / 2), (1.0, -tg["len"])).lineTo(1.0 + tg["t"], -tg["len"]).threePointArc((5.0 + tg["t"], -tg["len"] / 2), (tg["t"], 0)).close().extrude(tg["w"] / 2, both=True).val()
    P["TRIGGER"] = ("CH", place(trig, front, Y, up, top + front * (hx / 2 - 4.0 + 1.0) + up * 6.0), "pilot trigger under the grip head front (index finger, pulled toward the palm)")
    bt = s["button"]; btn = cq.Workplane("XY").circle(bt["ring_d"] / 2).extrude(1.2).faces(">Z").workplane().circle(bt["cap_d"] / 2).extrude(bt["h"]).edges(">Z").fillet(1.5).val()
    P["BUTTON"] = ("CH", place(btn, front, Y, up, top + up * hz + front * 6.0), "thumb power button + light ring on top of the grip head")
    sc = s["screen"]; hinge_pt = top + up * hz - front * (hx / 2 - 4.0 + 4.0)
    scr = rbox(sc["len"], sc["w"], sc["t"], 2.0).translate((sc["len"] / 2, 0, sc["t"] / 2))
    P["SCREEN"] = ("CH", place(scr, front, Y, up, hinge_pt - front * 0.0), "flip-up screen hinged at the grip head's rear edge, above the thumb")
    dl = s["dial"]; P["DIAL"] = ("CH", place(cq.Workplane("XZ").circle(dl["d"] / 2).extrude(dl["t"]).val(), front, Y, up, top + up * (hz / 2) - Y * (hy / 2)), "3-position mode dial (thumb side)")
    # rails + cuff with folding wings
    r = s["rails"]; r0, r1 = st["rails"]
    for sg in (1, -1): P[f"RAIL_{'L' if sg > 0 else 'R'}"] = ("CH", shaft_frame(cq.Workplane("XY").circle(r["d"] / 2).extrude(r1 - r0).val(), r0, r["n"], sg * r["y"]), "armrest guide rail")
    cu = s["cuff"]; cs = cu["centre_s"]; cn = cuff_centre_n()
    trough = cq.Workplane("XY").circle(cu["r_in"] + cu["t"]).circle(cu["r_in"]).extrude(cu["len"]).cut(cq.Workplane("XY").box(200, 200, 400).translate((100 - cu["r_in"] * 0.25, 0, 0)))
    P["CUFF_TROUGH"] = ("CH", shaft_frame(trough.val(), cs - cu["len"] / 2, cn), "cuff trough (bottom 105 deg) on the rail slider")
    for sg in (1, -1):
        wing = cq.Workplane("XY").circle(cu["r_in"] + cu["t"]).circle(cu["r_in"]).extrude(cu["len"]).intersect(cq.Workplane("XY").box(200, 200, 400).translate((100 - cu["r_in"] * 0.25, sg * 100 + sg * 0.5, 0))).cut(
            cq.Workplane("XY").box(200, 200, 400).translate((100 + cu["r_in"] * 0.75, 0, 0)))
        P[f"CUFF_WING_{'L' if sg > 0 else 'R'}"] = ("CH", shaft_frame(wing.val(), cs - cu["len"] / 2, cn), "spring cuff wing (folds flat for storage)")
    nb = cn - cu["r_in"]; sl = cq.Workplane("XY").box(nb - 1.0 - (nb - 5.0), 2 * r["y"] + 6, 40).translate(((nb - 5.0 + nb - 1.0) / 2, 0, 20))          # bridge under the trough
    for sg in (1, -1): sl = sl.union(cq.Workplane("XY").box(nb - 1.0 - (r["n"] - 4.0), 5.0, 40).translate(((nb - 1.0 + r["n"] - 4.0) / 2, sg * (r["y"] + 0.5), 20)))
    P["CUFF_SLIDER"] = ("CH", shaft_frame(sl.val(), cs - 20), "U-slider riding the side rails, carrying the cuff over the chassis top")
    geo = dict(grip_solid=grip_solid, up=up, front=front, base=base, top=top, hinge_pt=hinge_pt, cart=(Lc, Wc, Hc), n_bay=n_bay, b1=b1, cuff_n=cn)
    return P, geo
def wrist_point():
    """the wrist when the hand holds the grip: about 34 mm up the grip axis and 38 mm behind its back face (ASSUMED)"""
    up, front = g_axis(); g = SPEC["grip"]; return at(g["base_s"], g["base_n"]) + up * 34.0 - front * 38.0
def cuff_centre_n():
    w = wrist_point() - P0; return float(w @ N)                                       # the forearm axis parallel to the shaft through the wrist: the cuff centre on it
def electronics(geo):
    s = SPEC; st = s["st"]; E = {}; c = s["chassis"]
    def box(lx_n, ly, lz, s0, n, y=0.0): return shaft_frame(cq.Workplane("XY").box(lx_n, ly, lz).translate((0, 0, lz / 2)).val(), s0, n, y)
    nf = c["n"][0] + 3.0
    for nm, (s0, l, w, h, y) in dict(TXD_BOARD=(st["TXD"][0], 86.0, 56.0, 1.6, 0.0)).items(): E[nm] = ("CHASSIS", box(h, w, l, s0, nf + h / 2, y))
    for nm, (s0, l, w, h, y) in dict(HS1_OHMITE_D2=(818.0, 30.9, 14.2, 12.7, -18.0), CB_BULK_3x3=(818.0, 31.0, 31.0, 10.2, 12.0), C1_CLAMP_FILM=(855.0, 26.0, 11.0, 18.0, 16.0),
                                     U1_UCC5350=(855.0, 5.0, 6.0, 1.75, -18.0), Q1_C3M=(853.0, 15.0, 10.2, 4.4, -6.0)).items():
        E[nm] = ("CHASSIS", box(h, w, l, s0, nf + 1.6 + h / 2, y))
    E["PWR_BOARD"] = ("CHASSIS", box(1.6, 56.0, 120.0, 1000.0, nf + 0.8))
    for nm, (s0, l, w, h, y) in dict(Q30_C3M=(1005.0, 15.0, 10.2, 4.4, -16.0), L30_IND=(1025.0, 12.0, 12.0, 8.0, -14.0), C30_FILM=(1045.0, 26.0, 11.0, 17.0, 14.0), U31_LMR36520=(1080.0, 4.0, 4.0, 1.0, 0.0)).items():
        E[nm] = ("CHASSIS", box(h, w, l, s0, nf + 1.6 + h / 2, y))
    E["HB2M_BOARD"] = ("CHASSIS", box(1.6, 50.0, 80.0, 910.0, c["n"][1] - 6.0))
    for nm, (s0, l, w, h, y) in dict(U20_MCU=(930.0, 7.0, 7.0, 0.9, -10.0), LS1_PIEZO=(960.0, 12.0, 12.0, 3.0, 14.0), AHCT_x4=(945.0, 6.0, 14.0, 1.45, 10.0), RS485_ESD=(975.0, 10.0, 8.0, 1.5, -12.0)).items():
        E[nm] = ("CHASSIS", box(h, w, l, s0, c["n"][1] - 6.0 - 0.8 - h / 2, y))
    up, front = geo["up"], geo["front"]; top = geo["top"]
    def gbox(lx, ly, lz, o): return place(cq.Workplane("XY").box(lx, ly, lz).translate((0, 0, lz / 2)).val(), front, Y, up, o)
    E["HB2G_BOARD"] = ("GRIP_HEAD", gbox(30.0, 26.0, 1.2, top + up * 12.0))
    E["SW_PWR"] = ("GRIP_HEAD", gbox(6.3, 6.2, 3.5, top + up * 13.2 + front * 6.0))
    E["SW_TRG"] = ("GRIP_HEAD", gbox(6.2, 6.3, 3.5, top + up * 4.0 + front * 10.0))
    E["FFC_12WAY"] = ("GRIP", gbox(6.0, 0.5, SPEC["grip"]["length"] - 4, geo["base"] + up * 2.0))
    ce = s["cells"]; Lc, Wc, Hc = geo["cart"]; cw = s["cart_wall"]; s_c0 = geo["b1"] - Lc - s["bay_clear"]; cells = []
    for i in range(ce["n_s"]):
        for j in range(ce["n_p"]):
            cells.append(shaft_frame(cq.Workplane("XZ").circle(ce["d"] / 2).extrude(ce["l"] / 2, both=True).val(), s_c0 + cw + ce["d"] / 2 + i * ce["d"], geo["n_bay"] - Hc / 2 + cw + ce["d"] / 2 + j * ce["d"]))
    E["CELLS_7S2P"] = ("BATTERY_CARTRIDGE", cq.Compound.makeCompound(cells))
    to = s["tubes"]["outer"]
    ro = s["ref3_outer"]; E["REF3_WINDINGS"] = ("REF3_SLEEVE", rprof(ro[0] - 2.0, ro[1] - 2.0, st["REF3"][0] + 3, st["REF3"][1] - 3, wall=(ro[0] - 2.0 - to[0]) / 2 - 0.1, r=s["corner_r"] + 1))
    return E
# ---------------------------------------------------------------- fold transforms
def T_tele():
    c = SPEC["collapse"]; return {"LOW": (np.eye(3), D * (c["inner"] + c["mid"])), "MID": (np.eye(3), D * c["mid"]), "UPT": I3}
def T_hinge(axis, side, o):
    h = at(sum(SPEC["st"]["hinge"]) / 2, SPEC["chassis"]["n"][0])
    return rot_about(h + side * o * N, Y, math.pi) if axis == "Y" else rot_about(h + side * o * Y, N, math.pi)
def T_head(pitch, roll):
    return compose(rot_about(P0, D, math.radians(roll)), rot_about(P0, Y, math.radians(pitch)))
def T_store_ch(P):
    """storage pose inside the chassis group: cuff slid forward on its rails, wings folded in (rotation about the trough's long edges)"""
    return {"CUFF": (np.eye(3), -D * SPEC["cuff"]["slide"])}
def groups_pts(P, spacing, grip_folded=False, store=True):
    out = {}
    for g_ in ("HEAD", "LOW", "MID", "UPT", "CH"):
        sh = [p[1] for k, p in P.items() if p[0] == g_ and k not in ("HEAD_EAR_L", "HEAD_EAR_R", "YOKE_CHEEK_L", "YOKE_CHEEK_R")]
        if g_ == "CH" and store:
            sh = [p[1].moved(trsf(np.eye(3), -D * SPEC["cuff"]["slide"])) if k.startswith("CUFF") else p[1] for k, p in P.items() if p[0] == "CH"]
            if grip_folded:
                R, t = grip_fold_T(grip_folded); sh = [x.moved(trsf(R, t)) if k in ("GRIP", "GRIP_HEAD", "TRIGGER", "BUTTON", "SCREEN", "DIAL") else x for x, k in zip(sh, [k for k, p in P.items() if p[0] == "CH"])]
        out[g_] = samples(cq.Compound.makeCompound(sh), spacing)
    return out
def P_grip_pivot(): return at(SPEC["grip"]["base_s"], SPEC["grip"]["base_n"])
def grip_fold_T(mode):
    """grip storage: 'forward' folds 75 deg toward the head about a lateral pivot at its base; 'side' lays it 90 deg sideways about a pivot along the shaft
    at the chassis top edge, so it lies along the chassis side inside the chassis length"""
    if mode in (True, "forward"): return rot_about(P_grip_pivot(), Y, -math.radians(75.0))
    edge = at(SPEC["grip"]["base_s"], SPEC["grip"]["base_n"], SPEC["chassis"]["w"] / 2 + 2.0); return rot_about(edge, D, math.radians(90.0))
def fold_search(gp, spacing):
    from scipy.spatial import cKDTree
    t0 = time.time(); gap = SPEC["fold_gap"] + spacing / 2; ev = [0]
    def tf(Pts, T): return Pts @ T[0].T + T[1]
    def clear(A, B, tree=None):
        ev[0] += 1
        if np.any(A.min(0) - B.max(0) > gap) or np.any(B.min(0) - A.max(0) > gap): return True
        d, _ = (tree or cKDTree(B)).query(A, k=1, distance_upper_bound=gap); return bool(np.all(np.isinf(d)))
    TT = T_tele(); shaft = np.vstack([tf(gp["LOW"], TT["LOW"]), tf(gp["MID"], TT["MID"]), gp["UPT"]]); CH = gp["CH"]; tree_ch = cKDTree(CH)
    head0 = gp["HEAD"]; M = np.column_stack([D, N, Y]); best = None; log = []
    for axis, side in itertools.product(("Y", "N"), (1, -1)):
        lo, hi = 10.0, 160.0
        if not clear(tf(shaft, T_hinge(axis, side, hi)), CH, tree_ch): continue
        while hi - lo > 2.0:
            mid = (lo + hi) / 2
            if clear(tf(shaft, T_hinge(axis, side, mid)), CH, tree_ch): hi = mid
            else: lo = mid
        Th = T_hinge(axis, side, hi); SH = tf(shaft, Th); tree_sh = cKDTree(SH)
        for pitch in range(-180, 180, 15):
            for roll in (0, 90, -90):
                Thd = compose(Th, compose(TT["LOW"], T_head(pitch, roll))); HD = tf(head0, Thd)
                if not (clear(HD, CH, tree_ch) and clear(HD, SH, tree_sh)): continue
                Q = np.vstack([HD, SH, CH]) @ M; ext = sorted((Q.max(0) - Q.min(0)).tolist(), reverse=True); vol = float(np.prod(ext))
                row = dict(hinge=dict(axis=axis, side=side, offset_mm=round(hi, 1)), head_pitch=pitch, head_roll=roll, package_mm=[round(x) for x in ext]); log.append((vol, row))
                fits = all(a <= b for a, b in zip(ext, sorted(SPEC["backpack"], reverse=True))); row["fits_backpack"] = fits
                key = (0 if fits else 1, vol)
                if best is None or key < best[0]: best = (key, row)
    out = dict(best[1]) if best else dict(hinge=None, package_mm=[9999] * 3)
    out.update(evaluations=ev[0], search_s=round(time.time() - t0, 1), top3=[r for _, r in sorted(log, key=lambda x: (0 if x[1]["fits_backpack"] else 1, x[0]))[:3]]); return out
@memo("geom.chassis.fold", uses=[build, fold_search, groups_pts, T_tele, T_hinge, T_head, samples, U.build, SPEC, U.SPEC])
def fold_cached(grip_folded=False, spacing=2.0):
    P, geo = build(); gp = groups_pts(P, spacing, grip_folded); print("[fold] samples:", {k: len(v) for k, v in gp.items()}, "grip folded" if grip_folded else "", flush=True)
    return fold_search(gp, spacing)
# ---------------------------------------------------------------- checks
def main():
    t0 = time.time(); TIMINGS.clear(); s = SPEC; res = dict(status="MODELED; dimensions ASSUMED unless a datasheet is named; SDC 2300 used as a mechanism reference only", checks={})
    with phase("build"): P, geo = build(); E = electronics(geo)
    c = res["checks"]
    with phase("containment"):
        cont = {nm: round(sh.cut(geo["grip_solid"] if h == "GRIP" else P[h][1]).Volume(), 2) for nm, (h, sh) in E.items()}
    c["electronics inside their housings"] = dict(ok=max(cont.values()) < 1.0, outside_mm3={k: v for k, v in cont.items() if v >= 1.0})
    # inverted grip ergonomics + straight forearm line
    up, front = g_axis(); w = wrist_point(); cu = s["cuff"]; cuff_c = at(cu["centre_s"], geo["cuff_n"])
    fa = cuff_c - w; ang = math.degrees(math.acos(float(fa @ D) / np.linalg.norm(fa)))
    trough_bottom_n = geo["cuff_n"] - cu["r_in"]; chassis_top = s["chassis"]["n"][1]
    c["forearm_straight_in_cuff"] = dict(ok=ang <= 3.0 and trough_bottom_n >= chassis_top, wrist_to_cuff_angle_to_shaft_deg=round(ang, 2), forearm_length_mm=round(float(np.linalg.norm(fa))),
                                         cuff_centre_n_mm=round(geo["cuff_n"], 1), trough_bottom_above_chassis_mm=round(trough_bottom_n - chassis_top, 1),
                                         note="the forearm axis runs from the wrist (on the grip) straight back to the cuff centre, parallel to the shaft and above the chassis")
    gp = s["grip"]; pitch = np.diff([q[0] for q in gp["grooves"]])
    c["grip"] = dict(ok=gp["length"] >= 105 and all(21 <= p <= 26 for p in pitch), length_mm=gp["length"], groove_pitch_mm=pitch.tolist(), rake_deg=gp["rake_deg"], trigger_reach_mm=s["trigger"]["reach"],
                     note="inverted control stick: pinky at the base on the chassis, index on the trigger under the grip head, thumb on top")
    eye = geo["top"] + np.array([s["eye"]["behind"], 0, s["eye"]["above"]])
    angs = {}
    for sg in (1, -1):
        R, t = rot_about(geo["hinge_pt"], Y, sg * math.radians(s["screen"]["open_deg"])); n_open = R @ up; cpt = R @ (geo["hinge_pt"] - front * 15.0 + up * 3.0) + t; v = eye - cpt
        angs[sg] = math.degrees(math.acos(float(n_open @ v) / np.linalg.norm(v)))
    best_sg = min(angs, key=angs.get)
    c["screen_view"] = dict(ok=angs[best_sg] <= 25.0, angle_to_eye_deg=round(angs[best_sg], 1), open_deg=s["screen"]["open_deg"], opens=("lifting its front edge" if best_sg > 0 else "lifting its rear edge"))
    # telescope, REF3 distance, cable
    st = s["st"]; ext = s["extend_max"]; nominal = st["hinge"][0]; Lmin, Lmax = nominal - 100.0, nominal + ext["inner"] + ext["mid"]
    ref_c = (st["REF3"][0] + st["REF3"][1]) / 2; ref_min = ref_c - 100.0
    over_inner = st["inner"][1] - st["mid"][0] - ext["inner"]; over_mid = st["mid"][1] - st["outer"][0] - ext["mid"]
    c["telescope"] = dict(ok=over_inner >= s["overlap_min"] and over_mid >= s["overlap_min"] and ref_min >= 500.0, pivot_to_hinge_mm=dict(min_use=Lmin, nominal=nominal, max=Lmax),
                          collapsed_mm=nominal - s["collapse"]["inner"] - s["collapse"]["mid"], overlap_at_full_mm=dict(inner=over_inner, mid=over_mid), REF3_from_pivot_at_min_use_mm=ref_min)
    stretch = (Lmax - (nominal - s["collapse"]["inner"] - s["collapse"]["mid"])); cord = s["cord"]; comp_len = 160.0
    bore = min(s["tubes"]["inner"]) - 2 * s["wall"]
    c["coil_cord"] = dict(ok=cord["coil_od"] <= bore - 1.0 and (comp_len + stretch) / comp_len <= cord["stretch_max"] + 1, stretch_mm=round(stretch), coil_od_mm=cord["coil_od"], inner_bore_min_mm=bore,
                          stretch_ratio=round((comp_len + stretch) / comp_len, 2), note="coil cord (TX pair, VIN / GND, DATA, TXCMD / TXSTAT, 3 REF pairs; OD 7 mm ASSUMED) coiled 17 mm OD inside the inner bore; 160 mm compressed")
    run = 30.0; twist = 180.0 / run
    c["hinge_pass_through"] = dict(ok=twist <= s["twist_max_deg_per_mm"] and 12.0 >= s["bend_min"], axial_run_mm=run, twist_deg_per_mm=round(twist, 1), bend_r_mm=12.0,
                                   note="the bundle enters the hollow hinge axis with a 12 mm-radius 90 deg bend, twists 180 deg along a 30 mm axial run, leaves with a second 90 deg bend")
    L_pair = (Lmax + 120.0) / 1000.0; dC = s["C_pair_pF_per_m"] * L_pair * 1e-12
    try:
        tc = json.load(open(os.path.join(HERE, "results", "rf2_timing_cord.json"))); dg = max(v["shift_fixed_us"] for v in tc["cases"].values()); src = "rf2_timing_cord (nonlinear turn-off, Rd kept at the no-cord value)"
    except Exception: dg = (16.3 - 5.8) * (math.sqrt(1 + dC / 500e-12) - 1); src = "first-order (rf2_timing_cord not run)"
    c["tx_pair_in_cord"] = dict(ok=dg <= 0.6, length_m=round(L_pair, 2), C_pF=round(dC * 1e12, 1), first_gate_shift_us=round(dg, 3), source=src, note="TX in the chassis: the pair runs the whole shaft (50 pF/m ASSUMED)")
    Lc, Wc, Hc = geo["cart"]; cart = P["BATTERY_CARTRIDGE"][1]; hits = set()
    for dz in np.linspace(10, Lc + 10, 8):
        mv = cart.moved(trsf(np.eye(3), D * dz)); hits |= {k for k, p in P.items() if p[0] == "CH" and k not in ("BATTERY_CARTRIDGE", "BATTERY_BAY", "CHASSIS") and mv.distance(p[1]) < 0.3}
    c["battery_slide"] = dict(ok=not hits, hits=sorted(hits), cartridge_mm=[round(v, 1) for v in (Lc, Wc, Hc)])
    ffc = s["grip"]; c["grip_slide_lock"] = dict(ok=ffc["ffc_loop"] >= 2 * ffc["slide"], slide_mm=ffc["slide"], ffc_service_loop_mm=ffc["ffc_loop"], note="grip slides forward 25 mm to lock the hinge (SDC handle-lock); FFC loop >= 2 x travel")
    # folding
    with phase("fold search (cached)"):
        f0 = fold_cached(False); f1 = fold_cached("forward"); f2 = fold_cached("side")
    bp = sorted(s["backpack"], reverse=True)
    def fits(f): return f.get("hinge") is not None and all(a <= b for a, b in zip(sorted(f["package_mm"], reverse=True), bp))
    for f, m in ((f0, None), (f1, "forward"), (f2, "side")): f["grip_mode"] = m
    res["fold"] = dict(grip_fixed=f0, grip_folded_forward=f1, grip_folded_side=f2, sdc2300_reference_mm=s["sdc_folded"], backpack_ASSUMED_mm=bp)
    best = min((f for f in (f0, f1, f2) if f.get("hinge")), key=lambda f: (0 if fits(f) else 1, np.prod(f["package_mm"])), default=None)
    res["fold"]["chosen"] = best
    c["folds_to_backpack"] = dict(ok=best is not None and fits(best), grip_fixed_mm=f0["package_mm"], grip_forward_mm=f1["package_mm"], grip_side_mm=f2["package_mm"], target_mm=bp, sdc2300_folded_mm=s["sdc_folded"])
    with phase("deployed clearance"):
        G = {g_: cq.Compound.makeCompound([p[1] for k, p in P.items() if p[0] == g_ and k not in ("HEAD_EAR_L", "HEAD_EAR_R", "YOKE_CHEEK_L", "YOKE_CHEEK_R")]) for g_ in ("HEAD", "LOW", "MID", "UPT", "CH")}
        dep = {"HEAD-UPT": round(G["HEAD"].distance(G["UPT"]), 1), "HEAD-CH": round(G["HEAD"].distance(G["CH"]), 1), "LOW-CH": round(G["LOW"].distance(G["CH"]), 1)}
    c["deployed_clear"] = dict(ok=min(dep.values()) >= 2.0, min_gaps_mm=dep)
    # mass and torque about the hand
    ref_cu = REF3["copper_g_total"]
    masses = {"head (ASSUMED 650 g)": (650.0, np.array([0, 0, 8.0])), "rect profiles + yoke + clamps (CF, ASSUMED 330 g)": (330.0, at(420)), f"REF3 rect coils ({ref_cu} g Cu + 30 g)": (ref_cu + 30.0, at(ref_c)),
              "chassis shell + hinge + TXD + PWR + HB2 (ASSUMED 420 g)": (420.0, at(960)), "grip + head + screen (ASSUMED 120 g)": (120.0, geo["base"] + up * 60), "cuff + rails (ASSUMED 110 g)": (110.0, at(1140, 60)),
              "battery cartridge (14 x 47 g + 90 g)": (748.0, at(985, geo["n_bay"]))}
    hand = geo["base"] + up * 50.0
    tq = sum(m * 9.81e-3 * (hand[0] - p[0]) * 1e-3 for m, p in masses.values()); tot = sum(m for m, _ in masses.values())
    res["mass"] = dict(items_g={k: round(m) for k, (m, _) in masses.items()}, total_g=round(tot), torque_about_hand_Nm=round(tq, 2), sdc2300_reference_g=2300)
    for v in c.values(): v["ok"] = bool(v["ok"])
    res["ok"] = bool(all(v["ok"] for v in c.values()))
    with phase("exports and views"): export(P, E, geo, best)
    res["timings_s"] = dict(TIMINGS, total=round(time.time() - t0, 1))
    json.dump(res, open(os.path.join(OUT, "rf2_chassis_check.json"), "w"), indent=1, default=float)
    print(json.dumps({k: v["ok"] for k, v in c.items()}, indent=1)); print("fold:", f0.get("package_mm"), f1.get("package_mm"), f2.get("package_mm"), "mass", res["mass"]["total_g"], "torque", res["mass"]["torque_about_hand_Nm"]); print("timings", res["timings_s"])
    return res
def to_head_frame(sh): return U.to_head_frame(sh)
def export(P, E, geo, best):
    for k, (g_, sh, _) in P.items():
        if k != "HEAD_ENVELOPE": cq.exporters.export(to_head_frame(sh), os.path.join(OUT, f"{k}.stl"))
    asm = cq.Assembly(name="RF2_CHASSIS")
    for k, (g_, sh, _) in P.items():
        if k != "HEAD_ENVELOPE": asm.add(to_head_frame(sh), name=k)
    for k, (h, sh) in E.items(): asm.add(to_head_frame(sh), name="E_" + k, color=cq.Color(0.9, 0.7, 0.2))
    asm.export(os.path.join(OUT, "rf2_chassis.step"))
    views(P, E, geo, best)
def views(P, E, geo, best):
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true"); import pyvista as pv
    def pvm(sh, tol=0.6):
        v, t = sh.tessellate(tol); V = np.array([[q.x, q.y, q.z] for q in v]); return pv.PolyData(V, np.hstack([np.full((len(t), 1), 3), np.array(t)]).ravel())
    def tfm(m, T):
        m = m.copy(); m.points = (T[0] @ np.asarray(m.points).T).T + T[1]; return m
    Rh = np.array([[math.cos(math.radians(-U.HEEL)), -math.sin(math.radians(-U.HEEL)), 0], [math.sin(math.radians(-U.HEEL)), math.cos(math.radians(-U.HEEL)), 0], [0, 0, 1]])
    heads = []
    for path in (U.SPEC["head_shell"], U.SPEC["head_lid"]):
        m = pv.read(path); m.points = (Rh @ np.asarray(m.points).T).T; heads.append(m)
    col = dict(HEAD="#b8c2ca", LOW="#2b2b2b", MID="#3a3a3a", UPT="#2b2b2b", CH="#2f6db5")
    def colour(k, g_): return "#8e44ad" if k.startswith("REF3") else "#e67e22" if k in ("TRIGGER", "BUTTON") else "#1abc9c" if k == "SCREEN" else "#7f8c8d" if k == "BATTERY_CARTRIDGE" else "#555555" if k.startswith(("CAMLOCK", "HINGE", "RAIL")) else col[g_]
    pl = pv.Plotter(shape=(2, 2), off_screen=True, window_size=(1800, 1200), lighting="three lights")
    TT = T_tele()
    fold_T = None
    if best and best.get("hinge"):
        h = best["hinge"]; Th = T_hinge(h["axis"], h["side"], h["offset_mm"])
        fold_T = {"HEAD": compose(Th, compose(TT["LOW"], T_head(best["head_pitch"], best["head_roll"]))), "LOW": compose(Th, TT["LOW"]), "MID": compose(Th, TT["MID"]), "UPT": Th, "CH": I3}
    for idx, (title, state) in enumerate((("deployed: side (inverted grip, straight forearm line to the cuff)", "dep"), ("deployed: 3/4", "dep3"), ("folded (SDC-style: telescoped, hinged, head stowed)", "fold"), ("chassis: shells transparent, electronics placed", "up"))):
        pl.subplot(idx // 2, idx % 2); pl.set_background("#f6f7f9"); pl.add_text(title, font_size=10)
        T = {g_: I3 for g_ in col} if state != "fold" or fold_T is None else fold_T
        for k, (g_, sh, _) in P.items():
            if k == "HEAD_ENVELOPE" or (state == "up" and g_ != "CH"): continue
            shp = sh
            if state == "fold" and k.startswith("CUFF"): shp = sh.moved(trsf(np.eye(3), -D * SPEC["cuff"]["slide"]))
            if state == "fold" and best and best.get("grip_mode") and k in ("GRIP", "GRIP_HEAD", "TRIGGER", "BUTTON", "SCREEN", "DIAL"): shp = shp.moved(trsf(*grip_fold_T(best["grip_mode"])))
            pl.add_mesh(tfm(pvm(shp), T[g_]), color=colour(k, g_), opacity=0.25 if state == "up" and k in ("CHASSIS", "GRIP", "GRIP_HEAD", "BATTERY_BAY", "BATTERY_CARTRIDGE") else 1.0, smooth_shading=True)
        if state != "up":
            for m in heads: pl.add_mesh(tfm(m, T["HEAD"]), color="#d5dde3", smooth_shading=True)
        else:
            for k, (h, sh) in E.items():
                if P[h][0] == "CH": pl.add_mesh(pvm(sh, 1.0), color="#f1c40f" if not k.startswith("CELLS") else "#95a5a6")
        pl.reset_camera(); cf = np.array(pl.camera.focal_point); dist = np.linalg.norm(np.array(pl.camera.position) - cf)
        if state == "dep": pl.camera.position = tuple(cf - Y * dist); pl.camera.up = (0, 0, 1)
        elif state == "fold": pl.camera.position = tuple(cf + (0.8 * N + 0.45 * Y - 0.4 * D) / np.linalg.norm(0.8 * N + 0.45 * Y - 0.4 * D) * dist); pl.camera.up = tuple(D)
        elif state == "up": pl.camera.position = tuple(cf - Y * dist + N * 0.3 * dist); pl.camera.up = tuple(N)
        else: pl.view_isometric()
        pl.reset_camera(); pl.camera.zoom(1.3 if state == "dep" else 1.2)
    pl.screenshot(os.path.join(OUT, "rf2_chassis_views.png")); pl.close()
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
