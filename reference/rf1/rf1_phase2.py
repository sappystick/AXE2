#!/usr/bin/env python3
"""RF1 phase 2 (2026-10-29): receive-lead pickup and its unit-to-unit spread, and clock crosstalk into the analog lines of the AB1 <-> CB1D link.
Built on a copy of the receive simulation (src/sbq_sim_baseline_copy.py = src/sim/sbq_sim.py at the baseline commit): the same transmit model (sim_head1.py
sections S1-S3: the six former paths of kit_v15/LOW/paths.pkl, Mutual(), M_mono, the turn-off dI/dt), so the lead numbers are in the same units as the board
leak of kit_v22/sbq_sim.json (peak volts at turn-off, per the 20 A design point).
1. Lead pickup: the SB1R-QA / QB lead pair from the board pads to AB1A J1 (hub frame: J1 at x -36.7, y 0, z 12.7; QA pads (+-4, 33), QB pads as sbq_geometry),
   path rising to the gallery (z 6.0), across it, then up the floor slot (ASSUMED path: the repo has no lead-dress geometry). The pair is two conductors at
   +-s/2 about the path, rotated by theta(l) about it; the closed loop (out on one, back on the other) gives M with the transmit paths.
   Monte Carlo, 300 units each: (a) AWG36 untwisted, s 0.17-1.0 mm, random theta, path wander +-2 mm; (b) AWG36 twisted, s 0.17-0.30 mm, pitch 5-15 mm, random
   phase, wander +-2 mm; (c) flex broadside pair, s 0.050 mm +-10 %, theta at the design orientation +-5 deg, wander +-0.3 mm (soldered and potted).
2. Clock crosstalk: 2D finite-difference capacitance matrix of each link cross-section (Laplace with dielectric, Gauss charge), L = mu0 eps0 C0^-1 (TEM, homogeneous
   reference). Victims MONO_IN and VCM_OUT (analog, on AB1B J2), aggressors SCLK, CS, SDO1, SDO2, BLANK. Cross-sections: (i) 12-way 0.635 mm IDC ribbon in J2 pin
   order, AWG28 (d 0.32 mm), PVC er 3.5, no plane (ASSUMED class values); (ii) RF1 hinge: 2-layer flex, signals 0.10 mm on L1 at 0.30 mm pitch with a ground
   guard trace between every analog victim and its neighbours, a solid-equivalent ground on L2 50 um below (the hatched plane is less: the result is a bound),
   polyimide er 4 (Rigiflex flex table), coverlay 25 um. Coupled noise bound for an electrically short line: capacitive step on a victim node of C_node:
   dV = dV_aggr * Cm L / (C_node + Cself L); inductive: Lm L dI/dt with dI/dt from the aggressor charging its own line in the edge time.
MODELED; nothing built. usage (repo root): python3 experiments/RF1_rigidflex/rf1_phase2.py"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261029)

# ------------------------------------------------------------------ 1. lead pickup (transmit model of the copied receive simulation)
def lead_pickup(N=300):
    cwd = os.getcwd(); os.chdir(os.path.join(ROOT, "work"))
    src = open("sim_head1.py").read().split("# ======================= S4")[0]; ns = {}
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()): exec(src, ns)
    Mutual, TXs, M_mono, wf = ns["Mutual"], ns["TXs"], ns["M_mono"], ns["wf"]
    G = json.load(open("kit_v22/sbq_geometry.json")); base = json.load(open("kit_v22/sbq_sim.json")); os.chdir(cwd)
    didt = max(np.max(np.abs(np.gradient(w[1], w[0]))) for w in wf.values())          # A/s, the same scale factor as sbq_sim (peak V = |M| dI/dt)
    J1 = np.array([-36.7, 0.0, 12.7])
    boards = {"QA": (np.mean(G["pads"], axis=0), 3.18), "QB": (np.mean(G["padsB"], axis=0), 2.08)}
    def path(p0, z0, wander):
        P = [np.array([p0[0], p0[1], z0]), np.array([p0[0], p0[1], 6.0]), np.array([J1[0] + 3.0, J1[1], 6.0]), np.array([J1[0] + 3.0, J1[1], 9.8]), J1]
        pts = []
        for a, b in zip(P[:-1], P[1:]):
            n = max(2, int(np.linalg.norm(b - a) / 0.5)); pts += [a + (b - a) * t for t in np.linspace(0, 1, n, endpoint=False)]
        pts.append(P[-1]); pts = np.array(pts)
        if wander:                                                                    # smooth lateral wander (dress), zero at both soldered ends
            L = len(pts); s = np.linspace(0, 1, L); w = np.zeros((L, 3))
            for k in (1, 2, 3): w += np.outer(np.sin(k * np.pi * s), rng.normal(0, wander / k, 3))
            w[:, 2] *= 0.3; pts = pts + w
        return pts
    def loop(pts, s, theta_fn):
        t = np.gradient(pts, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]
        ref = np.where(np.abs(t[:, 2:3]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 0, 1.0]]))
        n1 = np.cross(t, ref); n1 /= np.linalg.norm(n1, axis=1)[:, None]; n2 = np.cross(t, n1)
        l = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]; th = theta_fn(l)
        o = (s / 2) * (np.cos(th)[:, None] * n1 + np.sin(th)[:, None] * n2)
        a, b = pts + o, pts - o
        return np.vstack([a, b[::-1], a[:1]]) * 1e-3
    def M_of(lp): return Mutual(TXs, [lp]) / 6.0
    res = {}
    for bn, (p0, z0) in boards.items():
        # design orientation for the flex: the theta (fixed along the path) that minimises |M| on the nominal path
        nom = path(p0, z0, 0.0); ths = np.radians(np.arange(0, 180, 5)); Ms = [abs(M_of(loop(nom, 0.05, lambda l, t=t: np.full(len(l), t)))) for t in ths]
        th_design = float(ths[int(np.argmin(Ms))]); th_worst = float(ths[int(np.argmax(Ms))])
        sc = {}
        t0 = time.time()
        for case in ("AWG36 untwisted", "AWG36 twisted", "flex broadside (RF1)"):
            v = []
            for _ in range(N):
                if case == "AWG36 untwisted":
                    pts = path(p0, z0, 2.0); s = rng.uniform(0.17, 1.0); t0_ = rng.uniform(0, 2 * np.pi); fn = lambda l, t=t0_: np.full(len(l), t)
                elif case == "AWG36 twisted":
                    pts = path(p0, z0, 2.0); s = rng.uniform(0.17, 0.30); pitch = rng.uniform(5, 15); ph = rng.uniform(0, 2 * np.pi); fn = lambda l, p=pitch, q=ph: q + 2 * np.pi * l / p
                else:
                    pts = path(p0, z0, 0.3); s = 0.05 * rng.uniform(0.9, 1.1); t0_ = th_design + np.radians(rng.uniform(-5, 5)); fn = lambda l, t=t0_: np.full(len(l), t)
                v.append(M_of(loop(pts, s, fn)) * didt * 1e3)                          # signed mV peak at turn-off
            v = np.array(v)
            sc[case] = dict(mean_mV=round(float(v.mean()), 4), std_mV=round(float(v.std()), 4), p95_abs_mV=round(float(np.percentile(np.abs(v), 95)), 4), max_abs_mV=round(float(np.abs(v).max()), 4))
        sc["flex at the worst fixed orientation (if routed carelessly)"] = dict(abs_mV=round(abs(M_of(loop(nom, 0.05, lambda l: np.full(len(l), th_worst)))) * didt * 1e3, 4))
        board_key = "QUAD-A board" if bn == "QA" else "QUAD-B board (rotated 45 deg)"
        sc["board_leak_reference_mV"] = {k: round(base["leak"][board_key][k]["peak_V"] * 1e3, 3) for k in ("aligned", "0.1 mm x", "0.5 mm x")}
        sc["design_theta_deg"] = round(math.degrees(th_design), 1); sc["seconds"] = round(time.time() - t0, 1)
        res[bn] = sc
    return dict(didt_A_per_s=round(float(didt), 1), units="peak mV at turn-off, the same scale as kit_v22/sbq_sim.json leak", path="ASSUMED: pad -> z 6 gallery -> floor slot -> AB1A J1 (x -36.7, z 12.7)", boards=res)

# ------------------------------------------------------------------ 2. clock crosstalk: 2D FD capacitance
EPS0, MU0 = 8.854e-12, 4e-7 * math.pi
def cap_matrix(cond, eps_fn, box, h):
    """cond: list of boolean masks on the grid (conductors), eps_fn grid of relative permittivity; outer boundary at 0 V (far ground). Returns C (F/m)."""
    from scipy.sparse import lil_matrix, csr_matrix
    from scipy.sparse.linalg import splu
    ny, nx = eps_fn.shape; allc = np.zeros_like(eps_fn, bool)
    for c in cond: allc |= c
    idx = -np.ones((ny, nx), int); free = ~allc; free[0, :] = free[-1, :] = free[:, 0] = free[:, -1] = False
    idx[free] = np.arange(free.sum()); n = free.sum()
    A = lil_matrix((n, n)); e = eps_fn
    # face permittivities (harmonic mean is not needed for a cell-centred mean; arithmetic mean of the two cells)
    ys, xs = np.nonzero(free)
    rows_b = []
    for k, (i, j) in enumerate(zip(ys, xs)):
        diag = 0.0
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ii, jj = i + di, j + dj; w = 0.5 * (e[i, j] + e[ii, jj]); diag += w
            if free[ii, jj]: A[k, idx[ii, jj]] = -w
        A[k, k] = diag
    lu = splu(csr_matrix(A).tocsc())
    C = np.zeros((len(cond), len(cond)))
    for a, ca in enumerate(cond):
        b = np.zeros(n)
        for k, (i, j) in enumerate(zip(ys, xs)):
            s = 0.0
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ii, jj = i + di, j + dj
                if ca[ii, jj]: s += 0.5 * (e[i, j] + e[ii, jj])
            b[k] = s
        phi = np.zeros((ny, nx)); phi[ca] = 1.0; phi[free] = lu.solve(b)
        for c_, cb in enumerate(cond):                                                 # charge on conductor cb: sum of eps * (phi_cond - phi_neighbour) over its boundary faces
            q = 0.0; bi, bj = np.nonzero(cb)
            for i, j in zip(bi, bj):
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < ny and 0 <= jj < nx and not allc[ii, jj]: q += 0.5 * (e[i, j] + e[ii, jj]) * (phi[i, j] - phi[ii, jj])
            C[c_, a] = q * EPS0
    return 0.5 * (C + C.T)

def section(kind, h=0.025):
    """build the grid for a cross-section; returns names, masks, eps(er), eps(vacuum)"""
    if kind == "ribbon":
        names = ["+5VA", "GND", "+3V3D", "GND", "SCLK", "CS", "SDO1", "SDO2", "BLANK", "MONO_IN", "VCM_OUT", "GND"]   # AB1B J2 order = ribbon order
        pitch, d, er = 0.635, 0.32, 3.5; W = len(names) * pitch + 6.0; H = 6.0
        nx, ny = int(W / h), int(H / h); X, Y = np.meshgrid((np.arange(nx) + 0.5) * h, (np.arange(ny) + 0.5) * h)
        eps = np.ones((ny, nx)); x0 = 3.0 + pitch / 2; yc = H / 2
        eps[(np.abs(Y - yc) <= 0.45) & (X >= 2.9) & (X <= W - 2.9)] = er
        masks = [((X - (x0 + k * pitch)) ** 2 + (Y - yc) ** 2) <= (d / 2) ** 2 for k in range(len(names))]
    else:
        # RF1 hinge, victims first-class: order on L1 with guard grounds around the analog pair, L2 ground plane
        names = ["+5VA", "GND", "+3V3D", "GND", "SCLK", "GND", "CS", "SDO1", "SDO2", "BLANK", "GND", "MONO_IN", "GND", "VCM_OUT", "GND", "GNDPLANE"]
        pitch, tw, tt, er = 0.30, 0.10, 0.035, 4.0; W = (len(names) - 1) * pitch + 4.0; H = 3.0
        nx, ny = int(W / h), int(H / h); X, Y = np.meshgrid((np.arange(nx) + 0.5) * h, (np.arange(ny) + 0.5) * h)
        y_plane = 1.2; y_core_top = y_plane + 0.035 + 0.050; eps = np.ones((ny, nx))
        eps[(Y >= y_plane - 0.025 - 0.025) & (Y <= y_core_top + tt + 0.025) & (X >= 1.0) & (X <= W - 1.0)] = er     # base film, core, coverlay
        masks = []
        for k, nm in enumerate(names[:-1]):
            xc = 2.0 + k * pitch; masks.append((np.abs(X - xc) <= tw / 2) & (Y >= y_core_top) & (Y <= y_core_top + tt + 1e-9))
        masks.append((X >= 1.2) & (X <= W - 1.2) & (Y >= y_plane) & (Y <= y_plane + 0.035))
    return names, masks, eps, np.ones_like(eps)

def crosstalk():
    out = {}
    for kind, L_m in (("ribbon", 0.135), ("hinge", 0.128)):                            # route lengths from phase 1 (link_path_check), m
        names, masks, eps, eps0 = section(kind)
        # ground conductors are tied together (one reference): merge every GND mask into one conductor
        g = np.zeros_like(masks[0]); keep = []; kn = []
        for nm, m in zip(names, masks):
            if nm.startswith("GND"): g |= m
            else: keep.append(m); kn.append(nm)
        cond = keep + [g]; kn = kn + ["GND"]
        C = cap_matrix(cond, eps, None, 0.025); C0 = cap_matrix(cond, eps0, None, 0.025)
        sig = list(range(len(kn) - 1))                                                  # reference: GND conductor + far boundary; reduce to signal conductors
        Cs, C0s = C[np.ix_(sig, sig)], C0[np.ix_(sig, sig)]
        Lm = MU0 * EPS0 * np.linalg.inv(C0s)
        res = {}
        for v in ("MONO_IN", "VCM_OUT"):
            iv = kn.index(v); rows = {}
            for a in ("SCLK", "CS", "SDO1", "SDO2", "BLANK"):
                ia = kn.index(a); cm = -Cs[iv, ia]; kc = cm / Cs[iv, iv]; kl = Lm[iv, ia] / Lm[iv, iv]
                # bounds on a victim node of C_node (MONO_IN: 100 pF ASSUMED input filter + ADC; VCM_OUT: buffer output, 10 ohm isolation R in RF1)
                dV, tr = 3.3, 2e-9; C_node = 100e-12
                v_cap = dV * cm * L_m / (C_node + Cs[iv, iv] * L_m)
                Ia = Cs[ia, ia] * L_m * dV / tr                                         # aggressor current charging its own line
                v_ind = Lm[iv, ia] * L_m * Ia / tr
                rows[a] = dict(Cm_pF_per_m=round(cm * 1e12, 3), kC=round(kc, 4), kL=round(kl, 4), v_cap_mV=round(v_cap * 1e3, 3), v_ind_mV=round(v_ind * 1e3, 3))
            res[v] = rows
        out[kind] = dict(length_m=L_m, conductors=kn, victims=res, C_self_pF_per_m={n: round(Cs[i, i] * 1e12, 2) for i, n in enumerate(kn[:-1])})
    lsb_uV = 76.29                                                                       # AD7389-4 LSB (DATASHEET_LOG B6)
    for v in ("MONO_IN", "VCM_OUT"):
        out[f"{v}_worst_mV"] = {k: max(max(r["v_cap_mV"], r["v_ind_mV"]) for r in out[k]["victims"][v].values()) for k in ("ribbon", "hinge")}
        out[f"{v}_worst_LSB"] = {k: round(val * 1e3 / lsb_uV, 1) for k, val in out[f"{v}_worst_mV"].items()}
    out["assumed"] = "ribbon AWG28 0.32 mm in PVC er 3.5; victim node 100 pF; 3.3 V edge in 2 ns; hinge L2 plane solid-equivalent (a hatched plane couples more: bound)"
    return out

if __name__ == "__main__":
    t = time.time(); X = crosstalk(); print("crosstalk", {k: v for k, v in X.items() if k.endswith(("_mV", "_LSB"))}, round(time.time() - t, 1), "s")
    t = time.time(); L = lead_pickup(); print("leads", json.dumps(L["boards"], indent=0)[:1500], round(time.time() - t, 1), "s")
    json.dump(dict(status="MODELED (RF1 phase 2, side experiment)", lead_pickup=L, crosstalk=X), open(os.path.join(OUT, "rf1_phase2.json"), "w"), indent=1)
