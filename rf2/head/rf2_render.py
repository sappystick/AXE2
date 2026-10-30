#!/usr/bin/env python3
"""RF2 head v1: 3D cut-away and exploded view, rendered from the real generated geometry (2026-10-29). Housing and seats: the manifold solids of rf2_head.py
(the cut is an exact boolean wedge, so the section faces are true); MP1 / TXJ / LR1: board slab from the outline, every routed copper track read from the KiCad
files, every part body at its netlist position; SH1 / QA / QB: board slabs; AB1A / AB1B: the RF1 exported board-with-components meshes, mounted component
side up; CB1D: its envelope only (not routed yet: Phase C). A small z-buffer rasterizer (numpy) with Lambert shading and part / crease outlines.
MODELED design, not a photograph of hardware. usage: python3 rf2/head/rf2_render.py  -> out/rf2_cutaway.png, out/rf2_exploded.png"""
import os, sys, json, math, struct
import numpy as np
import manifold3d as m3
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rf2_head as H
import rf2_netlist as NL
OUT = H.OUT; RF1 = os.path.join(HERE, "..", "..", "reference", "rf1", "build_ab1")
COL = dict(shell=(0.80, 0.83, 0.86), lid=(0.86, 0.88, 0.90), print=(0.70, 0.72, 0.75), wall_ci=(0.42, 0.36, 0.33), fr4=(0.16, 0.42, 0.25), fr4b=(0.12, 0.34, 0.45),
           shield=(0.86, 0.68, 0.26), copper=(0.85, 0.45, 0.20), litz=(0.80, 0.40, 0.14), ic=(0.12, 0.12, 0.13), res=(0.18, 0.18, 0.20), cap=(0.72, 0.60, 0.42),
           led=(0.95, 0.95, 0.92), pad=(0.90, 0.78, 0.40), env=(0.55, 0.75, 0.55), ab1=(0.20, 0.45, 0.30))
def mesh(man):
    m = man.to_mesh(); return np.asarray(m.vert_properties)[:, :3].astype(float), np.asarray(m.tri_verts).astype(int)
def wedge(d0, d1, z0=-5, z1=40):
    pts = [(0, 0)] + [(400 * math.cos(math.radians(a)), 400 * math.sin(math.radians(a))) for a in np.linspace(d0, d1, 64)]
    return m3.CrossSection([pts]).extrude(z1 - z0).translate([0, 0, z0])
