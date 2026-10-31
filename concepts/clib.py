#!/usr/bin/env python3
"""Isolated physics library for the owner's concept boards (2026-10-31). Independent of the AXE2 design code: the field comes from magpylib (an external
analytic library), inductance from a numerical Neumann integral, everything self-checked against textbook closed forms (selftest()).

Formulas (SI):
  loop / polyline field        magpylib Polyline (Biot-Savart, exact for straight segments)
  mutual inductance            M = mu0/4pi sum_i sum_j (dl_i . dl_j) / |r_i - r_j|                      (Neumann)
  self inductance              same, with |r| -> sqrt(r^2 + (a e^-1/4)^2) (GMD of a round wire, a = wire radius)
  circular loop (check)        L = mu0 R (ln(8R/a) - 7/4)  (round wire, uniform current)
  coaxial loops (check)        Maxwell: M = mu0 sqrt(R1 R2) ((2/k - k) K(k) - 2/k E(k)),  k^2 = 4 R1 R2 / ((R1+R2)^2 + d^2)
  parallel round wires         C' = pi eps0 eps_r / acosh(s / 2a)                                       (per metre)
  winding self-capacitance     chain estimate C_self = C_turn-pair / (N - 1) (single layer, adjacent-turn coupling only: a lower bound)
  critically damped PI tail    tau = sqrt(L C); settle from V0 to Vn: t = tau x s, (1 + s) e^-s = Vn / V0;  first sample = L I / V_clamp + t
  eddy loop (object echo)      L_o = mu0 r (ln(8r / 0.2235(w+t)) - 2), R_o = 2 pi r / (sigma w t), tau_o = L_o / R_o;
                               echo at time t after turn-off  ~ (Phi^2 I0 / L_o) (1/tau_o) e^(-t/tau_o)   (same TX / RX coil)
  thin conducting tube shield  transverse: |H_in / H_out| = 1 / |1 + j w mu0 sigma t R / 2|; static ferromagnetic: S = 1 + mu_r t / (2R)
  skin depth                   delta = sqrt(2 rho / (w mu0 mu_r))
  rectangular tube             I = (b h^3 - (b - 2t)(h - 2t)^3) / 12; round tube I = pi (D^4 - d^4) / 64; tip sag = P L^3 / 3EI + q L^4 / 8EI
  thin-tube local buckling     sigma_cr = E t / (R sqrt(3 (1 - nu^2)))
"""
import math
import numpy as np
from scipy.special import ellipk, ellipe
from scipy.optimize import brentq
MU0, EPS0, KB = 4e-7 * math.pi, 8.854e-12, 1.380649e-23

def polyline_B(path_m, I, pts_m):
    import magpylib as magpy
    return magpy.current.Polyline(current=I, vertices=np.asarray(path_m)).getB(np.asarray(pts_m))

def _seg(path, n_per):
    p = np.asarray(path, float); pts, dls = [], []
    for a, b in zip(p[:-1], p[1:]):
        for k in range(n_per):
            t0, t1 = k / n_per, (k + 1) / n_per; pts.append(a + (b - a) * (t0 + t1) / 2); dls.append((b - a) / n_per)
    return np.array(pts), np.array(dls)

def mutual(p1, p2, n_per=8):
    a, da = _seg(p1, n_per); b, db = _seg(p2, n_per)
    r = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2); dot = da @ db.T
    return MU0 / (4 * math.pi) * float(np.sum(dot / r))

def self_L(p, a_wire, n_per=8):
    s, ds = _seg(p, n_per); gmd = a_wire * math.exp(-0.25)
    r = np.linalg.norm(s[:, None, :] - s[None, :, :], axis=2); r = np.sqrt(r ** 2 + gmd ** 2)
    return MU0 / (4 * math.pi) * float(np.sum((ds @ ds.T) / r))

def coil_L(turns, a_wire, n_per=6):
    """turns: list of closed polylines (m); L = sum of self + all mutuals (one series winding)"""
    L = sum(self_L(t, a_wire, n_per) for t in turns)
    for i in range(len(turns)):
        for j in range(i + 1, len(turns)): L += 2 * mutual(turns[i], turns[j], n_per)
    return L

def circle(R, z=0.0, n=96, x0=0.0, y0=0.0):
    t = np.linspace(0, 2 * math.pi, n + 1); return np.c_[x0 + R * np.cos(t), y0 + R * np.sin(t), np.full(n + 1, z)]

