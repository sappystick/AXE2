#!/usr/bin/env python3
"""SUPERSEDED 2026-10-30 by rf2/rf2_chassis.py (SDC-style chassis v2); kept as a helper module (frame, placement, sampling, cache) and as the v1 record.
RF2 upper assembly and shaft (2026-10-30, owner: modern ergonomic grip with finger wedges, a fighter-pilot trigger, a thumb power button, a flip-up screen above
the thumb, an elbow cuff angled up from the shaft with the quick-swap battery under it, folding / telescoping to backpack size; outside of the head).
MODELED. Every dimension is ASSUMED unless a datasheet is named; anthropometric targets are typical adult values (ASSUMED, not from a survey on file).
Replaces the v1 / v2 cylindrical pod (head/rf2_pod.py, retired from the runner).

Frame: the head frame (mm, z up from the skid underside); the assembly is built in the heel's sagittal plane (X outward over the heel, Y lateral, Z up) and
rotated to the heel azimuth 178 deg. The shaft leaves the YOKE PIVOT P0 (r 85 at the heel, 12 mm above the lid) at TILT from vertical; s = distance along it.
Stations (s, mm):  yoke 0-40 | L1 lower segment 40-420 (TXD housing 255-345 beside it) | F1 fold hinge 420-450 | L2 middle segment 450-850 (REF3 housing 544-656;
  inner telescoping tube 0-250 mm travel) | F2 fold hinge 850-880 | UPPER UNIT 880-1260: neck, grip head 895-975 (thumb button, flip-up screen, mode dial,
  trigger), pistol grip under it (3 finger wedges + pinky shelf, 18 deg rake), spine 975-1205 (PWR board), cuff stem and cuff 1200-1260, battery bay under the
  spine 1050-1205 with a cartridge that slides out rearward.
Folding: the head turns about the yoke pivot; L2 folds 180 deg at F1; the upper unit folds 180 deg at F2. Hinge axis, side and offset are chosen by a search
for the smallest collision-free package (>= 2 mm between groups). The cable bundle runs inside the tubes with a service loop through each hinge and a coil in L2.
Writes rf2/upper_out/*.stl, rf2_upper_assembly.step, rf2_upper_check.json, rf2_upper_views.png.   usage: python3 rf2/rf2_upper.py"""
import os, sys, json, math, itertools, time
import numpy as np
import cadquery as cq
from OCP.gp import gp_Trsf
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "upper_out"); os.makedirs(OUT, exist_ok=True)
HEEL = 178.0
SPEC = dict(tilt_deg=50.0, pivot_r=85.0, pivot_above_lid=12.0, head_shell=os.path.join(HERE, "head", "out_BF", "RF2_SHELL_LOWER.stl"), head_lid=os.path.join(HERE, "head", "out_BF", "RF2_LID.stl"),
            head_r=116.5, skid_t=1.5, ear=dict(y=(16.0, 21.0), r=(76.0, 96.0)), cheek=dict(y=(22.0, 27.0)), pin_d=6.0,
            tube=dict(od=25.0, id=22.4), tele=dict(od=22.0, id=19.6, travel=250.0, overlap_min=150.0),
            st=dict(yoke=(0, 40), L1=(40, 420), TXD=(330, 420), F1=(420, 450), L2=(450, 850), REF3=(470, 820), lock=(820, 850), F2=(850, 880), neck=(880, 895), GH=(895, 975),
                    spine=(975, 1205), bay=(1050, 1205), cuff=(1200, 1262)),
            txd=dict(size=(90.0, 34.0, 30.0), lat=29.0, fillet=6.0), ref3=dict(sleeve_od=33.8, winding_r=(13.0, 15.9), note="rf2_ref3 sleeve layout: X/Y saddle pairs + Z solenoid on the tube, 1 mm cover"),
            gh=dict(n=(-22.0, 24.0), w=40.0, fillet=9.0), grip=dict(top_s=948.0, rake_deg=18.0, length=118.0, sections=[(0, 21, 18), (30, 23, 19.5), (65, 23.5, 19.5), (100, 22, 18.5), (118, 27, 21)],
            grooves=[(22.0, 10.5, 3.2), (47.0, 10.5, 3.2), (71.0, 10.0, 3.0)], pinky_shelf=(110.0, 118.0)),
            trigger=dict(s=914.0, len=30.0, w=11.0, t=6.0, travel_deg=10.0, reach_from_backstrap=70.0), guard=dict(s=(900.0, 940.0), depth=40.0, t=5.0),
            button=dict(s=936.0, cap_d=12.0, ring_d=17.0, height=3.0), screen=dict(s=(944.0, 975.0), w=32.0, t=6.0, open_deg=60.0, hinge_s=975.0),
            dial=dict(s=922.0, d=15.0, t=6.0, n=8.0), spine=dict(w=34.0, h=26.0, wall=2.5), cuff=dict(r_in=46.0, t=4.0, arc_deg=210.0, centre_n=62.0, stem_angle=20.0),
            cells=dict(d=18.6, l=65.2, n_s=7, n_p=2), cart_wall=3.0, bay_wall=2.5, bay_clear=0.6,
            eye=dict(above=600.0, behind=250.0), backpack=(520.0, 320.0, 210.0), fold_gap=2.0, bend_r_min=15.0)
