#!/usr/bin/env python3
"""AXE2 option B (owner 2026-10-30): can a coating, a 'sacrificial' pick-up coil or heavier receive copper protect the electronics from the transmit
pulse, and at what cost? MODELED; ASSUMED values are marked. Field and coil as rf2_zones (5 x 6 rim coil, 8.17 A, dI/dt 460 V / L).
  A. Coatings on a chip (thin spherical-shell shielding factor |B_out / B_in| at 100 kHz, the band of the turn-off edge, and the echo the coating adds
     at the first gate): ferrite-loaded paint mu' 10, 0.1 mm (UNVERIFIED typical of absorber paints); MG 841AR nickel paint 1.6 ohm/sq (datasheet);
     a 35 um copper can 4 x 4 x 1 mm; 0.1 mm mu-metal (mu_r 2e4, sigma 1.7e6 S/m, typical, UNVERIFIED). Shell radius 2 mm (a small IC).
       magnetic (mu >> 1): S = 1 + 2 mu t / (3 a);  eddy (thin conductor): S = |1 + j w mu0 a / (3 R_s)|;  echo: one loop of the shell's radius.
  B. A passive 'sacrificial' shorted loop around a zone (radius 10 mm, copper 0.5 mm x 35 um, at the AB1A edge nearest the coil): the field it removes
     at its centre, (mu0 pi a / 2 L) w tau / |1 + j w tau|, at 100 kHz, against its echo; the same loop with a series resistor that makes tau 0.1 us.
  C. The active version: a small counter-wound BUCKING loop wired in series with the transmit coil under each analog board (radius 16 mm, z 4.0, N turns
     chosen to null B_z at the board centre). Reported: the field at the board centre and at its edge nearest the coil, L, the current at 10.8 mJ and
     the mono depth (the loops also receive: transmit = receive path, so they are in Bt and Br).
  D. Receive-board copper (QA / QB: 16.99 m of 0.8 mm track each, sbq_geometry.json): resistance and thermal noise at 18 / 35 / 70 / 105 um, against an
     ASSUMED 1.7 nV/rtHz channel amplifier; depth scales about as SNR^(1/6) (1 / z^6 signal).
usage: python3 rf2/rf2_mitigation.py -> rf2/results/rf2_mitigation.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z, rf2_coil_search as C, rf2_rodin as RD, rf2_receiver_combo as RC
mu0 = C.mu0; OUT = os.path.join(HERE, "results"); F = 1e5; W = 2 * math.pi * F; NOISE = Z.NOISE_GATE; T = Z.T; I0 = Z.I0
AB1A = Z.deg(82, 106); EDGE = Z.deg(100, 106); ZB = 6.4
def echo_loop(Bz, r, w, t, sigma, tc=0.0039):
    phi = Bz * math.pi * r ** 2; v, tau = Z.loop_echo(phi, r, w, 0, sigma, t)
    return dict(tau_us=round(tau * 1e6, 4), x_gate_noise=float(f"{v / NOISE:.3g}"), drift_x_noise_per_K=float(f"{v / NOISE * abs(Z.GATE / tau - 1) * tc:.3g}"))
if __name__ == "__main__":
    res = dict(status=__doc__.split("\n")[1], coatings=[], sacrificial_loop=[], bucking=[], receive_copper=[])
    Bz_edge = float(Z.Bc((EDGE[0], EDGE[1], ZB))[0][2]); a = 2e-3
    for lab, S, echo in (("ferrite-loaded paint mu' 10, 0.1 mm (UNVERIFIED)", 1 + 2 * 10 * 0.1e-3 / (3 * a), None),
                         ("MG 841AR nickel paint, 25 um (1.6 ohm/sq)", abs(1 + 1j * W * mu0 * a / (3 * 1.6)), echo_loop(Bz_edge, a, 1e-3, 25e-6, 1 / (1.6 * 25e-6))),
                         ("copper can 35 um, 4 x 4 x 1 mm", abs(1 + 1j * W * mu0 * a / (3 / (Z.SIG_CU * 35e-6))), echo_loop(Bz_edge, a, 1e-3, 35e-6, Z.SIG_CU)),
                         ("mu-metal foil 0.1 mm (mu_r 2e4, UNVERIFIED)", 1 + 2 * 2e4 * 0.1e-3 / (3 * a), dict(tau_us=round(mu0 * 2e4 * 1.7e6 * (0.1e-3) ** 2 / math.pi ** 2 * 1e6, 1),
                          note="permeable AND conductive: diffusion time through the foil about 43 us (longer than the 16.3 us gate): a slow, strong target"))):
        row = dict(coating=lab, shielding_factor_100kHz=round(S, 4), field_reduction_pct=round(100 * (1 - 1 / S), 2), echo=echo); res["coatings"].append(row); print(json.dumps(row), flush=True)
    # B. passive shorted loop
    r, w, t = 10e-3, 0.5e-3, 35e-6; Lr = mu0 * r * (math.log(8 * r / (0.2235 * (w + t))) - 2); Rr = 2 * math.pi * r / (Z.SIG_CU * t * w)
    for lab, R in (("copper loop, shorted", Rr), ("same loop + series resistor (tau 0.1 us)", Lr / 1e-7)):
        tau = Lr / R; red = (mu0 * math.pi * r / (2 * Lr)) * abs(1j * W * tau / (1 + 1j * W * tau)); v, _ = Z.loop_echo(Bz_edge * math.pi * r ** 2, r, w, 0, Z.SIG_CU * Rr / R, t)
        row = dict(loop=lab, tau_us=round(tau * 1e6, 3), field_reduction_at_centre_pct_100kHz=round(100 * red, 1), echo_x_gate_noise=float(f"{v / NOISE:.3g}"),
                   drift_x_noise_per_K=float(f"{v / NOISE * abs(Z.GATE / tau - 1) * 0.0039:.3g}"))
        res["sacrificial_loop"].append(row); print(json.dumps(row), flush=True)
    # C. bucking loops in series (opposite sense) under AB1A and AB1B
    polys = RD.turn_polys(T); EPS = 0.465e-3
    def loop_poly(c, rad, z, n, sgn, ds=1.0):
        m = int(2 * math.pi * rad * 1e3 / ds); a_ = np.linspace(0, 2 * math.pi, m + 1)
        p = np.c_[c[0] * 1e-3 + rad * np.cos(a_), c[1] * 1e-3 + rad * np.sin(a_), np.full(m + 1, z * 1e-3)]
        return [p if sgn > 0 else p[::-1]] * n
    centres = [Z.deg(82, 106), Z.deg(82, 137)]; rad = 16e-3; zl = 4.0
    one = loop_poly(centres[0], rad, zl, 1, -1); Bl = C.B_paths(one, np.array([[centres[0][0] * 1e-3, centres[0][1] * 1e-3, ZB * 1e-3]]))[0][2]
    Bcen = float(Z.Bc((centres[0][0], centres[0][1], ZB))[0][2]); n_null = max(1, int(round(abs(Bcen / Bl))))
    for n in (0, max(1, n_null // 2), n_null):
        paths = polys + (sum((loop_poly(c, rad, zl, n, -1) for c in centres), []) if n else [])
        L = RD.neumann(paths, EPS) if n else C.L_turns(T); I = math.sqrt(2 * 10.8e-3 / L); Bf = RD.Field(paths)
        P = np.array([[centres[0][0], centres[0][1], ZB], [EDGE[0], EDGE[1], ZB]]) * 1e-3; B = Bf(P) * I * 1e3
        g = RD.gate_for(L, C.RHO_CU * RD.length(paths) / C.A_CU, I); d = {f"{m} g": RC.depth(Bf, I, g * 1e-6, m, Bf) for m in (0.1, 1.0, 20.0)}
        row = dict(bucking_turns_per_board=n, L_uH=round(L * 1e6, 1), I_A=round(I, 2), first_gate_us=g, B_mT_AB1A_centre=round(float(np.linalg.norm(B[0])), 3),
                   Bz_mT_AB1A_centre=round(float(B[0][2]), 3), B_mT_AB1A_edge_nearest_coil=round(float(np.linalg.norm(B[1])), 3), mono_depth_mm=d)
        res["bucking"].append(row); print(json.dumps(row), flush=True)
    # D. receive-board copper
    k, Tk, amp = 1.380649e-23, 300.0, 1.7e-9
    for t_um in (18, 35, 70, 105):
        R = C.RHO_CU * 16.99 / (0.8e-3 * t_um * 1e-6); en = math.sqrt(4 * k * Tk * R); tot = math.hypot(en, amp)
        res["receive_copper"].append(dict(copper_um=t_um, R_ohm=round(R, 2), thermal_nV=round(en * 1e9, 3), channel_total_nV=round(tot * 1e9, 3)))
    ref = next(r for r in res["receive_copper"] if r["copper_um"] == 35)["channel_total_nV"]
    for r in res["receive_copper"]: r["depth_change_pct_vs_35um"] = round(100 * ((ref / r["channel_total_nV"]) ** (1 / 6) - 1), 2)
    print(json.dumps(res["receive_copper"]), flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_mitigation.json"), "w"), indent=1, default=float); print("done")
