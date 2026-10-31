#!/usr/bin/env python3
"""RF2 hex / square CF shaft cross-section environment (owner study 2026-10-31): the cord conductors on flex strips bonded to the inner faces of a
carbon-fibre shaft, optional internal radial separators (hub + webs) and a central bore. MODELED; an options study, nothing adopted.

Sections   shape square | hex (vertices at 0 deg, flats facing +-y), across-flats AF 21 / 26 / 31 / 35.6 mm, wall t = 1.2 mm.
           internal: none | hub6 (CF tube OD 5 / ID 4 + 0.6 mm radial webs hub -> inner corners: 6 for hex, 4 for square) | hub6_cu (same,
           18 um Cu on both faces of webs and hub, grounded). CF 1.55 g/cm3, E 50 GPa (ASSUMED, as rf2_shaftlink_options), Cu 8.96 g/cm3.
           A and I from shapely polygons (hub circle 256-gon) by Green's theorem: Ixx = 1/12 sum (x_i y_i+1 - x_i+1 y_i)(y_i^2 + y_i y_i+1 + y_i+1^2),
           taken about the centroid; I reported = minimum principal value. Cu is left out of I (36 um, negligible) but counted in mass.
           g/m = A[mm2] x rho[g/cm3]. Usable face width = inner flat width - 2 x 0.3 mm (web / corner fillets).
Groups     from rf2_cordflex.LANES (flex strip 0.15 mm thick): HV = 0.75 + TX_A + 1.0 + TX_B + 0.75 (W_TX from IPC-2221); power = VIN_H, GND_H
           0.3 / gap 0.3; digital = TXCMD, TXSTAT, DATA pairs 2 x 0.15 / 0.15; REF X/Y/Z = guard 0.3 / 0.15 / trace 0.15 / 0.15 / trace 0.15 / 0.15 /
           guard 0.3 (1.35 mm per pair). LV strip edges 0.3 mm and strip-to-strip gap 0.3 mm on a shared face (ASSUMED). NOTE: LANES packs the
           three digital 0.45 mm pair lanes edge to edge (traces of adjacent pairs touch); this study inserts 0.15 mm between pairs, in the
           strips and in the coplanar reference alike.
Allocation HV is the aggressor and REF the victim: HV alone on the top face (symmetry fixes it there; HV never shares a face with LV), every
           other assignment of power / digital / REF to faces and every order / placement (centred, pushed to either end) on a face is
           enumerated; best = lexicographic max of centroid distances (HV-REF, digital-REF, power-REF). A group wider than every face is
           reported in not_fitting (none is, in the variants studied).
Central    digital moved to the bore: 6 PTFE AWG30 wires OD 0.5 (ASSUMED) or 3 POF (GH-4001-P jacket 2.2, or bare 1.0 cladding); bundle
bore       diameter from optimal circle packing (3 circles: d (1 + 2/sqrt 3); 6 circles: 3 d), compared with the hub ID 4.0 mm.
Electro-   2D finite-volume Laplace, uniform grid h = 0.05 mm, div(eps grad phi) = 0, eps taken at each edge midpoint; the CF wall is treated as a
statics    grounded conductor (CF is conductive: ASSUMED; sigma ~1e4 S/m), webs + hub grounded (hub6 and hub6_cu are therefore identical
           electrostatically and solved once); flex modelled: polyimide eps_r 3.4 from the wall to 0.15 mm over the strip width, traces as
           conductors at 0.05-0.10 mm above the wall (2-node band; Cu thickness not resolved), coverlay above. Power traces and REF guards are
           grounded (AC ground). Q_j = eps0 sum_(nodes of j) sum_edges eps_e (phi_j - phi_nb); C_ij (Maxwell matrix, pF/m) from unit excitations;
           coupling = -C_ij. Validated against a coax 2 pi eps0 / ln(b/a). Coplanar reference: all LANES side by side on one strip, strip bottom
           2.0 mm above an infinite ground plane, box 10 mm clear on the other sides (grounded; approximates free space).
Magnetics  free-space filaments at trace centres: M' = mu0/(2 pi) ln((d13 d24)/(d14 d23)), 1 = TX_A, 2 = TX_B (return), 3/4 = REF+/REF-.
           V' = M' dI/dt for 8 A / 6 us and 47 A / 5 us. Skin depth delta = sqrt(2 rho / (w mu0)); thin-sheet separator attenuation
           |H_in/H_out| = 1 / |1 + j w mu0 (sigma t) d / 2| (clib.tube_shield_transverse form; d = chamber depth r_in - r_hub) at 100 kHz. That formula
           assumes a closed enclosure; open radial webs whose loop closes through the resistive CF wall shield less: an upper bound.
CAD        cadquery: 300 mm folding-shaft segment (hex AF 31, hub6_cu) with HV / power / REF flex on three faces, POF in the bore, camlock window
           20 x 12, flex exit slot 16 x 2, two hinge knuckles OD 34 x 10 with hollow pin OD 6 / ID 2.8 (axis x, perpendicular to the shaft),
           fibre rotary-joint cavity D8 x 6 coaxial with the pin, flex drum OD 30 between the knuckles; plus a telescope inner tube (square 21).
Writes rf2/results/rf2_hex_section.json, hexseg_*.stl, hexseg.step, hexseg_view.png, hexseg_field.png.   usage: python3 rf2/rf2_hex_section.py"""
import os, sys, json, math, time, itertools
import numpy as np
import scipy.sparse as sp, scipy.sparse.linalg as sla
from shapely.geometry import Polygon, Point, box as sbox
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import contains_xy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
sys.path[:0] = [HERE, os.path.join(ROOT, "concepts")]
import rf2_cordflex as CFX
import clib as K
EPS0, MU0 = K.EPS0, K.MU0
T_WALL, AFS, AFS_ALLOC, SHAPES, INTERNALS = 1.2, (21.0, 26.0, 31.0, 35.6), (21.0, 26.0, 31.0), ("square", "hex"), ("none", "hub6", "hub6_cu")
RHO_CF, RHO_CU, E_CF, T_CU = 1.55, 8.96, 50e3, 0.018           # g/cm3, g/cm3, N/mm2 (ASSUMED), mm per face
HUB_OD, HUB_ID, WEB_T, FILLET = 5.0, 4.0, 0.6, 0.3
SIG_CF, SIG_CU = 1e4, 5.8e7                                     # S/m (CF ASSUMED; Cu handbook)
EPS_PI, H = 3.4, 0.05                                           # polyimide eps_r (ASSUMED typical), grid mm
STRIP_T, TR_V0, TR_V1, EDGE_LV, GAP_STRIP = 0.15, 0.05, 0.10, 0.3, 0.3
W_TX, HV_GAP = CFX.W_TX, CFX.HV_GAP
DIDT = {"8A_6us": 8.0 / 6e-6, "47A_5us": 47.0 / 5e-6}
WIRE_OD, POF_J, POF_B = 0.5, 2.2, 1.0
PACK = {3: 1 + 2 / math.sqrt(3), 6: 3.0}                       # enclosing-circle / member diameter, optimal packings

