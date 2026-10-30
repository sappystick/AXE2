#!/usr/bin/env python3
"""RF2 construct (2026-10-30): one assembled 3-D model of the option B clean-sheet head (variant BF) with the harness. MODELED / tool-checked.
Builds on rf2_head.py's solids (manifold3d) and adds what the housing did not have:
  - fin boards as real 1.0 mm slabs, the TXF pad positions from the built board (out/TXF/txf_check.json), the coil's lead ends from the coil SPEC
  - the harness: four wires from TXF (coil litz A / B to the coil's lead slot, shaft cable A / B up through the gland), each a polyline (pad face, 3 mm straight
    strain relief, a lane in the sector gap, the destination) with the FEP outer diameters of the SPEC; lane offset and height are searched so no two wires
    are closer than 0.3 mm and each keeps 0.3 mm to the fins, rails, floor, walls and the lid
  - printed wire saddles: posts from the floor every <= 22 mm with a half-round notch for the wire (molded-in routing)
  - potting cavities per sector (free volume minus every solid and wire), filled from the hub bore
Checks (all measured on the solids): wire-to-solid and wire-to-wire clearance, wire ends on their pads, bend turn angles, no wire sweeps round the axis (rule 5),
wire lengths, loop area of each coil lead pair, saddle notches seat their wire. Writes out_BF/construct/{assembly.glb, assembly_manifest.json, harness.json, construct_check.json}.
Placeholders (PENDING, not checked): the MP1 v2 sense wires (MP1 v2 fin not built), the MP1 LV output flex, AB1 / CB1D fins (Phase C).
usage: python3 rf2/head/rf2_construct.py"""
import os, sys, json, math, itertools
os.environ["RF2_VARIANT"] = "BF"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import manifold3d as m3
import rf2_head as H
S = H.SPEC; OUT = os.path.join(H.OUT, "construct"); os.makedirs(OUT, exist_ok=True)
CLEAR = 0.3
def seg_dist(p0, p1, q0, q1):
    """minimum distance between segments p0p1 and q0q1 (3-D)"""
    d1, d2, r = p1 - p0, q1 - q0, p0 - q0; a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-12 and e < 1e-12: return float(np.linalg.norm(r))
    if a < 1e-12: s, t = 0.0, np.clip(f / e, 0, 1)
    else:
        c = d1 @ r
        if e < 1e-12: t, s = 0.0, np.clip(-c / a, 0, 1)
        else:
            b = d1 @ d2; den = a * e - b * b
            s = np.clip((b * f - c * e) / den, 0, 1) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0: t, s = 0.0, np.clip(-c / a, 0, 1)
            elif t > 1: t, s = 1.0, np.clip((b - c) / a, 0, 1)
    return float(np.linalg.norm((p0 + d1 * s) - (q0 + d2 * t)))
def poly_dist(A, B): return min(seg_dist(A[i], A[i + 1], B[j], B[j + 1]) for i in range(len(A) - 1) for j in range(len(B) - 1))
def capsule(a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float); v = b - a; L = np.linalg.norm(v)
    cyl = m3.Manifold.cylinder(L, r, r, 24); z = v / L; x = np.cross([0, 0, 1.0], z)
    if np.linalg.norm(x) < 1e-9: R = np.eye(3) if z[2] > 0 else np.diag([1, -1, -1.0])
    else:
        x /= np.linalg.norm(x); y = np.cross(z, x); R = np.column_stack([x, y, z])
    M = np.column_stack([R, a]); cyl = cyl.transform(M.tolist())
    return cyl + m3.Manifold.sphere(r, 24).translate(a.tolist()) + m3.Manifold.sphere(r, 24).translate(b.tolist())
def wire_solid(P, r):
    out = None
    for a, b in zip(P[:-1], P[1:]):
        c = capsule(a, b, r); out = c if out is None else out + c
    return out
