#!/usr/bin/env python3
"""AXE2 study (owner 2026-10-30): a tapered ("T-bone") rim coil former for option B, and the owner's progressive winding order.
MODELED; ASSUMED values are marked. Same footprint as option B's rim window: r 103.8-113.4 mm (7 grooves at 1.6 mm), z 4.4-12.6 mm (5 rows at 1.6 mm).

Former shapes (bundle cross-section in r-z, 26 turns, columns at 1.6 mm pitch inward from r 113.4):
  rect 5 x 6      option B as studied (rf2_thin)
  taper, wide top     rows bottom -> top 3 / 4 / 6 / 6 / 7 grooves, both sides sloped inward going down (centred on the window)   <- the owner's former
  taper, wide top, outer wall flush   same row counts, only the inner face slopes (keeps the large radius)
  taper, wide bottom  the reverse (7 / 6 / 6 / 4 / 3 from the bottom), outer wall flush, for comparison
Winding orders (how the 26 grooves are filled in sequence; sets the turn-to-turn voltages, hence self-capacitance and insulation stress):
  layered      row by row, back and forth (conventional)
  progressive  the owner's: per vertical channel (groove column), down every other groove, back up through the skipped ones, then the next channel
  bank         turn-by-turn zig-zag between two adjacent rows, advancing one groove each pair (classic low-capacitance bank winding)
Each order is run with the cold end (VBUS, AC ground) at the bottom, next to the receive / shield stack, and the hot (drain, 460 V flyback) end at the top.

Self-capacitance (energy method, low-frequency linear voltage along the winding; Massarini-Kazimierczuk style):
  C_w = sum over neighbour pairs C_ij (V_i - V_j)^2 / V^2 + sum over bottom-row turns C_g (V_i / V)^2
  turn-turn: two parallel round wires, wire diameter 1.2 mm (rf2_coil_search A_WIRE radius 0.6), centre spacing 1.6 (side) / 2.26 mm (diagonal, x 0.5
  for screening, ASSUMED), eps_r 2.5 (PETG former + enamel + air mix, ASSUMED); turn-plane: the nearest conductor plane is the top of the receive stack
  at z 3.2 mm (ASSUMED as AC ground).
Node capacitance: the timing model's 500 pF (sim_head1, ASSUMED) is taken as C_ext + C_w(rect 5 x 6, layered); C_ext is then held fixed and each
design gets C_ext + C_w. The first gate is computed with rf2_timing.simulate (A alone, critical damping, 100 nV clean + 2 us preamp recovery).
Depth: mono channel (rf2_depth_levers.mono_depth: 10.8 mJ, 1.7 nV/rtHz, 100 pulses, SNR 3, gold spheres, in air) at the computed gate.
usage: python3 rf2/rf2_taper.py -> rf2/results/rf2_taper.json, rf2/results/rf2_taper.png"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_coil_search as C, rf2_timing as TM, rf2_depth_levers as DL, rf2_thin as TH
OUT = os.path.join(HERE, "results"); P = 1.6; Z0, NROW = 4.4, 5; R_OUT = 113.4; NCOL = 7
MASSES = (0.1, 1.0, 5.0, 20.0); EPS0 = 8.854e-12; EPS_R = 2.5; A_W = 0.6; Z_GND = 3.2; C_NODE0 = 500e-12; V_FLY = 460.0
SHAPES = {"rect 5 x 6": ("flush", [6, 6, 6, 6, 2]),                        # bottom -> top; rf2_thin fills rows bottom-up, 6 columns, 26 turns
          "taper, wide top (owner), both faces sloped": ("centre", [3, 4, 6, 6, 7]),
          "taper, wide top, outer wall flush": ("flush", [3, 4, 6, 6, 7]),
          "taper, wide bottom, outer wall flush": ("flush", [7, 6, 6, 4, 3])}
def sites(align, counts):
    """grooves as (row, col) with col 0 at r 113.4; 'centre' centres each row on the 7-groove window"""
    S = []
    for row, n in enumerate(counts):
        c0 = (NCOL - n) // 2 if align == "centre" else 0
        S += [(row, c0 + k) for k in range(n)]
    return S
def order(S, how):
    S = sorted(S); rows = sorted({r for r, c in S}); cols = sorted({c for r, c in S})
    if how == "layered":                               # bottom row outward -> inward, next row back, ...
        o = []
        for i, r in enumerate(rows):
            rr = sorted([s for s in S if s[0] == r], key=lambda s: s[1], reverse=bool(i % 2)); o += rr
        return o
    if how == "progressive":                           # per groove column (outer first): from the top down every other groove, back up the skipped ones
        o = []
        for c in cols:
            col = sorted([s for s in S if s[1] == c], key=lambda s: -s[0]); o += col[0::2] + col[1::2][::-1]
        return o[::-1]                                 # wound so the sequence starts at the bottom (cold end at the bottom)
    if how == "bank":                                  # zig-zag between row pairs, advancing a groove each pair
        o = []
        for i in range(0, len(rows), 2):
            pair = rows[i:i + 2]; cs = sorted({c for r, c in S if r in pair}, reverse=bool((i // 2) % 2))
            for c in cs: o += [s for r in pair for s in S if s == (r, c)]
        return o
def geom(s, align_off=0.0): return (R_OUT - P * s[1]), (Z0 + P * (s[0] + 0.5))
def c_pair(D): return math.pi * EPS0 * EPS_R / math.acosh(D / (2 * A_W))                 # F/m, two parallel round wires
def self_cap(seq):
    n = len(seq); V = {s: k / (n - 1) for k, s in enumerate(seq)}; Cw = 0.0; dvmax = 0.0
    for i, a in enumerate(seq):
        ra, za = geom(a)
        for b in seq[i + 1:]:
            dr, dz = abs(a[1] - b[1]), abs(a[0] - b[0])
            if max(dr, dz) != 1: continue
            w = 1.0 if dr + dz == 1 else 0.5
            Cij = w * c_pair(P * math.hypot(dr, dz)) * 2 * math.pi * 1e-3 * (ra + geom(b)[0]) / 2
            Cw += Cij * (V[a] - V[b]) ** 2; dvmax = max(dvmax, abs(V[a] - V[b]) * V_FLY)
        if a[0] == 0:                                 # bottom row over the receive / shield stack
            h = za - Z_GND; Cw += 2 * math.pi * EPS0 * EPS_R / math.acosh(h / A_W) * 2 * math.pi * ra * 1e-3 * V[a] ** 2
    return Cw, dvmax
def first_gate(T, Cn):
    Ls = C.L_turns(T); I = math.sqrt(2 * C.E0 / Ls); R = C.RHO_CU * sum(2 * math.pi * r for r, z, s in T) / C.A_CU
    TM.A = dict(T=T, L=Ls, I=I, R=R); TM.CN = Cn
    return TM.simulate("A alone", "critical")["mono_clean_us"]
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); DL.MASSES = MASSES
    res = dict(status="MODELED: tapered rim former in option B's window; self-capacitance by the energy method (eps_r 2.5, plane at z 3.2, 500 pF node ASSUMED); "
                      "first gate by rf2_timing.simulate; mono depth by rf2_depth_levers.mono_depth (in air, gold spheres)", designs=[])
    rect = sites(*SHAPES["rect 5 x 6"]); Cref, _ = self_cap(order(rect, "layered")); C_EXT = C_NODE0 - Cref
    res["C_ext_pF"] = round(C_EXT * 1e12, 1); print("C_w(rect, layered)", round(Cref * 1e12, 1), "pF -> C_ext", round(C_EXT * 1e12, 1), flush=True)
    gate_cache = {}
    for shape, (align, counts) in SHAPES.items():
        S = sites(align, counts); T = [(geom(s)[0] * 1e-3, geom(s)[1] * 1e-3, 1) for s in S]
        Ls = C.L_turns(T); I = math.sqrt(2 * C.E0 / Ls); Bz = C.B_turns(T, np.array([[0, 0, -0.1], [0, 0, -0.3]]))[:, 2] * I * 1e6
        zc = float(np.mean([t[1] for t in T]) * 1e3); rc = float(np.mean([t[0] for t in T]) * 1e3)
        for how in ("layered", "progressive", "bank"):
            seq = order(S, how); Cw, dv = self_cap(seq); Cn = C_EXT + Cw; key = round(Cn * 1e14)
            g = first_gate(T, Cn); d, L, Ia = DL.mono_depth(T, g)
            row = dict(shape=shape, winding=how, rows_bottom_to_top=counts, L_uH=L, I_A=Ia, centroid_r_z_mm=[round(rc, 2), round(zc, 2)],
                       Bz_uT_100_300mm=[round(float(v), 2) for v in Bz], C_winding_pF=round(Cw * 1e12, 1), C_node_pF=round(Cn * 1e12, 1),
                       max_turn_to_turn_V=round(dv), first_gate_us=g, mono_depth_mm=d)
            res["designs"].append(row); print(json.dumps(row), flush=True)
    base = next(r for r in res["designs"] if r["shape"] == "rect 5 x 6" and r["winding"] == "layered")
    for r in res["designs"]: r["depth_vs_rect_layered_pct"] = {k: round(100 * (v / base["mono_depth_mm"][k] - 1), 1) for k, v in r["mono_depth_mm"].items()}
    json.dump(res, open(os.path.join(OUT, "rf2_taper.json"), "w"), indent=1)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 4, figsize=(13, 3.4), sharey=True)
    for ax, (shape, (align, counts)) in zip(axs, SHAPES.items()):
        S = sites(align, counts); seq = order(S, "progressive")
        for k, s in enumerate(seq):
            r, z = geom(s); ax.add_patch(plt.Circle((r, z), 0.6, color=plt.cm.plasma(k / 25))); ax.text(r, z, str(k + 1), ha="center", va="center", fontsize=5, color="w")
        ax.set_xlim(102.5, 114.5); ax.set_ylim(2.8, 13.2); ax.set_aspect("equal"); ax.axhline(Z_GND, color="#999", lw=0.8); ax.set_title(shape, fontsize=7); ax.set_xlabel("r (mm)")
    axs[0].set_ylabel("z (mm)"); fig.suptitle("Rim former cross-sections (MODELED), progressive winding order 1 (cold, bottom) -> 26 (hot); grey = receive stack top", fontsize=8)
    fig.savefig(os.path.join(OUT, "rf2_taper.png"), dpi=140, bbox_inches="tight")