# ---------------------------------------------------------------- section geometry
def npoly(shape): return 6 if shape == "hex" else 4
def outline(shape, af):
    n = npoly(shape); rc = af / 2 / math.cos(math.pi / n); a0 = 0.0 if n == 6 else math.pi / 4
    return Polygon([(rc * math.cos(a0 + 2 * math.pi * k / n), rc * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)])
def hubweb(shape, af):
    n = npoly(shape); r_c = (af - 2 * T_WALL) / 2 / math.cos(math.pi / n); a0 = 0.0 if n == 6 else math.pi / 4
    parts = [Point(0, 0).buffer(HUB_OD / 2, 64).difference(Point(0, 0).buffer(HUB_ID / 2, 64))]
    for k in range(n):
        a = a0 + 2 * math.pi * k / n; L0, L1 = HUB_ID / 2 + 0.2, r_c + 0.5
        c, s = math.cos(a), math.sin(a); nx, ny = -s * WEB_T / 2, c * WEB_T / 2
        parts.append(Polygon([(L0 * c + nx, L0 * s + ny), (L1 * c + nx, L1 * s + ny), (L1 * c - nx, L1 * s - ny), (L0 * c - nx, L0 * s - ny)]))
    return unary_union(parts)
def faces(shape, af):
    """inner faces: normal angle, apothem, half width; face k is its own chamber when webs are present"""
    n = npoly(shape); r_in = af / 2 - T_WALL; side = 2 * r_in * math.tan(math.pi / n); a0 = math.pi / n if n == 6 else 0.0
    return [dict(k=k, th=a0 + 2 * math.pi * k / n, r=r_in, half=side / 2) for k in range(n)]
