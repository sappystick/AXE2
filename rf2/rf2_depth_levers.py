#!/usr/bin/env python3
"""AXE2: MONO-channel depth (the detection channel) for the head-thickness options, and the levers that move it. MODELED, noise-limited, in air,
gold spheres, SNR 3 after averaging; same physics as rf2_receiver_combo (which modeled the mono at 345-356 mm for 1 g) and the same SDC 2300-class
8-inch mono in the same chain as a yardstick (ASSUMED internals: Minelab does not publish them).

Correction (2026-10-30, docs/CORRECTIONS.md): the 136 / 190 mm quoted for the thickness options came from rf2_coil_search.evaluate, which scores a
transmit coil through the QUADRUPOLE receive boards (the bearing / pinpoint channel, ground-cancelling and weak at depth), not through the mono.
This study scores the mono, and the depth grid is extended to 1.0 m (it stopped at 0.5 m, which capped 20 g at 500 mm).

Levers (one at a time from the option-B baseline):
  front-end noise   5.0 nV/rtHz (MP1 v1: 1.41 kohm protection + OPA2211), 1.7 (MP1 v2, decided), 1.2 (v2 + Schottky input clamp and Rin2 47 ohm, part
                    UNVERIFIED), 0.9 (two LMH6629 in parallel per input, ASSUMED: amplifier noise / sqrt 2, resistor noise unchanged)
  averaging         100 pulses per decision (0.25 s at 400 Hz) and 400 (1 s, or 1.6 kHz): SNR x sqrt(N)
  energy per pulse  10.8 mJ and 27 mJ (pinpoint boost x2.5, rf2_pinpoint): signal x sqrt(E)
  first gate        16.3 us (rf2_timing, as designed), 10 us, 8 us (needs a faster turn-off: study 2)
usage: python3 rf2/rf2_depth_levers.py  -> rf2/results/rf2_depth_levers.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C, rf2_receiver_combo as RC, rf2_thin as TH
C.DEPTHS = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])          # extended: 20 g reached the old 0.5 m limit
MASSES = (1.0, 5.0, 20.0); E0 = 10.8e-3; OUT = os.path.join(HERE, "results")


def mono_depth(T, gate_us, noise=1.7e-9, navg=100, energy=E0):
    Ls = C.L_turns(T); I = math.sqrt(2 * energy / Ls); Bm = lambda P, T=T: C.B_turns(T, P)
    RC.NOISE = noise; C.NAVG = navg
    d = {f"{g} g": RC.depth(Bm, I, gate_us * 1e-6, g, Bm) for g in MASSES}
    RC.NOISE = 1.7e-9; C.NAVG = 100
    return d, round(Ls * 1e6, 1), round(I, 2)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    res = dict(status="MODELED: mono (detection) channel, noise-limited in air, gold spheres, SNR 3; ASSUMED SDC internals; not a field depth",
               correction="the thickness study's 136 / 190 mm were the quadrupole (bearing) channel; see docs/CORRECTIONS.md", options={}, levers={})
    # thickness options on the mono channel, designed gate 16.3 us and MP1 v2 noise
    for o in TH.OPTIONS:
        T, rows, cols = TH.coil_for(o["coil_window_z"])
        d, L, I = mono_depth(T, 16.3)
        res["options"][o["name"]] = dict(height_mm=o["height_mm"], coil=f"{rows} x {cols}", L_uH=L, I_A=I, mono_depth_mm=d); print(o["name"], res["options"][o["name"]], flush=True)
    # yardstick: SDC 2300-class 8 in mono (rf2_receiver_combo's construction: 3-column bundle, turns until 300 uH), same chain
    n = 12
    mk = lambda r_out, n: [(r_out - (j % 3) * C.PITCH, C.Z_TX0 + (j // 3) * C.PITCH, 1) for j in range(n)]
    while C.L_turns(mk(0.1016 - 0.004, n)) < 300e-6: n += 1
    d, L, I = mono_depth(mk(0.1016 - 0.004, n), 16.3)
    res["sdc2300_class_same_chain"] = dict(turns=n, L_uH=L, mono_depth_mm=d); print("SDC-class", d, flush=True)
    # levers on option B (single tier, 5 x 6)
    TB, _, _ = TH.coil_for(TH.OPTIONS[1]["coil_window_z"])
    cases = [("MP1 v1 front end (5.0 nV/rtHz)", dict(noise=5.0e-9)), ("MP1 v2 (1.7 nV/rtHz): baseline", dict()),
             ("v2 + Schottky clamp, Rin2 47 ohm (1.2 nV/rtHz)", dict(noise=1.2e-9)), ("2 x LMH6629 per input (0.9 nV/rtHz)", dict(noise=0.9e-9)),
             ("averaging 400 pulses", dict(navg=400)), ("boost energy 27 mJ", dict(energy=27e-3)), ("first gate 10 us", dict(gate=10.0)), ("first gate 8 us", dict(gate=8.0)),
             ("combined: 0.9 nV + 400 pulses + 10 us", dict(noise=0.9e-9, navg=400, gate=10.0))]
    for nm, kw in cases:
        g = kw.pop("gate", 16.3); d, L, I = mono_depth(TB, g, **kw); res["levers"][nm] = dict(first_gate_us=g, mono_depth_mm=d); print(nm, d, flush=True)
    json.dump(res, open(os.path.join(OUT, "rf2_depth_levers.json"), "w"), indent=1)