def main():
    P = H.parts(); co = S["coil"]; ch = S["channel"]; sh = S["shell"]; g = S["gland"]; wm = S["materials"]
    txf = json.load(open(os.path.join(H.HERE, "out", "TXF", "txf_check.json")))["placement_in_head"]; pad = {p["ref"]: p for p in txf}
    fin = next(v for v in S["boards_inner"].values() if v.get("kind") == "fin" and abs(v["deg"] - 186.0) < 1e-6); th = math.radians(186.0)
    u = np.array([math.cos(th), math.sin(th), 0.0]); t = np.array([-math.sin(th), math.cos(th), 0.0]); n = -t        # n: from the fin toward the 178 deg gap
    def padpt(ref):
        p = pad[ref]; return np.array([p["x"], p["y"], p["z"]]) + n * (fin["t"] / 2)
    od = dict(coil=wm["coil_wire_od_mm"], cable=2.4, sense=0.9)                                                    # cable / sense OD ASSUMED (FEP hookup wire, vendor to confirm)
    top_row = co["row0_z"] + (co["rows"] - 1) * co.get("row_pitch", co["pitch"])
    he = math.radians(ch["lead_exit_deg"]); ue = np.array([math.cos(he), math.sin(he), 0.0]); te = np.array([-math.sin(he), math.cos(he), 0.0])
    lid_u = sh["lid_z"][0]; gc = np.array([g["c"][0], g["c"][1], 0.0])
    wires = {                                             # name: (pad, r_wire, dest list, kind)
        "COIL_A": ("JCA", od["coil"] / 2, [ue * (ch["inner_wall_r"][0] - 1.5) + te * (-1.2) + np.array([0, 0, co["row0_z"] + CLEAR])], "coil litz, start (bottom row, lifted 0.3 mm off the floor after it leaves the winding)"),
        "COIL_B": ("JCB", od["coil"] / 2, [ue * (ch["inner_wall_r"][0] - 1.5) + te * (1.2) + np.array([0, 0, top_row])], "coil litz, end (top row)"),
        "CABLE_A": ("JKA", od["cable"] / 2, [gc + te * (-1.7) + np.array([0, 0, lid_u - 0.6]), gc + te * (-1.7) + np.array([0, 0, sh["lid_z"][1] + 2.0])], "shaft HV pair, up through the gland"),
        "CABLE_B": ("JKB", od["cable"] / 2, [gc + te * (1.7) + np.array([0, 0, lid_u - 0.6]), gc + te * (1.7) + np.array([0, 0, sh["lid_z"][1] + 2.0])], "shaft HV pair, up through the gland")}
    fixed = {k: [] for k in wires}
    solids = {k: v for k, v in P.items() if not k.startswith("ENV_") and k not in ("REF3_FORMER", "LITZ")}
    # fin boards as real slabs (the fin outline minus nothing: 1.0 mm FR4 within the slot)
    for k, v in S["boards_inner"].items():
        if v.get("kind") == "fin":
            r0, r1 = v["r"]; slab = H.m3.Manifold.cube([r1 - r0, v["t"], v["z"][1] - v["z"][0]], True).translate([(r0 + r1) / 2, 0, (v["z"][0] + v["z"][1]) / 2]).rotate([0, 0, v["deg"]])
            solids["BOARD_" + k] = slab
    # lane search (greedy, wire by wire, farther pad first so outer wires take lanes nearer the fin)
    lanes = [(float(d), float(z)) for d in np.arange(1.6, 11.1, 0.8) for z in np.arange(6.0, 12.1, 0.6)]
    order = sorted(wires, key=lambda k: -float(np.hypot(pad[wires[k][0]]["x"], pad[wires[k][0]]["y"])))
    def build(k, d, z):
        ref, r, dest, _ = wires[k]; p0 = padpt(ref); p1 = p0 + n * 3.0
        rr = float(np.hypot(p0[0], p0[1])); base = u * rr
        lane_a = base + n * d; lane_a = np.array([lane_a[0], lane_a[1], z])
        d0 = np.array(dest[0])
        rd = float(np.hypot(d0[0], d0[1])); lb = u * rd + n * d; lane_b = np.array([lb[0], lb[1], z])         # the lane runs radially at offset d from the fin plane
        pts = [p0, p1, lane_a, lane_b] + [np.array(q) for q in dest]
        return [pts[0]] + [q for i, q in enumerate(pts[1:], 1) if np.linalg.norm(q - pts[i - 1]) > 1e-6]
    tr = {k: wires[k][1] for k in wires}; FL = S["bay_floor"]["z"][1]
    def post_axes(Pk):
        a, b = Pk[2], Pk[3]; L = float(np.linalg.norm(b - a)); ins = min(2.5, L / 2); span = L - 2 * ins
        if L < 5.0: return [], (b - a) / max(L, 1e-9)                       # a lane under 5 mm is too short for a post: the pad's 3 mm strain relief and the potting hold it
        m = 1 if span < 1.0 else int(math.ceil(span / 22.0)) + 1; ss = [0.5] if m == 1 else list(np.linspace(ins / L, 1 - ins / L, m))
        return [(a + (b - a) * s_, m) for s_ in ss], (b - a) / L
    PR = 1.2                                              # saddle post radius (mm)
    def greedy(order):
        routes = {}; fixed = {}; placed_posts = {}
        for k in order:
            best = None
            for d, z in lanes:
                Pk = build(k, d, z)
                if any(poly_dist(np.array(Pk), np.array(routes[j])) < tr[k] + tr[j] + CLEAR for j in routes): continue
                px = post_axes(Pk)[0]
                col = lambda q: np.array([[q[0], q[1], FL], [q[0], q[1], q[2]]])
                if any(poly_dist(col(q), np.array(routes[j])) < PR + tr[j] + CLEAR for q, _ in px for j in routes): continue
                if any(poly_dist(col(q2), np.array(Pk)) < PR + tr[k] + CLEAR for j in placed_posts for q2 in placed_posts[j]): continue
                if any(poly_dist(col(q), col(q2)) < 2 * PR + CLEAR for q, _ in px for j in placed_posts for q2 in placed_posts[j]): continue
                if z - tr[k] < S["fin_guides"]["h"] + S["bay_floor"]["z"][1] + CLEAR: continue
                L = sum(np.linalg.norm(b - a) for a, b in zip(Pk[:-1], Pk[1:])); sc = L + 0.5 * d
                if best is None or sc < best[0]: best = (sc, d, z, Pk)
            if best is None: return None
            routes[k] = best[3]; fixed[k] = dict(lane_offset_mm=best[1], lane_z=best[2]); placed_posts[k] = [q for q, _ in post_axes(best[3])[0]]
        return routes, fixed
    tried = []
    for od_ in itertools.permutations(order):
        r_ = greedy(od_)
        if r_: tot = sum(sum(np.linalg.norm(b - a) for a, b in zip(P_[:-1], P_[1:])) for P_ in r_[0].values()); tried.append((tot, od_, r_))
        if len(tried) >= 6: break
    if not tried: raise SystemExit("no clear lane assignment for the harness")
    tot_, order_used, (routes, fixed) = min(tried, key=lambda x: x[0])
    # solids of the wires and the saddles
    wsol = {k: wire_solid(routes[k], wires[k][1]) for k in routes}
    saddles = None; sad_n = {}; sad_k = {}
    for k, Pk in routes.items():
        px, ud = post_axes(Pk); sad_n[k] = len(px)
        for q, _ in px:
            fl = S["bay_floor"]["z"][1]
            post = m3.Manifold.cylinder(q[2] - fl + 0.01, PR, PR, 24).translate([q[0], q[1], fl - 0.01])
            post = post - capsule(q - ud * 2.2, q + ud * 2.2, wires[k][1] + 0.1)
            saddles = post if saddles is None else saddles + post; sad_k[k] = post if k not in sad_k else sad_k[k] + post
    res = dict(status="MODELED / tool-checked (no fabricator, no bench)", checks={})
    # clearance: every wire to every solid; wire to wire; saddles seat (they touch only their own wire's notch)
    hard = dict(solids)
    gaps = {}
    wfree = {k: wire_solid(routes[k][1:], wires[k][1]) for k in routes}                  # from the end of the 3 mm strain relief on: the first segment touches its pad by design (checked as ends_on_pads)
    for k, ws in wfree.items():
        worst = 9e9; who = None
        for name, sol in hard.items():
            if name in ("LID",) and k.startswith("CABLE"): continue             # the cable passes the gland hole: checked against the gland hole below
            gp = ws.min_gap(sol, 1.0)
            if gp < worst: worst, who = gp, name
        gaps[k] = dict(min_gap_mm=round(float(worst), 3), nearest=who)
    gl = H.at(H.cyl(g["d"] / 2, g["boss_z"][0] - 1, sh["lid_z"][1] + 1, 64), g["c"])
    for k in ("CABLE_A", "CABLE_B"):
        inside = (wsol[k] ^ H.cyl(300, sh["lid_z"][0] - 0.5, sh["lid_z"][1] + 0.5)); out_of_hole = (inside - gl).volume()
        gaps[k]["gland_hole_ok"] = out_of_hole < 1e-3
    ww = min(poly_dist(np.array(routes[a]), np.array(routes[b])) - tr[a] - tr[b] for a, b in itertools.combinations(routes, 2))
    res["checks"]["wire_clearance"] = dict(ok=all(v["min_gap_mm"] >= CLEAR - 1e-3 and v.get("gland_hole_ok", True) for v in gaps.values()) and ww >= CLEAR - 1e-3, to_solids=gaps, wire_to_wire_min_mm=round(float(ww), 3), required_mm=CLEAR)
    ends = {k: round(float(np.linalg.norm(routes[k][0] - padpt(wires[k][0]))), 4) for k in routes}
    res["checks"]["ends_on_pads"] = dict(ok=all(v < 1e-6 for v in ends.values()), offsets_mm=ends)
    def turn(Pk):
        out = []
        for a, b, c in zip(Pk[:-2], Pk[1:-1], Pk[2:]):
            v1, v2 = b - a, c - b; cs = (v1 @ v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)); out.append(round(math.degrees(math.acos(np.clip(cs, -1, 1))), 1))
        return out
    sweep = {}
    for k, Pk in routes.items():
        ang = np.unwrap([math.atan2(q[1], q[0]) for q in Pk]); sweep[k] = round(math.degrees(abs(ang[-1] - ang[0])), 2)
    res["checks"]["bends_and_rule5"] = dict(ok=all(max(turn(Pk)) <= 100.0 for Pk in routes.values()) and all(v < 45.0 for v in sweep.values()),
                                              turn_angles_deg={k: turn(Pk) for k, Pk in routes.items()}, sweep_round_axis_deg=sweep,
                                              note="corner turn <= 100 deg; each corner is filleted by the wire when seated in its saddle notches (bend radius of FEP litz / hookup wire to be set by the vendor)")
    lens_ = lens = {k: round(sum(np.linalg.norm(b - a) for a, b in zip(Pk[:-1], Pk[1:])), 1) for k, Pk in routes.items()}
    def area(A, B):                                   # area of the (flat) loop between two wires: shoelace on their projections onto the plane through both, bound by the end segments
        Pa = np.array(A); Pb = np.array(B[::-1]); pts = np.vstack([Pa, Pb]); c = pts.mean(0); u_, s_, vt = np.linalg.svd(pts - c); xy = (pts - c) @ vt[:2].T
        x, y = xy[:, 0], xy[:, 1]; return abs(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) / 100.0
    res["checks"]["lengths_and_loops"] = dict(ok=True, length_mm=lens, coil_lead_pair_loop_cm2=round(float(area(routes["COIL_A"], routes["COIL_B"])), 3), shaft_pair_loop_cm2=round(float(area(routes["CABLE_A"], routes["CABLE_B"])), 3),
                                                note="the loops lie in planes through the head axis' neighbourhood (the fin gap): twist the pairs where the harness leaves the saddles; loop area is a bound, not a coupling model")
    cross = {k: round(float(min(sad_k[k].min_gap(wsol[j], 1.0) for j in wsol if j != k)), 3) for k in sad_k}
    seat = {k: round(float(sad_k[k].min_gap(wsol[k], 1.0)), 3) for k in sad_k}
    unsup = {k: lens_[k] for k in routes if k not in sad_k}
    res["checks"]["saddles"] = dict(ok=all(v >= CLEAR - 1e-3 for v in cross.values()) and all(v > 0.05 for v in seat.values()) and all(v <= 25.0 for v in unsup.values()),
                                    saddles_per_wire=sad_n, post_d_mm=2 * PR, spacing_mm=22, gap_to_other_wires_mm=cross, notch_gap_to_own_wire_mm=seat,
                                    wires_without_a_saddle_mm=unsup, note="a wire with a lane under 5 mm has no saddle: held by the pad's strain relief and the potting, and must be <= 25 mm long")
    # potting cavities per sector: free bay volume minus every solid, wire and saddle
    bz = S["bay"]["z"]; bay = H.cyl(S["bay"]["r_max"], *bz); allsol = None
    for k, v in solids.items():
        if k in ("SHELL_LOWER", "LID", "COIL_CHANNEL", "COIL_COMBS", "SHIELD_COAT", "BOARD_SH1", "BOARD_QA", "BOARD_QB"): continue
        allsol = v if allsol is None else allsol + v
    for k, v in wsol.items(): allsol = allsol + v
    allsol = allsol + saddles
    def sector(d0, d1):
        pts = [(0, 0)] + [(200 * math.cos(math.radians(a)), 200 * math.sin(math.radians(a))) for a in np.linspace(d0, d1, 64)]
        return m3.CrossSection([pts]).extrude(bz[1] - bz[0]).translate([0, 0, bz[0]])
    free = bay - allsol; secs = dict(analog=sector(*S["sectors"]["analog"]), hv=sector(*S["sectors"]["hv"])); secs["digital"] = H.cyl(300, bz[0], bz[1]) - secs["analog"] - secs["hv"]
    pots = {k: (free ^ v) for k, v in secs.items()}
    res["checks"]["potting_cavities"] = dict(ok=all(v.volume() > 1000 for v in pots.values()), cm3={k: round(v.volume() / 1000, 1) for k, v in pots.items()}, fill="from the 4 mm hub bore outwards; the sector walls start at r 21, so each sector fills through the open hub region",
                                              open_item="vent paths: the display flex covers the lid over the bay, so vents must go through the shell wall's high side")
    res["pending"] = ["MP1 v2 sense wires (TXF JSA / JSB to MP1 v2 J1 / J2): MP1 v2 fin not built", "MP1 LV output flex through the 156 deg wall slot to AB1", "AB1A / AB1B / CB1D fins (Phase C)",
                      "pad-side wire solder cups and the printed strain-relief clips at the pads"]
    res["ok"] = all(v["ok"] for v in res["checks"].values())
    # --- exports
    import trimesh
    colors = dict(SHELL_LOWER=(60, 60, 64), LID=(25, 25, 28), COIL_CHANNEL=(90, 90, 96), COIL_COMBS=(120, 120, 130), BAY_FLOOR=(80, 80, 86), BAY_WALLS=(70, 70, 76), FIN_RAILS=(100, 100, 108), HUB=(110, 110, 118),
                  SHIELD_COAT=(180, 180, 190), BOARD_SH1=(20, 120, 60), BOARD_QA=(20, 140, 70), BOARD_QB=(20, 140, 70), LITZ=(200, 140, 40))
    sc = trimesh.Scene(); man = {}
    def add(name, mn, rgb, role, material):
        if mn is None or mn.is_empty(): return
        mesh = mn.to_mesh(); tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False); tm.visual.face_colors = list(rgb) + [255]
        sc.add_geometry(tm, node_name=name, geom_name=name); bb = tm.bounds
        man[name] = dict(role=role, material=material, volume_cm3=round(mn.volume() / 1000, 3), bbox_min=[round(float(x), 2) for x in bb[0]], bbox_max=[round(float(x), 2) for x in bb[1]])
    for k, v in solids.items():
        role = "fin board" if k.startswith("BOARD_FIN") else ("receive / shield board" if k.startswith("BOARD_") else "printed housing")
        add(k, v, colors.get(k, (30, 130, 70) if k.startswith("BOARD_FIN") else (120, 120, 120)), role, "FR4 1.0 mm" if k.startswith("BOARD_FIN") else "PETG (printed)")
    add("LITZ", P["LITZ"], colors["LITZ"], "transmit / receive coil", wm["coil_wire"][:60]); add("SADDLES", saddles, (230, 230, 120), "molded wire saddles", "PETG (printed with the floor)")
    for k, v in wsol.items(): add("WIRE_" + k, v, {"C": (220, 90, 40)}.get(k[0], (60, 120, 220)) if k.startswith("COIL") else (200, 40, 40), "harness wire", wires[k][3])
    for k, v in pots.items(): add("POTTING_" + k, v, (120, 200, 255), "potting cavity (fill volume)", S["potting"].get(k, "") if isinstance(S["potting"].get(k, ""), str) else "")
    sc.export(os.path.join(OUT, "assembly.glb"))
    json.dump(dict(components=man, count=len(man)), open(os.path.join(OUT, "assembly_manifest.json"), "w"), indent=1)
    json.dump({k: dict(kind=wires[k][3], od_mm=round(2 * wires[k][1], 2), lane=fixed[k], points_mm=[[round(float(x), 3) for x in q] for q in routes[k]], length_mm=lens[k]) for k in routes}, open(os.path.join(OUT, "harness.json"), "w"), indent=1)
    json.dump(res, open(os.path.join(OUT, "construct_check.json"), "w"), indent=1)
    print(json.dumps({k: (v if k != "checks" else {c: v[c]["ok"] for c in v}) for k, v in res.items()}, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