def poly_I(geom):
    """A, centroid, min principal second moment of a polygon with holes (Green's theorem, exact for the polygon)"""
    A = Sx = Sy = Ixx = Iyy = Ixy = 0.0
    for g in getattr(geom, "geoms", [geom]):
        g = orient(g, 1.0)
        for ring in [g.exterior] + list(g.interiors):
            p = np.asarray(ring.coords); x0, y0, x1, y1 = p[:-1, 0], p[:-1, 1], p[1:, 0], p[1:, 1]; c = x0 * y1 - x1 * y0
            A += c.sum() / 2; Sx += ((x0 + x1) * c).sum() / 6; Sy += ((y0 + y1) * c).sum() / 6
            Ixx += ((y0 ** 2 + y0 * y1 + y1 ** 2) * c).sum() / 12; Iyy += ((x0 ** 2 + x0 * x1 + x1 ** 2) * c).sum() / 12
            Ixy += ((x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * c).sum() / 24
    cx, cy = Sx / A, Sy / A; Ixx -= A * cy * cy; Iyy -= A * cx * cx; Ixy -= A * cx * cy
    return A, (Ixx + Iyy) / 2 - math.hypot((Ixx - Iyy) / 2, Ixy)
def section(shape, af, internal):
    out = outline(shape, af); inn = outline(shape, af - 2 * T_WALL); g = out.difference(inn); cu_a = 0.0
    if internal != "none":
        hw = hubweb(shape, af).intersection(out); g = unary_union([g, hw])
        if internal == "hub6_cu": cu_a = (hw.intersection(inn).length - npoly(shape) * WEB_T) * T_CU
    A, I = poly_I(g); fw = 2 * faces(shape, af)[0]["half"] - 2 * FILLET
    return dict(A_mm2=round(A, 2), I_mm4=round(I, 1), mass_g_per_m=round(A * RHO_CF + cu_a * RHO_CU, 2), cu_g_per_m=round(cu_a * RHO_CU, 3),
                chambers=1 if internal == "none" else npoly(shape), face_width_mm=round(fw, 3), bore_id_mm=HUB_ID if internal != "none" else None,
                EI_Nm2=round(E_CF * I * 1e-6, 2))

# ---------------------------------------------------------------- conductor groups (element: name, u0, u1, net) net: 'sig' or 'gnd'
def group_elems(g):
    if g == "HV": return 2 * 0.75 + 2 * W_TX + HV_GAP, [("TX_A", 0.75, 0.75 + W_TX, "sig"), ("TX_B", 0.75 + W_TX + HV_GAP, 0.75 + 2 * W_TX + HV_GAP, "sig")]
    if g == "PWR": return 1.5, [("VIN_H", 0.3, 0.6, "gnd"), ("GND_H", 0.9, 1.2, "gnd")]
    if g == "DIG":
        e = []
        for k, n in enumerate(("TXCMD", "TXSTAT", "DATA")):
            s = EDGE_LV + 0.6 * k; e += [(n + "+", s, s + 0.15, "sig"), (n + "-", s + 0.3, s + 0.45, "sig")]
        return 2 * EDGE_LV + 3 * 0.45 + 2 * 0.15, e
    e = []
    for k, a in enumerate("XYZ"):
        s = EDGE_LV + 1.35 * k
        e += [(f"G{a}a", s, s + 0.3, "gnd"), (f"REF{a}+", s + 0.45, s + 0.6, "sig"), (f"REF{a}-", s + 0.75, s + 0.9, "sig"), (f"G{a}b", s + 1.05, s + 1.35, "gnd")]
    return 2 * EDGE_LV + 3 * 1.35, e
GROUPS = ("HV", "PWR", "DIG", "REF"); GW = {g: group_elems(g)[0] for g in GROUPS}

def fxy(f, u, v):
    n = np.array([math.cos(f["th"]), math.sin(f["th"])]); t = np.array([-n[1], n[0]]); return n * (f["r"] - v) + t * u
def allocate(shape, af):
    fs = faces(shape, af); usable = 2 * fs[0]["half"] - 2 * FILLET; top = [f["k"] for f in fs if abs(math.sin(f["th"]) - 1) < 1e-9][0]
    not_fit = [g for g in GROUPS if GW[g] > usable]; best = None
    others = [k for k in range(len(fs)) if k != top]
    for asg in itertools.product(others, repeat=3):
        A = dict(zip(("PWR", "DIG", "REF"), asg)); A["HV"] = top; byf = {}
        for g in GROUPS: byf.setdefault(A[g], []).append(g)
        if any(sum(GW[g] for g in gs) + GAP_STRIP * (len(gs) - 1) > usable for gs in byf.values()): continue
        opts = []
        for k, gs in byf.items():
            used = sum(GW[g] for g in gs) + GAP_STRIP * (len(gs) - 1); lo = -usable / 2; o = []
            for perm in itertools.permutations(gs):
                for start in ({lo, -used / 2, usable / 2 - used} if k != top else {-used / 2}):
                    pos, u = {}, start
                    for g in perm: pos[g] = (k, u); u += GW[g] + GAP_STRIP
                    o.append(pos)
            opts.append(o)
        for combo in itertools.product(*opts):
            pos = {g: p for d in combo for g, p in d.items()}
            cen = {g: fxy(fs[pos[g][0]], pos[g][1] + GW[g] / 2, STRIP_T / 2) for g in GROUPS}
            d = lambda a, b: round(float(np.linalg.norm(cen[a] - cen[b])), 2)
            sc = (d("HV", "REF"), d("DIG", "REF"), d("PWR", "REF"))
            if best is None or sc > best[0]: best = (sc, pos)
    sc, pos = best; fout = {}
    for g in GROUPS:
        k, u = pos[g]; f = fs[k]
        e = fout.setdefault(f"face{k}", dict(normal_deg=round(math.degrees(f["th"]), 1), chamber=k, usable_mm=round(usable, 3), groups=[]))
        e["groups"].append(dict(group=g, width_mm=round(GW[g], 3), u_start_mm=round(u, 3)))
    return dict(faces=fout, not_fitting=not_fit, distances_mm=dict(HV_REF=sc[0], DIG_REF=sc[1], PWR_REF=sc[2])), pos, fs

def central_bore(internal):
    has = internal != "none"; r = {}
    for key, n, d in (("digital_wires", 6, WIRE_OD), ("pof_jacketed", 3, POF_J), ("pof_bare", 3, POF_B)):
        bd = PACK[n] * d; r[key] = dict(count=n, bundle_d_mm=round(bd, 3), fits=bool(has and bd <= HUB_ID), member_d_mm=d)
    r["bore_id_mm"] = HUB_ID if has else None
    if not has: r["note"] = "no central tube in this variant: nothing runs in a bore"
    return r

# ---------------------------------------------------------------- 2D finite-volume electrostatics
def fv_solve(kind, ex, ey, ncond):
    """kind: -1 ground, 0 free, k>=1 conductor k; ex/ey: eps_r on x / y edges. Returns Maxwell C (F/m, ncond x ncond) and the solutions."""
    NY, NX = kind.shape; free = kind == 0; idx = -np.ones(kind.shape, int); nf = int(free.sum()); idx[free] = np.arange(nf)
    rows, cols, vals = [], [], []; diag = np.zeros(nf); rhs = np.zeros((nf, ncond))
    for a_sl, b_sl, e in (((slice(None), slice(0, NX - 1)), (slice(None), slice(1, NX)), ex), ((slice(0, NY - 1), slice(None)), (slice(1, NY), slice(None)), ey)):
        ia, ib, ka, kb, e = idx[a_sl].ravel(), idx[b_sl].ravel(), kind[a_sl].ravel(), kind[b_sl].ravel(), e.ravel()
        for p, q, kq in ((ia, ib, kb), (ib, ia, ka)):
            m = p >= 0; np.add.at(diag, p[m], e[m])
            mm = m & (q >= 0); rows.append(p[mm]); cols.append(q[mm]); vals.append(-e[mm])
            mc = m & (kq > 0); np.add.at(rhs, (p[mc], kq[mc] - 1), e[mc])
    A = sp.csc_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(nf)]), np.concatenate(cols + [np.arange(nf)]))), shape=(nf, nf))
    sol = sla.splu(A).solve(rhs); C = np.zeros((ncond, ncond)); phis = []
    for i in range(ncond):
        phi = np.zeros(kind.shape); phi[free] = sol[:, i]; phi[kind == i + 1] = 1.0
        Fx = ex * (phi[:, :-1] - phi[:, 1:]); Fy = ey * (phi[:-1, :] - phi[1:, :]); net = np.zeros(kind.shape)
        net[:, :-1] += Fx; net[:, 1:] -= Fx; net[:-1, :] += Fy; net[1:, :] -= Fy
        q = np.bincount(np.clip(kind, 0, None).ravel(), weights=net.ravel(), minlength=ncond + 1)[1:]; C[i] = EPS0 * q; phis.append(phi)
    return C, phis