TILT = math.radians(SPEC["tilt_deg"])
try: LID_TOP = float(json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_spec.json")))["shell"]["lid_z"][1])   # rf2_head option-B lid top (generated)
except Exception: LID_TOP = 15.65
P0 = np.array([SPEC["pivot_r"], 0.0, LID_TOP + SPEC["pivot_above_lid"]])        # sagittal frame
D = np.array([math.sin(TILT), 0.0, math.cos(TILT)]); Y = np.array([0.0, 1.0, 0.0]); N = np.cross(D, Y) * -1.0         # N: perpendicular to the shaft, 'up' (toward +Z)
if N[2] < 0: N = -N
def at(s, n=0.0, y=0.0): return P0 + s * D + n * N + y * Y
def trsf(R, t):
    T = gp_Trsf(); T.SetValues(*(list(R[0]) + [t[0]] + list(R[1]) + [t[1]] + list(R[2]) + [t[2]])); return cq.Location(T)
def place(sh, X, Yv, Z, o):
    """rigid placement; the frame is forced right-handed (a mirrored frame turns solids inside out: negative volume, zero distances)"""
    if np.linalg.det(np.column_stack([X, Yv, Z])) < 0: Yv = -np.asarray(Yv)
    return sh.moved(trsf(np.column_stack([X, Yv, Z]), o))
def shaft_frame(sh, s0, n=0.0, y=0.0): return place(sh, N, Y, D, at(s0, n, y))                 # local x = N, y = Y, z = along the shaft
def tube(od, idd, s0, s1, n=0.0, y=0.0):
    return shaft_frame(cq.Workplane("XY").circle(od / 2).circle(idd / 2).extrude(s1 - s0).val(), s0, n, y)
def rbox(lx, ly, lz, f):
    w = cq.Workplane("XY").box(lx, ly, lz)
    try: return w.edges().fillet(f).val()
    except Exception: return w.val()
def rot_about(axis_pt, axis_dir, ang):
    a = np.asarray(axis_dir, float); a /= np.linalg.norm(a); c, s = math.cos(ang), math.sin(ang); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    R = np.eye(3) + s * K + (1 - c) * K @ K; t = np.asarray(axis_pt) - R @ np.asarray(axis_pt); return R, t
def compose(A, B):                                                                  # A after B
    return A[0] @ B[0], A[0] @ B[1] + A[1]
def apply(sh, T): return sh.moved(trsf(T[0], T[1]))
I3 = (np.eye(3), np.zeros(3))
# ---------------------------------------------------------------- parts
def stl_solid(path):
    import trimesh
    m = trimesh.load(path); v, f = m.vertices, m.faces
    return v, f
def build():
    s = SPEC; st = s["st"]; parts = {}                                             # name -> (group, solid, role)
    # head exterior: wear skid (new) and yoke ears; the shells themselves come from rf2_head (out_BF) and are added to renders / bounds as meshes
    skid = cq.Workplane("XY").circle(s["head_r"] - 0.5).extrude(s["skid_t"]).translate((0, 0, -s["skid_t"])).edges(">Z or <Z").chamfer(0.6).val()
    parts["HEAD_SKID"] = ("HEAD", skid, "replaceable wear skid (PETG / TPU), clips over the shell rim")
    for sg in (1, -1):
        ear = cq.Workplane("XY").box(s["ear"]["r"][1] - s["ear"]["r"][0], s["ear"]["y"][1] - s["ear"]["y"][0], P0[2] + 9 - LID_TOP).translate(
            ((s["ear"]["r"][0] + s["ear"]["r"][1]) / 2, sg * sum(s["ear"]["y"]) / 2, (LID_TOP + P0[2] + 9) / 2)).edges("|Y").fillet(4.0).val()
        parts[f"HEAD_EAR_{'L' if sg > 0 else 'R'}"] = ("HEAD", ear, "yoke ear on the lid (moulded with the lid), pivot hole 6 mm")
    head_disc = cq.Workplane("XY").circle(s["head_r"]).extrude(LID_TOP).val()
    parts["HEAD_ENVELOPE"] = ("HEAD", head_disc, "envelope of the built shells (collision proxy)")
    # yoke: two cheeks outside the ears + a socket for L1
    for sg in (1, -1):
        ch = shaft_frame(cq.Workplane("XY").box(24, s["cheek"]["y"][1] - s["cheek"]["y"][0], 44).translate((0, sg * sum(s["cheek"]["y"]) / 2, 12)).edges("|Y").fillet(5).val(), 0.0)
        parts[f"YOKE_CHEEK_{'L' if sg > 0 else 'R'}"] = ("L1", ch, "yoke cheek with friction washer and pivot knob")
    parts["YOKE_SOCKET"] = ("L1", shaft_frame(cq.Workplane("XY").circle(16).circle(s["tube"]["od"] / 2).extrude(30).val(), 18.0), "yoke socket bonded to L1")
    parts["YOKE_BRIDGE"] = ("L1", shaft_frame(cq.Workplane("XY").box(24, 2 * s["cheek"]["y"][1], 8).translate((0, 0, 30)).val(), 0.0), "bridge joining the cheeks")
    parts["L1_TUBE"] = ("L1", tube(s["tube"]["od"], s["tube"]["id"], st["L1"][0], st["L1"][1]), "carbon-fibre tube 25 / 22.4")
    tx = s["txd"]; txs = st["TXD"]
    txd = shaft_frame(rbox(tx["size"][2], tx["size"][1], tx["size"][0], tx["fillet"]).translate((0, 0, (txs[1] - txs[0]) / 2)), txs[0], 0.0, tx["lat"])
    parts["TXD_HOUSING"] = ("L1", txd, "TX driver housing beside L1 (+Y), heat-sink vents on its outer face (position from the rf2_system echo search)")
    # hinges F1 / F2: two collars each (pin side chosen by the fold search; geometry here is the collar pair)
    for nm, (a, b) in (("F1", st["F1"]), ("F2", st["F2"])):
        ga, gb = ("L1", "L2") if nm == "F1" else ("L2", "UP")
        parts[f"{nm}_A"] = (ga, tube(34.0, s["tube"]["od"], a, (a + b) / 2 - 0.5), f"{nm} hinge half A with over-centre lever lock")
        parts[f"{nm}_B"] = (gb, tube(34.0, s["tube"]["od"], (a + b) / 2 + 0.5, b), f"{nm} hinge half B")
    parts["L2_TUBE"] = ("L2", tube(s["tube"]["od"], s["tube"]["id"], st["L2"][0], st["L2"][1]), "carbon-fibre outer tube 25 / 22.4")
    parts["L2_TELE"] = ("L2", tube(s["tele"]["od"], s["tele"]["id"], st["L2"][1] - 400.0, st["L2"][1]), "inner telescoping tube 22 / 19.6 (collapsed; slides out 0-250 mm)")
    parts["L2_LOCK"] = ("L2", tube(33.0, s["tube"]["od"], *st["lock"]), "cam-lock collar for the telescope")
    r3 = s["ref3"]
    sleeve = cq.Workplane("XY").circle(r3["sleeve_od"] / 2).circle(s["tube"]["od"] / 2).extrude(st["REF3"][1] - st["REF3"][0]).edges().chamfer(1.5).val()
    parts["REF3_SLEEVE"] = ("L2", shaft_frame(sleeve, st["REF3"][0]), "REF3 as a sleeve on L2: X / Y saddle coils + Z solenoid under a 1 mm cover (no box; rf2_ref3 'sleeve')")
    # ---------------- upper unit
    parts["UP_NECK"] = ("UP", tube(30.0, s["tube"]["od"] - 0.1, *st["neck"]), "neck from F2 into the grip head")
    gh = s["gh"]; g0, g1 = st["GH"]; gn0, gn1 = gh["n"]
    GH = shaft_frame(rbox(gn1 - gn0, gh["w"], g1 - g0, gh["fillet"]).translate(((gn0 + gn1) / 2, 0, (g1 - g0) / 2)), g0)
    parts["UP_GRIP_HEAD"] = ("UP", GH, "grip head: HB2 main board, button, screen hinge, dial, trigger pivot")
    # pistol grip: loft of ellipses along the grip axis g, raked back by rake_deg; finger wedges cut on the front face
    gp = s["grip"]; rk = math.radians(gp["rake_deg"]); g = math.cos(rk) * (-N) + math.sin(rk) * D; f = math.cos(rk) * (-D) + math.sin(rk) * (-N)
    w = cq.Workplane("XY")
    for k, (z, a, b) in enumerate(gp["sections"]):
        w = (w.ellipse(a, b) if k == 0 else w.workplane(offset=z - gp["sections"][k - 1][0]).ellipse(a, b))
    grip = w.loft(combine=True)
    for z, r, dep in gp["grooves"]:                                                   # finger wedges: cylinders across the front (local +X = front)
        a_here = float(np.interp(z, [q[0] for q in gp["sections"]], [q[1] for q in gp["sections"]]))
        grip = grip.cut(cq.Workplane("XZ").circle(r).extrude(30, both=True).translate((a_here + r - dep, 0, z)))
    grip_top = at(gp["top_s"], gn0 + 2.0)
    parts["UP_GRIP"] = ("UP", place(grip.val(), f, Y, g, grip_top), "pistol grip: 3 finger wedges (middle, ring, little), palm swell, pinky shelf; overmoulded TPE")
    tg = s["trigger"]
    trig = cq.Workplane("XZ").moveTo(0, 0).threePointArc((5.0, -tg["len"] / 2), (1.0, -tg["len"])).lineTo(1.0 + tg["t"], -tg["len"]).threePointArc((5.0 + tg["t"], -tg["len"] / 2), (tg["t"], 0)).close().extrude(tg["w"] / 2, both=True).val()
    parts["UP_TRIGGER"] = ("UP", place(trig, -D, Y, N, at(tg["s"], gn0)), "fighter-pilot trigger blade (index finger), pivot in the grip-head floor, tail presses SW_TRG")
    gd = s["guard"]
    guard = cq.Workplane("XZ").moveTo(gd["s"][0] - g0 + g0, 0)
    gpts = [(0, 0), (-8, -gd["depth"] * 0.55), (gd["s"][1] - gd["s"][0] - 8, -gd["depth"])]
    gpath = cq.Workplane("XZ").spline(gpts, includeCurrent=False)
    gsec = cq.Workplane("YZ").rect(9.0, gd["t"])
    try: gsolid = gsec.sweep(gpath).val()
    except Exception: gsolid = cq.Workplane("XY").box(gd["s"][1] - gd["s"][0], 9, gd["t"]).val()
    parts["UP_GUARD"] = ("UP", place(gsolid, D, Y, N, at(gd["s"][0], gn0)), "trigger guard loop")
    bt = s["button"]
    btn = cq.Workplane("XY").circle(bt["ring_d"] / 2).extrude(1.2).faces(">Z").workplane().circle(bt["cap_d"] / 2).extrude(bt["height"]).edges(">Z").fillet(1.5).val()
    parts["UP_BUTTON"] = ("UP", place(btn, D, Y, N, at(bt["s"], gn1)), "thumb power button (KSC2 TE below) with a light-pipe ring (3 x SK9822)")
    sc = s["screen"]; slen = sc["s"][1] - sc["s"][0]
    scr = rbox(slen, sc["w"], sc["t"], 2.0).translate((-slen / 2, 0, sc["t"] / 2))      # local x along -D from the hinge
    hinge_pt = at(sc["hinge_s"], gn1)
    scr_closed = place(scr, D, Y, N, hinge_pt)
    R_open, t_open = rot_about(hinge_pt, Y, math.radians(sc["open_deg"]))          # + lifts the front edge: the face turns toward the user
    parts["UP_SCREEN"] = ("UP", scr_closed, "flip-up screen (1.28 in memory LCD class) hinged at the grip head's rear top edge; push-push latch")
    dl = s["dial"]
    dial = cq.Workplane("XZ").circle(dl["d"] / 2).extrude(dl["t"]).val()
    parts["UP_DIAL"] = ("UP", place(dial, D, Y, N, at(dl["s"], 10.0, -gh["w"] / 2)), "3-position mode dial (thumb side): two cam lobes on two KSC2 TE")
    sp = s["spine"]; a0, a1 = st["spine"]
    parts["UP_SPINE"] = ("UP", shaft_frame(rbox(sp["h"], sp["w"], a1 - a0, 5.0).translate((0, 0, (a1 - a0) / 2)), a0), "spine beam: PWR board (LMR36520, regenerative buck), cable to the bay contacts")
    cu = s["cuff"]; c0, c1 = st["cuff"]
    keep_from = (cu["r_in"] + cu["t"]) * math.cos(math.radians((360.0 - cu["arc_deg"]) / 2))      # remove the top (360 - arc) deg: a plane cut at local x = R cos(half the gap)
    ring = cq.Workplane("XY").circle(cu["r_in"] + cu["t"]).circle(cu["r_in"]).extrude(c1 - c0).cut(cq.Workplane("XY").box(200, 200, 400).translate((keep_from + 100, 0, 0)))
    try: ring = ring.edges().fillet(1.5)
    except Exception: pass
    parts["UP_CUFF"] = ("UP", shaft_frame(ring.val(), c0, cu["centre_n"]), f"elbow cuff: {cu['arc_deg']:.0f} deg trough, r {cu['r_in']:.0f} mm, strap slots; folds flat")
    stem_len = cu["centre_n"] - cu["r_in"] - cu["t"] + sp["h"] / 2 + 6
    stem = rbox(stem_len, 26.0, 40.0, 4.0).translate((stem_len / 2 - sp["h"] / 2, 0, 20.0))
    parts["UP_CUFF_STEM"] = ("UP", shaft_frame(stem, c0 - 6), "cuff stem rising from the spine (cuff pivot at its base)")
    ce = s["cells"]; cw = s["cart_wall"]; Lc = ce["n_s"] * ce["d"] + 2 * cw; Wc = ce["l"] + 2 * cw; Hc = ce["n_p"] * ce["d"] + 4.0 + 2 * cw
    bw = s["bay_wall"]; bc = s["bay_clear"]; b0, b1 = st["bay"]
    Lb = Lc + 2 * bc + bw; Wb = Wc + 2 * bc + 2 * bw; Hb = Hc + 2 * bc + 2 * bw
    n_top = -sp["h"] / 2 + 1.0; n_bay = n_top - Hb / 2
    bay = rbox(Hb, Wb, Lb, 4.0).cut(cq.Workplane("XY").box(Hc + 2 * bc, Wc + 2 * bc, Lb).translate((0, 0, bw)).val())
    parts["UP_BAY"] = ("UP", shaft_frame(bay.translate((0, 0, Lb / 2)), b1 - Lb, n_bay), "battery bay under the spine, open at the rear; blade contacts at its front")
    cart = rbox(Hc, Wc, Lc, 3.0)
    parts["UP_CARTRIDGE"] = ("UP", shaft_frame(cart.translate((0, 0, Lc / 2)), b1 - Lc - bc, n_bay), f"battery cartridge: {ce['n_s']}S{ce['n_p']}P Molicel P30B + BQ76952 + MT60 charge port; slides out rearward")
    geo = dict(g=g, f=f, grip_top=grip_top, hinge_pt=hinge_pt, R_open=R_open, t_open=t_open, cart=(Lc, Wc, Hc), bay=(Lb, Wb, Hb), n_bay=n_bay, b1=b1)
    return parts, geo
# ---------------------------------------------------------------- electronics envelopes in the new housings (part, housing, local box in the housing frame)
def electronics(geo):
    s = SPEC; st = s["st"]; gh = s["gh"]; E = {}
    def box_in_shaft(lx, ly, lz, s0, n, y=0.0): return shaft_frame(cq.Workplane("XY").box(lx, ly, lz).translate((0, 0, lz / 2)).val(), s0, n, y)
    n_board = gh["n"][1] - 8.0                                                                    # HB2-M 1.0 mm board under the top wall
    E["HB2M_BOARD"] = ("UP_GRIP_HEAD", box_in_shaft(1.0, 30.0, 70.0, st["GH"][0] + 5, n_board))
    for nm, (s0, l, w, h, y) in dict(SW_PWR=(s["button"]["s"] - 3.15, 6.3, 6.2, 3.5, 0.0), LS1=(st["GH"][0] + 7, 12.0, 12.0, 3.0, 8.0), U20_MCU=(950.0, 7.0, 7.0, 0.9, -6.0),
                                     U21_LDO=(958.0, 3.0, 3.0, 1.45, 8.0), AHCT_x4=(944.0, 6.0, 14.0, 1.45, -8.0), J_SCR=(966.0, 3.0, 9.0, 2.0, 0.0)).items():
        E[nm] = ("UP_GRIP_HEAD", box_in_shaft(h, w, l, s0, n_board + 0.5 + h / 2, y))
    E["SW_SEL_AB"] = ("UP_GRIP_HEAD", box_in_shaft(6.2, 3.5, 14.0, s["dial"]["s"] - 7, 10.0, -gh["w"] / 2 + 5.5))
    E["SW_TRG"] = ("UP_GRIP_HEAD", box_in_shaft(6.3, 6.2, 3.5, s["trigger"]["s"] + 4, gh["n"][0] + 7.0))
    E["J1_RS485_ESD"] = ("UP_GRIP_HEAD", box_in_shaft(6.0, 16.0, 14.0, st["GH"][0] + 3, -4.0))
    sp = s["spine"]; inner_h = sp["h"] - 2 * sp["wall"]
    E["PWR_BOARD"] = ("UP_SPINE", box_in_shaft(1.6, sp["w"] - 2 * sp["wall"] - 1, 180.0, st["spine"][0] + 15, -inner_h / 2 + 1.5))
    for nm, (s0, l, w, h, y) in dict(Q30_C3M=(1000.0, 15.0, 10.2, 4.4, -6.0), U32_UCC5350=(1020.0, 5.0, 6.0, 1.75, 8.0), D30_US3M=(1030.0, 7.0, 6.1, 2.3, -8.0),
                                     L30_INDUCTOR=(1045.0, 12.0, 12.0, 8.0, 0.0), C30_FILM_630V=(1065.0, 26.0, 11.0, 17.0, 0.0), U31_LMR36520=(1100.0, 4.0, 4.0, 1.0, 6.0),
                                     L31_INDUCTOR=(1108.0, 5.0, 5.0, 3.0, 6.0)).items():
        E[nm] = ("UP_SPINE", box_in_shaft(h, w, l, s0, -inner_h / 2 + 2.3 + h / 2, y))
    tx = s["txd"]; t0 = st["TXD"][0]; ih = tx["size"][2] - 4
    for nm, (s0, l, w, h, nn) in dict(TXD_BOARD=(t0 + 5, 80.0, 28.0, 1.6, -ih / 2 + 0.8), HS1_OHMITE_D2=(t0 + 8, 30.9, 14.2, 12.7, -ih / 2 + 1.6 + 6.35),
                                      CB_BULK_3x3=(t0 + 44, 31.0, 31.0 - 4, 10.2, -ih / 2 + 1.6 + 5.1), C1_CLAMP_FILM=(t0 + 76, 10.0, 24.0, 18.0, -ih / 2 + 1.6 + 9.0)).items():
        E[nm] = ("TXD_HOUSING", box_in_shaft(h, w, l, s0, nn, tx["lat"]))
    r3 = s["ref3"]
    E["REF3_WINDINGS"] = ("REF3_SLEEVE", shaft_frame(cq.Workplane("XY").circle(r3["winding_r"][1]).circle(r3["winding_r"][0]).extrude(st["REF3"][1] - st["REF3"][0] - 6).val(), st["REF3"][0] + 3))
    ce = s["cells"]; Lc, Wc, Hc = geo["cart"]; cw = s["cart_wall"]; b1 = geo["b1"]; bc = s["bay_clear"]; s_c0 = b1 - Lc - bc
    cells = []
    for i in range(ce["n_s"]):
        for j in range(ce["n_p"]):
            c = cq.Workplane("XZ").circle(ce["d"] / 2).extrude(ce["l"] / 2, both=True).val()
            cells.append(shaft_frame(c.translate((0, 0, 0)), s_c0 + cw + ce["d"] / 2 + i * ce["d"], geo["n_bay"] - Hc / 2 + cw + ce["d"] / 2 + j * ce["d"]))
    E["CELLS_7S2P"] = ("UP_CARTRIDGE", cq.Compound.makeCompound(cells))
    E["BQ76952_BOARD"] = ("UP_CARTRIDGE", box_in_shaft(1.6, Wc - 2 * cw - 2, Lc - 2 * cw - 2, s_c0 + cw + 1, geo["n_bay"] + Hc / 2 - cw - 1.6))
    return E
# ---------------------------------------------------------------- checks and the fold search
def solids_of(parts, group, skip=("HEAD_ENVELOPE",)): return [p[1] for k, p in parts.items() if p[0] == group]
def comp(lst): return cq.Compound.makeCompound(lst)
# ---------------------------------------------------------------- timing, sampling, the fast fold search
TIMINGS = {}
class phase:
    def __init__(self, name): self.name = name
    def __enter__(self): self.t = time.time()
    def __exit__(self, *a):
        TIMINGS[self.name] = round(TIMINGS.get(self.name, 0.0) + time.time() - self.t, 2); print(f"[phase] {self.name}: {TIMINGS[self.name]} s", flush=True)
def fold_T(axis, side, o, nm):
    a, b = SPEC["st"][nm]; h = at((a + b) / 2)
    return rot_about(h + side * o * N, Y, math.pi) if axis == "Y" else rot_about(h + side * o * Y, N, math.pi)
def samples(shape, spacing=1.5, tol=0.8, seed=0):
    """surface samples: about one point per spacing^2 of area (area-weighted, seeded) plus points every `spacing` along each triangle edge, so a skinny
    triangle costs points in proportion to its size, not to its longest edge squared"""
    v, t = shape.tessellate(tol); V = np.array([[q.x, q.y, q.z] for q in v]); T = np.array(t); rng = np.random.default_rng(seed)
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]; area = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
    n = np.maximum(0, np.round(area / spacing ** 2)).astype(int); idx = np.repeat(np.arange(len(T)), n)
    r1, r2 = rng.random(len(idx)), rng.random(len(idx)); sw = r1 + r2 > 1; r1[sw], r2[sw] = 1 - r1[sw], 1 - r2[sw]
    inner = A[idx] + r1[:, None] * (B[idx] - A[idx]) + r2[:, None] * (C[idx] - A[idx])
    edges = []
    for P, Q in ((A, B), (B, C), (C, A)):
        L = np.linalg.norm(Q - P, axis=1); k = np.maximum(1, np.ceil(L / spacing)).astype(int); j = np.repeat(np.arange(len(P)), k)
        u = (np.concatenate([np.arange(kk) for kk in k]) / np.repeat(k, k))[:, None]; edges.append(P[j] + u * (Q[j] - P[j]))
    P = np.vstack([V, inner] + edges)
    key = np.floor(P / spacing).astype(np.int64); _, keep = np.unique(key, axis=0, return_index=True)          # one point per spacing-sized voxel
    return P[np.sort(keep)]
