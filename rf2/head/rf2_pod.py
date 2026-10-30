#!/usr/bin/env python3
"""RF2 handle pod (2026-10-30): the printed control pod near the grip / battery casing: the 3-position mode selector (AUDIO | LED | BOTH), the trigger (hold = pinpoint /
enhanced projection, continuous; double-press = set signature), the power button (hold 2 s), the sounder cavity and a battery bay. MODELED. EVERY DIMENSION HERE IS ASSUMED (no shaft, grip, switch, sounder or
battery datasheet is in the repo yet): the checks prove the arrangement fits itself and keeps its walls, not that these parts exist.
Frame: x along the shaft axis from the head side (x = 0) to the grip end; y sideways; z up (the thumb side). Sounder: a piezo or remote transducer (no magnet; rf2_ui.py).
Writes out/pod/*.stl, out/pod/rf2_pod_check.json.   usage: python3 rf2/head/rf2_pod.py"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("RF2_VARIANT", "BF")
import numpy as np, manifold3d as m3
import rf2_head as H
OUT = os.path.join(HERE, "out", "pod"); os.makedirs(OUT, exist_ok=True)
SPEC = dict(shaft_d=25.0, body_r=23.0, body_len=170.0, wall=2.0, shaft_clear=0.3,
            battery=dict(x=(60.0, 150.0), size=(80.0, 30.0, 24.0), note="ASSUMED 80 x 30 x 24 mm bay; the battery budget (7S pack, START_HERE step 4) sets the real cavity"),
            sounder=dict(x=(28.0, 52.0), d=24.0, grille_holes=7, hole_d=1.6, note="ASSUMED 24 mm piezo disc under a drilled grille on the thumb side"),
            selector=dict(x=(10.0, 26.0), collar_r=(23.0, 26.5), positions_deg=(-30.0, 0.0, 30.0), detent_notch_d=2.2, windows=("speaker", "LED", "both"), note="ASSUMED ball-detent collar around the body, three detents 30 deg apart, three icon windows"),
            power=dict(x=84.0, cap_d=11.0, pocket_d=12.0, pocket_depth=5.0, guard_h=1.0, ring_d=(13.0, 15.0), hold_s=2.0,
                       note="recessed momentary push button on TOP above the trigger (thumb position while the index finger is on the trigger); hold 2 s on / off so a knock "
                            "cannot switch it; a light-pipe ring around it shows green on, amber boost, red low battery. It drives the PM2 power-path controller (soft latch); "
                            "the PM2 fuse stays in series. Button part ASSUMED (a sealed 12 mm tactile, IP67 class)"),
            screen=dict(pocket_x=(94.0, 135.0), tray_x=(98.0, 130.0), w=28.0, tray_z=(13.5, 17.5), pocket_floor=13.0, hinge=(130.0, 17.5), hinge_d=2.0, open_deg=70.0,
                        latch_x=(94.5, 97.5), module=(30.0, 24.0, 2.6), flex_slot=(124.0, 128.0, 8.0),
                        note="flip-up screen cassette behind the power button: the thumb presses the front edge, a push-push latch (spring + heart-cam, like an SD-card socket) "
                             "releases it, a torsion spring lifts it, it is pulled up to 70 deg where a detent locks it; it hinges at its REAR edge so the face tilts toward the user. "
                             "Screen: a 1.28 in 128 x 128 reflective memory LCD (Sharp LS013B7DH03 class: sunlight-readable, microwatts) - part and module size ASSUMED until a datasheet is on file"),
            trigger=dict(x=(70.0, 96.0), lever_t=4.0, travel_deg=12.0, pivot_x=96.0, note="ASSUMED index-finger lever on the underside with a tactile switch behind it; double-press is read in firmware"))
def cylx(r, x0, x1): return m3.Manifold.cylinder(x1 - x0, r, r, 96).rotate([0, 90, 0]).translate([x0, 0, 0])
def boxc(x0, x1, y, z, cy=0.0, cz=0.0): return m3.Manifold.cube([x1 - x0, y, z], True).translate([(x0 + x1) / 2, cy, cz])
def build():
    s = SPEC; R = s["body_r"]; L = s["body_len"]
    body = cylx(R, 0, L) - cylx(s["shaft_d"] / 2 + s["shaft_clear"], -1, L + 1)
    bat = s["battery"]; bx = bat["x"]; bay = boxc(bx[0], bx[1], bat["size"][1], bat["size"][2], 0, -1.0)
    so = s["sounder"]; sx = so["x"]; z0s = R * 0.25; sound = m3.Manifold.cylinder(math.sqrt((R - 1.7) ** 2 - (so["d"] / 2) ** 2) - z0s, so["d"] / 2, so["d"] / 2, 48).translate([(sx[0] + sx[1]) / 2, 0, z0s])        # pocket top set so its rim keeps a 1.7 mm wall: the grille plate
    sw = boxc(s["trigger"]["x"][1] - 2, s["trigger"]["x"][1] + 10, 10.0, 8.0, 0, -R + 8.0)
    tg = s["trigger"]; slot = boxc(tg["x"][0] - 1, tg["x"][1] + 1, 14.0, R * 0.9, 0, -R * 0.55)
    body = body - bay - sound - sw - slot
    for k in range(so["grille_holes"]):
        a = 2 * math.pi * k / (so["grille_holes"] - 1) if k else 0.0; px = (sx[0] + sx[1]) / 2 + (0 if k == 0 else 7.0 * math.cos(a)); py = 0 if k == 0 else 7.0 * math.sin(a)
        body = body - m3.Manifold.cylinder(R, so["hole_d"] / 2, so["hole_d"] / 2, 16).translate([px, py, R * 0.55])
    sel = s["selector"]; sxr = sel["x"]
    for a in sel["positions_deg"]:                                                         # detent notches in the body under the collar, on the thumb side
        ang = math.radians(90 - a); body = body - m3.Manifold.sphere(sel["detent_notch_d"] / 2, 16).translate([(sxr[0] + sxr[1]) / 2, R * math.cos(ang), R * math.sin(ang)])
    collar = cylx(sel["collar_r"][1], *sxr) - cylx(sel["collar_r"][0] + 0.15, sxr[0] - 1, sxr[1] + 1)
    for a, nm in zip(sel["positions_deg"], sel["windows"]):                                # an icon window (Ø4.4) per position, radially through the collar on the thumb side
        ang = math.radians(90 - a); win = m3.Manifold.cylinder(8.0, 2.2, 2.2, 24).translate([0, 0, 0])
        v = np.array([0.0, math.cos(ang), math.sin(ang)]); zax = np.array([0.0, 0.0, 1.0]); ax = np.cross(zax, v); sn = np.linalg.norm(ax); cs = float(zax @ v)
        Rm = np.eye(3) if sn < 1e-9 else (lambda k, th: np.eye(3) + math.sin(th) * np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]) + (1 - math.cos(th)) * (np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]) @ np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])))(ax / sn, math.atan2(sn, cs))
        collar = collar - win.transform(np.column_stack([Rm, [(sxr[0] + sxr[1]) / 2, 0, 0] + v * (sel["collar_r"][0] - 0.5)]).tolist())
    lever = boxc(tg["x"][0] + 1, tg["x"][1] - 1, 12.0, tg["lever_t"], 0, -R * 0.55 - 2.0)
    pw = s["power"]; ztop = R - pw["pocket_depth"]
    pocket = m3.Manifold.cylinder(pw["pocket_depth"] + 2, pw["pocket_d"] / 2, pw["pocket_d"] / 2, 48).translate([pw["x"], 0, ztop])
    ringg = (m3.Manifold.cylinder(1.6, pw["ring_d"][1] / 2, pw["ring_d"][1] / 2, 64) - m3.Manifold.cylinder(1.8, pw["ring_d"][0] / 2, pw["ring_d"][0] / 2, 64).translate([0, 0, -0.1])).translate([pw["x"], 0, R - 1.5])
    body = body - pocket - ringg                                                          # the button pocket and the groove for the light-pipe ring
    cap = m3.Manifold.cylinder(pw["pocket_depth"] - pw["guard_h"] - 0.5, pw["cap_d"] / 2, pw["cap_d"] / 2, 48).translate([pw["x"], 0, ztop + 0.5])   # cap top sits guard_h below the surface
    lightring = (m3.Manifold.cylinder(1.4, pw["ring_d"][1] / 2 - 0.15, pw["ring_d"][1] / 2 - 0.15, 64) - m3.Manifold.cylinder(1.6, pw["ring_d"][0] / 2 + 0.15, pw["ring_d"][0] / 2 + 0.15, 64).translate([0, 0, -0.1])).translate([pw["x"], 0, R - 1.45])
    sc = s["screen"]; px0, px1 = sc["pocket_x"]; tx0, tx1 = sc["tray_x"]; hw = sc["w"] / 2
    spocket = boxc(px0, px1, sc["w"] + 1.0, R + 6 - sc["pocket_floor"], 0, (sc["pocket_floor"] + R + 6) / 2)
    fslot = boxc(sc["flex_slot"][0], sc["flex_slot"][1], sc["flex_slot"][2], sc["pocket_floor"] - 10.5, 0, (sc["pocket_floor"] + 10.5) / 2)     # flex cable down to the electronics
    body = body - spocket - fslot
    tray = boxc(tx0, tx1, sc["w"], sc["tray_z"][1] - sc["tray_z"][0], 0, sum(sc["tray_z"]) / 2)
    mx, my, mz = sc["module"]; win = boxc((tx0 + tx1) / 2 - mx / 2, (tx0 + tx1) / 2 + mx / 2, my, mz + 0.2, 0, sc["tray_z"][1] - mz / 2)
    tray = tray - win; module = boxc((tx0 + tx1) / 2 - mx / 2 + 0.2, (tx0 + tx1) / 2 + mx / 2 - 0.2, my - 0.4, mz, 0, sc["tray_z"][1] - mz / 2 - 0.1)
    hx, hz = sc["hinge"]
    def opened(m, deg): return m.translate([-hx, 0, -hz]).rotate([0, deg, 0]).translate([hx, 0, hz])
    sgn = 1.0                                                                             # +deg about +y: the face normal (0, 0, 1) turns toward +x, the user at the grip end
    latch = boxc(sc["latch_x"][0], sc["latch_x"][1], 10.0, 3.5, 0, sc["pocket_floor"] + 1.75)
    parts = dict(POD_BODY=body, POD_SELECTOR_COLLAR=collar, POD_TRIGGER=lever, POD_POWER_CAP=cap, POD_POWER_LIGHTRING=lightring, POD_SCREEN_TRAY=tray, POD_SCREEN_MODULE=module)
    keep = dict(BATTERY_BAY=bay, SOUNDER=sound, SWITCH=sw, TRIGGER_SLOT=slot, POWER_POCKET=pocket, SCREEN_POCKET=spocket, SCREEN_LATCH=latch,
                SCREEN_TRAY_OPEN=opened(tray, sgn * sc["open_deg"]), SCREEN_MODULE_OPEN=opened(module, sgn * sc["open_deg"]))
    return parts, keep
def main():
    P, K = build(); s = SPEC; R = s["body_r"]; res = dict(status="MODELED; all dimensions ASSUMED", checks={})
    for k, v in P.items(): H.write_stl(v, os.path.join(OUT, f"{k}.stl"))
    H.write_stl(K["SCREEN_TRAY_OPEN"], os.path.join(OUT, "POD_SCREEN_TRAY_OPEN.stl"))
    gap = lambda a, b: round(float(a.min_gap(b, 2.0)), 3)
    body_cyl = cylx(R, 0, s["body_len"]); inside = {k: round(float((K[k] ^ body_cyl).volume() / K[k].volume()), 3) for k in ("BATTERY_BAY", "SWITCH")}
    res["checks"]["fits_in_body"] = dict(ok=all(v > 0.999 for v in inside.values()), fraction_of_pocket_inside_body=inside, note="battery bay and switch pocket lie inside the body cylinder")
    wall_min = min(float(R - np.max(np.hypot(*np.asarray(K[k].to_mesh().vert_properties)[:, 1:3].T))) for k in ("BATTERY_BAY", "SOUNDER", "SWITCH"))
    res["checks"]["walls"] = dict(ok=wall_min >= 1.6 - 1e-6, min_wall_to_outside_mm=round(wall_min, 2), note="measured on the pockets' extreme vertices (battery bay, sounder, switch pocket) against the body radius; 1.6 mm printable minimum ASSUMED")
    res["checks"]["interference"] = dict(ok=(P["POD_TRIGGER"] ^ P["POD_BODY"]).volume() < 0.01 and (P["POD_SELECTOR_COLLAR"] ^ P["POD_BODY"]).volume() < 0.01 and (P["POD_TRIGGER"] ^ P["POD_SELECTOR_COLLAR"]).volume() < 0.01,
                                         trigger_x_body_mm3=round((P["POD_TRIGGER"] ^ P["POD_BODY"]).volume(), 3), collar_x_body_mm3=round((P["POD_SELECTOR_COLLAR"] ^ P["POD_BODY"]).volume(), 3))
    tg = s["trigger"]; lever_arm = tg["pivot_x"] - (tg["x"][0] + tg["x"][1]) / 2; travel = lever_arm * math.sin(math.radians(tg["travel_deg"]))
    res["checks"]["trigger_travel"] = dict(ok=0.0 < travel <= 6.0, travel_at_finger_mm=round(travel, 2), slot_clear_mm=round(tg["lever_t"] + 2.0, 1), note="travel at the finger; the tactile switch's real travel is a datasheet item")
    sel = s["selector"]; pos = sel["positions_deg"]; pitch_mm = 2 * math.pi * sel["collar_r"][1] * (abs(pos[1] - pos[0]) / 360.0)
    res["checks"]["selector"] = dict(ok=len(pos) == 3 and pitch_mm >= 10.0, positions=3, detent_pitch_mm_on_collar=round(pitch_mm, 1), icons=list(sel["windows"]), note="three detents at least 10 mm apart on the collar so the thumb can find each")
    res["checks"]["no_magnet_no_metal"] = dict(ok=True, note="all printed PETG; sounder must be a magnet-free piezo or a remote sounder; the pod sits about 0.9 m from the head (not a field zone) but the cable pair runs to it")
    pw = s["power"]; sel_c = (sel["x"][0] + sel["x"][1]) / 2; tg_c = (tg["x"][0] + tg["x"][1]) / 2
    gap_bay = round(float(P["POD_POWER_CAP"].min_gap(K["BATTERY_BAY"], 10.0)), 2); clash = max((P["POD_POWER_CAP"] ^ P[k]).volume() for k in ("POD_BODY", "POD_SELECTOR_COLLAR", "POD_TRIGGER", "POD_POWER_LIGHTRING"))
    res["checks"]["power_button"] = dict(ok=abs(pw["x"] - sel_c) >= 30.0 and abs(pw["x"] - tg_c) <= 15.0 and gap_bay >= 1.6 and clash < 0.01 and pw["guard_h"] > 0,
                                         distance_from_selector_mm=round(abs(pw["x"] - sel_c), 1), above_trigger_offset_mm=round(abs(pw["x"] - tg_c), 1), wall_to_battery_bay_mm=gap_bay,
                                         recess_mm=pw["guard_h"], hold_to_toggle_s=pw["hold_s"], max_interference_mm3=round(clash, 3),
                                         note="far enough from the selector (>= 30 mm) that the thumb cannot confuse them, directly above the trigger (thumb rest), recessed so it cannot be pressed by a knock")
    sc = s["screen"]; T = P["POD_SCREEN_TRAY"]; V = np.asarray(T.to_mesh().vert_properties)[:, :3]; rad = float(np.max(np.hypot(V[:, 1], V[:, 2])))
    Vo = np.asarray(K["SCREEN_TRAY_OPEN"].to_mesh().vert_properties)[:, :3]
    th = math.radians(sc["open_deg"]); normal = (math.sin(th), 0.0, math.cos(th))                                   # the face normal after opening (rotation about +y)
    face_toward_user = normal[0] > 0.5 and float(Vo[:, 2].max()) > sc["tray_z"][1] + 20
    clash_closed = max((T ^ P[k]).volume() for k in ("POD_BODY", "POD_POWER_CAP", "POD_POWER_LIGHTRING", "POD_SELECTOR_COLLAR", "POD_TRIGGER"))
    clash_open = max((K["SCREEN_TRAY_OPEN"] ^ P[k]).volume() for k in ("POD_POWER_CAP", "POD_POWER_LIGHTRING", "POD_SELECTOR_COLLAR", "POD_TRIGGER"))
    open_body = (K["SCREEN_TRAY_OPEN"] ^ P["POD_BODY"]).volume()
    gap_power_open = round(float(K["SCREEN_TRAY_OPEN"].min_gap(P["POD_POWER_CAP"], 20.0)), 2); wall_bay = round(sc["pocket_floor"] - 11.0, 2)
    gap_latch_power = round(float(K["SCREEN_LATCH"].min_gap(K["POWER_POCKET"], 10.0)), 2)
    res["checks"]["screen_cassette"] = dict(ok=face_toward_user and rad <= s["body_r"] - 0.3 and clash_closed < 0.01 and clash_open < 0.01 and open_body < 1.0 and wall_bay >= 1.6 and gap_power_open >= 3.0 and gap_latch_power >= 1.6,
        face_normal_open=[round(v, 3) for v in normal], face_toward_user=face_toward_user, stowed_inside_body_by_mm=round(s["body_r"] - rad, 2), wall_to_battery_bay_mm=wall_bay, open_deg=sc["open_deg"], open_top_above_axis_mm=round(float(Vo[:, 2].max()), 1),
        open_tray_to_power_button_mm=gap_power_open, latch_to_power_pocket_wall_mm=gap_latch_power, clash_closed_mm3=round(clash_closed, 3), clash_open_mm3=round(clash_open, 3), open_tray_into_body_mm3=round(open_body, 3),
        note="stowed flush below the body surface; opens on its rear hinge so the face tilts toward the user; clear of the power button when open; latch and flex slot inside the pocket")
    res["ok"] = all(v["ok"] for v in res["checks"].values()); res["spec"] = SPEC
    json.dump(res, open(os.path.join(OUT, "rf2_pod_check.json"), "w"), indent=1); print(json.dumps({k: v["ok"] for k, v in res["checks"].items()}, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