def coax_check():
    a, b = 1.0, 5.0; x = np.arange(-int(5.6 / H), int(5.6 / H) + 1) * H; X, Y = np.meshgrid(x, x); R = np.hypot(X, Y)
    kind = np.where(R <= a, 1, np.where(R >= b, -1, 0)); C, _ = fv_solve(kind, np.ones((len(x), len(x) - 1)), np.ones((len(x) - 1, len(x))), 1)
    exact = 2 * math.pi * EPS0 / math.log(b / a)
    return dict(case="coax a = 1 mm, b = 5 mm, h = 0.05 mm (staircased circles)", C_fd_pF_per_m=round(C[0, 0] * 1e12, 3),
                C_exact_pF_per_m=round(exact * 1e12, 3), error_pct=round((C[0, 0] / exact - 1) * 100, 2))

def raster_strips(X, Y, strips, kind, sig_names):
    """strips: list of (face dict, u_start, group). Marks conductors in kind; returns eps on x / y edges and trace centres"""
    xm_x, ym_x = (X[:, :-1] + X[:, 1:]) / 2, Y[:, :-1]; xm_y, ym_y = X[:-1, :], (Y[:-1, :] + Y[1:, :]) / 2
    ex, ey = np.ones(xm_x.shape), np.ones(xm_y.shape); centres = {}
    def uv(f, x, y):
        n = (math.cos(f["th"]), math.sin(f["th"])); return -n[1] * x + n[0] * y, f["r"] - (n[0] * x + n[1] * y)
    for f, u0, g in strips:
        w, el = group_elems(g)
        for (xx, yy, e) in ((xm_x, ym_x, ex), (xm_y, ym_y, ey)):
            u, v = uv(f, xx, yy); e[(u >= u0) & (u <= u0 + w) & (v >= 0) & (v <= STRIP_T)] = EPS_PI
        u, v = uv(f, X, Y)
        for name, a, b, net in el:
            m = (u >= u0 + a - 1e-9) & (u <= u0 + b + 1e-9) & (v >= TR_V0 - H / 2) & (v <= TR_V1 + H / 2) & (kind == 0)
            kind[m] = -1 if net == "gnd" else sig_names.index(name) + 1
            centres[name] = fxy(f, u0 + (a + b) / 2, (TR_V0 + TR_V1) / 2) if f.get("th") is not None else None
    return ex, ey, centres

def m_pair(p1, p2, p3, p4):
    d = lambda a, b: float(np.linalg.norm(np.asarray(a) - np.asarray(b)))
    return MU0 / (2 * math.pi) * math.log(d(p1, p3) * d(p2, p4) / (d(p1, p4) * d(p2, p3)))

def couple_metrics(C, names, centres):
    ix = {n: i for i, n in enumerate(names)}; refs = [n for n in names if n.startswith("REF")]
    c_tx = max([0.0] + [-C[ix["TX_A"], ix[r]] for r in refs]); c_da = max([0.0] + [-C[ix[d], ix[r]] for d in ("DATA+", "DATA-") for r in refs])   # -C_ij >= 0; clamps -0
    Ms = {a: m_pair(centres["TX_A"], centres["TX_B"], centres[f"REF{a}+"], centres[f"REF{a}-"]) for a in "XYZ"}
    M = max(Ms.values(), key=abs)
    return dict(C_tx_ref_pF_per_m=c_tx * 1e12, C_data_ref_pF_per_m=c_da * 1e12, M_tx_ref_nH_per_m=M * 1e9,
                V_ref_per_m_8A_6us_mV=abs(M) * DIDT["8A_6us"] * 1e3, V_ref_per_m_47A_5us_mV=abs(M) * DIDT["47A_5us"] * 1e3,
                M_by_axis_nH_per_m={a: round(v * 1e9, 4) for a, v in Ms.items()})

SIG = ["TX_A", "TX_B"] + [f"REF{a}{s}" for a in "XYZ" for s in "+-"] + [f"{n}{s}" for n in ("TXCMD", "TXSTAT", "DATA") for s in "+-"]