def box(cx, cy, sx, sy, z0, z1, rot=0.0): return m3.Manifold.cube([sx, sy, z1 - z0], True).rotate([0, 0, rot]).translate([cx, cy, (z0 + z1) / 2])
def board_slab(name):
    B = NL.BOARDS[name]; hd = B["head"]; z0 = hd["z_bottom"]; t = B["thickness"]
    if B["kind"] == "rect": s = box(hd["c"][0], hd["c"][1], B["w"], B["h"], z0, z0 + t)
    elif B["kind"] == "poly":                                               # the display flex: its real outline (notch, hinge slit)
        import rf2_ledgrid as LG, manifold3d as m3
        o = LG.outline(); cs = m3.CrossSection([list(o.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in o.interiors], m3.FillRule.EvenOdd)
        s = m3.Manifold.extrude(cs, t).translate([0, 0, z0])
        for r, a, d in B.get("holes", []): s = s - H.at(H.cyl(d / 2, z0 - 1, z0 + t + 1, 24), H.pol(r, a))
    else:
        s = H.cyl(B["r_out"], z0, z0 + t) - H.cyl(B["r_in"], z0 - 1, z0 + t + 1)
        for r, a, d in B.get("holes", []): s = s - H.at(H.cyl(d / 2, z0 - 1, z0 + t + 1, 24), H.pol(r, a))
    return s
def tracks(name):
    """routed copper from the KiCad file as thin boxes on the board faces (F.Cu on top, B.Cu underneath), plus vias"""
    import pcbnew
    B = NL.BOARDS[name]; hd = B["head"]; z0 = hd["z_bottom"]; t = B["thickness"]; pcb = os.path.join(OUT, name, f"PF233-RF2-{name}.kicad_pcb")
    if not os.path.exists(pcb): return None
    bd = pcbnew.LoadBoard(pcb); M = pcbnew.ToMM; parts = []
    for tr in bd.GetTracks():
        if tr.GetClass() == "PCB_VIA":
            x, y = M(tr.GetPosition().x) - 150 + hd["c"][0], 150 - M(tr.GetPosition().y) + hd["c"][1]; parts.append(H.at(H.cyl(M(tr.GetWidth(pcbnew.F_Cu)) / 2, z0 - 0.04, z0 + t + 0.04, 12), (x, y))); continue
        a = np.array([M(tr.GetStart().x) - 150, 150 - M(tr.GetStart().y)]) + hd["c"]; b = np.array([M(tr.GetEnd().x) - 150, 150 - M(tr.GetEnd().y)]) + hd["c"]
        L = float(np.hypot(*(b - a))); w = M(tr.GetWidth()); top = tr.GetLayer() == pcbnew.F_Cu
        if L < 1e-3: continue
        zz = (z0 + t, z0 + t + 0.04) if top else (z0 - 0.04, z0)
        parts.append(box(*((a + b) / 2), L + w, w, *zz, math.degrees(math.atan2(*(b - a)[::-1]))))
    return m3.Manifold.batch_boolean(parts, m3.OpType.Add) if parts else None
def bodies(name):
    B = NL.BOARDS[name]; hd = B["head"]; zt = hd["z_bottom"] + B["thickness"]; out = {}
    for p in B["parts"]:
        bw, bl, bh = NL.LIB[p["type"]]["body"]; x, y = hd["c"][0] + p["x"], hd["c"][1] + p["y"]
        kind = "ic" if p["type"] in ("OPA2211", "BAV199") else "res" if p["type"].startswith("R") else "cap" if p["type"].startswith("C") else "led" if p["type"].startswith("SK") else "pad"
        out.setdefault(kind, []).append(box(x, y, bw, bl, zt, zt + bh, p["rot"]))
    return {k: m3.Manifold.batch_boolean(v, m3.OpType.Add) for k, v in out.items()}
def stl(path):
    b = open(path, "rb").read(); n = struct.unpack("<I", b[80:84])[0]
    return np.frombuffer(b, dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]), count=n, offset=84)["v"].reshape(-1, 3, 3).astype(float)
def ab1(k):
    p = {"AB1A": os.path.join(RF1, "final_A/kit_v3/PCB_AB1A/pre_freerouting/PF233-AB1A_board_with_components.stl"), "AB1B": os.path.join(RF1, "final_B/kit_v3/PCB_AB1B/PF233-AB1B_board_with_components.stl")}[k]
    T = stl(p).copy(); v = H.SPEC["boards_inner"][k]; T[..., 1] *= -1; T[..., 2] = v["z"][0] + (1.6 - T[..., 2])      # flip about x: component side up, board z 5.6-7.2
    a = math.radians(v["hinge_deg"]); c, s = math.cos(a), math.sin(a); x, y = T[..., 0].copy(), T[..., 1].copy()
    T[..., 0] = x * c - y * s + v["c"][0]; T[..., 1] = x * s + y * c + v["c"][1]; return T[:, [0, 2, 1]]                 # flipped: restore outward winding
