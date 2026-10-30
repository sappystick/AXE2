#!/usr/bin/env python3
"""RF2 step 7 (2026-10-29, owner idea): golden-angle petal coils in a THIN RING around the rim, stacked in layers up the 1-inch height, against the rim
mono. MODELED; same chain and fairness as rf2_receiver_combo.py: equal energy per pulse (10.8 mJ), the coil set is both transmitter and receiver (mono
style), preamp noise 1.7 nV/rtHz, first gate 16.3 us (rf2_timing.py, critically damped mono), gold spheres, noise-limited (no ground) and the severe-
ground multi-period balance of rf2_ground.py for the best candidates.

Petal set: N petals (round loops of radius a, n_t turns each, 1.6 mm litz pitch) whose centres sit on a ring of radius Rc = R_OUT - a (the ring is 2a
wide), petal k at azimuth k x 137.508 deg and on layer k mod n_layers (layers spread over the transmit window z 3.2-21.9 mm). All petals in series, same
sense. Orientations: FLAT (petal plane horizontal, axis vertical), RADIAL (petal standing up, axis pointing outward), TANGENTIAL (standing up, axis along
the rim). Inductance: Neumann double sum between all turns plus each turn's self term mu0 a (ln(8a / 0.6 mm) - 1.75).
usage: python3 rf2/rf2_petal_ring.py"""
import os, sys, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_coil_search as C
import rf2_receiver_combo as RC
GA = math.radians(137.50776); TF = 16.3e-6; NSEG = 48
def petal_paths(N, a, n_t, orient, n_layers):
    z0, z1 = C.Z_TX0, C.H_1IN - C.TOP_STACK; Rc = C.R_OUT - a; paths = []
    zl = [z0 + a + 1e-3 if orient != "flat" else z0 + 1e-3] if n_layers == 1 else list(np.linspace(z0 + 1e-3 + (a if orient != "flat" else 0), z1 - 1e-3 - (a if orient != "flat" else 0), n_layers))
    th = np.linspace(0, 2 * np.pi, NSEG + 1)
    for k in range(N):
        ph = k * GA; cx, cy = Rc * math.cos(ph), Rc * math.sin(ph); zc = zl[k % n_layers]
        er = np.array([math.cos(ph), math.sin(ph), 0.0]); et = np.array([-math.sin(ph), math.cos(ph), 0.0]); ez = np.array([0.0, 0.0, 1.0])
        u, v = {"flat": (er, et), "radial": (et, ez), "tangential": (er, ez)}[orient]
        for j in range(n_t):
            r = a - j * C.PITCH
            if r <= 3e-3: break
            pts = np.array([cx, cy, zc]) + np.outer(r * np.cos(th), u) + np.outer(r * np.sin(th), v)
            paths.append((pts, r))
    return paths
def L_paths(paths):
    """Neumann mutual between all turns + self term per turn (all in series, same sense)"""
    segs = [(np.diff(p, axis=0), (p[:-1] + p[1:]) / 2) for p, r in paths]; L = sum(C.mu0 * r * (math.log(8 * r / C.A_WIRE) - 1.75) for p, r in paths)
    for i in range(len(segs)):
        di, mi = segs[i]
        for j in range(i + 1, len(segs)):
            dj, mj = segs[j]; d = np.linalg.norm(mi[:, None, :] - mj[None, :, :], axis=2); L += 2 * 1e-7 * float(np.sum((di @ dj.T) / np.maximum(d, 0.5e-3)))
    return L
def evaluate(name, paths, masses=(1.0, 5.0, 20.0)):
    L = L_paths(paths); I = math.sqrt(2 * C.E0 / L); P = [p for p, r in paths]
    B = lambda X: C.B_paths(P, X)
    m = np.zeros(3)
    for p, r in paths: m += 0.5 * np.sum(np.cross(p[:-1], np.diff(p, axis=0)), axis=0)
    wire = sum(float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))) for p, r in paths)
    row = dict(name=name, turns=len(paths), litz_m=round(wire, 1), L_uH=round(L * 1e6), I_A=round(I, 2), moment_Am2=[round(float(x) * I, 3) for x in m],
               depth_mm={f"{g} g": RC.depth(B, I, TF, g, B) for g in masses})
    print(json.dumps(row), flush=True); return row, B, I
if __name__ == "__main__":
    t0 = time.time(); rows = []
    # reference: the rim mono of rf2_receiver_combo (26 turns, about 320 uH) as circular paths
    Tm = [(C.R_OUT - (j % 3) * C.PITCH, C.Z_TX0 + (j // 3) * C.PITCH, 1) for j in range(26)]; th = np.linspace(0, 2 * np.pi, 97)
    ref = [(np.c_[r * np.cos(th), r * np.sin(th), np.full(97, z)], r) for r, z, s in Tm]
    rows.append(evaluate("REFERENCE rim mono, 26 turns", ref)[0])
    for orient in ("flat", "radial", "tangential"):
        for N, a in ((6, 0.025), (13, 0.015), (8, 0.040)):
            for nl in (1, 6):
                n_t = max(2, int(round(26 * 2 * math.pi * C.R_OUT / (N * 2 * math.pi * a))))  # about the reference's litz length, so wire mass is comparable
                n_t = min(n_t, int(a / C.PITCH))
                paths = petal_paths(N, a, n_t, orient, nl)
                rows.append(evaluate(f"{orient} petals: N {N}, radius {a*1e3:.0f} mm, {n_t} turns each, {nl} layer(s), golden angle", paths)[0])
    res = dict(status="MODELED (RF2 step 7: golden-angle petal ring vs rim mono; equal energy per pulse; noise-limited, no ground)", first_gate_us=TF * 1e6, rows=rows,
               seconds=round(time.time() - t0, 1))
    json.dump(res, open(os.path.join(C.OUT, "rf2_petal_ring.json"), "w"), indent=1, default=float); print("done", res["seconds"])