def shaft_es(shape, af, internal, pos, fs):
    rc = (af - 2 * T_WALL) / 2 / math.cos(math.pi / npoly(shape)); n = int(math.ceil(rc / H)) + 3
    x = np.arange(-n, n + 1) * H; X, Y = np.meshgrid(x, x); cav = outline(shape, af - 2 * T_WALL)
    if internal != "none": cav = cav.difference(Point(0, 0).buffer(HUB_OD / 2, 128)).difference(hubweb(shape, af))
    kind = np.where(contains_xy(cav, X, Y), 0, -1)
    ex, ey, cen = raster_strips(X, Y, [(fs[pos[g][0]], pos[g][1], g) for g in GROUPS], kind, SIG)
    C, phis = fv_solve(kind, ex, ey, len(SIG)); return C, phis, cen, (X, Y, kind)

def coplanar_es():
    """LANES side by side, strip bottom 2.0 mm above a ground plane; grounded box 10 mm clear elsewhere"""
    lay, u = [], 0.0
    for name, w in CFX.LANES:
        if name in ("TX_A", "TX_B"): lay.append((name, u, u + w, "sig"))
        elif name in ("VIN_H", "GND_H"): lay.append((name, u, u + w, "gnd"))
        elif name.split()[0] in ("TXCMD", "TXSTAT", "DATA"):
            nn = name.split()[0]; lay += [(nn + "+", u, u + 0.15, "sig"), (nn + "-", u + 0.3, u + 0.45, "sig")]
            if nn != "DATA": u += 0.15                                   # inter-pair gap added (see docstring)
        elif name.startswith("REF"):
            a = name[3]; lay += [(f"G{a}a", u, u + 0.3, "gnd"), (f"REF{a}+", u + 0.45, u + 0.6, "sig"), (f"REF{a}-", u + 0.75, u + 0.9, "sig"), (f"G{a}b", u + 1.05, u + 1.35, "gnd")]
        u += w
    W = u; xs = np.arange(-int(10 / H), int((W + 10) / H) + 1) * H; ys = np.arange(0, int(12 / H) + 1) * H; X, Y = np.meshgrid(xs, ys)
    kind = np.where((Y <= 1e-9) | (Y >= ys[-1] - 1e-9) | (X <= xs[0] + 1e-9) | (X >= xs[-1] - 1e-9), -1, 0)
    xm_x, ym_x = (X[:, :-1] + X[:, 1:]) / 2, Y[:, :-1]; xm_y, ym_y = X[:-1, :], (Y[:-1, :] + Y[1:, :]) / 2; y0 = 2.0
    ex = np.where((xm_x >= 0) & (xm_x <= W) & (ym_x >= y0) & (ym_x <= y0 + STRIP_T), EPS_PI, 1.0)
    ey = np.where((xm_y >= 0) & (xm_y <= W) & (ym_y >= y0) & (ym_y <= y0 + STRIP_T), EPS_PI, 1.0); cen = {}
    for name, a, b, net in lay:
        m = (X >= a - 1e-9) & (X <= b + 1e-9) & (Y >= y0 + TR_V0 - H / 2) & (Y <= y0 + TR_V1 + H / 2)
        kind[m] = -1 if net == "gnd" else SIG.index(name) + 1; cen[name] = ((a + b) / 2, y0 + 0.075)
    C, _ = fv_solve(kind, ex, ey, len(SIG)); return C, cen, W

# ---------------------------------------------------------------- shielding
def shielding():
    r = dict(assumptions="sigma_CF 1e4 S/m (ASSUMED; CF is anisotropic, 1e3-1e5 S/m typical), Cu 5.8e7 S/m; |H_in/H_out| = 1/|1 + j w mu0 sigma t d/2| at 100 kHz, "
             "d = chamber depth (inner apothem - hub radius); closed-enclosure formula, so an upper bound on what open radial webs give", skin_depth_mm={})
    for f in (1e4, 1e5, 1e6):
        r["skin_depth_mm"][f"{f:g}Hz"] = dict(CF=round(K.skin_depth(1 / SIG_CF, f) * 1e3, 2), Cu=round(K.skin_depth(1 / SIG_CU, f) * 1e3, 4))
    r["thin_vs_skin"] = "CF wall 1.2 mm and web 0.6 mm << delta_CF (>= 1.6 mm at 1 MHz, 50 mm at 10 kHz); Cu 2 x 18 um << delta_Cu (66 um at 1 MHz): thin-sheet regime"
    w = 2 * math.pi * 1e5; r["separator_100kHz"] = {}
    for shape in SHAPES:
        for af in AFS_ALLOC:
            d = (af / 2 - T_WALL - HUB_OD / 2) * 1e-3; att = lambda st: 1 / abs(1 + 1j * w * MU0 * st * d / 2)
            r["separator_100kHz"][f"{shape}{af:g}"] = dict(d_mm=round(d * 1e3, 2), CF_web_0p6=round(att(SIG_CF * WEB_T * 1e-3), 4),
                CF_wall_1p2=round(att(SIG_CF * T_WALL * 1e-3), 4), Cu_2x18um=round(att(SIG_CU * 2 * T_CU * 1e-3), 4),
                Cu_plus_CF_web=round(att(SIG_CU * 2 * T_CU * 1e-3 + SIG_CF * WEB_T * 1e-3), 4),
                Cu_dB=round(20 * math.log10(att(SIG_CU * 2 * T_CU * 1e-3)), 1))
    return r

