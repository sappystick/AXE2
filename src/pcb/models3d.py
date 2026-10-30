#!/usr/bin/env python3
"""Parametric 3-D models of every component package used on the PHI-FOLD 233 boards (Step 7): ONE source for (a) the VRML files KiCad shows on the boards
(`model` lines written by the footprint exporters), (b) the component bodies of the generated `*_board_with_components.stl` and (c) the neck-module fit check.
Models are NOMINAL package outlines built from the footprint pad geometry and the standard dimensions of each package family (chip sizes, SOIC / MSOP / SOT-23 / SOT-223 /
TO-263 / DO-214 / TO-92 bodies, 10 x 10 hybrid can, 2.54 / 1.27 mm headers, 5.08 mm terminal blocks, Pico 2, OKI-78SR, SK6812-mini-E): they are not manufacturer STEP files.
The datasheet-verified overall sizes (EEHZC1H101P 10.0 x 10.2, SF-1206S 3.1 x 1.55 x 0.6) are used where read (docs/design/DATASHEET_LOG.md); the rest is marked in
ASSUMPTIONS (item 34). Frame: footprint frame (x right, y DOWN as KiCad board coordinates, z up from the board surface); the VRML writer flips y for KiCad's model frame.
usage: python3 models3d.py OUT_DIR     writes OUT_DIR/<type>.wrl for every type of every board and OUT_DIR/models_report.json"""
import math, os, sys, json
import numpy as np
METAL, GOLD, BLACK, PLASTIC, GREEN, TAN, WHITE = (0.78, 0.78, 0.80), (0.85, 0.70, 0.25), (0.10, 0.10, 0.11), (0.16, 0.16, 0.18), (0.10, 0.45, 0.22), (0.72, 0.60, 0.38), (0.93, 0.93, 0.90)
ALU, DARK, BLUE, BROWN, RED = (0.74, 0.76, 0.80), (0.22, 0.22, 0.24), (0.12, 0.30, 0.75), (0.30, 0.20, 0.12), (0.75, 0.15, 0.12)
def box(x0, x1, y0, y1, z0, z1, c):
    X, Y, Z = (x0, x1), (y0, y1), (z0, z1); V = np.array([[x, y, z] for x in X for y in Y for z in Z], float)
    F = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return V[np.array(F)], c