def scene(explode=False):
    P = H.parts(); S = H.SPEC; items = []
    cutB = wedge(205, 295) if not explode else None; cutA = wedge(140, 320) if not explode else None
    dz = (lambda k: dict(SHELL_LOWER=0, BOARD_SH1=18, BOARD_QA=34, BOARD_QB=50, COIL_CHANNEL=72, LITZ=72, BAY_WALLS=100, CRADLE_AB1A=100, CRADLE_AB1B=100,
                         CB1D_TOWER=100, TRAY_MP1=100, TRAY_TXJ=100, ENV_CB1D=128, LED=150, LID=172, AB1=100, MP1=100, TXJ=100).get(k, 0)) if explode else (lambda k: 0)
    def add(name, man, col, cut=None, label=None, key=None):
        if man is None: return
        if cut is not None: man = man - cut
        if man.is_empty(): return
        V, F = mesh(man); V = V + [0, 0, dz(key or name)]; items.append((name, V[F], col, label))
    add("SHELL_LOWER", P["SHELL_LOWER"], COL["shell"], cutB, "shell: skid + wall (PETG)")
    add("LID", P["LID"], COL["lid"], cutA, "clear PETG lid over the display, gland")
    add("COIL_CHANNEL", P["COIL_CHANNEL"], COL["print"], cutB)
    co = S["coil"]; lz = None
    for j in range(co["turns"]):
        t = m3.CrossSection.circle(co["litz_od"] / 2, 10).translate([co["columns_r"][j % len(co["columns_r"])], co["row0_z"] + (j // len(co["columns_r"])) * co.get("row_pitch", co["pitch"])]).revolve(120)
        lz = t if lz is None else lz + t
    add("LITZ", lz, COL["litz"], cutB, "rim mono coil, 26 turns litz")
    add("BOARD_SH1", P["BOARD_SH1"], COL["shield"], cutB, "SH1 split-ring shield")
    add("BOARD_QA", P["BOARD_QA"], COL["fr4b"], cutB, "QA / QB quadrupole boards"); add("BOARD_QB", P["BOARD_QB"], COL["fr4"], cutB)
    add("BAY_WALLS", P["BAY_WALLS"], COL["wall_ci"], None, "sector walls (carbonyl-iron PETG)")
    for k in ("CRADLE_AB1A", "CRADLE_AB1B", "CB1D_TOWER", "TRAY_MP1", "TRAY_TXJ"): add(k, P[k], COL["print"], None, "CB1D tower" if k == "CB1D_TOWER" else None)
    add("ENV_CB1D", P["ENV_CB1D"], COL["env"], None, "CB1D section (envelope; routing: Phase C)")
    for nm in ("MP1", "TXJ", "LR1"):
        cut = cutA if nm == "LR1" else None; key = "LED" if nm == "LR1" else nm
        add(nm + "_board", board_slab(nm), COL["fr4"], cut, {"MP1": "MP1 mono preamp (routed)", "TXJ": "TXJ coil-lead board (routed)", "LR1": "LR1 display flex: 522 LEDs, 13 rings (routed)"}[nm], key)
        add(nm + "_cu", tracks(nm), COL["copper"], cut, None, key)
        for kind, man in bodies(nm).items(): add(f"{nm}_{kind}", man, COL[kind], cut, None, key)
    for k in ("AB1A", "AB1B"):
        T = ab1(k) + [0, 0, dz("AB1")]; items.append((k, T, COL["ab1"], f"{k} analog (RF1, routed)" if k == "AB1A" else None))
    return items
def render(items, path, az=232.0, el=36.0, dist=560.0, target=(0, 0, 9.0), W=2600, Hh=1750, fov=36.0, labels=True, title=""):
    eye = np.array(target) + dist * np.array([math.cos(math.radians(el)) * math.cos(math.radians(az)), math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))])
    f = np.array(target) - eye; f /= np.linalg.norm(f); r = np.cross(f, [0, 0, 1]); r /= np.linalg.norm(r); u = np.cross(r, f)
    foc = 0.5 * Hh / math.tan(math.radians(fov / 2)); light = np.array([-0.35, -0.55, 0.76]); light /= np.linalg.norm(light)
    zb = np.full((Hh, W), np.inf); img = np.ones((Hh, W, 3)) * np.array([0.97, 0.975, 0.98]); idb = np.full((Hh, W), -1, int); nb = np.zeros((Hh, W, 3))
    anchors = []
    for pid, (name, T, col, lab) in enumerate(items):
        Vc = T - eye; xs = Vc @ r; ys = Vc @ u; zs = Vc @ f
        px = W / 2 + foc * xs / zs; py = Hh / 2 - foc * ys / zs
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(n, axis=1); n = n / np.maximum(nl[:, None], 1e-12)
        shade = 0.42 + 0.58 * np.abs(n @ light); c = np.clip(np.outer(shade, col) + 0.06 * np.abs(n @ (-f))[:, None], 0, 1)
        for i in range(len(T)):
            x0, x1 = int(max(0, math.floor(px[i].min()))), int(min(W - 1, math.ceil(px[i].max()))); y0, y1 = int(max(0, math.floor(py[i].min()))), int(min(Hh - 1, math.ceil(py[i].max())))
            if x0 > x1 or y0 > y1: continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax_, bx, cx), (ay, by, cy) = px[i], py[i]; den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9: continue
            w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax_ - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
            m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not m.any(): continue
            zz = w0 * zs[i, 0] + w1 * zs[i, 1] + w2 * zs[i, 2]; sub = zb[y0:y1 + 1, x0:x1 + 1]; upd = m & (zz < sub)
            if not upd.any(): continue
            sub[upd] = zz[upd]; img[y0:y1 + 1, x0:x1 + 1][upd] = c[i]; idb[y0:y1 + 1, x0:x1 + 1][upd] = pid; nb[y0:y1 + 1, x0:x1 + 1][upd] = n[i]
        if lab:
            k = np.argmin(zs.mean(axis=1)) if len(T) else 0; cpt = T.reshape(-1, 3).mean(axis=0)
            vis = T.reshape(-1, 3)[np.argsort(((T.reshape(-1, 3) - eye) @ f))[: max(1, len(T) // 20)]].mean(axis=0)
            Vc = vis - eye; anchors.append((lab, W / 2 + foc * (Vc @ r) / (Vc @ f), Hh / 2 - foc * (Vc @ u) / (Vc @ f)))
    edge = np.zeros((Hh, W), bool)
    edge[:, 1:] |= idb[:, 1:] != idb[:, :-1]; edge[1:, :] |= idb[1:, :] != idb[:-1, :]
    dn = np.einsum("ijk,ijk->ij", nb[:, 1:], nb[:, :-1]); edge[:, 1:] |= (dn < 0.82) & (idb[:, 1:] >= 0)
    dn = np.einsum("ijk,ijk->ij", nb[1:, :], nb[:-1, :]); edge[1:, :] |= (dn < 0.82) & (idb[1:, :] >= 0)
    img[edge] = img[edge] * 0.35
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(W / 200, Hh / 200), dpi=200); ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(img, interpolation="lanczos"); ax.axis("off")
    if labels:
        anchors.sort(key=lambda a: a[2]); left = [a for a in anchors if a[1] < W / 2]; right = [a for a in anchors if a[1] >= W / 2]
        for side, group in ((0, left), (1, right)):
            for j, (lab, x, y) in enumerate(group):
                ty = 160 + j * (Hh - 320) / max(1, len(group) - 1) if len(group) > 1 else Hh / 2; tx = 60 if side == 0 else W - 60
                ax.annotate(lab, (x, y), (tx, ty), fontsize=7.5, ha="left" if side == 0 else "right", va="center", color="#1d2733",
                            arrowprops=dict(arrowstyle="-", lw=0.6, color="#1d2733", shrinkA=2, shrinkB=1), bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#9aa5b1", lw=0.5))
    ax.text(30, Hh - 30, title, fontsize=9, color="#1d2733", va="bottom")
    fig.savefig(path, dpi=200); plt.close(fig)
if __name__ == "__main__":
    import time; t0 = time.time()
    render(scene(False), os.path.join(OUT, "rf2_cutaway.png"),
           title="RF2 head v1, D233 x 25.4 mm: cut-away from the generated geometry (MODELED design; CB1D shown as its envelope, routing pending)")
    print("cutaway", round(time.time() - t0, 1), "s", flush=True)
    render(scene(True), os.path.join(OUT, "rf2_exploded.png"), el=24.0, dist=760.0, target=(0, 0, 80.0), fov=34.0, Hh=2100,
           title="RF2 head v1: exploded stack (z offsets for clarity), same geometry")
    print("exploded", round(time.time() - t0, 1), "s")