# ---------------------------------------------------------------- CAD
def build_cad(pos, fs):
    import cadquery as cq
    L, af, t = 300.0, 31.0, T_WALL; d_out, d_in = 2 * af / math.sqrt(3), 2 * (af - 2 * t) / math.sqrt(3); P = {}
    shell = cq.Workplane("XY").polygon(6, d_out).polygon(6, d_in).extrude(L)
    used = {pos[g][0] for g in ("HV", "PWR", "REF")}; empty = [f for f in fs if f["k"] not in used and f["k"] != pos["DIG"][0]] or [f for f in fs if f["k"] not in used]
    def face_cut(f, w_t, w_z, z): return cq.Workplane("XY").box(4.0, w_t, w_z).translate((af / 2 - 0.6, 0, z)).rotate((0, 0, 0), (0, 0, 1), math.degrees(f["th"]))
    shell = shell.cut(face_cut(empty[0], 12.0, 20.0, 120.0))                                                                               # camlock window 12 across x 20 along
    shell = shell.cut(face_cut(fs[pos["HV"][0]], 16.0, 2.0, L - 15.0))                                                                      # flex exit slot 16 x 2, HV face
    P["shell"] = shell; win_face = round(math.degrees(empty[0]["th"]), 1)
    hub = cq.Workplane("XY").circle(HUB_OD / 2).circle(HUB_ID / 2).extrude(L); rci = d_in / 2
    for k in range(6):
        hub = hub.union(cq.Workplane("XY").box(rci - HUB_ID / 2 - 0.2, WEB_T, L).translate(((rci + HUB_ID / 2 + 0.2) / 2, 0, L / 2)).rotate((0, 0, 0), (0, 0, 1), 60 * k))
    P["hub_cu"] = hub
    for g in ("HV", "PWR", "REF"):
        f = fs[pos[g][0]]; uc = pos[g][1] + GW[g] / 2                                  # local (radial, tangent) box rotated to the face normal = fxy()
        P[f"flex_{g}"] = cq.Workplane("XY").box(STRIP_T, GW[g], L - 20).translate((f["r"] - STRIP_T / 2, uc, (L - 20) / 2)).rotate((0, 0, 0), (0, 0, 1), math.degrees(f["th"]))
    rb = (POF_B + 0.02) / math.sqrt(3)                                                                                                        # bare POF: 3 x 1.0 (jacketed 2.2 do not fit ID 4)
    P["pof_bare"] = cq.Workplane("XY").pushPoints([(rb * math.cos(a), rb * math.sin(a)) for a in (math.pi / 2, math.pi / 2 + 2 * math.pi / 3, math.pi / 2 + 4 * math.pi / 3)]).circle(POF_B / 2).extrude(L + 10)
    zp, xr = L + 18.0, d_out / 2; kw = 10.0; xk = xr - kw / 2                                                                                # pin axis (x) at z = 318
    collar = cq.Workplane("XY").polygon(6, d_out).polygon(6, d_in).extrude(4).translate((0, 0, L))
    hinge = collar
    for s in (-1, 1):
        lug = cq.Workplane("XY").box(kw, 24, zp - L).translate((s * xk, 0, L + (zp - L) / 2))
        kn = cq.Workplane("YZ").circle(17).extrude(kw).translate((s * xk - kw / 2, 0, zp))
        hinge = hinge.union(lug).union(kn)
    hinge = hinge.cut(cq.Workplane("YZ").circle(3.0).extrude(2 * xr + 2).translate((-xr - 1, 0, zp)))
    hinge = hinge.cut(cq.Workplane("YZ").circle(4.0).extrude(6.0).translate((xr - 6.0, 0, zp)))                                             # fibre rotary-joint cavity D8 x 6
    P["hinge"] = hinge
    P["pin"] = cq.Workplane("YZ").circle(3.0).circle(1.4).extrude(2 * xr - 6.0).translate((-xr, 0, zp))                                     # hollow pin ends at the cavity floor
    wd = 2 * (xk - kw / 2) - 1.0
    P["drum"] = cq.Workplane("YZ").circle(15.0).circle(3.0).extrude(wd).translate((-wd / 2, 0, zp))
    tw = cq.Workplane("XY").rect(21, 21).rect(21 - 2 * t, 21 - 2 * t).extrude(L).translate((55, 0, 0)); P["telescope_sq21"] = tw
    files = []
    for k, w in P.items():
        fn = os.path.join(OUT, f"hexseg_{k}.stl"); cq.exporters.export(w, fn, tolerance=0.05, angularTolerance=0.2); files.append(os.path.basename(fn))
    cq.exporters.export(cq.Workplane("XY").add(cq.Compound.makeCompound([w.val() for w in P.values()])), os.path.join(OUT, "hexseg.step")); files.append("hexseg.step")
    # interference checks (volumes of pairwise intersections that must be empty)
    chk = {}
    for a, b in (("drum", "hinge"), ("drum", "shell"), ("pof_bare", "hub_cu"), ("flex_HV", "hub_cu"), ("flex_REF", "shell"), ("pin", "drum")):
        try: chk[f"{a}^{b}_mm3"] = round(P[a].val().intersect(P[b].val()).Volume(), 3)
        except Exception as e: chk[f"{a}^{b}_mm3"] = f"error {e}"
    chk["camlock_window_face_normal_deg"] = win_face
    return files, P, chk

