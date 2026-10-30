#!/usr/bin/env python3
"""AXE2 option B: zone map of stray field, coupling and metal echoes inside the head (owner 2026-10-30: 'understand each effect and stray field per
zone'; shielding, isolation, potting). MODELED; ASSUMED values are marked. Option-B geometry: rf2_thin option B (board tier z 5.6-7.2, CB1D board
z 6.6-8.2, display 13.1) and the 5 x 6 rim coil (r 105.4-113.4, z 5.2-11.6, 26 turns, 323 uH, 8.17 A, 10.8 mJ).

1. Transmit field per zone: |B| at the peak current and the largest dB/dt (clamp 460 V / L) at each board's centre and at its edge nearest the coil;
   the EMF this induces in a 1 cm2 loop lying flat on that board (what layout loops must survive / reject).
2. Receive coupling per zone: mutual inductance from a flat 1 cm2 loop on each board into the mono, and the current step in that loop that would
   equal the gate noise (4.2e-8 V gate-mean, the rf2_rodin magnet budget): digital edges during the receive window must stay below it.
3. Metal echoes: every conductive object is a target sitting next to the coil. Each is modeled as concentric current rings (a flat plate) or one loop
   (a can, a closed border), excited by the coil's turn-off (step, conservative) and decaying with its own L/R; the EMF it returns to the mono is
   averaged over the first gate (16.3 us, width 8.2 us) and compared with the gate noise. Copper sigma 5.8e7, aluminium 3.5e7 S/m.
   Board planes: solid / hatched (pitch 1.0 mm, track 0.25 mm) with an open border / hatched with a CLOSED border ring (0.5 mm wide). Box boards as
   the disc of equal area (ASSUMED). 35 um copper per plane.
4. Potting near the coil: the winding capacitance (rf2_taper energy method) at eps_r 1.8 (syntactic foam, glass bubbles; UNVERIFIED, the 3M iM30K
   sheet gives no permittivity), 2.5 (the earlier assumption), 2.8 (silicone gel, UNVERIFIED) and 3.7 (MG 832TC epoxy, datasheet, DF 0.1 at 1 MHz),
   then the first gate (rf2_timing.simulate) and the mono depth.
usage: python3 rf2/rf2_zones.py -> rf2/results/rf2_zones.json, rf2/results/rf2_zones.png"""
import os, sys, json, math
import numpy as np
from scipy.linalg import eig
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C, rf2_taper as TP, rf2_rodin as RD, rf2_receiver_combo as RC
mu0 = C.mu0; OUT = os.path.join(HERE, "results"); E0 = 10.8e-3; SIG_CU, SIG_AL = 5.8e7, 3.5e7; GATE = 16.33e-6; NOISE_GATE = 4.21e-8
def deg(r, d): return (r * math.cos(math.radians(d)), r * math.sin(math.radians(d)))
T = [(TP.geom(s)[0] * 1e-3, TP.geom(s)[1] * 1e-3, 1) for s in TP.sites(*TP.SHAPES["rect 5 x 6"])]
L = C.L_turns(T); I0 = math.sqrt(2 * E0 / L); DIDT = 460.0 / L
# option-B boards: centre (mm), equivalent radius (mm), board mid z (mm), copper planes (ASSUMED counts), what
BOARDS = {"CB1D (controller)": ((0.0, 0.0), 39.0, 7.4, 2), "AB1A (analog)": (deg(82, 106), 20.0, 6.4, 2), "AB1B (analog)": (deg(82, 137), 20.0, 6.4, 2),
          "MP1 (mono preamp)": ((-76.0, 14.0), math.sqrt(26 * 18 / math.pi), 6.4, 2), "TXJ (coil-lead board)": ((-99.5, 3.4), math.sqrt(9 * 15 / math.pi), 6.4, 1),
          "LR1 display flex (centre)": ((0.0, 0.0), 104.0, 13.2, 0), "QA / QB receive boards": ((0.0, 0.0), 114.0, 2.4, 0)}