def fold_search(group_pts, spacing):
    from scipy.spatial import cKDTree
    t0 = time.time(); gap = SPEC["fold_gap"] + spacing / 2; ev = [0]; trees = {}
    def tf(P, T): return P @ T[0].T + T[1]
    def clear(PA, key_b, PB):
        ev[0] += 1; lo_a, hi_a = PA.min(0), PA.max(0); lo_b, hi_b = PB.min(0), PB.max(0)
        if np.any(lo_a - hi_b > gap) or np.any(lo_b - hi_a > gap): return True             # bounding boxes apart: no query needed
        if key_b not in trees: trees[key_b] = cKDTree(PB)
        d, _ = trees[key_b].query(PA, k=1, distance_upper_bound=gap); return bool(np.all(np.isinf(d)))
    def bisect(ok_fn, lo, hi, res=2.5):
        if not ok_fn(hi): return None
        while hi - lo > res:
            mid = (lo + hi) / 2
            if ok_fn(mid): hi = mid
            else: lo = mid
        return round(hi, 1)
    L1, L2, UP, HD = group_pts["L1"], group_pts["L2"], group_pts["UP"], group_pts["HEAD"]; M = np.column_stack([D, N, Y]); log = []; best = None
    for ax1, sd1 in itertools.product(("Y", "N"), (1, -1)):
        o1 = bisect(lambda o: clear(tf(L2, fold_T(ax1, sd1, o, "F1")), "L1", L1), 15.0, 140.0)
        if o1 is None: continue
        T1 = fold_T(ax1, sd1, o1, "F1"); L2f = tf(L2, T1); trees.pop(("L2f"), None); trees["L2f"] = cKDTree(L2f)
        for ax2, sd2 in itertools.product(("Y", "N"), (1, -1)):
            o2 = bisect(lambda o: clear(tf(UP, compose(T1, fold_T(ax2, sd2, o, "F2"))), "L1", L1) and clear(tf(UP, compose(T1, fold_T(ax2, sd2, o, "F2"))), "L2f", L2f), 15.0, 220.0)
            if o2 is None: continue
            T2 = compose(T1, fold_T(ax2, sd2, o2, "F2")); UPf = tf(UP, T2); key_up = f"UP{ax1}{sd1}{ax2}{sd2}"; trees[key_up] = cKDTree(UPf)
            for ah in range(-180, 180, 10):
                Hf = tf(HD, rot_about(P0, Y, math.radians(ah)))
                if not (clear(Hf, "L1", L1) and clear(Hf, "L2f", L2f) and clear(Hf, key_up, UPf)): continue
                Q = np.vstack([Hf, L1, L2f, UPf]) @ M; ext = sorted((Q.max(0) - Q.min(0)).tolist(), reverse=True); vol = float(np.prod(ext))
                row = dict(F1=dict(axis=ax1, side=sd1, offset_mm=o1), F2=dict(axis=ax2, side=sd2, offset_mm=o2), head_deg=ah, package_mm=[round(x) for x in ext]); log.append((vol, row))
                if best is None or vol < best[0]: best = (vol, row)
            trees.pop(key_up, None)
    if best is None: return dict(F1=None, F2=None, head_deg=None, package_mm=[9999, 9999, 9999], evaluations=ev[0], search_s=round(time.time() - t0, 1), top5=[])
    out = dict(best[1]); out.update(evaluations=ev[0], search_s=round(time.time() - t0, 1), top5=[r for _, r in sorted(log, key=lambda x: x[0])[:5]]); return out
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from simcache import memo
def _groups_for_search():
    parts, geo = build()
    return {g_: cq.Compound.makeCompound([p[1] for k, p in parts.items() if p[0] == g_ and not k.startswith(("F1_", "F2_", "HEAD_EAR", "YOKE_CHEEK"))]) for g_ in ("HEAD", "L1", "L2", "UP")}
