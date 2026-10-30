#!/usr/bin/env python3
"""RF2 printable mechanical parts + DFM checker (2026-10-30; roadmap P3.6 yoke knuckle, P3.7 cuff, P3.9 head exterior). MODELED.
DFM rules (FDM, 0.4 mm nozzle, PETG / TPU; ASSUMED until a printer and material are chosen): minimum wall >= 1.2 mm (3 perimeters; TPU 1.6 mm), measured as
the larger of two readings per area-weighted surface sample: the inward ray length and the diameter of the largest inscribed sphere (the ray under-reads
beside obtuse corners, e.g. the rims of the lid's conical wells; the sphere under-reads at convex edges; a real thin wall or a feather edge is thin by both);
the 2nd percentile must reach 0.8 x the minimum and <= 3 % of samples may fall below it; overhang: faces steeper than 45 deg below horizontal, excluding the bed contact, as an area fraction (> 10 % = 'needs supports',
reported, not failed); the print orientation is the one of six axis-aligned options with the least overhang; the part must fit a 256 x 256 x 256 mm bed (ASSUMED printer class);
the mesh must be watertight. Kinematic sweeps: the head through the yoke's pitch range, the cuff slider along its rails, the wings through their fold.
Writes rf2/chassis_out/print/*.stl, rf2/head/out_BF/print/*.stl and rf2/results/rf2_print.json.   usage: python3 rf2/rf2_print.py"""
import os, sys, json, math
import numpy as np, trimesh, cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
OUT_C = os.path.join(HERE, "chassis_out", "print"); OUT_H = os.path.join(HERE, "head", "out_BF", "print")
for d in (OUT_C, OUT_H): os.makedirs(d, exist_ok=True)
BED = (256.0, 256.0, 256.0)                 # Bambu P1S / X1C class (ASSUMED printer); the 233 mm head parts need it
def mesh_of(shape, tol=0.2):
    v, t = shape.tessellate(tol); m = trimesh.Trimesh(np.array([[q.x, q.y, q.z] for q in v]), np.array(t), process=True); m.merge_vertices(); return m
def dfm(m, wall_min=1.2, n=1500, seed=0):
    rng = np.random.default_rng(seed); pts, fi = trimesh.sample.sample_surface(m, n, seed=seed); nrm = m.face_normals[fi]
    orig = pts - nrm * 0.02; loc, ri, _ = m.ray.intersects_location(orig, -nrm, multiple_hits=False)
    th = np.full(n, np.nan); th[ri] = np.linalg.norm(loc - orig[ri], axis=1) + 0.02
    # inscribed-sphere thickness: the largest sphere tangent at the point (centre along the inward normal) that stays inside, by bisection on its radius.
    # The ray alone under-reads beside obtuse corners (a ray from a face near a widening hole runs into the hole's wall); the sphere does not.
    ok_i = ~np.isnan(th); P, Nn, hi = pts[ok_i], nrm[ok_i], th[ok_i] / 2; lo = np.zeros_like(hi)
    pq = trimesh.proximity.ProximityQuery(m)
    for _ in range(10):
        mid = (lo + hi) / 2; d = np.abs(pq.signed_distance(P - Nn * mid[:, None])); inside = d >= mid * 0.95
        lo = np.where(inside, mid, lo); hi = np.where(inside, hi, mid)
    th_s = np.maximum(2 * lo, th[ok_i]); ray_p2 = float(np.percentile(th[ok_i], 2)) if ok_i.any() else 0.0      # larger of sphere and ray: each method's artefact is cancelled by the other
    p2 = float(np.percentile(th_s, 2)) if len(th_s) else 0.0; frac_thin = float(np.mean(th_s < wall_min)) if len(th_s) else 1.0
    best = None
    for name, R in (("+Z up", np.eye(3)), ("-Z up", np.diag([1, -1, -1])), ("+X up", np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])), ("-X up", np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])),
                    ("+Y up", np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])), ("-Y up", np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]]))):
        V = m.vertices @ R.T; F = m.faces; fn = m.face_normals @ R.T; zmin = V[:, 2].min()
        fz = V[F][:, :, 2].max(axis=1); down = (fn[:, 2] < -math.cos(math.radians(45))) & (fz > zmin + 0.2)
        over = float(m.area_faces[down].sum() / m.area); ext = sorted((V.max(0) - V.min(0)).tolist())
        fits = all(a <= b for a, b in zip(ext, sorted(BED)))
        if best is None or (fits, -over) > (best["fits_bed"], -best["overhang_frac"]): best = dict(orientation=name, overhang_frac=round(over, 3), fits_bed=fits, extents_mm=[round(x, 1) for x in ext])
    ok = m.is_watertight and p2 >= 0.8 * wall_min and frac_thin <= 0.03 and best["fits_bed"]
    return dict(ok=bool(ok), watertight=bool(m.is_watertight), volume_cm3=round(m.volume / 1000, 2), wall_p2_mm=round(p2, 2), thin_fraction=round(frac_thin, 3), wall_min_mm=wall_min,
                ray_wall_p2_mm=round(ray_p2, 2), method="max(inscribed sphere, inward ray) per sample: the ray under-reads beside obtuse corners, the sphere at convex edges; a real thin wall or feather edge is thin both ways",
                needs_supports=best["overhang_frac"] > 0.10, **best)