def Bc(P): return C.B_turns(T, np.atleast_2d(P) * 1e-3)                                   # T per A at P (mm)
def flux_disc(c, a, z, n_r=24, n_t=72):
    """coil flux (Wb per A) through concentric annuli of a flat disc (centre c, radius a, height z; mm): returns ring radii (m) and fluxes"""
    edges = np.linspace(0, a, n_r + 1); rm = (edges[1:] + edges[:-1]) / 2; th = (np.arange(n_t) + 0.5) * 2 * math.pi / n_t; out = []
    for k in range(n_r):
        rr = np.linspace(edges[k], edges[k + 1], 4)[1:-1] if k else np.linspace(0, edges[1], 3)[1:]
        P = np.array([[c[0] + r * math.cos(t), c[1] + r * math.sin(t), z] for r in rr for t in th]); bz = Bc(P)[:, 2].reshape(len(rr), n_t)
        out.append(float(np.mean(bz) * math.pi * (edges[k + 1] ** 2 - edges[k] ** 2) * 1e-6))
    return rm * 1e-3, np.array(out), (edges[1:] - edges[:-1]) * 1e-3
def gate_mean(t_fn):
    tc = GATE; Tg = 0.5 * tc; tt = np.linspace(tc - Tg / 2, tc + Tg / 2, 60); return float(np.mean(t_fn(tt)))
def rings_echo(rm, phi, w, sigma, t):
    """plate as coplanar rings: L di/dt + R i = 0 after a step turn-off; i(0+) = L^-1 phi I0; EMF into the mono = phi . di/dt"""
    n = len(rm); Rv = 2 * math.pi * rm / (sigma * t * w); Lm = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            Lm[i, j] = mu0 * rm[i] * (math.log(8 * rm[i] / (0.2235 * (w[i] + t))) - 2) if i == j else C.M_coax(rm[i], 0, rm[j], 0)
    A = -np.linalg.solve(Lm, np.diag(Rv)); lam, V = eig(A); lam, V = lam.real, V.real; i0 = np.linalg.solve(Lm, phi * I0); c = np.linalg.solve(V, i0)
    emf = lambda tt: np.abs(np.sum((phi @ V)[:, None] * (c * lam)[:, None] * np.exp(lam[:, None] * tt[None, :]), axis=0))
    return gate_mean(emf), float(-1 / lam.max())
def loop_echo(phi, r, w, h, sigma, t):
    """one closed loop (a can wall or a border ring): radius r, conductor width w (along the loop axis for a can) and thickness t"""
    Lr = mu0 * r * (math.log(8 * r / (0.2235 * (w + t))) - 2); R = 2 * math.pi * r / (sigma * t * w); tau = Lr / R
    return gate_mean(lambda tt: (phi ** 2 * I0 / Lr) / tau * np.exp(-tt / tau)), tau
def hatch_echo(Bz, area, p=1.0e-3, w=0.25e-3, t=35e-6):
    s = p; Lc = 2 * mu0 * s / math.pi * (math.log(s / (0.2235 * (w + t))) - 0.774); Rc = 4 * s / (SIG_CU * t * w); tau = Lc / Rc; n = area / p ** 2; phi = Bz * s * s
    return gate_mean(lambda tt: n * (phi ** 2 * I0 / Lc) / tau * np.exp(-tt / tau)), tau