@memo("geom.upper.fold", uses=[build, fold_search, samples, fold_T, rot_about, compose, at, SPEC])
def fold_search_cached(spacing=2.0):
    G = _groups_for_search(); pts = {k: samples(v, spacing) for k, v in G.items()}
    print("[fold] samples per group:", {k: len(v) for k, v in pts.items()}, flush=True)
    return fold_search(pts, spacing)
def main():
    t0 = time.time(); s = SPEC; TIMINGS.clear()
    with phase("build parts"): parts, geo = build(); E = electronics(geo)
    res = dict(status="MODELED; dimensions ASSUMED unless a datasheet is named", checks={}, parts={k: v[2] for k, v in parts.items()})
    c = res["checks"]
    # 1. electronics inside their housings (envelope minus housing solid: the housings here are solid proxies, so containment = inside the outer solid)
    cont = {}
    _ph = phase("containment"); _ph.__enter__()
    for nm, (hs, sh) in E.items():
        outer = parts[hs][1]; inside = sh.cut(outer).Volume(); cont[nm] = round(inside, 2)
    _ph.__exit__()
    c["electronics inside their housings"] = dict(ok=max(cont.values()) < 1.0, outside_mm3=cont, note="every part envelope inside the outer solid of its housing (walls 2-3 mm: the housing is printed in halves around the boards)")
    # 2. ergonomics
    gp = s["grip"]; grooves = [q[0] for q in gp["grooves"]]; pitch = np.diff(grooves)
    tg = s["trigger"]; reach = tg["reach_from_backstrap"]
    thumb_reach = float(np.linalg.norm(at(s["button"]["s"], s["gh"]["n"][1]) - (geo["grip_top"] + geo["f"] * 0 + D * 20.0)))
    c["grip"] = dict(ok=gp["length"] >= 110 and all(21.0 <= p <= 26.0 for p in pitch) and 120 <= math.pi * (3 * (23.5 + 19.5) - math.sqrt((3 * 23.5 + 19.5) * (23.5 + 3 * 19.5))) <= 150,
                     length_mm=gp["length"], groove_pitch_mm=pitch.tolist(), circumference_mm=round(math.pi * (3 * (23.5 + 19.5) - math.sqrt((3 * 23.5 + 19.5) * (23.5 + 3 * 19.5))), 1),
                     rake_deg=gp["rake_deg"], note="targets ASSUMED: length >= 110 (95th-pct hand breadth about 97 mm), finger pitch 21-26 mm, circumference 120-150 mm")
    c["trigger_and_thumb"] = dict(ok=60.0 <= reach <= 75.0 and 40.0 <= thumb_reach <= 70.0, trigger_reach_mm=reach, thumb_to_button_mm=round(thumb_reach, 1),
                                  note="trigger face 70 mm from the back strap (index first joint), button 40-70 mm from the web of the hand (ASSUMED targets)")
    # screen viewing angle toward the eye (sagittal frame: X behind the user? X is outward over the heel = toward the user)
    n_closed = N; n_open = geo["R_open"] @ n_closed; eye = at(s["screen"]["s"][0], s["gh"]["n"][1]) + np.array([s["eye"]["behind"], 0, s["eye"]["above"]]); scr_c = geo["R_open"] @ at(np.mean(s["screen"]["s"]), s["gh"]["n"][1] + 3) + geo["t_open"]
    v = eye - scr_c; ang = math.degrees(math.acos(float(np.dot(n_open, v) / np.linalg.norm(v))))
    c["screen_view"] = dict(ok=ang <= 25.0, angle_to_eye_deg=round(ang, 1), open_deg=s["screen"]["open_deg"], eye_ASSUMED_mm=s["eye"])
    # cuff / grip heights over tilt 35-50 deg above horizontal and telescope 0-250 (head flat on the ground)
    hts = []
    for elev in (35, 40, 45, 50):
        for ext in (0.0, s["tele"]["travel"]):
            th = math.radians(elev); sc_ = np.mean(s["st"]["cuff"]) + ext; z = P0[2] + sc_ * math.sin(th) + s["cuff"]["centre_n"] * math.cos(th); hts.append((elev, ext, round(z)))
    zs = [h[2] for h in hts]
    c["cuff_height_range"] = dict(ok=min(zs) <= 900 and max(zs) >= 1100, min_mm=min(zs), max_mm=max(zs), table=hts, note="elbow (cuff) height 0.90-1.10 m covered by tilt 35-50 deg and the 0-250 mm telescope (target ASSUMED)")
    c["telescope_overlap"] = dict(ok=400.0 - s["tele"]["travel"] >= s["tele"]["overlap_min"], overlap_at_full_mm=400.0 - s["tele"]["travel"])
    # 3. battery: cells fit the cartridge, cartridge fits the bay, rearward slide path clear
    Lc, Wc, Hc = geo["cart"]; cart = parts["UP_CARTRIDGE"][1]
    path_clear = []
    for dz in np.linspace(10, Lc + 10, 8):
        mv = cart.moved(trsf(np.eye(3), D * dz)); hits = [k for k, p in parts.items() if p[0] == "UP" and k not in ("UP_CARTRIDGE", "UP_BAY") and mv.distance(p[1]) < 0.3]; path_clear.append(hits)
    c["battery"] = dict(ok=all(not h for h in path_clear) and cont["CELLS_7S2P"] < 1.0, cartridge_mm=[round(v, 1) for v in (Lc, Wc, Hc)], slide_path_hits=sorted({x for h in path_clear for x in h}),
                        cells="14 x Molicel INR-18650-P30B (18.6 x 65.2 mm max, datasheet)", note="the cartridge slides out rearward under the cuff without touching anything")
    # 4. deployed collisions between groups (hinge halves excluded where they meet)
    groups = ["HEAD", "L1", "L2", "UP"]
    G = {g_: comp([p[1] for k, p in parts.items() if p[0] == g_ and not k.startswith(("F1_", "F2_", "HEAD_EAR", "YOKE_CHEEK"))]) for g_ in groups}
    dep = {f"{a}-{b}": round(G[a].distance(G[b]), 2) for a, b in itertools.combinations(groups, 2) if (a, b) not in (("HEAD", "L1"), ("L1", "L2"), ("L2", "UP"))}
    c["deployed_clear"] = dict(ok=min(dep.values()) >= 2.0, min_gaps_mm=dep)
    # 5. fold search (fast path): every group is tessellated ONCE into surface samples (about 1.5 mm apart); a candidate fold is a rigid transform applied to
    # those arrays; clearance is a KD-tree query, pruned first by bounding boxes; hinge offsets are found by bisection. Exact OCC distances verify only the
    # winner. The search result is memoised in state/simcache (kind geom.upper.fold) keyed on SPEC and this code, so an unchanged design skips it.
    with phase("fold search"):
        cfg = fold_search_cached()
    T1 = compose(I3, fold_T(cfg["F1"]["axis"], cfg["F1"]["side"], cfg["F1"]["offset_mm"], "F1")); T2 = compose(T1, fold_T(cfg["F2"]["axis"], cfg["F2"]["side"], cfg["F2"]["offset_mm"], "F2"))
    Th = rot_about(P0, Y, math.radians(cfg["head_deg"]))
    with phase("fold exact verification"):
        Hf, L2f, UPf = apply(G["HEAD"], Th), apply(G["L2"], T1), apply(G["UP"], T2); l1 = G["L1"]
        exact = {"HEAD-L1": Hf.distance(l1), "HEAD-L2": Hf.distance(L2f), "HEAD-UP": Hf.distance(UPf), "L1-L2": l1.distance(L2f), "L1-UP": l1.distance(UPf), "L2-UP": L2f.distance(UPf)}
    best = (None, cfg, cfg["package_mm"], (T1, T2, Th))
    bp = sorted(s["backpack"], reverse=True)
    fits = all(d_ <= b_ for d_, b_ in zip(sorted(cfg["package_mm"], reverse=True), bp)) and min(exact.values()) >= s["fold_gap"]
    res["fold"] = dict(best={k: cfg[k] for k in ("F1", "F2", "head_deg")}, package_mm=cfg["package_mm"], backpack_ASSUMED_mm=bp, exact_gaps_mm={k: round(v, 2) for k, v in exact.items()},
                       evaluations=cfg["evaluations"], search_s=cfg["search_s"], top5=cfg["top5"])
    c["folds_to_backpack"] = dict(ok=fits, package_mm=cfg["package_mm"], target_mm=bp, min_exact_gap_mm=round(min(exact.values()), 2),
                                  note="Z-fold at F1 and F2, head turned on the yoke; candidates screened on surface samples, the winner verified with exact OCC distances")
    bend = min(cfg["F1"]["offset_mm"], cfg["F2"]["offset_mm"])
    c["cable_bend_at_folds"] = dict(ok=bend >= s["bend_r_min"], min_hinge_offset_mm=bend, bend_r_min_mm=s["bend_r_min"], note="the bundle's 180 deg loop through a hinge has a radius about equal to the hinge offset")
    # 6. masses and balance (deployed, shaft at 40 deg above horizontal; torque about the hand at the grip top)
    dens = dict(PETG=1.27e-3, CF=1.55e-3)
    def vol(nm): return parts[nm][1].Volume()
    shell_m = 0.25                                                                                  # printed housings are shells: 25 % of the solid proxy volume (ASSUMED)
    masses = {"head (shells + coil + electronics + potting, ASSUMED 650 g)": (650.0, np.array([0.0, 0, 8.0])),
              "L1 + yoke tube": (dens["CF"] * (vol("L1_TUBE")) + 40.0, at(230)), "TXD (housing + parts, ASSUMED 180 g)": (180.0, at(375, 0, 29)),
              "L2 + telescope": (dens["CF"] * (vol("L2_TUBE") + vol("L2_TELE")) + 30.0, at(650)), "REF3 sleeve (332 g copper, rf2_ref3, + cover 30 g)": (362.0, at(645)),
              "grip head + grip + trigger (shells, ASSUMED 25 %) + HB2 30 g": (dens["PETG"] * shell_m * (vol("UP_GRIP_HEAD") + vol("UP_GRIP")) + 30.0, at(940, -20)),
              "spine + PWR board (ASSUMED 120 g)": (120.0, at(1090)), "cuff + stem": (dens["PETG"] * shell_m * (vol("UP_CUFF") + vol("UP_CUFF_STEM")) + 20, at(1230, 40)),
              "battery cartridge (14 x 47 g cells + 90 g)": (14 * 47.0 + 90.0, at(1130, geo["n_bay"]))}
    grip_pt = at(948.0, -22.0)
    def torque(include_batt=True):
        tq = 0.0
        for k, (m, p) in masses.items():
            if not include_batt and k.startswith("battery"): continue
            rel = (p - grip_pt); horiz = rel[0] * math.cos(math.radians(50 - SPEC["tilt_deg"]))                  # sagittal X is horizontal
            tq += m * 9.81e-3 * (-rel[0]) * 1e-3
        return tq
    tot = sum(m for m, _ in masses.values()); com = sum(m * p for m, p in masses.values()) / tot
    res["mass"] = dict(items_g={k: round(m) for k, (m, _) in masses.items()}, total_g=round(tot), com_s_mm=round(float(np.dot(com - P0, D))),
                       wrist_torque_Nm=round(torque(), 2), wrist_torque_without_battery_behind_Nm=round(torque(False), 2),
                       note="torque of the whole about the hand (head forward positive): the battery behind the hand is the counterweight; the cuff takes the rest")
    c["battery_counterweights"] = dict(ok=torque() < torque(False), with_Nm=res["mass"]["wrist_torque_Nm"], without_Nm=res["mass"]["wrist_torque_without_battery_behind_Nm"])
    res["fold_study_retired"] = {k: c.pop(k) for k in ("folds_to_backpack", "cable_bend_at_folds") if k in c}      # owner 2026-10-30: no shaft folds; telescope (+ cuff fold) next
    res["fold_study_retired"]["note"] = "the owner withdrew shaft folding (telescoping instead); kept as a record, not a pass / fail check"
    for v in c.values(): v["ok"] = bool(v["ok"])
    res["ok"] = bool(all(v["ok"] for v in c.values()))
    # exports and views
    with phase("exports and views"): export(parts, E, geo, best)
    res["timings_s"] = dict(TIMINGS, total=round(time.time() - t0, 1))
    json.dump(res, open(os.path.join(OUT, "rf2_upper_check.json"), "w"), indent=1, default=float)
    print(json.dumps({k: bool(v["ok"]) for k, v in c.items()}, indent=1)); print("fold:", res["fold"]["best"], res["fold"]["package_mm"]); print("mass:", res["mass"]["total_g"], "g; torque", res["mass"]["wrist_torque_Nm"], "N m"); print("timings:", res["timings_s"])
    return res