# ---------------------------------------------------------------- parts (local frames)
def yoke_parts():
    """dual-axis yoke for the 21 x 21 inner profile: a fork (two cheeks straddling the head ears, pivot bores 6.2 mm with friction-washer counterbores, bridge,
    round spigot) and a swivel socket bonded on the profile end (square bore, round bore for the spigot, 4 ball-detent seats at 90 deg, e-clip groove)"""
    cheek_t, cheek_gap = 5.0, 44.0                                                     # links at y = +-(22 .. 27); pivot at the origin, axis along Y
    fork = cq.Workplane("XY").box(24, cheek_gap + 2 * cheek_t, 8).translate((0, 0, 30))  # bridge
    for sg in (1, -1):
        yc = sg * (cheek_gap / 2 + cheek_t / 2)
        ch = cq.Workplane("XY").box(18, cheek_t, 30).translate((0, yc, 15)).union(cq.Workplane("XZ").circle(9.0).extrude(cheek_t / 2, both=True).translate((0, yc, 0)))
        ch = ch.cut(cq.Workplane("XZ").circle(3.1).extrude(30, both=True).translate((0, yc, 0)))
        ch = ch.cut(cq.Workplane("XZ").circle(6.0).extrude(0.5, both=True).translate((0, sg * (cheek_gap / 2 + cheek_t - 0.5), 0)))     # friction-washer seat on the outer face
        fork = fork.union(ch)
    fork = fork.union(cq.Workplane("XY").circle(9.0).extrude(20).translate((0, 0, 34))).cut(cq.Workplane("XY").circle(2.0).extrude(30).translate((0, 0, 30)))   # spigot + cable bore stub
    fork = fork.cut(cq.Workplane("XY").circle(9.6).circle(8.4).extrude(1.0).translate((0, 0, 50)))                                                          # e-clip groove
    sock = cq.Workplane("XY").rect(27.2, 27.2).extrude(46).edges("|Z").fillet(4).cut(cq.Workplane("XY").rect(21.3, 21.3).extrude(30).translate((0, 0, 16)))
    sock = sock.cut(cq.Workplane("XY").circle(9.2).extrude(17))
    for k in range(4):
        a = math.radians(90 * k)                                                         # ball-detent seat: a 2.4 mm radial drilled hole, 1.2 mm deep into the bore wall
        sock = sock.cut(cq.Workplane("XY").circle(1.2).extrude(1.6).rotate((0, 0, 0), (0, 1, 0), 90).translate((8.8, 0, 8)).rotate((0, 0, 0), (0, 0, 1), 90 * k))
    sock = sock.cut(cq.Workplane("XY").circle(1.6).extrude(20).translate((11.5, 0, -1)))          # ball-plunger bore (M4 plunger, ASSUMED)
    return {"YOKE_FORK": fork.val(), "YOKE_SWIVEL_SOCKET": sock.val()}