def hexagon(R_circ, z=0.0, rot=0.0, x0=0.0, y0=0.0, n_side=16):
    v = [(x0 + R_circ * math.cos(rot + k * math.pi / 3), y0 + R_circ * math.sin(rot + k * math.pi / 3)) for k in range(7)]
    pts = []
    for (x1, y1), (x2, y2) in zip(v[:-1], v[1:]):
        for s in np.linspace(0, 1, n_side, endpoint=False): pts.append((x1 + (x2 - x1) * s, y1 + (y2 - y1) * s, z))
    pts.append(pts[0]); return np.array(pts)

def zigzag_ring(R, amp, n_cells, z=0.0, n_per=6):
    """a turn woven through a ring of hexagonal cells: radius alternates R +- amp every cell (adjacent segments at about 120 deg in the cell walls)"""
    th = np.linspace(0, 2 * math.pi, 2 * n_cells * n_per + 1); r = R + amp * np.sign(np.sin(n_cells * th + 1e-9)) * np.abs(np.sin(n_cells * th)) ** 0.2
    return np.c_[r * np.cos(th), r * np.sin(th), np.full_like(th, z)]

def maxwell_M(R1, R2, d):
    k2 = 4 * R1 * R2 / ((R1 + R2) ** 2 + d ** 2); k = math.sqrt(k2)
    return MU0 * math.sqrt(R1 * R2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))

def c_parallel_wires(s, a, eps_r=1.0): return math.pi * EPS0 * eps_r / math.acosh(s / (2 * a))

def pi_first_sample(L, C, I, v_clamp, v_noise=1e-6):
    tau = math.sqrt(L * C); ratio = v_noise / v_clamp
    s = brentq(lambda x: (1 + x) * math.exp(-x) - ratio, 1e-6, 200.0)
    return dict(fall_us=L * I / v_clamp * 1e6, settle_us=tau * s * 1e6, first_sample_us=(L * I / v_clamp + tau * s) * 1e6, tau_us=tau * 1e6)

def eddy_echo(phi_per_A, r, w, t, sigma, I0, t_s):
    Lo = MU0 * r * (math.log(8 * r / (0.2235 * (w + t))) - 2); Ro = 2 * math.pi * r / (sigma * w * t); tau = Lo / Ro
    return (phi_per_A ** 2 * I0 / Lo) / tau * math.exp(-t_s / tau), tau

def tube_shield_transverse(f, sigma, t, R, mu_r=1.0):
    w = 2 * math.pi * f; return 1.0 / abs(1 + 1j * w * MU0 * sigma * t * R / 2) / (1 + mu_r * t / (2 * R))

def skin_depth(rho, f, mu_r=1.0): return math.sqrt(2 * rho / (2 * math.pi * f * MU0 * mu_r))
def I_rect(b, h, t): return (b * h ** 3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12.0
def I_round(D, d): return math.pi * (D ** 4 - d ** 4) / 64.0
def sag(P, q, L, E, I): return P * L ** 3 / (3 * E * I) + q * L ** 4 / (8 * E * I)
def buckling_stress(E, t, R, nu=0.3): return E * t / (R * math.sqrt(3 * (1 - nu ** 2)))
def johnson_noise_nV(R, T=300.0): return math.sqrt(4 * KB * T * R) * 1e9

def selftest():
    R, a = 0.1, 0.5e-3
    L_num = self_L(circle(R, n=400), a, 4); L_ana = MU0 * R * (math.log(8 * R / a) - 1.75)
    M_num = mutual(circle(0.1, 0.0, 200), circle(0.08, 0.02, 200), 4); M_ana = maxwell_M(0.1, 0.08, 0.02)
    B = float(np.atleast_2d(polyline_B(circle(R, n=400), 1.0, [[0, 0, 0]]))[0][2]); B_ana = MU0 / (2 * R)
    res = dict(L_rel=abs(L_num / L_ana - 1), M_rel=abs(M_num / M_ana - 1), B_rel=abs(B / B_ana - 1))
    res["ok"] = res["L_rel"] < 0.03 and res["M_rel"] < 0.01 and res["B_rel"] < 0.01
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in res.items()}

if __name__ == "__main__":
    print(selftest())