def to_head_frame(sh): return sh.moved(trsf(np.array([[math.cos(math.radians(HEEL)), -math.sin(math.radians(HEEL)), 0], [math.sin(math.radians(HEEL)), math.cos(math.radians(HEEL)), 0], [0, 0, 1]]), np.zeros(3)))
def export(parts, E, geo, best):
    import trimesh
    for k, (g_, sh, _) in parts.items():
        if k == "HEAD_ENVELOPE": continue
        cq.exporters.export(to_head_frame(sh), os.path.join(OUT, f"{k}.stl"))
    asm = cq.Assembly(name="RF2_UPPER")
    for k, (g_, sh, _) in parts.items():
        if k != "HEAD_ENVELOPE": asm.add(to_head_frame(sh), name=k)
    for k, (h, sh) in E.items(): asm.add(to_head_frame(sh), name="E_" + k, color=cq.Color(0.9, 0.7, 0.2))
    asm.save(os.path.join(OUT, "rf2_upper_assembly.step"))
    views(parts, E, geo, best)
def views(parts, E, geo, best):
    """pyvista off-screen renders: deployed side and 3/4, folded package, upper unit with its electronics (shell transparent, screen open)"""
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true"); import pyvista as pv
    def pvmesh(sh, tol=0.6):
        v, t = sh.tessellate(tol); V = np.array([[q.x, q.y, q.z] for q in v]); F = np.hstack([np.full((len(t), 1), 3), np.array(t)]).ravel(); return pv.PolyData(V, F)
    Rh = np.array([[math.cos(math.radians(-HEEL)), -math.sin(math.radians(-HEEL)), 0], [math.sin(math.radians(-HEEL)), math.cos(math.radians(-HEEL)), 0], [0, 0, 1]])   # head frame -> sagittal frame
    heads = []
    for path in (SPEC["head_shell"], SPEC["head_lid"]):
        m = pv.read(path); m.points = (Rh @ np.asarray(m.points).T).T; heads.append(m)
    col = dict(HEAD="#b8c2ca", L1="#2b2b2b", L2="#2b2b2b", UP="#2f6db5")
    def tcolor(k, g_): return "#c0392b" if k.startswith("TXD") else "#8e44ad" if k.startswith("REF3") else "#e67e22" if k in ("UP_TRIGGER", "UP_BUTTON") else "#1abc9c" if k == "UP_SCREEN" else "#7f8c8d" if k in ("UP_CARTRIDGE",) else col[g_]
    def tf_mesh(m, T):
        m = m.copy(); m.points = (T[0] @ np.asarray(m.points).T).T + T[1]; return m
    pl = pv.Plotter(shape=(2, 2), off_screen=True, window_size=(1800, 1200), lighting="three lights")
    screen_open = (geo["R_open"], geo["t_open"])
    for idx, (title, state) in enumerate((("deployed: side", "dep"), ("deployed: 3/4", "dep3"), ("folded package (best of the search)", "fold"), ("upper unit: housings transparent, electronics placed, screen open", "up"))):
        pl.subplot(idx // 2, idx % 2); pl.set_background("#f6f7f9"); pl.add_text(title, font_size=10)
        T = {"HEAD": I3, "L1": I3, "L2": I3, "UP": I3}
        if state == "fold" and best: T1, T2, Th = best[3]; T = {"HEAD": Th, "L1": I3, "L2": T1, "UP": T2}
        for k, (g_, sh, _) in parts.items():
            if k == "HEAD_ENVELOPE" or (state == "up" and g_ != "UP"): continue
            m = tf_mesh(pvmesh(sh), T[g_]) if not (state == "up" and k == "UP_SCREEN") else tf_mesh(pvmesh(sh), screen_open)
            op = 0.25 if state == "up" and k not in ("UP_TRIGGER", "UP_BUTTON", "UP_SCREEN", "UP_DIAL") else 1.0
            pl.add_mesh(m, color=tcolor(k, g_), opacity=op, smooth_shading=True)
        if state != "up":
            for m in heads: pl.add_mesh(tf_mesh(m, T["HEAD"]), color="#d5dde3", opacity=0.9, smooth_shading=True)
        else:
            for k, (h, sh) in E.items():
                if parts[h][0] == "UP": pl.add_mesh(pvmesh(sh, 1.0), color="#f1c40f" if not k.startswith("CELLS") else "#95a5a6")
        if state == "dep": pl.view_xz(); pl.camera.azimuth = 0
        elif state == "dep3": pl.view_isometric(); pl.camera.azimuth = -35
        elif state == "fold": pl.view_isometric()
        else: pl.view_xz(); pl.camera.azimuth = -25; pl.camera.elevation = 15
        pl.reset_camera(); pl.camera.zoom(1.15 if state != "dep" else 1.3)
    pl.screenshot(os.path.join(OUT, "rf2_upper_views.png")); pl.close()
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