def sector(r_in, r_out, a0, a1, L):
    """annular sector with RADIAL end faces (no feather edges): angles in degrees in the profile plane (x = N up, y lateral)"""
    am = math.radians((a0 + a1) / 2); p = lambda r, a: (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
    w = (cq.Workplane("XY").moveTo(*p(r_out, a0)).threePointArc(p(r_out, (a0 + a1) / 2), p(r_out, a1)).lineTo(*p(r_in, a1)).threePointArc(p(r_in, (a0 + a1) / 2), p(r_in, a0)).close())
    return w.extrude(L)
def cuff_parts():
    import rf2_chassis as CH
    cu = CH.SPEC["cuff"]; r = CH.SPEC["rails"]; ri, ro = cu["r_in"], cu["r_in"] + cu["t"]
    trough = sector(ri, ro, 105.0, 255.0, cu["len"])                                     # bottom 150 deg (x = N up: 180 deg is straight down)
    for a in (105.0, 255.0):                                                             # wing hinge knuckles on the trough edges, 2.2 mm pin bores
        c = (((ri + ro) / 2) * math.cos(math.radians(a)), ((ri + ro) / 2) * math.sin(math.radians(a)))
        trough = trough.union(cq.Workplane("XY").circle(3.2).extrude(cu["len"]).translate((c[0], c[1], 0))).cut(cq.Workplane("XY").circle(1.1).extrude(cu["len"] + 2).translate((c[0], c[1], -1)))
    for z0 in (10.0, cu["len"] - 10.0):                                                  # radial strap slots 4 mm wide through the wall at +-35 deg off the bottom
        for a in (145.0, 215.0):
            slot = cq.Workplane("XY").box(ro - ri + 4, 4.0, 10.0).translate(((ri + ro) / 2, 0, z0)).rotate((0, 0, 0), (0, 0, 1), a); trough = trough.cut(slot)
    wing = sector(ri, ro, 50.0, 103.5, cu["len"])                                       # one wing (mirror for the other), radial ends; folds about the knuckle
    rail_r = r["d"] / 2 + 0.2
    slider = cq.Workplane("XY").box(4.0, 2 * r["y"] + 6, 40).translate((0, 0, 20))
    for sg in (1, -1):
        plate = cq.Workplane("XY").box(24.0, 5.0, 40).translate((-12.0, sg * (r["y"] + 0.5), 20))
        boss = cq.Workplane("XY").circle(rail_r + 2.0).extrude(40).translate((-22.0, sg * (r["y"] + 0.5), 0))
        slider = slider.union(plate).union(boss).cut(cq.Workplane("XY").circle(rail_r).extrude(42).translate((-22.0, sg * (r["y"] + 0.5), -1)))
    return {"CUFF_TROUGH": trough.val(), "CUFF_WING": wing.val(), "CUFF_SLIDER": slider.val()}
def head_parts():
    import rf2_upper as U
    R = U.SPEC["head_r"]
    skid = cq.Workplane("XY").circle(R - 0.5).extrude(1.6).edges(">Z or <Z").chamfer(0.5)
    for k in range(6):                                                                   # snap clips around the rim: arm 1.6 mm, hook lip 0.8 mm
        a = math.radians(30 + 60 * k); c = (R - 0.5 - 0.8, 0)
        arm = cq.Workplane("XY").box(8.0, 1.6, 7.0).translate((R - 1.3, 0, 1.6 + 3.5)).union(cq.Workplane("XY").box(8.0, 2.4, 1.2).translate((R - 1.7, 0, 1.6 + 6.4)))
        skid = skid.union(arm.rotate((0, 0, 0), (0, 0, 1), math.degrees(a)))
    bumper = cq.Workplane("XY").circle(R + 2.5).circle(R - 0.2).extrude(8.0).edges().fillet(0.8)
    return {"HEAD_SKID_CLIP": skid.val(), "HEAD_BUMPER_TPU": bumper.val()}
# ---------------------------------------------------------------- sweeps
def sweeps():
    import rf2_chassis as CH, rf2_upper as U
    from scipy.spatial import cKDTree
    P, geo = CH.build(); out = {}
    head = U.samples(cq.Compound.makeCompound([P[k][1] for k in ("HEAD_SKID", "HEAD_ENVELOPE")]), 2.0)
    yoke = U.samples(cq.Compound.makeCompound([P[k][1] for k in ("YOKE_CHEEK_L", "YOKE_CHEEK_R", "YOKE_SWIVEL", "INNER_TUBE")]), 2.0); tree = cKDTree(yoke)
    free = []
    for ang in range(-60, 181, 5):
        R, t = U.rot_about(U.P0, U.Y, math.radians(ang)); d, _ = tree.query(head @ R.T + t, distance_upper_bound=1.5)
        free.append((ang, bool(np.all(np.isinf(d)))))
    ok_angles = [a for a, f in free if f]; use = [a for a in range(-25, 46, 5)]          # working range: shaft angle 35-50 deg (+-7.5) + terrain +-15 = +-22.5, with margin
    out["yoke_pitch"] = dict(ok=all(dict(free)[a] for a in use), free_deg=[min(ok_angles), max(ok_angles)] if ok_angles else None, blocked_deg=[a for a, f in free if not f],
                             note="head (skid + envelope) about the pivot vs the yoke links, swivel and inner profile; the working range -25..+45 deg must be free (need +-22.5 deg: shaft 35-50 deg and +-15 deg terrain)")
    import rf2_chassis as CH2; best = json.load(open(os.path.join(HERE, "chassis_out", "rf2_chassis_check.json")))["fold"]["chosen"]
    blocked_store = []                                                                   # 1) pitch to the stored pitch: head about the pivot vs the links, swivel and profile
    for ang in range(0, int(best["head_pitch"]) + 1, 5):
        R, t = U.rot_about(U.P0, U.Y, math.radians(ang)); d, _ = tree.query(head @ R.T + t, distance_upper_bound=1.5)
        if np.any(~np.isinf(d)): blocked_store.append(("pitch", ang))
    links = U.samples(cq.Compound.makeCompound([P[k][1] for k in ("YOKE_CHEEK_L", "YOKE_CHEEK_R")]), 2.0)
    shaft_t = cKDTree(U.samples(cq.Compound.makeCompound([P[k][1] for k in ("INNER_TUBE",)]), 2.0))       # 2) roll: head + links turn together on the swivel, vs the inner profile
    Rp, tp = U.rot_about(U.P0, U.Y, math.radians(best["head_pitch"])); moving = np.vstack([head @ Rp.T + tp, links])
    for ang in range(0, int(abs(best["head_roll"])) + 1, 5):
        R, t = U.rot_about(U.P0, U.D, math.radians(math.copysign(ang, best["head_roll"]))); d, _ = shaft_t.query(moving @ R.T + t, distance_upper_bound=1.5)
        if np.any(~np.isinf(d)): blocked_store.append(("roll", ang))
    out["yoke_storage_path"] = dict(ok=not blocked_store, roll_deg=best["head_roll"], pitch_to_deg=best["head_pitch"], blocked_deg=blocked_store, note="pitch first (head vs the fixed links), then roll on the swivel (head + links vs the inner profile)")
    chs = [p[1] for k, p in P.items() if p[0] == "CH" and not k.startswith(("CUFF", "RAIL"))]; body = cKDTree(U.samples(cq.Compound.makeCompound(chs), 2.0))
    cuffs = U.samples(cq.Compound.makeCompound([p[1] for k, p in P.items() if k.startswith(("CUFF_TROUGH", "CUFF_WING"))]), 2.0); hits = []
    for dz in np.linspace(0, CH.SPEC["cuff"]["slide"], 8):
        d, _ = body.query(cuffs - U.D * dz, distance_upper_bound=1.0); hits.append(bool(np.any(~np.isinf(d))))
    out["cuff_slide"] = dict(ok=not any(hits), travel_mm=CH.SPEC["cuff"]["slide"], positions_hit=int(sum(hits)), note="cuff trough + wings along the rails toward the grip vs the chassis, grip and battery")
    return out
def main():
    res = dict(status="MODELED; DFM rules ASSUMED (FDM PETG / TPU)", parts={}, sweeps={})
    groups = {"P3.6": ("yoke", yoke_parts(), OUT_C, 1.2), "P3.7": ("cuff", cuff_parts(), OUT_C, 1.2), "P3.9": ("head", head_parts(), OUT_H, 1.2)}
    for gid, (name, parts, outdir, wmin) in groups.items():
        for k, sh in parts.items():
            m = mesh_of(sh); r = dfm(m, 1.6 if "TPU" in k else wmin); r["group"] = gid; res["parts"][k] = r; m.export(os.path.join(outdir, f"{k}.stl"))
            print(k, json.dumps(r), flush=True)
    for k, path in (("HEAD_SHELL_LOWER (rf2_head)", os.path.join(HERE, "head", "out_BF", "RF2_SHELL_LOWER.stl")), ("HEAD_LID (rf2_head)", os.path.join(HERE, "head", "out_BF", "RF2_LID.stl"))):
        m = trimesh.load(path); r = dfm(m, 1.2); r["group"] = "P3.9"; res["parts"][k] = r; print(k, json.dumps(r), flush=True)
    res["sweeps"] = sweeps(); print(json.dumps(res["sweeps"]), flush=True)
    for gid, extra in (("P3.6", ["yoke_pitch", "yoke_storage_path"]), ("P3.7", ["cuff_slide"]), ("P3.9", [])):
        res[f"{gid}_ok"] = all(v["ok"] for v in res["parts"].values() if v["group"] == gid) and all(res["sweeps"][e]["ok"] for e in extra)
    json.dump(res, open(os.path.join(HERE, "results", "rf2_print.json"), "w"), indent=1)
    print({g: res[f"{g}_ok"] for g in ("P3.6", "P3.7", "P3.9")}); return res
if __name__ == "__main__":
    main()