def render(files):
    import pyvista as pv
    pv.OFF_SCREEN = True; pl = pv.Plotter(off_screen=True, window_size=(1800, 1000), shape=(1, 2))
    col = dict(shell="#555555", hub_cu="#c87533", flex_HV="#d62728", flex_PWR="#2ca02c", flex_REF="#1f77b4", pof_bare="#ffdd00", hinge="#777777", pin="#bbbbbb", drum="#9467bd", telescope_sq21="#8c8c8c")
    for f in files:
        if f.endswith(".stl"):
            k = f[7:-4]; pl.add_mesh(pv.read(os.path.join(OUT, f)), color=col.get(k, "white"), opacity=0.35 if k == "shell" else 1.0, smooth_shading=False)
    pl.add_text("hexseg: hex AF31 hub6_cu 300 mm segment + hinge; square 21 telescope tube", font_size=10); pl.view_isometric(); pl.reset_camera(); pl.camera.zoom(1.1)
    pl.subplot(0, 1)
    for f in files:
        if f.endswith(".stl") and "telescope" not in f:
            k = f[7:-4]; pl.add_mesh(pv.read(os.path.join(OUT, f)), color=col.get(k, "white"), opacity=0.25 if k in ("shell", "hinge") else 1.0)
    pl.add_text("hinge end: knuckles, hollow pin, drum, fibre cavity, slot; strips red HV / green PWR / blue REF, POF yellow", font_size=9)
    pl.camera.focal_point = (0, 0, 270); pl.camera.position = (150, 120, 400); pl.camera.view_up = (0, 0, 1)
    pl.screenshot(os.path.join(OUT, "hexseg_view.png")); pl.close()

def field_png(phis, grid, title):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    X, Y, kind = grid; phi = phis[SIG.index("TX_A")]; fig, axs = plt.subplots(1, 2, figsize=(14, 6.8))
    for ax, lim in zip(axs, (None, (-6, 6, 9.5, 15.0))):
        ax.imshow(np.where(kind == -1, 0.6, np.where(kind > 0, 0.15, 1.0)), extent=(X.min(), X.max(), Y.min(), Y.max()), origin="lower", cmap="gray", vmin=0, vmax=1)
        lv = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 0.03, 0.1, 0.2, 0.4, 0.6, 0.8]
        cs = ax.contour(X, Y, np.where(kind == 0, phi, np.nan), levels=lv, cmap="viridis", linewidths=0.8); ax.clabel(cs, fontsize=6, fmt="%g")
        ax.set_aspect("equal"); ax.set_xlabel("x mm"); ax.set_ylabel("y mm")
        if lim: ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3]); ax.set_title("zoom: HV strip (top face)")
        else: ax.set_title(title)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "hexseg_field.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- main