if __name__ == "__main__":
    res = dict(status=__doc__.split("\n")[1], coil=dict(L_uH=round(L * 1e6, 1), I_A=round(I0, 2), dIdt_A_per_us=round(DIDT * 1e-6, 2)), zones={}, echoes=[], potting=[])
    for name, (c, a, z, nplanes) in BOARDS.items():
        cr = math.hypot(*c); ux = (c[0] / cr, c[1] / cr) if cr > 1 else (1.0, 0.0); near = (c[0] + ux[0] * a, c[1] + ux[1] * a, z) if name[:2] not in ("LR", "QA") else (a * ux[0] - 1, a * ux[1] - 1, z)
        for tag, P in (("centre", (c[0], c[1], z)), ("edge nearest the coil", near)):
            B = Bc(P)[0]; Bm = float(np.linalg.norm(B)); Bz = abs(float(B[2]))
            res["zones"].setdefault(name, {})[tag] = dict(at_mm=[round(v, 1) for v in P], B_peak_mT=round(Bm * I0 * 1e3, 3), dBdt_T_per_s=round(Bm * DIDT, 1),
                EMF_1cm2_flat_loop_V=round(Bz * DIDT * 1e-4, 3), M_1cm2_flat_loop_nH=round(Bz * 1e-4 * 1e9, 4), current_step_equal_to_gate_noise_uA=round(NOISE_GATE / (Bz * 1e-4 / 1e-6) * 1e6, 2) if Bz > 0 else None)
        print(name, json.dumps(res["zones"][name]), flush=True)
    # metal echoes
    def add(obj, where, v, tau, note="", tc=0.0039):
        # a fixed echo is a constant offset that the baseline removes; what remains is its DRIFT: resistivity 0.39 %/K (copper; Al 0.40) changes tau,
        # and the gate-mean of (1/tau) e^(-t/tau) moves by (t/tau - 1) per unit change of ln tau
        drift = v / NOISE_GATE * abs(GATE / tau - 1) * tc if tau > 0 else 0.0
        res["echoes"].append(dict(object=obj, where=where, tau_us=round(tau * 1e6, 3), V_gate=float(f"{v:.3g}"), x_gate_noise=float(f"{v / NOISE_GATE:.3g}"),
                                  drift_x_noise_per_K=float(f"{drift:.3g}"), note=note))
        print(f"{obj:60s} {where:28s} tau {tau*1e6:9.3f} us  V {v:9.3g}  x noise {v / NOISE_GATE:9.3g}", flush=True)
    for name, (c, a, z, npl) in BOARDS.items():
        if npl == 0: continue
        rm, phi, w = flux_disc(c, a, z); v, tau = rings_echo(rm, phi, w, SIG_CU, 35e-6); add(f"{name}: one SOLID 35 um plane", name, v * npl, tau, f"x {npl} planes")
        vb, tb = loop_echo(float(phi.sum()), a * 1e-3, 0.5e-3, 0, SIG_CU, 35e-6); add(f"{name}: hatched plane with a CLOSED 0.5 mm border", name, vb * npl, tb)
        Bz = float(np.mean([Bc((c[0] + rr * math.cos(t), c[1] + rr * math.sin(t), z))[0][2] for rr in np.linspace(0, a, 5) for t in np.linspace(0, 6.28, 9)]))
        vh, th = hatch_echo(abs(Bz), math.pi * (a * 1e-3) ** 2); add(f"{name}: hatched 1.0 / 0.25 mm, border slit open", name, vh * npl, th)
    # objects
    for obj, (c, z, r, h, wt, sig, n) in {"aluminium electrolytic can 6.3 x 5.4 mm (wall 0.25 ASSUMED)": ((30.0, 0.0, 0), 9.0, 3.15, 5.4, 0.25, SIG_AL, 1),
                                         "same can at the analog boards": (deg(82, 120) + (0,), 8.0, 3.15, 5.4, 0.25, SIG_AL, 1)}.items():
        phi = float(Bc((c[0], c[1], z))[0][2]) * math.pi * (r * 1e-3) ** 2; v, tau = loop_echo(phi, r * 1e-3, h * 1e-3, 0, sig, wt * 1e-3); add(obj, f"r {math.hypot(c[0], c[1]):.0f}", v * n, tau)
    rm, phi, w = flux_disc((-76.0, 14.0), 3.4, 7.6, n_r=8); v, tau = rings_echo(rm, phi, w, SIG_CU, 0.5e-3); add("IXTY08N100D2 TO-252 tab (copper 6.5 x 6 x 0.5, as a disc)", "MP1", v, tau)
    v_led = 0.0; t_led = 0.0; res["led_rings"] = []
    for r in (104, 96, 88, 80, 72, 64, 56, 48, 40, 32, 24, 16, 8):
        n = max(1, int(round(2 * math.pi * r / 8))) if r > 8 else 6; rm, phi, w = flux_disc((r, 0.0), 1.1, 13.4, n_r=6); v, tau = rings_echo(rm, phi, w, SIG_CU, 0.2e-3); v_led += v * n; t_led = max(t_led, tau)
        res["led_rings"].append(dict(r_mm=r, leds=n, x_gate_noise=float(f"{v * n / NOISE_GATE:.3g}")))
    add("522 SK9822-EC20 lead frames (copper 2 x 2 x 0.2 mm, ASSUMED)", "display", v_led, t_led)
    rmax = 113.0; phi_sh = abs(float(flux_disc((0.0, 0.0), rmax, 1.4, n_r=40)[1].sum())); v, tau = loop_echo(phi_sh, rmax * 1e-3, 1.0e-3, 0, SIG_CU, 35e-6)
    add("SH1 shield: ONE outer ring left CLOSED (1 mm, no slit) - failure case", "SH1", v, tau, "rule 5: every SH1 ring has its slit")
    v, tau = loop_echo(phi_sh, rmax * 1e-3, 1.0e-3, 0, 1 / (1.6 * 25e-6), 25e-6); add("MG 841AR nickel paint, closed band 1 mm wide inside the shell (1.6 ohm/sq)", "shell", v, tau)
    # potting near the coil
    seq = TP.order(TP.sites(*TP.SHAPES["rect 5 x 6"]), "layered"); TP.EPS_R = 2.5; Cref, _ = TP.self_cap(seq); C_ext = 500e-12 - Cref
    for lab, eps in (("syntactic foam, glass bubbles (eps 1.8 UNVERIFIED)", 1.8), ("earlier assumption (eps 2.5)", 2.5), ("silicone gel (eps 2.8 UNVERIFIED)", 2.8),
                     ("MG 832TC epoxy (eps 3.7 at 1 MHz, DF 0.1; datasheet)", 3.7)):
        TP.EPS_R = eps; Cw, _ = TP.self_cap(seq); g = RD.gate_for(L, C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU, I0, Cn=C_ext + Cw)
        Bf = lambda P: C.B_turns(T, P); d = {f"{m} g": RC.depth(Bf, I0, g * 1e-6, m, Bf) for m in (0.1, 1.0, 20.0)}
        row = dict(potting=lab, eps_r=eps, C_winding_pF=round(Cw * 1e12, 1), C_node_pF=round((C_ext + Cw) * 1e12, 1), first_gate_us=g, mono_depth_mm=d); res["potting"].append(row); print(json.dumps(row), flush=True)
    TP.EPS_R = 2.5
    json.dump(res, open(os.path.join(OUT, "rf2_zones.json"), "w"), indent=1, default=float)
    # figure: |B| at the peak current over the board tier (z 6.4) and the echo budget
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw=dict(width_ratios=[1, 1.3]))
    g = np.linspace(-118, 118, 119); X, Y = np.meshgrid(g, g); P = np.c_[X.ravel(), Y.ravel(), np.full(X.size, 6.4)]; B = np.linalg.norm(Bc(P), axis=1).reshape(X.shape) * I0 * 1e3
    im = axs[0].pcolormesh(X, Y, np.log10(B), shading="auto", vmin=-0.5, vmax=1.5); fig.colorbar(im, ax=axs[0], label="log10 |B| (mT) at the peak current, z 6.4")
    for name, (c, a, z, n) in BOARDS.items():
        if name[:2] in ("LR", "QA"): continue
        axs[0].add_patch(plt.Circle(c, a, fill=False, color="w", lw=1)); axs[0].text(c[0], c[1], name.split(" ")[0], color="w", fontsize=7, ha="center")
    axs[0].set_aspect("equal"); axs[0].set_title("Option B board tier: transmit field at the peak current (MODELED)", fontsize=8)
    e = res["echoes"]; y = np.arange(len(e)); vals = [max(r["x_gate_noise"], 1e-6) for r in e]
    axs[1].barh(y, np.log10(vals), color=["#c62828" if v > 1 else "#2e7d32" for v in vals]); axs[1].axvline(0, color="k", lw=0.8)
    axs[1].set_yticks(y); axs[1].set_yticklabels([r["object"][:70] for r in e], fontsize=6); axs[1].invert_yaxis(); axs[1].set_xlabel("log10 (echo at the first gate / gate noise)")
    axs[1].set_title("Metal echoes into the mono at 16.3 us: red = visible above the noise", fontsize=8)
    fig.savefig(os.path.join(OUT, "rf2_zones.png"), dpi=130, bbox_inches="tight"); print("done")