def cyl(cx, cy, r, z0, z1, c, n=28, sx=1.0):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False); T = []
    for i in range(n):
        j = (i + 1) % n; a = (cx + sx * r * math.cos(t[i]), cy + r * math.sin(t[i])); b = (cx + sx * r * math.cos(t[j]), cy + r * math.sin(t[j]))
        T += [[(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1)], [(a[0], a[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], [(cx, cy, z1), (a[0], a[1], z1), (b[0], b[1], z1)], [(cx, cy, z0), (b[0], b[1], z0), (a[0], a[1], z0)]]
    return np.array(T, float), c
def prism(poly, z0, z1, c):
    """extruded convex polygon (list of (x, y))"""
    n = len(poly); cx = sum(p[0] for p in poly) / n; cy = sum(p[1] for p in poly) / n; T = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        T += [[(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1)], [(a[0], a[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], [(cx, cy, z1), (a[0], a[1], z1), (b[0], b[1], z1)], [(cx, cy, z0), (b[0], b[1], z0), (a[0], a[1], z0)]]
    return np.array(T, float), c
def D_poly(w, d, r_flat=0.0, n=10):                                                    # TO-92 body: half circle of radius w/2 on a flat face (y = +d/2 side flat)
    R = w / 2; pts = [(-R, d / 2 - R), (R, d / 2 - R)]
    for k in range(n + 1):
        a = math.pi * k / n; pts.append((R * math.cos(a) * -1 if False else R * math.cos(a), (d / 2 - R) - R * math.sin(a) + 0))
    return pts
def gullwing(pads, body_x, body_y, c=METAL, thick=0.18, z_top=0.35):
    """a thin lead from each body edge to the outer end of its pad (SOIC / MSOP / SOT-23 families)"""
    out = []
    for n, px, py, w, h, shp in pads:
        if abs(px) > body_x:                                                         # pads on the left / right of the body
            e = math.copysign(body_x, px); xo = px + math.copysign(w / 2 - 0.15, px); out.append(box(min(e, xo), max(e, xo), py - min(h, 0.5) / 2, py + min(h, 0.5) / 2, 0.0, thick, c))
        else:                                                                        # pads above / below
            e = math.copysign(body_y, py); yo = py + math.copysign(h / 2 - 0.15, py); out.append(box(px - min(w, 0.5) / 2, px + min(w, 0.5) / 2, min(e, yo), max(e, yo), 0.0, thick, c))
    return out
def pin_dot(x, y, z, r=0.25): return cyl(x, y, r, z, z + 0.02, WHITE, 10)
def chip(L, body, cap_frac=0.2, color=BLACK, caps=METAL):
    bw, bh, bz = body; cl = bw * cap_frac; return [box(-bw / 2 + cl, bw / 2 - cl, -bh / 2, bh / 2, 0.0, bz, color), box(-bw / 2, -bw / 2 + cl, -bh / 2, bh / 2, 0.0, bz, caps), box(bw / 2 - cl, bw / 2, -bh / 2, bh / 2, 0.0, bz, caps)]
def soic(L, bx, by, bz, mark=True):                                                  # body bx (across the pad columns) x by (along the pin rows)
    parts = [box(-bx / 2, bx / 2, -by / 2, by / 2, 0.1, bz, BLACK)] + gullwing(L["pads"], bx / 2, by / 2)
    p1 = next(p for p in L["pads"] if str(p[0]) == "1"); parts.append(pin_dot(-bx / 2 + 0.7, p1[2] - 0.0 if False else p1[2], bz))
    return parts
def sot(L, bx, by, bz): return [box(-bx / 2, bx / 2, -by / 2, by / 2, 0.05, bz, BLACK)] + gullwing(L["pads"], bx / 2, by / 2)
# --------------------------------------------------------------------------------------------------------- recipes by LIB type
def build(t, L):
    bw, bh, bz = L["body"]; P = L["pads"]
    if t == "R0805": return chip(L, L["body"], 0.18, BLACK)
    if t in ("R0402", "R0603", "R0805", "R1206", "R2512"): return chip(L, L["body"], 0.18, BLACK)
    if t in ("C0402", "C0603", "C0805", "C1210"): return chip(L, L["body"], 0.2, TAN)
    if t == "FUSE1206B": return chip(L, L["body"], 0.2, (0.88, 0.80, 0.55))
    if t == "FUSE1812": return chip(L, L["body"], 0.2, (0.88, 0.80, 0.55))
    if t == "FB1812": return chip(L, L["body"], 0.18, BROWN)
    if t in ("DSMC", "DSMB", "DSOD"):
        k1 = next(p for p in P if str(p[0]) == "1"); sgn = math.copysign(1, k1[1]); body_x = bw / 2 - (0.0 if t != "DSOD" else 0.0)
        parts = [box(-bw / 2 + 0.4, bw / 2 - 0.4, -bh / 2, bh / 2, 0.15, bz, PLASTIC)]
        for s in (-1, 1): parts.append(box(s * (bw / 2 - 0.5) - (0.5 if s > 0 else 0.0) if False else (min(s * (bw / 2), s * (bw / 2 - 0.9))), max(s * (bw / 2), s * (bw / 2 - 0.9)), -min(bh, 2.0 if t != "DSMC" else 3.0) / 2, min(bh, 2.0 if t != "DSMC" else 3.0) / 2, 0.0, 0.5, METAL))
        parts.append(box(sgn * (bw / 2 - 1.6) - 0.35, sgn * (bw / 2 - 1.6) + 0.35, -bh / 2 + 0.05, bh / 2 - 0.05, bz, bz + 0.03, METAL) if t != "DSOD" else box(sgn * (bw / 2 - 0.75) - 0.2, sgn * (bw / 2 - 0.75) + 0.2, -bh / 2 + 0.05, bh / 2 - 0.05, bz, bz + 0.03, METAL))
        return parts
    if t in ("TC4420", "LM393", "OPA2211"): return soic(L, 3.9, 4.9, 1.7)
    if t == "PMOS_SO8": return soic(L, 3.9, 4.9, 1.75)
    if t == "HC4051": return soic(L, 3.9, 9.9, 1.7)
    if t in ("OPA2365", "REF5041"): return [box(-1.5, 1.5, -1.5, 1.5, 0.1, bz, BLACK)] + gullwing(P, 1.5, 1.5) + [pin_dot(-1.0, -1.0, bz)]
    if t == "AD7389": return [box(-2.0, 2.0, -2.0, 2.0, 0.035, bz, BLACK), pin_dot(-1.6, -1.6, bz)]            # LFCSP-24 4 x 4 x 0.55 body, no leads beyond the body (nominal)
    if t == "ADS8860": return [box(-1.5, 1.5, -1.5, 1.5, 0.1, bz, BLACK)] + gullwing(P, 1.5, 1.5) + [pin_dot(-1.0, -1.0, bz)]
    if t in ("BAV199", "SW1G66", "SOT23-5"): return sot(L, 1.6 if t != "SOT23-5" else 1.6, 2.9, 1.1) if False else [box(-bh / 2, bh / 2, -bw / 2, bw / 2, 0.05, bz, BLACK) if False else box(-bw / 2, bw / 2, -bh / 2, bh / 2, 0.05, bz, BLACK)] + gullwing(P, bw / 2, bh / 2)
    if t == "SOT223": return [box(-3.15 + 0.7, 3.15 - 0.7, -1.7, 1.7, 0.1, 1.6, PLASTIC)] + gullwing(P, 2.3, 1.7) + [box(2.0, 3.15 + 0.4, -1.6, 1.6, 0.0, 0.25, METAL)]
    if t == "D2PAK":                                                                                   # leads at -x (G, S), tab (drain) at +x under the 10.2 x 9.2 body
        return [box(-2.4, 7.8, -4.6, 4.6, 0.3, 4.4, PLASTIC), box(5.0, 10.0, -4.2, 4.2, 0.0, 0.3, METAL), box(7.8, 9.4, -3.9, 3.9, 0.0, 0.3, METAL)] + [box(-7.2, -2.4, py - 0.4, py + 0.4, 0.0, 0.5, METAL) for (_, px, py, w, h, s) in P if px < -3]
    if t == "CAPD": return [box(-bw / 2, bw / 2, -bh / 2, bh / 2, 0.0, bz, (0.85, 0.78, 0.55))]
    if t == "CAN10":                                                                                   # Panasonic ZC / ZK family: 10.0 x 10.2 mm can on a 10.3 x 10.3 base plate, polarity bar on the "+" side
        parts = [box(-5.15, 5.15, -5.15, 5.15, 0.0, 1.0, BLACK), cyl(0, 0, 5.0, 1.0, 10.2, ALU), cyl(0, 0, 4.2, 10.2, 10.5, DARK)]
        k = next(p for p in P if str(p[0]) == "1"); s = math.copysign(1, k[1]); parts.append(box(s * 3.5 - 0.9, s * 3.5 + 0.9, -4.6, 4.6, 10.5, 10.55, WHITE)); return parts
    if t == "HALL_SW":                                                                                 # TO-92 (DRV5023 LPG): D-shaped body on the pads, flat face toward +y
        poly = [(-2.0, 0.0), (2.0, 0.0)] + [(2.0 * math.cos(a), -2.0 * math.sin(a) * 0.8 + 0.0) for a in np.linspace(0, math.pi, 10)]
        return [prism([(-2.0, 0.8), (2.0, 0.8)] + [(2.0 * math.cos(a), 0.8 - 1.6 * math.sin(a)) for a in np.linspace(0, math.pi, 9)][::-1], 0.8, 4.5, BLACK)] + [box(px - 0.2, px + 0.2, -0.2, 0.2, 0.0, 1.0, METAL) for (_, px, py, w, h, s) in P]
    if t.startswith("HDR"):
        pitch = 2.54 if "2x6S" not in t and t not in ("HDR1x6", "HDR1x8", "HDR2x6") or t in ("HDR1x2", "HDR1x3", "HDR1x4", "HDR1x5", "HDR1x7", "HDR2x4", "HDR2x6") and bz > 8 else 1.27
        pitch = 2.54 if (bz > 8.5 and "S" not in t) else 1.27; ph = 2.5 if pitch == 2.54 else 1.5
        parts = [box(-bw / 2, bw / 2, -bh / 2, bh / 2, 0.0, ph, PLASTIC)]
        pw = 0.64 if pitch == 2.54 else 0.35
        parts += [box(px - pw / 2, px + pw / 2, py - pw / 2, py + pw / 2, 0.0, bz, GOLD) for (_, px, py, w, h, s) in P]; return parts
    if t in ("TERM2", "TERM4"):
        parts = [box(-bw / 2, bw / 2, -bh / 2, bh / 2, 0.0, 7.5, GREEN)]
        for (_, px, py, w, h, s) in P: parts += [cyl(px, py, 1.9, 7.5, 8.0, METAL), box(px - 0.3, px + 0.3, py - 1.6, py + 1.6, 8.0, 8.05, DARK)]
        return parts + [box(-bw / 2, -bw / 2 + 1.2, -bh / 2 + 0.3, bh / 2 - 0.3, 7.5, bz, GREEN)]
    if t == "OKI3": return [box(-1.5, 10.0, -4.25, 4.25, 0.0, 10.2, BLACK), box(-1.2, 9.7, -3.0, 3.0, 10.2, 10.25, WHITE)] + [box(-0.3, 0.3, py - 0.3, py + 0.3, 0.0, 1.0, METAL) for (_, px, py, w, h, s) in P]
    if t == "BMI270": return [box(-1.5, 1.5, -1.25, 1.25, 0.0, 0.83, (0.25, 0.25, 0.28))]      # LGA-14 3.0 x 2.5 x 0.83 (Bosch BST-BMI270-DS000-08)
    if t == "SK9822EC20": return [box(-1.0, 1.0, -1.0, 1.0, 0.0, 0.5, WHITE), box(-0.8, 0.8, -0.8, 0.8, 0.5, 0.65, (0.95, 0.95, 0.7))]      # 2.0 x 2.0 x 0.65 (OPSCO Rev. A/0), bottom-terminated
    if t == "LED2020": return [box(-1.6, 1.6, -1.4, 1.4, 0.0, 0.6, WHITE), cyl(0, 0, 1.2, 0.6, 0.8, (0.95, 0.95, 0.7), 16)] + gullwing(P, 1.6, 1.4, METAL, 0.1, 0.2)[:0]
    if t == "PICO":                                                                                    # Raspberry Pi Pico 2 W: 21 x 51 mm green module on the 40 pins, USB-micro at -y end, RP2350 + CYW43439 can
        z0 = 2.5; return [box(-10.5, 10.5, -25.5, 25.5, z0, z0 + 1.0, GREEN), box(-4.0, 4.0, -26.0, -20.0, z0 + 1.0, z0 + 3.8, METAL), box(-3.5, 3.5, -8.0, -1.0, z0 + 1.0, z0 + 1.9, BLACK), box(2.0, 8.0, 6.0, 14.0, z0 + 1.0, z0 + 2.0, METAL), box(-6.0, -1.0, 8.0, 13.0, z0 + 1.0, z0 + 1.9, BLACK)] + [box(px - 0.3, px + 0.3, py - 0.3, py + 0.3, 0.0, z0 + 1.0, GOLD) for (_, px, py, w, h, s) in P]
    if t.startswith("WIRE"): return []                                                                  # bare solder pads for wires
    if t in ("VSSOP28", "HVSSOP8EP", "WQFN16EP", "SOT23-6BUCK", "SOT23-5LDO", "SRN4018"):              # AU1 packages: body box from LIB body (datasheet package size and max height)
        bw, bh, bz = L["body"]; col = (0.35, 0.35, 0.35) if t == "SRN4018" else BLACK
        body = [box(-bw / 2, bw / 2, -bh / 2, bh / 2, 0.0, bz, col)]
        if t in ("VSSOP28", "HVSSOP8EP", "SOT23-6BUCK", "SOT23-5LDO"):                              # leaded packages: gull-wing leads from the body edge to each pad (the body alone missed the HVSSOP pads)
            body += gullwing([q for q in L["pads"] if abs(q[1]) > bw / 2 or abs(q[2]) > bh / 2], bw / 2, bh / 2)
        return body
    raise KeyError(t)
# --------------------------------------------------------------------------------------------------------- VRML
def wrl(parts, name):
    L = ["#VRML V2.0 utf8", f"# PHI-FOLD 233 nominal package model {name} (src/pcb/models3d.py): units mm, KiCad model frame (y up = board -y)", "Transform { scale 1 1 1 children ["]
    for k, (T, c) in enumerate(parts):
        pts = []; idx = []
        for tri in T:
            base = len(pts); pts += [(float(v[0]), float(-v[1]), float(v[2])) for v in tri]; idx.append((base, base + 2, base + 1))      # y flip reverses the winding
        L.append("  Shape { appearance Appearance { material Material { diffuseColor %.3f %.3f %.3f specularColor 0.3 0.3 0.3 shininess 0.3 } } geometry IndexedFaceSet { creaseAngle 0.6 solid FALSE" % c)
        L.append("    coord Coordinate { point [ " + ", ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in pts) + " ] }")
        L.append("    coordIndex [ " + ", ".join(f"{a},{b},{c_},-1" for a, b, c_ in idx) + " ] } }")
    L.append("] }"); return "\n".join(L) + "\n"
def model_line(t, indent="    ", rot_z=0.0):
    """the KiCad `model` line for package type t ('' for bare solder pads); path relative to the project folder (data/kicad/3dmodels)"""
    if t.startswith("WIRE"): return ""
    return f'{indent}(model "${{KIPRJMOD}}/3dmodels/PF233_{t}.wrl" (offset (xyz 0 0 0)) (scale (xyz 0.3937 0.3937 0.3937)) (rotate (xyz 0 0 {rot_z:g})))'
def placed_mesh(t, L, x0, y0, rot=0.0, back=False):
    """component body triangles in BOARD y-UP coordinates (what the *_board_with_components.stl uses) for a footprint at KiCad (x0, y0) [y-DOWN] rotated rot deg;
    back=True mirrors the part to the underside (z -> -z, as for a B.Cu footprint). Returns (V, F) with outward-oriented faces, or None for bare pads."""
    parts = build(t, L)
    if not parts: return None
    V = []; F = []
    a = math.radians(rot); ca, sa = math.cos(a), math.sin(a)
    for T, c in parts:
        P = T.reshape(-1, 3).copy(); P[:, 1] = -P[:, 1]                                 # footprint frame is y-down: flip to y-up
        P = np.stack([ca * P[:, 0] - sa * P[:, 1], sa * P[:, 0] + ca * P[:, 1], P[:, 2]], 1)
        P[:, 0] += x0; P[:, 1] += -y0
        if back: P[:, 2] = -P[:, 2]
        Fi = np.arange(len(P)).reshape(-1, 3)
        n = np.cross(P[Fi[:, 1]] - P[Fi[:, 0]], P[Fi[:, 2]] - P[Fi[:, 0]]); vol = float(np.sum(np.einsum("ij,ij->i", P[Fi[:, 0]], n)) / 6.0)
        if vol < 0 or (back and False): Fi = Fi[:, ::-1]
        F.append(Fi + sum(len(v) for v in V)); V.append(P)
    return np.concatenate(V), np.concatenate(F)
def types_by_board():
    import importlib
    out = {}
    for pw in "CRPGLHMTU":          # U = AU1 (2026-10-28: its own package types had no models)
        os.environ["PW"] = pw; os.environ["DISC"] = "1"; sys.modules.pop("pw_design", None)
        try: D = importlib.import_module("pw_design")
        except Exception: continue
        for t in {p["type"] for p in D.PARTS}: out.setdefault(("pw", t), D.LIB[t])
    for b in "AB":
        os.environ["BOARD"] = b; sys.modules.pop("afe_design", None)
        try: A = importlib.import_module("afe_design")
        except Exception: continue
        for t in {p["type"] for p in A.PARTS}: out.setdefault(("afe", t), A.LIB[t])
    return out
EXTRA = {"R0805": dict(fp="Resistor_SMD:R_0805_2012Metric", body=(2.0, 1.25, 0.5), pads=[("1", -0.95, 0, 1.0, 1.45, "roundrect"), ("2", 0.95, 0, 1.0, 1.45, "roundrect")])}    # types used by writers that have no pw/afe LIB (sbq_export)
def mesh_of(t, L):
    parts = build(t, L); return parts
def bbox(parts):
    if not parts: return None
    V = np.concatenate([T.reshape(-1, 3) for T, c in parts]); return V.min(0), V.max(0)
if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); rep = {}
    allt = dict(types_by_board()); allt.update({("extra", t): L for t, L in EXTRA.items()})
    for (src, t), L in sorted(allt.items()):
        key = t if (src, t) != ("afe", t) or ("pw", t) not in types_by_board() else "AFE_" + t
        try: parts = build(t, L)
        except KeyError: print("no recipe for", t); continue
        name = f"PF233_{t}" if src == "pw" else f"PF233_{t}"
        if not parts: rep[t] = dict(model=None, note="bare solder pads, no body"); continue
        open(os.path.join(out, f"{name}.wrl"), "w").write(wrl(parts, name)); lo, hi = bbox(parts); rep[t] = dict(model=f"{name}.wrl", fp=L["fp"], bbox_lo=np.round(lo, 2).tolist(), bbox_hi=np.round(hi, 2).tolist(), envelope=list(L["body"]))
    json.dump(rep, open(os.path.join(out, "models_report.json"), "w"), indent=1); print(len(rep), "package types,", sum(1 for v in rep.values() if v["model"]), "models ->", out)