def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    res = dict(status="", solver_check=coax_check(), sections={}, allocation={}, coupling={}, coplanar_reference={}, shielding=shielding(), cad={}, findings=[])
    for shape in SHAPES:
        for af in AFS:
            for it in INTERNALS: res["sections"][f"{shape}{af:g}|{it}"] = section(shape, af, it)
    Cc, cenc, Wc = coplanar_es(); cp = couple_metrics(Cc, SIG, cenc)
    res["coplanar_reference"] = dict(geometry=f"rf2_cordflex.LANES side by side ({Wc:.2f} mm incl. 2 x 0.15 inter-pair gaps), strip bottom 2.0 mm above ground plane, grounded box 10 mm clear",
                                     **{k: (round(v, 5) if isinstance(v, float) else v) for k, v in cp.items()},
                                     C_TXA_self_pF_per_m=round(Cc[0, 0] * 1e12, 2), C_TXA_TXB_pF_per_m=round(-Cc[0, 1] * 1e12, 3),
                                     cps_formula_TX_pair_pF_per_m=round(CFX.cps_c_pf_per_m(), 2))
    keep = {}
    for shape in SHAPES:
        for af in AFS_ALLOC:
            alloc, pos, fs = allocate(shape, af); es = {}
            for it in INTERNALS:
                key = f"{shape}{af:g}|{it}"; a = dict(alloc); a["central_bore"] = central_bore(it); res["allocation"][key] = a
                if it == "hub6_cu": C, phis, cen, grid = es["hub6"]                                    # identical electrostatics (webs grounded either way)
                else: es[it] = shaft_es(shape, af, it, pos, fs); C, phis, cen, grid = es[it]
                m = couple_metrics(C, SIG, {k: tuple(v) for k, v in cen.items()})
                m["ratio_vs_coplanar_tx_ref"] = m["C_tx_ref_pF_per_m"] / cp["C_tx_ref_pF_per_m"]; m["ratio_vs_coplanar_data_ref"] = m["C_data_ref_pF_per_m"] / cp["C_data_ref_pF_per_m"]
                m = {k: (float(f"{v:.4g}") if isinstance(v, float) else v) for k, v in m.items()}
                m["C_TXA_self_pF_per_m"] = round(C[0, 0] * 1e12, 2); m["C_TXA_DATA_pF_per_m"] = float(f"{max([0.0] + [-C[0, SIG.index(d)] for d in ('DATA+', 'DATA-')]) * 1e12:.4g}")
                m["C_matrix_names"] = SIG; m["C_matrix_pF_per_m"] = [[float(f"{c * 1e12:.5g}") for c in row] for row in C]
                if it != "none": m["note"] = ("each chamber is fully enclosed by grounded wall / webs / hub in this model, so the cross-chamber C is exactly 0 (below resolution); "
                                             "the real value is set by web-to-wall contact, web-end gaps and the flex exits (not modelled). M is free-space (CF transparent)" +
                                             ("; electrostatics identical to hub6, Cu shielding factor in shielding.separator_100kHz" if it == "hub6_cu" else ""))
                res["coupling"][key] = m
                if key == "hex31|hub6": keep = dict(phis=phis, grid=grid, pos=pos, fs=fs)
            print(f"{shape}{af:g} done {time.time() - t0:.0f} s", flush=True)
    field_png(keep["phis"], keep["grid"], "hex31 | hub6_cu: equipotentials, TX_A = 1 V, all else 0 V (log levels)")
    files, P, chk = build_cad(keep["pos"], keep["fs"]); render(files)
    res["cad"] = dict(files=files + ["hexseg_view.png", "hexseg_field.png"], interference_mm3=chk,
                      notes=["the 3 POF in the bore are modelled BARE (1.0 mm): 3 x 2.2 mm jacketed need a bundle of 4.74 mm > hub ID 4.0 (a hub ID >= 5.1 would take them)",
                             "Cu plating (18 um) is not modelled as a separate solid: hexseg_hub_cu.stl is the plated hub + webs envelope",
                             f"camlock window 20 x 12 in an empty face (normal {chk['camlock_window_face_normal_deg']} deg); flex exit slot 16 x 2 in the HV (top) face 15 mm from the hinge end",
                             "hinge pin axis along x at z = 318 mm; knuckles OD 34 x 10 at the hex vertices' x extent; drum OD 30 between them"])
    # findings
    S, Cp, Al = res["sections"], res["coupling"], res["allocation"]
    res["findings"] += [
        f"solver check: coax FD {res['solver_check']['C_fd_pF_per_m']} vs exact {res['solver_check']['C_exact_pF_per_m']} pF/m ({res['solver_check']['error_pct']} %)",
        f"coplanar single flex (LANES): TX_A->nearest REF {cp['C_tx_ref_pF_per_m']:.3g} pF/m, DATA->nearest REF {cp['C_data_ref_pF_per_m']:.3g} pF/m, M {cp['M_tx_ref_nH_per_m']:.3g} nH/m "
        f"({cp['V_ref_per_m_8A_6us_mV']:.3g} mV/m at 8 A / 6 us, {cp['V_ref_per_m_47A_5us_mV']:.3g} mV/m at 47 A / 5 us)",
        "every group fits one face in every variant studied (HV strip %.2f mm vs smallest usable face %.2f mm, hex 21); not_fitting is empty" % (GW["HV"], S["hex21|none"]["face_width_mm"]),
        "central bore (hub ID 4.0): 6 digital wires (PTFE AWG30 OD 0.5 ASSUMED) bundle 1.50 mm FIT; 3 POF bare 1.0 mm bundle 2.15 mm FIT; 3 POF jacketed 2.2 mm bundle 4.74 mm DO NOT FIT; 'none' variants have no bore",
        "hub6 and hub6_cu are electrostatically identical once the CF wall and webs are grounded; Cu adds magnetic separation only (thin-sheet, see shielding)",
        "magnetic coupling is set by filament geometry (free space): CF (delta >= 1.6 mm up to 1 MHz) is transparent; 2 x 18 um Cu separators give at most the 100 kHz factor in shielding (upper bound)",
        "hub6 webs (0.6 mm CF) add %.0f-%.0f %% mass for %.0f-%.0f %% more I (hex 21-31); the Cu plating adds a further %.1f-%.1f g/m" % (
            100 * (S['hex21|hub6']['mass_g_per_m'] / S['hex21|none']['mass_g_per_m'] - 1), 100 * (S['hex31|hub6']['mass_g_per_m'] / S['hex31|none']['mass_g_per_m'] - 1),
            100 * (S['hex21|hub6']['I_mm4'] / S['hex21|none']['I_mm4'] - 1), 100 * (S['hex31|hub6']['I_mm4'] / S['hex31|none']['I_mm4'] - 1), S['hex21|hub6_cu']['cu_g_per_m'], S['hex31|hub6_cu']['cu_g_per_m']),
        "allocation optimum (lexicographic HV-REF, DIG-REF, PWR-REF centroid distance; HV alone): HV on the top face, REF on the opposite face pushed to one end, digital + power share a face adjacent to HV; in hub variants each group therefore sits in its own chamber except digital + power",
        "LANES packs the three digital pair lanes edge to edge (adjacent pairs' traces touch); a 0.15 mm inter-pair gap was added here; rf2_cordflex should be checked",
    ]
    for key, m in Cp.items():
        s = S[key]; res["findings"].append(f"{key}: C TX_A-REF {m['C_tx_ref_pF_per_m']:.3g} pF/m (x{m['ratio_vs_coplanar_tx_ref']:.2g} coplanar), C DATA-REF {m['C_data_ref_pF_per_m']:.3g} pF/m "
                                           f"(x{m['ratio_vs_coplanar_data_ref']:.2g}), M {m['M_tx_ref_nH_per_m']:.3g} nH/m, {s['mass_g_per_m']} g/m, I {s['I_mm4']} mm4")
    res["status"] = (f"MODELED (no bench test): {len(S)} sections, {len(Cp)} coupled variants, coax check {res['solver_check']['error_pct']} %, "
                     f"CAD interference {'none' if all(isinstance(v, float) and v < 1e-3 for k, v in chk.items() if k.endswith('_mm3')) else chk}; run {time.time() - t0:.0f} s")
    json.dump(res, open(os.path.join(OUT, "rf2_hex_section.json"), "w"), indent=1, default=float)
    print(res["status"]); [print(" -", f) for f in res["findings"]]
    return res

if __name__ == "__main__":
    main(); sys.exit(0)
