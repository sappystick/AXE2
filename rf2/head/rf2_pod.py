#!/usr/bin/env python3
"""RF2 handle pod v2 (2026-10-30): the printed grip around the shaft tube, now with its electronics placed. MODELED; every dimension marked ASSUMED is one.
v1 fault (CORRECTIONS): the tube runs THROUGH the pod, but v1's battery bay (80 x 30 x 24 mm), sounder pocket and trigger-switch pocket cut into the shaft bore
(its 'fits_in_body' check only tested the outer cylinder, and its magnet check could not fail). v2 keeps the bore clear and checks it.
Layout (x along the tube from the head side, y sideways, z up = thumb side; bore r 12.8 = tube 25 mm + 0.3 mm; outer r 23; wall 1.6 mm):
  HB2-T  top board in the annulus above the bore, x 6-92: two selector-cam switches (x 18), the piezo (x 40, rf2_audio), the RP2354A, the 3.3 V LDO, four
         SN74AHCT1G125 (piezo bridge, LED data / clock), the power switch under the button cap (x 84) with three SK9822 under the light-pipe ring, the screen FPC
         connector at the rear end (x 90).
  HB2-B  bottom board below the bore, x 100-165: the trigger switch at its front (the lever's tail presses it through a sealed boot), the RS-485 transceiver,
         the TPD4E1B06 and the bundle connector J1 next to the grommeted exit hole in the tube.
  FLEX   HB2 is one rigid-flex: a side flex arm (x 90-102) wraps around the -y side of the bore from T's edge to B's edge; no board-to-board connector.
  Inputs: four identical C&K KSC2 TE (IP67): power, trigger, selector A / B. The selector collar carries two inward cam lobes at +-46.7 deg; at -30 / +30 deg a
         lobe stands over the plunger at +16.7 / -16.7 deg (vertical plungers through a sealed membrane); at 0 deg both are free. No magnet in the pod.
  Screen cassette as v1, pocket floor raised to keep 1.2 mm of wall over the bore (tray 26 mm wide); its FPC runs on the pocket floor under the tray, from the
         hinge at the rear to a slot in the pocket's front wall and into J_SCR on HB2-T.
  The battery left the pod: it is the PACK module under the forearm (rf2_system.py).
Writes out/pod/*.stl, out/pod/rf2_pod_check.json, out/pod/rf2_pod_layout.png.   usage: python3 rf2/head/rf2_pod.py"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("RF2_VARIANT", "BF")
import numpy as np, manifold3d as m3
import rf2_head as H
OUT = os.path.join(HERE, "out", "pod"); os.makedirs(OUT, exist_ok=True)
SPEC = dict(shaft_d=25.0, body_r=23.0, body_len=170.0, wall=1.6, shaft_clear=0.3, bore_wall_min=1.2,
            selector=dict(x=(10.0, 26.0), collar_r=(23.0, 26.5), positions_deg=(-30.0, 0.0, 30.0), detent_notch_d=2.2, windows=("speaker", "LED", "both"),
                          plunger_d=3.0, lobe_deg=(46.7, -46.7), lobe_w_mm=3.0, note="ball-detent collar, three detents 30 deg apart; two cam lobes press the selector switches"),
            power=dict(x=84.0, cap_d=11.0, pocket_d=12.0, pocket_depth=5.0, guard_h=1.0, ring_d=(13.0, 15.0), hold_s=2.0,
                       note="recessed button on TOP above the trigger; hold 2 s: the press wakes the BQ76952 (TS2) in the pack, the pod MCU decides on / off; light-pipe ring "
                            "over three SK9822 (green on, amber boost, red low battery)"),
            screen=dict(pocket_x=(94.0, 135.0), tray_x=(98.0, 130.0), w=26.0, tray_z=(14.5, 18.5), pocket_floor=14.0, hinge=(130.0, 18.5), hinge_d=2.0, open_deg=70.0,
                        latch_x=(94.5, 97.5), module=(30.0, 24.0, 2.6), fpc_slot=(92.0, 94.0, 10.0, 14.0, 14.6),
                        note="flip-up cassette (push-push latch, torsion spring, 70 deg detent, rear hinge); 1.28 in memory LCD (Sharp LS013B7DH03 class, ASSUMED)"),
            trigger=dict(x=(70.0, 96.0), lever_t=4.0, travel_deg=12.0, pivot_x=96.0, slot_z=(-24.0, -15.5), lever_z=(-21.5, -17.5),
                         note="index-finger lever recessed in a slot under the bore; its tail behind the pivot presses the trigger switch on HB2-B through a boot"),
            boards=dict(T=dict(x=(6.0, 92.0), z=(13.6, 14.6), w=22.0, side=+1), B=dict(x=(100.0, 165.0), z=(-14.6, -13.6), w=22.0, side=-1),
                        flex=dict(x=(90.0, 102.0), r=(16.8, 17.0), deg=(135.0, 225.0))),
            tube_exit=dict(x=157.0, deg=200.0, d=6.0, note="grommeted hole in the tube wall beside HB2-B; the pod tap of the bundle reaches J1 in a short pigtail"))
# parts: board, ref, x0, x1, y0, y1, height above the board face (outward), what (footprints and heights ASSUMED unless the datasheet is on file)
PARTS = [("T", "SW_SEL_A", 14.85, 21.15, 3.45, 9.75, 3.5, "C&K KSC2 TE 6.2 x 6.3 x 3.5 (datasheet)"), ("T", "SW_SEL_B", 14.85, 21.15, -9.75, -3.45, 3.5, "C&K KSC2 TE"),
         ("T", "LS1", 34.0, 46.0, -6.0, 6.0, 3.0, "Murata PKLCS1212E4001-R1 12 x 12 x 3 (datasheet)"),
         ("T", "U22", 47.5, 50.5, 3.5, 6.5, 1.45, "SN74AHCT1G125 SOT-23-5 (piezo leg A)"), ("T", "U23", 47.5, 50.5, -6.5, -3.5, 1.45, "SN74AHCT1G125 (piezo leg B)"),
         ("T", "U20", 52.5, 59.5, -3.5, 3.5, 0.9, "RP2354A, 7 x 7 QFN (ASSUMED)"), ("T", "U21", 62.0, 65.0, -1.5, 1.5, 1.45, "TLV755P SOT-23-5"),
         ("T", "U24", 67.5, 70.5, 3.0, 6.0, 1.45, "SN74AHCT1G125 (LED data)"), ("T", "U25", 67.5, 70.5, -6.0, -3.0, 1.45, "SN74AHCT1G125 (LED clock)"),
         ("T", "SW_PWR", 80.85, 87.15, -3.15, 3.15, 3.5, "C&K KSC2 TE under the cap"),
         ("T", "LED1", 83.0, 85.0, 6.0, 8.0, 0.9, "SK9822-EC20 2 x 2 (light ring)"), ("T", "LED2", 83.0, 85.0, -8.0, -6.0, 0.9, "SK9822-EC20"), ("T", "LED3", 76.0, 78.0, -1.0, 1.0, 0.9, "SK9822-EC20"),
         ("T", "J_SCR", 88.5, 91.5, -4.5, 4.5, 2.0, "screen FPC connector (ASSUMED 10-pin 0.5 mm)"),
         ("B", "SW_TRG", 100.5, 106.8, -3.15, 3.15, 3.5, "C&K KSC2 TE (trigger)"), ("B", "U26", 140.0, 143.0, -1.5, 1.5, 1.1, "RS-485 transceiver MSOP-8 (ASSUMED)"),
         ("B", "U27", 145.5, 147.5, -0.8, 0.8, 0.6, "TPD4E1B06 (package ASSUMED 2 x 1.6)"), ("B", "J1", 150.0, 164.0, -2.25, 2.25, 3.0, "bundle connector, 10-pin wire-to-board (ASSUMED)")]
def cylx(r, x0, x1): return m3.Manifold.cylinder(x1 - x0, r, r, 96).rotate([0, 90, 0]).translate([x0, 0, 0])
def boxc(x0, x1, y, z, cy=0.0, cz=0.0): return m3.Manifold.cube([x1 - x0, y, z], True).translate([(x0 + x1) / 2, cy, cz])
def boxz(x0, x1, y0, y1, z0, z1): return m3.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])
def r_bore(): return SPEC["shaft_d"] / 2 + SPEC["shaft_clear"]
def part_box(p):
    b = SPEC["boards"][p[0]]; z0 = b["z"][1] if b["side"] > 0 else b["z"][0] - p[6]; return boxz(p[2], p[3], p[4], p[5], z0, z0 + p[6])
def board_box(k):
    b = SPEC["boards"][k]; return boxz(b["x"][0], b["x"][1], -b["w"] / 2, b["w"] / 2, *b["z"])
def flex_band():
    f = SPEC["boards"]["flex"]; segs = []; a0, a1 = map(math.radians, f["deg"]); n = 12; rm = sum(f["r"]) / 2; t = f["r"][1] - f["r"][0]
    for k in range(n):
        a = a0 + (a1 - a0) * (k + 0.5) / n; L = rm * (a1 - a0) / n * 1.05
        segs.append(m3.Manifold.cube([f["x"][1] - f["x"][0], t, L], True).rotate([math.degrees(a) - 90, 0, 0]).translate([(f["x"][0] + f["x"][1]) / 2, rm * math.cos(a), rm * math.sin(a)]))
    return m3.Manifold.batch_boolean(segs, m3.OpType.Add)
def plunger_axis_y(): return (SPEC["boards"]["T"]["z"][1] + 3.5) * math.tan(math.radians(20.0))     # where a vertical plunger meets the switch top
def build():
    s = SPEC; R = s["body_r"]; L = s["body_len"]; rb = r_bore()
    bore = cylx(rb, -1, L + 1); body = cylx(R, 0, L) - bore
    tg = s["trigger"]; slot = boxz(tg["x"][0] - 1, tg["x"][1] + 1, -7.0, 7.0, tg["slot_z"][0], tg["slot_z"][1])
    boot = boxz(tg["pivot_x"], 100.6, -2.0, 2.0, -18.6, -15.6)                                               # sealed boot passage from the lever tail to SW_TRG
    lever = boxz(tg["x"][0] + 1, tg["x"][1] - 1, -6.0, 6.0, *tg["lever_z"])
    # electronics cavity: the annulus regions the boards and parts occupy (the body is printed in halves around them, then potted / sealed)
    elec = [board_box("T"), board_box("B")] + [part_box(p) for p in PARTS]; flex = flex_band()
    cavity = m3.Manifold.batch_boolean([e for e in elec] + [flex], m3.OpType.Add)
    # piezo sound holes: centre + 4 at 3 mm, through the top wall above LS1
    holes = [m3.Manifold.cylinder(R, 0.8, 0.8, 16).translate([40.0 + dx, dy, SPEC["boards"]["T"]["z"][1] + 3.0]) for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3))]
    # selector plungers: vertical through the wall above SW_SEL_A / B
    yp = (PARTS[0][4] + PARTS[0][5]) / 2; pl = s["selector"]["plunger_d"] / 2
    plungers = [m3.Manifold.cylinder(R, pl, pl, 24).translate([18.0, sgn * yp, s["boards"]["T"]["z"][1] + 3.5]) for sgn in (1, -1)]
    pw = s["power"]; ztop = R - pw["pocket_depth"]
    pocket = m3.Manifold.cylinder(pw["pocket_depth"] + 2, pw["pocket_d"] / 2, pw["pocket_d"] / 2, 48).translate([pw["x"], 0, ztop])
    ringg = (m3.Manifold.cylinder(1.6, pw["ring_d"][1] / 2, pw["ring_d"][1] / 2, 64) - m3.Manifold.cylinder(1.8, pw["ring_d"][0] / 2, pw["ring_d"][0] / 2, 64).translate([0, 0, -0.1])).translate([pw["x"], 0, R - 1.5])
    lightpipe_well = m3.Manifold.cylinder(R - 1.5 - 15.5, pw["ring_d"][1] / 2, pw["ring_d"][1] / 2, 64).translate([pw["x"], 0, 15.5]) - m3.Manifold.cylinder(R, pw["ring_d"][0] / 2, pw["ring_d"][0] / 2, 64).translate([pw["x"], 0, 15.0])
    cap = m3.Manifold.cylinder(pw["pocket_depth"] - pw["guard_h"] - 0.5, pw["cap_d"] / 2, pw["cap_d"] / 2, 48).translate([pw["x"], 0, ztop + 0.5])
    lightring = (m3.Manifold.cylinder(1.4, pw["ring_d"][1] / 2 - 0.15, pw["ring_d"][1] / 2 - 0.15, 64) - m3.Manifold.cylinder(1.6, pw["ring_d"][0] / 2 + 0.15, pw["ring_d"][0] / 2 + 0.15, 64).translate([0, 0, -0.1])).translate([pw["x"], 0, R - 1.45])
    sc = s["screen"]; px0, px1 = sc["pocket_x"]; tx0, tx1 = sc["tray_x"]
    spocket = boxc(px0, px1, sc["w"] + 1.0, R + 6 - sc["pocket_floor"], 0, (sc["pocket_floor"] + R + 6) / 2)
    f = sc["fpc_slot"]; fslot = boxz(f[0], f[1], -f[2] / 2, f[2] / 2, f[3], f[4])                          # FPC slot through the pocket's front wall
    sel = s["selector"]; sxr = sel["x"]
    body = body - slot - boot - cavity - spocket - fslot - pocket - ringg - lightpipe_well
    for h in holes + plungers: body = body - h
    for a in sel["positions_deg"]:
        ang = math.radians(90 - a); body = body - m3.Manifold.sphere(sel["detent_notch_d"] / 2, 16).translate([(sxr[0] + sxr[1]) / 2, R * math.cos(ang), R * math.sin(ang)])
    collar = cylx(sel["collar_r"][1], *sxr) - cylx(sel["collar_r"][0] + 0.15, sxr[0] - 1, sxr[1] + 1)
    tray = boxc(tx0, tx1, sc["w"], sc["tray_z"][1] - sc["tray_z"][0], 0, sum(sc["tray_z"]) / 2)
    mx, my, mz = sc["module"]; win = boxc((tx0 + tx1) / 2 - mx / 2, (tx0 + tx1) / 2 + mx / 2, my, mz + 0.2, 0, sc["tray_z"][1] - mz / 2)
    tray = tray - win; module = boxc((tx0 + tx1) / 2 - mx / 2 + 0.2, (tx0 + tx1) / 2 + mx / 2 - 0.2, my - 0.4, mz, 0, sc["tray_z"][1] - mz / 2 - 0.1)
    hx, hz = sc["hinge"]
    def opened(m, deg): return m.translate([-hx, 0, -hz]).rotate([0, deg, 0]).translate([hx, 0, hz])
    latch = boxc(sc["latch_x"][0], sc["latch_x"][1], 10.0, 3.5, 0, sc["pocket_floor"] + 1.75)
    boards = m3.Manifold.batch_boolean([board_box("T"), board_box("B"), flex], m3.OpType.Add)
    parts3d = m3.Manifold.batch_boolean([part_box(p) for p in PARTS], m3.OpType.Add)
    P = dict(POD_BODY=body, POD_SELECTOR_COLLAR=collar, POD_TRIGGER=lever, POD_POWER_CAP=cap, POD_POWER_LIGHTRING=lightring, POD_SCREEN_TRAY=tray, POD_SCREEN_MODULE=module,
             POD_HB2_BOARDS=boards, POD_HB2_PARTS=parts3d)
    K = dict(BORE=bore, TRIGGER_SLOT=slot, BOOT=boot, POWER_POCKET=pocket, SCREEN_POCKET=spocket, FPC_SLOT=fslot, SCREEN_LATCH=latch, FLEX=flex, HOLES=holes, PLUNGERS=plungers,
             SCREEN_TRAY_OPEN=opened(tray, sc["open_deg"]), SCREEN_MODULE_OPEN=opened(module, sc["open_deg"]))
    return P, K
def main():
    P, K = build(); s = SPEC; R = s["body_r"]; rb = r_bore(); res = dict(status="MODELED; dimensions ASSUMED unless a datasheet is named", checks={}, parts=[list(p) for p in PARTS])
    for k, v in P.items(): H.write_stl(v, os.path.join(OUT, f"{k}.stl"))
    H.write_stl(K["SCREEN_TRAY_OPEN"], os.path.join(OUT, "POD_SCREEN_TRAY_OPEN.stl"))
    vol = lambda a, b: float((a ^ b).volume())
    bore = K["BORE"]
    intr = {k: round(vol(K[k], bore), 3) for k in ("TRIGGER_SLOT", "BOOT", "POWER_POCKET", "SCREEN_POCKET", "FPC_SLOT", "SCREEN_LATCH", "FLEX")}
    intr.update(HB2_BOARDS=round(vol(P["POD_HB2_BOARDS"], bore), 3), HB2_PARTS=round(vol(P["POD_HB2_PARTS"], bore), 3), LEVER=round(vol(P["POD_TRIGGER"], bore), 3))
    res["checks"]["nothing_in_the_bore"] = dict(ok=max(intr.values()) < 0.01, intrusion_mm3=intr, note="the v1 fault: pockets cut into the tube's bore")
    def rad_range(m):
        V = np.asarray(m.to_mesh().vert_properties)[:, :3]; r = np.hypot(V[:, 1], V[:, 2]); return float(r.min()), float(r.max())
    ri = R - s["wall"]; el = {"HB2_BOARDS": P["POD_HB2_BOARDS"], "HB2_PARTS": P["POD_HB2_PARTS"]}
    gaps = {k: round(float(v.min_gap(bore, 5.0)), 2) for k, v in el.items()}
    rmax = {k: round(rad_range(v)[1], 2) for k, v in el.items()}
    res["checks"]["electronics_in_the_annulus"] = dict(ok=all(g >= 0.5 for g in gaps.values()) and all(r <= ri + 1e-6 for r in rmax.values()), clearance_to_bore_mm=gaps, max_radius_mm=rmax, inner_wall_r=ri,
                                                       note="boards and part envelopes >= 0.5 mm from the bore and inside the 1.6 mm outer wall")
    ov = []
    for i, a in enumerate(PARTS):
        for b in PARTS[i + 1:]:
            if a[0] == b[0] and min(a[3], b[3]) - max(a[2], b[2]) > -0.3 and min(a[5], b[5]) - max(a[4], b[4]) > -0.3: ov.append((a[1], b[1]))
    onb = [p[1] for p in PARTS if not (s["boards"][p[0]]["x"][0] <= p[2] and p[3] <= s["boards"][p[0]]["x"][1] and -s["boards"][p[0]]["w"] / 2 <= p[4] and p[5] <= s["boards"][p[0]]["w"] / 2)]
    res["checks"]["parts_placed"] = dict(ok=not ov and not onb, overlaps_under_0p3mm=ov, off_board=onb, n_parts=len(PARTS))
    keep = {k: K[k] for k in ("TRIGGER_SLOT", "SCREEN_POCKET", "POWER_POCKET", "BOOT")}
    fg = {k: round(float(K["FLEX"].min_gap(v, 5.0)), 2) for k, v in keep.items()}
    res["checks"]["flex_route"] = dict(ok=min(fg.values()) >= 1.0 and rad_range(K["FLEX"])[1] <= ri, gap_to_voids_mm=fg, note="side flex arm around the bore, >= 1 mm of printed wall to every void")
    res["checks"]["interference"] = dict(ok=vol(P["POD_TRIGGER"], P["POD_BODY"]) < 0.01 and vol(P["POD_SELECTOR_COLLAR"], P["POD_BODY"]) < 0.01 and vol(P["POD_HB2_PARTS"], P["POD_BODY"]) < 0.01 and vol(P["POD_HB2_BOARDS"], P["POD_BODY"]) < 0.01,
                                         note="lever, collar, boards and parts against the printed body")
    tg = s["trigger"]; arm = tg["pivot_x"] - (tg["x"][0] + tg["x"][1]) / 2; travel = arm * math.sin(math.radians(tg["travel_deg"]))
    wall_slot = round(-tg["slot_z"][1] - rb, 2)
    res["checks"]["trigger"] = dict(ok=0.0 < travel <= 6.0 and wall_slot >= s["bore_wall_min"], travel_at_finger_mm=round(travel, 2), wall_slot_to_bore_mm=wall_slot)
    sel = s["selector"]; yp = (PARTS[0][4] + PARTS[0][5]) / 2; zs = s["boards"]["T"]["z"][1] + 3.5
    plunger_deg = math.degrees(math.atan2(yp, math.sqrt(R ** 2 - yp ** 2)))                                       # where the vertical plunger exits the surface
    pls = [plunger_deg, -plunger_deg]; sep_need = math.degrees((sel["plunger_d"] + sel["lobe_w_mm"]) / sel["collar_r"][0])
    table = {}; ok_sel = True
    for pos in sel["positions_deg"]:
        lobes = [l + pos for l in sel["lobe_deg"]]; pressed = [any(abs(l - p) < 1.0 for l in lobes) for p in pls]
        free_sep = min([abs(l - p) for l in lobes for p in pls if abs(l - p) >= 1.0] or [99.0]); table[str(pos)] = dict(pressed_A_B=pressed, min_sep_free_deg=round(free_sep, 1))
        want = {-30.0: [True, False], 0.0: [False, False], 30.0: [False, True]}[pos]          # -30: A (+y plunger), +30: B
        ok_sel &= (pressed == want) and free_sep >= sep_need
    pitch = 2 * math.pi * sel["collar_r"][1] * (30.0 / 360.0)
    res["checks"]["selector"] = dict(ok=ok_sel and pitch >= 10.0, plunger_deg=[round(v, 1) for v in pls], needed_sep_deg=round(sep_need, 1), states=table, detent_pitch_mm=round(pitch, 1),
                                     note="one lobe over one plunger at each side detent, both free at the centre; >= one plunger + lobe width apart otherwise")
    pw = s["power"]; cap_bottom = R - pw["pocket_depth"] + 0.5; sw_top = s["boards"]["T"]["z"][1] + 3.5
    res["checks"]["power_button"] = dict(ok=0.0 <= cap_bottom - sw_top <= 0.8 and abs(pw["x"] - (s["trigger"]["x"][0] + s["trigger"]["x"][1]) / 2) <= 15.0 and pw["guard_h"] > 0,
                                         cap_to_switch_gap_mm=round(cap_bottom - sw_top, 2), above_trigger_offset_mm=round(abs(pw["x"] - (s["trigger"]["x"][0] + s["trigger"]["x"][1]) / 2), 1),
                                         note="the cap sits 0-0.8 mm above the KSC2 TE actuator (pre-travel); recessed 1 mm against knocks")
    hole_c = [(40.0 + dx, dy) for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3))]; ls = PARTS[2]
    res["checks"]["piezo_window"] = dict(ok=all(ls[2] + 1 <= x <= ls[3] - 1 and ls[4] + 1 <= y <= ls[5] - 1 for x, y in hole_c) and vol(m3.Manifold.batch_boolean(K["HOLES"], m3.OpType.Add), P["POD_HB2_PARTS"]) < 0.01,
                                         holes=len(hole_c), note="five 1.6 mm holes over the piezo's port, through the top wall only")
    sc = s["screen"]; T = P["POD_SCREEN_TRAY"]; V = np.asarray(T.to_mesh().vert_properties)[:, :3]; rad = float(np.max(np.hypot(V[:, 1], V[:, 2])))
    Vo = np.asarray(K["SCREEN_TRAY_OPEN"].to_mesh().vert_properties)[:, :3]; th = math.radians(sc["open_deg"]); normal = (math.sin(th), 0.0, math.cos(th))
    face_toward_user = normal[0] > 0.5 and float(Vo[:, 2].max()) > sc["tray_z"][1] + 20
    clash_closed = max(vol(T, P[k]) for k in ("POD_BODY", "POD_POWER_CAP", "POD_POWER_LIGHTRING", "POD_SELECTOR_COLLAR", "POD_TRIGGER"))
    clash_open = max(vol(K["SCREEN_TRAY_OPEN"], P[k]) for k in ("POD_POWER_CAP", "POD_POWER_LIGHTRING", "POD_SELECTOR_COLLAR", "POD_TRIGGER"))
    gap_power_open = round(float(K["SCREEN_TRAY_OPEN"].min_gap(P["POD_POWER_CAP"], 20.0)), 2); wall_bore = round(sc["pocket_floor"] - rb, 2)
    fpc_gap = round(sc["tray_z"][0] - sc["pocket_floor"], 2)
    res["checks"]["screen_cassette"] = dict(ok=face_toward_user and rad <= R - 0.3 and clash_closed < 0.01 and clash_open < 0.01 and wall_bore >= s["bore_wall_min"] and gap_power_open >= 3.0 and fpc_gap >= 0.3,
        face_normal_open=[round(v, 3) for v in normal], stowed_inside_body_by_mm=round(R - rad, 2), wall_over_bore_mm=wall_bore, fpc_gap_under_tray_mm=fpc_gap,
        open_tray_to_power_button_mm=gap_power_open, clash_closed_mm3=round(clash_closed, 3), clash_open_mm3=round(clash_open, 3))
    res["checks"]["no_magnet"] = dict(ok=not any("magnet" in p[7].lower() and "magnet-free" not in p[7].lower() for p in PARTS), note="selector by cam and switches; piezo magnet-free (rf2_system: REF3 coupling)")
    ex = s["tube_exit"]; j1 = next(p for p in PARTS if p[1] == "J1"); jc = np.array([(j1[2] + j1[3]) / 2, 0.0, s["boards"]["B"]["z"][0] - j1[6]])
    ec = np.array([ex["x"], s["shaft_d"] / 2 * math.cos(math.radians(ex["deg"])), s["shaft_d"] / 2 * math.sin(math.radians(ex["deg"]))])
    res["checks"]["bundle_tap"] = dict(ok=float(np.linalg.norm(jc - ec)) <= 25.0, exit_to_J1_mm=round(float(np.linalg.norm(jc - ec)), 1), note="short pigtail from the tube's grommeted hole to J1")
    res["ok"] = all(v["ok"] for v in res["checks"].values()); res["spec"] = SPEC
    json.dump(res, open(os.path.join(OUT, "rf2_pod_check.json"), "w"), indent=1); figure(res)
    print(json.dumps({k: v["ok"] for k, v in res["checks"].items()}, indent=1)); return res
def figure(res):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    s = SPEC; R = s["body_r"]; rb = r_bore(); fig = plt.figure(figsize=(14, 7.5))
    for k, (side, title) in enumerate((("T", "HB2-T (top, seen from above)"), ("B", "HB2-B (bottom, seen from below)"))):
        ax = fig.add_subplot(2, 2, 1 + 2 * k); b = s["boards"][side]
        ax.add_patch(plt.Rectangle((0, -R), s["body_len"], 2 * R, fc="none", ec="#aaa", ls="--")); ax.add_patch(plt.Rectangle((b["x"][0], -b["w"] / 2), b["x"][1] - b["x"][0], b["w"], fc="#2a7a2a", alpha=0.25, ec="#2a7a2a"))
        for p in PARTS:
            if p[0] != side: continue
            y0, y1 = (p[4], p[5]) if side == "T" else (-p[5], -p[4]); ax.add_patch(plt.Rectangle((p[2], y0), p[3] - p[2], y1 - y0, fc="#ffcc66", ec="k", lw=0.6)); ax.text(p[2], y1 + 0.6, p[1], fontsize=6)
        if side == "T":
            sc = s["screen"]; ax.add_patch(plt.Rectangle((sc["pocket_x"][0], -sc["w"] / 2 - 0.5), sc["pocket_x"][1] - sc["pocket_x"][0], sc["w"] + 1, fc="#88aaff", alpha=0.25)); ax.text(100, 0, "screen pocket", fontsize=7)
            ax.add_patch(plt.Circle((s["power"]["x"], 0), s["power"]["ring_d"][1] / 2, fc="none", ec="#d62728")); ax.add_patch(plt.Rectangle((s["selector"]["x"][0], -R), 16, 2 * R, fc="#9467bd", alpha=0.12)); ax.text(10, R - 4, "collar", fontsize=7)
        else:
            tg = s["trigger"]; ax.add_patch(plt.Rectangle((tg["x"][0] - 1, -7), tg["x"][1] - tg["x"][0] + 2, 14, fc="#888", alpha=0.3)); ax.text(72, 0, "trigger slot", fontsize=7)
        ax.set_xlim(-2, 172); ax.set_ylim(-R - 2, R + 2); ax.set_aspect("equal"); ax.set_title(title, fontsize=9); ax.set_xlabel("x along the tube, mm (head side at 0)")
    for k, xc in enumerate((40.0, 84.0)):
        ax = fig.add_subplot(2, 2, 2 + 2 * k); th = np.linspace(0, 2 * np.pi, 200)
        ax.fill(R * np.cos(th), R * np.sin(th), color="#ddd"); ax.fill((R - s["wall"]) * np.cos(th), (R - s["wall"]) * np.sin(th), color="#f6f6f6"); ax.fill(rb * np.cos(th), rb * np.sin(th), color="#555"); ax.text(-5, -1, "tube", color="w", fontsize=7)
        for side in ("T", "B"):
            b = s["boards"][side]
            if b["x"][0] <= xc <= b["x"][1]:
                ax.add_patch(plt.Rectangle((-b["w"] / 2, b["z"][0]), b["w"], 1.0, fc="#2a7a2a"))
                for p in PARTS:
                    if p[0] == side and p[2] <= xc <= p[3]:
                        z0 = b["z"][1] if b["side"] > 0 else b["z"][0] - p[6]; ax.add_patch(plt.Rectangle((p[4], z0), p[5] - p[4], p[6], fc="#ffcc66", ec="k", lw=0.6)); ax.text(p[4], z0 + p[6] + 0.3, p[1], fontsize=6)
        f = s["boards"]["flex"]
        if f["x"][0] <= xc <= f["x"][1]:
            a = np.radians(np.linspace(*f["deg"], 50)); ax.plot(16.9 * np.cos(a), 16.9 * np.sin(a), color="#2a7a2a", lw=2)
        ax.set_aspect("equal"); ax.set_xlim(-R - 1, R + 1); ax.set_ylim(-R - 1, R + 1); ax.set_title(f"section at x = {xc:.0f} mm (looking toward the head)", fontsize=9)
    fig.suptitle("RF2 handle pod v2: HB2 rigid-flex placed in the annulus around the tube (MODELED; footprints ASSUMED unless named)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rf2_pod_layout.png"), dpi=120); plt.close(fig)
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
